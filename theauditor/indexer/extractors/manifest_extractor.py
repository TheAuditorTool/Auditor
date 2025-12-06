"""Unified manifest extractor for all package manifest file types (Fidelity Protocol Compliant).

Single location for extracting:
- package.json (Node.js)
- pyproject.toml (Python)
- requirements.txt / requirements-*.txt (Python)
- Cargo.toml (Rust)
- go.mod (Go)

All extracted data is normalized into proper junction tables, not JSON blobs.
"""

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken
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

    if spec.startswith("-e "):
        spec = spec[3:].strip()

    if spec.startswith("git+"):
        result["git_url"] = spec
        if "#egg=" in spec:
            egg_part = spec.split("#egg=")[1]
            result["name"] = egg_part.split("&")[0].strip()
        return result

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
        for op in ["===", "==", "!=", "~=", ">=", "<=", ">", "<"]:
            if op in spec:
                parts = spec.split(op, 1)
                result["name"] = parts[0].strip()
                result["version"] = f"{op}{parts[1].strip()}"
                return result

        result["name"] = spec.strip()
        version_part = ""

    if version_part:
        result["version"] = version_part.strip()

    return result


class ManifestExtractor(BaseExtractor):
    """Unified extractor for ALL package manifest file types (Fidelity Protocol Compliant).

    Handles:
    - package.json -> package_configs + package_dependencies + package_scripts + ...
    - pyproject.toml -> python_package_configs + python_package_dependencies + python_build_requires
    - requirements.txt -> python_package_configs + python_package_dependencies
    """

    PACKAGE_JSON = frozenset(["package.json"])
    PYPROJECT = frozenset(["pyproject.toml"])

    def supported_extensions(self) -> list[str]:
        """Return extensions - we use should_extract for name-based matching."""
        return [".json", ".toml", ".txt", ".mod"]

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file."""
        path = Path(file_path)
        file_name = path.name.lower()

        if file_name == "package.json":
            return True

        if file_name == "pyproject.toml":
            return True

        if file_name == "cargo.toml":
            return True

        if file_name == "go.mod":
            return True

        return file_name.startswith("requirements") and path.suffix == ".txt"

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract manifest data and return with fidelity manifest."""
        file_path = str(file_info["path"])
        file_name = Path(file_path).name.lower()

        result: dict[str, Any] = {
            "imports": [],
            "routes": [],
            "sql_queries": [],
            "symbols": [],
            "package_configs": [],
            "package_dependencies": [],
            "package_scripts": [],
            "package_engines": [],
            "package_workspaces": [],
            "python_package_configs": [],
            "python_package_dependencies": [],
            "python_build_requires": [],
            "cargo_package_configs": [],
            "cargo_dependencies": [],
            "go_module_configs": [],
            "go_module_dependencies": [],
        }

        if file_name == "package.json":
            self._extract_package_json(file_path, content, result)
        elif file_name == "pyproject.toml":
            self._extract_pyproject(file_path, content, result)
        elif file_name == "cargo.toml":
            self._extract_cargo_toml(file_path, content, result)
        elif file_name == "go.mod":
            self._extract_go_mod(file_path, content, result)
        elif file_name.startswith("requirements") and file_name.endswith(".txt"):
            self._extract_requirements(file_path, content, result)

        return FidelityToken.attach_manifest(result)

    def _extract_package_json(self, file_path: str, content: str, result: dict[str, Any]) -> None:
        """Extract package.json into result data lists."""
        try:
            pkg_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"[ManifestExtractor] Failed to parse {file_path}: {e}")
            return

        result["package_configs"].append(
            {
                "file_path": file_path,
                "package_name": pkg_data.get("name", "unknown"),
                "version": pkg_data.get("version", "unknown"),
                "is_private": pkg_data.get("private", False),
            }
        )

        deps = pkg_data.get("dependencies") or {}
        for name, version_spec in deps.items():
            result["package_dependencies"].append(
                {
                    "file_path": file_path,
                    "name": name,
                    "version_spec": version_spec,
                    "is_dev": False,
                    "is_peer": False,
                }
            )

        dev_deps = pkg_data.get("devDependencies") or {}
        for name, version_spec in dev_deps.items():
            result["package_dependencies"].append(
                {
                    "file_path": file_path,
                    "name": name,
                    "version_spec": version_spec,
                    "is_dev": True,
                    "is_peer": False,
                }
            )

        peer_deps = pkg_data.get("peerDependencies") or {}
        for name, version_spec in peer_deps.items():
            result["package_dependencies"].append(
                {
                    "file_path": file_path,
                    "name": name,
                    "version_spec": version_spec,
                    "is_dev": False,
                    "is_peer": True,
                }
            )

        scripts = pkg_data.get("scripts") or {}
        for script_name, script_command in scripts.items():
            result["package_scripts"].append(
                {
                    "file_path": file_path,
                    "script_name": script_name,
                    "script_command": script_command,
                }
            )

        engines = pkg_data.get("engines") or {}
        for engine_name, version_spec in engines.items():
            result["package_engines"].append(
                {
                    "file_path": file_path,
                    "engine_name": engine_name,
                    "version_spec": version_spec,
                }
            )

        workspaces = pkg_data.get("workspaces") or []
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])
        for workspace_path in workspaces:
            result["package_workspaces"].append(
                {
                    "file_path": file_path,
                    "workspace_path": workspace_path,
                }
            )

    def _extract_pyproject(self, file_path: str, content: str, result: dict[str, Any]) -> None:
        """Extract pyproject.toml into result data lists."""
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            logger.error(f"[ManifestExtractor] Failed to parse {file_path}: {e}")
            return

        project = data.get("project", {})
        project_name = project.get("name")
        project_version = project.get("version")

        result["python_package_configs"].append(
            {
                "file_path": file_path,
                "file_type": "pyproject",
                "project_name": project_name,
                "project_version": project_version,
            }
        )

        deps_list = project.get("dependencies", [])
        for dep_spec in deps_list:
            dep_info = _parse_python_dep_spec(dep_spec)
            if dep_info["name"]:
                extras_json = json.dumps(dep_info["extras"]) if dep_info["extras"] else None
                result["python_package_dependencies"].append(
                    {
                        "file_path": file_path,
                        "name": dep_info["name"],
                        "version_spec": dep_info["version"] or None,
                        "is_dev": False,
                        "group_name": None,
                        "extras": extras_json,
                        "git_url": dep_info["git_url"] or None,
                    }
                )

        optional_deps = project.get("optional-dependencies", {})
        for group_name, group_deps in optional_deps.items():
            is_dev = group_name.lower() in ("dev", "development", "test", "testing")
            for dep_spec in group_deps:
                dep_info = _parse_python_dep_spec(dep_spec)
                if dep_info["name"]:
                    extras_json = json.dumps(dep_info["extras"]) if dep_info["extras"] else None
                    result["python_package_dependencies"].append(
                        {
                            "file_path": file_path,
                            "name": dep_info["name"],
                            "version_spec": dep_info["version"] or None,
                            "is_dev": is_dev,
                            "group_name": group_name,
                            "extras": extras_json,
                            "git_url": dep_info["git_url"] or None,
                        }
                    )

        build_sys = data.get("build-system", {})
        build_requires = build_sys.get("requires", [])
        for req_spec in build_requires:
            dep_info = _parse_python_dep_spec(req_spec)
            if dep_info["name"]:
                result["python_build_requires"].append(
                    {
                        "file_path": file_path,
                        "name": dep_info["name"],
                        "version_spec": dep_info["version"] or None,
                    }
                )

    def _extract_requirements(self, file_path: str, content: str, result: dict[str, Any]) -> None:
        """Extract requirements.txt into result data lists."""

        result["python_package_configs"].append(
            {
                "file_path": file_path,
                "file_type": "requirements",
                "project_name": None,
                "project_version": None,
            }
        )

        for line in content.splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if line.startswith("-r") or line.startswith("-c"):
                continue

            if "#" in line and not line.startswith("git+"):
                line = line.split("#")[0].strip()

            if not line:
                continue

            dep_info = _parse_python_dep_spec(line)
            if dep_info["name"]:
                extras_json = json.dumps(dep_info["extras"]) if dep_info["extras"] else None
                result["python_package_dependencies"].append(
                    {
                        "file_path": file_path,
                        "name": dep_info["name"],
                        "version_spec": dep_info["version"] or None,
                        "is_dev": False,
                        "group_name": None,
                        "extras": extras_json,
                        "git_url": dep_info["git_url"] or None,
                    }
                )

    def _extract_cargo_toml(self, file_path: str, content: str, result: dict[str, Any]) -> None:
        """Extract Cargo.toml into result data lists."""
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            logger.error(f"[ManifestExtractor] Failed to parse {file_path}: {e}")
            return

        package = data.get("package", {})
        package_name = package.get("name")

        raw_version = package.get("version")
        package_version = "workspace" if isinstance(raw_version, dict) and raw_version.get("workspace") else raw_version

        raw_edition = package.get("edition")
        edition = "workspace" if isinstance(raw_edition, dict) and raw_edition.get("workspace") else raw_edition

        result["cargo_package_configs"].append(
            {
                "file_path": file_path,
                "package_name": package_name,
                "package_version": package_version,
                "edition": edition,
            }
        )

        self._extract_cargo_deps(file_path, data.get("dependencies", {}), False, result)

        self._extract_cargo_deps(file_path, data.get("dev-dependencies", {}), True, result)

        self._extract_cargo_deps(file_path, data.get("build-dependencies", {}), True, result)

    def _extract_cargo_deps(
        self,
        file_path: str,
        deps_dict: dict[str, Any],
        is_dev: bool,
        result: dict[str, Any],
    ) -> None:
        """Extract Cargo dependencies from a section."""
        for name, spec in deps_dict.items():
            if isinstance(spec, str):
                version_spec = spec
                features = None
            elif isinstance(spec, dict):
                version_spec = "workspace" if spec.get("workspace") is True else spec.get("version")
                features_list = spec.get("features", [])
                features = json.dumps(features_list) if features_list else None
            else:
                continue

            result["cargo_dependencies"].append(
                {
                    "file_path": file_path,
                    "name": name,
                    "version_spec": version_spec,
                    "is_dev": is_dev,
                    "features": features,
                }
            )

    def _extract_go_mod(self, file_path: str, content: str, result: dict[str, Any]) -> None:
        """Extract go.mod into result data lists."""

        module_match = re.search(r"^module\s+(\S+)", content, re.MULTILINE)
        module_path = module_match.group(1) if module_match else ""

        go_version_match = re.search(r"^go\s+(\d+\.\d+)", content, re.MULTILINE)
        go_version = go_version_match.group(1) if go_version_match else None

        result["go_module_configs"].append(
            {
                "file_path": file_path,
                "module_path": module_path,
                "go_version": go_version,
            }
        )

        require_block_match = re.search(r"require\s*\((.*?)\)", content, re.DOTALL)
        if require_block_match:
            for line in require_block_match.group(1).strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("//"):
                    self._extract_go_mod_dep(file_path, line, result)

        for match in re.finditer(r"^require\s+([a-zA-Z][\S]*)\s+(v[\S]+)", content, re.MULTILINE):
            result["go_module_dependencies"].append(
                {
                    "file_path": file_path,
                    "module_path": match.group(1),
                    "version": match.group(2),
                    "is_indirect": False,
                }
            )

    def _extract_go_mod_dep(
        self,
        file_path: str,
        line: str,
        result: dict[str, Any],
    ) -> None:
        """Extract a single Go module dependency line."""

        is_indirect = "indirect" in line
        code_part = line.split("//")[0].strip() if "//" in line else line.strip()

        parts = code_part.split()
        if len(parts) >= 2:
            result["go_module_dependencies"].append(
                {
                    "file_path": file_path,
                    "module_path": parts[0],
                    "version": parts[1],
                    "is_indirect": is_indirect,
                }
            )
