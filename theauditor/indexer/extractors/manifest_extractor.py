"""Unified manifest extractor for all package manifest file types.

Single location for extracting:
- package.json (Node.js)
- pyproject.toml (Python)
- requirements.txt / requirements-*.txt (Python)

All extracted data is normalized into proper junction tables, not JSON blobs.
"""

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from . import BaseExtractor


def _parse_python_dep_spec(spec: str) -> dict[str, Any]:
    """Parse a Python dependency specification into components.

    Handles:
    - Simple: requests
    - Versioned: requests>=2.28.0
    - Extras: requests[security,socks]>=2.28.0
    - Git: git+https://github.com/user/repo.git#egg=package
    - Editable: -e ./local/path
    """
    result = {"name": "", "version": "", "extras": [], "git_url": ""}

    # Handle editable installs
    if spec.startswith("-e "):
        spec = spec[3:].strip()

    # Handle git URLs
    if spec.startswith("git+"):
        result["git_url"] = spec
        if "#egg=" in spec:
            egg_part = spec.split("#egg=")[1]
            result["name"] = egg_part.split("&")[0].strip()
        return result

    # Handle extras: package[extra1,extra2]>=version
    if "[" in spec and "]" in spec:
        match = re.match(r"^([a-zA-Z0-9_-]+)\[([^\]]+)\](.*)$", spec)
        if match:
            result["name"] = match.group(1).strip()
            extras_str = match.group(2)
            result["extras"] = [e.strip() for e in extras_str.split(",")]
            version_part = match.group(3).strip()
        else:
            version_part = spec
    else:
        # No extras - parse version operators
        for op in ["===", "==", "!=", "~=", ">=", "<=", ">", "<"]:
            if op in spec:
                parts = spec.split(op, 1)
                result["name"] = parts[0].strip()
                result["version"] = f"{op}{parts[1].strip()}"
                return result

        # No version constraint
        result["name"] = spec.strip()
        version_part = ""

    if version_part:
        result["version"] = version_part.strip()

    return result


