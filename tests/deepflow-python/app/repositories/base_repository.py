"""Base repository - HOP 7: Data access pattern base.

Provides common database operations.
"""

from app.database import get_db


class BaseRepository:
    """Base repository with common database operations.

    HOP 7: Data access layer that passes queries to adapters.
    """

    def __init__(self):
        self.db = get_db

    def execute_query(self, query: str) -> list:
        """Execute a SQL query.

        WARNING: This method is vulnerable if query contains user input.

        Args:
            query: SQL query string (potentially TAINTED)
        """
        from app.adapters.cache_adapter import CacheAdapter

        # Try cache first
        cache = CacheAdapter()
        return cache.get_or_fetch(query)
