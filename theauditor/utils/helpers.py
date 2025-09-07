"""Helper utility functions for TheAuditor."""

import hashlib
import json
from pathlib import Path
from typing import Any


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
    """
    with open(file_path) as f:
        return json.load(f)


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
        # Current format: wrapped with metadata
        return data[key]
    elif isinstance(data, list):
        # Legacy format: flat array (backward compatibility)
        return data
    else:
        # Invalid format - log warning and return empty list
        print(f"[WARNING] Invalid format in {path} - expected dict with '{key}' key or flat list")
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
    
    # Exclude all TheAuditor's own directories
    patterns = [
        "theauditor/**",
        "tests/**",
        "agent_templates/**",
        ".claude/**",
        ".make/**",
        ".venv/**",
        ".venv_wsl/**",
        ".auditor_venv/**",
    ]
    
    # Exclude ALL root-level files to prevent framework/project detection
    # This makes TheAuditor think there's no project at root level
    root_files_to_exclude = [
        "pyproject.toml",
        "pyproject.toml.bak",  # Created by deps --upgrade-all
        "package.json.bak",  # Created by deps --upgrade-all
        "requirements*.txt.bak",  # Created by deps --upgrade-all
        "*.bak",  # Catch any other backup files from deps
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
        "*.md",  # All markdown files at root
        "LICENSE*",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
    ]
    patterns.extend(root_files_to_exclude)
    
    return patterns