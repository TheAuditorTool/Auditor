"""GraphQL-specific security rules."""

from .injection import check_graphql_injection
from .input_validation import check_input_validation
from .mutation_auth import check_mutation_auth
from .nplus1 import check_graphql_nplus1
from .overfetch import check_graphql_overfetch
from .query_depth import check_query_depth
from .rate_limiting import check_rate_limiting
from .sensitive_fields import check_sensitive_fields

__all__ = [
    "check_mutation_auth",
    "check_query_depth",
    "check_input_validation",
    "check_sensitive_fields",
    "check_rate_limiting",
    "check_graphql_injection",
    "check_graphql_nplus1",
    "check_graphql_overfetch",
]
