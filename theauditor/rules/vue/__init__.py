"""Vue.js-specific rule detectors for TheAuditor.

This package contains AST-based rules for detecting
Vue reactivity issues and props mutation anti-patterns.
"""

from .reactivity_analyzer import find_vue_reactivity_issues

__all__ = ['find_vue_reactivity_issues']