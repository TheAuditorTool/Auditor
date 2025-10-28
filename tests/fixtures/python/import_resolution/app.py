"""Entry point exercising intra-package imports."""

from .api.controllers import register_routes
from .services.audit import AuditService
from .services.user import UserService


def bootstrap() -> UserService:
    audit = AuditService()
    service = UserService(audit_service=audit)
    register_routes(service)
    return service
