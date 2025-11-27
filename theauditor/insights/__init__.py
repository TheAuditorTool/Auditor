"""TheAuditor insights package - optional interpretive intelligence.

This package contains all optional scoring, classification, and
recommendation modules that add interpretation on top of facts.

The insights package follows the Truth Courier principle - all modules
here are OPTIONAL and add subjective analysis on top of objective facts.
The core audit pipeline works without any of these modules.

Modules:
  - ml: Machine learning predictions and risk scoring
  - graph: Architecture health metrics and recommendations
  - semantic_context: User-defined business logic and semantic understanding
  - impact_analyzer: Change blast radius and coupling analysis
"""

from theauditor.insights.ml import (
    check_ml_available,
    learn,
    suggest,
    build_feature_matrix,
    build_labels,
    train_models,
    save_models,
    load_models,
    is_source_file,
    load_journal_stats,
    load_rca_stats,
    load_ast_stats,
    load_graph_stats,
    load_git_churn,
    load_semantic_import_features,
    load_ast_complexity_metrics,
    extract_text_features,
    fowler_noll_hash,
)


from theauditor.insights.graph import (
    GraphInsights,
    check_insights_available,
    create_insights,
)


from theauditor.insights.semantic_context import (
    SemanticContext,
    ContextPattern,
    ClassificationResult,
    load_semantic_context,
)


from theauditor.insights.impact_analyzer import (
    analyze_impact,
    find_upstream_dependencies,
    find_downstream_dependencies,
    calculate_transitive_impact,
    trace_frontend_to_backend,
    format_impact_report,
)

__all__ = [
    "check_ml_available",
    "learn",
    "suggest",
    "build_feature_matrix",
    "build_labels",
    "train_models",
    "save_models",
    "load_models",
    "is_source_file",
    "load_journal_stats",
    "load_rca_stats",
    "load_ast_stats",
    "load_graph_stats",
    "load_git_churn",
    "load_semantic_import_features",
    "load_ast_complexity_metrics",
    "extract_text_features",
    "fowler_noll_hash",
    "GraphInsights",
    "check_insights_available",
    "create_insights",
    "SemanticContext",
    "ContextPattern",
    "ClassificationResult",
    "load_semantic_context",
    "analyze_impact",
    "find_upstream_dependencies",
    "find_downstream_dependencies",
    "calculate_transitive_impact",
    "trace_frontend_to_backend",
    "format_impact_report",
]
