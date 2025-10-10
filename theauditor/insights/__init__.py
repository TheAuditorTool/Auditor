"""TheAuditor insights package - optional interpretive intelligence.

This package contains all optional scoring, classification, and
recommendation modules that add interpretation on top of facts.

The insights package follows the Truth Courier principle - all modules
here are OPTIONAL and add subjective analysis on top of objective facts.
The core audit pipeline works without any of these modules.

Modules:
  - ml: Machine learning predictions and risk scoring
  - graph: Architecture health metrics and recommendations
  - taint: Security vulnerability severity classification
  - semantic_context: User-defined business logic and semantic understanding
"""

# ML Insights - predictions and risk scoring
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

# Graph Insights - health metrics and recommendations  
from theauditor.insights.graph import (
    GraphInsights,
    check_insights_available,
    create_insights,
)

# Taint Insights - severity scoring and classification
from theauditor.insights.taint import (
    calculate_severity,
    classify_vulnerability,
    generate_summary,
    format_taint_report,
    get_taint_summary,
    is_vulnerable_sink,
)

# Semantic Context - user-defined business logic application
from theauditor.insights.semantic_context import (
    SemanticContext,
    ContextPattern,
    ClassificationResult,
    load_semantic_context,
)

__all__ = [
    # ML exports
    'check_ml_available',
    'learn',
    'suggest',
    'build_feature_matrix',
    'build_labels',
    'train_models',
    'save_models',
    'load_models',
    'is_source_file',
    'load_journal_stats',
    'load_rca_stats',
    'load_ast_stats',
    'load_graph_stats',
    'load_git_churn',
    'load_semantic_import_features',
    'load_ast_complexity_metrics',
    'extract_text_features',
    'fowler_noll_hash',
    # Graph exports
    'GraphInsights',
    'check_insights_available',
    'create_insights',
    # Taint exports
    'calculate_severity',
    'classify_vulnerability',
    'generate_summary',
    'format_taint_report',
    'get_taint_summary',
    'is_vulnerable_sink',
    # Semantic Context exports
    'SemanticContext',
    'ContextPattern',
    'ClassificationResult',
    'load_semantic_context',
]