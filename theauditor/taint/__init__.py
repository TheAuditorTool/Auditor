"""Taint analysis module - Schema-driven IFDS architecture.

Clean architecture after stub removal:
- IFDS analyzer (Allen et al. 2021)
- Database-driven source/sink discovery (NO hardcoded patterns)
- Auto-generated schema cache
- ZERO FALLBACK POLICY enforced
"""

from .core import (
    trace_taint,
    TaintRegistry,
    save_taint_analysis,
    normalize_taint_path,
    has_sanitizer_between,
    deduplicate_paths,
)
from .taint_path import TaintPath


from .ifds_analyzer import IFDSTaintAnalyzer


from .discovery import TaintDiscovery


from .schema_cache_adapter import SchemaMemoryCacheAdapter


__all__ = [
    "trace_taint",
    "TaintPath",
    "TaintRegistry",
    "save_taint_analysis",
    "normalize_taint_path",
    "has_sanitizer_between",
    "deduplicate_paths",
    "IFDSTaintAnalyzer",
    "TaintDiscovery",
    "SchemaMemoryCacheAdapter",
]
