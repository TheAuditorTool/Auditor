"""Performance-related rule definitions."""

from .perf_analyze import analyze as find_performance_issues

__all__ = [
    "find_performance_issues",
]
