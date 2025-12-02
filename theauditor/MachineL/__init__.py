"""TheAuditor MachineL package - ML-based risk prediction and insights."""

from theauditor.MachineL.cli import learn, suggest
from theauditor.MachineL.impact_analyzer import (
    analyze_impact,
    calculate_transitive_impact,
    find_downstream_dependencies,
    find_upstream_dependencies,
    format_impact_report,
    trace_frontend_to_backend,
)
from theauditor.MachineL.models import (
    build_feature_matrix,
    build_labels,
    check_ml_available,
    is_source_file,
    load_models,
    save_models,
    train_models,
)

__all__ = [
    "learn",
    "suggest",
    "check_ml_available",
    "build_feature_matrix",
    "build_labels",
    "train_models",
    "save_models",
    "load_models",
    "is_source_file",
    "analyze_impact",
    "find_upstream_dependencies",
    "find_downstream_dependencies",
    "calculate_transitive_impact",
    "trace_frontend_to_backend",
    "format_impact_report",
]
