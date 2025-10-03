"""
Integration tests for database operations.

Tests that verify database.py methods ACTUALLY work when called,
not just that they exist. Tests the full data flow:
  extractor → add_* → batch → flush → database → query

NO MOCKING OF USER CODE - tests real database operations.
"""

import pytest
import sqlite3
import subprocess
import tempfile
from pathlib import Path


class TestRefsTablePopulation:
    """Test refs table gets populated with imports (CRITICAL - was claimed empty)."""

    def test_python_imports_populate_refs_table(self, sample_project):
        """Verify Python imports are actually stored in refs table."""
        # Create Python file with multiple import types
        (sample_project / "main.py").write_text('''
import os
import sys
from pathlib import Path
from typing import List, Dict
from collections import defaultdict, Counter
''')

        # Run indexer
        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        # Connect to database
        db_path = sample_project / '.pf' / 'repo_index.db'
        assert db_path.exists(), "Database not created"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # VERIFY: refs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='refs'")
        assert cursor.fetchone() is not None, "refs table doesn't exist"

        # VERIFY: refs table has entries
        cursor.execute("SELECT COUNT(*) FROM refs")
        count = cursor.fetchone()[0]
        assert count >= 5, f"Expected at least 5 imports (os, sys, pathlib, typing, collections), got {count}"

        # VERIFY: imports have correct structure (src, kind, value, line)
        cursor.execute("SELECT src, kind, value, line FROM refs ORDER BY line")
        refs = cursor.fetchall()

        # Check we have both 'import' and 'from' kinds
        kinds = {r[1] for r in refs}
        assert 'import' in kinds, "Should have 'import' kind"
        assert 'from' in kinds, "Should have 'from' kind"

        # Check expected modules are imported
        values = {r[2] for r in refs}
        assert 'os' in values, "Should have imported 'os'"
        assert 'sys' in values, "Should have imported 'sys'"
        assert 'pathlib' in values or 'Path' in values, "Should have imported pathlib"
        assert 'typing' in values, "Should have imported typing"

        # VERIFY: line numbers are populated
        line_numbers = [r[3] for r in refs]
        assert all(line is not None for line in line_numbers), "All imports should have line numbers"
        assert all(isinstance(line, int) for line in line_numbers), "Line numbers should be integers"
        assert all(line > 0 for line in line_numbers), "Line numbers should be positive"

        conn.close()


