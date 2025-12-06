"""SessionExecutionStore - Persist session execution data to SQLite."""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger


@dataclass
class SessionExecution:
    """Complete session execution record."""

    session_id: str
    task_description: str
    workflow_compliant: bool
    compliance_score: float
    risk_score: float
    task_completed: bool
    corrections_needed: bool
    rollback: bool
    timestamp: str
    tool_call_count: int
    files_modified: int
    user_message_count: int
    user_engagement_rate: float
    diffs_scored: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class SessionExecutionStore:
    """Store session execution data to SQLite database.

    Note: JSON dual-write removed - was creating thousands of files.
    Use database queries for data access instead.
    """

    def __init__(self, db_path: Path = None):
        """Initialize session execution store."""
        self.db_path = db_path or Path(".pf/ml/session_history.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_session_executions_table()

    def _create_session_executions_table(self):
        """Create session_executions table with indexes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    task_description TEXT,
                    workflow_compliant INTEGER DEFAULT 0,
                    compliance_score REAL DEFAULT 0.0,
                    risk_score REAL DEFAULT 0.0,
                    task_completed INTEGER DEFAULT 0,
                    corrections_needed INTEGER DEFAULT 0,
                    rollback INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    tool_call_count INTEGER DEFAULT 0,
                    files_modified INTEGER DEFAULT 0,
                    user_message_count INTEGER DEFAULT 0,
                    user_engagement_rate REAL DEFAULT 0.0,
                    diffs_scored TEXT,
                    last_modified TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_executions_session_id
                ON session_executions(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_executions_timestamp
                ON session_executions(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_executions_compliant
                ON session_executions(workflow_compliant)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_executions_engagement
                ON session_executions(user_engagement_rate)
            """)

            conn.commit()
            logger.debug("session_executions table created/verified")
        except sqlite3.Error as e:
            logger.error(f"Failed to create session_executions table: {e}")
            conn.rollback()
            conn.close()
            raise
        finally:
            conn.close()

    def store_execution(self, execution: SessionExecution):
        """Store single session execution to database."""
        self._write_to_db(execution)
        logger.debug(f"Stored session execution: {execution.session_id}")

    def store_executions_batch(self, executions: list[SessionExecution]):
        """Store multiple executions in a single transaction (much faster)."""
        if not executions:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            last_modified = datetime.now().isoformat()
            data_to_insert = []

            for exc in executions:
                diffs_json = json.dumps(exc.diffs_scored)
                data_to_insert.append(
                    (
                        exc.session_id,
                        exc.task_description,
                        1 if exc.workflow_compliant else 0,
                        exc.compliance_score,
                        exc.risk_score,
                        1 if exc.task_completed else 0,
                        1 if exc.corrections_needed else 0,
                        1 if exc.rollback else 0,
                        exc.timestamp,
                        exc.tool_call_count,
                        exc.files_modified,
                        exc.user_message_count,
                        exc.user_engagement_rate,
                        diffs_json,
                        last_modified,
                    )
                )

            cursor.executemany(
                """
                INSERT OR REPLACE INTO session_executions (
                    session_id, task_description, workflow_compliant,
                    compliance_score, risk_score, task_completed,
                    corrections_needed, rollback, timestamp,
                    tool_call_count, files_modified, user_message_count,
                    user_engagement_rate, diffs_scored, last_modified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                data_to_insert,
            )

            conn.commit()
            logger.info(f"Batch stored {len(executions)} session executions")
        except sqlite3.Error as e:
            logger.error(f"Failed batch write: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def _write_to_db(self, execution: SessionExecution):
        """Write session execution to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            diffs_json = json.dumps(execution.diffs_scored)
            last_modified = datetime.now().isoformat()

            cursor.execute(
                """
                INSERT OR REPLACE INTO session_executions (
                    session_id, task_description, workflow_compliant,
                    compliance_score, risk_score, task_completed,
                    corrections_needed, rollback, timestamp,
                    tool_call_count, files_modified, user_message_count,
                    user_engagement_rate, diffs_scored, last_modified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    execution.session_id,
                    execution.task_description,
                    1 if execution.workflow_compliant else 0,
                    execution.compliance_score,
                    execution.risk_score,
                    1 if execution.task_completed else 0,
                    1 if execution.corrections_needed else 0,
                    1 if execution.rollback else 0,
                    execution.timestamp,
                    execution.tool_call_count,
                    execution.files_modified,
                    execution.user_message_count,
                    execution.user_engagement_rate,
                    diffs_json,
                    last_modified,
                ),
            )

            conn.commit()
            logger.debug(f"Wrote session to database: {execution.session_id}")
        except sqlite3.Error as e:
            logger.error(f"Failed to write to database: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def query_executions_for_file(self, file_path: str) -> list[SessionExecution]:
        """Query session executions that modified a specific file."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT session_id, task_description, workflow_compliant,
                       compliance_score, risk_score, task_completed,
                       corrections_needed, rollback, timestamp,
                       tool_call_count, files_modified, user_message_count,
                       user_engagement_rate, diffs_scored
                FROM session_executions
                WHERE diffs_scored LIKE ?
                ORDER BY timestamp DESC
            """,
                (f"%{file_path}%",),
            )

            rows = cursor.fetchall()

            executions = []
            for row in rows:
                diffs_scored = json.loads(row[13]) if row[13] else []
                executions.append(
                    SessionExecution(
                        session_id=row[0],
                        task_description=row[1],
                        workflow_compliant=bool(row[2]),
                        compliance_score=row[3],
                        risk_score=row[4],
                        task_completed=bool(row[5]),
                        corrections_needed=bool(row[6]),
                        rollback=bool(row[7]),
                        timestamp=row[8],
                        tool_call_count=row[9],
                        files_modified=row[10],
                        user_message_count=row[11],
                        user_engagement_rate=row[12],
                        diffs_scored=diffs_scored,
                    )
                )

            return executions
        except sqlite3.Error as e:
            logger.error(f"Failed to query executions: {e}")
            return []
        finally:
            conn.close()

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregate statistics from session executions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    workflow_compliant,
                    COUNT(*) as count,
                    AVG(risk_score) as avg_risk,
                    AVG(compliance_score) as avg_compliance,
                    AVG(user_engagement_rate) as avg_engagement,
                    SUM(corrections_needed) * 1.0 / COUNT(*) as correction_rate,
                    SUM(rollback) * 1.0 / COUNT(*) as rollback_rate
                FROM session_executions
                GROUP BY workflow_compliant
            """)

            rows = cursor.fetchall()

            stats = {}
            for row in rows:
                key = "compliant" if row[0] else "non_compliant"
                stats[key] = {
                    "count": row[1],
                    "avg_risk_score": row[2],
                    "avg_compliance_score": row[3],
                    "avg_user_engagement": row[4],
                    "correction_rate": row[5],
                    "rollback_rate": row[6],
                }

            cursor.execute("SELECT COUNT(*) FROM session_executions")
            stats["total_sessions"] = cursor.fetchone()[0]

            return stats
        except sqlite3.Error as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
        finally:
            conn.close()
