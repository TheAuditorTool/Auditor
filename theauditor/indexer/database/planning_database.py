"""Planning and meta-system database operations.

This module contains add_* methods for PLANNING_TABLES defined in schemas/planning_schema.py.
Handles 9 planning tables including plans, phases, tasks, jobs, specs, snapshots, diffs, and refactor tracking.

ERIC'S FRAMEWORK INTEGRATION:
    Phase → Task → Job hierarchy enables problem decomposition thinking:
    - Phases define success criteria (with "Success Criteria" field)
    - Tasks break down phase goals into actionable steps
    - Jobs are atomic checkbox items within tasks
    - Audit loops at task and phase level enforce loop-until-correct semantics
"""


class PlanningDatabaseMixin:
    """Mixin providing add_* methods for PLANNING_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.

    PLANNING TABLES (9 tables - Eric's Framework Integration):
    - plans: Main planning table (id, name, description, status, metadata)
    - plan_phases: Phase hierarchy (plan_id FK, phase_number, success_criteria) [NEW]
    - plan_tasks: Tasks within phases (plan_id FK, phase_id FK, task_number, audit_status)
    - plan_jobs: Checkbox items (task_id FK, job_number, completed, is_audit_job) [NEW]
    - plan_specs: Specs for plans (plan_id FK, spec_yaml, spec_type)
    - code_snapshots: Code snapshots/checkpoints (plan_id FK, task_id FK, checkpoint_name, git_ref)
    - code_diffs: Diffs between snapshots (snapshot_id FK, file_path, diff_text, line counts)
    - refactor_candidates: Files flagged for refactoring (file_path, reason, severity, metrics)
    - refactor_history: Refactor execution history (timestamp, target_file, migrations)

    ERIC'S FRAMEWORK METHODS:
    - add_plan_phase() - Create phase with "Success Criteria" field
    - add_plan_job() - Add checkbox item to task with audit flag
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
        loc: int | None = None,
        cyclomatic_complexity: int | None = None,
        duplication_percent: float | None = None,
        num_dependencies: int | None = None,
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
        migrations_found: int | None = None,
        migrations_complete: int | None = None,
        schema_consistent: int | None = None,
        validation_status: str | None = None,
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

    def add_plan_phase(
        self,
        plan_id: int,
        phase_number: int,
        title: str,
        description: str | None = None,
        success_criteria: str | None = None,
        status: str = 'pending',
        created_at: str = ''
    ):
        """Add a phase to a plan (hierarchical planning structure).

        Args:
            plan_id: Foreign key to plans table
            phase_number: Sequential phase number (1, 2, 3...)
            title: Phase title (e.g., "Verify File is Active")
            description: What this phase accomplishes
            success_criteria: What completion looks like for this phase (criteria)
            status: Phase status (pending, in_progress, completed)
            created_at: ISO timestamp
        """
        self.generic_batches['plan_phases'].append((
            plan_id,
            phase_number,
            title,
            description,
            success_criteria,
            status,
            created_at
        ))

    def add_plan_job(
        self,
        task_id: int,
        job_number: int,
        description: str,
        completed: int = 0,
        is_audit_job: int = 0,
        created_at: str = ''
    ):
        """Add a job (checkbox item) to a task (hierarchical task breakdown).

        Args:
            task_id: Foreign key to plan_tasks table
            job_number: Sequential job number within task (1, 2, 3...)
            description: Job description (e.g., "Execute: aud deadcode | grep storage.py")
            completed: Boolean as INTEGER (0 = not completed, 1 = completed)
            is_audit_job: Boolean as INTEGER (0 = regular job, 1 = audit job)
            created_at: ISO timestamp
        """
        self.generic_batches['plan_jobs'].append((
            task_id,
            job_number,
            description,
            completed,
            is_audit_job,
            created_at
        ))
