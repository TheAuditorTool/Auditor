"""Snapshot management for planning system.

DEPRECATED: This module contains legacy snapshot functions that use subprocess
to shell out to git and manually parse diffs. New code should use:
- PlanningManager.create_snapshot() - Uses pygit2 shadow repo
- ShadowRepoManager - Direct access to .pf/snapshots.git

The legacy functions are kept for backward compatibility but will be removed
in a future version.

Migration path:
    # OLD (deprecated)
    from theauditor.planning.snapshots import create_snapshot
    snapshot_data = create_snapshot(plan_id, name, repo_root, task_id, manager)

    # NEW (recommended)
    from theauditor.planning import PlanningManager
    manager = PlanningManager(db_path)
    snapshot_id, sha = manager.create_snapshot(plan_id, name, repo_root, files, task_id)
"""

import warnings
from pathlib import Path
from datetime import datetime, UTC

from .shadow_git import ShadowRepoManager


def create_snapshot(
    plan_id: int,
    checkpoint_name: str,
    repo_root: Path,
    task_id: int | None = None,
    manager=None,
) -> dict:
    """DEPRECATED: Create a code snapshot at the current git state.

    Use PlanningManager.create_snapshot() instead, which uses pygit2
    for efficient, binary-safe snapshot storage.

    Args:
        plan_id: Plan ID to associate snapshot with
        checkpoint_name: Name for this checkpoint
        repo_root: Repository root directory
        task_id: Optional task ID for sequence tracking
        manager: Optional PlanningManager instance to persist snapshot

    Returns:
        Dict with snapshot data

    .. deprecated:: 1.6.5
        Use :meth:`PlanningManager.create_snapshot` instead.
    """
    warnings.warn(
        "create_snapshot() is deprecated. Use PlanningManager.create_snapshot() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    if manager:
        import subprocess

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            shell=False,
        )

        files_affected = []
        for line in result.stdout.strip().split("\n"):
            if line:
                filename = line[3:].strip()

                if " -> " in filename:
                    filename = filename.split(" -> ")[1]
                files_affected.append(filename)

        snapshot_id, shadow_sha = manager.create_snapshot(
            plan_id=plan_id,
            checkpoint_name=checkpoint_name,
            project_root=repo_root,
            files_affected=files_affected,
            task_id=task_id,
        )

        return {
            "snapshot_id": snapshot_id,
            "shadow_sha": shadow_sha,
            "checkpoint_name": checkpoint_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "files_affected": files_affected,
            "diffs": [],
        }

    return {
        "checkpoint_name": checkpoint_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "files_affected": [],
        "diffs": [],
    }


def load_snapshot(snapshot_id: int, manager) -> dict | None:
    """DEPRECATED: Load a snapshot from the database.

    Use PlanningManager.get_snapshot() instead.

    Args:
        snapshot_id: Snapshot ID to load
        manager: PlanningManager instance

    Returns:
        Dict with snapshot data or None if not found

    .. deprecated:: 1.6.5
        Use :meth:`PlanningManager.get_snapshot` instead.
    """
    warnings.warn(
        "load_snapshot() is deprecated. Use PlanningManager.get_snapshot() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    return manager.get_snapshot(snapshot_id)


__all__ = ["create_snapshot", "load_snapshot", "ShadowRepoManager"]
