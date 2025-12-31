"""Admin routes - HOP 1: File-related taint sources.

Contains endpoints with path traversal vulnerabilities.
"""

from fastapi import APIRouter, Query

from app.api.middleware.auth import require_auth
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/files/{filename:path}")
@require_auth
async def get_file(filename: str):
    """Get file contents by filename.

    HOP 1: Taint SOURCE - user input from path parameter.

    VULNERABILITY: Path Traversal (10 hops)
    - filename flows to open() without proper sanitization
    """
    service = AdminService()
    return await service.read_file(filename)  # filename is TAINTED


@router.get("/logs")
@require_auth
async def get_logs(logfile: str = Query(..., description="Log file to read")):
    """Get log file contents.

    Another path traversal vector.
    """
    service = AdminService()
    return await service.read_log(logfile)


@router.post("/backup")
@require_auth
async def create_backup(destination: str = Query(...)):
    """Create backup to specified destination.

    Path traversal via destination parameter.
    """
    service = AdminService()
    return await service.create_backup(destination)
