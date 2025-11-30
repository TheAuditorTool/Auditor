"""
Authentication exceptions for AWS Cognito.

This file is part of the AFTER state (Cognito).
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


class CognitoServiceError(AuthenticationError):
    """Raised when cannot connect to Cognito service."""

    pass


class InsufficientPermissionsError(AuthenticationError):
    """Raised when user lacks required permissions."""

    pass
