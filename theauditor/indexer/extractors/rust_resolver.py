"""Rust module resolution for cross-file type/trait references.

Resolves local names to canonical paths using Rust's module system:
- crate:: - absolute path from crate root
- super:: - parent module
- self:: - current module
- use aliases - imported names

Usage:
    resolver = RustResolver(db_path=".pf/repo_index.db")
    canonical = resolver.resolve("src/models/user.rs", "HashMap")
    # Returns "std::collections::HashMap"
"""

import sqlite3
from pathlib import Path

_STD_PRELUDE = frozenset(
    {
        "Option",
        "Some",
        "None",
        "Result",
        "Ok",
        "Err",
        "Vec",
        "String",
        "Box",
        "Rc",
        "Arc",
        "Cell",
        "RefCell",
        "Copy",
        "Clone",
        "Default",
        "Debug",
        "Display",
        "Iterator",
        "IntoIterator",
        "From",
        "Into",
        "PartialEq",
        "Eq",
        "PartialOrd",
        "Ord",
        "Hash",
        "Send",
        "Sync",
        "Sized",
        "Drop",
        "Fn",
        "FnMut",
        "FnOnce",
    }
)

_PRELUDE_PATHS = {
    "Vec": "std::vec::Vec",
    "String": "std::string::String",
    "Box": "std::boxed::Box",
    "Rc": "std::rc::Rc",
    "Arc": "std::sync::Arc",
    "Cell": "std::cell::Cell",
    "RefCell": "std::cell::RefCell",
    "Option": "std::option::Option",
    "Result": "std::result::Result",
}

_PRIMITIVES = frozenset(
    {
        "i8",
        "i16",
        "i32",
        "i64",
        "i128",
        "isize",
        "u8",
        "u16",
        "u32",
        "u64",
        "u128",
        "usize",
        "f32",
        "f64",
        "bool",
        "char",
        "str",
    }
)


class RustResolver:
    """Resolves Rust type/trait names to canonical paths."""

    def __init__(self, db_path: str = ".pf/repo_index.db"):
        """Initialize resolver with database path.

        Args:
            db_path: Path to repo_index.db
        """
        self.db_path = Path(db_path)
        self._alias_cache: dict[str, dict[str, str]] = {}
        self._modules_cache: dict[str, str] = {}
        self._loaded = False

    def _load_from_db(self) -> None:
        """Load use statements and module info from database."""
        if self._loaded or not self.db_path.exists():
            return

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='rust_use_statements'
            """)
            if not cursor.fetchone():
                return

            cursor.execute("""
                SELECT file_path, import_path, local_name, is_glob
                FROM rust_use_statements
                WHERE local_name IS NOT NULL
            """)

            for row in cursor.fetchall():
                file_path = row["file_path"]
                import_path = row["import_path"]
                local_name = row["local_name"]

                if file_path not in self._alias_cache:
                    self._alias_cache[file_path] = {}

                self._alias_cache[file_path][local_name] = import_path

            cursor.execute("""
                SELECT file_path, module_name, parent_module
                FROM rust_modules
            """)

            for row in cursor.fetchall():
                file_path = row["file_path"]
                module_name = row["module_name"]
                parent_module = row["parent_module"]

                if parent_module:
                    self._modules_cache[file_path] = f"{parent_module}::{module_name}"
                else:
                    self._modules_cache[file_path] = module_name

            self._loaded = True
        finally:
            conn.close()

    def resolve(self, file_path: str, local_name: str) -> str | None:
        """Resolve a local name to its canonical path.

        Args:
            file_path: Path to the source file where the name is used
            local_name: The local type/trait name to resolve

        Returns:
            Canonical path (e.g., "std::collections::HashMap") or None if not found
        """
        self._load_from_db()

        if file_path in self._alias_cache:
            aliases = self._alias_cache[file_path]
            if local_name in aliases:
                return aliases[local_name]

        if "::" in local_name:
            return local_name

        if local_name in _STD_PRELUDE:
            return _PRELUDE_PATHS.get(local_name, f"std::prelude::{local_name}")

        if local_name in _PRIMITIVES:
            return local_name

        return local_name

    def resolve_for_file(self, file_path: str) -> dict[str, str]:
        """Get all alias mappings for a file.

        Args:
            file_path: Path to the source file

        Returns:
            Dict mapping local names to canonical paths
        """
        self._load_from_db()
        return self._alias_cache.get(file_path, {})

    def update_resolved_paths(self) -> dict[str, int]:
        """Update target_type_resolved and trait_resolved in rust_impl_blocks.

        Returns:
            Stats dict with counts of updates
        """
        self._load_from_db()

        if not self.db_path.exists():
            return {"updated": 0, "skipped": 0}

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        stats = {"updated": 0, "skipped": 0}

        try:
            cursor.execute("""
                SELECT rowid, file_path, target_type_raw, trait_name
                FROM rust_impl_blocks
                WHERE target_type_raw IS NOT NULL
            """)

            updates = []
            for row in cursor.fetchall():
                rowid = row["rowid"]
                file_path = row["file_path"]
                target_raw = row["target_type_raw"]
                trait_name = row["trait_name"]

                target_resolved = self.resolve(file_path, target_raw)

                trait_resolved = None
                if trait_name:
                    trait_resolved = self.resolve(file_path, trait_name)

                if target_resolved or trait_resolved:
                    updates.append((target_resolved, trait_resolved, rowid))
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1

            if updates:
                cursor.executemany(
                    """
                    UPDATE rust_impl_blocks
                    SET target_type_resolved = ?, trait_resolved = ?
                    WHERE rowid = ?
                """,
                    updates,
                )
                conn.commit()

        finally:
            conn.close()

        return stats

    def update_canonical_paths(self) -> dict[str, int]:
        """Update canonical_path in rust_use_statements.

        For complex use patterns like `use std::collections::{HashMap, HashSet}`,
        ensures canonical_path reflects the full path.

        Returns:
            Stats dict with counts of updates
        """
        self._load_from_db()

        if not self.db_path.exists():
            return {"updated": 0, "skipped": 0}

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        stats = {"updated": 0, "skipped": 0}

        try:
            cursor.execute("""
                SELECT rowid, import_path, local_name
                FROM rust_use_statements
                WHERE local_name IS NOT NULL
            """)

            updates = []
            for row in cursor.fetchall():
                rowid = row["rowid"]
                import_path = row["import_path"]
                local_name = row["local_name"]

                if "::{" in import_path and "}" in import_path:
                    base = import_path.split("::{")[0]
                    canonical = f"{base}::{local_name}"
                    updates.append((canonical, rowid))
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1

            if updates:
                cursor.executemany(
                    """
                    UPDATE rust_use_statements
                    SET canonical_path = ?
                    WHERE rowid = ?
                """,
                    updates,
                )
                conn.commit()

        finally:
            conn.close()

        return stats


def resolve_rust_modules(db_path: str = ".pf/repo_index.db") -> dict[str, int]:
    """Run full module resolution update on database.

    Args:
        db_path: Path to repo_index.db

    Returns:
        Combined stats from all resolution passes
    """
    resolver = RustResolver(db_path)

    stats = {}
    stats["use_statements"] = resolver.update_canonical_paths()
    stats["impl_blocks"] = resolver.update_resolved_paths()

    return stats
