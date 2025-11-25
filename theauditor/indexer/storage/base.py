"""Base class for domain-specific storage modules.

Provides shared infrastructure:
- db_manager: DatabaseManager instance for database operations
- counts: Statistics tracking dict (mutated across all handlers)
- _current_extracted: Cross-cutting data access (e.g., resolved_imports)

All domain storage modules (CoreStorage, PythonStorage, etc.) inherit from
this base class to access shared dependencies without duplication.
"""


class BaseStorage:
    """Base class for domain-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        self.db_manager = db_manager
        self.counts = counts
        self._current_extracted = {}  # Set by DataStorer.store()

    def _debug(self, message: str):
        """Debug logging helper."""
        import os
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG STORAGE] {message}")
