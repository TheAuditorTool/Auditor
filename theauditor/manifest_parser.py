"""Universal parser for all manifest file types used in framework detection."""


import json
import yaml
import configparser
from pathlib import Path
from typing import Any


class ManifestParser:
    """Universal parser for all manifest file types."""
    
    def parse_toml(self, path: Path) -> dict:
        """Parse TOML using tomllib with fallback to tomli for older Python."""
        try:
            import tomllib
        except ImportError:
            # Python < 3.11
            try:
                import tomli as tomllib
            except ImportError:
                print(f"Warning: Cannot parse {path} - tomllib not available")
                return {}
        
        try:
            with open(path, 'rb') as f:
                return tomllib.load(f)
        except Exception as e:
            print(f"Warning: Failed to parse TOML {path}: {e}")
            return {}
    
    def parse_json(self, path: Path) -> dict:
        """Parse JSON safely."""
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Failed to parse JSON {path}: {e}")
            return {}
    
    def parse_yaml(self, path: Path) -> dict:
        """Parse YAML safely."""
        try:
            with open(path, encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError) as e:
            print(f"Warning: Failed to parse YAML {path}: {e}")
            return {}
    
    def parse_ini(self, path: Path) -> dict:
        """Parse INI/CFG files."""
        try:
            config = configparser.ConfigParser()
            config.read(path)
            return {s: dict(config[s]) for s in config.sections()}
        except Exception as e:
            print(f"Warning: Failed to parse INI/CFG {path}: {e}")
            return {}
    
    def parse_requirements_txt(self, path: Path) -> list[str]:
        """Parse requirements.txt format, returns list of package specs."""
        try:
            with open(path, encoding='utf-8') as f:
                lines = []
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    # Skip special directives
                    if line.startswith('-'):
                        continue
                    # Strip inline comments
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    if line:
                        lines.append(line)
                return lines
        except OSError as e:
            print(f"Warning: Failed to parse requirements.txt {path}: {e}")
            return []
    
    def extract_nested_value(self, data: dict | list, key_path: list[str]) -> Any:
        """
        Navigate nested dict with key path.
        Handles wildcards (*) for dynamic keys.
        
        Example: ["tool", "poetry", "group", "*", "dependencies"]
        Returns the value at the path, or None if not found.
        """
        if not key_path:
            return data
        
        current = data
        
        for i, key in enumerate(key_path):
            if key == "*":
                # Wildcard - collect from all keys at this level
                if isinstance(current, dict):
                    results = {}
                    remaining_path = key_path[i+1:] if i+1 < len(key_path) else []
                    
                    for k, v in current.items():
                        if remaining_path:
                            nested_result = self.extract_nested_value(v, remaining_path)
                            if nested_result is not None:
                                # Merge results for wildcards
                                if isinstance(nested_result, dict):
                                    results.update(nested_result)
                                elif isinstance(nested_result, list):
                                    if not results:
                                        results = []
                                    results.extend(nested_result)
                                else:
                                    results[k] = nested_result
                        else:
                            results[k] = v
                    
                    return results if results else None
                else:
                    return None
            
            elif isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return None
            else:
                return None
        
        return current
    
    def check_package_in_deps(self, deps: Any, package_name: str) -> str | None:
        """
        Check if a package exists in dependencies and return its version.
        Handles various dependency formats including Cargo workspace inheritance.
        """
        if deps is None:
            return None

        # Handle dict format (package.json, pyproject.toml with Poetry, Cargo.toml)
        if isinstance(deps, dict):
            if package_name in deps:
                version = deps[package_name]
                # Handle complex version specs
                if isinstance(version, dict):
                    # Cargo workspace inheritance: {workspace: true}
                    if version.get('workspace') is True:
                        return 'workspace'
                    # Git dependency
                    if 'git' in version:
                        return f"git:{version.get('branch', version.get('tag', 'HEAD'))}"
                    # Path dependency
                    if 'path' in version:
                        return f"path:{version['path']}"
                    # Regular version spec
                    version = version.get('version', str(version))
                return str(version)
        
        # Handle list format (PEP 621 pyproject.toml)
        elif isinstance(deps, list):
            for dep_spec in deps:
                if isinstance(dep_spec, str):
                    # Parse "package==version" or "package>=version" format
                    import re
                    # Handle extras: package[extra]==version
                    dep_spec_clean = re.sub(r'\[.*?\]', '', dep_spec)

                    # Check if this is our package (case-insensitive for Python packages)
                    # Python package names in requirements.txt can be Django/django, Flask/flask, etc.
                    if dep_spec_clean.lower().startswith(package_name.lower()):
                        # Extract version if present (case-insensitive regex)
                        match = re.match(rf'^{re.escape(package_name)}\s*([><=~!]+)\s*(.+)$', dep_spec_clean, re.IGNORECASE)
                        if match:
                            return match.group(2).strip()
                        elif dep_spec_clean.strip().lower() == package_name.lower():
                            return "latest"
        
        # Handle string format (requirements.txt content)
        elif isinstance(deps, str):
            lines = deps.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    import re
                    # Remove extras
                    line_clean = re.sub(r'\[.*?\]', '', line)
                    if line_clean.startswith(package_name):
                        match = re.match(rf'^{re.escape(package_name)}\s*([><=~!]+)\s*(.+)$', line_clean)
                        if match:
                            return match.group(2).strip()
                        elif line_clean.strip() == package_name:
                            return "latest"

        return None

    def parse_cargo_toml(self, path: Path) -> dict:
        """Parse Cargo.toml for Rust dependencies and workspace info.

        Returns:
            Dict with keys:
            - dependencies: {name: version_or_spec}
            - dev_dependencies: {name: version_or_spec}
            - workspace_dependencies: {name: version_or_spec} (if workspace root)
            - workspace_members: [str] (if workspace root)
            - is_workspace_member: bool
        """
        data = self.parse_toml(path)
        if not data:
            return {}

        result = {
            'dependencies': {},
            'dev_dependencies': {},
            'workspace_dependencies': {},
            'workspace_members': [],
            'is_workspace_member': False,
        }

        # Extract workspace info (if this is a workspace root)
        workspace = data.get('workspace', {})
        if workspace:
            result['workspace_members'] = workspace.get('members', [])

            # Workspace-level dependencies
            ws_deps = workspace.get('dependencies', {})
            for name, spec in ws_deps.items():
                result['workspace_dependencies'][name] = self._normalize_cargo_dep(spec)

        # Extract package dependencies
        deps = data.get('dependencies', {})
        for name, spec in deps.items():
            norm = self._normalize_cargo_dep(spec)
            if norm == 'workspace':
                result['is_workspace_member'] = True
            result['dependencies'][name] = norm

        # Extract dev dependencies
        dev_deps = data.get('dev-dependencies', {})
        for name, spec in dev_deps.items():
            result['dev_dependencies'][name] = self._normalize_cargo_dep(spec)

        return result

    def _normalize_cargo_dep(self, spec: Any) -> str:
        """Normalize a Cargo dependency spec to a version string.

        Args:
            spec: Can be:
                - "1.0" (simple version string)
                - {"version": "1.0", "features": [...]}
                - {"workspace": true}
                - {"git": "...", "branch": "..."}

        Returns:
            Version string, "workspace", "git", or str(spec)
        """
        if isinstance(spec, str):
            return spec

        if isinstance(spec, dict):
            # Check for workspace inheritance first
            if spec.get('workspace') is True:
                return 'workspace'

            # Check for git dependency
            if 'git' in spec:
                return f"git:{spec.get('branch', spec.get('tag', 'HEAD'))}"

            # Check for path dependency
            if 'path' in spec:
                return f"path:{spec['path']}"

            # Regular version spec
            if 'version' in spec:
                return spec['version']

        return str(spec)

    def discover_monorepo_manifests(self, root: Path) -> list[Path]:
        """Find all manifest files in a polyglot monorepo.

        Args:
            root: Project root directory

        Returns:
            List of manifest file paths, excluding node_modules/vendor/etc.
        """
        manifests = []
        skip_dirs = {'node_modules', 'vendor', '.git', '.venv', 'venv',
                     '__pycache__', 'dist', 'build', 'target', '.auditor_venv'}

        patterns = [
            'package.json',
            'pyproject.toml',
            'requirements.txt',
            'Cargo.toml',
            'Gemfile',
            'pom.xml',
            'build.gradle',
            'composer.json',
        ]

        for pattern in patterns:
            for path in root.rglob(pattern):
                # Skip if in excluded directory
                if not any(skip in path.parts for skip in skip_dirs):
                    manifests.append(path)

        return manifests