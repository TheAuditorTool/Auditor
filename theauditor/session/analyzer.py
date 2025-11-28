"""Analyze Claude Code sessions for patterns, anti-patterns, and optimization opportunities."""

import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .parser import Session

COMMENT_REFERENCE_PATTERNS = [
    r"(?:this|the|that)\s+comment\s+(?:says?|said|states?|stated|indicates?|indicated|explains?|explained|mentions?|mentioned|suggests?|suggested)",
    r"according\s+to\s+(?:the|this|that)\s+comment",
    r"(?:the|this)\s+comment\s+(?:at|on)\s+line\s+\d+",
    r"as\s+(?:the|this)\s+comment\s+(?:says?|notes?|explains?)",
    r"#\s*(?:the|this)\s+comment",
    r"the\s+(?:inline|block|doc)\s*comment",
    r'comment\s*["\']([^"\']+)["\']',
    r'comment:\s*["\']([^"\']+)["\']',
    r"(?:the|this)\s+(?:TODO|FIXME|NOTE|HACK|XXX)\s+(?:says?|indicates?|suggests?)",
]


COMPILED_COMMENT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in COMMENT_REFERENCE_PATTERNS]


@dataclass
class Finding:
    """Represents a session analysis finding."""

    category: str
    severity: str
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

    def analyze_session(
        self, session: Session, comment_graveyard_path: Path = None
    ) -> tuple[SessionStats, list[Finding]]:
        """Analyze a single session and return stats + findings."""
        stats = self._compute_stats(session)
        findings = []

        findings.extend(self._detect_blind_edits(session))
        findings.extend(self._detect_duplicate_reads(session))
        findings.extend(self._detect_missing_searches(session))
        findings.extend(self._detect_comment_hallucinations(session, comment_graveyard_path))

        if self.conn:
            findings.extend(self._detect_duplicate_implementations(session))
            findings.extend(self._detect_missed_existing_code(session))

        return stats, findings

    def _compute_stats(self, session: Session) -> SessionStats:
        """Compute basic statistics about the session."""
        tool_counts = Counter(call.tool_name for call in session.all_tool_calls)

        total_tokens = sum(
            msg.tokens_used.get("output_tokens", 0) for msg in session.assistant_messages
        )
        avg_tokens = (
            total_tokens / len(session.assistant_messages) if session.assistant_messages else 0
        )

        return SessionStats(
            total_turns=len(session.user_messages) + len(session.assistant_messages),
            user_messages=len(session.user_messages),
            assistant_messages=len(session.assistant_messages),
            tool_calls=len(session.all_tool_calls),
            files_read=tool_counts.get("Read", 0),
            files_written=tool_counts.get("Write", 0),
            files_edited=tool_counts.get("Edit", 0),
            bash_commands=tool_counts.get("Bash", 0),
            avg_tokens_per_turn=avg_tokens,
        )

    def _detect_blind_edits(self, session: Session) -> list[Finding]:
        """Detect Edit calls that were not preceded by Read on same file."""
        findings = []
        files_read = set()
        read_edit_pairs = []

        for call in session.all_tool_calls:
            file_path = call.input_params.get("file_path")
            if not file_path:
                continue

            if call.tool_name == "Read":
                files_read.add(file_path)
                read_edit_pairs.append((file_path, call.timestamp, "read"))

            elif call.tool_name == "Edit":
                read_edit_pairs.append((file_path, call.timestamp, "edit"))
                if file_path not in files_read:
                    findings.append(
                        Finding(
                            category="blind_edit",
                            severity="warning",
                            title="Edit without prior Read",
                            description=f"File {file_path} was edited without being read first",
                            session_id=session.session_id,
                            timestamp=call.timestamp,
                            evidence={"file": file_path, "tool_call_uuid": call.uuid},
                        )
                    )

        return findings

    def _detect_duplicate_reads(self, session: Session) -> list[Finding]:
        """Detect multiple Read calls on the same file."""
        findings = []
        read_counts = Counter()

        for call in session.all_tool_calls:
            if call.tool_name == "Read":
                file_path = call.input_params.get("file_path")
                if file_path:
                    read_counts[file_path] += 1

        for file_path, count in read_counts.items():
            if count > 3:
                findings.append(
                    Finding(
                        category="duplicate_read",
                        severity="info",
                        title="File read multiple times",
                        description=f"File {file_path} was read {count} times in one session",
                        session_id=session.session_id,
                        timestamp="",
                        evidence={"file": file_path, "read_count": count},
                    )
                )

        return findings

    def _detect_missing_searches(self, session: Session) -> list[Finding]:
        """Detect Write operations that could have benefited from prior Grep/Glob."""
        findings = []
        searches_done = False

        for call in session.all_tool_calls:
            if call.tool_name in ("Grep", "Glob", "Task"):
                searches_done = True
                break

        writes = [call for call in session.all_tool_calls if call.tool_name == "Write"]

        if writes and not searches_done:
            findings.append(
                Finding(
                    category="missing_search",
                    severity="info",
                    title="Files created without search",
                    description=f"{len(writes)} files created without prior search (Grep/Glob/Task)",
                    session_id=session.session_id,
                    timestamp=writes[0].timestamp,
                    evidence={"files_written": len(writes)},
                )
            )

        return findings

    def _detect_comment_hallucinations(
        self, session: Session, graveyard_path: Path = None
    ) -> list[Finding]:
        """Detect when AI references comments that may not match reality."""
        findings = []

        graveyard_by_file = defaultdict(list)
        if graveyard_path and Path(graveyard_path).exists():
            try:
                with open(graveyard_path, encoding="utf-8") as f:
                    graveyard = json.load(f)
                for entry in graveyard:
                    file_path = entry.get("file", "")
                    if file_path:
                        graveyard_by_file[file_path].append(entry)
            except (json.JSONDecodeError, OSError):
                pass

        files_read = set()
        for call in session.all_tool_calls:
            if call.tool_name == "Read":
                file_path = call.input_params.get("file_path")
                if file_path:
                    files_read.add(file_path)

        for msg in session.assistant_messages:
            text = msg.text_content
            if not text:
                continue

            comment_refs = []
            for pattern in COMPILED_COMMENT_PATTERNS:
                matches = pattern.finditer(text)
                for match in matches:
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end]

                    comment_refs.append(
                        {"pattern": match.group(0), "context": context, "position": match.start()}
                    )

            if not comment_refs:
                continue

            file_pattern = re.compile(r"[\w./\\-]+\.(?:py|js|ts|jsx|tsx|rs|go|java|c|cpp|h)")
            mentioned_files = set(file_pattern.findall(text))

            for ref in comment_refs:
                suspicious_files = []
                for file_path in mentioned_files:
                    normalized = file_path.replace("\\", "/")
                    if normalized in graveyard_by_file or file_path in graveyard_by_file:
                        suspicious_files.append(file_path)

                relevant_files = mentioned_files & files_read

                severity = "info"
                if graveyard_by_file and suspicious_files:
                    severity = "warning"

                concerning_patterns = [
                    r"comment\s+(?:is|was)\s+(?:wrong|incorrect|misleading|outdated)",
                    r"(?:actually|but|however).*(?:different|contrary|opposite)",
                    r"comment\s+(?:says?|said)\s+.{1,50}(?:but|however|actually)",
                ]
                for cp in concerning_patterns:
                    if re.search(cp, ref["context"], re.IGNORECASE):
                        severity = "warning"
                        break

                findings.append(
                    Finding(
                        category="comment_hallucination",
                        severity=severity,
                        title="AI referenced comment content",
                        description=f'AI interpreted comment: "{ref["pattern"][:50]}..."',
                        session_id=session.session_id,
                        timestamp=msg.timestamp,
                        evidence={
                            "reference_text": ref["pattern"],
                            "context": ref["context"][:200],
                            "mentioned_files": list(mentioned_files)[:5],
                            "files_with_removed_comments": suspicious_files[:5],
                            "files_read_in_session": list(relevant_files)[:5],
                        },
                    )
                )

        return findings

    def _detect_duplicate_implementations(self, session: Session) -> list[Finding]:
        """Detect if agent created code that already exists (requires DB)."""
        if not self.conn:
            return []

        findings = []
        cursor = self.conn.cursor()

        writes = [call for call in session.all_tool_calls if call.tool_name == "Write"]

        for write_call in writes:
            file_path = write_call.input_params.get("file_path", "")
            content = write_call.input_params.get("content", "")

            import re

            patterns = [r"def (\w+)\(", r"class (\w+)", r"function (\w+)\(", r"const (\w+) = "]

            created_symbols = set()
            for pattern in patterns:
                created_symbols.update(re.findall(pattern, content))

            for symbol in created_symbols:
                cursor.execute(
                    """
                    SELECT path, type FROM symbols
                    WHERE name = ? AND path != ?
                    LIMIT 5
                """,
                    (symbol, file_path),
                )

                existing = cursor.fetchall()
                if existing:
                    findings.append(
                        Finding(
                            category="duplicate_implementation",
                            severity="warning",
                            title=f'Symbol "{symbol}" already exists',
                            description=f"Created {symbol} in {file_path}, but similar symbols exist in {len(existing)} other files",
                            session_id=session.session_id,
                            timestamp=write_call.timestamp,
                            evidence={
                                "symbol": symbol,
                                "new_file": file_path,
                                "existing_locations": [{"path": p, "type": t} for p, t in existing],
                            },
                        )
                    )

        return findings

    def _detect_missed_existing_code(self, session: Session) -> list[Finding]:
        """Detect when agent should have found existing code but didn't."""
        if not self.conn:
            return []

        findings = []
        cursor = self.conn.cursor()

        user_keywords = set()
        for user_msg in session.user_messages:
            import re

            words = re.findall(r"\b[a-z_][a-z0-9_]{2,}\b", user_msg.content.lower())
            user_keywords.update(words)

        files_read = {
            call.input_params.get("file_path")
            for call in session.all_tool_calls
            if call.tool_name == "Read" and call.input_params.get("file_path")
        }

        for keyword in user_keywords:
            cursor.execute(
                """
                SELECT DISTINCT path FROM symbols
                WHERE name LIKE ?
                LIMIT 10
            """,
                (f"%{keyword}%",),
            )

            relevant_files = {row[0] for row in cursor.fetchall()}
            missed_files = relevant_files - files_read

            if missed_files and len(missed_files) <= 5:
                findings.append(
                    Finding(
                        category="missed_existing_code",
                        severity="info",
                        title=f'Relevant files for "{keyword}" not read',
                        description=f'User mentioned "{keyword}" but {len(missed_files)} relevant files were not examined',
                        session_id=session.session_id,
                        timestamp=session.user_messages[0].timestamp
                        if session.user_messages
                        else "",
                        evidence={"keyword": keyword, "missed_files": list(missed_files)[:5]},
                    )
                )

        return findings

    def analyze_multiple_sessions(self, sessions: list[Session]) -> dict[str, Any]:
        """Analyze patterns across multiple sessions."""
        all_findings = []
        all_stats = []

        for session in sessions:
            stats, findings = self.analyze_session(session)
            all_stats.append(stats)
            all_findings.extend(findings)

        finding_counts = Counter(f.category for f in all_findings)

        total_tool_calls = sum(s.tool_calls for s in all_stats)
        total_edits = sum(s.files_edited for s in all_stats)
        total_reads = sum(s.files_read for s in all_stats)

        return {
            "total_sessions": len(sessions),
            "total_findings": len(all_findings),
            "findings_by_category": dict(finding_counts),
            "aggregate_stats": {
                "total_tool_calls": total_tool_calls,
                "total_reads": total_reads,
                "total_edits": total_edits,
                "avg_tool_calls_per_session": total_tool_calls / len(sessions) if sessions else 0,
                "edit_to_read_ratio": total_edits / total_reads if total_reads > 0 else 0,
            },
            "top_findings": sorted(
                all_findings,
                key=lambda f: {"error": 3, "warning": 2, "info": 1}.get(f.severity, 0),
                reverse=True,
            )[:10],
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
