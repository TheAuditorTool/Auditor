"""Custom exceptions for the graph module."""


class GraphFidelityError(Exception):
    """Raised when graph data does not match expected shape or counts."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class GraphSchemaError(Exception):
    """Raised when graph nodes/edges violate schema constraints."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}
