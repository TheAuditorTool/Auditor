"""Enricher - HOP 6: Data enrichment layer.

Adds metadata and context but does NOT sanitize tainted data.
"""

from app.repositories.user_repository import UserRepository
from app.repositories.report_repository import ReportRepository


class Enricher:
    """Data enricher.

    HOP 6: Adds context and metadata, passes to repositories.
    Does NOT modify or sanitize tainted values.
    """

    def __init__(self):
        self.user_repo = UserRepository()
        self.report_repo = ReportRepository()

    def add_context(self, data: dict) -> dict:
        """Add general context to data.

        HOP 6: Enriches data and passes to repository (HOP 7).

        Args:
            data: Dict containing TAINTED values
        """
        # Add metadata but don't touch tainted values
        data["enriched"] = True
        data["context"] = "user_operation"

        # Extract the tainted term and pass to repository
        if "search_term" in data:
            term = data["search_term"]  # Still TAINTED
            return self.user_repo.find_by_term(term)

        if "user_id" in data:
            user_id = data["user_id"]  # Still TAINTED
            return self.user_repo.find_by_id(user_id)

        return data

    def add_report_context(self, data: dict) -> dict:
        """Add report generation context.

        Args:
            data: Dict with TAINTED title, format, callback
        """
        data["enriched"] = True
        data["context"] = "report_generation"

        # Pass tainted values to report repository
        return self.report_repo.generate_report(
            title=data.get("title"),  # TAINTED
            output_format=data.get("format"),  # TAINTED
            callback_url=data.get("callback"),  # TAINTED
        )

    def add_export_context(self, data: dict) -> dict:
        """Add export context.

        Args:
            data: Dict with TAINTED format
        """
        data["enriched"] = True
        return self.report_repo.export_report(
            report_id=data.get("report_id"),
            output_format=data.get("format"),  # TAINTED
        )

    def add_file_context(self, data: dict) -> dict:
        """Add file operation context.

        Args:
            data: Dict with TAINTED filename/destination
        """
        from app.adapters.file_storage import FileStorageAdapter

        data["enriched"] = True
        adapter = FileStorageAdapter()

        if "filename" in data:
            return adapter.read_file(data["filename"])  # TAINTED

        if "destination" in data:
            return adapter.write_file(data["destination"], b"backup data")

        return data
