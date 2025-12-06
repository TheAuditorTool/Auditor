"""AST cache management for improved parsing performance."""

import json
import os
import random
from pathlib import Path
from typing import Any


class ASTCache:
    """Manages persistent AST caching for improved performance."""

    def __init__(self, cache_dir: Path):
        """Initialize the AST cache."""
        self.cache_dir = cache_dir / "ast_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, context: dict[str, Any] = None) -> dict | None:
        """Get cached AST for a file by its hash."""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def set(self, key: str, value: dict, context: dict[str, Any] = None) -> None:
        """Store an AST tree in the cache.

        Uses atomic write (temp file + rename) for crash safety.
        Probabilistic eviction (1% chance) to avoid O(N) stat overhead.
        """
        cache_file = self.cache_dir / f"{key}.json"
        temp_file = self.cache_dir / f"{key}.tmp"
        try:
            if isinstance(value, dict):
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(value, f)
                os.replace(temp_file, cache_file)

                if random.random() < 0.01:
                    self._evict_if_needed()
        except (OSError, PermissionError, TypeError):
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except OSError:
                pass

    def _evict_if_needed(self, max_size_bytes: int = 1073741824, max_files: int = 20000) -> None:
        """Evict old cache entries if limits are exceeded (1GB or 20k files)."""
        try:
            cache_files = []
            total_size = 0

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    stat = cache_file.stat()
                    cache_files.append((cache_file, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size
                except OSError:
                    continue

            cache_files.sort(key=lambda x: x[1])

            if total_size > max_size_bytes:
                target_size = int(max_size_bytes * 0.8)
                for cache_file, _, file_size in cache_files:
                    if total_size <= target_size:
                        break
                    try:
                        cache_file.unlink()
                        total_size -= file_size
                    except (OSError, PermissionError):
                        pass

            if len(cache_files) > max_files:
                target_count = int(max_files * 0.8)
                files_to_delete = len(cache_files) - target_count
                for cache_file, _, _ in cache_files[:files_to_delete]:
                    try:
                        cache_file.unlink()
                    except (OSError, PermissionError):
                        pass
        except OSError:
            pass
