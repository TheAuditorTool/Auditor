"""React-specific rule detectors for TheAuditor.

This package contains semantic AST-based rules for detecting
React component, hooks, rendering, and state management issues.

All rules follow the database-first architecture and use the
standardized rule interface (StandardRuleContext → List[StandardFinding]).
"""

from .component_analyze import analyze as find_react_component_issues
from .hooks_analyze import analyze as find_react_hooks_issues
from .render_analyze import analyze as find_react_render_issues
from .state_analyze import analyze as find_react_state_issues

__all__ = [
    'find_react_component_issues',
    'find_react_hooks_issues',
    'find_react_render_issues',
    'find_react_state_issues'
]
