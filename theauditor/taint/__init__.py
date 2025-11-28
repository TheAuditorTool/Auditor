"""Taint analysis module - Schema-driven IFDS architecture."""

from .core import (
    TaintRegistry,
    deduplicate_paths,
    has_sanitizer_between,
    normalize_taint_path,
    save_taint_analysis,
    trace_taint,
)
from .discovery import TaintDiscovery
from .ifds_analyzer import IFDSTaintAnalyzer
from .schema_cache_adapter import SchemaMemoryCacheAdapter
from .taint_path import TaintPath

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
