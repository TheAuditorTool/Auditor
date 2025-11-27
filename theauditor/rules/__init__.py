"""TheAuditor AST-based rule definitions.

This package contains high-fidelity AST-based rules for detecting
security vulnerabilities, code quality issues, and anti-patterns.
"""

from .node import find_runtime_issues as find_node_runtime_issues
from .performance import find_performance_issues
from .secrets import find_hardcoded_secrets
from .security.api_auth_analyze import find_apiauth_issues
from .sql import find_multi_tenant_issues, find_sql_injection, find_sql_safety_issues
from .typescript import find_type_safety_issues
from .xss import find_all_xss_issues

__all__ = [
    "find_hardcoded_secrets",
    "find_sql_injection",
    "find_sql_safety_issues",
    "find_multi_tenant_issues",
    "find_all_xss_issues",
    "find_node_runtime_issues",
    "find_type_safety_issues",
    "find_performance_issues",
    "find_apiauth_issues",
]
