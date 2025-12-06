"""Core functionality for file system operations and AST caching."""

import fnmatch
import os
import sqlite3
from pathlib import Path
from typing import Any

from theauditor.utils import compute_file_hash, count_lines_in_file
from theauditor.utils.logging import logger

from .config import MONOREPO_ENTRY_FILES, SKIP_DIRS, STANDARD_MONOREPO_PATHS


def is_text_file(file_path: Path) -> bool:
    """Check if file is text (not binary)."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            if b"\0" in chunk:
                return False

            try:
                chunk.decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        return False


def get_first_lines(file_path: Path, n: int = 2) -> list[str]:
    """Get first n lines of a text file."""
    lines = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break

                line = line.replace("\r", "").rstrip("\n")[:200]
                lines.append(line)
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        pass
    return lines


BASH_SHEBANGS = (
    "#!/bin/bash",
    "#!/usr/bin/env bash",
    "#!/bin/sh",
    "#!/usr/bin/env sh",
)


def _detect_bash_shebang(first_line: str) -> bool:
    """Check if first line is a bash/shell shebang."""
    if not first_line:
        return False
    return any(first_line.startswith(shebang) for shebang in BASH_SHEBANGS)


def load_gitignore_patterns(root_path: Path) -> set[str]:
    """Load patterns from .gitignore if it exists."""
    gitignore_path = root_path / ".gitignore"
    patterns = set()

    if gitignore_path.exists():
        try:
            with open(gitignore_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    if line and not line.startswith("#"):
                        pattern = line.rstrip("/")
                        if "/" not in pattern and "*" not in pattern:
                            patterns.add(pattern)
        except Exception:
            pass

    return patterns


class FileWalker:
    """Handles directory walking with monorepo detection and filtering."""

    def __init__(
        self,
        root_path: Path,
        follow_symlinks: bool = False,
        exclude_patterns: list[str] | None = None,
    ):
        """Initialize the file walker."""
        self.root_path = root_path
        self.follow_symlinks = follow_symlinks
        self.exclude_patterns = exclude_patterns or []

        gitignore_patterns = load_gitignore_patterns(root_path)
        self.skip_dirs = SKIP_DIRS | gitignore_patterns

        self.stats = {
            "total_files": 0,
            "text_files": 0,
            "binary_files": 0,
            "large_files": 0,
            "skipped_dirs": 0,
        }

    def detect_monorepo(self) -> tuple[bool, list[Path], list[Path]]:
        """Detect if project is a monorepo and return source directories."""
        monorepo_dirs = []
        monorepo_detected = False

        for base_dir, src_dir in STANDARD_MONOREPO_PATHS:
            base_path = self.root_path / base_dir
            if base_path.exists() and base_path.is_dir():
                if src_dir:
                    src_path = base_path / src_dir
                    if src_path.exists() and src_path.is_dir():
                        monorepo_dirs.append(src_path)
                        monorepo_detected = True
                else:
                    for subdir in base_path.iterdir():
                        if subdir.is_dir() and not subdir.name.startswith("."):
                            src_path = subdir / "src"
                            if src_path.exists() and src_path.is_dir():
                                monorepo_dirs.append(src_path)
                                monorepo_detected = True

        root_entry_files = []
        if monorepo_detected:
            for entry_file in MONOREPO_ENTRY_FILES:
                entry_path = self.root_path / entry_file
                if entry_path.exists() and entry_path.is_file():
                    root_entry_files.append(entry_path)

        return monorepo_detected, monorepo_dirs, root_entry_files

    def process_file(self, file: Path, exclude_file_patterns: list[str]) -> dict[str, Any] | None:
        """Process a single file and return its info."""

        if exclude_file_patterns:
            filename = file.name
            relative_path = file.relative_to(self.root_path).as_posix()
            for pattern in exclude_file_patterns:
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(relative_path, pattern):
                    return None

        try:
            if not self.follow_symlinks and file.is_symlink():
                return None
        except (OSError, PermissionError):
            return None

        try:
            file_size = file.stat().st_size

            if not is_text_file(file):
                self.stats["binary_files"] += 1
                return None

            self.stats["text_files"] += 1

            relative_path = file.relative_to(self.root_path)
            posix_path = relative_path.as_posix()

            first_lines = get_first_lines(file)

            file_info = {
                "path": posix_path,
                "sha256": compute_file_hash(file),
                "ext": file.suffix,
                "bytes": file_size,
                "loc": count_lines_in_file(file),
            }

            if not file.suffix or file.suffix in (".sh", ".bash"):
                if first_lines and _detect_bash_shebang(first_lines[0]):
                    file_info["detected_language"] = "bash"

                    if not file.suffix:
                        file_info["ext"] = ".sh"

            return file_info

        except (FileNotFoundError, PermissionError, UnicodeDecodeError, sqlite3.Error, OSError):
            return None

    def walk(self) -> tuple[list[dict], dict[str, Any]]:
        """Walk directory and collect file information."""
        files = []

        exclude_file_patterns = []
        if self.exclude_patterns:
            for pattern in self.exclude_patterns:
                if pattern.endswith("/**"):
                    self.skip_dirs.add(pattern.removesuffix("/**"))
                elif pattern.endswith("/"):
                    self.skip_dirs.add(pattern.rstrip("/"))
                elif "/" in pattern and "*" not in pattern:
                    self.skip_dirs.add(pattern.split("/")[0])
                else:
                    exclude_file_patterns.append(pattern)

        monorepo_detected, monorepo_dirs, _root_entry_files = self.detect_monorepo()

        if monorepo_detected:
            logger.info(
                f"Monorepo detected ({len(monorepo_dirs)} src directories). Scanning ALL paths."
            )
        else:
            logger.info("Standard project structure detected.")

        for dirpath, dirnames, filenames in os.walk(
            self.root_path, followlinks=self.follow_symlinks
        ):
            skipped_count = len([d for d in dirnames if d in self.skip_dirs])
            self.stats["skipped_dirs"] += skipped_count

            dirnames[:] = [d for d in dirnames if d not in self.skip_dirs]

            current_path = Path(dirpath)
            try:
                if not os.access(dirpath, os.R_OK):
                    continue

                if any(
                    part in [".venv", "venv", "virtualenv"] for part in current_path.parts
                ) and current_path.name in ["lib64", "bin64", "include64"]:
                    dirnames.clear()
                    continue
            except (OSError, PermissionError):
                continue

            for filename in filenames:
                self.stats["total_files"] += 1
                file = Path(dirpath) / filename

                file_info = self.process_file(file, exclude_file_patterns)
                if file_info:
                    files.append(file_info)

        files.sort(key=lambda x: x["path"])

        return files, self.stats
