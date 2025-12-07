"""Planning database manager."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from theauditor.indexer.schema import TABLES

from .shadow_git import ShadowRepoManager


class PlanningManager:
    """Manages planning database operations."""

    def __init__(self, db_path: Path):
        """Initialize planning database connection."""
        if not db_path.is_absolute():
            raise ValueError(f"db_path must be absolute, got: {db_path}")

        if not db_path.exists():
            raise FileNotFoundError(
                f"Planning database not found: {db_path}\nRun 'aud planning init' first."
            )

        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._validate_schema_integrity()

    @classmethod
    def init_database(cls, db_path: Path) -> PlanningManager:
        """Create planning.db if it doesn't exist and initialize schema."""

        conn = sqlite3.connect(str(db_path))
        conn.close()

        manager = cls.__new__(cls)
        manager.db_path = db_path
        manager.conn = sqlite3.connect(str(db_path))
        manager.conn.row_factory = sqlite3.Row
        manager.create_schema()

        ShadowRepoManager(db_path.parent)

        return manager

    def create_schema(self):
        """Create planning tables using schema.py definitions."""
        cursor = self.conn.cursor()

        planning_tables = [
            "plans",
            "plan_tasks",
            "plan_specs",
            "code_snapshots",
            "code_diffs",
            "plan_phases",
            "plan_jobs",
        ]

        for table_name in planning_tables:
            if table_name not in TABLES:
                raise ValueError(f"Planning table '{table_name}' not found in schema.py")

            schema = TABLES[table_name]

            create_sql = schema.create_table_sql()
            cursor.execute(create_sql)

            for index_sql in schema.create_indexes_sql():
                cursor.execute(index_sql)

        self.conn.commit()

    def _validate_schema_integrity(self):
        """Validate DB schema exists. Hard fail if corrupt or unmigrated.

        ZERO FALLBACK: Do not attempt to fix schema at runtime.
        If this fails, the DB is corrupt or needs migration.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT shadow_sha FROM code_snapshots LIMIT 1")
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                "Planning DB schema mismatch! Column 'shadow_sha' missing in code_snapshots. "
                "Delete .pf/planning/planning.db and run 'aud planning init' to recreate."
            ) from e

    def create_plan(self, name: str, description: str = "", metadata: dict = None) -> int:
        """Create new plan and return plan ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plans (name, description, created_at, status, metadata_json)
               VALUES (?, ?, ?, 'active', ?)""",
            (
                name,
                description,
                datetime.now(UTC).isoformat(),
                json.dumps(metadata) if metadata else "{}",
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_task(
        self,
        plan_id: int,
        title: str,
        description: str = "",
        spec_yaml: str = None,
        assigned_to: str = None,
    ) -> int:
        """Add task to plan and return task ID."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT MAX(task_number) FROM plan_tasks WHERE plan_id = ?", (plan_id,))
        max_task_num = cursor.fetchone()[0]
        task_number = (max_task_num or 0) + 1

        spec_id = None
        if spec_yaml:
            spec_id = self._insert_spec(plan_id, spec_yaml)

        cursor.execute(
            """INSERT INTO plan_tasks
               (plan_id, task_number, title, description, status, assigned_to, spec_id, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (
                plan_id,
                task_number,
                title,
                description,
                assigned_to,
                spec_id,
                datetime.now(UTC).isoformat(),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_task_status(self, task_id: int, status: str, completed_at: str = None):
        """Update task status."""
        cursor = self.conn.cursor()

        if completed_at is None and status == "completed":
            completed_at = datetime.now(UTC).isoformat()

        cursor.execute(
            "UPDATE plan_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id),
        )
        self.conn.commit()

    def load_task_spec(self, task_id: int) -> str | None:
        """Load verification spec YAML for task."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT ps.spec_yaml
               FROM plan_tasks pt
               JOIN plan_specs ps ON pt.spec_id = ps.id
               WHERE pt.id = ?""",
            (task_id,),
        )
        row = cursor.fetchone()
        return row["spec_yaml"] if row else None

    def get_plan(self, plan_id: int) -> dict | None:
        """Get plan by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_tasks(self, plan_id: int, status_filter: str = None) -> list[dict]:
        """List tasks for a plan."""
        cursor = self.conn.cursor()

        if status_filter:
            cursor.execute(
                "SELECT * FROM plan_tasks WHERE plan_id = ? AND status = ? ORDER BY task_number",
                (plan_id, status_filter),
            )
        else:
            cursor.execute(
                "SELECT * FROM plan_tasks WHERE plan_id = ? ORDER BY task_number", (plan_id,)
            )

        return [dict(row) for row in cursor.fetchall()]

    def create_snapshot(
        self,
        plan_id: int,
        checkpoint_name: str,
        project_root: Path,
        files_affected: list[str] | None = None,
        task_id: int | None = None,
    ) -> dict:
        """Create code snapshot using shadow git repository.

        Args:
            plan_id: Plan ID to associate snapshot with
            checkpoint_name: Human-readable checkpoint name
            project_root: Path to the project root
            files_affected: List of files to snapshot. If None, auto-detects dirty files.
            task_id: Optional task ID to associate snapshot with

        Returns:
            dict with: snapshot_id, shadow_sha, checkpoint_name, timestamp, files_affected, sequence
        """
        shadow = ShadowRepoManager(self.db_path.parent)

        if files_affected is None:
            files_affected = shadow.detect_dirty_files(project_root)

        shadow_sha = shadow.create_snapshot(
            project_root,
            files_affected,
            f"Snapshot: {checkpoint_name}",
        )

        cursor = self.conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        sequence = None
        if task_id is not None:
            cursor.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM code_snapshots WHERE task_id = ?",
                (task_id,),
            )
            sequence = cursor.fetchone()[0]

        timestamp = datetime.now(UTC).isoformat()
        files_json = json.dumps(files_affected)

        cursor.execute(
            """INSERT INTO code_snapshots
               (plan_id, task_id, sequence, checkpoint_name, timestamp, shadow_sha, files_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, task_id, sequence, checkpoint_name, timestamp, shadow_sha, files_json),
        )

        snapshot_id = cursor.lastrowid
        self.conn.commit()

        return {
            "snapshot_id": snapshot_id,
            "shadow_sha": shadow_sha,
            "checkpoint_name": checkpoint_name,
            "timestamp": timestamp,
            "files_affected": files_affected,
            "sequence": sequence,
        }

    def add_diff(
        self, snapshot_id: int, file_path: str, diff_text: str, added_lines: int, removed_lines: int
    ) -> int:
        """Add diff to snapshot."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO code_diffs
               (snapshot_id, file_path, diff_text, added_lines, removed_lines)
               VALUES (?, ?, ?, ?, ?)""",
            (snapshot_id, file_path, diff_text, added_lines, removed_lines),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_snapshot(self, snapshot_id: int) -> dict | None:
        """Get snapshot by ID with associated diffs."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM code_snapshots WHERE id = ?", (snapshot_id,))
        snapshot = cursor.fetchone()

        if not snapshot:
            return None

        result = dict(snapshot)

        shadow_sha = result.get("shadow_sha")
        if shadow_sha:
            result["diff_text"] = self.get_snapshot_diff(snapshot_id)
            result["diffs"] = []
        else:
            cursor.execute("SELECT * FROM code_diffs WHERE snapshot_id = ?", (snapshot_id,))
            result["diffs"] = [dict(row) for row in cursor.fetchall()]

        return result

    def get_snapshot_diff(self, snapshot_id: int) -> str:
        """Get unified diff for a snapshot from shadow git repo."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT shadow_sha, task_id, sequence FROM code_snapshots WHERE id = ?",
            (snapshot_id,),
        )
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        shadow_sha = row["shadow_sha"]
        if not shadow_sha:
            raise ValueError(f"Snapshot {snapshot_id} has no shadow_sha (legacy snapshot)")

        task_id = row["task_id"]
        sequence = row["sequence"]
        old_sha = None

        if task_id and sequence and sequence > 1:
            cursor.execute(
                """SELECT shadow_sha FROM code_snapshots
                   WHERE task_id = ? AND sequence = ?""",
                (task_id, sequence - 1),
            )
            prev_row = cursor.fetchone()
            if prev_row:
                old_sha = prev_row["shadow_sha"]

        shadow = ShadowRepoManager(self.db_path.parent)
        return shadow.get_diff(old_sha, shadow_sha)

    def archive_plan(self, plan_id: int):
        """Archive plan (mark as archived)."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE plans SET status = 'archived' WHERE id = ?", (plan_id,))
        self.conn.commit()

    def get_task_number(self, task_id: int) -> int | None:
        """Get task_number from task_id."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT task_number FROM plan_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return row["task_number"] if row else None

    def get_task_id(self, plan_id: int, task_number: int) -> int | None:
        """Get task_id from plan_id and task_number."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM plan_tasks WHERE plan_id = ? AND task_number = ?",
            (plan_id, task_number),
        )
        row = cursor.fetchone()
        return row["id"] if row else None

    def update_task_assignee(self, task_id: int, assigned_to: str):
        """Update task assignee."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE plan_tasks SET assigned_to = ? WHERE id = ?", (assigned_to, task_id))
        self.conn.commit()

    def update_plan_status(self, plan_id: int, status: str, metadata_json: str = None):
        """Update plan status and metadata."""
        cursor = self.conn.cursor()
        if metadata_json:
            cursor.execute(
                "UPDATE plans SET status = ?, metadata_json = ? WHERE id = ?",
                (status, metadata_json, plan_id),
            )
        else:
            cursor.execute("UPDATE plans SET status = ? WHERE id = ?", (status, plan_id))
        self.conn.commit()

    def _insert_spec(self, plan_id: int, spec_yaml: str, spec_type: str = None) -> int:
        """Insert spec and return spec ID (internal helper)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plan_specs (plan_id, spec_yaml, spec_type, created_at)
               VALUES (?, ?, ?, ?)""",
            (plan_id, spec_yaml, spec_type, datetime.now(UTC).isoformat()),
        )
        return cursor.lastrowid

    def add_plan_phase(
        self,
        plan_id: int,
        phase_number: int,
        title: str,
        description: str = None,
        success_criteria: str = None,
        status: str = "pending",
        created_at: str = "",
    ):
        """Add a phase to a plan (hierarchical planning structure)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plan_phases
               (plan_id, phase_number, title, description, success_criteria, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                plan_id,
                phase_number,
                title,
                description,
                success_criteria,
                status,
                created_at if created_at else datetime.now(UTC).isoformat(),
            ),
        )

    def add_plan_job(
        self,
        task_id: int,
        job_number: int,
        description: str,
        completed: int = 0,
        is_audit_job: int = 0,
        created_at: str = "",
    ):
        """Add a job (checkbox item) to a task (hierarchical task breakdown)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plan_jobs
               (task_id, job_number, description, completed, is_audit_job, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                job_number,
                description,
                completed,
                is_audit_job,
                created_at if created_at else datetime.now(UTC).isoformat(),
            ),
        )

    def commit(self):
        """Commit pending transactions."""
        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()
