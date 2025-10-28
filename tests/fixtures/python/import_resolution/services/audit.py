"""Audit service demonstrating upward relative imports."""

from ..util.helpers import now_millis


class AuditService:
    def audit(self, event_name: str, payload) -> dict[str, object]:
        return {
            "event": event_name,
            "timestamp": now_millis(),
            "payload": payload,
        }
