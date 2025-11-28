"""Configuration management for TheAuditor."""

import tomllib
from pathlib import Path


def ensure_mypy_config(pyproject_path: str) -> dict[str, str]:
    """Ensure minimal mypy config exists in pyproject.toml."""
    path = Path(pyproject_path)

    if not path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    if "tool" in data and "mypy" in data["tool"]:
        return {"status": "exists"}

    mypy_block = """

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true"""

    with open(path, "a") as f:
        f.write(mypy_block)

    return {"status": "created"}
