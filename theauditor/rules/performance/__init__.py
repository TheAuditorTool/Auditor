"""Performance-related rule definitions."""

from .perf_analyze import find_performance_issues

# Legacy imports for backward compatibility
find_queries_in_loops = find_performance_issues
find_inefficient_string_concatenation = find_performance_issues
find_expensive_operations_in_loops = find_performance_issues

__all__ = [
    'find_performance_issues',
    'find_queries_in_loops',
    'find_inefficient_string_concatenation',
    'find_expensive_operations_in_loops'
]