"""XSS vulnerability detection rules module.

This module provides XSS detection across multiple contexts:
- DOM XSS (client-side sources to sinks)
- Template XSS (server-side template injection)
- Framework-specific XSS (React, Vue, Express)
- General XSS patterns

Each sub-module exports an `analyze` function that returns RuleResult.
"""

from .dom_xss_analyze import analyze as analyze_dom_xss
from .express_xss_analyze import analyze as analyze_express_xss
from .react_xss_analyze import analyze as analyze_react_xss
from .template_xss_analyze import analyze as analyze_template_xss
from .vue_xss_analyze import analyze as analyze_vue_xss
from .xss_analyze import analyze as analyze_xss

__all__ = [
    "analyze_dom_xss",
    "analyze_express_xss",
    "analyze_react_xss",
    "analyze_template_xss",
    "analyze_vue_xss",
    "analyze_xss",
]
