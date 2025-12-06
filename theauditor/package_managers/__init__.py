"""Package managers module - unified interface for dependency management across ecosystems.

Provides a registry pattern for package manager implementations:
- Docker (docker-compose.yml, Dockerfile)
- Cargo (Cargo.toml) - Rust/crates.io
- Go (go.mod) - Go modules/proxy.golang.org

Usage:
    from theauditor.package_managers import get_manager, get_all_managers

    # Get specific manager
    cargo_mgr = get_manager("cargo")
    if cargo_mgr:
        deps = cargo_mgr.parse_manifest(Path("Cargo.toml"))

    # Get all managers
    for mgr in get_all_managers():
        print(f"{mgr.manager_name}: {mgr.file_patterns}")
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Dependency

if TYPE_CHECKING:
    from .base import BasePackageManager


_REGISTRY: dict[str, type[BasePackageManager]] | None = None


_EXACT_FILE_MAP: dict[str, str] = {
    "cargo.toml": "cargo",
    "go.mod": "go",
}


_GLOB_PATTERNS: list[tuple[str, str]] = [
    ("docker-compose*.yml", "docker"),
    ("docker-compose*.yaml", "docker"),
    ("dockerfile*", "docker"),
]


def _init_registry() -> dict[str, type[BasePackageManager]]:
    """Initialize the registry with all package manager implementations."""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY

    from .cargo import CargoPackageManager
    from .docker import DockerPackageManager
    from .go import GoPackageManager

    _REGISTRY = {
        "docker": DockerPackageManager,
        "cargo": CargoPackageManager,
        "go": GoPackageManager,
    }
    return _REGISTRY


def get_manager(manager_name: str) -> BasePackageManager | None:
    """Get package manager instance by name.

    Args:
        manager_name: The manager identifier (e.g., 'cargo', 'go', 'docker')

    Returns:
        Package manager instance or None if not found
    """
    registry = _init_registry()
    cls = registry.get(manager_name.lower())
    return cls() if cls else None


def get_all_managers() -> list[BasePackageManager]:
    """Get all registered package manager instances.

    Returns:
        List of all package manager instances
    """
    registry = _init_registry()
    return [cls() for cls in registry.values()]


def get_manager_for_file(file_path: str) -> BasePackageManager | None:
    """Get the appropriate package manager for a given file.

    Uses O(1) hash lookup for exact matches, O(patterns) for globs.

    Args:
        file_path: Path to a manifest file

    Returns:
        Package manager instance that handles this file type, or None
    """
    file_name = Path(file_path).name.lower()

    if file_name in _EXACT_FILE_MAP:
        return get_manager(_EXACT_FILE_MAP[file_name])

    for pattern, mgr_name in _GLOB_PATTERNS:
        if fnmatch.fnmatch(file_name, pattern):
            return get_manager(mgr_name)

    return None


__all__ = [
    "get_manager",
    "get_all_managers",
    "get_manager_for_file",
    "BasePackageManager",
    "Dependency",
]
