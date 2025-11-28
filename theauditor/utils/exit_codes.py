"""Centralized exit codes for TheAuditor CLI."""


class ExitCodes:
    """Standard exit codes for TheAuditor CLI commands."""

    SUCCESS = 0

    HIGH_SEVERITY = 1
    CRITICAL_SEVERITY = 2

    TASK_INCOMPLETE = 3

    SCHEMA_STALE = 10

    @classmethod
    def get_description(cls, code: int) -> str:
        """Get human-readable description for an exit code."""
        descriptions = {
            cls.SUCCESS: "Success - No issues found",
            cls.HIGH_SEVERITY: "High severity findings detected",
            cls.CRITICAL_SEVERITY: "Critical security findings detected",
            cls.TASK_INCOMPLETE: "Task could not be completed due to missing prerequisites",
            cls.SCHEMA_STALE: "Schema files changed but generated code not regenerated - please retry",
        }
        return descriptions.get(code, f"Unknown exit code: {code}")

    @classmethod
    def should_fail_pipeline(cls, code: int) -> bool:
        """Determine if an exit code should fail a CI/CD pipeline."""

        return code >= cls.TASK_INCOMPLETE
