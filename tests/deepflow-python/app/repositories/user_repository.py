"""User repository - HOP 7: User data access.

Handles user database operations with SQL injection vulnerability.
"""

from app.repositories.base_repository import BaseRepository
from app.adapters.cache_adapter import CacheAdapter


class UserRepository(BaseRepository):
    """User data access repository.

    HOP 7: Receives tainted search terms, builds queries, passes to cache.
    """

    def __init__(self):
        super().__init__()
        self.cache = CacheAdapter()

    def find_by_term(self, term: str) -> dict:
        """Find users by search term.

        HOP 7: Passes tainted term to cache adapter.

        Args:
            term: TAINTED search term - SQL injection vector

        VULNERABILITY: Term flows to SQL query construction.
        """
        # Pass tainted term to cache (HOP 8)
        return self.cache.get_or_fetch(term)

    def find_by_id(self, user_id: str) -> dict:
        """Find user by ID.

        Args:
            user_id: TAINTED user ID - SQL injection vector
        """
        return self.cache.get_or_fetch_by_id(user_id)

    def find_by_email(self, email: str) -> dict:
        """Find user by email (will be used for sanitized path demo).

        Args:
            email: Email address to search
        """
        return self.cache.get_or_fetch_by_email(email)
