"""TheAuditor AST-based rule definitions."""

from .bash import (
    find_dangerous_patterns as find_bash_dangerous_patterns,
)
from .bash import (
    find_injection_issues as find_bash_injection_issues,
)
from .bash import (
    find_quoting_issues as find_bash_quoting_issues,
)
from .node import find_runtime_issues as find_node_runtime_issues
from .performance import find_performance_issues
from .secrets import find_hardcoded_secrets
from .security.api_auth_analyze import find_apiauth_issues
from .sql import find_multi_tenant_issues, find_sql_injection_issues, find_sql_safety_issues
from .typescript import find_type_safety_issues
from .xss import find_all_xss_issues

__all__ = [
    "find_hardcoded_secrets",
    "find_sql_injection_issues",
    "find_sql_safety_issues",
    "find_multi_tenant_issues",
    "find_all_xss_issues",
    "find_node_runtime_issues",
    "find_type_safety_issues",
    "find_performance_issues",
    "find_apiauth_issues",
    "find_bash_injection_issues",
    "find_bash_quoting_issues",
    "find_bash_dangerous_patterns",
]
