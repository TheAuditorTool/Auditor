"""Taint analysis module - refactored with backward compatibility.

This module maintains 100% backward compatibility while providing
a modular architecture for the taint analyzer.

All existing imports continue to work:
- from theauditor.taint_analyzer import trace_taint  # Still works via this module
- from theauditor.taint import trace_taint  # Also works
"""

# Import everything from the refactored modules
from .core import (
    trace_taint,
    TaintPath,
    save_taint_analysis,
    normalize_taint_path,
)

from .database import (
    find_taint_sources,
    find_security_sinks,
    build_call_graph,
    get_containing_function,
    get_function_boundaries,
    get_code_snippet,
    # Object literal resolution (v1.2+)
    resolve_object_literal_properties,
    find_dynamic_dispatch_targets,
    check_object_literals_available,
)

from .sources import (
    TAINT_SOURCES,
    SECURITY_SINKS,
    SANITIZERS,
    IS_WINDOWS,
)

from .propagation import (
    trace_from_source,
    # DELETED: trace_from_source_legacy - proximity-based algorithm removed (v1.2)
    # DELETED: is_sanitizer - moved to TaintRegistry.is_sanitizer() method
    has_sanitizer_between,
    # DELETED: is_external_source - string matching fallback removed
    deduplicate_paths,
)

# Import registry for backward compatibility
from .registry import TaintRegistry

# Create module-level function for backward compatibility
_registry = TaintRegistry()
def is_sanitizer(function_name: str) -> bool:
    """Check if a function is a known sanitizer (backward compatibility wrapper)."""
    return _registry.is_sanitizer(function_name)

from .interprocedural import (
    trace_inter_procedural_flow_insensitive,
    trace_inter_procedural_flow_cfg,
)

from .interprocedural_cfg import (
    InterProceduralCFGAnalyzer,
    InterProceduralEffect,
)

from .cfg_integration import (
    BlockTaintState,
    PathAnalyzer,
)

# DELETED: taint/javascript.py (375 lines) - All string parsing fallbacks removed
#
# Functions that existed:
#   - track_destructuring()
#   - track_spread_operators()
#   - track_bracket_notation()
#   - track_array_operations()
#   - track_type_conversions()
#   - enhance_javascript_tracking()
#
# These existed because indexer wasn't populating symbols with call/property types.
# Now that indexer is fixed, these fallbacks are CANCER.
#
# NEVER re-add this file. If JavaScript analysis is incomplete:
#   1. Check symbols table has call/property records
#   2. Add missing patterns to taint/sources.py
#   3. Fix indexer extraction

# DELETED: taint/python.py (473 lines) - All string parsing fallbacks removed
#
# Functions that existed:
#   - track_fstrings()
#   - track_comprehensions()
#   - track_unpacking()
#   - track_decorators()
#   - track_context_managers()
#   - track_string_operations()
#   - track_exception_propagation()
#   - enhance_python_tracking()
#
# Same reason as javascript.py - these existed because symbols table was empty.
# Now that indexer populates call/property symbols, these are unnecessary fallbacks.
#
# NEVER re-add this file. Python taint analysis works via database queries.

# Memory cache optimization (NEW!)
from .memory_cache import (
    MemoryCache,
    attempt_cache_preload,
)

# Re-export EVERYTHING to maintain backward compatibility
# This ensures that any code doing "from theauditor.taint_analyzer import X"
# will continue to work when we update taint/__init__.py to import from here
__all__ = [
    # Core functions
    "trace_taint",
    "TaintPath",
    "save_taint_analysis",
    "normalize_taint_path",
    
    # Database functions
    "find_taint_sources",
    "find_security_sinks",
    "build_call_graph",
    "get_containing_function",
    "get_function_boundaries",
    "get_code_snippet",

    # Object literal resolution (v1.2+)
    "resolve_object_literal_properties",
    "find_dynamic_dispatch_targets",
    "check_object_literals_available",
    
    # Constants
    "TAINT_SOURCES",
    "SECURITY_SINKS",
    "SANITIZERS",
    "IS_WINDOWS",
    
    # Propagation functions
    "trace_from_source",
    # DELETED: "trace_from_source_legacy" - proximity-based algorithm removed (v1.2)
    "is_sanitizer",
    "has_sanitizer_between",
    # DELETED: "is_external_source" - string matching fallback removed
    "deduplicate_paths",

    # Inter-procedural (flow-insensitive and CFG-based)
    "trace_inter_procedural_flow_insensitive",
    "trace_inter_procedural_flow_cfg",
    "InterProceduralCFGAnalyzer",
    "InterProceduralEffect",

    # CFG integration classes
    "BlockTaintState",
    "PathAnalyzer",

    # DELETED: JavaScript enhancements - taint/javascript.py removed (375 lines)
    # These functions were string parsing fallbacks:
    #   - track_destructuring
    #   - track_spread_operators
    #   - track_bracket_notation
    #   - track_array_operations
    #   - track_type_conversions
    #   - enhance_javascript_tracking

    # DELETED: Python enhancements - taint/python.py removed (473 lines)
    # These functions were string parsing fallbacks:
    #   - track_fstrings
    #   - track_comprehensions
    #   - track_unpacking
    #   - track_decorators
    #   - track_context_managers
    #   - track_string_operations
    #   - track_exception_propagation
    #   - enhance_python_tracking
    
    # Memory cache optimization (NEW!)
    "MemoryCache",
    "attempt_cache_preload",
]