"""Workset resolver - computes target file set from git diff and dependencies."""

import json
import os
import platform
import sqlite3
import subprocess
import tempfile
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

# Windows compatibility
IS_WINDOWS = platform.system() == "Windows"


def normalize_path(path: str) -> str:
    """Normalize path to POSIX style."""
    # Replace backslashes with forward slashes
    path = path.replace("\\", "/")
    # Use Path to properly resolve .. and .
    path = str(Path(path).as_posix())
    # Remove leading ./
    if path.startswith("./"):
        path = path[2:]
    return path


def load_manifest(manifest_path: str) -> dict[str, str]:
    """Load manifest and create path -> sha256 mapping."""
    with open(manifest_path) as f:
        manifest = json.load(f)
    return {item["path"]: item["sha256"] for item in manifest}


def get_git_diff_files(diff_spec: str, root_path: str = ".") -> list[str]:
    """Get list of changed files from git diff."""
    import tempfile
    try:
        # Use temp files to avoid buffer overflow
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt', encoding='utf-8') as stdout_fp, \
             tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt', encoding='utf-8') as stderr_fp:
            
            stdout_path = stdout_fp.name
            stderr_path = stderr_fp.name
            
            result = subprocess.run(
                ["git", "diff", "--name-only"] + diff_spec.split(".."),
                cwd=root_path,
                stdout=stdout_fp,
                stderr=stderr_fp,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
                shell=IS_WINDOWS  # Windows compatibility fix
            )
        
        # Read the outputs back
        with open(stdout_path, 'r', encoding='utf-8') as f:
            stdout_content = f.read()
        with open(stderr_path, 'r', encoding='utf-8') as f:
            stderr_content = f.read()
        
        # Clean up temp files
        os.unlink(stdout_path)
        os.unlink(stderr_path)
        
        files = stdout_content.strip().split("\n") if stdout_content.strip() else []
        return [normalize_path(f) for f in files]
    except subprocess.CalledProcessError as e:
        # Read stderr for error message
        try:
            with open(stderr_path, 'r', encoding='utf-8') as f:
                error_msg = f.read()
        except:
            error_msg = 'git not available'
        finally:
            # Clean up temp files
            if 'stdout_path' in locals() and os.path.exists(stdout_path):
                os.unlink(stdout_path)
            if 'stderr_path' in locals() and os.path.exists(stderr_path):
                os.unlink(stderr_path)
        raise RuntimeError(f"Git diff failed: {error_msg}") from e
    except FileNotFoundError:
        # Clean up temp files if they exist
        if 'stdout_path' in locals() and os.path.exists(stdout_path):
            os.unlink(stdout_path)
        if 'stderr_path' in locals() and os.path.exists(stderr_path):
            os.unlink(stderr_path)
        raise RuntimeError("Git is not available. Use --files instead.") from None


def get_forward_deps(
    conn: sqlite3.Connection, file_path: str, manifest_paths: set[str]
) -> set[str]:
    """Get files that this file imports/uses."""
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM refs WHERE src = ? AND kind = 'from'", (file_path,))

    deps = set()
    for (value,) in cursor.fetchall():
        # Skip certain values that are not paths
        if value in ["{", "}", "(", ")", "*"] or value.startswith("'") and value.endswith("'"):
            continue

        # Skip external packages (starting with @ or no slashes)
        if value.startswith("@"):
            continue

        # Clean up the value - remove quotes if present
        value = value.strip("'\"")

        # Try to resolve the import path
        candidates = []

        # If it's a relative path
        if value.startswith("./") or value.startswith("../"):
            # Resolve relative to file's directory
            file_dir = Path(file_path).parent
            # Use normpath instead of resolve to stay relative
            resolved = os.path.normpath(str(file_dir / value))
            resolved = normalize_path(resolved)

            # Remove any leading path that's outside the repo
            if resolved.startswith(".."):
                continue

            candidates.append(resolved)

            # Try with common extensions
            for ext in [".ts", ".js", ".tsx", ".jsx", ".py"]:
                candidates.append(resolved + ext)
                candidates.append(resolved + "/index" + ext)
        elif "/" in value and not value.startswith("/"):
            # Could be a project path
            candidates.append(normalize_path(value))
            for ext in [".ts", ".js", ".tsx", ".jsx", ".py"]:
                candidates.append(normalize_path(value) + ext)

        # Check if any candidate exists in manifest
        for candidate in candidates:
            if candidate in manifest_paths:
                deps.add(candidate)
                break

    return deps


