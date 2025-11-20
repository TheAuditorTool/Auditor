"""Configuration management for TheAuditor."""
from __future__ import annotations


import tomllib
from pathlib import Path


def ensure_mypy_config(pyproject_path: str) -> dict[str, str]:
    """
    Ensure minimal mypy config exists in pyproject.toml.

    Returns:
        {"status": "created"} if config was added
        {"status": "exists"} if config already present
    """
    path = Path(pyproject_path)

    if not path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    # Parse to check if [tool.mypy] exists
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Check if mypy config already exists
    if "tool" in data and "mypy" in data["tool"]:
        return {"status": "exists"}

    # Mypy config to append
    mypy_block = """

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true"""

    # Append to file
    with open(path, "a") as f:
        f.write(mypy_block)

    return {"status": "created"}
