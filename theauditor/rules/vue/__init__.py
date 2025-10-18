"""Vue.js-specific rule detectors for TheAuditor.

This package contains database-first rules for detecting Vue.js
anti-patterns, performance issues, and security vulnerabilities
across Options API, Composition API, Vuex, and Pinia.
"""

from .reactivity_analyze import find_vue_reactivity_issues
from .component_analyze import find_vue_component_issues
from .hooks_analyze import find_vue_hooks_issues
from .render_analyze import find_vue_render_issues
from .state_analyze import find_vue_state_issues
from .lifecycle_analyze import find_vue_lifecycle_issues

__all__ = [
    'find_vue_reactivity_issues',
    'find_vue_component_issues',
    'find_vue_hooks_issues',
    'find_vue_render_issues',
    'find_vue_state_issues',
    'find_vue_lifecycle_issues'
]