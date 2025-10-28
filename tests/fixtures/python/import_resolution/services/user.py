"""User service making intra-package imports."""

from __future__ import annotations

from typing import Any, Optional

from ..util.helpers import now_millis
from .repository import UserRepository


class UserService:
    def __init__(self, audit_service: Optional["AuditService"] = None) -> None:
        self.repository = UserRepository()
        self.audit_service = audit_service

    def create_user(self, email: str) -> dict[str, Any]:
        record = {"email": email, "created_at": now_millis()}
        self.repository.save(record)
        if self.audit_service:
            self.audit_service.audit("user.created", record)
        return record

    def touch(self, slug: str) -> None:
        payload = {"slug": slug, "touched_at": now_millis()}
        if self.audit_service:
            self.audit_service.audit("user.touched", payload)


from .audit import AuditService  # noqa: E402  (circular for typing only)
