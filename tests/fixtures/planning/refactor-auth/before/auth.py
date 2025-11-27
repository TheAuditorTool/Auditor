"""
Auth module using Auth0 (to be refactored to AWS Cognito).
This represents the BEFORE state of a refactoring project.

Demonstrates:
- Import chain: auth.py → validators → exceptions
- Taint flow: request token → validation → user lookup → SQL
"""

import os
import sqlite3

from auth0 import Auth0Client
from validators import extract_permissions, extract_user_id, validate_auth0_token


class AuthService:
    """Authentication service using Auth0."""

    def __init__(self):
        self.auth0_domain = os.getenv("AUTH0_DOMAIN")
        self.client_id = os.getenv("AUTH0_CLIENT_ID")
        self.client = Auth0Client(
            domain=self.auth0_domain,
            client_id=self.client_id
        )

    def login(self, username, password):
        """Login using Auth0."""
        token = self.client.login(username, password)
        return {"access_token": token, "provider": "auth0"}

    def verify_token(self, token):
        """
        Verify Auth0 JWT token with full validation.

        Args:
            token: JWT token (TAINT SOURCE from request)

        Returns:
            Token payload with user info
        """
        # TAINT FLOW: Token validation via validators module
        payload = validate_auth0_token(token)

        # Extract user ID
        user_id = extract_user_id(payload)

        # TAINT FLOW: User lookup with raw SQL
        user_info = self._get_user_from_database(user_id)

        return {
            "payload": payload,
            "user": user_info,
            "permissions": extract_permissions(payload)
        }

    def _get_user_from_database(self, user_id):
        """
        Fetch user from local database using raw SQL.

        Args:
            user_id: User ID from Auth0 token (TAINT SOURCE)

        Returns:
            User dict
        """
        db_path = os.getenv('DATABASE_PATH', 'users.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Raw SQL query (tests sql_queries table)
        cursor.execute("""
            SELECT id, email, role, created_at
            FROM users
            WHERE auth0_user_id = ?
        """, (user_id,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'id': result[0],
                'email': result[1],
                'role': result[2],
                'created_at': result[3]
            }

        return None

    def get_user_info(self, user_id):
        """Get user info from Auth0."""
        return self.client.get_user(user_id)


# Global auth instance
auth = AuthService()
