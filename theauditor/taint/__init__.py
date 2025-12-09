"""Taint analysis module - Schema-driven IFDS architecture."""

from .core import (
    TaintRegistry,
    deduplicate_paths,
    has_sanitizer_between,
    normalize_taint_path,
    trace_taint,
)
from .discovery import TaintDiscovery
from .ifds_analyzer import IFDSTaintAnalyzer
from .taint_path import TaintPath

__all__ = [
    "trace_taint",
    "TaintPath",
    "TaintRegistry",
    "normalize_taint_path",
    "has_sanitizer_between",
    "deduplicate_paths",
    "IFDSTaintAnalyzer",
    "TaintDiscovery",
]
