"""Authentication middleware - HOP 2: Passes tainted data through.

This middleware performs authentication but does NOT sanitize
the tainted parameters, allowing them to flow to deeper layers.
"""

from functools import wraps
from typing import Callable

from app.config import config


def require_auth(func: Callable) -> Callable:
    """Authentication decorator.

    HOP 2: Middleware passes tainted data through without sanitization.

    The decorator checks authentication but does not modify or sanitize
    any of the function parameters - tainted input flows through unchanged.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Authentication check would go here
        # CRITICAL: kwargs contain tainted parameters like 'q', 'filename', etc.
        # We pass them through WITHOUT sanitization

        # Simulate auth check (does not touch tainted params)
        _ = config.SECRET_KEY

        # All kwargs including tainted inputs pass through
        return await func(*args, **kwargs)

    return wrapper


def validate_token(token: str) -> bool:
    """Validate an authentication token.

    Note: This does NOT sanitize any user input - it only validates tokens.
    Tainted data from request parameters is not affected.
    """
    if not token:
        return False
    # Simple validation - does not touch tainted request data
    return token.startswith("Bearer ")
