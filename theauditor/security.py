"""Security utilities for input sanitization and validation."""

import shlex
import urllib.parse
from pathlib import Path


class SecurityError(Exception):
    """Raised when a security violation is detected."""

    pass


def sanitize_path(path_str: str, project_root: str | None = None) -> Path:
    """Sanitize a file path to prevent path traversal attacks."""
    if project_root is None:
        project_root = "."

    root = Path(project_root).resolve()

    if not Path(path_str).is_absolute():
        target = (root / path_str).resolve()
    else:
        target = Path(path_str).resolve()

    try:
        target.relative_to(root)
    except ValueError as e:
        raise SecurityError(
            f"Path traversal attempt detected: {path_str} resolves outside project root"
        ) from e

    return target


def sanitize_shell_arg(arg: str) -> str:
    """Sanitize a string for safe use as a shell argument."""

    return shlex.quote(arg)


def sanitize_url_component(component: str) -> str:
    """Sanitize a string for safe use in URL construction."""

    return urllib.parse.quote(component, safe="")


def validate_package_name(name: str, manager: str) -> bool:
    """Validate that a package name follows the expected format for its package manager."""
    import re

    if not name or len(name) > 214:
        return False

    if manager == "npm":
        pattern = r"^(@[a-z0-9][\w.-]*\/)?[a-z0-9][\w.-]*$"
        return bool(re.match(pattern, name))

    elif manager == "py":
        pattern = r"^[a-zA-Z0-9][\w.-]*$"
        return bool(re.match(pattern, name))

    elif manager == "docker":
        pattern = r"^[a-z0-9][\w./:-]*$"
        return bool(re.match(pattern, name))

    return False


def sanitize_config_path(
    config_value: str, config_section: str, config_key: str, project_root: str = "."
) -> Path:
    """Sanitize a path value from configuration."""
    if not config_value:
        raise SecurityError(f"Empty path in config[{config_section}][{config_key}]")

    if config_section == "paths" and config_key in ["manifest", "db", "workset", "pf_dir"]:
        if not config_value.startswith("./.pf/") and not config_value.startswith(".pf/"):
            config_value = f"./.pf/{Path(config_value).name}"

    return sanitize_path(config_value, project_root)
