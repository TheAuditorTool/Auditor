"""Database layer - contains SQL injection sinks (TAINT SINKS)."""

import sqlite3

import psycopg2


class Database:
    """Database operations with SQL injection vulnerabilities.

    This demonstrates taint reaching sinks after cross-file propagation:
      controller.py (source) → service.py (propagation) → database.py (SINK)
    """

    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()

    def execute_search(self, query: str):
        """
        SINK: cursor.execute with tainted query parameter

        Expected vulnerability:
          SQL Injection - query comes from request.args.get('query') via service layer
        """
        # VULNERABLE: String concatenation in SQL query
        sql = f"SELECT * FROM users WHERE name = '{query}'"

        # SINK: Execute query with tainted data
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def get_user(self, user_id: str):
        """
        SINK: cursor.execute with tainted user_id parameter

        Expected vulnerability:
          SQL Injection - user_id comes from URL parameter via service layer
        """
        # VULNERABLE: Direct string formatting
        sql = "SELECT * FROM users WHERE id = " + user_id

        # SINK: Execute query with tainted data
        self.cursor.execute(sql)
        return self.cursor.fetchone()

    def dynamic_query(self, filter_expression: str):
        """
        SINK: cursor.execute with tainted filter_expression

        Expected vulnerability:
          SQL Injection - filter_expression comes from request.json via service layer
        """
        # VULNERABLE: User-controlled WHERE clause
        sql = f"SELECT * FROM records WHERE {filter_expression}"

        # SINK: Execute query with tainted data
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def batch_insert(self, data: dict):
        """
        SINK: cursor.execute with tainted data values

        Expected vulnerability:
          SQL Injection - data comes from batch processing in service layer
        """
        # VULNERABLE: String interpolation of user data
        columns = ', '.join(data.keys())
        values = ', '.join(f"'{v}'" for v in data.values())
        sql = f"INSERT INTO items ({columns}) VALUES ({values})"

        # SINK: Execute query with tainted data
        self.cursor.execute(sql)
        self.conn.commit()

    def raw_query(self, sql_string: str):
        """
        SINK: Direct execution of user-provided SQL

        Expected vulnerability:
          SQL Injection - worst case, entire SQL statement is user-controlled
        """
        # SINK: Execute arbitrary SQL
        self.cursor.execute(sql_string)
        return self.cursor.fetchall()

    def postgres_query(self, query: str):
        """
        SINK: PostgreSQL cursor.execute with tainted query

        Expected vulnerability:
          SQL Injection - demonstrates cross-database library support
        """
        pg_conn = psycopg2.connect("dbname=test")
        pg_cursor = pg_conn.cursor()

        # SINK: PostgreSQL execution
        pg_cursor.execute(query)
        return pg_cursor.fetchall()
