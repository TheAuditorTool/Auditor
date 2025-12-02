"""Base class for domain-specific storage modules."""

from theauditor.utils.logging import logger


class BaseStorage:
    """Base class for domain-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        self.db_manager = db_manager
        self.counts = counts
        self._current_extracted = {}

    def begin_file_processing(self) -> None:
        """Reset per-file state before processing a new file.

        Override in subclasses to clear gatekeeper tracking sets.
        Called by DataStorer.store() at the start of each file.
        """
        pass

    def _debug(self, message: str):
        """Debug logging helper."""
        logger.debug(f"[DEBUG STORAGE] {message}")
