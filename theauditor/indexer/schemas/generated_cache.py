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

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table_name, schema in TABLES.items():
            if table_name in existing_tables:
                data = self._load_table(cursor, table_name, schema)
            else:
                data = []
            setattr(self, table_name, data)

            for _idx_name, idx_cols in schema.indexes:
                if len(idx_cols) == 1:
                    col_name = idx_cols[0]
                    index = self._build_index(data, table_name, col_name, schema)
                    setattr(self, f"{table_name}_by_{col_name}", index)

        conn.close()

    def _load_table(
        self, cursor: sqlite3.Cursor, table_name: str, schema: Any
    ) -> list[dict[str, Any]]:
        """Load a table into memory as list of dicts."""
        col_names = [col.name for col in schema.columns]
        query = build_query(table_name, col_names)
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(zip(col_names, row, strict=True)) for row in rows]

    def _build_index(
        self, data: list[dict[str, Any]], table_name: str, col_name: str, schema: Any
    ) -> dict[Any, list[dict[str, Any]]]:
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
