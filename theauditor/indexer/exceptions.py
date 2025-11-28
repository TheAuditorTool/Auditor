"""Custom exceptions for the indexer module."""


class DataFidelityError(Exception):
    """Raised when extracted data does not match stored data."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}
