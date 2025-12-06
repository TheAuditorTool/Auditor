"""Session analysis for AI agent interactions."""

from theauditor.session.activity_metrics import (
    ActivityClassifier,
    ActivityMetrics,
    ActivityType,
    TurnClassification,
    analyze_activity,
    analyze_multiple_sessions,
)
from theauditor.session.analysis import (
    Finding,
    SessionAnalysis,
    SessionStats,
)
from theauditor.session.parser import (
    Session,
    SessionParser,
    load_project_sessions,
    load_session,
)

__all__ = [
    "Session",
    "SessionParser",
    "load_session",
    "load_project_sessions",
    "ActivityType",
    "ActivityMetrics",
    "ActivityClassifier",
    "TurnClassification",
    "analyze_activity",
    "analyze_multiple_sessions",
    "Finding",
    "SessionAnalysis",
    "SessionStats",
]
