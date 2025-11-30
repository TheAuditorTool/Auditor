"""AST Data Extraction Engine - Language-specific implementation modules."""

from . import python as python_impl
from .base import detect_language

try:
    from ..js_semantic_parser import get_semantic_ast_batch
except ImportError:
    get_semantic_ast_batch = None

__all__ = [
    "python_impl",
    "detect_language",
    "get_semantic_ast_batch",
]
