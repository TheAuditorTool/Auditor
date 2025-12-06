"""Abstract base class for package manager implementations.

All package managers must inherit from BasePackageManager and implement
the required methods for parsing, version checking, docs fetching, and upgrading.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Dependency:
    """Typed dependency representation with guaranteed structure.

    Eliminates dict key guessing and defensive 'if key in dep' checks.
    Uses slots for memory efficiency.

    Required fields:
        name: Package/module name
        version: Version string (may include operators like ^, ~, >=)
        manager: Manager identifier ('cargo', 'go', 'docker')
        source: Path to manifest file this dependency came from

    Optional fields have sensible defaults for each ecosystem.
    """

    name: str
    version: str
    manager: str
    source: str

    files: list[str] = field(default_factory=list)
    is_dev: bool = False

    features: list[str] = field(default_factory=list)
    kind: str = ""
    is_workspace: bool = False

    is_indirect: bool = False
    module_path: str = ""
    go_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for backward compatibility with dict-based code."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Dependency:
        """Create Dependency from dict for backward compatibility.

        Ignores unknown keys to handle manager-specific fields gracefully.
        """
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            manager=data.get("manager", ""),
            source=data.get("source", ""),
            files=data.get("files", []),
            is_dev=data.get("is_dev", False),
            features=data.get("features", []),
            kind=data.get("kind", ""),
            is_workspace=data.get("is_workspace", False),
            is_indirect=data.get("is_indirect", False),
            module_path=data.get("module_path", ""),
            go_version=data.get("go_version", ""),
        )


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
    def parse_manifest(self, path: Path) -> list[Dependency]:
        """Parse manifest file and return list of Dependency objects.

        Args:
            path: Path to the manifest file

        Returns:
            List of Dependency objects with guaranteed structure.
            All required fields (name, version, manager, source) are always present.
            Optional fields have sensible defaults per ecosystem.
        """
        ...

    @abstractmethod
    async def fetch_latest_async(
        self,
        client: Any,
        dep: Dependency,
        allow_prerelease: bool = False,
    ) -> str | None:
        """Fetch latest version from registry.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency object from parse_manifest()
            allow_prerelease: Include pre-release versions

        Returns:
            Latest version string, or None if not found/error
        """
        ...

    @abstractmethod
    async def fetch_docs_async(
        self,
        client: Any,
        dep: Dependency,
        output_path: Path,
        allowlist: list[str],
    ) -> str:
        """Fetch documentation for a dependency.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency object from parse_manifest()
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
        deps: list[Dependency],
    ) -> int:
        """Upgrade manifest file to latest versions.

        Args:
            path: Path to the manifest file
            latest_info: Dict mapping dep keys to version info dicts
                         Key format: '{manager}:{name}:{current_version}'
                         Value: {'latest': str, 'is_outdated': bool, ...}
            deps: List of Dependency objects from parse_manifest()

        Returns:
            Count of dependencies upgraded
        """
        ...

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<{self.__class__.__name__} manager_name={self.manager_name!r}>"