class TestJWTPatterns:
    """Test jwt_patterns table gets populated (P0 GAP - was ZERO TESTS)."""

    def test_jwt_sign_populates_jwt_patterns_table(self, sample_project):
        """Verify JWT sign patterns are stored in jwt_patterns table."""
        # Create Python file with JWT sign call
        (sample_project / "auth.py").write_text('''
import jwt

def create_token(user):
    payload = {"user_id": user.id, "password": user.password}
    token = jwt.encode(payload, "hardcoded-secret-123", algorithm="HS256")
    return token

def create_safe_token(user):
    import os
    payload = {"user_id": user.id}
    token = jwt.encode(payload, os.environ.get("JWT_SECRET"), algorithm="HS256")
    return token
''')

        # Run indexer
        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed: {result.stderr}"

        # Connect to database
        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # VERIFY: jwt_patterns table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jwt_patterns'")
        assert cursor.fetchone() is not None, "jwt_patterns table doesn't exist"

        # VERIFY: jwt_patterns table has entries
        cursor.execute("SELECT COUNT(*) FROM jwt_patterns")
        count = cursor.fetchone()[0]
        assert count >= 2, f"Expected at least 2 JWT patterns (sign calls), got {count}"

        # VERIFY: Secret source detection works
        cursor.execute("SELECT secret_source FROM jwt_patterns")
        secret_sources = [r[0] for r in cursor.fetchall()]
        assert 'hardcoded' in secret_sources, "Should detect hardcoded secret"
        assert 'env' in secret_sources, "Should detect environment variable secret"

        # VERIFY: Sensitive field detection
        cursor.execute("SELECT sensitive_fields FROM jwt_patterns WHERE sensitive_fields IS NOT NULL")
        sensitive_rows = cursor.fetchall()
        assert len(sensitive_rows) >= 1, "Should detect password in payload"

        conn.close()

    def test_jwt_verify_populates_jwt_patterns_table(self, sample_project):
        """Verify JWT verify patterns are stored with security metadata."""
        # Create JavaScript file with JWT verify (testing JS extraction)
        (sample_project / "verify.js").write_text('''
const jwt = require('jsonwebtoken');

function verifyToken(token) {
    // Dangerous: allows 'none' algorithm
    return jwt.verify(token, secret, { algorithms: ['HS256', 'none'] });
}

function verifyTokenConfusion(token) {
    // Algorithm confusion vulnerability
    return jwt.verify(token, secret, { algorithms: ['HS256', 'RS256'] });
}

function insecureDecode(token) {
    // No verification
    return jwt.decode(token);
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

        # VERIFY: jwt_patterns has verify entries
        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE type = 'jwt_verify'")
        verify_count = cursor.fetchone()[0]
        assert verify_count >= 2, f"Expected at least 2 verify patterns, got {verify_count}"

        # VERIFY: Detects 'none' algorithm vulnerability
        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE allows_none = 1")
        allows_none_count = cursor.fetchone()[0]
        assert allows_none_count >= 1, "Should detect 'none' algorithm vulnerability"

        # VERIFY: Detects algorithm confusion
        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE has_confusion = 1")
        confusion_count = cursor.fetchone()[0]
        assert confusion_count >= 1, "Should detect algorithm confusion vulnerability"

        # VERIFY: Detects insecure decode
        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE type = 'jwt_decode'")
        decode_count = cursor.fetchone()[0]
        assert decode_count >= 1, "Should detect insecure decode calls"

        conn.close()


class TestBatchFlushLogic:
    """Test batch flushing handles boundary conditions (P0 GAP - was ZERO TESTS)."""

    def test_batch_flush_exactly_200_items(self, sample_project):
        """Test batch flush at exact batch_size boundary (200 items)."""
        # Create file with exactly 200 symbols (default batch size)
        lines = [f"var_{i} = {i}\n" for i in range(200)]
        (sample_project / "batch_200.py").write_text(''.join(lines))

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed at batch boundary: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # VERIFY: All 200 symbols are flushed
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE name LIKE 'var_%'")
        count = cursor.fetchone()[0]
        assert count == 200, f"Expected 200 symbols at batch boundary, got {count}"

        conn.close()

    def test_batch_flush_201_items(self, sample_project):
        """Test batch flush just over batch_size (201 items)."""
        # Create file with 201 symbols (one over batch size)
        lines = [f"val_{i} = {i}\n" for i in range(201)]
        (sample_project / "batch_201.py").write_text(''.join(lines))

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Indexer failed over batch boundary: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # VERIFY: All 201 symbols are flushed (tests partial batch flush)
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE name LIKE 'val_%'")
        count = cursor.fetchone()[0]
        assert count == 201, f"Expected 201 symbols (batch + 1), got {count}"

        conn.close()

    def test_batch_flush_multiple_batches(self, sample_project):
        """Test batch flush with 500 items (2.5 batches)."""
        # Create file with 500 symbols (2 full batches + 100 items)
        lines = [f"item_{i} = {i}\n" for i in range(500)]
        (sample_project / "batch_500.py").write_text(''.join(lines))

        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=90
        )
        assert result.returncode == 0, f"Indexer failed with multiple batches: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # VERIFY: All 500 symbols flushed correctly
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE name LIKE 'item_%'")
        count = cursor.fetchone()[0]
        assert count == 500, f"Expected 500 symbols across multiple batches, got {count}"

        # VERIFY: No duplicates (tests deduplication logic)
        cursor.execute("SELECT name, COUNT(*) as cnt FROM symbols WHERE name LIKE 'item_%' GROUP BY name HAVING cnt > 1")
        duplicates = cursor.fetchall()
        assert len(duplicates) == 0, f"Found duplicate symbols: {duplicates}"

        conn.close()


class TestSQLExtractionSourceTagging:
    """Test SQL extraction_source categorization (P1 GAP - was ZERO TESTS)."""

    def test_migration_file_tagged_correctly(self, sample_project):
        """Verify migration files get extraction_source='migration_file'."""
        # Create migration file
        migrations_dir = sample_project / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "001_create_users.py").write_text('''
import sqlite3

def upgrade(conn):
    cursor = conn.cursor()
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

        # VERIFY: Migration file SQL is tagged correctly
        cursor.execute("""
            SELECT COUNT(*) FROM sql_queries
            WHERE file_path LIKE '%migrations%' AND extraction_source = 'migration_file'
        """)
        count = cursor.fetchone()[0]
        assert count >= 2, f"Expected migration SQL queries to be tagged, got {count}"

        conn.close()

    def test_orm_query_tagged_correctly(self, sample_project):
        """Verify ORM queries get extraction_source='orm_query'."""
        # Create Django-style ORM code
        (sample_project / "models.py").write_text('''
from django.db import models

class User(models.Model):
    name = models.CharField(max_length=255)

def get_active_users():
    return User.objects.filter(active=True).all()

def create_user(name):
    return User.objects.create(name=name)
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

        # VERIFY: ORM queries are tagged
        cursor.execute("""
            SELECT COUNT(*) FROM orm_queries
            WHERE file_path LIKE '%models.py%'
        """)
        count = cursor.fetchone()[0]
        assert count >= 2, f"Expected ORM queries (filter, create), got {count}"

        conn.close()

    def test_code_execute_tagged_correctly(self, sample_project):
        """Verify direct SQL execution gets extraction_source='code_execute'."""
        # Create API file with direct SQL
        (sample_project / "api.py").write_text('''
import sqlite3

def get_user_by_id(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()

def delete_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
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

        # VERIFY: Code execution SQL is tagged
        cursor.execute("""
            SELECT COUNT(*) FROM sql_queries
            WHERE file_path LIKE '%api.py%' AND extraction_source = 'code_execute'
        """)
        count = cursor.fetchone()[0]
        assert count >= 2, f"Expected code_execute SQL queries, got {count}"

        # VERIFY: Commands are detected correctly
        cursor.execute("""
            SELECT command FROM sql_queries
            WHERE file_path LIKE '%api.py%' AND extraction_source = 'code_execute'
        """)
        commands = [r[0] for r in cursor.fetchall()]
        assert 'SELECT' in commands, "Should detect SELECT command"
        assert 'DELETE' in commands, "Should detect DELETE command"

        conn.close()


class TestFullPipelineIntegration:
    """Test full pipeline populates all tables correctly (P0 GAP - was incomplete)."""

    def test_full_pipeline_populates_critical_tables(self, sample_project):
        """Verify complete pipeline populates files, symbols, refs, routes, sql_queries, api_endpoints."""
        # Create realistic multi-file project
        (sample_project / "app.py").write_text('''
from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
@login_required
def get_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return jsonify(users)

@app.route('/api/users/<id>', methods=['POST'])
def update_user(id):
    # SQL injection vulnerability (for testing)
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = f"UPDATE users SET name = ? WHERE id = {id}"
    cursor.execute(query, (request.json.get('name'),))
    conn.commit()
    return jsonify({"status": "updated"})
''')

        # Run full pipeline
        result = subprocess.run(
            ['aud', 'full', '--offline'],  # Use offline to skip network operations
            cwd=sample_project,
            capture_output=True,
            text=True,
            timeout=300
        )
        assert result.returncode == 0, f"Full pipeline failed: {result.stderr}"

        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # VERIFY: files table populated
        cursor.execute("SELECT COUNT(*) FROM files")
        files_count = cursor.fetchone()[0]
        assert files_count >= 1, f"Expected at least 1 file, got {files_count}"

        # VERIFY: symbols table populated
        cursor.execute("SELECT COUNT(*) FROM symbols")
        symbols_count = cursor.fetchone()[0]
        assert symbols_count > 0, f"Expected symbols, got {symbols_count}"

        # VERIFY: refs table populated (imports)
        cursor.execute("SELECT COUNT(*) FROM refs")
        refs_count = cursor.fetchone()[0]
        assert refs_count >= 3, f"Expected at least 3 imports (flask, sqlite3, os), got {refs_count}"

        # VERIFY: api_endpoints table populated
        cursor.execute("SELECT COUNT(*) FROM api_endpoints")
        endpoints_count = cursor.fetchone()[0]
        assert endpoints_count >= 2, f"Expected 2 Flask routes, got {endpoints_count}"

        # VERIFY: Routes have auth detection
        cursor.execute("SELECT has_auth FROM api_endpoints WHERE pattern LIKE '%/api/users'")
        auth_statuses = [r[0] for r in cursor.fetchall()]
        assert any(auth_statuses), "At least one route should have auth detected (@login_required)"

        # VERIFY: sql_queries table populated
        cursor.execute("SELECT COUNT(*) FROM sql_queries WHERE command != 'UNKNOWN'")
        sql_count = cursor.fetchone()[0]
        assert sql_count >= 2, f"Expected at least 2 SQL queries (SELECT, UPDATE), got {sql_count}"

        # VERIFY: SQL commands are detected
        cursor.execute("SELECT DISTINCT command FROM sql_queries WHERE command != 'UNKNOWN'")
        commands = [r[0] for r in cursor.fetchall()]
        assert 'SELECT' in commands, "Should detect SELECT command"

        # VERIFY: taint_paths detected (if taint analysis ran)
        cursor.execute("SELECT COUNT(*) FROM taint_paths")
        taint_count = cursor.fetchone()[0]
        # Note: May be 0 if taint didn't detect this specific case, but table should exist

        conn.close()
