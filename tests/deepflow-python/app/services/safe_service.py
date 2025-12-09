"""Safe service - Demonstrates sanitized patterns.

These methods use secure coding practices that should be
recognized by TheAuditor as NOT vulnerable.
"""

from app.repositories.safe_repository import SafeRepository
from app.core.template_renderer import TemplateRenderer


class SafeService:
    """Service with safe implementations.

    All methods here use proper sanitization and should NOT
    be flagged as vulnerable.
    """

    def __init__(self):
        self.repo = SafeRepository()
        self.renderer = TemplateRenderer()

    async def get_by_email(self, email: str) -> dict:
        """Get user by email.

        The email has already been validated by regex in the route.
        This uses parameterized queries for additional safety.

        Args:
            email: SANITIZED email (regex validated)
        """
        return self.repo.find_by_email_safe(email)

    async def safe_search(self, query: str) -> dict:
        """Safe search using parameterized queries.

        Args:
            query: Search query (will be parameterized, not concatenated)
        """
        return self.repo.search_safe(query)

    async def safe_render(self, title: str) -> dict:
        """Safe template rendering with HTML escaping.

        Args:
            title: Title to render (will be HTML escaped)
        """
        html = self.renderer.render_safe(title, {"type": "safe_demo"})
        return {"html": html, "sanitized": True}
