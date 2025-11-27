"""AST Data Extraction Engine - Language-specific implementation modules.

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This package provides language-specific AST extraction implementations:

- Python: ast_extractors/python/ - Uses CPython ast module with FileContext
- JavaScript/TypeScript: ast_extractors/typescript_impl.py - Uses TypeScript Compiler API
- Tree-sitter: ast_extractors/treesitter_impl.py - DEPRECATED for JS/TS

CRITICAL: All extraction functions return data with 'line' numbers only.
The indexer layer adds file_path when storing to database.

Example flow:
  indexer/extractors/python.py:300
    → python_impl.extract_python_functions(context)  # Direct function call
    → python/core_extractors.py:112                  # Implementation
    → Returns [{"line": 42, "name": "foo", ...}]

WHY: Single source of truth for file paths, prevents architectural violations.
"""

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
