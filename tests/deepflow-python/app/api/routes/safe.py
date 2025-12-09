"""Safe routes - Sanitized path demonstrations.

These endpoints demonstrate SAFE patterns that should NOT be
flagged as vulnerable by TheAuditor.
"""

import re
from fastapi import APIRouter, Query, HTTPException

from app.services.safe_service import SafeService

router = APIRouter(prefix="/safe", tags=["safe"])


@router.get("/users/by-email")
async def get_user_by_email(email: str = Query(..., description="Email address")):
    """Get user by email with proper validation.

    SANITIZED PATH #1: Email regex validation.

    The email is validated with a strict regex before being used.
    TheAuditor should detect this sanitization and NOT flag it.
    """
    # SANITIZER: Regex validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # After validation, email is SANITIZED
    service = SafeService()
    return await service.get_by_email(email)


@router.get("/search")
async def safe_search(q: str = Query(..., description="Search query")):
    """Safe search with parameterized queries.

    SANITIZED PATH #2: Parameterized query.

    Uses parameterized SQL (?) instead of string concatenation.
    TheAuditor should detect this as safe.
    """
    service = SafeService()
    return await service.safe_search(q)


@router.post("/render")
async def safe_render(title: str = Query(...)):
    """Safe template rendering with HTML escaping.

    SANITIZED PATH #3: HTML escaping.

    Uses html.escape() before inserting into template.
    TheAuditor should detect this as safe (no XSS).
    """
    service = SafeService()
    return await service.safe_render(title)
