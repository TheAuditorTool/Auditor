"""Polyglot Type Identity Checker.

Answers: "Do these two variables represent the same Data Model?"
Used for ORM aliasing when no direct graph edge exists.

Created as part of refactor-polyglot-taint-engine Phase 2 (2025-11-27).
"""

import json
import sqlite3
from typing import Any


class TypeResolver:
    """Resolves type identity for ORM model aliasing.

    Uses graph node metadata to determine if two variables represent the
    same Data Model type (e.g., both are 'User' model instances).

    Also provides utilities for detecting controller files via api_endpoints.
    """

    def __init__(self, graph_cursor: sqlite3.Cursor, repo_cursor: sqlite3.Cursor = None):
        """Initialize TypeResolver.

        Args:
            graph_cursor: Cursor for graphs.db (for node metadata)
            repo_cursor: Cursor for repo_index.db (for api_endpoints). Optional.
        """
        self.graph_cursor = graph_cursor
        self.repo_cursor = repo_cursor
        self._model_cache: dict[str, str | None] = {}
        self._controller_files: set[str] | None = None

    def get_model_for_node(self, node_id: str) -> str | None:
        """Get model name for a node from metadata.

        Queries the nodes table in graphs.db and parses the metadata JSON
        to find the 'model' key.

        Args:
            node_id: Node ID in format 'file::scope::variable'

        Returns:
            Model name if found, None otherwise
        """
        # Check cache first
        if node_id in self._model_cache:
            return self._model_cache[node_id]

        # Query nodes table
        self.graph_cursor.execute(
            "SELECT metadata FROM nodes WHERE id = ?",
            (node_id,)
        )
        row = self.graph_cursor.fetchone()

        model = None
        if row and row[0]:
            model = self._extract_model_from_metadata(row[0])

        # Cache result (even None)
        self._model_cache[node_id] = model
        return model

    def _extract_model_from_metadata(self, metadata_str: str) -> str | None:
        """Parse metadata JSON and extract model name.

        Args:
            metadata_str: JSON string from nodes.metadata column

        Returns:
            Model name if found, None otherwise
        """
        if not metadata_str:
            return None

        try:
            metadata = json.loads(metadata_str)
        except (json.JSONDecodeError, TypeError):
            return None

        # Direct 'model' key (from ORM strategies)
        if 'model' in metadata:
            return metadata['model']

        # Extract from query_type (e.g., 'User.findAll' -> 'User')
        query_type = metadata.get('query_type', '')
        if query_type and '.' in query_type:
            return query_type.split('.')[0]

        # Extract from target_model (from ORM relationship edges)
        if 'target_model' in metadata:
            return metadata['target_model']

        return None

    def is_same_type(self, node_a_id: str, node_b_id: str) -> bool:
        """Check if two nodes represent the same model type.

        Useful for ORM aliasing - detecting that 'user' in File A and
        'user' in File B both refer to the 'User' model.

        Args:
            node_a_id: First node ID
            node_b_id: Second node ID

        Returns:
            True if both nodes have same non-null model name
        """
        model_a = self.get_model_for_node(node_a_id)
        model_b = self.get_model_for_node(node_b_id)

        # Both must have a model, and they must match
        if model_a and model_b:
            return model_a == model_b

        return False

    def is_controller_file(self, file_path: str) -> bool:
        """Check if file is a controller/route handler (any framework).

        Queries api_endpoints table to see if the file handles routes.

        Args:
            file_path: Path to file

        Returns:
            True if file contains API endpoints
        """
        if self.repo_cursor is None:
            # No repo cursor - fall back to name-based heuristic
            lower = file_path.lower()
            return any(pattern in lower for pattern in [
                'controller', 'routes', 'handlers', 'views', 'endpoints'
            ])

        # Lazy load controller files
        if self._controller_files is None:
            self._load_controller_files()

        return file_path in self._controller_files

    def _load_controller_files(self) -> None:
        """Pre-load all controller files from api_endpoints table."""
        self._controller_files = set()

        if self.repo_cursor is None:
            return

        self.repo_cursor.execute("SELECT DISTINCT file FROM api_endpoints")
        for row in self.repo_cursor.fetchall():
            if row[0]:
                self._controller_files.add(row[0])

    def get_model_from_edge(self, edge_metadata: str | dict) -> str | None:
        """Extract model name from edge metadata.

        Useful for traversing ORM edges where metadata contains model info.

        Args:
            edge_metadata: JSON string or dict from edges.metadata column

        Returns:
            Model name if found, None otherwise
        """
        if isinstance(edge_metadata, str):
            try:
                metadata = json.loads(edge_metadata)
            except (json.JSONDecodeError, TypeError):
                return None
        elif isinstance(edge_metadata, dict):
            metadata = edge_metadata
        else:
            return None

        # Check common keys
        for key in ['model', 'target_model', 'source_model']:
            if key in metadata:
                return metadata[key]

        # Extract from query_type
        query_type = metadata.get('query_type', '')
        if query_type and '.' in query_type:
            return query_type.split('.')[0]

        return None

    def clear_cache(self) -> None:
        """Clear the model cache (useful after graph rebuild)."""
        self._model_cache.clear()
        self._controller_files = None
