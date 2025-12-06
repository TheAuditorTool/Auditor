"""Workset resolver - computes target file set from git diff and dependencies."""

import json
import os
import platform
import re
import sqlite3
import subprocess
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

IS_WINDOWS = platform.system() == "Windows"


def validate_diff_spec(diff_spec: str) -> list[str]:
    """Validate and parse git diff spec to prevent command injection."""

    if not re.match(r"^[a-zA-Z0-9_\-\./~^]+(\.\.[a-zA-Z0-9_\-\./~^]+)?$", diff_spec):
        raise ValueError(
            f"Invalid diff spec format: {diff_spec}. "
            "Only alphanumeric, dash, underscore, slash, tilde, caret, and '..' allowed."
        )

    parts = diff_spec.split("..", 1) if ".." in diff_spec else [diff_spec]

    return parts


def normalize_path(path: str) -> str:
    """Normalize path to POSIX style."""

    path = path.replace("\\", "/")

    path = str(Path(path).as_posix())

    if path.startswith("./"):
        path = path[2:]
    return path


def load_files_from_db(db_path: str) -> dict[str, str]:
    """Load file paths and hashes from database.

    Args:
        db_path: Path to repo_index.db

    Returns:
        Dict mapping path -> sha256
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT path, sha256 FROM files")
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result


def get_git_diff_files(diff_spec: str, root_path: str = ".") -> list[str]:
    """Get list of changed files from git diff."""
    diff_parts = validate_diff_spec(diff_spec)

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"] + diff_parts,
            cwd=root_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return [normalize_path(f) for f in files]
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else "git command failed"
        raise RuntimeError(f"Git diff failed: {error_msg}") from e
    except FileNotFoundError:
        raise RuntimeError("Git is not available. Use --files instead.") from None


IMPORT_EXTENSIONS = (".ts", ".js", ".tsx", ".jsx", ".py")


def _resolve_import_to_file(
    src_file: str, import_value: str, manifest_paths: set[str]
) -> str | None:
    """Resolve an import statement to an actual file path.

    Args:
        src_file: The file containing the import
        import_value: The raw import string (e.g., './utils', '../lib/foo')
        manifest_paths: Set of known file paths in the repo

    Returns:
        Resolved file path if found, None otherwise
    """
    value = import_value.strip("'\"")

    if value in ["{", "}", "(", ")", "*"] or value.startswith("@"):
        return None

    candidates = []

    if value.startswith("./") or value.startswith("../"):
        src_dir = Path(src_file).parent
        resolved = normalize_path(os.path.normpath(str(src_dir / value)))

        if resolved.startswith(".."):
            return None

        candidates.append(resolved)
        for ext in IMPORT_EXTENSIONS:
            candidates.append(resolved + ext)
            candidates.append(resolved + "/index" + ext)

    elif "/" in value and not value.startswith("/"):
        normalized = normalize_path(value)
        candidates.append(normalized)
        for ext in IMPORT_EXTENSIONS:
            candidates.append(normalized + ext)

    for candidate in candidates:
        if candidate in manifest_paths:
            return candidate

    return None


def _build_dependency_maps(
    conn: sqlite3.Connection, manifest_paths: set[str]
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build forward and reverse dependency maps from refs table.

    PERFORMANCE: Loads entire refs table ONCE instead of N queries per file.
    This is O(1) DB queries instead of O(N * depth) where N = number of files.

    Args:
        conn: Database connection
        manifest_paths: Set of known file paths

    Returns:
        Tuple of (forward_deps, reverse_deps) where:
        - forward_deps[file] = set of files that `file` imports
        - reverse_deps[file] = set of files that import `file`
    """
    cursor = conn.cursor()
    cursor.execute("SELECT src, value FROM refs WHERE kind = 'from'")
    all_refs = cursor.fetchall()

    forward_deps: dict[str, set[str]] = {}
    reverse_deps: dict[str, set[str]] = {}

    for src, import_value in all_refs:
        if src not in manifest_paths:
            continue

        resolved = _resolve_import_to_file(src, import_value, manifest_paths)
        if resolved is None:
            continue

        if src not in forward_deps:
            forward_deps[src] = set()
        forward_deps[src].add(resolved)

        if resolved not in reverse_deps:
            reverse_deps[resolved] = set()
        reverse_deps[resolved].add(src)

    return forward_deps, reverse_deps


