"""TheAuditor Cache Package.

This package provides unified caching infrastructure for all TheAuditor components.
It includes:
- Unified cache manager with plugin architecture
- AST caching for parsed syntax trees
- Pattern caching with version hashing
- Graph caching with incremental updates
- CFG caching for taint analysis

The unified architecture reduces analysis time from 30+ minutes to <8 minutes
on cached runs while maintaining correctness through intelligent invalidation.
"""

from .ast_cache import ASTCache

__all__ = [
    'ASTCache',
]