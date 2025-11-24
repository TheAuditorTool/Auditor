"""Shadow Git Manager.

Manages an isolated, bare git repository in .pf/snapshots.git.
Used for tracking incremental AI edits without polluting the user's
actual git history.

Architecture:
    - Creates a BARE repository (no working tree, just object database)
    - User's .git folder is NEVER touched
    - All snapshots stored in .pf/snapshots.git
    - Provides O(1) tree-based diffing via libgit2

NO FALLBACKS. Hard failure if pygit2 operations fail.
"""

from pathlib import Path
from datetime import datetime, UTC
import warnings

import pygit2


class ShadowRepoManager:
    """Manages shadow git repository for planning snapshots.

    The shadow repo is a bare git repository that stores file states
    without affecting the user's actual git history.

    Attributes:
        repo_path: Path to .pf/snapshots.git
    """

    def __init__(self, pf_root: Path):
        """Initialize or load the shadow repository.

        Args:
            pf_root: The .pf/ directory path

        Raises:
            pygit2.GitError: If repository initialization fails
        """
        self.repo_path = pf_root / "snapshots.git"
        self._repo = self._init_or_load()

    def _init_or_load(self) -> pygit2.Repository:
        """Initialize bare repo if missing, otherwise load it.

        Returns:
            pygit2.Repository instance

        NO FALLBACKS. Raises on any error.
        """
        if not self.repo_path.exists():
            # bare=True: No working tree, just object database
            return pygit2.init_repository(str(self.repo_path), bare=True)
        return pygit2.Repository(str(self.repo_path))

    def create_snapshot(
        self,
        project_root: Path,
        file_paths: list[str],
        message: str,
    ) -> str:
        """Read files from project_root and commit them to the shadow repo.

        Args:
            project_root: Root directory of the user's project
            file_paths: List of relative file paths to snapshot
            message: Commit message for the snapshot

        Returns:
            str: The SHA-1 hash of the new shadow commit

        Raises:
            pygit2.GitError: If git operations fail

        Warns:
            UserWarning: If any files in file_paths don't exist (skipped)

        NO FALLBACKS. pygit2 errors cause hard failure.
        Missing files are warned and skipped (may have been deleted).
        """
        # Create an in-memory index for the shadow repo
        index = pygit2.Index()

        files_added = []
        skipped_files = []
        for rel_path in file_paths:
            full_path = project_root / rel_path
            if not full_path.exists():
                # File may have been deleted - track for warning
                skipped_files.append(rel_path)
                continue

            # Create blob from file content directly
            blob_id = self._repo.create_blob_fromdisk(str(full_path))

            # Add blob to our in-memory index
            # 33188 = 0o100644 (standard rw-r--r-- file mode)
            index.add(pygit2.IndexEntry(rel_path, blob_id, 33188))
            files_added.append(rel_path)

        # Warn about skipped files (visible to user, not silent)
        if skipped_files:
            warnings.warn(
                f"Skipped {len(skipped_files)} missing file(s): {', '.join(skipped_files[:5])}"
                + (f" (+{len(skipped_files)-5} more)" if len(skipped_files) > 5 else ""),
                UserWarning,
                stacklevel=2,
            )

        # Write the tree object from our in-memory index
        tree_id = index.write_tree(self._repo)

        # Determine parent commit (if shadow repo has history)
        parents = []
        if not self._repo.is_empty:
            parents = [self._repo.head.target]

        # Create signature for commits
        author = pygit2.Signature(
            "TheAuditor",
            "internal@auditor.local",
            int(datetime.now(UTC).timestamp()),
            0  # UTC offset
        )

        # Create the commit in shadow repo
        # Updates HEAD in shadow repo to maintain history chain
        commit_oid = self._repo.create_commit(
            "HEAD",         # Update shadow HEAD
            author,         # Author
            author,         # Committer
            message,        # Commit message
            tree_id,        # Root tree
            parents         # Parent commits
        )

        return str(commit_oid)

    def get_diff(self, old_sha: str | None, new_sha: str) -> str:
        """Generate a unified diff between two shadow commits.

        Args:
            old_sha: SHA of older commit (None for first commit)
            new_sha: SHA of newer commit

        Returns:
            str: Unified diff text

        Raises:
            KeyError: If SHA not found in repository
        """
        new_commit = self._repo.get(new_sha)
        new_tree = new_commit.tree

        if old_sha:
            old_commit = self._repo.get(old_sha)
            old_tree = old_commit.tree
            # Diff tree-to-tree
            diff = self._repo.diff(old_tree, new_tree)
        else:
            # First commit - diff against empty tree
            diff = new_tree.diff_to_tree(swap=True)

        return diff.patch or ""

    def get_file_at_snapshot(self, sha: str, file_path: str) -> bytes | None:
        """Retrieve file content at a specific snapshot.

        Args:
            sha: Commit SHA
            file_path: Relative path to file

        Returns:
            bytes: File content, or None if file doesn't exist at that snapshot
        """
        commit = self._repo.get(sha)
        tree = commit.tree

        try:
            entry = tree[file_path]
            blob = self._repo.get(entry.id)
            return blob.data
        except KeyError:
            return None

    def list_snapshots(self, limit: int = 100) -> list[dict]:
        """List all snapshots in the shadow repository.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of dicts with snapshot metadata:
                - sha: Commit SHA
                - message: Commit message
                - timestamp: ISO timestamp
                - files: List of files in snapshot
        """
        if self._repo.is_empty:
            return []

        snapshots = []
        for commit in self._repo.walk(self._repo.head.target, pygit2.GIT_SORT_TIME):
            if len(snapshots) >= limit:
                break

            # Get file list from tree
            files = [entry.name for entry in commit.tree]

            snapshots.append({
                "sha": str(commit.id),
                "message": commit.message.strip(),
                "timestamp": datetime.fromtimestamp(
                    commit.commit_time, UTC
                ).isoformat(),
                "files": files,
            })

        return snapshots

    def get_diff_stats(self, old_sha: str | None, new_sha: str) -> dict:
        """Get diff statistics between two snapshots.

        Args:
            old_sha: SHA of older commit (None for first commit)
            new_sha: SHA of newer commit

        Returns:
            dict with:
                - files_changed: Number of files changed
                - insertions: Lines added
                - deletions: Lines removed
                - files: List of changed file paths
        """
        new_commit = self._repo.get(new_sha)
        new_tree = new_commit.tree

        if old_sha:
            old_commit = self._repo.get(old_sha)
            old_tree = old_commit.tree
            diff = self._repo.diff(old_tree, new_tree)
        else:
            diff = new_tree.diff_to_tree(swap=True)

        stats = diff.stats
        files = [delta.new_file.path for delta in diff.deltas]

        return {
            "files_changed": stats.files_changed,
            "insertions": stats.insertions,
            "deletions": stats.deletions,
            "files": files,
        }
