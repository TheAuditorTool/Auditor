"""TheAuditor AST-based rule definitions.

This package contains high-fidelity AST-based rules for detecting
security vulnerabilities, code quality issues, and anti-patterns.
"""

from .secrets import find_hardcoded_secrets
from .xss import find_xss_vulnerabilities
from .node import analyze as find_node_runtime_issues
from .typescript import find_typescript_type_issues
from .sql import (
    find_sql_injection,
    find_sql_safety_issues,
    find_multi_tenant_issues
)
from .security.api_auth_detector import find_missing_api_authentication
from .performance import (
    find_queries_in_loops,
    find_inefficient_string_concatenation,
    find_expensive_operations_in_loops,
    find_performance_issues
)

__all__ = [
    'find_hardcoded_secrets',
    'find_sql_injection',
    'find_sql_safety_issues',
    'find_multi_tenant_issues',
    'find_xss_vulnerabilities',
    'find_node_runtime_issues',
    'find_typescript_type_issues',
    'find_queries_in_loops',
    'find_inefficient_string_concatenation',
    'find_expensive_operations_in_loops',
    'find_missing_api_authentication',
]