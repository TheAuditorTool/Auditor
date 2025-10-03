"""End-to-end tests for taint analysis."""
import pytest
import subprocess
import sqlite3
from pathlib import Path

class TestTaintAnalysisE2E:
    """End-to-end taint analysis tests."""

    def test_taint_finds_vulnerabilities_in_sample(self, sample_project):
        """Test taint analysis finds XSS in sample code."""
        # Create vulnerable code
        (sample_project / "vulnerable.py").write_text("""
from flask import Flask, request

app = Flask(__name__)

@app.route('/user')
def get_user():
    user_input = request.args.get('name')
    # XSS vulnerability - no sanitization
    return f"<h1>Hello {user_input}</h1>"
""")

        # Run indexer
        result = subprocess.run(
            ['aud', 'index'],
            cwd=sample_project,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Indexer should succeed"

        # Run taint analysis
        result = subprocess.run(
            ['aud', 'taint-analyze'],
            cwd=sample_project,
            capture_output=True,
            text=True
        )

        # Check for taint paths
        db_path = sample_project / '.pf' / 'repo_index.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM taint_paths")
        count = cursor.fetchone()[0]

        assert count > 0, "Should detect at least one taint path (request.args -> response)"

    def test_memory_cache_loads_without_errors(self, sample_project):
        """Verify memory cache initialization doesn't crash."""
        # Create minimal project
        (sample_project / "main.py").write_text("print('hello')")

        # Run with cache enabled
        result = subprocess.run(
            ['aud', 'taint-analyze'],
            cwd=sample_project,
            capture_output=True,
            text=True
        )

        # Should not see schema errors in output
        assert 'no such column' not in result.stderr.lower()
        assert 'OperationalError' not in result.stderr

    def test_no_schema_mismatch_errors_in_logs(self, sample_project):
        """Verify no schema mismatch errors during analysis."""
        (sample_project / "app.py").write_text("""
def process(data):
    return data.upper()
""")

        result = subprocess.run(
            ['aud', 'full'],
            cwd=sample_project,
            capture_output=True,
            text=True
        )

        # Check for known schema error patterns
        error_patterns = [
            'no such column: var_name',
            'no such column: context',
            'no such column: line',  # Fixed in PHASE 1
        ]

        for pattern in error_patterns:
            assert pattern not in result.stderr.lower(), f"Found schema error: {pattern}"
