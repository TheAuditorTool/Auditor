"""Graph database cache layer - Lazy loading with LRU cache.

Phase 0.2: Converted from eager loading (500k+ rows at startup) to on-demand
queries with bounded LRU cache. Memory usage drops from O(all_imports) to O(cache_size).

GRAPH FIX G7: Use MappingProxyType for immutable cached dicts.
"""

import sqlite3
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from theauditor.utils.logging import logger


class GraphDatabaseCache:
    """Lazy-loading cache of database tables for graph building.

    Uses @lru_cache for O(1) repeated lookups while keeping memory bounded.
    Only known_files is loaded eagerly (small set, needed for O(1) file_exists).
    """

    IMPORTS_CACHE_SIZE = 2000
    EXPORTS_CACHE_SIZE = 2000
    RESOLVE_CACHE_SIZE = 5000
    RESOLVED_IMPORTS_CACHE_SIZE = 2000

    def __init__(self, db_path: Path):
        """Initialize cache - only loads file list, imports/exports are lazy."""
        self.db_path = db_path

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"repo_index.db not found: {self.db_path}\nRun 'aud full' to create it."
            )

        self.known_files: set[str] = set()
        self._load_file_list()

    def _normalize_path(self, path: str) -> str:
        """Normalize path to forward-slash format."""
        return path.replace("\\", "/") if path else ""

    def _load_file_list(self):
        """Load only the file list - small and needed for O(1) file_exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT path FROM files")
        self.known_files = {self._normalize_path(row[0]) for row in cursor.fetchall()}

        conn.close()

        logger.info(f"[GraphCache] Loaded {len(self.known_files)} files (imports/exports: lazy)")

    @lru_cache(maxsize=IMPORTS_CACHE_SIZE)  # noqa: B019 - singleton, lives entire session
    def get_imports(self, file_path: str) -> tuple[MappingProxyType, ...]:
        """Get all imports for a file (lazy query with LRU cache).

        Returns tuple of immutable MappingProxyType instead of mutable dicts.
        GRAPH FIX G7: Prevents cache corruption from consumer modifications.
        """
        normalized = self._normalize_path(file_path)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT kind, value, line
            FROM refs
            WHERE src = ?
              AND kind IN ('import', 'require', 'from', 'import_type', 'export', 'dynamic_import')
        """,
            (normalized,),
        )

        results = tuple(
            MappingProxyType(
                {
                    "kind": row["kind"],
                    "value": row["value"],
                    "line": row["line"],
                }
            )
            for row in cursor.fetchall()
        )

        conn.close()
        return results

    @lru_cache(maxsize=RESOLVED_IMPORTS_CACHE_SIZE)  # noqa: B019 - singleton, lives entire session
    def get_resolved_imports(self, file_path: str) -> frozenset[str]:
        """Get pre-resolved import paths for a file from import_styles table.

        Returns frozenset of resolved paths (hashable for lru_cache).
        Only returns imports where resolved_path IS NOT NULL.
        """
        normalized = self._normalize_path(file_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT resolved_path
            FROM import_styles
            WHERE file = ?
              AND resolved_path IS NOT NULL
        """,
            (normalized,),
        )

        results = frozenset(self._normalize_path(row[0]) for row in cursor.fetchall())

        conn.close()
        return results

    @lru_cache(maxsize=EXPORTS_CACHE_SIZE)  # noqa: B019 - singleton, lives entire session
    def get_exports(self, file_path: str) -> tuple[MappingProxyType, ...]:
        """Get all exports for a file (lazy query with LRU cache).

        Returns tuple of immutable MappingProxyType instead of mutable dicts.
        GRAPH FIX G7: Prevents cache corruption from consumer modifications.
        """
        normalized = self._normalize_path(file_path)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name, type, line
            FROM symbols
            WHERE path = ?
              AND type IN ('function', 'class')
        """,
            (normalized,),
        )

        results = tuple(
            MappingProxyType(
                {
                    "name": row["name"],
                    "symbol_type": row["type"],
                    "line": row["line"],
                }
            )
            for row in cursor.fetchall()
        )

        conn.close()
        return results

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in project (O(1) lookup)."""
        normalized = self._normalize_path(file_path)
        return normalized in self.known_files

    @lru_cache(maxsize=RESOLVE_CACHE_SIZE)  # noqa: B019 - singleton, lives entire session
    def resolve_filename(self, path_guess: str) -> str | None:
        """Smart-resolve a path to an actual file in the DB, handling extensions."""
        clean = self._normalize_path(path_guess)

        if clean in self.known_files:
            return clean

        extensions = [".ts", ".tsx", ".js", ".jsx", ".d.ts", ".py"]

        for ext in extensions:
            candidate = clean + ext
            if candidate in self.known_files:
                return candidate

        for ext in extensions:
            candidate = f"{clean}/index{ext}"
            if candidate in self.known_files:
                return candidate

        return None

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        imports_info = self.get_imports.cache_info()
        exports_info = self.get_exports.cache_info()
        resolve_info = self.resolve_filename.cache_info()
        resolved_imports_info = self.get_resolved_imports.cache_info()

        return {
            "files": len(self.known_files),
            "imports_cache_hits": imports_info.hits,
            "imports_cache_misses": imports_info.misses,
            "imports_cache_size": imports_info.currsize,
            "exports_cache_hits": exports_info.hits,
            "exports_cache_misses": exports_info.misses,
            "exports_cache_size": exports_info.currsize,
            "resolve_cache_hits": resolve_info.hits,
            "resolve_cache_misses": resolve_info.misses,
            "resolved_imports_cache_hits": resolved_imports_info.hits,
            "resolved_imports_cache_misses": resolved_imports_info.misses,
        }

    def clear_caches(self):
        """Clear all LRU caches - useful for testing or memory pressure."""
        self.get_imports.cache_clear()
        self.get_exports.cache_clear()
        self.resolve_filename.cache_clear()
        self.get_resolved_imports.cache_clear()
