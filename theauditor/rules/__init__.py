"""TheAuditor AST-based rule definitions.

This package contains high-fidelity AST-based rules for detecting
security vulnerabilities, code quality issues, and anti-patterns.
"""

from .secrets import find_hardcoded_secrets
from .xss import find_xss_vulnerabilities  
from .node import analyze as find_node_runtime_issues
from .typescript import find_typescript_type_issues
from .sql.sql_injection_analyzer import find_sql_injection
from .security.api_auth_detector import find_missing_api_authentication
from .performance.performance import (
    find_queries_in_loops,
    find_inefficient_string_concatenation,
    find_expensive_operations_in_loops
)

__all__ = [
    'find_hardcoded_secrets',
    'find_sql_injection',
    'find_xss_vulnerabilities',
    'find_node_runtime_issues',
    'find_typescript_type_issues',
    'find_queries_in_loops',
    'find_inefficient_string_concatenation',
    'find_expensive_operations_in_loops',
    'find_missing_api_authentication',
]