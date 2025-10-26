"""Code context query module.

This module provides direct database query interfaces for AI-assisted
code navigation and refactoring. NO inference, NO embeddings, NO guessing -
just exact SQL queries over TheAuditor's indexed data.

Architecture:
- CodeQueryEngine: Main query interface
- SymbolInfo/CallSite/Dependency: Typed result objects
- format_output: Output formatting (text, json, tree)
- Direct queries on repo_index.db and graphs.db

Performance:
- Query time: <50ms (indexed lookups)
- No caching needed (SQLite is fast enough)
- Transitive queries use BFS (max depth: 5)
"""

from theauditor.context.query import CodeQueryEngine, SymbolInfo, CallSite, Dependency
from theauditor.context.formatters import format_output

__all__ = ['CodeQueryEngine', 'SymbolInfo', 'CallSite', 'Dependency', 'format_output']
