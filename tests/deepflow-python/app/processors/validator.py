"""Validator - HOP 5: Validation layer (INTENTIONALLY WEAK).

This validator performs length checks but does NOT sanitize
dangerous characters, allowing SQL injection, path traversal, etc.
"""

from app.processors.enricher import Enricher


class Validator:
    """Data validator (intentionally weak).

    HOP 5: Performs superficial validation that does NOT prevent attacks.
    Only checks length, not content. SQL special chars pass through.
    """

    MAX_LENGTH = 1000

    def __init__(self):
        self.enricher = Enricher()

    def check_length(self, data: dict) -> dict:
        """Check data length (WEAK - does not sanitize content).

        HOP 5: Only checks length, NOT content.
        SQL injection chars like ' and -- pass through.

        Args:
            data: Dict containing TAINTED values
        """
        # INTENTIONALLY WEAK: Only check length, not content
        for key, value in data.items():
            if isinstance(value, str) and len(value) > self.MAX_LENGTH:
                raise ValueError(f"{key} too long")
            # NOTE: Does NOT check for SQL injection chars
            # NOTE: Does NOT check for path traversal chars
            # NOTE: Does NOT check for command injection chars

        # Pass to enricher (HOP 6)
        return self.enricher.add_context(data)

    def check_report_params(self, data: dict) -> dict:
        """Check report parameters (WEAK).

        Args:
            data: Dict with TAINTED title, format, callback
        """
        # WEAK: Only checks existence, not content
        if not data.get("title"):
            data["title"] = "Untitled"

        # Does NOT validate format for shell-safe characters
        # Does NOT validate callback URL for SSRF

        return self.enricher.add_report_context(data)

    def check_export_params(self, data: dict) -> dict:
        """Check export parameters (WEAK).

        Args:
            data: Dict with TAINTED format
        """
        # WEAK: Does not validate format for injection
        return self.enricher.add_export_context(data)

    def check_file_params(self, data: dict) -> dict:
        """Check file parameters (WEAK).

        Args:
            data: Dict with TAINTED filename/destination
        """
        # WEAK: Does NOT check for .. or absolute paths
        # Path traversal attack vectors pass through
        return self.enricher.add_file_context(data)
