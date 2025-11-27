"""Flask blueprint to mirror admin-style routes."""


from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Blueprint, jsonify, request

from ..services.accounts import AccountService
from .deps import get_email_service, get_repository

admin = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that ensures admin access (no-op for fixtures)."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        request.environ.setdefault("is_admin", True)
        return func(*args, **kwargs)

    return wrapper


@admin.route("/audits", methods=["GET"])
@admin_required
def list_audits() -> Any:
    """Return audit log metadata to exercise Flask route extraction."""

    service = AccountService(
        repository=get_repository(),
        email_service=get_email_service(),
    )
    audits = [
        {"event": entry.event_type, "actor": entry.actor.email}
        for entry in service.stream_audit_events(limit=10)
    ]
    return jsonify({"audits": audits})
