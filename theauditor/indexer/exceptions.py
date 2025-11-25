"""Custom exceptions for the indexer module.

Contains exception classes for specific failure modes that require
explicit handling rather than generic error propagation.
"""


class DataFidelityError(Exception):
    """Raised when extracted data does not match stored data.

    This exception enforces the ZERO FALLBACK POLICY by crashing loudly
    when data loss is detected. If extraction produces N records but
    storage receives 0, something is critically wrong.

    Attributes:
        message: Human-readable error description
        details: Dict containing errors and warnings for debugging
    """

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}
