"""Bash-specific security rules for shell script analysis."""

from .dangerous_patterns_analyze import analyze as find_dangerous_patterns
from .injection_analyze import analyze as find_injection_issues
from .quoting_analyze import analyze as find_quoting_issues

__all__ = [
    "find_injection_issues",
    "find_quoting_issues",
    "find_dangerous_patterns",
]
