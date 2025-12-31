"""Report service - HOP 3: Business logic for reports.

Handles report generation with multiple tainted inputs.
"""

from app.processors.data_transformer import DataTransformer


class ReportService:
    """Report business logic service.

    HOP 3: Receives multiple tainted inputs (title, format, callback_url)
    and routes them to appropriate processors.
    """

    def __init__(self):
        self.transformer = DataTransformer()

    async def generate(
        self,
        title: str,
        output_format: str,
        callback_url: str | None = None,
    ) -> dict:
        """Generate a report.

        HOP 3: Multiple tainted inputs flow through:
        - title -> XSS chain (14 hops)
        - output_format -> Command Injection chain (12 hops)
        - callback_url -> SSRF chain (8 hops)

        Args:
            title: TAINTED - flows to template rendering
            output_format: TAINTED - flows to command execution
            callback_url: TAINTED - flows to HTTP request
        """
        # Each parameter flows to different vulnerability chains
        report_data = self.transformer.prepare_report(
            title=title,
            output_format=output_format,
            callback_url=callback_url,
        )
        return report_data

    async def export(self, report_id: str, format: str) -> dict:
        """Export report in specified format.

        Args:
            report_id: Report identifier
            format: TAINTED - flows to command execution
        """
        return self.transformer.prepare_export(report_id, format)
