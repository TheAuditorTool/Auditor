"""Pytest configuration and fixtures."""
import pytest
import sqlite3
import tempfile
from pathlib import Path

@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    yield conn

    conn.close()
    Path(db_path).unlink()

@pytest.fixture
def golden_db():
    """
    Golden snapshot database from 5 production runs.

    This is a known-good database state created by running:
      aud full --offline on 5 diverse projects

    Tests use this snapshot to avoid dogfooding (testing TheAuditor by running TheAuditor).

    Benefits:
    - Fast: No subprocess, no indexing, just SQLite queries
    - Deterministic: Same data every run
    - No circular logic: Tests don't depend on TheAuditor working

    If this fixture fails, run: python scripts/create_golden_snapshot.py
    """
    db_path = Path(__file__).parent.parent / "repo_index.db"

    if not db_path.exists():
        pytest.skip(
            f"Golden snapshot not found at {db_path}\n"
            "Run: python scripts/create_golden_snapshot.py\n"
            "This combines databases from 5 production runs into a test snapshot."
        )

    return db_path

@pytest.fixture
def golden_conn(golden_db):
    """
    Open connection to golden snapshot database.

    Automatically closes connection after test.
    Read-only to prevent accidental modification of golden snapshot.
    """
    conn = sqlite3.connect(f"file:{golden_db}?mode=ro", uri=True)
    yield conn
    conn.close()

@pytest.fixture
def sample_project():
    """Create minimal test project structure for dogfooding tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create sample Python file
        (project_path / "app.py").write_text("""
import os
from pathlib import Path

def get_user(user_id):
    return {"id": user_id}
""")

        yield project_path
