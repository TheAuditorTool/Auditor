"""Bash-specific security rules for shell script analysis."""

from .dangerous_patterns_analyze import find_bash_dangerous_patterns
from .injection_analyze import find_bash_injection_issues
from .quoting_analyze import find_bash_quoting_issues

__all__ = [
    "find_bash_dangerous_patterns",
    "find_bash_injection_issues",
    "find_bash_quoting_issues",
]
