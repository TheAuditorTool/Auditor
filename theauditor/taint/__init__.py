"""Taint analysis module - Schema-driven refactored version.

This module has been refactored to use schema-driven architecture:
- Auto-generated memory cache from schema
- Database-driven source/sink discovery
- Unified CFG analysis

Backward compatibility is maintained through stub files during transition.
"""

# Core functionality
from .core import (
    trace_taint,
    TaintPath,
    save_taint_analysis,
    normalize_taint_path,
)

# New unified analyzer
from .analysis import TaintFlowAnalyzer

# New discovery system
from .discovery import TaintDiscovery

# Schema-driven cache adapter
from .schema_cache_adapter import SchemaMemoryCacheAdapter

# Stubs for backward compatibility (temporary)
from .database import (
    find_taint_sources,
    find_security_sinks,
    build_call_graph,
    get_containing_function,
)

from .sources import (
    TAINT_SOURCES,
    SECURITY_SINKS,
    SANITIZERS,
    IS_WINDOWS,
)

from .propagation import (
    has_sanitizer_between,
    deduplicate_paths,
)

from .registry import TaintRegistry

# Create module-level function for backward compatibility
_registry = TaintRegistry()
def is_sanitizer(function_name: str) -> bool:
    """Check if a function is a known sanitizer."""
    return _registry.is_sanitizer(function_name)

# Exports
__all__ = [
    # Core functions
    "trace_taint",
    "TaintPath",
    "save_taint_analysis",
    "normalize_taint_path",

    # New components
    "TaintFlowAnalyzer",
    "TaintDiscovery",
    "SchemaMemoryCacheAdapter",

    # Backward compatibility stubs
    "find_taint_sources",
    "find_security_sinks",
    "build_call_graph",
    "get_containing_function",
    "TAINT_SOURCES",
    "SECURITY_SINKS",
    "SANITIZERS",
    "IS_WINDOWS",
    "has_sanitizer_between",
    "deduplicate_paths",
    "is_sanitizer",
    "TaintRegistry",
]