# AUTO-GENERATED FILE - DO NOT EDIT
# SCHEMA_HASH: 1fcfd5cebfe25504e258d740acb2cda72d0bafaf5fa6428f55415563f023682e
from typing import Dict, List, Any, Optional, DefaultDict
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

            # Auto-build indexes for indexed columns
            if data:  # Only build indexes if we have data
                for idx_name, idx_cols in schema.indexes:
                    if len(idx_cols) == 1:  # Single column index
                        col_name = idx_cols[0]
                        index = self._build_index(data, table_name, col_name, schema)
                        setattr(self, f"{table_name}_by_{col_name}", index)

        conn.close()

    def _load_table(self, cursor: sqlite3.Cursor, table_name: str, schema: Any) -> List[Dict[str, Any]]:
        """Load a table into memory as list of dicts."""
        col_names = [col.name for col in schema.columns]
        query = build_query(table_name, col_names)
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(zip(col_names, row)) for row in rows]

    def _build_index(self, data: List[Dict[str, Any]], table_name: str, col_name: str, schema: Any) -> Dict[Any, List[Dict[str, Any]]]:
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

    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about cached data."""
        stats = {}
        for table_name in TABLES.keys():
            stats[table_name] = self.get_table_size(table_name)
        return stats