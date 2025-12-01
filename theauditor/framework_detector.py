"""Framework detection for various languages and ecosystems."""

import glob
import json
import re
from pathlib import Path
from typing import Any

from theauditor.framework_registry import FRAMEWORK_REGISTRY
from theauditor.manifest_parser import ManifestParser
from theauditor.utils.logging import logger
from theauditor.utils.validation_debug import log_validation


class FrameworkDetector:
    """Detects frameworks and libraries used in a project."""

    def __init__(self, project_path: Path, exclude_patterns: list[str] = None):
        """Initialize detector with project path."""
        self.project_path = Path(project_path)
        self.detected_frameworks = []
        self.deps_cache = None
        self.exclude_patterns = exclude_patterns or []

        self._cargo_workspace_cache: dict[str, dict] = {}

    def detect_all(self) -> list[dict[str, Any]]:
        """Detect all frameworks in the project."""
        self.detected_frameworks = []

        self._load_deps_cache()

        self._detect_from_manifests()

        self._detect_from_workspaces()

        manifest_frameworks = {}
        for fw in self.detected_frameworks:
            if fw["source"] != "imports":
                key = (fw["framework"], fw["language"])
                manifest_frameworks[key] = fw["version"]

        self._check_framework_files()

        for fw in self.detected_frameworks:
            if fw["version"] == "unknown" and fw["source"] == "framework_files":
                key = (fw["framework"], fw["language"])

                if key in manifest_frameworks:
                    fw["version"] = manifest_frameworks[key]
                    fw["source"] = f"{fw['source']} (version from manifest)"

                elif self.deps_cache and fw["framework"] in self.deps_cache:
                    cached_dep = self.deps_cache[fw["framework"]]
                    manager = cached_dep.get("manager", "")

                    if (fw["language"] == "python" and manager == "py") or (
                        fw["language"] in ["javascript", "typescript"] and manager == "npm"
                    ):
                        fw["version"] = cached_dep.get("version", "")
                        if fw["version"] != "unknown":
                            fw["source"] = f"{fw['source']} (version from deps cache)"

        seen = {}
        for fw in self.detected_frameworks:
            key = (fw["framework"], fw["language"], fw.get("path", "."))
            if key not in seen or fw["version"] != "unknown" and seen[key]["version"] == "unknown":
                seen[key] = fw

        final_frameworks = list(seen.values())

        validation_frameworks = [
            fw
            for fw in final_frameworks
            if FRAMEWORK_REGISTRY.get(fw["framework"], {}).get("category") == "validation"
        ]
        if validation_frameworks:
            for fw in validation_frameworks:
                log_validation(
                    "L1-DETECT",
                    f"Detected validation framework: {fw['framework']}",
                    {
                        "framework": fw["framework"],
                        "version": fw["version"],
                        "language": fw["language"],
                        "source": fw["source"],
                        "path": fw.get("path", "."),
                    },
                )

        return final_frameworks

    def _detect_from_manifests(self):
        """Unified manifest detection using registry and ManifestParser - now directory-aware."""
        parser = ManifestParser()

        manifest_names = [
            "pyproject.toml",
            "package.json",
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-test.txt",
            "setup.py",
            "setup.cfg",
            "Gemfile",
            "Gemfile.lock",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "composer.json",
        ]

        manifests = {}
        for manifest_name in manifest_names:
            for manifest_path in self.project_path.rglob(manifest_name):
                try:
                    relative_path = manifest_path.relative_to(self.project_path)
                    should_skip = False

                    for part in relative_path.parts[:-1]:
                        if part in [
                            "node_modules",
                            "venv",
                            ".venv",
                            ".auditor_venv",
                            "vendor",
                            "dist",
                            "build",
                            "__pycache__",
                            ".git",
                            ".tox",
                            ".pytest_cache",
                        ]:
                            should_skip = True
                            break

                    if should_skip:
                        continue

                    dir_path = manifest_path.parent.relative_to(self.project_path)
                    dir_str = str(dir_path) if dir_path != Path(".") else "."

                    manifest_key = f"{dir_str}/{manifest_name}" if dir_str != "." else manifest_name
                    manifests[manifest_key] = manifest_path

                except ValueError:
                    continue

        parsed_data = {}
        for manifest_key, path in manifests.items():
            if path.exists():
                try:
                    filename = path.name

                    if filename.endswith(".toml"):
                        parsed_data[manifest_key] = parser.parse_toml(path)
                    elif filename.endswith(".json"):
                        parsed_data[manifest_key] = parser.parse_json(path)
                    elif filename.endswith((".yml", ".yaml")):
                        parsed_data[manifest_key] = parser.parse_yaml(path)
                    elif filename.endswith(".cfg"):
                        parsed_data[manifest_key] = parser.parse_ini(path)
                    elif filename.endswith(".txt"):
                        parsed_data[manifest_key] = parser.parse_requirements_txt(path)
                    elif (
                        filename == "Gemfile"
                        or filename == "Gemfile.lock"
                        or (
                            filename.endswith(".xml")
                            or filename.endswith(".gradle")
                            or filename.endswith(".kts")
                            or filename.endswith(".mod")
                        )
                        or filename == "setup.py"
                    ):
                        with open(path, encoding="utf-8") as f:
                            parsed_data[manifest_key] = f.read()
                except Exception as e:
                    logger.info(f"Warning: Failed to parse {manifest_key}: {e}")

        for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
            for required_manifest_name, search_configs in fw_config.get(
                "detection_sources", {}
            ).items():
                for manifest_key, manifest_data in parsed_data.items():
                    if not manifest_key.endswith(required_manifest_name):
                        continue

                    if "/" in manifest_key:
                        dir_path = "/".join(manifest_key.split("/")[:-1])
                    else:
                        dir_path = "."

                    if search_configs == "line_search":
                        if isinstance(manifest_data, list):
                            for line in manifest_data:
                                version = parser.check_package_in_deps([line], fw_name)
                                if version:
                                    fw_info = {
                                        "framework": fw_name,
                                        "version": version or "unknown",
                                        "language": fw_config["language"],
                                        "path": dir_path,
                                        "source": manifest_key,
                                    }
                                    self.detected_frameworks.append(fw_info)

                                    if fw_config.get("category") == "validation":
                                        log_validation(
                                            "L1-DETECT",
                                            f"Found validation framework: {fw_name}",
                                            {
                                                "framework": fw_name,
                                                "version": version or "unknown",
                                                "source": manifest_key,
                                                "path": dir_path,
                                            },
                                        )
                                    break
                    elif isinstance(manifest_data, str):
                        if fw_name in manifest_data or (
                            fw_config.get("package_pattern")
                            and fw_config["package_pattern"] in manifest_data
                        ):
                            version = "unknown"
                            import re

                            if fw_config.get("package_pattern"):
                                pattern = fw_config["package_pattern"]
                            else:
                                pattern = fw_name

                            version_match = re.search(
                                rf'{re.escape(pattern)}["\']?\s*[,:]?\s*["\']?([\d.]+)',
                                manifest_data,
                            )
                            if not version_match:
                                version_match = re.search(
                                    rf"{re.escape(pattern)}\s+v([\d.]+)", manifest_data
                                )
                            if not version_match:
                                version_match = re.search(
                                    rf'gem\s+["\']?{re.escape(pattern)}["\']?\s*,\s*["\']([\d.]+)["\']',
                                    manifest_data,
                                )

                            if version_match:
                                version = version_match.group(1)

                            self.detected_frameworks.append(
                                {
                                    "framework": fw_name,
                                    "version": version,
                                    "language": fw_config["language"],
                                    "path": dir_path,
                                    "source": manifest_key,
                                }
                            )

                    elif search_configs == "content_search":
                        if isinstance(manifest_data, str):
                            found = False

                            if (
                                fw_config.get("package_pattern")
                                and fw_config["package_pattern"] in manifest_data
                            ):
                                found = True

                            elif fw_config.get("content_patterns"):
                                for pattern in fw_config["content_patterns"]:
                                    if pattern in manifest_data:
                                        found = True
                                        break

                            elif fw_name in manifest_data:
                                found = True

                            if found:
                                version = "unknown"
                                import re

                                pattern = fw_config.get("package_pattern", fw_name)
                                version_match = re.search(
                                    rf"{re.escape(pattern)}.*?[>v]([\d.]+)",
                                    manifest_data,
                                    re.DOTALL,
                                )
                                if version_match:
                                    version = version_match.group(1)

                                self.detected_frameworks.append(
                                    {
                                        "framework": fw_name,
                                        "version": version,
                                        "language": fw_config["language"],
                                        "path": dir_path,
                                        "source": manifest_key,
                                    }
                                )

                    elif search_configs == "exists":
                        self.detected_frameworks.append(
                            {
                                "framework": fw_name,
                                "version": "unknown",
                                "language": fw_config["language"],
                                "path": dir_path,
                                "source": manifest_key,
                            }
                        )

                    else:
                        for key_path in search_configs:
                            deps = parser.extract_nested_value(manifest_data, key_path)
                            if deps:
                                package_name = fw_config.get("package_pattern", fw_name)
                                version = parser.check_package_in_deps(deps, package_name)
                                if version:
                                    if version == "workspace" and manifest_key.endswith(
                                        "Cargo.toml"
                                    ):
                                        manifest_path = manifests.get(manifest_key)
                                        if manifest_path:
                                            version = self._resolve_cargo_workspace_version(
                                                package_name, manifest_path
                                            )
                                    self.detected_frameworks.append(
                                        {
                                            "framework": fw_name,
                                            "version": version,
                                            "language": fw_config["language"],
                                            "path": dir_path,
                                            "source": manifest_key,
                                        }
                                    )
                                    break

    def _detect_from_workspaces(self):
        """Detect frameworks from monorepo workspace packages."""

        package_json = self.project_path / "package.json"
        if not package_json.exists():
            return

        parser = ManifestParser()
        try:
            data = parser.parse_json(package_json)

            workspaces = data.get("workspaces", [])

            if isinstance(workspaces, dict):
                workspaces = workspaces.get("packages", [])

            if workspaces and isinstance(workspaces, list):
                for pattern in workspaces:
                    abs_pattern = str(self.project_path / pattern)

                    if "*" in abs_pattern:
                        matched_paths = glob.glob(abs_pattern)
                        for matched_path in matched_paths:
                            matched_dir = Path(matched_path)
                            if matched_dir.is_dir():
                                workspace_pkg = matched_dir / "package.json"
                                if workspace_pkg.exists():
                                    self._check_workspace_package(workspace_pkg, parser)
                    else:
                        workspace_dir = self.project_path / pattern
                        if workspace_dir.is_dir():
                            workspace_pkg = workspace_dir / "package.json"
                            if workspace_pkg.exists():
                                self._check_workspace_package(workspace_pkg, parser)
        except Exception as e:
            logger.info(f"Warning: Failed to check workspaces: {e}")

    def _check_workspace_package(self, pkg_path: Path, parser: ManifestParser):
        """Check a single workspace package.json for frameworks."""
        try:
            data = parser.parse_json(pkg_path)

            all_deps = {}
            if "dependencies" in data:
                all_deps.update(data["dependencies"])
            if "devDependencies" in data:
                all_deps.update(data["devDependencies"])

            for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
                if fw_config["language"] != "javascript":
                    continue

                package_name = fw_config.get("package_pattern", fw_name)
                if package_name in all_deps:
                    version = all_deps[package_name]

                    version = re.sub(r"^[~^>=<]+", "", str(version)).strip()

                    try:
                        rel_path = pkg_path.parent.relative_to(self.project_path)
                        path = str(rel_path).replace("\\", "/") if rel_path != Path(".") else "."
                        source = str(pkg_path.relative_to(self.project_path)).replace("\\", "/")
                    except ValueError:
                        path = "."
                        source = str(pkg_path)

                    self.detected_frameworks.append(
                        {
                            "framework": fw_name,
                            "version": version,
                            "language": "javascript",
                            "path": path,
                            "source": source,
                        }
                    )
        except Exception as e:
            logger.info(f"Warning: Failed to parse workspace package {pkg_path}: {e}")

        pass

    def _scan_source_imports(self):
        """Scan source files for framework imports."""

        max_files = 100
        files_scanned = 0

        lang_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "javascript",
            ".tsx": "javascript",
            ".go": "go",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".sh": "bash",
            ".bash": "bash",
        }

        for ext, language in lang_extensions.items():
            if files_scanned >= max_files:
                break

            for file_path in self.project_path.rglob(f"*{ext}"):
                if files_scanned >= max_files:
                    break

                if any(
                    part in file_path.parts
                    for part in [
                        "node_modules",
                        "venv",
                        ".venv",
                        ".auditor_venv",
                        "vendor",
                        "dist",
                        "build",
                        "__pycache__",
                        ".git",
                    ]
                ):
                    continue

                relative_path = file_path.relative_to(self.project_path)
                should_skip = False
                for pattern in self.exclude_patterns:
                    if pattern.endswith("/"):
                        dir_pattern = pattern.rstrip("/")
                        if str(relative_path).startswith(dir_pattern + "/") or str(
                            relative_path
                        ).startswith(dir_pattern + "\\"):
                            should_skip = True
                            break

                    elif "*" in pattern:
                        from fnmatch import fnmatch

                        if fnmatch(str(relative_path), pattern):
                            should_skip = True
                            break

                    elif str(relative_path) == pattern:
                        should_skip = True
                        break

                if should_skip:
                    continue

                files_scanned += 1

                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
                        if fw_config["language"] != language:
                            continue

                        if "import_patterns" in fw_config:
                            for import_pattern in fw_config["import_patterns"]:
                                if import_pattern in content:
                                    file_dir = file_path.parent.relative_to(self.project_path)
                                    dir_str = (
                                        str(file_dir).replace("\\", "/")
                                        if file_dir != Path(".")
                                        else "."
                                    )

                                    if not any(
                                        fw["framework"] == fw_name
                                        and fw["language"] == language
                                        and fw.get("path", ".") == dir_str
                                        for fw in self.detected_frameworks
                                    ):
                                        self.detected_frameworks.append(
                                            {
                                                "framework": fw_name,
                                                "version": "unknown",
                                                "language": language,
                                                "path": dir_str,
                                                "source": "imports",
                                            }
                                        )
                                    break

                except Exception:
                    continue

    def _check_framework_files(self):
        """Check for framework-specific files."""

        for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
            if "file_markers" in fw_config:
                for file_marker in fw_config["file_markers"]:
                    if "*" in file_marker:
                        import glob

                        pattern = str(self.project_path / file_marker)
                        if glob.glob(pattern):
                            if not any(
                                fw["framework"] == fw_name
                                and fw["language"] == fw_config["language"]
                                for fw in self.detected_frameworks
                            ):
                                self.detected_frameworks.append(
                                    {
                                        "framework": fw_name,
                                        "version": "unknown",
                                        "language": fw_config["language"],
                                        "path": ".",
                                        "source": "framework_files",
                                    }
                                )
                            break
                    else:
                        if (self.project_path / file_marker).exists():
                            if not any(
                                fw["framework"] == fw_name
                                and fw["language"] == fw_config["language"]
                                for fw in self.detected_frameworks
                            ):
                                self.detected_frameworks.append(
                                    {
                                        "framework": fw_name,
                                        "version": "unknown",
                                        "language": fw_config["language"],
                                        "path": ".",
                                        "source": "framework_files",
                                    }
                                )
                            break

    def _load_deps_cache(self):
        """Load TheAuditor's deps.json if available for version info."""
        deps_file = self.project_path / ".pf" / "deps.json"
        if deps_file.exists():
            try:
                with open(deps_file) as f:
                    data = json.load(f)
                    self.deps_cache = {}

                    deps_list = data if isinstance(data, list) else data.get("dependencies", [])

                    for dep in deps_list:
                        self.deps_cache[dep["name"]] = dep
            except Exception as e:
                logger.info(f"Warning: Could not load deps cache: {e}")
                pass

    def _find_cargo_workspace_root(self, cargo_toml_path: Path) -> Path | None:
        """Find the Cargo workspace root for a given Cargo.toml."""
        parser = ManifestParser()
        current = cargo_toml_path.parent

        while current >= self.project_path:
            candidate = current / "Cargo.toml"
            if candidate.exists() and candidate != cargo_toml_path:
                data = parser.parse_toml(candidate)
                if "workspace" in data:
                    return candidate
            current = current.parent

        data = parser.parse_toml(cargo_toml_path)
        if "workspace" in data:
            return cargo_toml_path

        return None

    def _get_cargo_workspace_deps(self, workspace_root: Path) -> dict:
        """Get workspace dependencies from a Cargo workspace root."""
        cache_key = str(workspace_root)
        if cache_key in self._cargo_workspace_cache:
            return self._cargo_workspace_cache[cache_key]

        parser = ManifestParser()
        cargo_data = parser.parse_cargo_toml(workspace_root)
        ws_deps = cargo_data.get("workspace_dependencies", {})

        self._cargo_workspace_cache[cache_key] = ws_deps
        return ws_deps

    def _resolve_cargo_workspace_version(self, package_name: str, cargo_toml_path: Path) -> str:
        """Resolve a workspace dependency version."""
        workspace_root = self._find_cargo_workspace_root(cargo_toml_path)
        if not workspace_root:
            return "workspace"

        ws_deps = self._get_cargo_workspace_deps(workspace_root)
        return ws_deps.get(package_name, "workspace")

    def format_table(self) -> str:
        """Format detected frameworks as a table."""
        if not self.detected_frameworks:
            return "No frameworks detected."

        lines = []
        lines.append("FRAMEWORK          LANGUAGE      PATH            VERSION          SOURCE")
        lines.append("-" * 80)

        imports_only = []
        for fw in self.detected_frameworks:
            framework = fw["framework"][:18].ljust(18)
            language = fw["language"][:12].ljust(12)
            path = fw.get("path", ".")[:15].ljust(15)
            version = fw["version"][:15].ljust(15)
            source = fw["source"]

            lines.append(f"{framework} {language} {path} {version} {source}")

            if fw["source"] == "imports" and fw["version"] == "unknown":
                imports_only.append(fw["framework"])

        if imports_only:
            lines.append("\n" + "=" * 60)
            lines.append("NOTE: Frameworks marked with 'imports' source were detected from")
            lines.append("import statements in the codebase (possibly test files) but are")
            lines.append("not listed as dependencies. Version shown as 'unknown' because")
            lines.append("they are not in package.json, pyproject.toml, or requirements.txt.")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export detected frameworks to JSON."""
        return json.dumps(self.detected_frameworks, indent=2, sort_keys=True)

    def save_to_file(self, output_path: Path) -> None:
        """Save detected frameworks to a JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_json())

    def detect_test_framework(self) -> dict[str, str]:
        """Detect the test framework used in the project.

        Returns dict with 'name', 'language', and 'cmd' keys.
        Used by FCE to determine how to run tests.
        """
        if not self.detected_frameworks:
            self.detect_all()

        for fw in self.detected_frameworks:
            fw_name = fw["framework"]
            fw_config = FRAMEWORK_REGISTRY.get(fw_name, {})
            if fw_config.get("category") == "test":
                cmd = fw_config.get("command", "")
                # Handle Java build tool variants
                if fw_name == "junit":
                    if (self.project_path / "pom.xml").exists():
                        cmd = fw_config.get("command_maven", "mvn test")
                    elif (self.project_path / "build.gradle").exists() or (
                        self.project_path / "build.gradle.kts"
                    ).exists():
                        cmd = fw_config.get("command_gradle", "gradle test")
                return {"name": fw_name, "language": fw["language"], "cmd": cmd}

        return {"name": "unknown", "language": "unknown", "cmd": ""}
