"""Report repository - HOP 7: Report data access.

Handles report operations with multiple vulnerability chains.
"""

from app.repositories.base_repository import BaseRepository
from app.adapters.cache_adapter import CacheAdapter
from app.adapters.external_api import ExternalApiAdapter


class ReportRepository(BaseRepository):
    """Report data access repository.

    HOP 7: Routes multiple tainted inputs to different adapters.
    """

    def __init__(self):
        super().__init__()
        self.cache = CacheAdapter()
        self.external = ExternalApiAdapter()

    def generate_report(
        self,
        title: str,
        output_format: str,
        callback_url: str | None = None,
    ) -> dict:
        """Generate a report.

        HOP 7: Multiple tainted inputs flow to different sinks.

        Args:
            title: TAINTED - flows to template (XSS)
            output_format: TAINTED - flows to command (Command Injection)
            callback_url: TAINTED - flows to HTTP request (SSRF)
        """
        # Each parameter flows to a different adapter
        result = {
            "status": "generating",
            "title": title,  # Still TAINTED
        }

        # Cache the report data
        self.cache.store_report(title, output_format)

        # If callback URL provided, notify (SSRF vector)
        if callback_url:
            self.external.post(callback_url, result)

        # Render and convert
        from app.core.template_renderer import TemplateRenderer
        from app.core.command_executor import CommandExecutor

        renderer = TemplateRenderer()
        rendered = renderer.render_report(title, result)

        executor = CommandExecutor()
        converted = executor.convert_format(rendered, output_format)

        return converted

    def export_report(self, report_id: str, output_format: str) -> dict:
        """Export a report.

        Args:
            report_id: Report identifier
            output_format: TAINTED - Command Injection vector
        """
        from app.core.command_executor import CommandExecutor

        executor = CommandExecutor()
        return executor.export(report_id, output_format)
