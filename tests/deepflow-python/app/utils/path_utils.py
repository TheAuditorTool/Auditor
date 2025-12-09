"""Path utilities - HOP 15: Path operations.

Provides path manipulation that does NOT prevent path traversal.
"""

import os


def build_path(base: str, filename: str) -> str:
    """Build file path.

    HOP 15: DOES NOT sanitize path traversal.

    Args:
        base: Base directory path
        filename: Filename (TAINTED - may contain ..)

    Returns:
        Combined path (VULNERABLE to path traversal)
    """
    # VULNERABLE: os.path.join does NOT prevent path traversal
    # If filename starts with / or contains .., it can escape base
    # Example: filename = "../../etc/passwd"
    #          result = "/tmp/uploads/../../etc/passwd"
    #          which resolves to "/etc/passwd"
    return os.path.join(base, filename)


def get_extension(filename: str) -> str:
    """Get file extension.

    Args:
        filename: Filename (TAINTED)

    Returns:
        Extension (still part of TAINTED filename)
    """
    if not filename:
        return ""

    _, ext = os.path.splitext(filename)
    return ext.lower()


def normalize_path(path: str) -> str:
    """Normalize path (DOES NOT prevent traversal).

    This resolves .. and . but does NOT validate against base directory.

    Args:
        path: Path to normalize (TAINTED)

    Returns:
        Normalized path (still VULNERABLE)
    """
    # WARNING: normpath resolves .. but doesn't prevent traversal
    # It just makes the path cleaner
    return os.path.normpath(path)


def safe_join(base: str, *parts: str) -> str:
    """Safely join paths (SAFE VERSION).

    Used to demonstrate sanitized path detection.

    Args:
        base: Base directory (trusted)
        parts: Path parts to join (may be tainted)

    Returns:
        Safe joined path or raises ValueError if traversal detected

    Raises:
        ValueError: If path escapes base directory
    """
    # Join the paths
    path = os.path.join(base, *parts)

    # Resolve to absolute path
    resolved = os.path.realpath(path)
    base_resolved = os.path.realpath(base)

    # SAFE: Check that resolved path starts with base
    if not resolved.startswith(base_resolved + os.sep) and resolved != base_resolved:
        raise ValueError(f"Path traversal detected: {path}")

    return resolved
