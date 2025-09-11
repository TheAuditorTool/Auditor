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

from .unified_manager import UnifiedCacheManager, get_cache_manager, CacheProvider
from .ast_cache import ASTCache
from .pattern_cache import PatternCache
from .graph_cache import GraphCache
from .cfg_cache import CFGCacheManager

__all__ = [
    'UnifiedCacheManager',
    'get_cache_manager',
    'CacheProvider',
    'ASTCache',
    'PatternCache',
    'GraphCache',
    'CFGCacheManager',
]

# Version for cache compatibility checks
__version__ = '1.0.0'