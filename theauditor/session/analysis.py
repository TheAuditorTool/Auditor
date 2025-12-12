"""SessionAnalysis - Unified session analysis pipeline.

Consolidated from analyzer.py and analysis.py. One class, one pipeline.
"""

import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from theauditor.session.activity_metrics import ActivityClassifier, ActivityMetrics
from theauditor.session.diff_scorer import DiffScorer
from theauditor.session.parser import Session
from theauditor.session.store import SessionExecution, SessionExecutionStore
from theauditor.session.workflow_checker import WorkflowChecker
from theauditor.utils.logging import logger

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


class SessionAnalysis:
    """Unified session analysis pipeline.

    Combines:
    - Pattern detection (blind edits, duplicate reads, etc.)
    - Diff scoring (security risk)
    - Workflow compliance checking
    - Activity classification (talk vs work vs planning)
    - Persistence to ML database
    """

    def __init__(
        self,
        db_path: Path = None,
        project_root: Path = None,
        workflow_path: Path | None = None,
    ):
        """Initialize session analysis."""
        self.project_root = project_root or Path.cwd()
        self.db_path = db_path or (self.project_root / ".pf" / "repo_index.db")
        self.workflow_path = workflow_path

        self.diff_scorer = DiffScorer(self.db_path, self.project_root)
        self.workflow_checker = WorkflowChecker(workflow_path)
        self.activity_classifier = ActivityClassifier()
        self.store = SessionExecutionStore()

        self.conn = None
        if self.db_path and Path(self.db_path).exists():
            self.conn = sqlite3.connect(self.db_path)

        logger.info("SessionAnalysis initialized")

    def analyze_session(self, session: Session) -> tuple[SessionExecution, ActivityMetrics]:
        """Analyze session: score diffs + check workflow + activity + store."""
        logger.info(f"Analyzing session: {session.session_id}")

        activity_metrics = self.activity_classifier.classify_session(session)

        files_read = set()
        for call in session.all_tool_calls:
            if call.tool_name == "Read":
                file_path = call.input_params.get("file_path")
                if file_path:
                    files_read.add(file_path)

        diff_scores = []
        for tool_call in session.all_tool_calls:
            if tool_call.tool_name in ["Edit", "Write"]:
                score = self.diff_scorer.score_diff(tool_call, files_read)
                if score:
                    diff_scores.append(score.to_dict())

        if diff_scores:
            avg_risk = sum(d["risk_score"] for d in diff_scores) / len(diff_scores)
        else:
            avg_risk = 0.0

        compliance = self.workflow_checker.check_compliance(session)

        task_completed = True
        corrections_needed = False
        rollback = False

        task_description = ""
        if session.user_messages:
            task_description = session.user_messages[0].content[:200]

        user_msg_count = len(session.user_messages)
        tool_call_count = len(session.all_tool_calls)
        user_engagement_rate = user_msg_count / max(tool_call_count, 1)

        files_modified = len(session.files_touched.get("Edit", [])) + len(
            session.files_touched.get("Write", [])
        )

        execution = SessionExecution(
            session_id=session.session_id,
            task_description=task_description,
            workflow_compliant=compliance.compliant,
            compliance_score=compliance.score,
            risk_score=avg_risk,
            task_completed=task_completed,
            corrections_needed=corrections_needed,
            rollback=rollback,
            timestamp=session.assistant_messages[0].datetime.isoformat()
            if session.assistant_messages
            else "",
            tool_call_count=tool_call_count,
            files_modified=files_modified,
            user_message_count=user_msg_count,
            user_engagement_rate=user_engagement_rate,
            diffs_scored=diff_scores,
        )

        self.store.store_execution(execution)

        logger.info(
            f"Session analysis complete: "
            f"risk={avg_risk:.2f}, compliance={compliance.score:.2f}, "
            f"engagement={user_engagement_rate:.2f}, "
            f"planning={activity_metrics.planning_ratio:.1%}, "
            f"working={activity_metrics.working_ratio:.1%}, "
            f"research={activity_metrics.research_ratio:.1%}"
        )

        return execution, activity_metrics

    def analyze_session_with_findings(
        self, session: Session, comment_graveyard_path: Path = None
    ) -> tuple[SessionStats, list[Finding]]:
        """Analyze session and return stats + findings (for reports)."""
        stats = self._compute_stats(session)
        findings = []

        findings.extend(self._detect_blind_edits(session))
        findings.extend(self._detect_duplicate_reads(session))
        findings.extend(self._detect_missing_searches(session))
        findings.extend(self._detect_partial_batch_reads(session))
        findings.extend(self._detect_comment_hallucinations(session, comment_graveyard_path))

        if self.conn:
            findings.extend(self._detect_duplicate_implementations(session))

        return stats, findings

    def analyze_multiple_sessions(
        self, sessions: list
    ) -> tuple[list[SessionExecution], list[ActivityMetrics]]:
        """Analyze multiple sessions in batch."""
        logger.info(f"Analyzing {len(sessions)} sessions...")

        executions = []
        all_activity_metrics = []
        for i, session in enumerate(sessions, 1):
            try:
                execution, activity_metrics = self.analyze_session(session)
                executions.append(execution)
                all_activity_metrics.append(activity_metrics)

                if i % 10 == 0:
                    logger.info(f"Progress: {i}/{len(sessions)} sessions analyzed")
            except Exception as e:
                logger.error(f"Failed to analyze session {session.session_id}: {e}")
                continue

        logger.info(f"Batch analysis complete: {len(executions)} sessions analyzed")
        return executions, all_activity_metrics

    def analyze_multiple_sessions_with_findings(self, sessions: list[Session]) -> dict[str, Any]:
        """Analyze patterns across multiple sessions (for reports)."""
        all_findings = []
        all_stats = []

        for session in sessions:
            stats, findings = self.analyze_session_with_findings(session)
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

    def get_activity_summary(self, activity_metrics: list[ActivityMetrics]) -> dict:
        """Get aggregated activity summary across sessions."""
        if not activity_metrics:
            return {}

        total_planning = sum(m.planning_tokens for m in activity_metrics)
        total_working = sum(m.working_tokens for m in activity_metrics)
        total_research = sum(m.research_tokens for m in activity_metrics)
        total_conversation = sum(m.conversation_tokens for m in activity_metrics)
        total_all = total_planning + total_working + total_research + total_conversation

        return {
            "session_count": len(activity_metrics),
            "token_distribution": {
                "planning": total_planning,
                "working": total_working,
                "research": total_research,
                "conversation": total_conversation,
                "total": total_all,
            },
            "ratios": {
                "planning": total_planning / total_all if total_all > 0 else 0,
                "working": total_working / total_all if total_all > 0 else 0,
                "research": total_research / total_all if total_all > 0 else 0,
                "conversation": total_conversation / total_all if total_all > 0 else 0,
            },
            "averages": {
                "work_to_talk_ratio": (
                    sum(m.work_to_talk_ratio for m in activity_metrics) / len(activity_metrics)
                ),
                "tokens_per_edit": (
                    sum(m.tokens_per_edit for m in activity_metrics) / len(activity_metrics)
                ),
            },
        }

    def get_correlation_statistics(self) -> dict:
        """Get correlation statistics (workflow compliance vs outcomes)."""
        stats = self.store.get_statistics()

        if "compliant" in stats and "non_compliant" in stats:
            compliant_risk = stats["compliant"]["avg_risk_score"]
            non_compliant_risk = stats["non_compliant"]["avg_risk_score"]

            if non_compliant_risk > 0:
                risk_reduction = (non_compliant_risk - compliant_risk) / non_compliant_risk
                stats["risk_reduction_pct"] = risk_reduction * 100
            else:
                stats["risk_reduction_pct"] = 0

            compliant_engagement = stats["compliant"]["avg_user_engagement"]
            non_compliant_engagement = stats["non_compliant"]["avg_user_engagement"]

            if non_compliant_engagement > 0:
                engagement_improvement = (
                    non_compliant_engagement - compliant_engagement
                ) / non_compliant_engagement
                stats["engagement_improvement_pct"] = engagement_improvement * 100
            else:
                stats["engagement_improvement_pct"] = 0

        return stats

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

        for call in session.all_tool_calls:
            file_path = call.input_params.get("file_path")
            if not file_path:
                continue

            if call.tool_name == "Read":
                files_read.add(file_path)

            elif call.tool_name == "Edit":
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

    def _detect_partial_batch_reads(self, session: Session) -> list[Finding]:
        """Detect when agent proceeds after partial batch read failures.

        This catches the critical anti-pattern where:
        1. Agent is asked to read multiple files (batch read)
        2. Some reads fail (file not found, permission denied, etc.)
        3. Agent proceeds with partial information instead of:
           - Acknowledging the failure
           - Searching for correct file paths
           - Asking for clarification

        This violates the Prime Directive: assumptions are forbidden,
        all beliefs must be verified before acting.
        """
        findings = []

        for i, assistant_msg in enumerate(session.assistant_messages):
            read_calls = [
                call for call in assistant_msg.tool_calls if call.tool_name == "Read"
            ]

            if len(read_calls) < 2:
                continue

            failed_reads = []
            successful_reads = []

            for read_call in read_calls:
                if read_call.result is None:
                    continue

                if read_call.failed:
                    failed_reads.append(read_call)
                else:
                    successful_reads.append(read_call)

            if not (failed_reads and successful_reads):
                continue

            # Check if agent proceeded without addressing failures
            has_subsequent_work = i + 1 < len(session.assistant_messages)

            if has_subsequent_work:
                next_msg = session.assistant_messages[i + 1]
                # Agent proceeded with work (not just asking about failure)
                proceeded_without_addressing = (
                    any(tc.tool_name in ["Edit", "Write"] for tc in next_msg.tool_calls)
                    or (
                        len(next_msg.text_content) > 100
                        and not any(
                            phrase in next_msg.text_content.lower()
                            for phrase in [
                                "could not read",
                                "file not found",
                                "failed to read",
                                "error reading",
                                "let me find",
                                "let me search",
                            ]
                        )
                    )
                )

                if proceeded_without_addressing:
                    failed_files = [
                        rc.input_params.get("file_path", "unknown")
                        for rc in failed_reads
                    ]
                    findings.append(
                        Finding(
                            category="partial_batch_read",
                            severity="error",
                            title="Proceeded with incomplete information",
                            description=(
                                f"Batch read: {len(failed_reads)}/{len(read_calls)} reads failed. "
                                f"Agent proceeded with partial info instead of addressing failures."
                            ),
                            session_id=session.session_id,
                            timestamp=assistant_msg.timestamp,
                            evidence={
                                "total_reads": len(read_calls),
                                "successful_reads": len(successful_reads),
                                "failed_reads": len(failed_reads),
                                "failed_files": failed_files[:5],
                                "successful_files": [
                                    rc.input_params.get("file_path", "unknown")
                                    for rc in successful_reads
                                ][:5],
                            },
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

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
