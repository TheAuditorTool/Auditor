"""Centralized exit codes for TheAuditor CLI.

This module provides a single source of truth for all program exit codes,
eliminating magic numbers and ensuring consistency across the application.
"""
from __future__ import annotations



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
    
    # Success states
    SUCCESS = 0  # Complete success, no issues found
    
    # Issue severity levels (command succeeded but found problems)
    HIGH_SEVERITY = 1  # High severity findings (e.g., lint errors, bugs)
    CRITICAL_SEVERITY = 2  # Critical/security findings (e.g., vulnerabilities)
    
    # Task completion failures (command ran but couldn't complete objective)
    TASK_INCOMPLETE = 3  # Task could not be completed (e.g., missing prerequisites)

    # Build and configuration errors
    SCHEMA_STALE = 10  # Schema files changed but generated code not regenerated (auto-fixable)
    
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
        # Exit codes 0, 1, 2 indicate successful command execution
        # 0 = no findings, 1 = high severity findings, 2 = critical findings
        # Only 3+ (task incomplete or other errors) should fail the pipeline
        return code >= cls.TASK_INCOMPLETE