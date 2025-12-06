"""Abstract base class for graph strategies."""

from abc import ABC, abstractmethod
from typing import Any


class GraphStrategy(ABC):
    """Abstract base class for language-specific DFG strategies."""

    @property
    def name(self) -> str:
        """Human-readable name for logging."""
        return self.__class__.__name__

    @abstractmethod
    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build specific graph edges (e.g. ORM, Middleware)."""
        pass
