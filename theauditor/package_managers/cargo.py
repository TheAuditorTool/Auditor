"""Cargo package manager implementation for Rust.

Handles Cargo.toml files for:
- Parsing dependencies
- Fetching latest versions from crates.io
- Fetching documentation from crates.io / GitHub
- Upgrading Cargo.toml versions
"""

from __future__ import annotations

import platform
import re
from pathlib import Path
from typing import Any

from theauditor import __version__
from theauditor.pipeline.ui import console
from theauditor.utils.logging import logger
from theauditor.utils.rate_limiter import get_rate_limiter

from .base import BasePackageManager, Dependency

IS_WINDOWS = platform.system() == "Windows"


def _clean_version(version_spec: str) -> str:
    """Clean version specification to get actual version."""
    version = re.sub(r"^[><=~!^]+", "", version_spec)
    if " " in version:
        version = version.split()[0]
    return version.strip()


class CargoPackageManager(BasePackageManager):
    """Cargo package manager for Rust Cargo.toml files."""

    @property
    def manager_name(self) -> str:
        return "cargo"

    @property
    def file_patterns(self) -> list[str]:
        return ["Cargo.toml"]

    @property
    def registry_url(self) -> str | None:
        return "https://crates.io/api/v1/crates/"

    def parse_manifest(self, path: Path) -> list[Dependency]:
        """Parse Cargo.toml file for dependencies.

        Args:
            path: Path to Cargo.toml file

        Returns:
            List of Dependency objects with guaranteed structure.
        """
        import tomllib

        deps: list[Dependency] = []

        with open(path, "rb") as f:
            data = tomllib.load(f)

        deps.extend(
            self._parse_cargo_deps(
                data.get("dependencies", {}),
                kind="normal",
                source=str(path),
            )
        )

        deps.extend(
            self._parse_cargo_deps(
                data.get("dev-dependencies", {}),
                kind="dev",
                source=str(path),
            )
        )

        deps.extend(
            self._parse_cargo_deps(
                data.get("build-dependencies", {}),
                kind="build",
                source=str(path),
            )
        )

        return deps

    def _parse_cargo_deps(
        self,
        deps_dict: dict[str, Any],
        kind: str,
        source: str,
    ) -> list[Dependency]:
        """Parse a Cargo.toml dependency section."""
        deps: list[Dependency] = []

        for name, spec in deps_dict.items():
            if isinstance(spec, str):
                version = _clean_version(spec)
                features: list[str] = []
                is_workspace = False
            elif isinstance(spec, dict):
                if spec.get("workspace") is True:
                    is_workspace = True
                    version = "workspace"
                    features = spec.get("features", [])
                else:
                    version = _clean_version(spec.get("version", "*"))
                    features = spec.get("features", [])
                    is_workspace = False
            else:
                continue

            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    manager="cargo",
                    source=source,
                    features=features,
                    kind=kind,
                    is_dev=kind == "dev",
                    is_workspace=is_workspace,
                )
            )

        return deps

    async def fetch_latest_async(
        self,
        client: Any,
        dep: Dependency,
        allow_prerelease: bool = False,
    ) -> str | None:
        """Fetch latest crate version from crates.io.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency object
            allow_prerelease: Include pre-release versions

        Returns:
            Latest version string or None
        """

        if dep.is_workspace:
            return None

        limiter = get_rate_limiter("cargo")
        await limiter.acquire()

        url = f"https://crates.io/api/v1/crates/{dep.name}"
        headers = {"User-Agent": f"TheAuditor/{__version__} (dependency checker)"}
        response = await client.get(url, headers=headers, timeout=10.0)

        if response.status_code != 200:
            return None

        data = response.json()
        crate_data = data.get("crate", {})

        if allow_prerelease:
            return crate_data.get("newest_version")
        return crate_data.get("max_version")

    async def fetch_docs_async(
        self,
        client: Any,
        dep: Dependency,
        output_path: Path,
        allowlist: list[str],
    ) -> str:
        """Fetch crate documentation from crates.io API, then GitHub if needed.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency object
            output_path: Directory to write documentation to
            allowlist: List of package names to fetch (empty = all)

        Returns:
            Status: 'fetched', 'cached', 'skipped', or 'error'
        """
        name = dep.name

        if allowlist and name not in allowlist:
            return "skipped"

        doc_file = output_path / f"{name}.md"
        if doc_file.exists():
            return "cached"

        limiter = get_rate_limiter("cargo")
        await limiter.acquire()

        try:
            url = f"https://crates.io/api/v1/crates/{name}"
            headers = {"User-Agent": f"TheAuditor/{__version__} (dependency docs fetcher)"}
            response = await client.get(url, headers=headers, timeout=10.0)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch docs for {name}: HTTP {response.status_code}")
                return "error"

            data = response.json()
            crate_data = data.get("crate", {})
            readme = crate_data.get("readme")

            if readme:
                output_path.mkdir(parents=True, exist_ok=True)
                doc_file.write_text(readme, encoding="utf-8")
                return "fetched"

            repository = crate_data.get("repository", "")
            if repository and "github.com" in repository:
                github_readme = await self._fetch_github_readme(client, repository)
                if github_readme:
                    output_path.mkdir(parents=True, exist_ok=True)
                    doc_file.write_text(github_readme, encoding="utf-8")
                    return "fetched"

            logger.info(f"No README available for {name}")
            return "skipped"

        except Exception as e:
            logger.warning(f"Failed to fetch docs for {name}: {e}")
            return "error"

    async def _fetch_github_readme(
        self,
        client: Any,
        repository_url: str,
    ) -> str | None:
        """Fetch README from GitHub repository.

        Args:
            client: httpx.AsyncClient instance
            repository_url: GitHub repository URL

        Returns:
            README content or None
        """

        match = re.search(r"github\.com[:/]([^/]+)/([^/\s.]+)", repository_url)
        if not match:
            return None

        owner = match.group(1)
        repo = match.group(2).rstrip(".git")

        limiter = get_rate_limiter("github")
        await limiter.acquire()

        for readme_name in ["README.md", "readme.md", "Readme.md", "README.rst", "README"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{readme_name}"
            response = await client.get(url, timeout=10.0, follow_redirects=True)

            if response.status_code == 200:
                return response.text

        return None

    def upgrade_file(
        self,
        path: Path,
        latest_info: dict[str, dict[str, Any]],
        deps: list[Dependency],
    ) -> int:
        """Upgrade Cargo.toml to latest versions using regex.

        Note: Caller is responsible for creating backup before calling.

        Args:
            path: Path to Cargo.toml
            latest_info: Dict mapping dep keys to version info
            deps: List of Dependency objects

        Returns:
            Count of dependencies upgraded
        """
        content = path.read_text(encoding="utf-8")
        original = content
        count = 0
        upgraded = {}

        for dep in deps:
            if dep.source != str(path):
                continue

            if dep.is_workspace:
                continue

            key = f"cargo:{dep.name}:{dep.version}"
            info = latest_info.get(key)
            if not info or not info.get("latest") or not info.get("is_outdated"):
                continue

            old_version = dep.version
            new_version = info["latest"]
            name = dep.name

            pattern1 = rf'({re.escape(name)}\s*=\s*")({re.escape(old_version)})(")'
            if re.search(pattern1, content):
                content = re.sub(pattern1, rf"\g<1>{new_version}\g<3>", content)
                upgraded[name] = (old_version, new_version)
                count += 1
                continue

            pattern2 = (
                rf'({re.escape(name)}\s*=\s*\{{[^}}]*version\s*=\s*")({re.escape(old_version)})(")'
            )
            if re.search(pattern2, content):
                content = re.sub(pattern2, rf"\g<1>{new_version}\g<3>", content)
                upgraded[name] = (old_version, new_version)
                count += 1

        if content != original:
            path.write_text(content, encoding="utf-8")

        check_mark = "[OK]" if IS_WINDOWS else "[OK]"
        arrow = "->" if IS_WINDOWS else "->"
        for name, (old_ver, new_ver) in upgraded.items():
            console.print(f"  {check_mark} {name}: {old_ver} {arrow} {new_ver}", highlight=False)

        return count
