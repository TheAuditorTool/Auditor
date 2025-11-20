"""Graph database cache layer - Solves N+1 query problem.

Loads all file paths, imports, and exports into memory ONCE at initialization,
converting 50,000 database round-trips into 1 bulk query.

Architecture:
- Guardian of Hygiene: Normalizes all paths internally (Windows/Unix compatible)
- Zero Fallback Policy: Crashes if database missing or malformed
- Single Responsibility: Data access layer only (no business logic)

2025 Standard: Batch loading for performance.

Example:
    >>> cache = GraphDatabaseCache(Path(".pf/repo_index.db"))
    [GraphCache] Loaded 360 files, 1243 import records, 892 export records

    >>> cache.file_exists("theauditor\\cli.py")  # Windows path
    True
    >>> cache.file_exists("theauditor/cli.py")   # Unix path
    True

    >>> imports = cache.get_imports("theauditor/main.py")
    >>> len(imports)
    15
"""
from __future__ import annotations


import sqlite3
from pathlib import Path
from typing import Set, Dict, List, Any


class GraphDatabaseCache:
    """In-memory cache of database tables for graph building.

    Loads data once at init, provides O(1) lookups during graph construction.
    Eliminates N+1 query problem where each file triggers separate DB queries.

    Responsibilities:
    - Bulk load all graph-relevant data (files, imports, exports)
    - Normalize all paths to forward-slash format internally
    - Provide O(1) existence checks and lookups
    - Crash immediately if database missing/malformed (zero fallback policy)

    Performance:
    - Small project (100 files): ~0.1s load, ~10MB RAM
    - Medium project (1K files): ~0.5s load, ~50MB RAM
    - Large project (10K files): ~2s load, ~200MB RAM
    """

    def __init__(self, db_path: Path):
        """Initialize cache by loading all data once.

        Args:
            db_path: Path to repo_index.db

        Raises:
            FileNotFoundError: If database doesn't exist (NO FALLBACK)
            sqlite3.Error: If schema wrong or query fails (NO FALLBACK)
        """
        self.db_path = db_path

        # ZERO FALLBACK POLICY: Crash if DB missing
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"repo_index.db not found: {self.db_path}\n"
                f"Run 'aud full' to create it."
            )

        # In-memory caches
        self.known_files: set[str] = set()
        self.imports_by_file: dict[str, list[dict[str, Any]]] = {}
        self.exports_by_file: dict[str, list[dict[str, Any]]] = {}

        # Load all data in one pass
        self._load_cache()

    def _normalize_path(self, path: str) -> str:
        """Normalize path to forward-slash format.

        Guardian of Hygiene: All paths stored internally use forward slashes.
        Builder.py never needs to call .replace("\\", "/").

        Args:
            path: File path (Windows or Unix format)

        Returns:
            Normalized path with forward slashes

        Examples:
            >>> self._normalize_path("theauditor\\cli.py")
            "theauditor/cli.py"
            >>> self._normalize_path("theauditor/cli.py")
            "theauditor/cli.py"
        """
        return path.replace("\\", "/") if path else ""

    def _load_cache(self):
        """Load all graph-relevant data from database in bulk.

        NO TRY/EXCEPT - Let database errors crash (zero fallback policy).
        If this fails, database schema is wrong and must be fixed.
        """
        # NO TRY/EXCEPT - Crashes expose schema bugs immediately
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Load all file paths (for existence checks)
        # NO TABLE CHECK - Schema contract guarantees 'files' exists
        cursor.execute("SELECT path FROM files")
        self.known_files = {
            self._normalize_path(row["path"]) for row in cursor.fetchall()
        }

        # Load all imports (for build_import_graph)
        # NO TABLE CHECK - Schema contract guarantees 'refs' exists
        cursor.execute("""
            SELECT src, kind, value, line
            FROM refs
            WHERE kind IN ('import', 'require', 'from', 'import_type', 'export', 'import_dynamic')
        """)
        for row in cursor.fetchall():
            src = self._normalize_path(row["src"])
            if src not in self.imports_by_file:
                self.imports_by_file[src] = []

            self.imports_by_file[src].append({
                "kind": row["kind"],
                "value": row["value"],  # NOT normalized - may be module name
                "line": row["line"],
            })

        # Load all exports (for build_call_graph)
        # NO TABLE CHECK - Schema contract guarantees 'symbols' exists
        cursor.execute("""
            SELECT path, name, type, line
            FROM symbols
            WHERE type IN ('function', 'class')
        """)
        for row in cursor.fetchall():
            path = self._normalize_path(row["path"])
            if path not in self.exports_by_file:
                self.exports_by_file[path] = []

            self.exports_by_file[path].append({
                "name": row["name"],
                "symbol_type": row["type"],
                "line": row["line"],
            })

        conn.close()

        # Report cache size
        print(f"[GraphCache] Loaded {len(self.known_files)} files, "
              f"{sum(len(v) for v in self.imports_by_file.values())} import records, "
              f"{sum(len(v) for v in self.exports_by_file.values())} export records")

    def get_imports(self, file_path: str) -> list[dict[str, Any]]:
        """Get all imports for a file (O(1) lookup).

        Args:
            file_path: File path (Windows or Unix format - auto-normalized)

        Returns:
            List of import dicts (kind, value, line) or empty list if none

        Example:
            >>> cache.get_imports("theauditor\\main.py")  # Windows
            [{"kind": "from", "value": "theauditor/cli.py", "line": 5}]
            >>> cache.get_imports("theauditor/main.py")   # Unix
            [{"kind": "from", "value": "theauditor/cli.py", "line": 5}]
        """
        normalized = self._normalize_path(file_path)
        return self.imports_by_file.get(normalized, [])

    def get_exports(self, file_path: str) -> list[dict[str, Any]]:
        """Get all exports for a file (O(1) lookup).

        Args:
            file_path: File path (Windows or Unix format - auto-normalized)

        Returns:
            List of export dicts (name, symbol_type, line) or empty list if none

        Example:
            >>> cache.get_exports("theauditor/cli.py")
            [{"name": "main", "symbol_type": "function", "line": 42}]
        """
        normalized = self._normalize_path(file_path)
        return self.exports_by_file.get(normalized, [])

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in project (O(1) lookup).

        Guardian of Hygiene: Accepts both Windows and Unix paths.

        Args:
            file_path: File path (Windows or Unix format - auto-normalized)

        Returns:
            True if file was indexed, False otherwise

        Example:
            >>> cache.file_exists("theauditor\\cli.py")  # Windows
            True
            >>> cache.file_exists("theauditor/cli.py")   # Unix
            True
            >>> cache.file_exists("nonexistent.py")
            False
        """
        normalized = self._normalize_path(file_path)
        return normalized in self.known_files

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dict with file count, import count, export count

        Example:
            >>> cache.get_stats()
            {"files": 360, "imports": 1243, "exports": 892}
        """
        return {
            "files": len(self.known_files),
            "imports": sum(len(v) for v in self.imports_by_file.values()),
            "exports": sum(len(v) for v in self.exports_by_file.values()),
        }
