"""Snapshot management for planning system."""

import warnings
from datetime import UTC, datetime
from pathlib import Path

from .shadow_git import ShadowRepoManager


def create_snapshot(
    plan_id: int,
    checkpoint_name: str,
    repo_root: Path,
    task_id: int | None = None,
    manager=None,
) -> dict:
    """DEPRECATED: Create a code snapshot at the current git state."""
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
    """DEPRECATED: Load a snapshot from the database."""
    warnings.warn(
        "load_snapshot() is deprecated. Use PlanningManager.get_snapshot() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    return manager.get_snapshot(snapshot_id)


__all__ = ["create_snapshot", "load_snapshot", "ShadowRepoManager"]
