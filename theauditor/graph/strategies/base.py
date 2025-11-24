"""Abstract base class for graph strategies.

This module defines the contract that all language-specific strategies must follow.
Strategies encapsulate framework-specific logic (Express, Django ORM, etc.) that
would otherwise pollute the core DFGBuilder.

Architecture:
- Strategies are stateless (mostly) - they receive DB access at build time
- They return standard Graph dictionaries compatible with DFGBuilder
- If a strategy fails, it should not crash the entire graph build
"""

from abc import ABC, abstractmethod
from typing import Any


class GraphStrategy(ABC):
    """Abstract base class for language-specific DFG strategies.

    Implementations:
    - PythonOrmStrategy: Handles SQLAlchemy/Django ORM relationships
    - NodeExpressStrategy: Handles Express middleware chains

    Future:
    - RustStrategy: Cargo/async patterns
    - GoStrategy: Goroutines/channels
    """

    @property
    def name(self) -> str:
        """Human-readable name for logging."""
        return self.__class__.__name__

    @abstractmethod
    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """
        Build specific graph edges (e.g. ORM, Middleware).

        Args:
            db_path: Path to sqlite database (repo_index.db)
            project_root: Root path for metadata

        Returns:
            Dict containing:
            - "nodes": List[dict] (from asdict(DFGNode))
            - "edges": List[dict] (from asdict(DFGEdge))
            - "metadata": dict with stats and graph_type

        Raises:
            Should NOT raise - return empty results on failure
            Log errors but don't crash the build
        """
        pass
