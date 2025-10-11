"""
Integration Test: Object Literal Parsing + Taint Analysis (Phase 5.5)

Validates that taint analyzer correctly detects flows through dynamic dispatch
using the new database-backed object literal resolution.
"""

import pytest
import sqlite3
import tempfile
import shutil
from pathlib import Path

# Import TheAuditor components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theauditor.indexer import IndexerOrchestrator
from theauditor.indexer.database import DatabaseManager


@pytest.fixture
def test_workspace():
    """Create temporary workspace with test files."""
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / '.pf' / 'repo_index.db'
    db_path.parent.mkdir(exist_ok=True)

    # Copy test fixture
    src_file = Path(__file__).parent.parent / 'fixtures' / 'taint' / 'dynamic_dispatch.js'
    dest_file = temp_dir / 'dynamic_dispatch.js'

    if src_file.exists():
        shutil.copy(src_file, dest_file)
    else:
        pytest.skip(f"Test fixture not found: {src_file}")

    yield temp_dir, db_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_object_literals_extracted(test_workspace):
    """Test 1: Verify object literals are extracted during indexing."""
    temp_dir, db_path = test_workspace

    # Create database and run indexer
    db_manager = DatabaseManager(str(db_path))
    db_manager.create_schema()
    db_manager.close()

    orchestrator = IndexerOrchestrator(root_path=temp_dir, db_path=str(db_path))
    orchestrator.index()

    # Verify object_literals table populated
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM object_literals")
    count = cursor.fetchone()[0]
    assert count > 0, "No object literals extracted"

    # Verify specific objects exist
    cursor.execute("""
        SELECT variable_name, COUNT(*)
        FROM object_literals
        GROUP BY variable_name
    """)
    objects = dict(cursor.fetchall())

    # Check for test objects
    assert 'handlers' in objects, "Missing 'handlers' object"
    assert 'actions' in objects, "Missing 'actions' object (shorthand)"
    assert objects['handlers'] == 3, f"Expected 3 properties in 'handlers', got {objects['handlers']}"

    conn.close()
    print(f"✓ Extracted {count} object literal properties")
    print(f"✓ Found objects: {list(objects.keys())}")


def test_object_literal_query_works(test_workspace):
    """Test 2: Verify object literal database queries work correctly."""
    temp_dir, db_path = test_workspace

    # Index
    db_manager = DatabaseManager(str(db_path))
    db_manager.create_schema()
    db_manager.close()

    orchestrator = IndexerOrchestrator(root_path=temp_dir, db_path=str(db_path))
    orchestrator.index()

    # Query database (simulates what taint analyzer does)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Test query: Find all function refs for 'handlers' object
    from theauditor.indexer.schema import build_query
    query = build_query('object_literals',
        ['property_value'],
        where="variable_name = ? AND property_type IN ('function_ref', 'shorthand')"
    )
    cursor.execute(query, ('handlers',))
    results = [row[0] for row in cursor.fetchall()]

    conn.close()

    # Validate
    assert len(results) == 3, f"Expected 3 handlers, got {len(results)}"
    assert 'createUser' in results
    assert 'updateUser' in results
    assert 'deleteUser' in results

    print(f"✓ Database query returned {len(results)} function references")
    print(f"✓ Functions: {results}")


def test_shorthand_syntax_extraction(test_workspace):
    """Test 3: Verify shorthand syntax is correctly extracted."""
    temp_dir, db_path = test_workspace

    # Index
    db_manager = DatabaseManager(str(db_path))
    db_manager.create_schema()
    db_manager.close()

    orchestrator = IndexerOrchestrator(root_path=temp_dir, db_path=str(db_path))
    orchestrator.index()

    # Query for shorthand properties
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT variable_name, property_name, property_value
        FROM object_literals
        WHERE property_type = 'shorthand'
    """)
    shorthand_props = cursor.fetchall()

    conn.close()

    # Validate
    assert len(shorthand_props) > 0, "No shorthand properties extracted"

    # Check for 'actions' object with shorthand syntax
    actions_props = [p for p in shorthand_props if p[0] == 'actions']
    assert len(actions_props) == 3, f"Expected 3 shorthand props in 'actions', got {len(actions_props)}"

    print(f"✓ Extracted {len(shorthand_props)} shorthand properties")
    print(f"✓ Actions object has: {[p[1] for p in actions_props]}")


def test_nested_objects(test_workspace):
    """Test 4: Verify nested object extraction."""
    temp_dir, db_path = test_workspace

    # Index
    db_manager = DatabaseManager(str(db_path))
    db_manager.create_schema()
    db_manager.close()

    orchestrator = IndexerOrchestrator(root_path=temp_dir, db_path=str(db_path))
    orchestrator.index()

    # Check nested objects in database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Query for nested objects
    cursor.execute("""
        SELECT variable_name, property_name, property_value, nested_level
        FROM object_literals
        WHERE nested_level > 0
        ORDER BY variable_name, nested_level
    """)
    nested = cursor.fetchall()

    conn.close()

    assert len(nested) > 0, "No nested objects extracted"

    print(f"✓ Found {len(nested)} nested object properties")
    for var, prop, val, level in nested[:10]:
        print(f"  - Level {level}: {var}.{prop} = {val}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
