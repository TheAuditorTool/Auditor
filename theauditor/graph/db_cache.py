"""Graph database cache layer - Solves N+1 query problem."""

import sqlite3
from pathlib import Path
from typing import Any


class GraphDatabaseCache:
    """In-memory cache of database tables for graph building."""

    def __init__(self, db_path: Path):
        """Initialize cache by loading all data once."""
        self.db_path = db_path

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"repo_index.db not found: {self.db_path}\nRun 'aud full' to create it."
            )

        self.known_files: set[str] = set()
        self.imports_by_file: dict[str, list[dict[str, Any]]] = {}
        self.exports_by_file: dict[str, list[dict[str, Any]]] = {}

        self._load_cache()

    def _normalize_path(self, path: str) -> str:
        """Normalize path to forward-slash format."""
        return path.replace("\\", "/") if path else ""

    def _load_cache(self):
        """Load all graph-relevant data from database in bulk."""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT path FROM files")
        self.known_files = {self._normalize_path(row["path"]) for row in cursor.fetchall()}

        cursor.execute("""
            SELECT src, kind, value, line
            FROM refs
            WHERE kind IN ('import', 'require', 'from', 'import_type', 'export', 'dynamic_import')
        """)
        for row in cursor.fetchall():
            src = self._normalize_path(row["src"])
            if src not in self.imports_by_file:
                self.imports_by_file[src] = []

            self.imports_by_file[src].append(
                {
                    "kind": row["kind"],
                    "value": row["value"],
                    "line": row["line"],
                }
            )

        cursor.execute("""
            SELECT path, name, type, line
            FROM symbols
            WHERE type IN ('function', 'class')
        """)
        for row in cursor.fetchall():
            path = self._normalize_path(row["path"])
            if path not in self.exports_by_file:
                self.exports_by_file[path] = []

            self.exports_by_file[path].append(
                {
                    "name": row["name"],
                    "symbol_type": row["type"],
                    "line": row["line"],
                }
            )

        conn.close()

        print(
            f"[GraphCache] Loaded {len(self.known_files)} files, "
            f"{sum(len(v) for v in self.imports_by_file.values())} import records, "
            f"{sum(len(v) for v in self.exports_by_file.values())} export records"
        )

    def get_imports(self, file_path: str) -> list[dict[str, Any]]:
        """Get all imports for a file (O(1) lookup)."""
        normalized = self._normalize_path(file_path)
        return self.imports_by_file.get(normalized, [])

    def get_exports(self, file_path: str) -> list[dict[str, Any]]:
        """Get all exports for a file (O(1) lookup)."""
        normalized = self._normalize_path(file_path)
        return self.exports_by_file.get(normalized, [])

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in project (O(1) lookup)."""
        normalized = self._normalize_path(file_path)
        return normalized in self.known_files

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
        return {
            "files": len(self.known_files),
            "imports": sum(len(v) for v in self.imports_by_file.values()),
            "exports": sum(len(v) for v in self.exports_by_file.values()),
        }
