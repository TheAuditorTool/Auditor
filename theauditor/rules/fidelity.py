"""Fidelity tracking for rule execution.

Provides infrastructure to track what rules actually scan and verify
they don't silently fail. False negatives (rules that scan nothing
but report no findings) are caught by fidelity verification.

Usage:
    from theauditor.rules.fidelity import RuleDB, RuleResult

    def my_rule(context: StandardRuleContext) -> RuleResult:
        with RuleDB(context.db_path, "my_rule") as db:
            rows = db.query(Q("symbols").select("name").where("type = ?", "function"))
            findings = []
            for row in rows:
                # ... analyze ...
                pass
            return RuleResult(findings=findings, manifest=db.get_manifest())

Migration Patterns:
    BEFORE (raw SQL, no fidelity tracking):
    ```python
    def old_rule(context: StandardRuleContext) -> list[StandardFinding]:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, line FROM symbols WHERE type = ?", ("function",))
        rows = cursor.fetchall()
        findings = []
        for name, line in rows:
            if is_vulnerable(name):
                findings.append(StandardFinding(...))
        conn.close()
        return findings
    ```

    AFTER (Q class + fidelity tracking):
    ```python
    def new_rule(context: StandardRuleContext) -> RuleResult:
        with RuleDB(context.db_path, "new_rule") as db:
            rows = db.query(
                Q("symbols")
                .select("name", "line")
                .where("type = ?", "function")
            )
            findings = []
            for name, line in rows:
                if is_vulnerable(name):
                    findings.append(StandardFinding(...))
            return RuleResult(findings=findings, manifest=db.get_manifest())
    ```

    Key differences:
    - Connection management: RuleDB handles open/close via context manager
    - Query building: Q class validates columns against schema
    - Fidelity: Manifest tracks items_scanned, tables_queried, queries_executed
    - Return type: RuleResult wraps findings + manifest for orchestrator verification
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from theauditor.utils.logging import logger

if TYPE_CHECKING:
    from theauditor.rules.base import StandardFinding
    from theauditor.rules.query import Q


STRICT_FIDELITY = os.environ.get("THEAUDITOR_FIDELITY_STRICT", "0") == "1"


class FidelityError(Exception):
    """Raised when fidelity verification fails in strict mode."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Fidelity check failed: {errors}")


@dataclass
class RuleResult:
    """Wrapper for rule findings with fidelity manifest.

    Rules can return either list[StandardFinding] (legacy) or RuleResult.
    RuleResult includes a manifest tracking what was scanned for verification.
    """

    findings: list[StandardFinding]
    manifest: dict = field(default_factory=dict)


class RuleManifest:
    """Tracks fidelity metrics during rule execution.

    Automatically records:
    - items_scanned: Total rows processed across all queries
    - tables_queried: Set of table names accessed
    - queries_executed: Count of queries run
    - execution_time_ms: Time from manifest creation to to_dict()
    """

    def __init__(self, rule_name: str):
        """Initialize manifest for a rule.

        Args:
            rule_name: Name of the rule being executed
        """
        self.rule_name = rule_name
        self.items_scanned = 0
        self.tables_queried: set[str] = set()
        self.queries_executed = 0
        self._start_time = time.time()

    def track_query(self, table_name: str, row_count: int) -> None:
        """Record a query execution.

        Args:
            table_name: Primary table queried
            row_count: Number of rows returned
        """
        self.tables_queried.add(table_name)
        self.queries_executed += 1
        self.items_scanned += row_count

    def to_dict(self) -> dict:
        """Convert manifest to dictionary for storage/verification.

        Returns:
            Dict with standardized fidelity keys
        """
        return {
            "rule_name": self.rule_name,
            "items_scanned": self.items_scanned,
            "tables_queried": sorted(self.tables_queried),
            "queries_executed": self.queries_executed,
            "execution_time_ms": int((time.time() - self._start_time) * 1000),
        }


class RuleDB:
    """Database helper for rules with automatic fidelity tracking.

    Manages connection lifecycle and tracks all queries for manifest.
    Use as context manager for automatic cleanup.

    Usage:
        with RuleDB(db_path, "my_rule") as db:
            rows = db.query(Q("symbols").select("name"))
            # ... process rows ...
            return RuleResult(findings=findings, manifest=db.get_manifest())
    """

    def __init__(self, db_path: str, rule_name: str = "unknown"):
        """Initialize database helper.

        Args:
            db_path: Path to SQLite database
            rule_name: Name for manifest tracking
        """
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._manifest = RuleManifest(rule_name)

    def query(self, q: Q) -> list[tuple]:
        """Execute a Q query with fidelity tracking.

        Args:
            q: Q query builder object

        Returns:
            List of result tuples
        """
        sql, params = q.build()
        self.cursor.execute(sql, params)
        rows = self.cursor.fetchall()
        self._manifest.track_query(q._base_table, len(rows))
        return rows

    def execute(self, sql: str, params: list | None = None) -> list[tuple]:
        """Execute raw SQL with fidelity tracking.

        Use for queries that Q cannot express. Tracks query count
        and row count but cannot track table name.

        Args:
            sql: SQL query string
            params: Optional parameter list

        Returns:
            List of result tuples
        """
        self.cursor.execute(sql, params or [])
        rows = self.cursor.fetchall()
        self._manifest.queries_executed += 1
        self._manifest.items_scanned += len(rows)
        return rows

    def get_manifest(self) -> dict:
        """Get current fidelity manifest.

        Returns:
            Dict with fidelity tracking data
        """
        return self._manifest.to_dict()

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self) -> RuleDB:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - always close connection."""
        self.close()
        return False


def verify_fidelity(manifest: dict, expected: dict) -> tuple[bool, list[str]]:
    """Verify rule manifest against expected behavior.

    Checks:
    1. items_scanned > 0 when table has rows (catches silent failures)

    In strict mode (THEAUDITOR_FIDELITY_STRICT=1), raises FidelityError.
    In warn mode (default), logs warning and returns errors.

    Args:
        manifest: Fidelity manifest from rule execution
        expected: Expected values computed by orchestrator

    Returns:
        Tuple of (passed: bool, errors: list[str])

    Raises:
        FidelityError: In strict mode when verification fails
    """
    errors = []

    items_scanned = manifest.get("items_scanned", 0)
    table_row_count = expected.get("table_row_count", 0)

    if items_scanned == 0 and table_row_count > 0:
        errors.append(f"Rule scanned 0 items but table has {table_row_count} rows")

    passed = len(errors) == 0

    if not passed:
        if STRICT_FIDELITY:
            raise FidelityError(errors)
        else:
            rule_name = manifest.get("rule_name", "unknown")
            logger.warning(f"Fidelity check failed for {rule_name}: {errors}")

    return passed, errors
