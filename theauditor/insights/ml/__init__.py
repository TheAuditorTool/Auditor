"""ML module for TheAuditor - Clean architecture.

Public API:
- learn(): Train ML models from historical data
- suggest(): Generate predictions for workset files
- check_ml_available(): Check if ML dependencies are installed

Internal modules (exported for backwards compatibility):
- loaders: Historical data loading
- features: Database feature extraction
- intelligence: Smart parsing (journal + raw artifacts)
- models: Model operations
- cli: CLI orchestration
"""

# Primary CLI API
from .cli import learn, suggest

# Models API
from .models import (
    check_ml_available,
    build_feature_matrix,
    build_labels,
    train_models,
    save_models,
    load_models,
    is_source_file,
    extract_text_features,
    fowler_noll_hash,
)

# Loaders API
from .loaders import (
    load_journal_stats,
    load_rca_stats,
    load_ast_stats,
    load_git_churn,
)

# Features API
from .features import (
    load_graph_stats,
    load_semantic_import_features,
    load_ast_complexity_metrics,
)

__all__ = [
    # CLI API
    "learn",
    "suggest",
    # Models API
    "check_ml_available",
    "build_feature_matrix",
    "build_labels",
    "train_models",
    "save_models",
    "load_models",
    "is_source_file",
    "extract_text_features",
    "fowler_noll_hash",
    # Loaders API
    "load_journal_stats",
    "load_rca_stats",
    "load_ast_stats",
    "load_git_churn",
    # Features API
    "load_graph_stats",
    "load_semantic_import_features",
    "load_ast_complexity_metrics",
]
