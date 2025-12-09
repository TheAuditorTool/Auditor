"""Notification service - Additional service layer.

Handles notifications and callbacks.
"""


class NotificationService:
    """Notification service for sending alerts and callbacks."""

    async def send_callback(self, url: str, payload: dict) -> dict:
        """Send callback to URL.

        Args:
            url: TAINTED - SSRF vector
            payload: Data to send
        """
        from app.adapters.external_api import ExternalApiAdapter

        adapter = ExternalApiAdapter()
        return adapter.post(url, payload)

    async def notify_user(self, user_id: str, message: str) -> dict:
        """Send notification to user.

        Args:
            user_id: User identifier
            message: TAINTED - potential injection
        """
        return {"status": "sent", "user_id": user_id, "message": message}
