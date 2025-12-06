"""
Authentication and authorization middleware.

This fixture demonstrates:
- Decorator-based authentication controls
- Role-based access control (RBAC)
- Token validation patterns
- Middleware chaining for api_endpoint_controls testing
"""

import os
from functools import wraps

import jwt
from flask import abort, g, request


def require_auth(f):
    """
    Authentication decorator.

    Verifies JWT token in Authorization header.
    This tests api_endpoint_controls extraction.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            abort(401, description="Missing authorization token")

        try:
            if token.startswith("Bearer "):
                token = token[7:]

            secret = os.getenv("JWT_SECRET", "default-secret")
            payload = jwt.decode(token, secret, algorithms=["HS256"])

            g.user_id = payload.get("user_id")
            g.username = payload.get("username")

        except jwt.ExpiredSignatureError:
            abort(401, description="Token has expired")
        except jwt.InvalidTokenError:
            abort(401, description="Invalid token")

        return f(*args, **kwargs)

    return decorated


def require_role(role_name):
    """
    Role-based access control decorator.

    Ensures user has required role.
    This tests api_endpoint_controls extraction with parameterized decorators.

    Args:
        role_name: Required role (e.g., 'admin', 'manager')
    """

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "user_id"):
                abort(401, description="Authentication required")

            user_id = g.user_id

            from services.user_service import get_user_role

            user_role = get_user_role(user_id)

            if not user_role or user_role != role_name:
                abort(403, description=f"Requires {role_name} role")

            return f(*args, **kwargs)

        return decorated

    return decorator


def require_permission(permission):
    """
    Permission-based access control decorator.

    Fine-grained permission check (e.g., 'products:create', 'orders:delete').
    This tests api_endpoint_controls extraction with complex authorization.

    Args:
        permission: Required permission string
    """

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "user_id"):
                abort(401, description="Authentication required")

            from services.user_service import get_user_role

            user_role = get_user_role(g.user_id)

            if user_role != "admin":
                resource, action = (
                    permission.split(":") if ":" in permission else (permission, "access")
                )

                if action != "read":
                    abort(403, description=f"Requires permission: {permission}")

            return f(*args, **kwargs)

        return decorated

    return decorator


def rate_limit(requests_per_minute=60):
    """
    Rate limiting decorator.

    Demonstrates another type of control for api_endpoint_controls testing.

    Args:
        requests_per_minute: Maximum requests allowed per minute
    """

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            return f(*args, **kwargs)

        return decorated

    return decorator
