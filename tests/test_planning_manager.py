"""Unit tests for PlanningManager database operations."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, UTC

from theauditor.planning.manager import PlanningManager


@pytest.fixture
def temp_db():
    """Create a temporary planning database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    # Initialize database
    manager = PlanningManager.init_database(db_path)

    yield manager, db_path

    # Cleanup
    manager.conn.close()
    db_path.unlink()


def test_create_schema(temp_db):
    """Test planning.db schema creation."""
    manager, db_path = temp_db

    # Check all 5 tables exist
    cursor = manager.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    expected_tables = ['code_diffs', 'code_snapshots', 'plan_specs', 'plan_tasks', 'plans']
    assert tables == expected_tables, f"Expected {expected_tables}, got {tables}"

    # Check plans table has correct columns
    cursor.execute("PRAGMA table_info(plans)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}  # name: type

    assert 'id' in columns
    assert 'name' in columns
    assert 'status' in columns
    assert 'created_at' in columns


def test_create_plan(temp_db):
    """Test plan creation returns valid plan_id."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan", "Test description", {"key": "value"})

    assert isinstance(plan_id, int)
    assert plan_id > 0

    # Verify plan exists in database
    plan = manager.get_plan(plan_id)
    assert plan is not None
    assert plan['name'] == "Test Plan"
    assert plan['description'] == "Test description"
    assert plan['status'] == 'active'
    assert 'created_at' in plan


def test_add_task_auto_increment(temp_db):
    """Test task_number auto-increments correctly."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan")

    # Add first task
    task_id_1 = manager.add_task(plan_id, "Task 1")
    task_number_1 = manager.get_task_number(task_id_1)
    assert task_number_1 == 1

    # Add second task
    task_id_2 = manager.add_task(plan_id, "Task 2")
    task_number_2 = manager.get_task_number(task_id_2)
    assert task_number_2 == 2

    # Add third task
    task_id_3 = manager.add_task(plan_id, "Task 3", description="Third task")
    task_number_3 = manager.get_task_number(task_id_3)
    assert task_number_3 == 3

    # Verify all tasks belong to same plan
    tasks = manager.list_tasks(plan_id)
    assert len(tasks) == 3
    assert tasks[0]['task_number'] == 1
    assert tasks[1]['task_number'] == 2
    assert tasks[2]['task_number'] == 3


def test_add_task_with_spec(temp_db):
    """Test task with YAML spec."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan")
    spec_yaml = """
refactor_name: Test Spec
description: Test verification
rules:
  - id: test-rule
    match:
      identifiers: [oldFunction]
    expect:
      identifiers: [newFunction]
"""

    task_id = manager.add_task(plan_id, "Task with spec", spec_yaml=spec_yaml)

    # Verify spec was stored
    loaded_spec = manager.load_task_spec(task_id)
    assert loaded_spec is not None
    assert 'refactor_name: Test Spec' in loaded_spec
    assert 'oldFunction' in loaded_spec
    assert 'newFunction' in loaded_spec


def test_load_task_spec(temp_db):
    """Test loading spec YAML from task."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan")

    # Task without spec
    task_id_no_spec = manager.add_task(plan_id, "Task without spec")
    spec_none = manager.load_task_spec(task_id_no_spec)
    assert spec_none is None

    # Task with spec
    spec_yaml = "refactor_name: My Spec"
    task_id_with_spec = manager.add_task(plan_id, "Task with spec", spec_yaml=spec_yaml)
    spec_loaded = manager.load_task_spec(task_id_with_spec)
    assert spec_loaded == spec_yaml


