"""Unified cache management for all TheAuditor components.

This module provides centralized cache management with a plugin architecture,
ensuring consistent invalidation and performance tracking across all components.
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod


class CacheProvider(Protocol):
    """Protocol for cache providers."""
    
    def get(self, key: str, context: Dict[str, Any]) -> Optional[Any]:
        """Get cached value."""
        ...
    
    def set(self, key: str, value: Any, context: Dict[str, Any]) -> None:
        """Store value in cache."""
        ...
    
    def invalidate(self, key: str) -> None:
        """Invalidate cache entry."""
        ...
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        ...
    
    def clear_cache(self) -> None:
        """Clear all cached entries."""
        ...


class UnifiedCacheManager:
    """Central cache management for TheAuditor.
    
    This provides a single entry point for all caching operations,
    coordinating between different cache providers and ensuring
    consistent behavior across the system.
    
    Benefits:
    - Single place to monitor cache performance
    - Consistent invalidation strategies
    - Shared configuration and limits
    - Easy to add new cache types
    """
    
    def __init__(self, cache_dir: Path = None):
        """Initialize the unified cache manager.
        
        Args:
            cache_dir: Base directory for all cache files.
                      Defaults to .pf/.cache/
        """
        if cache_dir is None:
            cache_dir = Path(".pf/.cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir
        
        # Registry of cache providers
        self.providers: Dict[str, CacheProvider] = {}
        
        # Initialize all cache providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize individual cache providers.
        
        This is called during construction to set up all available
        cache types. Each provider manages its own storage and
        invalidation logic.
        """
        # Import providers here to avoid circular imports
        try:
            from .ast_cache import ASTCache
            self.providers["ast"] = ASTCache(self.cache_dir)
        except ImportError:
            pass  # AST cache not yet moved
        
        try:
            from .pattern_cache import PatternCache
            self.providers["pattern"] = PatternCache(self.cache_dir)
        except ImportError:
            pass  # Pattern cache not yet created
        
        try:
            from .graph_cache import GraphCache
            self.providers["graph"] = GraphCache(self.cache_dir)
        except ImportError:
            pass  # Graph cache not yet created
        
        try:
            from .cfg_cache import CFGCacheManager
            self.providers["cfg"] = CFGCacheManager(
                str(self.cache_dir / "cfg_analysis_cache.db")
            )
        except ImportError:
            pass  # CFG cache not yet moved
    
    def get(self, cache_type: str, key: str, context: Dict = None) -> Optional[Any]:
        """Get value from specified cache.
        
        Args:
            cache_type: Type of cache to use ('ast', 'pattern', 'graph', 'cfg')
            key: Cache key (interpretation depends on cache type)
            context: Additional context for cache lookup (e.g., file paths)
        
        Returns:
            Cached value or None if not found
        """
        provider = self.providers.get(cache_type)
        if provider:
            return provider.get(key, context or {})
        return None
    
    def set(self, cache_type: str, key: str, value: Any, context: Dict = None) -> None:
        """Store value in specified cache.
        
        Args:
            cache_type: Type of cache to use
            key: Cache key
            value: Value to cache
            context: Additional context for caching
        """
        provider = self.providers.get(cache_type)
        if provider:
            provider.set(key, value, context or {})
    
    def invalidate(self, cache_type: str, key: str) -> None:
        """Invalidate specific cache entry.
        
        Args:
            cache_type: Type of cache
            key: Cache key to invalidate
        """
        provider = self.providers.get(cache_type)
        if provider:
            provider.invalidate(key)
    
    def invalidate_file(self, file_path: str) -> None:
        """Invalidate all caches for a specific file.
        
        This is useful when a file is modified and all related
        cache entries need to be cleared.
        
        Args:
            file_path: Path to the file that changed
        """
        # Each provider handles file invalidation differently
        for provider in self.providers.values():
            if hasattr(provider, 'invalidate_file'):
                provider.invalidate_file(file_path)
    
    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics from all caches.
        
        Returns:
            Dictionary mapping cache type to statistics
        """
        stats = {}
        for name, provider in self.providers.items():
            if hasattr(provider, 'get_stats'):
                stats[name] = provider.get_stats()
        return stats
    
    def clear_all(self) -> None:
        """Clear all caches.
        
        This is useful for testing or when cache corruption is suspected.
        """
        for provider in self.providers.values():
            if hasattr(provider, 'clear_cache'):
                provider.clear_cache()
    
    def register_provider(self, name: str, provider: CacheProvider) -> None:
        """Register a new cache provider.
        
        This allows dynamic addition of cache types.
        
        Args:
            name: Name for the cache type
            provider: Cache provider instance
        """
        self.providers[name] = provider
    
    def get_total_size(self) -> int:
        """Calculate total disk usage of all caches.
        
        Returns:
            Total size in bytes
        """
        total = 0
        
        # Check all cache files in the cache directory
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.rglob("*"):
                if cache_file.is_file():
                    try:
                        total += cache_file.stat().st_size
                    except OSError:
                        pass
        
        return total
    
    def print_summary(self) -> None:
        """Print a summary of cache statistics."""
        stats = self.get_stats()
        total_size = self.get_total_size()
        
        print("\n=== Cache Statistics ===")
        for cache_type, cache_stats in stats.items():
            print(f"\n{cache_type.upper()} Cache:")
            for key, value in cache_stats.items():
                print(f"  {key}: {value}")
        
        print(f"\nTotal cache size: {total_size / (1024*1024):.2f} MB")
        print("========================\n")


# Singleton instance for global access
_manager_instance: Optional[UnifiedCacheManager] = None


def get_cache_manager(cache_dir: Path = None) -> UnifiedCacheManager:
    """Get or create the global cache manager instance.
    
    Args:
        cache_dir: Cache directory (only used on first call)
    
    Returns:
        The global UnifiedCacheManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = UnifiedCacheManager(cache_dir)
    return _manager_instance