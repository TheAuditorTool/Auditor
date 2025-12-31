"""Data transformer - HOP 4: Data transformation layer.

Transforms data but does NOT sanitize user input.
"""

from app.processors.validator import Validator


class DataTransformer:
    """Data transformation processor.

    HOP 4: Receives tainted data, adds metadata, passes to validator.
    Does NOT sanitize the actual tainted values.
    """

    def __init__(self):
        self.validator = Validator()

    def prepare_search(self, term: str) -> dict:
        """Prepare search term for database query.

        HOP 4: Transformer adds metadata but doesn't sanitize the term.

        Args:
            term: TAINTED search term from user input
        """
        # Add metadata but don't sanitize the tainted term
        prepared = {
            "search_term": term,  # Still TAINTED
            "operation": "search",
            "timestamp": "now",
        }
        # Pass to validator (HOP 5)
        return self.validator.check_length(prepared)

    def prepare_lookup(self, user_id: str) -> dict:
        """Prepare user lookup.

        Args:
            user_id: TAINTED user identifier
        """
        prepared = {
            "user_id": user_id,  # Still TAINTED
            "operation": "lookup",
        }
        return self.validator.check_length(prepared)

    def prepare_report(
        self,
        title: str,
        output_format: str,
        callback_url: str | None = None,
    ) -> dict:
        """Prepare report generation data.

        HOP 4: Multiple tainted inputs wrapped in dict.

        Args:
            title: TAINTED - XSS vector
            output_format: TAINTED - Command Injection vector
            callback_url: TAINTED - SSRF vector
        """
        prepared = {
            "title": title,  # TAINTED
            "format": output_format,  # TAINTED
            "callback": callback_url,  # TAINTED
            "operation": "generate_report",
        }
        return self.validator.check_report_params(prepared)

    def prepare_export(self, report_id: str, format: str) -> dict:
        """Prepare export operation.

        Args:
            report_id: Report identifier
            format: TAINTED - Command Injection vector
        """
        prepared = {
            "report_id": report_id,
            "format": format,  # TAINTED
            "operation": "export",
        }
        return self.validator.check_export_params(prepared)

    def prepare_file_read(self, filename: str) -> dict:
        """Prepare file read operation.

        Args:
            filename: TAINTED - Path Traversal vector
        """
        prepared = {
            "filename": filename,  # TAINTED
            "operation": "file_read",
        }
        return self.validator.check_file_params(prepared)

    def prepare_backup(self, destination: str) -> dict:
        """Prepare backup operation.

        Args:
            destination: TAINTED - Path Traversal vector
        """
        prepared = {
            "destination": destination,  # TAINTED
            "operation": "backup",
        }
        return self.validator.check_file_params(prepared)
