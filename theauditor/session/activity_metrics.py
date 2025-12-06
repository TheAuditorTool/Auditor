"""ActivityMetrics - Classify and measure talk vs work vs planning in AI sessions.

Answers the question: "How much do we talk to the AI vs how much does it work vs plan?"
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from theauditor.session.parser import Session


class ActivityType(Enum):
    """Classification of turn activity."""

    PLANNING = "planning"
    WORKING = "working"
    RESEARCH = "research"
    CONVERSATION = "conversation"


WORKING_TOOLS = frozenset({"Edit", "Write", "Bash", "NotebookEdit"})
RESEARCH_TOOLS = frozenset({"Read", "Grep", "Glob", "Task", "WebFetch", "WebSearch"})
META_TOOLS = frozenset({"TodoWrite", "AskUserQuestion"})


@dataclass
class TurnClassification:
    """Classification of a single turn."""

    turn_index: int
    timestamp: datetime
    activity: ActivityType
    tokens: int
    duration_seconds: float
    tool_calls: list[str] = field(default_factory=list)
    is_user: bool = False
    text_length: int = 0


@dataclass
class ActivityMetrics:
    """Aggregated activity metrics for a session."""

    total_turns: int = 0
    planning_turns: int = 0
    working_turns: int = 0
    research_turns: int = 0
    conversation_turns: int = 0

    total_tokens: int = 0
    planning_tokens: int = 0
    working_tokens: int = 0
    research_tokens: int = 0
    conversation_tokens: int = 0

    total_duration: float = 0.0
    planning_duration: float = 0.0
    working_duration: float = 0.0
    research_duration: float = 0.0
    conversation_duration: float = 0.0

    planning_ratio: float = 0.0
    working_ratio: float = 0.0
    research_ratio: float = 0.0
    conversation_ratio: float = 0.0

    planning_token_ratio: float = 0.0
    working_token_ratio: float = 0.0
    research_token_ratio: float = 0.0
    conversation_token_ratio: float = 0.0

    work_to_talk_ratio: float = 0.0
    research_to_work_ratio: float = 0.0
    tokens_per_edit: float = 0.0

    turn_classifications: list[TurnClassification] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes turn_classifications for brevity)."""
        return {
            "total_turns": self.total_turns,
            "planning_turns": self.planning_turns,
            "working_turns": self.working_turns,
            "research_turns": self.research_turns,
            "conversation_turns": self.conversation_turns,
            "total_tokens": self.total_tokens,
            "planning_tokens": self.planning_tokens,
            "working_tokens": self.working_tokens,
            "research_tokens": self.research_tokens,
            "conversation_tokens": self.conversation_tokens,
            "total_duration_seconds": self.total_duration,
            "planning_duration_seconds": self.planning_duration,
            "working_duration_seconds": self.working_duration,
            "research_duration_seconds": self.research_duration,
            "conversation_duration_seconds": self.conversation_duration,
            "planning_ratio": self.planning_ratio,
            "working_ratio": self.working_ratio,
            "research_ratio": self.research_ratio,
            "conversation_ratio": self.conversation_ratio,
            "planning_token_ratio": self.planning_token_ratio,
            "working_token_ratio": self.working_token_ratio,
            "research_token_ratio": self.research_token_ratio,
            "conversation_token_ratio": self.conversation_token_ratio,
            "work_to_talk_ratio": self.work_to_talk_ratio,
            "research_to_work_ratio": self.research_to_work_ratio,
            "tokens_per_edit": self.tokens_per_edit,
        }


