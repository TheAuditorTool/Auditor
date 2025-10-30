"""
Utils Module (Part of Circular Import Pattern)

Tests extraction when:
- This module imports from controllers.py
- controllers.py imports from models.py and services.py
- models.py and services.py import each other
- Creates 4-way circular dependency chain

Validates deep circular import resolution.
"""

from typing import List, Dict, Any

# Import from controllers (which imports from models and services)
from controllers import UserController, PostController, CommentController


def get_user_summary(user_id: int) -> Dict[str, Any]:
    """
    Get user summary including posts and comments.
    Tests: Utility function using circular import chain.
    """
    controller = UserController()
    user = controller.get_user(user_id)

    if not user:
        return {}

    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "validation": user.validate()
    }


def bulk_update_user_emails(user_ids: List[int], new_domain: str) -> List[bool]:
    """
    Bulk update user emails.
    Tests: Bulk operation through circular imports.
    """
    controller = UserController()
    results = []

    for user_id in user_ids:
        user = controller.get_user(user_id)
        if user:
            # Extract username and create new email
            new_email = f"{user.username}@{new_domain}"
            success = controller.update_user_email(user_id, new_email)
            results.append(success)
        else:
            results.append(False)

    return results


def get_post_with_comments(post_id: int) -> Dict[str, Any]:
    """
    Get post with all its comments.
    Tests: Deep traversal through circular imports.
    """
    post_controller = PostController()
    comment_controller = CommentController()

    post = post_controller.get_post(post_id)
    if not post:
        return {}

    # Get post author (involves User model - circular)
    author = post.get_author()

    return {
        "post_id": post.post_id,
        "title": post.title,
        "content": post.content,
        "author": author.to_dict() if author else None
    }


def search_users_and_posts(query: str) -> Dict[str, List[Any]]:
    """
    Search across users and posts.
    Tests: Multiple circular import paths in one function.
    """
    user_controller = UserController()
    post_controller = PostController()

    # Would search in real code
    # This function demonstrates multiple circular import dependencies
    return {
        "users": [],
        "posts": []
    }


# Import at module level (tests top-level circular import)
from models import User, Post


def create_post_with_author(username: str, email: str, title: str, content: str) -> Post:
    """
    Create user and post in one operation.
    Tests: Function using multiple circularly imported models.
    """
    # Create user
    user = User(user_id=0, username=username, email=email)

    # Create post for user
    post = Post(
        post_id=0,
        author_id=user.user_id,
        title=title,
        content=content
    )

    return post
