"""Abstract base class for package manager implementations.

All package managers must inherit from BasePackageManager and implement
the required methods for parsing, version checking, docs fetching, and upgrading.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BasePackageManager(ABC):
    """Abstract base class for all package manager implementations.

    Implementations must provide:
    - manager_name: Identifier for this manager (e.g., 'cargo', 'go', 'docker')
    - file_patterns: Glob patterns for manifest files this manager handles
    - parse_manifest(): Parse manifest file and return dependencies
    - fetch_latest_async(): Fetch latest version from registry
    - fetch_docs_async(): Fetch documentation for a dependency
    - upgrade_file(): Upgrade manifest file to latest versions
    """

    @property
    @abstractmethod
    def manager_name(self) -> str:
        """Return manager identifier (e.g., 'cargo', 'go', 'docker')."""
        ...

    @property
    @abstractmethod
    def file_patterns(self) -> list[str]:
        """Return glob patterns for manifest files (e.g., ['Cargo.toml']).

        Patterns should be file names or glob patterns that this manager handles.
        Examples:
        - ['Cargo.toml'] for Cargo
        - ['go.mod'] for Go
        - ['docker-compose*.yml', 'Dockerfile*'] for Docker
        """
        ...

    @property
    def registry_url(self) -> str | None:
        """Return base URL for the package registry (optional).

        Examples:
        - 'https://crates.io/api/v1/crates/' for Cargo
        - 'https://proxy.golang.org/' for Go
        - None for Docker (uses Docker Hub API)
        """
        return None

    @abstractmethod
    def parse_manifest(self, path: Path) -> list[dict[str, Any]]:
        """Parse manifest file and return list of dependency dicts.

        Args:
            path: Path to the manifest file

        Returns:
            List of dependency dicts with at minimum:
            - name: Dependency name
            - version: Current version string
            - manager: Manager name (e.g., 'cargo')
            - source: Path to source file

            Additional fields vary by manager (e.g., is_dev, features, etc.)
        """
        ...

    @abstractmethod
    async def fetch_latest_async(
        self,
        client: Any,  # httpx.AsyncClient
        dep: dict[str, Any],
    ) -> str | None:
        """Fetch latest version from registry.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency dict from parse_manifest()

        Returns:
            Latest version string, or None if not found/error
        """
        ...

    @abstractmethod
    async def fetch_docs_async(
        self,
        client: Any,  # httpx.AsyncClient
        dep: dict[str, Any],
        output_path: Path,
        allowlist: list[str],
    ) -> str:
        """Fetch documentation for a dependency.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency dict from parse_manifest()
            output_path: Directory to write documentation to
            allowlist: List of package names to fetch (empty = all)

        Returns:
            Status string: 'fetched', 'cached', 'skipped', or 'error'
        """
        ...

    @abstractmethod
    def upgrade_file(
        self,
        path: Path,
        latest_info: dict[str, dict[str, Any]],
        deps: list[dict[str, Any]],
    ) -> int:
        """Upgrade manifest file to latest versions.

        Args:
            path: Path to the manifest file
            latest_info: Dict mapping dep keys to version info dicts
                         Key format: '{manager}:{name}:{current_version}'
                         Value: {'latest': str, 'is_outdated': bool, ...}
            deps: List of dependency dicts from parse_manifest()

        Returns:
            Count of dependencies upgraded
        """
        ...

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<{self.__class__.__name__} manager_name={self.manager_name!r}>"
