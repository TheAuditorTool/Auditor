"""Taint analysis module - Schema-driven IFDS architecture.

Clean architecture after stub removal:
- IFDS analyzer (Allen et al. 2021)
- Database-driven source/sink discovery (NO hardcoded patterns)
- Auto-generated schema cache
- ZERO FALLBACK POLICY enforced
"""

# Core functionality
from .core import (
    trace_taint,
    TaintPath,
    TaintRegistry,          # Pattern accumulator (owned by taint/core.py)
    save_taint_analysis,
    normalize_taint_path,
    has_sanitizer_between,  # Moved from propagation.py
    deduplicate_paths,      # Moved from propagation.py
)

# Analyzers
from .analysis import TaintFlowAnalyzer
from .ifds_analyzer import IFDSTaintAnalyzer

# Discovery system (database-driven, NO hardcoded patterns)
from .discovery import TaintDiscovery

# Schema-driven cache adapter
from .schema_cache_adapter import SchemaMemoryCacheAdapter

# Exports (CLEAN - all stubs removed)
__all__ = [
    # Core functions
    "trace_taint",
    "TaintPath",
    "TaintRegistry",
    "save_taint_analysis",
    "normalize_taint_path",
    "has_sanitizer_between",
    "deduplicate_paths",

    # Analyzers
    "TaintFlowAnalyzer",
    "IFDSTaintAnalyzer",

    # Discovery
    "TaintDiscovery",

    # Cache
    "SchemaMemoryCacheAdapter",
]