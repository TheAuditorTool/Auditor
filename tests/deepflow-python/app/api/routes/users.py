"""User routes - HOP 1: Taint sources from HTTP requests.

This module contains endpoints that accept user input, which becomes
the SOURCE of taint in our vulnerability chains.
"""

from fastapi import APIRouter, Query, Request

from app.api.middleware.auth import require_auth
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/search")
@require_auth
async def search_users(q: str = Query(..., description="Search query")):
    """Search users by name.

    HOP 1: Taint SOURCE - user input from query parameter 'q'.
    This input flows through 16 layers to reach a SQL sink.

    VULNERABILITY: SQL Injection (16 hops)
    """
    service = UserService()
    return await service.search(q)  # q is TAINTED, passed to HOP 2


@router.get("/{user_id}")
@require_auth
async def get_user(user_id: str):
    """Get user by ID.

    HOP 1: Taint SOURCE - user input from path parameter.
    """
    service = UserService()
    return await service.get_by_id(user_id)
