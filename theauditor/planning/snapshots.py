"""
Snapshot management for planning system.

Handles git-based code snapshots and diffs for tracking implementation progress.
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import platform

# Windows detection
IS_WINDOWS = platform.system() == "Windows"


def create_snapshot(plan_id: int, checkpoint_name: str, repo_root: Path, manager=None) -> Dict:
    """
    Create a code snapshot at the current git state.

    Args:
        plan_id: Plan ID to associate snapshot with
        checkpoint_name: Name for this checkpoint (e.g., "pre-refactor", "post-migration")
        repo_root: Repository root directory
        manager: Optional PlanningManager instance to persist snapshot

    Returns:
        Dict with snapshot data:
            - git_ref: Current git commit SHA
            - files_affected: List of modified file paths
            - diffs: List of diffs with added/removed line counts

    Raises:
        subprocess.CalledProcessError: If git commands fail
    """
    # Get current git commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
        shell=IS_WINDOWS
    )
    git_ref = result.stdout.strip()

    # Get git diff (staged and unstaged changes)
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
        shell=IS_WINDOWS
    )
    full_diff = result.stdout

    # Parse diff to extract file paths and line counts
    files_affected = []
    diffs = []

    if full_diff:
        current_file = None
        current_diff = []
        added_lines = 0
        removed_lines = 0

        for line in full_diff.split('\n'):
            if line.startswith('diff --git'):
                # Save previous file's diff
                if current_file:
                    diffs.append({
                        'file_path': current_file,
                        'diff_text': '\n'.join(current_diff),
                        'added_lines': added_lines,
                        'removed_lines': removed_lines
                    })
                    files_affected.append(current_file)

                # Extract file path from "diff --git a/path b/path"
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[2][2:]  # Remove 'a/' prefix
                    current_diff = [line]
                    added_lines = 0
                    removed_lines = 0
            elif current_file:
                current_diff.append(line)
                if line.startswith('+') and not line.startswith('+++'):
                    added_lines += 1
                elif line.startswith('-') and not line.startswith('---'):
                    removed_lines += 1

        # Save last file's diff
        if current_file:
            diffs.append({
                'file_path': current_file,
                'diff_text': '\n'.join(current_diff),
                'added_lines': added_lines,
                'removed_lines': removed_lines
            })
            files_affected.append(current_file)

    snapshot_data = {
        'git_ref': git_ref,
        'checkpoint_name': checkpoint_name,
        'timestamp': datetime.utcnow().isoformat(),
        'files_affected': files_affected,
        'diffs': diffs
    }

    # Persist to database if manager provided
    if manager:
        files_json = json.dumps(files_affected)
        cursor = manager.conn.cursor()

        cursor.execute("""
            INSERT INTO code_snapshots (plan_id, checkpoint_name, timestamp, git_ref, files_json)
            VALUES (?, ?, ?, ?, ?)
        """, (plan_id, checkpoint_name, snapshot_data['timestamp'], git_ref, files_json))

        snapshot_id = cursor.lastrowid

        # Insert diffs
        for diff_item in diffs:
            cursor.execute("""
                INSERT INTO code_diffs (snapshot_id, file_path, diff_text, added_lines, removed_lines)
                VALUES (?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                diff_item['file_path'],
                diff_item['diff_text'],
                diff_item['added_lines'],
                diff_item['removed_lines']
            ))

        manager.conn.commit()
        snapshot_data['snapshot_id'] = snapshot_id

    return snapshot_data


def load_snapshot(snapshot_id: int, manager) -> Optional[Dict]:
    """
    Load a snapshot from the database.

    Args:
        snapshot_id: Snapshot ID to load
        manager: PlanningManager instance

    Returns:
        Dict with snapshot data or None if not found
    """
    cursor = manager.conn.cursor()

    # Load snapshot metadata
    cursor.execute("""
        SELECT id, plan_id, checkpoint_name, timestamp, git_ref, files_json
        FROM code_snapshots
        WHERE id = ?
    """, (snapshot_id,))

    row = cursor.fetchone()
    if not row:
        return None

    snapshot_data = {
        'snapshot_id': row[0],
        'plan_id': row[1],
        'checkpoint_name': row[2],
        'timestamp': row[3],
        'git_ref': row[4],
        'files_affected': json.loads(row[5]) if row[5] else []
    }

    # Load diffs
    cursor.execute("""
        SELECT file_path, diff_text, added_lines, removed_lines
        FROM code_diffs
        WHERE snapshot_id = ?
    """, (snapshot_id,))

    diffs = []
    for diff_row in cursor.fetchall():
        diffs.append({
            'file_path': diff_row[0],
            'diff_text': diff_row[1],
            'added_lines': diff_row[2],
            'removed_lines': diff_row[3]
        })

    snapshot_data['diffs'] = diffs

    return snapshot_data
