"""Planning system for task management and verification.

This package provides:
- PlanningManager: Database operations for planning.db
- verify_task_spec: Verification integration with RefactorRuleEngine
- create_snapshot: Git snapshot management
"""

from .manager import PlanningManager

__all__ = ["PlanningManager"]
