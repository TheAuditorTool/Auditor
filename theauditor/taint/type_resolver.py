"""Polyglot Type Identity Checker."""

import json
import sqlite3


class TypeResolver:
    """Resolves type identity for ORM model aliasing."""

    def __init__(self, graph_cursor: sqlite3.Cursor, repo_cursor: sqlite3.Cursor = None):
        """Initialize TypeResolver."""
        self.graph_cursor = graph_cursor
        self.repo_cursor = repo_cursor
        self._model_cache: dict[str, str | None] = {}
        self._controller_files: set[str] | None = None

    def get_model_for_node(self, node_id: str) -> str | None:
        """Get model name for a node from metadata."""

        if node_id in self._model_cache:
            return self._model_cache[node_id]

        self.graph_cursor.execute("SELECT metadata FROM nodes WHERE id = ?", (node_id,))
        row = self.graph_cursor.fetchone()

        model = None
        if row and row[0]:
            model = self._extract_model_from_metadata(row[0])

        self._model_cache[node_id] = model
        return model

    def _extract_model_from_metadata(self, metadata_str: str) -> str | None:
        """Parse metadata JSON and extract model name."""
        if not metadata_str:
            return None

        try:
            metadata = json.loads(metadata_str)
        except (json.JSONDecodeError, TypeError):
            return None

        if "model" in metadata:
            return metadata["model"]

        query_type = metadata.get("query_type", "")
        if query_type and "." in query_type:
            return query_type.split(".")[0]

        if "target_model" in metadata:
            return metadata["target_model"]

        return None

    def is_same_type(self, node_a_id: str, node_b_id: str) -> bool:
        """Check if two nodes represent the same model type."""
        model_a = self.get_model_for_node(node_a_id)
        model_b = self.get_model_for_node(node_b_id)

        if model_a and model_b:
            return model_a == model_b

        return False

    def is_controller_file(self, file_path: str) -> bool:
        """Check if file is a controller/route handler (any framework)."""
        if self.repo_cursor is None:
            lower = file_path.lower()
            return any(
                pattern in lower
                for pattern in [
                    "controller",
                    "routes",
                    "handlers",
                    "views",
                    "endpoints",
                    "internal/api",
                    "cmd/server",
                    "pkg/api",
                ]
            )

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
        """Extract model name from edge metadata."""
        if isinstance(edge_metadata, str):
            try:
                metadata = json.loads(edge_metadata)
            except (json.JSONDecodeError, TypeError):
                return None
        elif isinstance(edge_metadata, dict):
            metadata = edge_metadata
        else:
            return None

        for key in ["model", "target_model", "source_model"]:
            if key in metadata:
                return metadata[key]

        query_type = metadata.get("query_type", "")
        if query_type and "." in query_type:
            return query_type.split(".")[0]

        return None

    def clear_cache(self) -> None:
        """Clear the model cache (useful after graph rebuild)."""
        self._model_cache.clear()
        self._controller_files = None
