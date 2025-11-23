"""Backward compatibility shim for impact_analyzer module.

This module has been moved to theauditor.insights.impact_analyzer.
This shim maintains backward compatibility for existing imports.
"""

from theauditor.insights.impact_analyzer import (
    analyze_impact,
    find_upstream_dependencies,
    find_downstream_dependencies,
    calculate_transitive_impact,
    trace_frontend_to_backend,
    format_impact_report,
    classify_risk,
)

__all__ = [
    'analyze_impact',
    'find_upstream_dependencies',
    'find_downstream_dependencies',
    'calculate_transitive_impact',
    'trace_frontend_to_backend',
    'format_impact_report',
    'classify_risk',
]
