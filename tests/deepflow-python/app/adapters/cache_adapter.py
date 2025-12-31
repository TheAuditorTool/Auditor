"""Cache adapter - HOP 8: Caching layer.

Caches query results but does NOT sanitize queries.
"""

from app.core.query_builder import QueryBuilder


class CacheAdapter:
    """Cache adapter for database queries.

    HOP 8: Receives tainted search terms, checks cache, builds queries.
    Cache misses trigger vulnerable SQL query construction.
    """

    def __init__(self):
        self.cache = {}  # Simple in-memory cache
        self.builder = QueryBuilder()

    def get_or_fetch(self, key: str) -> dict:
        """Get from cache or fetch from database.

        HOP 8: Cache miss triggers query builder with TAINTED key.

        Args:
            key: TAINTED search term - flows to SQL query
        """
        # Check cache (rarely hits in this fixture)
        cache_key = f"search:{key}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Cache miss - build and execute query (HOP 9+)
        result = self.builder.build_user_search(key)  # key is TAINTED

        # Store in cache
        self.cache[cache_key] = result
        return result

    def get_or_fetch_by_id(self, user_id: str) -> dict:
        """Get user by ID from cache or database.

        Args:
            user_id: TAINTED user ID - SQL injection vector
        """
        cache_key = f"user:{user_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = self.builder.build_user_lookup(user_id)  # TAINTED
        self.cache[cache_key] = result
        return result

    def get_or_fetch_by_email(self, email: str) -> dict:
        """Get user by email (used in sanitized path).

        Args:
            email: Email to search (will be sanitized before reaching here)
        """
        cache_key = f"email:{email}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = self.builder.build_email_lookup(email)
        self.cache[cache_key] = result
        return result

    def store_report(self, title: str, format: str) -> None:
        """Store report metadata in cache.

        Args:
            title: TAINTED report title
            format: TAINTED output format
        """
        self.cache[f"report:{title}"] = {"format": format}
