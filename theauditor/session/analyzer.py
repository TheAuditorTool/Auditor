"""Analyze Claude Code sessions for patterns, anti-patterns, and optimization opportunities."""


import sqlite3
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from collections import Counter

from .parser import Session


@dataclass
class Finding:
    """Represents a session analysis finding."""
    category: str  # e.g., "duplicate_implementation", "blind_edit", "missed_search"
    severity: str  # "info", "warning", "error"
    title: str
    description: str
    session_id: str
    timestamp: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionStats:
    """Statistics about a session."""
    total_turns: int
    user_messages: int
    assistant_messages: int
    tool_calls: int
    files_read: int
    files_written: int
    files_edited: int
    bash_commands: int
    errors: int = 0
    avg_tokens_per_turn: float = 0.0


class SessionAnalyzer:
    """Analyze Claude Code sessions for patterns and opportunities."""

    def __init__(self, db_path: Path = None):
        """Initialize with optional path to repo_index.db for cross-referencing."""
        self.db_path = db_path
        self.conn = None
        if db_path and Path(db_path).exists():
            self.conn = sqlite3.connect(db_path)

    def analyze_session(self, session: Session) -> tuple[SessionStats, list[Finding]]:
        """Analyze a single session and return stats + findings."""
        stats = self._compute_stats(session)
        findings = []

        # Run all detectors
        findings.extend(self._detect_blind_edits(session))
        findings.extend(self._detect_duplicate_reads(session))
        findings.extend(self._detect_missing_searches(session))

        if self.conn:
            findings.extend(self._detect_duplicate_implementations(session))
            findings.extend(self._detect_missed_existing_code(session))

        return stats, findings

    def _compute_stats(self, session: Session) -> "SessionStats":
        """Compute basic statistics about the session."""
        tool_counts = Counter(call.tool_name for call in session.all_tool_calls)

        total_tokens = sum(
            msg.tokens_used.get('output_tokens', 0)
            for msg in session.assistant_messages
        )
        avg_tokens = total_tokens / len(session.assistant_messages) if session.assistant_messages else 0

        return SessionStats(
            total_turns=len(session.user_messages) + len(session.assistant_messages),
            user_messages=len(session.user_messages),
            assistant_messages=len(session.assistant_messages),
            tool_calls=len(session.all_tool_calls),
            files_read=tool_counts.get('Read', 0),
            files_written=tool_counts.get('Write', 0),
            files_edited=tool_counts.get('Edit', 0),
            bash_commands=tool_counts.get('Bash', 0),
            avg_tokens_per_turn=avg_tokens
        )

    def _detect_blind_edits(self, session: Session) -> list[Finding]:
        """Detect Edit calls that were not preceded by Read on same file."""
        findings = []
        files_read = set()
        read_edit_pairs = []

        for call in session.all_tool_calls:
            file_path = call.input_params.get('file_path')
            if not file_path:
                continue

            if call.tool_name == 'Read':
                files_read.add(file_path)
                read_edit_pairs.append((file_path, call.timestamp, 'read'))

            elif call.tool_name == 'Edit':
                read_edit_pairs.append((file_path, call.timestamp, 'edit'))
                if file_path not in files_read:
                    findings.append(Finding(
                        category='blind_edit',
                        severity='warning',
                        title='Edit without prior Read',
                        description=f'File {file_path} was edited without being read first',
                        session_id=session.session_id,
                        timestamp=call.timestamp,
                        evidence={'file': file_path, 'tool_call_uuid': call.uuid}
                    ))

        return findings

    def _detect_duplicate_reads(self, session: Session) -> list[Finding]:
        """Detect multiple Read calls on the same file."""
        findings = []
        read_counts = Counter()

        for call in session.all_tool_calls:
            if call.tool_name == 'Read':
                file_path = call.input_params.get('file_path')
                if file_path:
                    read_counts[file_path] += 1

        for file_path, count in read_counts.items():
            if count > 3:  # More than 3 reads is suspicious
                findings.append(Finding(
                    category='duplicate_read',
                    severity='info',
                    title='File read multiple times',
                    description=f'File {file_path} was read {count} times in one session',
                    session_id=session.session_id,
                    timestamp='',
                    evidence={'file': file_path, 'read_count': count}
                ))

        return findings

    def _detect_missing_searches(self, session: Session) -> list[Finding]:
        """Detect Write operations that could have benefited from prior Grep/Glob."""
        findings = []
        searches_done = False

        for call in session.all_tool_calls:
            if call.tool_name in ('Grep', 'Glob', 'Task'):
                searches_done = True
                break

        # Check if new files were created without search
        writes = [
            call for call in session.all_tool_calls
            if call.tool_name == 'Write'
        ]

        if writes and not searches_done:
            findings.append(Finding(
                category='missing_search',
                severity='info',
                title='Files created without search',
                description=f'{len(writes)} files created without prior search (Grep/Glob/Task)',
                session_id=session.session_id,
                timestamp=writes[0].timestamp,
                evidence={'files_written': len(writes)}
            ))

        return findings

    def _detect_duplicate_implementations(self, session: Session) -> list[Finding]:
        """Detect if agent created code that already exists (requires DB)."""
        if not self.conn:
            return []

        findings = []
        cursor = self.conn.cursor()

        # Get all Write operations
        writes = [
            call for call in session.all_tool_calls
            if call.tool_name == 'Write'
        ]

        for write_call in writes:
            file_path = write_call.input_params.get('file_path', '')
            content = write_call.input_params.get('content', '')

            # Extract function/class names from content (naive approach)
            import re
            patterns = [
                r'def (\w+)\(',  # Python functions
                r'class (\w+)',  # Python classes
                r'function (\w+)\(',  # JS functions
                r'const (\w+) = '  # JS const assignments
            ]

            created_symbols = set()
            for pattern in patterns:
                created_symbols.update(re.findall(pattern, content))

            # Check if these symbols exist elsewhere in codebase
            for symbol in created_symbols:
                cursor.execute("""
                    SELECT path, type FROM symbols
                    WHERE name = ? AND path != ?
                    LIMIT 5
                """, (symbol, file_path))

                existing = cursor.fetchall()
                if existing:
                    findings.append(Finding(
                        category='duplicate_implementation',
                        severity='warning',
                        title=f'Symbol "{symbol}" already exists',
                        description=f'Created {symbol} in {file_path}, but similar symbols exist in {len(existing)} other files',
                        session_id=session.session_id,
                        timestamp=write_call.timestamp,
                        evidence={
                            'symbol': symbol,
                            'new_file': file_path,
                            'existing_locations': [{'path': p, 'type': t} for p, t in existing]
                        }
                    ))

        return findings

    def _detect_missed_existing_code(self, session: Session) -> list[Finding]:
        """Detect when agent should have found existing code but didn't."""
        if not self.conn:
            return []

        findings = []
        cursor = self.conn.cursor()

        # Get keywords from user messages
        user_keywords = set()
        for user_msg in session.user_messages:
            # Extract potential symbol names (simple heuristic)
            import re
            words = re.findall(r'\b[a-z_][a-z0-9_]{2,}\b', user_msg.content.lower())
            user_keywords.update(words)

        # Check if agent read files related to these keywords
        files_read = {
            call.input_params.get('file_path')
            for call in session.all_tool_calls
            if call.tool_name == 'Read' and call.input_params.get('file_path')
        }

        # For each keyword, check if relevant files exist but weren't read
        for keyword in user_keywords:
            cursor.execute("""
                SELECT DISTINCT path FROM symbols
                WHERE name LIKE ?
                LIMIT 10
            """, (f'%{keyword}%',))

            relevant_files = {row[0] for row in cursor.fetchall()}
            missed_files = relevant_files - files_read

            if missed_files and len(missed_files) <= 5:  # Only report if reasonable number
                findings.append(Finding(
                    category='missed_existing_code',
                    severity='info',
                    title=f'Relevant files for "{keyword}" not read',
                    description=f'User mentioned "{keyword}" but {len(missed_files)} relevant files were not examined',
                    session_id=session.session_id,
                    timestamp=session.user_messages[0].timestamp if session.user_messages else '',
                    evidence={
                        'keyword': keyword,
                        'missed_files': list(missed_files)[:5]
                    }
                ))

        return findings

    def analyze_multiple_sessions(self, sessions: list[Session]) -> dict[str, Any]:
        """Analyze patterns across multiple sessions."""
        all_findings = []
        all_stats = []

        for session in sessions:
            stats, findings = self.analyze_session(session)
            all_stats.append(stats)
            all_findings.extend(findings)

        # Aggregate findings by category
        finding_counts = Counter(f.category for f in all_findings)

        # Compute aggregate stats
        total_tool_calls = sum(s.tool_calls for s in all_stats)
        total_edits = sum(s.files_edited for s in all_stats)
        total_reads = sum(s.files_read for s in all_stats)

        return {
            'total_sessions': len(sessions),
            'total_findings': len(all_findings),
            'findings_by_category': dict(finding_counts),
            'aggregate_stats': {
                'total_tool_calls': total_tool_calls,
                'total_reads': total_reads,
                'total_edits': total_edits,
                'avg_tool_calls_per_session': total_tool_calls / len(sessions) if sessions else 0,
                'edit_to_read_ratio': total_edits / total_reads if total_reads > 0 else 0
            },
            'top_findings': sorted(
                all_findings,
                key=lambda f: {'error': 3, 'warning': 2, 'info': 1}.get(f.severity, 0),
                reverse=True
            )[:10]
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