class ActivityClassifier:
    """Classify session turns into activity types and compute metrics."""

    def __init__(self, planning_text_threshold: int = 200):
        """Initialize classifier.

        Args:
            planning_text_threshold: Min text length to classify as PLANNING
                                     when no tools are used.
        """
        self.planning_text_threshold = planning_text_threshold

    def classify_session(self, session: Session) -> ActivityMetrics:
        """Classify all turns in a session and compute metrics."""
        classifications = []

        all_turns = self._build_turn_sequence(session)

        for i, turn in enumerate(all_turns):
            if i < len(all_turns) - 1:
                next_turn = all_turns[i + 1]
                duration = (next_turn["timestamp"] - turn["timestamp"]).total_seconds()
                duration = max(0, min(duration, 3600))
            else:
                duration = 0.0

            classification = self._classify_turn(turn, i, duration)
            classifications.append(classification)

        return self._aggregate_metrics(classifications, session)

    def _build_turn_sequence(self, session: Session) -> list[dict[str, Any]]:
        """Build chronological sequence of all turns."""
        turns = []

        for msg in session.user_messages:
            turns.append(
                {
                    "type": "user",
                    "message": msg,
                    "timestamp": msg.datetime,
                    "tokens": 0,
                }
            )

        for msg in session.assistant_messages:
            tokens = msg.tokens_used.get("output_tokens", 0)
            turns.append(
                {
                    "type": "assistant",
                    "message": msg,
                    "timestamp": msg.datetime,
                    "tokens": tokens,
                }
            )

        turns.sort(key=lambda t: t["timestamp"])
        return turns

    def _classify_turn(
        self, turn: dict[str, Any], index: int, duration: float
    ) -> TurnClassification:
        """Classify a single turn."""
        msg = turn["message"]
        is_user = turn["type"] == "user"

        if is_user:
            return TurnClassification(
                turn_index=index,
                timestamp=turn["timestamp"],
                activity=ActivityType.CONVERSATION,
                tokens=0,
                duration_seconds=duration,
                tool_calls=[],
                is_user=True,
                text_length=len(msg.content) if hasattr(msg, "content") else 0,
            )

        tool_names = [tc.tool_name for tc in msg.tool_calls]
        text_length = len(msg.text_content) if msg.text_content else 0

        activity = self._classify_assistant_turn(tool_names, text_length)

        return TurnClassification(
            turn_index=index,
            timestamp=turn["timestamp"],
            activity=activity,
            tokens=turn["tokens"],
            duration_seconds=duration,
            tool_calls=tool_names,
            is_user=False,
            text_length=text_length,
        )

    def _classify_assistant_turn(self, tool_names: list[str], text_length: int) -> ActivityType:
        """Classify an assistant turn based on tools used and text length."""
        if not tool_names:
            if text_length >= self.planning_text_threshold:
                return ActivityType.PLANNING
            return ActivityType.CONVERSATION

        meaningful_tools = [t for t in tool_names if t not in META_TOOLS]

        if not meaningful_tools:
            if text_length >= self.planning_text_threshold:
                return ActivityType.PLANNING
            return ActivityType.CONVERSATION

        has_working = any(t in WORKING_TOOLS for t in meaningful_tools)
        has_research = any(t in RESEARCH_TOOLS for t in meaningful_tools)

        if has_working:
            return ActivityType.WORKING

        if has_research:
            return ActivityType.RESEARCH

        return ActivityType.WORKING

    def _aggregate_metrics(
        self, classifications: list[TurnClassification], session: Session
    ) -> ActivityMetrics:
        """Aggregate turn classifications into session metrics."""
        metrics = ActivityMetrics()
        metrics.turn_classifications = classifications
        metrics.total_turns = len(classifications)

        edit_count = sum(1 for tc in session.all_tool_calls if tc.tool_name in ("Edit", "Write"))

        for tc in classifications:
            if tc.activity == ActivityType.PLANNING:
                metrics.planning_turns += 1
                metrics.planning_tokens += tc.tokens
                metrics.planning_duration += tc.duration_seconds
            elif tc.activity == ActivityType.WORKING:
                metrics.working_turns += 1
                metrics.working_tokens += tc.tokens
                metrics.working_duration += tc.duration_seconds
            elif tc.activity == ActivityType.RESEARCH:
                metrics.research_turns += 1
                metrics.research_tokens += tc.tokens
                metrics.research_duration += tc.duration_seconds
            else:
                metrics.conversation_turns += 1
                metrics.conversation_tokens += tc.tokens
                metrics.conversation_duration += tc.duration_seconds

            metrics.total_tokens += tc.tokens
            metrics.total_duration += tc.duration_seconds

        if metrics.total_turns > 0:
            metrics.planning_ratio = metrics.planning_turns / metrics.total_turns
            metrics.working_ratio = metrics.working_turns / metrics.total_turns
            metrics.research_ratio = metrics.research_turns / metrics.total_turns
            metrics.conversation_ratio = metrics.conversation_turns / metrics.total_turns

        if metrics.total_tokens > 0:
            metrics.planning_token_ratio = metrics.planning_tokens / metrics.total_tokens
            metrics.working_token_ratio = metrics.working_tokens / metrics.total_tokens
            metrics.research_token_ratio = metrics.research_tokens / metrics.total_tokens
            metrics.conversation_token_ratio = metrics.conversation_tokens / metrics.total_tokens

        talk_tokens = metrics.planning_tokens + metrics.conversation_tokens
        if talk_tokens > 0:
            metrics.work_to_talk_ratio = metrics.working_tokens / talk_tokens

        if metrics.working_tokens > 0:
            metrics.research_to_work_ratio = metrics.research_tokens / metrics.working_tokens

        if edit_count > 0:
            metrics.tokens_per_edit = metrics.total_tokens / edit_count

        return metrics


def analyze_activity(session: Session) -> ActivityMetrics:
    """Convenience function to analyze a single session."""
    classifier = ActivityClassifier()
    return classifier.classify_session(session)


def analyze_multiple_sessions(sessions: list[Session]) -> dict[str, Any]:
    """Analyze activity patterns across multiple sessions."""
    classifier = ActivityClassifier()

    all_metrics = []
    for session in sessions:
        metrics = classifier.classify_session(session)
        all_metrics.append(metrics)

    if not all_metrics:
        return {}

    total_planning = sum(m.planning_tokens for m in all_metrics)
    total_working = sum(m.working_tokens for m in all_metrics)
    total_research = sum(m.research_tokens for m in all_metrics)
    total_conversation = sum(m.conversation_tokens for m in all_metrics)
    total_all = total_planning + total_working + total_research + total_conversation

    return {
        "session_count": len(all_metrics),
        "aggregate": {
            "total_tokens": total_all,
            "planning_tokens": total_planning,
            "working_tokens": total_working,
            "research_tokens": total_research,
            "conversation_tokens": total_conversation,
        },
        "ratios": {
            "planning": total_planning / total_all if total_all > 0 else 0,
            "working": total_working / total_all if total_all > 0 else 0,
            "research": total_research / total_all if total_all > 0 else 0,
            "conversation": total_conversation / total_all if total_all > 0 else 0,
        },
        "averages": {
            "planning_ratio": sum(m.planning_ratio for m in all_metrics) / len(all_metrics),
            "working_ratio": sum(m.working_ratio for m in all_metrics) / len(all_metrics),
            "research_ratio": sum(m.research_ratio for m in all_metrics) / len(all_metrics),
            "conversation_ratio": sum(m.conversation_ratio for m in all_metrics) / len(all_metrics),
            "work_to_talk_ratio": sum(m.work_to_talk_ratio for m in all_metrics) / len(all_metrics),
            "tokens_per_edit": sum(m.tokens_per_edit for m in all_metrics) / len(all_metrics),
        },
        "per_session": [m.to_dict() for m in all_metrics],
    }
