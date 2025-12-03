"""Session analysis for AI agent interactions."""

from theauditor.session.activity_metrics import (
    ActivityClassifier,
    ActivityMetrics,
    ActivityType,
    TurnClassification,
    analyze_activity,
    analyze_multiple_sessions,
)
from theauditor.session.parser import (
    Session,
    SessionParser,
    load_project_sessions,
    load_session,
)

__all__ = [
    # Parser
    "Session",
    "SessionParser",
    "load_session",
    "load_project_sessions",
    # Activity metrics
    "ActivityType",
    "ActivityMetrics",
    "ActivityClassifier",
    "TurnClassification",
    "analyze_activity",
    "analyze_multiple_sessions",
]
