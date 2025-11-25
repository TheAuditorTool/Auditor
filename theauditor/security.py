"""Security utilities for input sanitization and validation."""


import shlex
import urllib.parse
from pathlib import Path


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


def sanitize_path(path_str: str, project_root: str | None = None) -> Path:
    """
    Sanitize a file path to prevent path traversal attacks.
    
    Args:
        path_str: The path string to sanitize
        project_root: The root directory to restrict paths within (default: current directory)
    
    Returns:
        A resolved Path object that is safe to use
    
    Raises:
        SecurityError: If the path attempts to escape the project root
    """
    if project_root is None:
        project_root = "."
    
    # Resolve both paths to absolute
    root = Path(project_root).resolve()
    
    # Handle relative paths - make them relative to project root
    if not Path(path_str).is_absolute():
        target = (root / path_str).resolve()
    else:
        target = Path(path_str).resolve()
    
    # Check if the resolved path is within the project root
    try:
        # This will raise ValueError if target is not relative to root
        target.relative_to(root)
    except ValueError:
        # Path is outside project root - this is a security violation
        raise SecurityError(f"Path traversal attempt detected: {path_str} resolves outside project root")
    
    return target


def sanitize_shell_arg(arg: str) -> str:
    """
    Sanitize a string for safe use as a shell argument.
    
    Uses shlex.quote to properly escape special characters and prevent command injection.
    
    Args:
        arg: The argument string to sanitize
    
    Returns:
        A properly quoted/escaped string safe for shell use
    """
    # shlex.quote properly escapes shell metacharacters
    return shlex.quote(arg)


def sanitize_url_component(component: str) -> str:
    """
    Sanitize a string for safe use in URL construction.
    
    Properly encodes special characters to prevent URL injection.
    
    Args:
        component: The URL component to sanitize (e.g., package name)
    
    Returns:
        A properly URL-encoded string
    """
    # URL-encode the component to handle special characters safely
    # safe='' means encode everything except alphanumerics
    return urllib.parse.quote(component, safe='')


def validate_package_name(name: str, manager: str) -> bool:
    """
    Validate that a package name follows the expected format for its package manager.
    
    Args:
        name: The package name to validate
        manager: The package manager type ("npm", "py", "docker")
    
    Returns:
        True if the name is valid, False otherwise
    """
    import re
    
    if not name or len(name) > 214:  # npm max length is 214
        return False
    
    if manager == "npm":
        # npm package names: lowercase, alphanumeric, hyphens, underscores, dots
        # Can be scoped: @scope/package
        pattern = r'^(@[a-z0-9][\w.-]*\/)?[a-z0-9][\w.-]*$'
        return bool(re.match(pattern, name))
    
    elif manager == "py":
        # PyPI package names: alphanumeric, hyphens, underscores, dots
        # Case insensitive but typically lowercase
        pattern = r'^[a-zA-Z0-9][\w.-]*$'
        return bool(re.match(pattern, name))
    
    elif manager == "docker":
        # Docker image names: lowercase, alphanumeric, hyphens, underscores, dots, slashes
        # Can include registry and namespace
        pattern = r'^[a-z0-9][\w./:-]*$'
        return bool(re.match(pattern, name))
    
    return False


def sanitize_config_path(config_value: str, config_section: str, config_key: str, project_root: str = ".") -> Path:
    """
    Sanitize a path value from configuration.
    
    This is specifically for paths that come from config files or environment variables,
    which are common sources of tainted input.
    
    Args:
        config_value: The path value from config
        config_section: The config section (e.g., "paths")
        config_key: The config key (e.g., "manifest")
        project_root: The root directory to restrict paths within
    
    Returns:
        A sanitized Path object
    
    Raises:
        SecurityError: If the path is invalid or attempts traversal
    """
    if not config_value:
        raise SecurityError(f"Empty path in config[{config_section}][{config_key}]")
    
    # Special handling for known config paths that should always be under .pf/
    if config_section == "paths" and config_key in ["manifest", "db", "workset", "pf_dir"]:
        # These should always be under .pf/ directory
        if not config_value.startswith("./.pf/") and not config_value.startswith(".pf/"):
            # Force it to be under .pf/ for safety
            config_value = f"./.pf/{Path(config_value).name}"
    
    return sanitize_path(config_value, project_root)