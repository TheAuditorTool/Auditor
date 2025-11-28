"""AST Data Extraction Engine - Language-specific implementation modules."""

from . import python as python_impl
from . import treesitter_impl, typescript_impl
from .base import detect_language

try:
    from ..js_semantic_parser import get_semantic_ast_batch
except ImportError:
    get_semantic_ast_batch = None

__all__ = [
    "python_impl",
    "typescript_impl",
    "treesitter_impl",
    "detect_language",
    "get_semantic_ast_batch",
]
