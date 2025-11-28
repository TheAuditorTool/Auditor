"""ML module for TheAuditor - Clean architecture."""

from .cli import learn, suggest
from .features import (
    load_ast_complexity_metrics,
    load_comment_hallucination_features,
    load_graph_stats,
    load_semantic_import_features,
)
from .loaders import (
    load_ast_stats,
    load_git_churn,
    load_journal_stats,
    load_rca_stats,
)
from .models import (
    build_feature_matrix,
    build_labels,
    check_ml_available,
    extract_text_features,
    fowler_noll_hash,
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
    "extract_text_features",
    "fowler_noll_hash",
    "load_journal_stats",
    "load_rca_stats",
    "load_ast_stats",
    "load_git_churn",
    "load_graph_stats",
    "load_semantic_import_features",
    "load_ast_complexity_metrics",
    "load_comment_hallucination_features",
]