def expand_dependencies(
    conn: sqlite3.Connection,
    seed_files: set[str],
    manifest_paths: set[str],
    max_depth: int,
) -> set[str]:
    """Expand file set by following dependencies up to max_depth.

    PERFORMANCE: Uses cached dependency maps (single DB query) instead of
    per-file queries. Reduces O(N * depth) queries to O(1).
    """
    if max_depth == 0:
        return seed_files

    forward_deps, reverse_deps = _build_dependency_maps(conn, manifest_paths)

    expanded = seed_files.copy()
    current_level = seed_files

    for _depth in range(max_depth):
        next_level = set()

        for file_path in current_level:
            forward = forward_deps.get(file_path, set())
            next_level.update(forward - expanded)

            reverse = reverse_deps.get(file_path, set())
            next_level.update(reverse - expanded)

        if not next_level:
            break

        expanded.update(next_level)
        current_level = next_level

    return expanded


def apply_glob_filters(
    files: set[str],
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> set[str]:
    """Apply include/exclude glob patterns to file set."""
    if not include_patterns:
        include_patterns = ["**"]

    filtered = set()
    for file_path in files:
        included = any(fnmatch(file_path, pattern) for pattern in include_patterns)

        excluded = any(fnmatch(file_path, pattern) for pattern in exclude_patterns)

        if included and not excluded:
            filtered.add(file_path)

    return filtered


def compute_workset(
    root_path: str = ".",
    db_path: str = "repo_index.db",
    all_files: bool = False,
    diff_spec: str = None,
    file_list: list[str] = None,
    include_patterns: list[str] = None,
    exclude_patterns: list[str] = None,
    max_depth: int = 2,
    output_path: str = "./.pf/workset.json",
    print_stats: bool = False,
) -> dict[str, Any]:
    """Compute workset from git diff, file list, or all files."""

    if sum([bool(all_files), bool(diff_spec), bool(file_list)]) > 1:
        raise ValueError("Cannot specify multiple input modes (--all, --diff, --files)")
    if not all_files and not diff_spec and not file_list:
        raise ValueError("Must specify either --all, --diff, or --files")

    try:
        file_mapping = load_files_from_db(db_path)
        indexed_paths = set(file_mapping.keys())
    except FileNotFoundError:
        cwd = Path.cwd()
        helpful_msg = f"Database not found at {db_path}. Run 'aud full' first."
        if cwd.name in ["Desktop", "Documents", "Downloads"]:
            helpful_msg += f"\n\nAre you in the right directory? You're in: {cwd}"
            helpful_msg += "\nTry: cd <your-project-folder> then run this command again"
        raise RuntimeError(helpful_msg) from None

    conn = sqlite3.connect(db_path)

    seed_files = set()
    seed_mode = None
    seed_value = None

    if all_files:
        seed_mode = "all"
        seed_value = "all_indexed_files"

        seed_files = indexed_paths.copy()

        max_depth = 0
    elif diff_spec:
        seed_mode = "diff"
        seed_value = diff_spec
        diff_files = get_git_diff_files(diff_spec, root_path)

        seed_files = {f for f in diff_files if f in indexed_paths}
    else:
        seed_mode = "files"
        seed_value = ",".join(file_list)

        seed_files = {normalize_path(f) for f in file_list if normalize_path(f) in indexed_paths}

    expanded_files = expand_dependencies(conn, seed_files, indexed_paths, max_depth)

    filtered_files = apply_glob_filters(
        expanded_files,
        include_patterns or [],
        exclude_patterns or [],
    )

    sorted_files = sorted(filtered_files)

    workset_data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": root_path,
        "seed": {"mode": seed_mode, "value": seed_value},
        "max_depth": max_depth,
        "counts": {
            "seed_files": len(seed_files),
            "expanded_files": len(sorted_files),
        },
        "paths": [{"path": path, "sha256": file_mapping[path]} for path in sorted_files],
    }

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(workset_data, f, indent=2)

    if print_stats:
        include_count = len(include_patterns) if include_patterns else 0
        exclude_count = len(exclude_patterns) if exclude_patterns else 0
        logger.info(
            f"seed={len(seed_files)} expanded={len(sorted_files)} depth={max_depth} include={include_count} exclude={exclude_count}"
        )

    conn.close()

    return {
        "success": True,
        "seed_count": len(seed_files),
        "expanded_count": len(sorted_files),
        "output_path": output_path,
    }
