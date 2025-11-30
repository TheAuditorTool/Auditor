"""
Authentication exceptions for Auth0.

This file is part of the BEFORE state (Auth0).
"""


class AuthenticationError(Exception):
    """Base exception for authentication errors."""

    pass


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""

    pass


class ExpiredTokenError(AuthenticationError):
    """Raised when JWT token has expired."""

    pass


class Auth0ConnectionError(AuthenticationError):
    """Raised when cannot connect to Auth0 service."""

    pass


class InsufficientPermissionsError(AuthenticationError):
    """Raised when user lacks required permissions."""

    pass
