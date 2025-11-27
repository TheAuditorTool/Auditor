"""
Controllers Module (Part of Circular Import Pattern)

Tests extraction when:
- This module imports from BOTH models.py AND services.py
- models.py imports from services.py (TYPE_CHECKING)
- services.py imports from models.py (direct)
- Creates circular triangle: models ↔ services ↔ controllers

Validates that import resolution handles complex circular dependency graphs.
"""


# Import from both modules that have circular dependency with each other
from models import Comment, Post, User
from services import CommentService, PostService, UserService


class UserController:
    """
    User controller coordinating models and services.
    Tests: Controller in middle of circular import triangle.
    """

    def get_user(self, user_id: int) -> User | None:
        """
        Get user by ID.
        Tests: Method returning circularly imported model.
        """
        # Would fetch from database
        user = User(user_id=user_id, username="user", email="user@example.com")
        return user

    def create_user(self, username: str, email: str) -> User:
        """
        Create new user.
        Tests: Method creating model and returning service.
        """
        user = User(user_id=0, username=username, email=email)

        # Get service for the user (circular: User → UserService)
        user.get_service()

        return user

    def update_user_email(self, user_id: int, new_email: str) -> bool:
        """
        Update user email using service.
        Tests: Method using both model and service (circular imports).
        """
        user = self.get_user(user_id)
        if user:
            service = UserService(user)
            return service.update_email(new_email)
        return False

    def delete_user_cascade(self, user_id: int) -> bool:
        """
        Delete user and cascade to related data.
        Tests: Complex operation involving multiple circular imports.
        """
        user = self.get_user(user_id)
        if user:
            # Get user's posts
            service = UserService(user)
            posts = service.get_user_posts()

            # Delete each post (involves PostService, CommentService)
            for post in posts:
                post_controller = PostController()
                post_controller.delete_post(post.post_id)

            # Delete user
            return True
        return False


class PostController:
    """
    Post controller.
    Tests: Second controller in circular import web.
    """

    def get_post(self, post_id: int) -> Post | None:
        """Get post by ID."""
        return Post(
            post_id=post_id,
            author_id=1,
            title="Sample Post",
            content="Content"
        )

    def create_post(self, author_id: int, title: str, content: str) -> Post:
        """
        Create new post.
        Tests: Method creating Post model (circular import).
        """
        post = Post(
            post_id=0,
            author_id=author_id,
            title=title,
            content=content
        )

        # Get author user (circular: Post → User via author)
        post.get_author()

        return post

    def add_comment_to_post(self, post_id: int, author_id: int, text: str) -> Comment:
        """
        Add comment to post.
        Tests: Method involving Post, Comment, and services.
        """
        post = self.get_post(post_id)
        if post:
            service = PostService(post)
            comment = service.add_comment(author_id, text)
            return comment

        return Comment(comment_id=0, post_id=post_id, author_id=author_id, text=text)

    def delete_post(self, post_id: int) -> bool:
        """
        Delete post and comments.
        Tests: Cascade deletion through circular imports.
        """
        post = self.get_post(post_id)
        if post:
            # Delete comments first
            comment_service = CommentService(post_id)
            comment_service.get_comments()

            # Would delete each comment

            return True
        return False


class CommentController:
    """
    Comment controller.
    Tests: Third controller completing complex circular import graph.
    """

    def create_comment(self, post_id: int, author_id: int, text: str) -> Comment:
        """Create comment."""
        return Comment(
            comment_id=0,
            post_id=post_id,
            author_id=author_id,
            text=text
        )

    def get_comment_author(self, comment: Comment) -> User | None:
        """
        Get comment author.
        Tests: Traversing circular import graph (Comment → User).
        """
        user_controller = UserController()
        return user_controller.get_user(comment.author_id)

    def get_comment_post(self, comment: Comment) -> Post | None:
        """
        Get comment's post.
        Tests: Circular traversal (Comment → Post → User → Service).
        """
        post_controller = PostController()
        return post_controller.get_post(comment.post_id)
