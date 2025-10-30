"""
Auth module using AWS Cognito (refactored from Auth0).
This represents the AFTER state of a refactoring project.

Demonstrates:
- Import chain: auth.py → validators → exceptions
- Taint flow: request token → validation → user lookup → SQL
- Migration from Auth0 to Cognito patterns
"""

from aws_cognito import CognitoIdentityClient
from validators import validate_cognito_token, extract_user_id, extract_groups, extract_permissions
from exceptions import InvalidTokenError, ExpiredTokenError
import os
import sqlite3


class AuthService:
    """Authentication service using AWS Cognito."""

    def __init__(self):
        self.cognito_pool_id = os.getenv("COGNITO_USER_POOL_ID")
        self.cognito_client_id = os.getenv("COGNITO_CLIENT_ID")
        self.client = CognitoIdentityClient(
            user_pool_id=self.cognito_pool_id,
            client_id=self.cognito_client_id
        )

    def login(self, username, password):
        """Login using AWS Cognito."""
        token = self.client.authenticate(username, password)
        return {"access_token": token, "provider": "cognito"}

    def verify_token(self, token):
        """
        Verify Cognito JWT token with full validation.

        Args:
            token: JWT token (TAINT SOURCE from request)

        Returns:
            Token payload with user info
        """
        # TAINT FLOW: Token validation via validators module
        payload = validate_cognito_token(token)

        # Extract user ID
        user_id = extract_user_id(payload)

        # TAINT FLOW: User lookup with raw SQL
        user_info = self._get_user_from_database(user_id)

        return {
            "payload": payload,
            "user": user_info,
            "groups": extract_groups(payload),
            "permissions": extract_permissions(payload)
        }

    def _get_user_from_database(self, user_id):
        """
        Fetch user from local database using raw SQL.

        Args:
            user_id: User ID from Cognito token (TAINT SOURCE)

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
            WHERE cognito_user_id = ?
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
        """Get user info from Cognito."""
        return self.client.get_user_attributes(user_id)


# Global auth instance
auth = AuthService()
