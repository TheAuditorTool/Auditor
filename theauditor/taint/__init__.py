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
)

from .sources import (
    TAINT_SOURCES,
    SECURITY_SINKS,
    SANITIZERS,
    IS_WINDOWS,
)

from .propagation import (
    trace_from_source,
    trace_from_source_legacy,
    is_sanitizer,
    has_sanitizer_between,
    is_external_source,
    deduplicate_paths,
)

from .interprocedural import (
    trace_inter_procedural_flow,
)

from .javascript import (
    track_destructuring,
    track_spread_operators,
    track_bracket_notation,
    track_array_operations,
    track_type_conversions,
    enhance_javascript_tracking,
)

from .python import (
    track_fstrings,
    track_comprehensions,
    track_unpacking,
    track_decorators,
    track_context_managers,
    track_string_operations,
    track_exception_propagation,
    enhance_python_tracking,
)

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
    
    # Constants
    "TAINT_SOURCES",
    "SECURITY_SINKS",
    "SANITIZERS",
    "IS_WINDOWS",
    
    # Propagation functions
    "trace_from_source",
    "trace_from_source_legacy",
    "is_sanitizer",
    "has_sanitizer_between",
    "is_external_source",
    "deduplicate_paths",
    
    # Inter-procedural
    "trace_inter_procedural_flow",
    
    # JavaScript enhancements
    "track_destructuring",
    "track_spread_operators",
    "track_bracket_notation",
    "track_array_operations",
    "track_type_conversions",
    "enhance_javascript_tracking",
    
    # Python enhancements (new!)
    "track_fstrings",
    "track_comprehensions",
    "track_unpacking",
    "track_decorators",
    "track_context_managers",
    "track_string_operations",
    "track_exception_propagation",
    "enhance_python_tracking",
    
    # Memory cache optimization (NEW!)
    "MemoryCache",
    "attempt_cache_preload",
]