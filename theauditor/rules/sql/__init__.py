"""SQL security and safety rule definitions."""

from .multi_tenant_analyze import METADATA as multi_tenant_metadata
from .multi_tenant_analyze import analyze as multi_tenant_analyze
from .sql_injection_analyze import METADATA as sql_injection_metadata
from .sql_injection_analyze import analyze as sql_injection_analyze
from .sql_safety_analyze import METADATA as sql_safety_metadata
from .sql_safety_analyze import analyze as sql_safety_analyze

__all__ = [
    "sql_injection_analyze",
    "sql_injection_metadata",
    "multi_tenant_analyze",
    "multi_tenant_metadata",
    "sql_safety_analyze",
    "sql_safety_metadata",
]
