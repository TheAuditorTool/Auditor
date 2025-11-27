"""Centralized exit codes for TheAuditor CLI.

This module provides a single source of truth for all program exit codes,
eliminating magic numbers and ensuring consistency across the application.
"""


class ExitCodes:
    """Standard exit codes for TheAuditor CLI commands.

    These codes follow a semantic pattern:
    - 0: Complete success, no issues found
    - 1: Command executed but found issues requiring attention
    - 2: Command executed but found critical/security issues
    - 3: Command could not complete its intended task
    - 4+: Reserved for future use

    This aligns with Unix conventions where 0 = success and non-zero = various failure modes.
    """

    SUCCESS = 0

    HIGH_SEVERITY = 1
    CRITICAL_SEVERITY = 2

    TASK_INCOMPLETE = 3

    SCHEMA_STALE = 10

    @classmethod
    def get_description(cls, code: int) -> str:
        """Get human-readable description for an exit code.

        Args:
            code: The exit code to describe

        Returns:
            Human-readable description of the exit code's meaning
        """
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
        """Determine if an exit code should fail a CI/CD pipeline.

        Args:
            code: The exit code to check

        Returns:
            True if the code indicates a failure that should stop the pipeline
        """

        return code >= cls.TASK_INCOMPLETE
