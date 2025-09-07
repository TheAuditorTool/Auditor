"""React-specific rule detectors for TheAuditor.

This package contains semantic AST-based rules for detecting
React Hooks issues and other React-specific anti-patterns.
"""

from .hooks_analyzer import find_react_hooks_issues

__all__ = ['find_react_hooks_issues']