def get_reverse_deps(
    conn: sqlite3.Connection, file_path: str, manifest_paths: set[str]
) -> set[str]:
    """Get files that import/use this file."""
    cursor = conn.cursor()

    # Find all refs that might point to this file
    deps = set()
    logged_paths = set()  # Track which paths we've already logged errors for

    # Get all 'from' refs
    cursor.execute("SELECT src, value FROM refs WHERE kind = 'from'")

    # Remove extension from target file for matching
    file_path_no_ext = str(Path(file_path).with_suffix(""))

    for src, value in cursor.fetchall():
        if src == file_path:
            continue

        # Clean up the value
        value = value.strip("'\"")

        # Skip non-path values
        if value in ["{", "}", "(", ")", "*"] or value.startswith("@"):
            continue

        # Try to resolve this import from the source file
        if value.startswith("./") or value.startswith("../"):
            # Resolve relative to source file's directory
            src_dir = Path(src).parent
            try:
                resolved = os.path.normpath(str(src_dir / value))
                resolved = normalize_path(resolved)

                # Check if this resolves to our target file
                if resolved in (file_path_no_ext, file_path):
                    deps.add(src)
                    continue

                # Also check with common extensions
                for ext in [".ts", ".js", ".tsx", ".jsx", ".py"]:
                    if resolved + ext == file_path:
                        deps.add(src)
                        break
            except (FileNotFoundError, OSError, ValueError) as e:
                # Log path resolution issue once per file
                if src not in logged_paths:
                    logged_paths.add(src)
                    print(f"Debug: Could not resolve import from {src}: {type(e).__name__}")
                continue

    return deps


def expand_dependencies(
    conn: sqlite3.Connection,
    seed_files: set[str],
    manifest_paths: set[str],
    max_depth: int,
) -> set[str]:
    """Expand file set by following dependencies up to max_depth."""
    if max_depth == 0:
        return seed_files

    expanded = seed_files.copy()
    current_level = seed_files

    for _depth in range(max_depth):
        next_level = set()

        for file_path in current_level:
            # Forward dependencies
            forward = get_forward_deps(conn, file_path, manifest_paths)
            next_level.update(forward - expanded)

            # Reverse dependencies
            reverse = get_reverse_deps(conn, file_path, manifest_paths)
            # Filter to only files in manifest
            reverse = {f for f in reverse if f in manifest_paths}
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
        # Check if file matches any include pattern
        included = any(fnmatch(file_path, pattern) for pattern in include_patterns)

        # Check if file matches any exclude pattern
        excluded = any(fnmatch(file_path, pattern) for pattern in exclude_patterns)

        if included and not excluded:
            filtered.add(file_path)

    return filtered


def compute_workset(
    root_path: str = ".",
    db_path: str = "repo_index.db",
    manifest_path: str = "manifest.json",
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
    # Validate inputs
    if sum([bool(all_files), bool(diff_spec), bool(file_list)]) > 1:
        raise ValueError("Cannot specify multiple input modes (--all, --diff, --files)")
    if not all_files and not diff_spec and not file_list:
        raise ValueError("Must specify either --all, --diff, or --files")

    # Load manifest
    try:
        manifest_mapping = load_manifest(manifest_path)
        manifest_paths = set(manifest_mapping.keys())
    except FileNotFoundError:
        # Check if user is in wrong directory
        cwd = Path.cwd()
        helpful_msg = f"Manifest not found at {manifest_path}. Run 'aud full' first."
        if cwd.name in ["Desktop", "Documents", "Downloads"]:
            helpful_msg += f"\n\nAre you in the right directory? You're in: {cwd}"
            helpful_msg += "\nTry: cd <your-project-folder> then run this command again"
        raise RuntimeError(helpful_msg) from None

    # Connect to database
    if not Path(db_path).exists():
        raise RuntimeError(f"Database not found at {db_path}. Run 'aud full' first.")

    conn = sqlite3.connect(db_path)

    # Get seed files
    seed_files = set()
    seed_mode = None
    seed_value = None

    if all_files:
        seed_mode = "all"
        seed_value = "all_indexed_files"
        # Use all files from manifest
        seed_files = manifest_paths.copy()
        # No dependency expansion needed for all files
        max_depth = 0
    elif diff_spec:
        seed_mode = "diff"
        seed_value = diff_spec
        diff_files = get_git_diff_files(diff_spec, root_path)
        # Filter to files in manifest
        seed_files = {f for f in diff_files if f in manifest_paths}
    else:
        seed_mode = "files"
        seed_value = ",".join(file_list)
        # Normalize and filter to manifest
        seed_files = {normalize_path(f) for f in file_list if normalize_path(f) in manifest_paths}

    # Expand dependencies
    expanded_files = expand_dependencies(conn, seed_files, manifest_paths, max_depth)

    # Apply filters
    filtered_files = apply_glob_filters(
        expanded_files,
        include_patterns or [],
        exclude_patterns or [],
    )

    # Sort for deterministic output
    sorted_files = sorted(filtered_files)

    # Build output
    workset_data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": root_path,
        "seed": {"mode": seed_mode, "value": seed_value},
        "max_depth": max_depth,
        "counts": {
            "seed_files": len(seed_files),
            "expanded_files": len(sorted_files),
        },
        "paths": [{"path": path, "sha256": manifest_mapping[path]} for path in sorted_files],
    }

    # Create output directory if needed
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write output
    with open(output_path, "w") as f:
        json.dump(workset_data, f, indent=2)

    if print_stats:
        include_count = len(include_patterns) if include_patterns else 0
        exclude_count = len(exclude_patterns) if exclude_patterns else 0
        print(
            f"seed={len(seed_files)} expanded={len(sorted_files)} depth={max_depth} include={include_count} exclude={exclude_count}"
        )

    conn.close()

    return {
        "success": True,
        "seed_count": len(seed_files),
        "expanded_count": len(sorted_files),
        "output_path": output_path,
    }
