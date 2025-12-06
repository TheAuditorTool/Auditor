# AUTO-GENERATED FILE - DO NOT EDIT
# SCHEMA_HASH: 1ce39d543ef52f4c36657e291f976ac1ac457e4cd69bf31343d8b339bdc0fe8a
import sqlite3
from collections import defaultdict
from typing import Any

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

    def get_memory_usage_mb(self) -> float:
        """Estimate memory usage of the cache in MB."""
        import sys
        total_bytes = 0
        for _attr, value in self.__dict__.items():
            total_bytes += sys.getsizeof(value)
            if isinstance(value, list):
                total_bytes += sum(sys.getsizeof(i) for i in value)
            elif isinstance(value, dict):
                total_bytes += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in value.items())
        return total_bytes / (1024 * 1024)
