"""
Services Module (Part of Circular Import Pattern)

Tests extraction when:
- This module imports from models.py (DIRECT import)
- models.py imports from this module (TYPE_CHECKING guard)
- Creates circular dependency: models ↔ services

Validates that import resolution handles circular imports without crashing.
"""


# DIRECT import from models - creates circular dependency
from models import Comment, Post, User


class UserService:
    """
    User service that operates on User model.
    Tests: Service class with circular dependency to User model.
    """

    def __init__(self, user: User):
        self.user = user

    def update_email(self, new_email: str) -> bool:
        """
        Update user email.
        Tests: Method that modifies circularly imported model.
        """
        if "@" in new_email:
            self.user.email = new_email
            return True
        return False

    def get_user_posts(self) -> list[Post]:
        """
        Get all posts for this user.
        Tests: Method returning list of circularly imported models.
        """
        # Would query from database in real code
        return []

    def delete_user(self) -> bool:
        """Delete user and cascade to posts."""
        # Would use controllers in real code
        from controllers import UserController
        controller = UserController()
        return controller.delete_user_cascade(self.user.user_id)


class PostService:
    """
    Post service that operates on Post model.
    Tests: Another service with circular dependencies.
    """

    def __init__(self, post: Post):
        self.post = post

    def publish(self) -> bool:
        """Publish the post."""
        # Would update database
        return True

    def get_author(self) -> User | None:
        """
        Get post author.
        Tests: Method returning circularly imported User model.
        """
        # This creates a cycle: PostService → User (from models)
        # But User.get_service() → UserService (from services)
        return User(
            user_id=self.post.author_id,
            username="author",
            email="author@example.com"
        )

    def add_comment(self, author_id: int, text: str) -> Comment:
        """
        Add comment to post.
        Tests: Method creating Comment instance (circular import).
        """
        comment = Comment(
            comment_id=0,
            post_id=self.post.post_id,
            author_id=author_id,
            text=text
        )
        return comment


class CommentService:
    """
    Comment service.
    Tests: Third service in circular import web.
    """

    def __init__(self, post_id: int):
        self.post_id = post_id

    def get_comments(self) -> list[Comment]:
        """Get all comments for post."""
        return []

    def get_post(self) -> Post | None:
        """
        Get the post this service is for.
        Tests: Circular path through multiple modules.
        """
        # Imports from controllers which imports from models
        from controllers import PostController
        controller = PostController()
        return controller.get_post(self.post_id)


# Module-level function that uses models
def create_user(username: str, email: str) -> User:
    """
    Factory function to create User.
    Tests: Module-level function with circular import dependency.
    """
    user = User(user_id=0, username=username, email=email)
    return user


def bulk_create_users(users_data: list[dict]) -> list[User]:
    """
    Bulk create users.
    Tests: Function returning list of circularly imported models.
    """
    users = []
    for data in users_data:
        user = create_user(data["username"], data["email"])
        users.append(user)
    return users
