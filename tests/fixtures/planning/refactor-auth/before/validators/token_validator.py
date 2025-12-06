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

    secret = os.getenv("AUTH0_CLIENT_SECRET")

    try:
        payload = jwt.decode(
            token, secret, algorithms=["RS256"], audience=os.getenv("AUTH0_AUDIENCE")
        )

        if "sub" not in payload:
            raise InvalidTokenError("Missing 'sub' claim in token")

        if "exp" not in payload:
            raise InvalidTokenError("Missing 'exp' claim in token")

        return payload

    except jwt.ExpiredSignatureError as e:
        raise ExpiredTokenError("Token has expired") from e

    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}") from e


def extract_user_id(token_payload):
    """
    Extract user ID from Auth0 token payload.

    Args:
        token_payload: Decoded JWT payload (from validate_auth0_token)

    Returns:
        User ID string
    """

    sub = token_payload.get("sub", "")

    if sub.startswith("auth0|"):
        return sub[6:]

    return sub


def extract_permissions(token_payload):
    """
    Extract permissions from Auth0 token.

    Args:
        token_payload: Decoded JWT payload

    Returns:
        List of permission strings
    """
    return token_payload.get("permissions", [])
