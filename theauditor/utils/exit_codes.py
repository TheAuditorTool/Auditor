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
    
    # Success states
    SUCCESS = 0  # Complete success, no issues found
    
    # Issue severity levels (command succeeded but found problems)
    HIGH_SEVERITY = 1  # High severity findings (e.g., lint errors, bugs)
    CRITICAL_SEVERITY = 2  # Critical/security findings (e.g., vulnerabilities)
    
    # Task completion failures (command ran but couldn't complete objective)
    TASK_INCOMPLETE = 3  # Task could not be completed (e.g., missing prerequisites)
    
    # Future expansion
    # CONFIGURATION_ERROR = 4  # Invalid configuration
    # DEPENDENCY_ERROR = 5  # Missing dependencies
    # PERMISSION_ERROR = 6  # Insufficient permissions
    
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
        # Only SUCCESS (0) should allow pipeline to continue
        return code != cls.SUCCESS