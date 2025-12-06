"""GraphQL security rules.

Rules for detecting security vulnerabilities in GraphQL schemas and resolvers:
- Injection: SQL injection via GraphQL arguments
- Input validation: Missing validation on mutation arguments
- Mutation auth: Unprotected mutations
- N+1: Database queries inside loops
- Overfetch: Sensitive ORM fields not exposed but fetched
- Query depth: Unbounded nesting enabling DoS
- Sensitive fields: PII/secrets exposed in schema
"""

from .injection import METADATA as injection_metadata
from .injection import analyze as analyze_injection
from .input_validation import METADATA as input_validation_metadata
from .input_validation import analyze as analyze_input_validation
from .mutation_auth import METADATA as mutation_auth_metadata
from .mutation_auth import analyze as analyze_mutation_auth
from .nplus1 import METADATA as nplus1_metadata
from .nplus1 import analyze as analyze_nplus1
from .overfetch import METADATA as overfetch_metadata
from .overfetch import analyze as analyze_overfetch
from .query_depth import METADATA as query_depth_metadata
from .query_depth import analyze as analyze_query_depth
from .sensitive_fields import METADATA as sensitive_fields_metadata
from .sensitive_fields import analyze as analyze_sensitive_fields

__all__ = [
    "analyze_injection",
    "analyze_input_validation",
    "analyze_mutation_auth",
    "analyze_nplus1",
    "analyze_overfetch",
    "analyze_query_depth",
    "analyze_sensitive_fields",
    "injection_metadata",
    "input_validation_metadata",
    "mutation_auth_metadata",
    "nplus1_metadata",
    "overfetch_metadata",
    "query_depth_metadata",
    "sensitive_fields_metadata",
]
