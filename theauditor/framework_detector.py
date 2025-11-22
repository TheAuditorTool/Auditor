"""Framework detection for various languages and ecosystems."""


import json
import re
import glob
from pathlib import Path
from typing import Any
from theauditor.manifest_parser import ManifestParser
from theauditor.framework_registry import FRAMEWORK_REGISTRY
from theauditor.utils.validation_debug import log_validation


class FrameworkDetector:
    """Detects frameworks and libraries used in a project."""
    
    # Note: Framework detection now uses the centralized FRAMEWORK_REGISTRY
    # from framework_registry.py instead of the old FRAMEWORK_SIGNATURES

    def __init__(self, project_path: Path, exclude_patterns: list[str] = None):
        """Initialize detector with project path.

        Args:
            project_path: Root directory of the project.
            exclude_patterns: List of patterns to exclude from scanning.
        """
        self.project_path = Path(project_path)
        self.detected_frameworks = []
        self.deps_cache = None
        self.exclude_patterns = exclude_patterns or []

    def detect_all(self) -> list[dict[str, Any]]:
        """Detect all frameworks in the project.

        Returns:
            List of detected framework info dictionaries.
        """
        self.detected_frameworks = []

        # Load TheAuditor's deps.json if available for better version info
        self._load_deps_cache()

        # Use unified manifest detection
        self._detect_from_manifests()
        
        # Also detect from monorepo workspaces (keep existing logic)
        self._detect_from_workspaces()

        # Store frameworks found in manifests for version lookup
        manifest_frameworks = {}
        for fw in self.detected_frameworks:
            if fw["source"] != "imports":
                key = (fw["framework"], fw["language"])
                manifest_frameworks[key] = fw["version"]

        # DISABLED: Import scanning causes too many false positives
        # It detects framework names in strings, comments, and detection code itself
        # Real dependencies should be in manifest files (package.json, requirements.txt, etc.)
        # self._scan_source_imports()

        # Check for framework-specific files
        self._check_framework_files()

        # Update versions for frameworks detected from framework files only (imports disabled)
        for fw in self.detected_frameworks:
            if fw["version"] == "unknown" and fw["source"] == "framework_files":
                key = (fw["framework"], fw["language"])
                # First try manifest frameworks
                if key in manifest_frameworks:
                    fw["version"] = manifest_frameworks[key]
                    fw["source"] = f"{fw['source']} (version from manifest)"
                # Then try deps cache
                elif self.deps_cache and fw["framework"] in self.deps_cache:
                    cached_dep = self.deps_cache[fw["framework"]]
                    manager = cached_dep.get("manager", "")
                    # Match language to manager (py -> python, npm -> javascript)
                    if (fw["language"] == "python" and manager == "py") or \
                       (fw["language"] in ["javascript", "typescript"] and manager == "npm"):
                        fw["version"] = cached_dep.get("version", "")  # Empty not unknown
                        if fw["version"] != "unknown":
                            fw["source"] = f"{fw['source']} (version from deps cache)"

        # Deduplicate results, preferring entries with known versions
        # Now we keep framework+language+path as unique key to support monorepos
        seen = {}
        for fw in self.detected_frameworks:
            key = (fw["framework"], fw["language"], fw.get("path", "."))
            if key not in seen:
                seen[key] = fw
            elif fw["version"] != "unknown" and seen[key]["version"] == "unknown":
                # Replace with version that has a known version
                seen[key] = fw

        final_frameworks = list(seen.values())

        # Debug logging for validation frameworks (after deduplication)
        validation_frameworks = [
            fw for fw in final_frameworks
            if FRAMEWORK_REGISTRY.get(fw["framework"], {}).get("category") == "validation"
        ]
        if validation_frameworks:
            for fw in validation_frameworks:
                log_validation("L1-DETECT", f"Detected validation framework: {fw['framework']}", {
                    "framework": fw["framework"],
                    "version": fw["version"],
                    "language": fw["language"],
                    "source": fw["source"],
                    "path": fw.get("path", ".")
                })

        return final_frameworks

    def _detect_from_manifests(self):
        """Unified manifest detection using registry and ManifestParser - now directory-aware."""
        parser = ManifestParser()
        
        # Manifest file names to search for
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
        
        # Recursively find all manifest files in the project
        manifests = {}
        for manifest_name in manifest_names:
            # Use rglob to find all instances of this manifest file
            for manifest_path in self.project_path.rglob(manifest_name):
                # Skip excluded directories
                try:
                    relative_path = manifest_path.relative_to(self.project_path)
                    should_skip = False
                    
                    # Check common skip directories
                    for part in relative_path.parts[:-1]:  # Don't check the filename itself
                        if part in ["node_modules", "venv", ".venv", ".auditor_venv", "vendor", 
                                   "dist", "build", "__pycache__", ".git", ".tox", ".pytest_cache"]:
                            should_skip = True
                            break
                    
                    if should_skip:
                        continue
                    
                    # Calculate the directory path relative to project root
                    dir_path = manifest_path.parent.relative_to(self.project_path)
                    dir_str = str(dir_path) if dir_path != Path('.') else '.'
                    
                    # Create a unique key for this manifest
                    manifest_key = f"{dir_str}/{manifest_name}" if dir_str != '.' else manifest_name
                    manifests[manifest_key] = manifest_path
                    
                except ValueError:
                    # File is outside project path somehow, skip it
                    continue
        
        # Parse each manifest that exists
        parsed_data = {}
        for manifest_key, path in manifests.items():
            if path.exists():
                try:
                    # Extract just the filename for parsing logic
                    filename = path.name
                    
                    if filename.endswith('.toml'):
                        parsed_data[manifest_key] = parser.parse_toml(path)
                    elif filename.endswith('.json'):
                        parsed_data[manifest_key] = parser.parse_json(path)
                    elif filename.endswith(('.yml', '.yaml')):
                        parsed_data[manifest_key] = parser.parse_yaml(path)
                    elif filename.endswith('.cfg'):
                        parsed_data[manifest_key] = parser.parse_ini(path)
                    elif filename.endswith('.txt'):
                        parsed_data[manifest_key] = parser.parse_requirements_txt(path)
                    elif filename == 'Gemfile' or filename == 'Gemfile.lock':
                        # Parse Gemfile as text for now
                        with open(path, encoding='utf-8') as f:
                            parsed_data[manifest_key] = f.read()
                    elif filename.endswith('.xml') or filename.endswith('.gradle') or filename.endswith('.kts') or filename.endswith('.mod'):
                        # Parse as text content for now
                        with open(path, encoding='utf-8') as f:
                            parsed_data[manifest_key] = f.read()
                    elif filename == 'setup.py':
                        with open(path, encoding='utf-8') as f:
                            parsed_data[manifest_key] = f.read()
                except Exception as e:
                    print(f"Warning: Failed to parse {manifest_key}: {e}")
        
        # Check each framework against all manifests
        for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
            for required_manifest_name, search_configs in fw_config.get("detection_sources", {}).items():
                # Check all parsed manifests that match this manifest type
                for manifest_key, manifest_data in parsed_data.items():
                    # Check if this manifest matches the required type
                    if not manifest_key.endswith(required_manifest_name):
                        continue
                    
                    # Extract the directory path from the manifest key
                    if '/' in manifest_key:
                        dir_path = '/'.join(manifest_key.split('/')[:-1])
                    else:
                        dir_path = '.'
                    
                    if search_configs == "line_search":
                        # Simple text search for requirements.txt style or Gemfile
                        if isinstance(manifest_data, list):
                            # Requirements.txt parsed as list
                            for line in manifest_data:
                                version = parser.check_package_in_deps([line], fw_name)
                                if version:
                                    fw_info = {
                                        "framework": fw_name,
                                        "version": version or "unknown",
                                        "language": fw_config["language"],
                                        "path": dir_path,
                                        "source": manifest_key
                                    }
                                    self.detected_frameworks.append(fw_info)

                                    # Debug logging for validation frameworks
                                    if fw_config.get("category") == "validation":
                                        log_validation("L1-DETECT", f"Found validation framework: {fw_name}", {
                                            "framework": fw_name,
                                            "version": version or "unknown",
                                            "source": manifest_key,
                                            "path": dir_path
                                        })
                                    break
                    elif isinstance(manifest_data, str):
                        # Text file content
                        if fw_name in manifest_data or (fw_config.get("package_pattern") and fw_config["package_pattern"] in manifest_data):
                            # Try to extract version
                            version = "unknown"
                            import re
                            if fw_config.get("package_pattern"):
                                pattern = fw_config["package_pattern"]
                            else:
                                pattern = fw_name
                            
                            # Try different version patterns
                            version_match = re.search(rf'{re.escape(pattern)}["\']?\s*[,:]?\s*["\']?([\d.]+)', manifest_data)
                            if not version_match:
                                version_match = re.search(rf'{re.escape(pattern)}\s+v([\d.]+)', manifest_data)
                            if not version_match:
                                version_match = re.search(rf'gem\s+["\']?{re.escape(pattern)}["\']?\s*,\s*["\']([\d.]+)["\']', manifest_data)
                            
                            if version_match:
                                version = version_match.group(1)
                            
                            self.detected_frameworks.append({
                                "framework": fw_name,
                                "version": version,
                                "language": fw_config["language"],
                                "path": dir_path,
                                "source": manifest_key
                            })
                            
                    elif search_configs == "content_search":
                        # Content search for text-based files
                        if isinstance(manifest_data, str):
                            found = False
                            # Check package pattern first
                            if fw_config.get("package_pattern") and fw_config["package_pattern"] in manifest_data:
                                found = True
                            # Check content patterns
                            elif fw_config.get("content_patterns"):
                                for pattern in fw_config["content_patterns"]:
                                    if pattern in manifest_data:
                                        found = True
                                        break
                            # Fallback to framework name
                            elif fw_name in manifest_data:
                                found = True
                                
                            if found:
                                # Try to extract version
                                version = "unknown"
                                import re
                                pattern = fw_config.get("package_pattern", fw_name)
                                version_match = re.search(rf'{re.escape(pattern)}.*?[>v]([\d.]+)', manifest_data, re.DOTALL)
                                if version_match:
                                    version = version_match.group(1)
                                
                                self.detected_frameworks.append({
                                    "framework": fw_name,
                                    "version": version,
                                    "language": fw_config["language"],
                                    "path": dir_path,
                                    "source": manifest_key
                                })
                            
                    elif search_configs == "exists":
                        # Just check if file exists (for go.mod with go test framework)
                        self.detected_frameworks.append({
                            "framework": fw_name,
                            "version": "unknown",
                            "language": fw_config["language"],
                            "path": dir_path,
                            "source": manifest_key
                        })
                    
                    else:
                        # Structured search for JSON/TOML/YAML
                        for key_path in search_configs:
                            deps = parser.extract_nested_value(manifest_data, key_path)
                            if deps:
                                # Check if framework is in dependencies
                                package_name = fw_config.get("package_pattern", fw_name)
                                version = parser.check_package_in_deps(deps, package_name)
                                if version:
                                    self.detected_frameworks.append({
                                        "framework": fw_name,
                                        "version": version,
                                        "language": fw_config["language"],
                                        "path": dir_path,
                                        "source": manifest_key
                                    })
                                    break
    
    def _detect_from_workspaces(self):
        """Detect frameworks from monorepo workspace packages."""
        # This preserves the existing monorepo detection logic
        package_json = self.project_path / "package.json"
        if not package_json.exists():
            return
            
        parser = ManifestParser()
        try:
            data = parser.parse_json(package_json)
            
            # Check for workspaces field (Yarn/npm workspaces)
            workspaces = data.get("workspaces", [])
            
            # Handle different workspace formats
            if isinstance(workspaces, dict):
                # npm 7+ format: {"packages": ["packages/*"]}
                workspaces = workspaces.get("packages", [])
            
            if workspaces and isinstance(workspaces, list):
                # This is a monorepo - check workspace packages
                for pattern in workspaces:
                    # Convert workspace pattern to absolute path pattern
                    abs_pattern = str(self.project_path / pattern)
                    
                    # Handle glob patterns
                    if "*" in abs_pattern:
                        matched_paths = glob.glob(abs_pattern)
                        for matched_path in matched_paths:
                            matched_dir = Path(matched_path)
                            if matched_dir.is_dir():
                                workspace_pkg = matched_dir / "package.json"
                                if workspace_pkg.exists():
                                    # Parse and check this workspace package
                                    self._check_workspace_package(workspace_pkg, parser)
                    else:
                        # Direct path without glob
                        workspace_dir = self.project_path / pattern
                        if workspace_dir.is_dir():
                            workspace_pkg = workspace_dir / "package.json"
                            if workspace_pkg.exists():
                                self._check_workspace_package(workspace_pkg, parser)
        except Exception as e:
            print(f"Warning: Failed to check workspaces: {e}")
    
    def _check_workspace_package(self, pkg_path: Path, parser: ManifestParser):
        """Check a single workspace package.json for frameworks."""
        try:
            data = parser.parse_json(pkg_path)
            
            # Check dependencies
            all_deps = {}
            if "dependencies" in data:
                all_deps.update(data["dependencies"])
            if "devDependencies" in data:
                all_deps.update(data["devDependencies"])
            
            # Check each JavaScript framework
            for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
                if fw_config["language"] != "javascript":
                    continue
                    
                package_name = fw_config.get("package_pattern", fw_name)
                if package_name in all_deps:
                    version = all_deps[package_name]
                    # Clean version
                    version = re.sub(r'^[~^>=<]+', '', str(version)).strip()
                    
                    # Calculate relative path for path field
                    try:
                        rel_path = pkg_path.parent.relative_to(self.project_path)
                        path = str(rel_path).replace("\\", "/") if rel_path != Path('.') else '.'
                        source = str(pkg_path.relative_to(self.project_path)).replace("\\", "/")
                    except ValueError:
                        path = '.'
                        source = str(pkg_path)
                    
                    self.detected_frameworks.append({
                        "framework": fw_name,
                        "version": version,
                        "language": "javascript",
                        "path": path,
                        "source": source
                    })
        except Exception as e:
            print(f"Warning: Failed to parse workspace package {pkg_path}: {e}")
    
        # Stub method kept for backward compatibility - actual logic moved to _detect_from_manifests
        pass

    def _scan_source_imports(self):
        """Scan source files for framework imports."""
        # Limit scanning to avoid performance issues
        max_files = 100
        files_scanned = 0

        # Language file extensions
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
        }

        for ext, language in lang_extensions.items():
            if files_scanned >= max_files:
                break

            for file_path in self.project_path.rglob(f"*{ext}"):
                if files_scanned >= max_files:
                    break

                # Skip node_modules, venv, etc.
                if any(
                    part in file_path.parts
                    for part in ["node_modules", "venv", ".venv", ".auditor_venv", "vendor", "dist", "build", "__pycache__", ".git"]
                ):
                    continue
                
                # Check exclude patterns
                relative_path = file_path.relative_to(self.project_path)
                should_skip = False
                for pattern in self.exclude_patterns:
                    # Handle directory patterns
                    if pattern.endswith('/'):
                        dir_pattern = pattern.rstrip('/')
                        if str(relative_path).startswith(dir_pattern + '/') or str(relative_path).startswith(dir_pattern + '\\'):
                            should_skip = True
                            break
                    # Handle glob patterns
                    elif '*' in pattern:
                        from fnmatch import fnmatch
                        if fnmatch(str(relative_path), pattern):
                            should_skip = True
                            break
                    # Handle exact matches
                    elif str(relative_path) == pattern:
                        should_skip = True
                        break
                
                if should_skip:
                    continue

                files_scanned += 1

                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Check frameworks from registry
                    for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
                        # Only check frameworks for this language
                        if fw_config["language"] != language:
                            continue
                            
                        if "import_patterns" in fw_config:
                            for import_pattern in fw_config["import_patterns"]:
                                if import_pattern in content:
                                    # Check if not already detected in this directory
                                    file_dir = file_path.parent.relative_to(self.project_path)
                                    dir_str = str(file_dir).replace("\\", "/") if file_dir != Path('.') else '.'
                                    
                                    if not any(
                                        fw["framework"] == fw_name and fw["language"] == language and fw.get("path", ".") == dir_str
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
                    # Skip files that can't be read
                    continue

    def _check_framework_files(self):
        """Check for framework-specific files."""
        # Check all frameworks in registry for file markers
        for fw_name, fw_config in FRAMEWORK_REGISTRY.items():
            if "file_markers" in fw_config:
                for file_marker in fw_config["file_markers"]:
                    # Handle wildcard patterns
                    if "*" in file_marker:
                        # Use glob for wildcard patterns
                        import glob
                        pattern = str(self.project_path / file_marker)
                        if glob.glob(pattern):
                            # Check if not already detected
                            if not any(
                                fw["framework"] == fw_name and fw["language"] == fw_config["language"]
                                for fw in self.detected_frameworks
                            ):
                                self.detected_frameworks.append(
                                    {
                                        "framework": fw_name,
                                        "version": "unknown",
                                        "language": fw_config["language"],
                                        "path": ".",  # Framework files typically at root
                                        "source": "framework_files",
                                    }
                                )
                            break
                    else:
                        # Direct file path
                        if (self.project_path / file_marker).exists():
                            # Check if not already detected
                            if not any(
                                fw["framework"] == fw_name and fw["language"] == fw_config["language"]
                                for fw in self.detected_frameworks
                            ):
                                self.detected_frameworks.append(
                                    {
                                        "framework": fw_name,
                                        "version": "unknown",
                                        "language": fw_config["language"],
                                        "path": ".",  # Framework files typically at root
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
                    # Handle both old format (list) and new format (dict with "dependencies" key)
                    if isinstance(data, list):
                        deps_list = data
                    else:
                        deps_list = data.get("dependencies", [])
                    
                    for dep in deps_list:
                        # Store by name for quick lookup
                        self.deps_cache[dep["name"]] = dep
            except Exception as e:
                # Log the error but continue
                print(f"Warning: Could not load deps cache: {e}")
                pass

    def format_table(self) -> str:
        """Format detected frameworks as a table.

        Returns:
            Formatted table string.
        """
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
            
            # Track if any are from imports only
            if fw["source"] == "imports" and fw["version"] == "unknown":
                imports_only.append(fw["framework"])

        # Add note if frameworks detected from imports without versions
        if imports_only:
            lines.append("\n" + "="*60)
            lines.append("NOTE: Frameworks marked with 'imports' source were detected from")
            lines.append("import statements in the codebase (possibly test files) but are")
            lines.append("not listed as dependencies. Version shown as 'unknown' because")
            lines.append("they are not in package.json, pyproject.toml, or requirements.txt.")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export detected frameworks to JSON.

        Returns:
            JSON string.
        """
        return json.dumps(self.detected_frameworks, indent=2, sort_keys=True)
    
    def save_to_file(self, output_path: Path) -> None:
        """Save detected frameworks to a JSON file.
        
        Args:
            output_path: Path where the JSON file should be saved.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_json())