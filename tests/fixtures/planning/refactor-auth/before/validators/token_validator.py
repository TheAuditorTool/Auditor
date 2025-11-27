"""
Token validation for Auth0 JWT tokens.

This file is part of the BEFORE state (Auth0).
Demonstrates import chain: middleware → validators → exceptions
"""

import os

import jwt
from exceptions import ExpiredTokenError, InvalidTokenError


def validate_auth0_token(token):
    """
    Validate Auth0 JWT token.

    Args:
        token: JWT token string (TAINT SOURCE)

    Returns:
        Decoded token payload

    Raises:
        InvalidTokenError: Token is invalid
        ExpiredTokenError: Token has expired
    """
    # TAINT SOURCE: Token from request header
    secret = os.getenv('AUTH0_CLIENT_SECRET')

    try:
        # TAINT FLOW: Token validation
        payload = jwt.decode(
            token,
            secret,
            algorithms=['RS256'],
            audience=os.getenv('AUTH0_AUDIENCE')
        )

        # Verify required claims
        if 'sub' not in payload:
            raise InvalidTokenError("Missing 'sub' claim in token")

        if 'exp' not in payload:
            raise InvalidTokenError("Missing 'exp' claim in token")

        return payload

    except jwt.ExpiredSignatureError:
        raise ExpiredTokenError("Token has expired")

    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")


def extract_user_id(token_payload):
    """
    Extract user ID from Auth0 token payload.

    Args:
        token_payload: Decoded JWT payload (from validate_auth0_token)

    Returns:
        User ID string
    """
    # The 'sub' claim in Auth0 format: auth0|{user_id}
    sub = token_payload.get('sub', '')

    if sub.startswith('auth0|'):
        return sub[6:]  # Remove 'auth0|' prefix

    return sub


def extract_permissions(token_payload):
    """
    Extract permissions from Auth0 token.

    Args:
        token_payload: Decoded JWT payload

    Returns:
        List of permission strings
    """
    return token_payload.get('permissions', [])
