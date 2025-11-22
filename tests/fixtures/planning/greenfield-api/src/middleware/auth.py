"""
Authentication and authorization middleware.

This fixture demonstrates:
- Decorator-based authentication controls
- Role-based access control (RBAC)
- Token validation patterns
- Middleware chaining for api_endpoint_controls testing
"""

from functools import wraps
from flask import request, g, abort, jsonify
import jwt
import os


def require_auth(f):
    """
    Authentication decorator.

    Verifies JWT token in Authorization header.
    This tests api_endpoint_controls extraction.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # TAINT SOURCE: Token from external input
        token = request.headers.get('Authorization')

        if not token:
            abort(401, description='Missing authorization token')

        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]

            # TAINT FLOW: Token validation
            # This demonstrates taint from request -> jwt.decode
            secret = os.getenv('JWT_SECRET', 'default-secret')
            payload = jwt.decode(token, secret, algorithms=['HS256'])

            # Store user info in request context
            g.user_id = payload.get('user_id')
            g.username = payload.get('username')

        except jwt.ExpiredSignatureError:
            abort(401, description='Token has expired')
        except jwt.InvalidTokenError:
            abort(401, description='Invalid token')

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
            # Assumes require_auth was already applied
            if not hasattr(g, 'user_id'):
                abort(401, description='Authentication required')

            # TAINT SOURCE: User ID from context
            user_id = g.user_id

            # Import here to avoid circular dependency
            from models import User
            from services.user_service import get_user_role

            # TAINT FLOW: User lookup with raw SQL (in user_service)
            user_role = get_user_role(user_id)

            if not user_role or user_role != role_name:
                abort(403, description=f'Requires {role_name} role')

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
            if not hasattr(g, 'user_id'):
                abort(401, description='Authentication required')

            # In a real app, would check permissions in database
            # For fixture purposes, admin role has all permissions
            from services.user_service import get_user_role

            user_role = get_user_role(g.user_id)

            # Simple permission check: admins have all permissions
            if user_role != 'admin':
                # Parse permission (e.g., 'products:create' -> resource:action)
                resource, action = permission.split(':') if ':' in permission else (permission, 'access')

                # Non-admins can only read products
                if action != 'read':
                    abort(403, description=f'Requires permission: {permission}')

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
            # In a real app, would check Redis or similar
            # For fixture purposes, just pass through
            # But this still tests that the decorator is tracked
            return f(*args, **kwargs)

        return decorated

    return decorator
