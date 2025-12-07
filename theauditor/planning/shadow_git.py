"""Shadow Git Manager."""

from datetime import UTC, datetime
from pathlib import Path

import pygit2

from theauditor.utils.logging import logger


class ShadowRepoManager:
    """Manages shadow git repository for planning snapshots."""

    def __init__(self, pf_root: Path):
        """Initialize or load the shadow repository."""
        self.repo_path = pf_root / "snapshots.git"
        self._repo = self._init_or_load()

    def _init_or_load(self) -> pygit2.Repository:
        """Initialize bare repo if missing, otherwise load it."""
        if not self.repo_path.exists():
            return pygit2.init_repository(str(self.repo_path), bare=True)
        return pygit2.Repository(str(self.repo_path))

    def create_snapshot(
        self,
        project_root: Path,
        file_paths: list[str],
        message: str,
    ) -> str:
        """Read files from project_root and commit them to the shadow repo."""

        index = pygit2.Index()

        files_added = []
        skipped_files = []
        for rel_path in file_paths:
            full_path = project_root / rel_path
            if not full_path.exists():
                skipped_files.append(rel_path)
                continue

            blob_id = self._repo.create_blob_fromdisk(str(full_path))

            index.add(pygit2.IndexEntry(rel_path, blob_id, 33188))
            files_added.append(rel_path)

        if skipped_files:
            logger.warning(
                "Skipped {} missing file(s): {}{}",
                len(skipped_files),
                ", ".join(skipped_files[:5]),
                f" (+{len(skipped_files) - 5} more)" if len(skipped_files) > 5 else "",
            )

        tree_id = index.write_tree(self._repo)

        parents = []
        if not self._repo.is_empty:
            parents = [self._repo.head.target]

        author = pygit2.Signature(
            "TheAuditor", "internal@auditor.local", int(datetime.now(UTC).timestamp()), 0
        )

        commit_oid = self._repo.create_commit("HEAD", author, author, message, tree_id, parents)

        return str(commit_oid)

    def get_diff(self, old_sha: str | None, new_sha: str) -> str:
        """Generate a unified diff between two shadow commits."""
        new_commit = self._repo.get(new_sha)
        new_tree = new_commit.tree

        if old_sha:
            old_commit = self._repo.get(old_sha)
            old_tree = old_commit.tree

            diff = self._repo.diff(old_tree, new_tree)
        else:
            diff = new_tree.diff_to_tree(swap=True)

        return diff.patch or ""

    def get_file_at_snapshot(self, sha: str, file_path: str) -> bytes | None:
        """Retrieve file content at a specific snapshot."""
        commit = self._repo.get(sha)
        tree = commit.tree

        try:
            entry = tree[file_path]
            blob = self._repo.get(entry.id)
            return blob.data
        except KeyError:
            return None

    def list_snapshots(self, limit: int = 100) -> list[dict]:
        """List all snapshots in the shadow repository."""
        if self._repo.is_empty:
            return []

        snapshots = []
        for commit in self._repo.walk(self._repo.head.target, pygit2.GIT_SORT_TIME):
            if len(snapshots) >= limit:
                break

            files = [entry.name for entry in commit.tree]

            snapshots.append(
                {
                    "sha": str(commit.id),
                    "message": commit.message.strip(),
                    "timestamp": datetime.fromtimestamp(commit.commit_time, UTC).isoformat(),
                    "files": files,
                }
            )

        return snapshots

    def get_diff_stats(self, old_sha: str | None, new_sha: str) -> dict:
        """Get diff statistics between two snapshots."""
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

    def detect_dirty_files(
        self, project_root: Path, max_files: int = 500, timeout_seconds: int = 30
    ) -> list[str]:
        """Detect files with uncommitted changes using pygit2.

        Replaces legacy subprocess 'git status' parsing.
        Returns relative paths as strings.

        Args:
            project_root: Path to the git repository root
            max_files: Maximum number of dirty files to return (prevents hanging on huge repos)
            timeout_seconds: Not used directly, but documents expected max time

        Note: If pygit2.status() is slow, falls back to subprocess git status.
        """
        import subprocess
        import time

        start_time = time.time()

        # Try pygit2 first, but fall back to subprocess if too slow
        try:
            repo = pygit2.Repository(str(project_root))

            # Use a thread to detect if status() hangs
            dirty_files = []
            status = repo.status()

            for filepath, flags in status.items():
                # Check timeout periodically
                if len(dirty_files) % 100 == 0:
                    if time.time() - start_time > timeout_seconds:
                        logger.warning(
                            "detect_dirty_files timeout after {}s, returning {} files",
                            timeout_seconds,
                            len(dirty_files),
                        )
                        break

                if flags & (
                    pygit2.GIT_STATUS_INDEX_NEW
                    | pygit2.GIT_STATUS_INDEX_MODIFIED
                    | pygit2.GIT_STATUS_WT_NEW
                    | pygit2.GIT_STATUS_WT_MODIFIED
                ):
                    # Skip common large directories that shouldn't be tracked
                    if any(
                        skip in filepath
                        for skip in ["node_modules/", ".git/", "__pycache__/", ".venv/", "venv/"]
                    ):
                        continue
                    dirty_files.append(filepath)

                    if len(dirty_files) >= max_files:
                        logger.warning(
                            "detect_dirty_files hit max_files limit ({}), truncating",
                            max_files,
                        )
                        break

            return dirty_files

        except Exception as e:
            logger.warning("pygit2 status failed ({}), falling back to subprocess", str(e))

            # Fallback to subprocess git status (usually faster)
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain", "-uall"],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                if result.returncode == 0:
                    dirty_files = []
                    for line in result.stdout.strip().split("\n"):
                        if line and len(line) > 3:
                            filepath = line[3:].strip()
                            # Handle renamed files (old -> new)
                            if " -> " in filepath:
                                filepath = filepath.split(" -> ")[1]
                            dirty_files.append(filepath)
                            if len(dirty_files) >= max_files:
                                break
                    return dirty_files
            except subprocess.TimeoutExpired:
                logger.error("git status timed out after {}s", timeout_seconds)
            except Exception as fallback_e:
                logger.error("Subprocess fallback failed: {}", str(fallback_e))

            return []
