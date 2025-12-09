"""Query builder - HOPs 11-16: SQL query construction.

This is the SQL INJECTION SINK. Tainted user input is concatenated
into SQL queries and executed.
"""

import sqlite3

from app.utils.string_utils import clean_whitespace
from app.utils.serializers import serialize_result


class QueryBuilder:
    """SQL query builder.

    HOPs 11-16: Final destination for tainted search terms.
    Constructs SQL using string concatenation (VULNERABLE).

    VULNERABILITY: SQL Injection - User input is concatenated into SQL.
    """

    def __init__(self):
        self.conn = sqlite3.connect("deepflow.db")
        self.conn.row_factory = sqlite3.Row

    def build_user_search(self, term: str) -> dict:
        """Build and execute user search query.

        HOPS 11-16: SQL INJECTION SINK.

        Args:
            term: TAINTED search term from user input

        VULNERABILITY: f-string SQL concatenation allows injection.
        Payload: ' OR '1'='1' --
        """
        # HOP 11: Build base query
        base = "SELECT * FROM users WHERE "

        # HOP 12: Add condition (VULNERABLE - string concatenation)
        term = clean_whitespace(term)  # HOP 14 - still TAINTED
        condition = f"name LIKE '%{term}%'"  # term is TAINTED!

        # HOP 13: Combine
        query = base + condition

        # HOP 14: Add ordering
        query += " ORDER BY created_at DESC"

        # HOP 15: Add limit
        query += " LIMIT 100"

        # HOP 16: Execute (SQL INJECTION SINK)
        cursor = self.conn.cursor()
        try:
            cursor.execute(query)  # VULNERABLE: Tainted query executed
            rows = cursor.fetchall()
            return serialize_result([dict(row) for row in rows])
        except Exception as e:
            return {"error": str(e), "query": query}

    def build_user_lookup(self, user_id: str) -> dict:
        """Build and execute user lookup query.

        SQL INJECTION SINK.

        Args:
            user_id: TAINTED user ID

        VULNERABILITY: String concatenation in WHERE clause.
        """
        # VULNERABLE: Direct string interpolation
        query = f"SELECT * FROM users WHERE id = {user_id}"  # TAINTED

        cursor = self.conn.cursor()
        try:
            cursor.execute(query)  # SQL INJECTION SINK
            row = cursor.fetchone()
            return serialize_result(dict(row) if row else {})
        except Exception as e:
            return {"error": str(e)}

    def build_email_lookup(self, email: str) -> dict:
        """Build email lookup query (SAFE VERSION).

        This version uses parameterized queries and is NOT vulnerable.
        Used to demonstrate sanitized path detection.

        Args:
            email: Email address (should be sanitized before reaching here)
        """
        # SAFE: Parameterized query prevents SQL injection
        query = "SELECT * FROM users WHERE email = ?"

        cursor = self.conn.cursor()
        try:
            cursor.execute(query, (email,))  # SAFE: Parameter binding
            row = cursor.fetchone()
            return serialize_result(dict(row) if row else {})
        except Exception as e:
            return {"error": str(e)}
