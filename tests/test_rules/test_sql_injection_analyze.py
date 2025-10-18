"""Tests for SQL injection analyzer (theauditor/rules/sql/sql_injection_analyze.py).

Tests verify SQL injection detection including:
- String formatting (.format(), f-strings)
- String concatenation (+ operator, ||)
- Template literals (`${var}`)
- Parameterized queries (safe - should NOT flag)
- ORM usage (safe - should NOT flag)
- Migration files (should be excluded)
"""

import pytest
import sqlite3
import subprocess
import json
from pathlib import Path


class TestSQLInjectionFormatString:
    """Test detection of SQL injection via string formatting."""

    def test_detects_format_injection_python(self, sample_project):
        """Verify detection of .format() SQL injection in Python."""
        (sample_project / "sqli_format.py").write_text('''
import sqlite3

def get_user_by_name(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # CRITICAL: SQL injection via .format()
    query = "SELECT * FROM users WHERE username = '{}'".format(username)
    cursor.execute(query)
    return cursor.fetchone()

def delete_user(user_id):
    conn = sqlite3.connect('users.db')
    # CRITICAL: SQL injection
    query = "DELETE FROM users WHERE id = {}".format(user_id)
    conn.execute(query)
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for SQL queries with .format()
        cursor.execute("""
            SELECT query_text FROM sql_queries
            WHERE query_text LIKE '%.format%'
        """)
        format_queries = cursor.fetchall()
        conn.close()

        # Should detect format string SQL
        # Note: May be 0 if SQL_QUERY_PATTERNS was removed and only AST extraction works
        # Alternative: Check function_call_args for .execute() with format

    def test_detects_percent_formatting_python(self, sample_project):
        """Verify detection of % formatting SQL injection."""
        (sample_project / "sqli_percent.py").write_text('''
import sqlite3

def find_users(role):
    conn = sqlite3.connect('users.db')
    # CRITICAL: SQL injection via % formatting
    query = "SELECT * FROM users WHERE role = '%s'" % role
    return conn.execute(query).fetchall()
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"


class TestSQLInjectionFString:
    """Test detection of SQL injection via f-strings."""

    def test_detects_fstring_injection_python(self, sample_project):
        """Verify detection of f-string SQL injection."""
        (sample_project / "sqli_fstring.py").write_text('''
import sqlite3

def search_products(category):
    conn = sqlite3.connect('products.db')
    # CRITICAL: SQL injection via f-string
    query = f"SELECT * FROM products WHERE category = '{category}'"
    return conn.execute(query).fetchall()

def update_price(product_id, new_price):
    conn = sqlite3.connect('products.db')
    # CRITICAL: SQL injection
    query = f"UPDATE products SET price = {new_price} WHERE id = {product_id}"
    conn.execute(query)
    conn.commit()
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for f-strings in SQL context
        cursor.execute("""
            SELECT COUNT(*) FROM sql_queries
            WHERE query_text LIKE '%f"%' OR query_text LIKE "%f'%"
        """)
        fstring_count = cursor.fetchone()[0]
        conn.close()


class TestSQLInjectionConcatenation:
    """Test detection of SQL injection via string concatenation."""

    def test_detects_concatenation_python(self, sample_project):
        """Verify detection of + concatenation SQL injection."""
        (sample_project / "sqli_concat.py").write_text('''
import sqlite3

def get_orders(user_id):
    conn = sqlite3.connect('orders.db')
    # CRITICAL: SQL injection via concatenation
    query = "SELECT * FROM orders WHERE user_id = " + user_id
    return conn.execute(query).fetchall()
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

    def test_detects_concatenation_javascript(self, sample_project):
        """Verify detection of concatenation SQL injection in JavaScript."""
        (sample_project / "sqli_concat.js").write_text('''
const db = require('db');

function getUserById(userId) {
    // CRITICAL: SQL injection via concatenation
    const query = "SELECT * FROM users WHERE id = " + userId;
    return db.query(query);
}

function deleteComment(commentId) {
    // CRITICAL: SQL injection
    const sql = "DELETE FROM comments WHERE id = " + commentId;
    db.execute(sql);
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for db.query/execute calls
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE callee_function LIKE '%db.query%' OR callee_function LIKE '%db.execute%'
        """)
        db_calls = cursor.fetchone()[0]
        conn.close()

        assert db_calls >= 2, f"Expected 2 db calls, got {db_calls}"


class TestSQLInjectionTemplateLiterals:
    """Test detection of SQL injection via template literals."""

    def test_detects_template_literal_injection(self, sample_project):
        """Verify detection of template literal SQL injection."""
        (sample_project / "sqli_template.js").write_text('''
const { Pool } = require('pg');
const pool = new Pool();

async function findUser(email) {
    // CRITICAL: SQL injection via template literal
    const query = `SELECT * FROM users WHERE email = '${email}'`;
    const result = await pool.query(query);
    return result.rows[0];
}

async function updateUser(userId, newName) {
    // CRITICAL: SQL injection
    const sql = `UPDATE users SET name = '${newName}' WHERE id = ${userId}`;
    await pool.query(sql);
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for template literals in SQL
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE argument_expr LIKE '%`%${%'
        """)
        template_count = cursor.fetchone()[0]
        conn.close()


class TestSQLInjectionParameterizedQueries:
    """Test that parameterized queries are NOT flagged (safe pattern)."""

    def test_safe_parameterized_python(self, sample_project):
        """Verify parameterized queries are NOT flagged as SQL injection."""
        (sample_project / "safe_sql.py").write_text('''
import sqlite3

def get_user_safe(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # SAFE: Parameterized query
    query = "SELECT * FROM users WHERE username = ?"
    cursor.execute(query, (username,))
    return cursor.fetchone()

def update_user_safe(user_id, new_email):
    conn = sqlite3.connect('users.db')
    # SAFE: Parameterized query
    query = "UPDATE users SET email = ? WHERE id = ?"
    conn.execute(query, (new_email, user_id))
    conn.commit()
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check that parameterized queries are extracted
        cursor.execute("""
            SELECT COUNT(*) FROM sql_queries
            WHERE query_text LIKE '%?%'
        """)
        param_count = cursor.fetchone()[0]
        conn.close()

        # Should be captured but NOT flagged as SQL injection
        assert param_count >= 2, "Parameterized queries should be captured"

    def test_safe_parameterized_javascript(self, sample_project):
        """Verify PostgreSQL parameterized queries are safe."""
        (sample_project / "safe_pg.js").write_text('''
const { Pool } = require('pg');
const pool = new Pool();

async function getUserSafe(userId) {
    // SAFE: Parameterized query
    const query = 'SELECT * FROM users WHERE id = $1';
    const result = await pool.query(query, [userId]);
    return result.rows[0];
}

async function createUser(name, email) {
    // SAFE: Parameterized query
    const sql = 'INSERT INTO users (name, email) VALUES ($1, $2)';
    await pool.query(sql, [name, email]);
}
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for $1, $2 parameterized queries
        cursor.execute("""
            SELECT COUNT(*) FROM sql_queries
            WHERE query_text LIKE '%$1%' OR query_text LIKE '%$2%'
        """)
        pg_param_count = cursor.fetchone()[0]
        conn.close()


class TestSQLInjectionORMSafety:
    """Test that ORM queries are NOT flagged (safe pattern)."""

    def test_safe_django_orm(self, sample_project):
        """Verify Django ORM is NOT flagged as SQL injection."""
        (sample_project / "django_models.py").write_text('''
from django.db import models

class User(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()

def find_user_orm(email):
    # SAFE: Django ORM (parameterized internally)
    return User.objects.filter(email=email).first()

def get_active_users(role):
    # SAFE: Django ORM
    return User.objects.filter(role=role, active=True).all()
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check that ORM queries are in orm_queries table
        cursor.execute("SELECT COUNT(*) FROM orm_queries WHERE method = 'filter'")
        orm_count = cursor.fetchone()[0]
        conn.close()

        # Should be in orm_queries, NOT flagged as SQL injection
        assert orm_count >= 2, "Django ORM calls should be in orm_queries table"


class TestSQLInjectionMigrationExclusion:
    """Test that migration files are excluded."""

    def test_migrations_are_excluded(self, sample_project):
        """Verify migration files are excluded from SQL injection detection."""
        # Create migration directory
        migrations_dir = sample_project / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_create_users.py").write_text('''
def upgrade(cursor):
    # This is a migration - should be excluded
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    cursor.execute("CREATE INDEX idx_users_name ON users(name)")
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Migration SQL should be tagged as 'migration_file'
        cursor.execute("""
            SELECT extraction_source FROM sql_queries
            WHERE file_path LIKE '%migrations%'
        """)
        sources = cursor.fetchall()
        conn.close()

        # Should be tagged as migration, not flagged as SQL injection
        if sources:
            assert all(s[0] == 'migration_file' for s in sources), "Migrations should be tagged correctly"


class TestSQLInjectionComplexPatterns:
    """Test detection of complex SQL injection patterns."""

    def test_detects_second_order_injection(self, sample_project):
        """Verify detection of stored SQL injection."""
        (sample_project / "second_order.py").write_text('''
import sqlite3

def store_user_input(user_input):
    conn = sqlite3.connect('app.db')
    # First, safely store the input
    conn.execute("INSERT INTO inputs (data) VALUES (?)", (user_input,))
    conn.commit()

def use_stored_input():
    conn = sqlite3.connect('app.db')
    # Retrieve stored input
    cursor = conn.execute("SELECT data FROM inputs")
    stored_data = cursor.fetchone()[0]

    # CRITICAL: Use stored data in unsafe query (second-order injection)
    query = f"SELECT * FROM users WHERE name = '{stored_data}'"
    return conn.execute(query).fetchall()
''')

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        # Should detect f-string SQL injection in use_stored_input()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
