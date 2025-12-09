"""Report routes - HOP 1: Additional taint sources.

Contains endpoints for report generation with multiple vulnerability chains.
"""

from fastapi import APIRouter, Request

from app.api.middleware.auth import require_auth
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate")
@require_auth
async def generate_report(request: Request):
    """Generate a report with custom format.

    HOP 1: Taint SOURCE - user input from JSON body.

    VULNERABILITY: Command Injection (12 hops)
    - request.json["format"] flows to subprocess.run()

    VULNERABILITY: XSS (14 hops)
    - request.json["title"] flows to unescaped template
    """
    body = await request.json()
    output_format = body.get("format", "pdf")  # TAINTED - Command Injection source
    title = body.get("title", "Report")  # TAINTED - XSS source
    callback_url = body.get("callback_url")  # TAINTED - SSRF source

    service = ReportService()
    return await service.generate(
        title=title,
        output_format=output_format,
        callback_url=callback_url,
    )


@router.get("/export")
@require_auth
async def export_report(report_id: str, format: str = "json"):
    """Export report in specified format.

    Another command injection vector through format parameter.
    """
    service = ReportService()
    return await service.export(report_id, format)
