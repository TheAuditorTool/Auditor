"""Helper utility functions for TheAuditor.

IMPORTANT UTILITIES:
- normalize_path_for_db(): Use this for ANY database query involving file paths.
  The database stores Unix-style relative paths (e.g., 'theauditor/cli.py'),
  but users may pass Windows absolute paths (e.g., 'C:\\Users\\...\\cli.py').
  This function normalizes both to match.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from .logger import setup_logger

logger = setup_logger(__name__)


def normalize_path_for_db(file_path: str, project_root: Path | str | None = None) -> str:
    """Normalize a file path for database queries.

    CRITICAL: Use this function before ANY database query that matches file paths.
    The database stores Unix-style relative paths. This function converts Windows
    absolute paths to match.

    Transformations:
    1. Convert backslashes to forward slashes (Windows -> Unix)
    2. Strip project root prefix if provided (absolute -> relative)
    3. Strip leading slashes

    Args:
        file_path: The file path to normalize (can be absolute or relative,
                   Windows or Unix style)
        project_root: Optional project root to strip. If the file_path starts
                      with this root, it will be removed to create a relative path.

    Returns:
        Normalized path suitable for database LIKE queries

    Examples:
        >>> normalize_path_for_db("theauditor\\context\\query.py")
        'theauditor/context/query.py'

        >>> normalize_path_for_db(
        ...     "C:\\Users\\santa\\Desktop\\TheAuditor\\theauditor\\cli.py",
        ...     project_root="C:\\Users\\santa\\Desktop\\TheAuditor"
        ... )
        'theauditor/cli.py'

        >>> normalize_path_for_db("src/auth.ts")
        'src/auth.ts'

    Usage in query.py:
        from theauditor.utils.helpers import normalize_path_for_db

        def get_file_symbols(self, file_path: str, limit: int = 50):
            # ALWAYS normalize before querying!
            normalized = normalize_path_for_db(file_path, self.root_dir)
            cursor.execute("SELECT * FROM symbols WHERE path LIKE ?",
                          (f"%{normalized}",))
    """

    normalized = file_path.replace("\\", "/")

    if project_root is not None:
        root_str = str(project_root).replace("\\", "/")

        root_str = root_str.rstrip("/")

        if normalized.startswith(root_str + "/"):
            normalized = normalized[len(root_str) + 1 :]
        elif normalized.startswith(root_str):
            normalized = normalized[len(root_str) :]

    normalized = normalized.lstrip("/")

    return normalized


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hex digest of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def load_json_file(file_path: str) -> dict[str, Any]:
    """
    Load and parse a JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
        PermissionError: If file cannot be read
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"JSON file not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {file_path}: {e}")
        raise
    except PermissionError:
        logger.error(f"Permission denied reading file: {file_path}")
        raise


def save_json_file(data: dict[str, Any], file_path: str) -> None:
    """
    Save data as JSON to file.

    Args:
        data: Data to save
        file_path: Path to output file
    """
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def count_lines_in_file(file_path: Path) -> int:
    """
    Count number of lines in a text file.

    Args:
        file_path: Path to the file

    Returns:
        Number of lines
    """
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def extract_data_array(data: Any, key: str, path: str) -> list:
    """
    Extract array from potentially wrapped data structure.

    This function provides a standardized way to handle both legacy flat arrays
    and current wrapped object formats that include metadata.

    Args:
        data: The loaded JSON data (could be dict, list, or other)
        key: The key to look for if data is a dictionary
        path: The file path for logging warnings

    Returns:
        The extracted list of items, or empty list if invalid format

    Examples:
        >>> extract_data_array({"results": [1, 2, 3]}, "results", "file.json")
        [1, 2, 3]
        >>> extract_data_array([1, 2, 3], "any_key", "file.json")
        [1, 2, 3]
        >>> extract_data_array("invalid", "key", "file.json")
        []
    """
    if isinstance(data, dict) and key in data:
        return data[key]
    elif isinstance(data, list):
        return data
    else:
        logger.warning(f"Invalid format in {path} - expected dict with '{key}' key or flat list")
        return []


def get_self_exclusion_patterns(exclude_self_enabled: bool) -> list[str]:
    """
    Get exclusion patterns for TheAuditor's own files.

    Centralized function to provide consistent exclusion patterns
    across all commands that support --exclude-self.

    Args:
        exclude_self_enabled: Whether to exclude TheAuditor's own files

    Returns:
        List of exclusion patterns if enabled, empty list otherwise
    """
    if not exclude_self_enabled:
        return []

    patterns = [
        "theauditor/**",
        "tests/**",
        ".make/**",
        ".venv/**",
        ".venv_wsl/**",
        ".auditor_venv/**",
    ]

    root_files_to_exclude = [
        "pyproject.toml",
        "pyproject.toml.bak",
        "package.json.bak",
        "requirements*.txt.bak",
        "*.bak",
        "package-template.json",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.production.yml",
        "setup.py",
        "setup.cfg",
        "MANIFEST.in",
        "requirements*.txt",
        "tox.ini",
        ".dockerignore",
        "*.md",
        "LICENSE*",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
    ]
    patterns.extend(root_files_to_exclude)

    return patterns
