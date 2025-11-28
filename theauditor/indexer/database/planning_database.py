"""Planning and meta-system database operations."""


class PlanningDatabaseMixin:
    """Mixin providing add_* methods for PLANNING_TABLES."""

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
        metadata_json: str = "{}",
    ):
        """Add a refactor candidate record to the batch."""
        self.generic_batches["refactor_candidates"].append(
            (
                file_path,
                reason,
                severity,
                loc,
                cyclomatic_complexity,
                duplication_percent,
                num_dependencies,
                detected_at,
                metadata_json,
            )
        )

    def add_refactor_history(
        self,
        timestamp: str,
        target_file: str,
        refactor_type: str,
        migrations_found: int | None = None,
        migrations_complete: int | None = None,
        schema_consistent: int | None = None,
        validation_status: str | None = None,
        details_json: str = "{}",
    ):
        """Add a refactor history record to the batch."""
        self.generic_batches["refactor_history"].append(
            (
                timestamp,
                target_file,
                refactor_type,
                migrations_found,
                migrations_complete,
                schema_consistent,
                validation_status,
                details_json,
            )
        )

    def add_plan_phase(
        self,
        plan_id: int,
        phase_number: int,
        title: str,
        description: str | None = None,
        success_criteria: str | None = None,
        status: str = "pending",
        created_at: str = "",
    ):
        """Add a phase to a plan (hierarchical planning structure)."""
        self.generic_batches["plan_phases"].append(
            (plan_id, phase_number, title, description, success_criteria, status, created_at)
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
        self.generic_batches["plan_jobs"].append(
            (task_id, job_number, description, completed, is_audit_job, created_at)
        )