def test_update_task_status(temp_db):
    """Test updating task status."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan")
    task_id = manager.add_task(plan_id, "Test Task")

    # Initial status should be pending
    cursor = manager.conn.cursor()
    cursor.execute("SELECT status FROM plan_tasks WHERE id = ?", (task_id,))
    initial_status = cursor.fetchone()[0]
    assert initial_status == 'pending'

    # Update to in_progress
    manager.update_task_status(task_id, 'in_progress')
    cursor.execute("SELECT status FROM plan_tasks WHERE id = ?", (task_id,))
    new_status = cursor.fetchone()[0]
    assert new_status == 'in_progress'

    # Update to completed with timestamp
    completed_at = datetime.now(UTC).isoformat()
    manager.update_task_status(task_id, 'completed', completed_at)
    cursor.execute("SELECT status, completed_at FROM plan_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    assert row[0] == 'completed'
    assert row[1] == completed_at


def test_list_tasks_filter_by_status(temp_db):
    """Test filtering tasks by status."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan")

    # Create tasks with different statuses
    task_id_1 = manager.add_task(plan_id, "Pending Task")
    task_id_2 = manager.add_task(plan_id, "In Progress Task")
    task_id_3 = manager.add_task(plan_id, "Completed Task")
    task_id_4 = manager.add_task(plan_id, "Another Pending")

    manager.update_task_status(task_id_2, 'in_progress')
    manager.update_task_status(task_id_3, 'completed')

    # Get all tasks
    all_tasks = manager.list_tasks(plan_id)
    assert len(all_tasks) == 4

    # Filter by status
    pending_tasks = manager.list_tasks(plan_id, status_filter='pending')
    assert len(pending_tasks) == 2
    assert all(t['status'] == 'pending' for t in pending_tasks)

    in_progress_tasks = manager.list_tasks(plan_id, status_filter='in_progress')
    assert len(in_progress_tasks) == 1
    assert in_progress_tasks[0]['title'] == "In Progress Task"

    completed_tasks = manager.list_tasks(plan_id, status_filter='completed')
    assert len(completed_tasks) == 1
    assert completed_tasks[0]['title'] == "Completed Task"


def test_missing_planning_db_error(tmpdir):
    """Test error when planning.db missing."""
    # Create a path that doesn't exist
    non_existent_path = Path(tmpdir) / "nonexistent.db"

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError) as exc_info:
        PlanningManager(non_existent_path)

    assert "Planning database not found" in str(exc_info.value)
    assert "Run 'aud planning init' first" in str(exc_info.value)


def test_bidirectional_task_id_lookup(temp_db):
    """Test bidirectional lookup between task_id and task_number."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan")

    # Add tasks
    task_id_1 = manager.add_task(plan_id, "Task 1")
    task_id_2 = manager.add_task(plan_id, "Task 2")
    task_id_3 = manager.add_task(plan_id, "Task 3")

    # Forward lookup: task_id -> task_number
    assert manager.get_task_number(task_id_1) == 1
    assert manager.get_task_number(task_id_2) == 2
    assert manager.get_task_number(task_id_3) == 3

    # Reverse lookup: plan_id + task_number -> task_id
    assert manager.get_task_id(plan_id, 1) == task_id_1
    assert manager.get_task_id(plan_id, 2) == task_id_2
    assert manager.get_task_id(plan_id, 3) == task_id_3

    # Non-existent task
    assert manager.get_task_id(plan_id, 99) is None
    assert manager.get_task_number(99999) is None


def test_update_task_assignee(temp_db):
    """Test updating task assignee."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan")
    task_id = manager.add_task(plan_id, "Test Task")

    # Initial assignee should be None
    cursor = manager.conn.cursor()
    cursor.execute("SELECT assigned_to FROM plan_tasks WHERE id = ?", (task_id,))
    initial_assignee = cursor.fetchone()[0]
    assert initial_assignee is None

    # Assign to Alice
    manager.update_task_assignee(task_id, "Alice")
    cursor.execute("SELECT assigned_to FROM plan_tasks WHERE id = ?", (task_id,))
    new_assignee = cursor.fetchone()[0]
    assert new_assignee == "Alice"

    # Reassign to Bob
    manager.update_task_assignee(task_id, "Bob")
    cursor.execute("SELECT assigned_to FROM plan_tasks WHERE id = ?", (task_id,))
    final_assignee = cursor.fetchone()[0]
    assert final_assignee == "Bob"


def test_update_plan_status(temp_db):
    """Test updating plan status and metadata."""
    manager, _ = temp_db

    plan_id = manager.create_plan("Test Plan", metadata={"initial": "data"})

    # Update status to archived with new metadata
    import json
    new_metadata = {"archived_at": "2025-10-30", "notes": "Test archive"}
    manager.update_plan_status(plan_id, 'archived', json.dumps(new_metadata))

    # Verify update
    plan = manager.get_plan(plan_id)
    assert plan['status'] == 'archived'

    metadata = json.loads(plan['metadata_json'])
    assert metadata['archived_at'] == "2025-10-30"
    assert metadata['notes'] == "Test archive"
