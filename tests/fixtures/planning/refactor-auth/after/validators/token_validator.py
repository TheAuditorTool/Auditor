"""
Token validation for AWS Cognito JWT tokens.

This file is part of the AFTER state (Cognito).
Demonstrates import chain: middleware → validators → exceptions
"""

import os

import jwt
import requests
from exceptions import ExpiredTokenError, InvalidTokenError
from jose import jwk
from jose import jwt as jose_jwt


def get_cognito_public_keys():
    """
    Fetch Cognito public keys for JWT verification.

    Returns:
        Dict of public keys
    """
    pool_id = os.getenv('COGNITO_USER_POOL_ID')
    region = os.getenv('AWS_REGION', 'us-east-1')

    keys_url = f'https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json'

    # TAINT SOURCE: External HTTP request
    response = requests.get(keys_url)
    keys = response.json()['keys']

    return {key['kid']: key for key in keys}


def validate_cognito_token(token):
    """
    Validate AWS Cognito JWT token.

    Args:
        token: JWT token string (TAINT SOURCE)

    Returns:
        Decoded token payload

    Raises:
        InvalidTokenError: Token is invalid
        ExpiredTokenError: Token has expired
    """
    # TAINT SOURCE: Token from request header
    try:
        # Get token header to find key ID
        headers = jwt.get_unverified_header(token)
        kid = headers.get('kid')

        if not kid:
            raise InvalidTokenError("Missing 'kid' in token header")

        # Get public key
        public_keys = get_cognito_public_keys()

        if kid not in public_keys:
            raise InvalidTokenError(f"Unknown key ID: {kid}")

        # TAINT FLOW: Token validation with Cognito public key
        public_key = jwk.construct(public_keys[kid])

        payload = jose_jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=os.getenv('COGNITO_CLIENT_ID'),
            issuer=f'https://cognito-idp.{os.getenv("AWS_REGION")}.amazonaws.com/{os.getenv("COGNITO_USER_POOL_ID")}'
        )

        # Verify token_use claim (must be 'access' or 'id')
        token_use = payload.get('token_use')
        if token_use not in ['access', 'id']:
            raise InvalidTokenError(f"Invalid token_use: {token_use}")

        return payload

    except jose_jwt.ExpiredSignatureError:
        raise ExpiredTokenError("Token has expired")

    except jose_jwt.JWTError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")


def extract_user_id(token_payload):
    """
    Extract user ID from Cognito token payload.

    Args:
        token_payload: Decoded JWT payload (from validate_cognito_token)

    Returns:
        User ID string
    """
    # Cognito uses 'sub' claim for user ID (UUID format)
    return token_payload.get('sub', '')


def extract_groups(token_payload):
    """
    Extract Cognito user groups from token.

    Args:
        token_payload: Decoded JWT payload

    Returns:
        List of group names
    """
    return token_payload.get('cognito:groups', [])


def extract_permissions(token_payload):
    """
    Extract custom permissions from Cognito token.

    Args:
        token_payload: Decoded JWT payload

    Returns:
        List of permission strings
    """
    # Custom permissions stored in custom:permissions claim
    permissions = token_payload.get('custom:permissions', '')

    if permissions:
        return permissions.split(',')

    return []
