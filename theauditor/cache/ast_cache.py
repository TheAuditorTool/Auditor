"""AST cache management for improved parsing performance.

This module provides persistent caching for Abstract Syntax Trees,
avoiding repeated parsing of unchanged files.
"""


import json
from pathlib import Path
from typing import Any


class ASTCache:
    """Manages persistent AST caching for improved performance.
    
    This cache stores parsed AST trees keyed by file content hash,
    allowing us to skip re-parsing unchanged files. This provides
    significant performance improvements for large codebases.
    """

    def __init__(self, cache_dir: Path):
        """Initialize the AST cache.
        
        Args:
            cache_dir: Base directory for cache files
        """
        self.cache_dir = cache_dir / "ast_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "errors": 0
        }

    def get(self, key: str, context: dict[str, Any] = None) -> dict | None:
        """Get cached AST for a file by its hash.
        
        Args:
            key: SHA256 hash of the file content
            context: Additional context (unused for AST cache)
            
        Returns:
            Cached AST tree or None if not found
        """
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding='utf-8') as f:
                    self._stats["hits"] += 1
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                # Cache corrupted, return None
                self._stats["errors"] += 1
                return None

        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: dict, context: dict[str, Any] = None) -> None:
        """Store an AST tree in the cache.
        
        Args:
            key: SHA256 hash of the file content
            value: AST tree to cache (must be JSON serializable)
            context: Additional context (unused)
        """
        cache_file = self.cache_dir / f"{key}.json"
        try:
            # Only cache if tree is JSON serializable (dict), not a Tree object
            if isinstance(value, dict):
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(value, f)
                    self._stats["writes"] += 1

                # Check if eviction is needed after writing
                self._evict_if_needed()
        except (OSError, PermissionError, TypeError):
            # Cache write failed, non-critical
            self._stats["errors"] += 1

    def invalidate(self, key: str) -> None:
        """Invalidate cache entry for a specific file.
        
        Args:
            key: SHA256 hash of the file content
        """
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                cache_file.unlink()
            except (OSError, PermissionError):
                self._stats["errors"] += 1

    def clear_cache(self) -> None:
        """Clear all cached AST entries."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                except (OSError, PermissionError):
                    pass
        except OSError:
            pass

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        # Count cached files
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            self._stats["total_entries"] = len(cache_files)

            # Calculate cache size
            total_size = 0
            for f in cache_files:
                try:
                    total_size += f.stat().st_size
                except OSError:
                    pass
            self._stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
        except OSError:
            pass

        # Calculate hit rate
        total_requests = self._stats["hits"] + self._stats["misses"]
        if total_requests > 0:
            self._stats["hit_rate"] = round(self._stats["hits"] / total_requests * 100, 1)
        else:
            self._stats["hit_rate"] = 0

        return self._stats

    def get_cache_size(self) -> int:
        """Get total disk usage of AST cache.
        
        Returns:
            Total size in bytes
        """
        total = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    total += cache_file.stat().st_size
                except OSError:
                    pass
        except OSError:
            pass
        return total

    def _evict_if_needed(self, max_size_bytes: int = 1073741824, max_files: int = 20000) -> None:
        """Evict old cache entries if limits are exceeded.
        
        This prevents unbounded disk usage that could fill the entire drive.
        
        Args:
            max_size_bytes: Maximum cache size in bytes (default: 1GB = 1073741824 bytes)
            max_files: Maximum number of cached files (default: 20,000)
        """
        try:
            # Get all cache files sorted by modification time (oldest first)
            cache_files = []
            total_size = 0

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    stat = cache_file.stat()
                    cache_files.append((cache_file, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size
                except OSError:
                    continue

            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[1])

            # Check if we need to evict based on size
            if total_size > max_size_bytes:
                # Delete oldest files until we're under 80% of limit
                target_size = int(max_size_bytes * 0.8)
                for cache_file, _, file_size in cache_files:
                    if total_size <= target_size:
                        break
                    try:
                        cache_file.unlink()
                        total_size -= file_size
                        self._stats.setdefault("evicted", 0)
                        self._stats["evicted"] += 1
                    except (OSError, PermissionError):
                        pass

            # Check if we need to evict based on file count
            if len(cache_files) > max_files:
                # Delete oldest files until we have 80% of max
                target_count = int(max_files * 0.8)
                files_to_delete = len(cache_files) - target_count

                for cache_file, _, _ in cache_files[:files_to_delete]:
                    try:
                        cache_file.unlink()
                        self._stats.setdefault("evicted", 0)
                        self._stats["evicted"] += 1
                    except (OSError, PermissionError):
                        pass

        except OSError:
            # Non-critical - cache cleanup failed
            self._stats["errors"] += 1