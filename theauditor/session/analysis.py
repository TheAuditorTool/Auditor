"""SessionAnalysis - Orchestrate complete session analysis pipeline."""

import logging
from pathlib import Path

from theauditor.session.activity_metrics import ActivityClassifier, ActivityMetrics
from theauditor.session.diff_scorer import DiffScorer
from theauditor.session.parser import Session
from theauditor.session.store import SessionExecution, SessionExecutionStore
from theauditor.session.workflow_checker import WorkflowChecker

logger = logging.getLogger(__name__)


class SessionAnalysis:
    """Orchestrate complete session analysis pipeline."""

    def __init__(
        self, db_path: Path = None, project_root: Path = None, workflow_path: Path | None = None
    ):
        """Initialize session analysis orchestrator."""

        self.project_root = project_root or Path.cwd()
        self.db_path = db_path or (self.project_root / ".pf" / "repo_index.db")
        self.workflow_path = workflow_path

        self.diff_scorer = DiffScorer(self.db_path, self.project_root)
        self.workflow_checker = WorkflowChecker(workflow_path)
        self.activity_classifier = ActivityClassifier()

        self.store = SessionExecutionStore()

        logger.info("SessionAnalysis orchestrator initialized")

    def analyze_session(
        self, session: Session
    ) -> tuple[SessionExecution, ActivityMetrics]:
        """Analyze complete session: score diffs + check workflow + activity + store."""
        logger.info(f"Analyzing session: {session.session_id}")

        # Activity classification (talk vs work vs planning)
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
                    sum(m.work_to_talk_ratio for m in activity_metrics)
                    / len(activity_metrics)
                ),
                "tokens_per_edit": (
                    sum(m.tokens_per_edit for m in activity_metrics)
                    / len(activity_metrics)
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
