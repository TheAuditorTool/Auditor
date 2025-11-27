"""Real-world integrity tests - no mocks, no stubs, real subprocesses.

This suite verifies the actual CLI binary works end-to-end after refactoring.
It catches issues that unit tests miss: circular imports, broken entry points,
silent extraction failures.

Tier 1: CLI loads without ModuleNotFoundError
Tier 2: Filesystem operations work (init scaffolding)
Tier 3: Full 4-layer pipeline (Parser -> Extractor -> Indexer -> Database)
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# The CLI entry point - use theauditor.cli module directly
# (aud = "theauditor.cli:main" in pyproject.toml)
AUD_CMD = [sys.executable, "-m", "theauditor.cli"]


class TestTier1CliEntry:
    """Tier 1: Verify the CLI loads and responds."""

    def test_cli_help_returns_zero(self):
        """Does the CLI load without crashing?"""
        result = subprocess.run(
            AUD_CMD + ["--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"CLI failed to load:\n{result.stderr}"
        assert "Usage:" in result.stdout, "Help output missing Usage section"

    def test_cli_version_returns_zero(self):
        """Does --version work?"""
        result = subprocess.run(
            AUD_CMD + ["--version"],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"Version check failed:\n{result.stderr}"


class TestTier2Filesystem:
    """Tier 2: Verify tool checks and module imports work."""

    def test_tool_versions_runs(self):
        """Does aud tool-versions run successfully?"""
        result = subprocess.run(
            AUD_CMD + ["tool-versions"],
            capture_output=True,
            text=True,
            timeout=60
        )

        # May have warnings but should not crash
        assert result.returncode == 0, f"tool-versions failed:\n{result.stderr}"
        # Output should mention Python version at minimum
        assert "python" in result.stdout.lower() or "Python" in result.stdout


class TestTier3Pipeline:
    """Tier 3: Verify the 4-layer extraction pipeline works.

    Tests indexer directly in Python to avoid sandbox requirements.
    This still validates: Parser -> Extractor -> Indexer -> Database
    """

    def test_indexer_extracts_symbols(self, tmp_path):
        """Does the indexer extract symbols from Python files?"""
        # Setup a minimal Python project
        project_dir = tmp_path / "indexer_test"
        project_dir.mkdir()

        # Create a valid Python file with extractable symbols
        (project_dir / "main.py").write_text(
            '''"""Smoke test module."""

def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator."""

    def multiply(self, x: int, y: int) -> int:
        return x * y
'''
        )

        # Create .pf directory for database
        pf_dir = project_dir / ".pf"
        pf_dir.mkdir()
        db_path = pf_dir / "repo_index.db"

        # Run indexer directly (expects Path objects)
        from theauditor.indexer.orchestrator import IndexerOrchestrator

        orchestrator = IndexerOrchestrator(
            root_path=project_dir,
            db_path=db_path
        )
        # Create schema before indexing
        orchestrator.db_manager.create_schema()
        orchestrator.index()

        # Verify database was created
        assert db_path.exists(), "Database not created!"

        # Verify data inside - no silent failures!
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check symbols were extracted
        cursor.execute("SELECT count(*) FROM symbols")
        symbol_count = cursor.fetchone()[0]
        assert symbol_count > 0, "Database created but symbols table empty! Extraction failed silently."

        # Check files were indexed
        cursor.execute("SELECT count(*) FROM files")
        file_count = cursor.fetchone()[0]
        assert file_count > 0, "Database created but files table empty!"

        conn.close()

    def test_indexer_extracts_specific_symbols(self, tmp_path):
        """Verify specific symbols are extracted correctly."""
        project_dir = tmp_path / "symbol_test"
        project_dir.mkdir()

        (project_dir / "app.py").write_text(
            '''def process_data(data: list) -> dict:
    """Process input data."""
    result = {}
    for item in data:
        result[item] = len(item)
    return result

class DataProcessor:
    """Process data."""
    pass
'''
        )

        pf_dir = project_dir / ".pf"
        pf_dir.mkdir()
        db_path = pf_dir / "repo_index.db"

        from theauditor.indexer.orchestrator import IndexerOrchestrator

        orchestrator = IndexerOrchestrator(
            root_path=project_dir,
            db_path=db_path
        )
        # Create schema before indexing
        orchestrator.db_manager.create_schema()
        orchestrator.index()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Verify the function was extracted
        cursor.execute("SELECT name, type FROM symbols WHERE name = 'process_data'")
        row = cursor.fetchone()
        assert row is not None, "Function 'process_data' not found in symbols!"
        assert row[1] == "function", f"Expected type 'function', got '{row[1]}'"

        # Verify the class was extracted
        cursor.execute("SELECT name, type FROM symbols WHERE name = 'DataProcessor'")
        row = cursor.fetchone()
        assert row is not None, "Class 'DataProcessor' not found in symbols!"
        assert row[1] == "class", f"Expected type 'class', got '{row[1]}'"

        conn.close()
