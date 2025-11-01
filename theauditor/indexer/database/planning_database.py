"""Planning and meta-system database operations.

This module contains add_* methods for PLANNING_TABLES defined in schemas/planning_schema.py.
Handles 5 planning tables including plans, tasks, specs, code snapshots, and diffs.

NOTE: This module is currently a stub. Planning methods will be added as the
      planning system (aud planning commands) evolves. This is kept separate
      because the planning subsystem will iterate rapidly and needs clean isolation.
"""

from typing import Optional, List, Dict


class PlanningDatabaseMixin:
    """Mixin providing add_* methods for PLANNING_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.

    PLANNING TABLES (6 tables):
    - plans: Main planning table (id, name, description, status, metadata)
    - plan_tasks: Tasks within plans (plan_id FK, task_number, status, spec_id FK)
    - plan_specs: Specs for plans (plan_id FK, spec_yaml, spec_type)
    - code_snapshots: Code snapshots/checkpoints (plan_id FK, task_id FK, checkpoint_name, git_ref)
    - code_diffs: Diffs between snapshots (snapshot_id FK, file_path, diff_text, line counts)
    - refactor_candidates: Files flagged for refactoring (file_path, reason, severity, metrics)

    FUTURE: Add methods as planning system evolves:
    - add_plan()
    - add_plan_task()
    - add_plan_spec()
    - add_code_snapshot()
    - add_code_diff()
    """

    # ========================================================
    # REFACTOR CANDIDATE METHODS
    # ========================================================

    def add_refactor_candidate(
        self,
        file_path: str,
        reason: str,
        severity: str,
        detected_at: str,
        loc: Optional[int] = None,
        cyclomatic_complexity: Optional[int] = None,
        duplication_percent: Optional[float] = None,
        num_dependencies: Optional[int] = None,
        metadata_json: str = '{}'
    ):
        """Add a refactor candidate record to the batch.

        Args:
            file_path: Path to file flagged for refactoring
            reason: Why file needs refactoring (complexity, duplication, size, coupling)
            severity: Severity level (low, medium, high, critical)
            detected_at: ISO timestamp when detected
            loc: Lines of code (optional)
            cyclomatic_complexity: McCabe complexity score (optional)
            duplication_percent: Percentage of duplicated code (optional)
            num_dependencies: Number of dependencies/imports (optional)
            metadata_json: Additional metadata as JSON string
        """
        self.generic_batches['refactor_candidates'].append((
            file_path,
            reason,
            severity,
            loc,
            cyclomatic_complexity,
            duplication_percent,
            num_dependencies,
            detected_at,
            metadata_json
        ))

    # ========================================================
    # REFACTOR HISTORY METHODS
    # ========================================================

    def add_refactor_history(
        self,
        timestamp: str,
        target_file: str,
        refactor_type: str,
        migrations_found: Optional[int] = None,
        migrations_complete: Optional[int] = None,
        schema_consistent: Optional[int] = None,
        validation_status: Optional[str] = None,
        details_json: str = '{}'
    ):
        """Add a refactor history record to the batch.

        Args:
            timestamp: ISO timestamp when refactor was executed
            target_file: File that was refactored
            refactor_type: Type of refactor (split, rename, consolidate)
            migrations_found: Number of migrations found
            migrations_complete: Number of migrations completed
            schema_consistent: Boolean (as INTEGER) - schema consistency check
            validation_status: Validation result (success, failed, partial)
            details_json: Additional details as JSON string
        """
        self.generic_batches['refactor_history'].append((
            timestamp,
            target_file,
            refactor_type,
            migrations_found,
            migrations_complete,
            schema_consistent,
            validation_status,
            details_json
        ))

    # ========================================================
    # PLANNING BATCH METHODS
    # ========================================================
    # TODO: Add planning methods as aud planning commands evolve
    # Pattern: Follow same normalized many-to-many approach as other mixins
    # Example:
    #   def add_plan(self, name: str, description: Optional[str], ...):
    #       self.generic_batches['plans'].append((name, description, ...))
