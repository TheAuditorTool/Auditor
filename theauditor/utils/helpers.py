"""Helper utility functions for TheAuditor."""

import hashlib
import json
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger


def normalize_path_for_db(file_path: str, project_root: Path | str | None = None) -> str:
    """Normalize a file path for database queries."""

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
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def load_json_file(file_path: str) -> dict[str, Any]:
    """Load and parse a JSON file."""
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


def count_lines_in_file(file_path: Path) -> int:
    """Count number of lines in a text file."""
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def get_self_exclusion_patterns(exclude_self_enabled: bool) -> list[str]:
    """Get exclusion patterns for TheAuditor's own files."""
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
