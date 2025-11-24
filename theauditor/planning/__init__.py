"""Planning system for task management and verification.

This package provides:
- PlanningManager: Database operations for planning.db
- ShadowRepoManager: Shadow git repository for efficient snapshots (pygit2)
- verify_task_spec: Verification integration with RefactorRuleEngine
"""

from .manager import PlanningManager
from .shadow_git import ShadowRepoManager

__all__ = ["PlanningManager", "ShadowRepoManager"]
