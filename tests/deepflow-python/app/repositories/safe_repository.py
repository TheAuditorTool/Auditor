"""Safe repository - Demonstrates secure database access.

Uses parameterized queries to prevent SQL injection.
"""

import sqlite3

from app.database import get_db


class SafeRepository:
    """Repository with safe query patterns.

    All methods use parameterized queries (?) instead of
    string concatenation, preventing SQL injection.
    """

    def find_by_email_safe(self, email: str) -> dict:
        """Find user by email using parameterized query.

        SAFE: Uses ? placeholder - SQL injection prevented.

        Args:
            email: Email address (already regex validated)
        """
        with get_db() as conn:
            cursor = conn.cursor()
            # SAFE: Parameterized query
            cursor.execute(
                "SELECT id, name, email FROM users WHERE email = ?",
                (email,)  # Parameter binding prevents injection
            )
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "name": row[1], "email": row[2]}
            return {"error": "User not found"}

    def search_safe(self, query: str) -> dict:
        """Search users safely using parameterized query.

        SAFE: Uses ? placeholder even for LIKE patterns.

        Args:
            query: Search term
        """
        with get_db() as conn:
            cursor = conn.cursor()
            # SAFE: Parameterized LIKE query
            # The % wildcards are part of the parameter, not the query
            cursor.execute(
                "SELECT id, name, email FROM users WHERE name LIKE ?",
                (f"%{query}%",)  # Parameter binding - safe even with LIKE
            )
            rows = cursor.fetchall()
            return {
                "results": [
                    {"id": row[0], "name": row[1], "email": row[2]}
                    for row in rows
                ],
                "count": len(rows),
            }

    def get_by_id_safe(self, user_id: int) -> dict:
        """Get user by ID safely.

        SAFE: Uses parameterized query with proper type.

        Args:
            user_id: User ID (integer)
        """
        with get_db() as conn:
            cursor = conn.cursor()
            # SAFE: Parameterized query
            cursor.execute(
                "SELECT id, name, email FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "name": row[1], "email": row[2]}
            return {"error": "User not found"}
