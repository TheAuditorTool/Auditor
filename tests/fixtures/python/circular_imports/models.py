"""
Models Module (Part of Circular Import Pattern)

Tests extraction when:
- This module imports from services.py (TYPE_CHECKING guard)
- services.py imports from this module (direct import)
- Creates circular dependency: models ↔ services

Validates that import resolution doesn't infinite loop or crash.
"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from services import UserService


class User:
    """
    User model with reference to UserService.
    Tests: Forward reference to circularly imported class.
    """

    def __init__(self, user_id: int, username: str, email: str):
        self.user_id = user_id
        self.username = username
        self.email = email
        self._service: UserService | None = None

    def get_service(self) -> UserService:
        """
        Lazy load UserService to avoid circular import at runtime.
        Tests: Runtime import resolution inside method.
        """
        if self._service is None:
            from services import UserService

            self._service = UserService(self)
        return self._service

    def validate(self) -> bool:
        """Validate user data."""
        return bool(self.username and self.email and "@" in self.email)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {"user_id": self.user_id, "username": self.username, "email": self.email}


class Post:
    """
    Post model that also references services.
    Tests: Multiple classes with circular dependencies.
    """

    def __init__(self, post_id: int, author_id: int, title: str, content: str):
        self.post_id = post_id
        self.author_id = author_id
        self.title = title
        self.content = content

    def get_author(self) -> User | None:
        """
        Get post author using UserService.
        Tests: Method that imports from circular module.
        """

        return None

    def get_comment_service(self):
        """
        Get comment service for this post.
        Tests: Another circular import path.
        """
        from services import CommentService

        return CommentService(self.post_id)


class Comment:
    """
    Comment model.
    Tests: Third class in circular import scenario.
    """

    def __init__(self, comment_id: int, post_id: int, author_id: int, text: str):
        self.comment_id = comment_id
        self.post_id = post_id
        self.author_id = author_id
        self.text = text

    def get_post(self) -> Post | None:
        """Get the parent post."""

        return None
