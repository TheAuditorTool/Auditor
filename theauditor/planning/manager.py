"""Planning database manager.

This module manages planning.db operations following DatabaseManager pattern.

ARCHITECTURE: Separate planning.db from repo_index.db
- planning.db stores plans, tasks, specs, and code snapshots
- repo_index.db remains unchanged (used for verification)
- NO FALLBACKS. Hard failure if planning.db malformed or missing.
"""
from __future__ import annotations


from pathlib import Path
import sqlite3
import json
from typing import Dict, List, Optional
from datetime import datetime, UTC

from theauditor.indexer.schema import TABLES


class PlanningManager:
    """Manages planning database operations.

    Follows DatabaseManager pattern from theauditor/indexer/database.py
    but operates on planning.db instead of repo_index.db.

    NO FALLBACKS. Hard failure if planning.db is malformed or missing.
    """

    def __init__(self, db_path: Path):
        """Initialize planning database connection.

        Args:
            db_path: Path to planning.db (typically .pf/planning.db)

        Raises:
            FileNotFoundError: If planning.db doesn't exist (must init first)
        """
        if not db_path.exists():
            raise FileNotFoundError(
                f"Planning database not found: {db_path}\n"
                "Run 'aud planning init' first."
            )

        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access

    @classmethod
    def init_database(cls, db_path: Path) -> PlanningManager:
        """Create planning.db if it doesn't exist and initialize schema.

        Args:
            db_path: Path to planning.db

        Returns:
            PlanningManager instance
        """
        # Create database file if missing
        conn = sqlite3.connect(str(db_path))
        conn.close()

        # Create manager instance (now file exists)
        manager = cls.__new__(cls)
        manager.db_path = db_path
        manager.conn = sqlite3.connect(str(db_path))
        manager.conn.row_factory = sqlite3.Row
        manager.create_schema()
        return manager

    def create_schema(self):
        """Create planning tables using schema.py definitions.

        Creates: plans, plan_tasks, plan_specs, code_snapshots, code_diffs, plan_phases, plan_jobs
        """
        cursor = self.conn.cursor()

        planning_tables = ["plans", "plan_tasks", "plan_specs", "code_snapshots", "code_diffs", "plan_phases", "plan_jobs"]

        for table_name in planning_tables:
            if table_name not in TABLES:
                raise ValueError(f"Planning table '{table_name}' not found in schema.py")

            schema = TABLES[table_name]

            # Create table
            create_sql = schema.create_table_sql()
            cursor.execute(create_sql)

            # Create indexes
            for index_sql in schema.create_indexes_sql():
                cursor.execute(index_sql)

        self.conn.commit()

    def create_plan(self, name: str, description: str = "", metadata: dict = None) -> int:
        """Create new plan and return plan ID.

        Args:
            name: Plan name (required)
            description: Plan description
            metadata: Optional metadata dict (stored as JSON)

        Returns:
            plan_id: ID of created plan

        NO FALLBACKS. Raises sqlite3.IntegrityError if name is duplicate.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plans (name, description, created_at, status, metadata_json)
               VALUES (?, ?, ?, 'active', ?)""",
            (name, description, datetime.now(UTC).isoformat(),
             json.dumps(metadata) if metadata else "{}")
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_task(self, plan_id: int, title: str, description: str = "",
                 spec_yaml: str = None, assigned_to: str = None) -> int:
        """Add task to plan and return task ID.

        Args:
            plan_id: ID of plan to add task to
            title: Task title (required)
            description: Task description
            spec_yaml: Optional YAML spec for verification
            assigned_to: Optional assignee

        Returns:
            task_id: ID of created task

        NO FALLBACKS. Raises sqlite3.IntegrityError if plan_id invalid.
        """
        cursor = self.conn.cursor()

        # Get next task number for this plan
        cursor.execute(
            "SELECT MAX(task_number) FROM plan_tasks WHERE plan_id = ?",
            (plan_id,)
        )
        max_task_num = cursor.fetchone()[0]
        task_number = (max_task_num or 0) + 1

        # Insert spec if provided
        spec_id = None
        if spec_yaml:
            spec_id = self._insert_spec(plan_id, spec_yaml)

        # Insert task
        cursor.execute(
            """INSERT INTO plan_tasks
               (plan_id, task_number, title, description, status, assigned_to, spec_id, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (plan_id, task_number, title, description, assigned_to, spec_id,
             datetime.now(UTC).isoformat())
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_task_status(self, task_id: int, status: str, completed_at: str = None):
        """Update task status.

        Args:
            task_id: ID of task to update
            status: New status (pending|in_progress|completed|failed)
            completed_at: Optional completion timestamp

        NO FALLBACKS. Raises sqlite3.IntegrityError if task_id invalid.
        """
        cursor = self.conn.cursor()

        if completed_at is None and status == "completed":
            completed_at = datetime.now(UTC).isoformat()

        cursor.execute(
            "UPDATE plan_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id)
        )
        self.conn.commit()

    def load_task_spec(self, task_id: int) -> str | None:
        """Load verification spec YAML for task.

        Args:
            task_id: ID of task

        Returns:
            spec_yaml: YAML text or None if no spec

        NO FALLBACKS. Returns None if task has no spec (not an error).
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT ps.spec_yaml
               FROM plan_tasks pt
               JOIN plan_specs ps ON pt.spec_id = ps.id
               WHERE pt.id = ?""",
            (task_id,)
        )
        row = cursor.fetchone()
        return row['spec_yaml'] if row else None

    def get_plan(self, plan_id: int) -> dict | None:
        """Get plan by ID.

        Args:
            plan_id: ID of plan

        Returns:
            dict with plan details or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_tasks(self, plan_id: int, status_filter: str = None) -> list[dict]:
        """List tasks for a plan.

        Args:
            plan_id: ID of plan
            status_filter: Optional status filter (pending|in_progress|completed|failed)

        Returns:
            List of task dicts
        """
        cursor = self.conn.cursor()

        if status_filter:
            cursor.execute(
                "SELECT * FROM plan_tasks WHERE plan_id = ? AND status = ? ORDER BY task_number",
                (plan_id, status_filter)
            )
        else:
            cursor.execute(
                "SELECT * FROM plan_tasks WHERE plan_id = ? ORDER BY task_number",
                (plan_id,)
            )

        return [dict(row) for row in cursor.fetchall()]

    def create_snapshot(self, plan_id: int, checkpoint_name: str, task_id: int = None,
                       git_ref: str = None, files_json: str = None) -> int:
        """Create code snapshot for plan/task.

        Args:
            plan_id: ID of plan
            checkpoint_name: Name of checkpoint
            task_id: Optional task ID
            git_ref: Git commit SHA or branch name
            files_json: JSON list of affected files

        Returns:
            snapshot_id: ID of created snapshot
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO code_snapshots
               (plan_id, task_id, checkpoint_name, timestamp, git_ref, files_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (plan_id, task_id, checkpoint_name, datetime.now(UTC).isoformat(),
             git_ref, files_json or "[]")
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_diff(self, snapshot_id: int, file_path: str, diff_text: str,
                 added_lines: int, removed_lines: int) -> int:
        """Add diff to snapshot.

        Args:
            snapshot_id: ID of snapshot
            file_path: Path of changed file
            diff_text: Full unified diff text
            added_lines: Number of added lines
            removed_lines: Number of removed lines

        Returns:
            diff_id: ID of created diff
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO code_diffs
               (snapshot_id, file_path, diff_text, added_lines, removed_lines)
               VALUES (?, ?, ?, ?, ?)""",
            (snapshot_id, file_path, diff_text, added_lines, removed_lines)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_snapshot(self, snapshot_id: int) -> dict | None:
        """Get snapshot by ID with associated diffs.

        Args:
            snapshot_id: ID of snapshot

        Returns:
            dict with snapshot details and diffs list
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM code_snapshots WHERE id = ?", (snapshot_id,))
        snapshot = cursor.fetchone()

        if not snapshot:
            return None

        cursor.execute("SELECT * FROM code_diffs WHERE snapshot_id = ?", (snapshot_id,))
        diffs = [dict(row) for row in cursor.fetchall()]

        result = dict(snapshot)
        result['diffs'] = diffs
        return result

    def archive_plan(self, plan_id: int):
        """Archive plan (mark as archived).

        Args:
            plan_id: ID of plan to archive
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE plans SET status = 'archived' WHERE id = ?",
            (plan_id,)
        )
        self.conn.commit()

    def get_task_number(self, task_id: int) -> int | None:
        """Get task_number from task_id.

        Args:
            task_id: ID of task

        Returns:
            task_number or None if task not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT task_number FROM plan_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return row['task_number'] if row else None

    def get_task_id(self, plan_id: int, task_number: int) -> int | None:
        """Get task_id from plan_id and task_number.

        Args:
            plan_id: ID of plan
            task_number: Task number within plan

        Returns:
            task_id or None if task not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM plan_tasks WHERE plan_id = ? AND task_number = ?",
            (plan_id, task_number)
        )
        row = cursor.fetchone()
        return row['id'] if row else None

    def update_task_assignee(self, task_id: int, assigned_to: str):
        """Update task assignee.

        Args:
            task_id: ID of task to update
            assigned_to: New assignee name
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE plan_tasks SET assigned_to = ? WHERE id = ?",
            (assigned_to, task_id)
        )
        self.conn.commit()

    def update_plan_status(self, plan_id: int, status: str, metadata_json: str = None):
        """Update plan status and metadata.

        Args:
            plan_id: ID of plan to update
            status: New status (active|archived|cancelled)
            metadata_json: Optional metadata JSON string
        """
        cursor = self.conn.cursor()
        if metadata_json:
            cursor.execute(
                "UPDATE plans SET status = ?, metadata_json = ? WHERE id = ?",
                (status, metadata_json, plan_id)
            )
        else:
            cursor.execute(
                "UPDATE plans SET status = ? WHERE id = ?",
                (status, plan_id)
            )
        self.conn.commit()

    def _insert_spec(self, plan_id: int, spec_yaml: str, spec_type: str = None) -> int:
        """Insert spec and return spec ID (internal helper).

        Args:
            plan_id: ID of plan
            spec_yaml: YAML specification text
            spec_type: Optional spec type (e.g., "api_migration")

        Returns:
            spec_id: ID of created spec
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plan_specs (plan_id, spec_yaml, spec_type, created_at)
               VALUES (?, ?, ?, ?)""",
            (plan_id, spec_yaml, spec_type, datetime.now(UTC).isoformat())
        )
        return cursor.lastrowid

    def add_plan_phase(self, plan_id: int, phase_number: int, title: str,
                      description: str = None, success_criteria: str = None,
                      status: str = 'pending', created_at: str = ''):
        """Add a phase to a plan (hierarchical planning structure).

        Args:
            plan_id: ID of plan
            phase_number: Phase number within plan
            title: Phase title (required)
            description: Phase description
            success_criteria: What completion looks like for this phase (criteria)
            status: Phase status (pending|in_progress|completed)
            created_at: Creation timestamp (auto-generated if empty)

        NO FALLBACKS. Raises sqlite3.IntegrityError if duplicate phase_number.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plan_phases
               (plan_id, phase_number, title, description, success_criteria, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, phase_number, title, description, success_criteria, status,
             created_at if created_at else datetime.now(UTC).isoformat())
        )
        # Note: commit() must be called separately by caller

    def add_plan_job(self, task_id: int, job_number: int, description: str,
                    completed: int = 0, is_audit_job: int = 0, created_at: str = ''):
        """Add a job (checkbox item) to a task (hierarchical task breakdown).

        Args:
            task_id: ID of task
            job_number: Job number within task
            description: Job description (checkbox text)
            completed: Job completion status (0 or 1, SQLite BOOLEAN)
            is_audit_job: Flag for audit jobs (0 or 1, SQLite BOOLEAN)
            created_at: Creation timestamp (auto-generated if empty)

        NO FALLBACKS. Raises sqlite3.IntegrityError if duplicate job_number.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plan_jobs
               (task_id, job_number, description, completed, is_audit_job, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_id, job_number, description, completed, is_audit_job,
             created_at if created_at else datetime.now(UTC).isoformat())
        )
        # Note: commit() must be called separately by caller

    def commit(self):
        """Commit pending transactions."""
        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()