class ManifestExtractor(BaseExtractor):
    """Unified extractor for ALL package manifest file types.

    Handles:
    - package.json -> package_configs + package_dependencies + package_scripts + ...
    - pyproject.toml -> python_package_configs + python_package_dependencies + python_build_requires
    - requirements.txt -> python_package_configs + python_package_dependencies
    """

    # Patterns this extractor handles
    PACKAGE_JSON = frozenset(["package.json"])
    PYPROJECT = frozenset(["pyproject.toml"])

    def supported_extensions(self) -> list[str]:
        """Return extensions - we use should_extract for name-based matching."""
        return [".json", ".toml", ".txt"]

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file."""
        path = Path(file_path)
        file_name = path.name.lower()

        # package.json
        if file_name == "package.json":
            return True

        # pyproject.toml
        if file_name == "pyproject.toml":
            return True

        # requirements*.txt
        if file_name.startswith("requirements") and path.suffix == ".txt":
            return True

        return False

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract manifest data directly to database."""
        file_path = str(file_info["path"])
        file_name = Path(file_path).name.lower()

        if file_name == "package.json":
            self._extract_package_json(file_path, content)
        elif file_name == "pyproject.toml":
            self._extract_pyproject(file_path, content)
        elif file_name.startswith("requirements") and file_name.endswith(".txt"):
            self._extract_requirements(file_path, content)

        # Return empty - all data goes directly to database
        return {"imports": [], "routes": [], "sql_queries": [], "symbols": []}

    def _extract_package_json(self, file_path: str, content: str) -> None:
        """Extract package.json to Node.js tables (normalized)."""
        try:
            pkg_data = json.loads(content)
        except json.JSONDecodeError as e:
            # ZERO FALLBACK: Log parse errors visibly
            logger.error(f"[ManifestExtractor] Failed to parse {file_path}: {e}")
            return

        # Main package config
        self.db_manager.add_package_config(
            file_path=file_path,
            package_name=pkg_data.get("name", "unknown"),
            version=pkg_data.get("version", "unknown"),
            is_private=pkg_data.get("private", False),
        )

        # Dependencies
        deps = pkg_data.get("dependencies") or {}
        for name, version_spec in deps.items():
            self.db_manager.add_package_dependency(
                file_path=file_path,
                name=name,
                version_spec=version_spec,
                is_dev=False,
                is_peer=False,
            )

        # Dev dependencies
        dev_deps = pkg_data.get("devDependencies") or {}
        for name, version_spec in dev_deps.items():
            self.db_manager.add_package_dependency(
                file_path=file_path,
                name=name,
                version_spec=version_spec,
                is_dev=True,
                is_peer=False,
            )

        # Peer dependencies
        peer_deps = pkg_data.get("peerDependencies") or {}
        for name, version_spec in peer_deps.items():
            self.db_manager.add_package_dependency(
                file_path=file_path,
                name=name,
                version_spec=version_spec,
                is_dev=False,
                is_peer=True,
            )

        # Scripts
        scripts = pkg_data.get("scripts") or {}
        for script_name, script_command in scripts.items():
            self.db_manager.add_package_script(
                file_path=file_path,
                script_name=script_name,
                script_command=script_command,
            )

        # Engines
        engines = pkg_data.get("engines") or {}
        for engine_name, version_spec in engines.items():
            self.db_manager.add_package_engine(
                file_path=file_path,
                engine_name=engine_name,
                version_spec=version_spec,
            )

        # Workspaces
        workspaces = pkg_data.get("workspaces") or []
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])
        for workspace_path in workspaces:
            self.db_manager.add_package_workspace(
                file_path=file_path,
                workspace_path=workspace_path,
            )

    def _extract_pyproject(self, file_path: str, content: str) -> None:
        """Extract pyproject.toml to Python tables (normalized)."""
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            # ZERO FALLBACK: Log parse errors visibly
            logger.error(f"[ManifestExtractor] Failed to parse {file_path}: {e}")
            return

        project = data.get("project", {})
        project_name = project.get("name")
        project_version = project.get("version")

        # Main package config
        self.db_manager.add_python_package_config(
            file_path=file_path,
            file_type="pyproject",
            project_name=project_name,
            project_version=project_version,
        )

        # Regular dependencies
        deps_list = project.get("dependencies", [])
        for dep_spec in deps_list:
            dep_info = _parse_python_dep_spec(dep_spec)
            if dep_info["name"]:
                extras_json = json.dumps(dep_info["extras"]) if dep_info["extras"] else None
                self.db_manager.add_python_package_dependency(
                    file_path=file_path,
                    name=dep_info["name"],
                    version_spec=dep_info["version"] or None,
                    is_dev=False,
                    group_name=None,
                    extras=extras_json,
                    git_url=dep_info["git_url"] or None,
                )

        # Optional dependencies (grouped)
        optional_deps = project.get("optional-dependencies", {})
        for group_name, group_deps in optional_deps.items():
            is_dev = group_name.lower() in ("dev", "development", "test", "testing")
            for dep_spec in group_deps:
                dep_info = _parse_python_dep_spec(dep_spec)
                if dep_info["name"]:
                    extras_json = json.dumps(dep_info["extras"]) if dep_info["extras"] else None
                    self.db_manager.add_python_package_dependency(
                        file_path=file_path,
                        name=dep_info["name"],
                        version_spec=dep_info["version"] or None,
                        is_dev=is_dev,
                        group_name=group_name,
                        extras=extras_json,
                        git_url=dep_info["git_url"] or None,
                    )

        # Build system requirements
        build_sys = data.get("build-system", {})
        build_requires = build_sys.get("requires", [])
        for req_spec in build_requires:
            dep_info = _parse_python_dep_spec(req_spec)
            if dep_info["name"]:
                self.db_manager.add_python_build_requirement(
                    file_path=file_path,
                    name=dep_info["name"],
                    version_spec=dep_info["version"] or None,
                )

    def _extract_requirements(self, file_path: str, content: str) -> None:
        """Extract requirements.txt to Python tables (normalized)."""
        # Main package config (no project name/version for requirements.txt)
        self.db_manager.add_python_package_config(
            file_path=file_path,
            file_type="requirements",
            project_name=None,
            project_version=None,
        )

        # Parse each line
        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Skip -r and -c includes
            if line.startswith("-r") or line.startswith("-c"):
                continue

            # Remove inline comments (but not in git URLs)
            if "#" in line and not line.startswith("git+"):
                line = line.split("#")[0].strip()

            if not line:
                continue

            dep_info = _parse_python_dep_spec(line)
            if dep_info["name"]:
                extras_json = json.dumps(dep_info["extras"]) if dep_info["extras"] else None
                self.db_manager.add_python_package_dependency(
                    file_path=file_path,
                    name=dep_info["name"],
                    version_spec=dep_info["version"] or None,
                    is_dev=False,
                    group_name=None,
                    extras=extras_json,
                    git_url=dep_info["git_url"] or None,
                )
