# AUTO-GENERATED FILE - DO NOT EDIT
# SCHEMA_HASH: 0338c23dff5a1fb17e1fd42975828befa754f95777c37bc170d7fd43e8124848
from typing import Any
from collections import defaultdict
import sqlite3
from ..schema import TABLES, build_query


class SchemaMemoryCache:
    """Auto-generated memory cache that loads ALL tables."""

    def __init__(self, db_path: str):
        """Initialize cache by loading all tables from database."""
        self.db_path = db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get list of existing tables in database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Auto-load ALL tables that exist
        for table_name, schema in TABLES.items():
            if table_name in existing_tables:
                data = self._load_table(cursor, table_name, schema)
            else:
                # Table doesn't exist yet, use empty list
                data = []
            setattr(self, table_name, data)

            # Auto-build indexes for indexed columns (always create, even if empty)
            for idx_def in schema.indexes:
                _idx_name, idx_cols = idx_def[0], idx_def[1]  # Handle 2 or 3 element tuples
                if len(idx_cols) == 1:  # Single column index
                    col_name = idx_cols[0]
                    index = self._build_index(data, table_name, col_name, schema)
                    setattr(self, f"{table_name}_by_{col_name}", index)

        conn.close()

    def _load_table(self, cursor: sqlite3.Cursor, table_name: str, schema: Any) -> list[dict[str, Any]]:
        """Load a table into memory as list of dicts."""
        col_names = [col.name for col in schema.columns]
        query = build_query(table_name, col_names)
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(zip(col_names, row, strict=True)) for row in rows]

    def _build_index(self, data: list[dict[str, Any]], table_name: str, col_name: str, schema: Any) -> dict[Any, list[dict[str, Any]]]:
        """Build an index on a column for fast lookups."""
        index = defaultdict(list)
        for row in data:
            key = row.get(col_name)
            if key is not None:
                index[key].append(row)
        return dict(index)

    def get_table_size(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        if hasattr(self, table_name):
            return len(getattr(self, table_name))
        return 0

    def get_cache_stats(self) -> dict[str, int]:
        """Get statistics about cached data."""
        stats = {}
        for table_name in TABLES:
            stats[table_name] = self.get_table_size(table_name)
        return stats