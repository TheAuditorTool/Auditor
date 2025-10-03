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
def sample_project():
    """Create minimal test project structure."""
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
