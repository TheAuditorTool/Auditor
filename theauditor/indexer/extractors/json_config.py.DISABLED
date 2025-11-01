"""JSON configuration file extractor.

Extracts package.json, package-lock.json, yarn.lock, pnpm-lock.yaml
for build analysis and dependency management.

This extractor follows the gold standard database-first pattern:
- Parses package.json for dependencies/devDependencies
- Analyzes lock files to detect duplicate dependencies
- Stores all data in database for rule consumption
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

from . import BaseExtractor


class JsonConfigExtractor(BaseExtractor):
    """Extractor for package.json and lock files."""

    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        # Support .json for package.json, package-lock.json
        # Support .lock for yarn.lock
        # Support .yaml for pnpm-lock.yaml
        return ['.json', '.lock', '.yaml']

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.

        Only process specific build configuration files, not all JSON/YAML.
        """
        filename = Path(file_path).name.lower()
        return filename in [
            'package.json',
            'package-lock.json',
            'yarn.lock',
            'pnpm-lock.yaml'
        ]

    def extract(self, file_info: Dict[str, Any], content: str,
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract package.json and lock file data.

        Args:
            file_info: File metadata with 'path' key
            content: Raw file content
            tree: Unused (no AST for JSON/YAML)

        Returns:
            Dictionary with 'package_configs' and 'lock_analysis' lists
        """
        result = {
            'package_configs': [],
            'lock_analysis': []
        }

        filename = Path(file_info['path']).name.lower()

        if filename == 'package.json':
            result['package_configs'] = self._extract_package_json(
                file_info['path'], content
            )
        elif filename in ['package-lock.json', 'yarn.lock', 'pnpm-lock.yaml']:
            result['lock_analysis'] = self._extract_lock_file(
                file_info['path'], filename, content
            )

        return result

    def _extract_package_json(self, file_path: str, content: str) -> List[Dict]:
        """Parse package.json and extract dependency data.

        Extracts all fields needed for build security analysis:
        - dependencies: Production dependencies
        - devDependencies: Development-only dependencies (security risk if in prod)
        - peerDependencies: Required peer dependencies
        - scripts: Build/dev scripts (may contain secrets)
        - engines: Node/npm version constraints
        - workspaces: Monorepo workspace configuration
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Invalid JSON - return empty, don't crash indexer
            return []

        return [{
            'file_path': file_path,
            'package_name': data.get('name', ''),
            'version': data.get('version', ''),
            'dependencies': data.get('dependencies', {}),
            'dev_dependencies': data.get('devDependencies', {}),
            'peer_dependencies': data.get('peerDependencies', {}),
            'scripts': data.get('scripts', {}),
            'engines': data.get('engines', {}),
            'workspaces': data.get('workspaces', []),
            'is_private': data.get('private', False)
        }]

    def _extract_lock_file(self, file_path: str, filename: str,
                           content: str) -> List[Dict]:
        """Parse lock files and detect duplicate dependencies.

        Lock files contain the full dependency tree with exact versions.
        Duplicate packages (same package, different versions) indicate:
        - Bundle bloat (both versions shipped)
        - Potential version conflicts
        - Inefficient dependency management

        Args:
            file_path: Path to lock file
            filename: Lock file name (determines format)
            content: Raw lock file content

        Returns:
            List with single lock analysis record
        """
        if filename == 'package-lock.json':
            return self._parse_npm_lock(file_path, content)
        elif filename == 'yarn.lock':
            return self._parse_yarn_lock(file_path, content)
        elif filename == 'pnpm-lock.yaml':
            return self._parse_pnpm_lock(file_path, content)
        return []

    def _parse_npm_lock(self, file_path: str, content: str) -> List[Dict]:
        """Parse npm package-lock.json.

        Handles both lockfileVersion 1 (nested dependencies) and
        lockfileVersion 2+ (flat packages structure).
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []

        # Detect duplicates by package name
        packages = {}
        duplicates = defaultdict(set)

        # Handle both lockfileVersion 1 and 2+ formats
        if 'dependencies' in data:
            # Lockfile v1 format (nested dependencies)
            self._collect_npm_v1_packages(data['dependencies'], packages, duplicates)
        elif 'packages' in data:
            # Lockfile v2+ format (flat packages)
            self._collect_npm_v2_packages(data['packages'], packages, duplicates)

        # Filter to only packages with multiple versions
        duplicate_packages = {
            name: sorted(list(versions))
            for name, versions in duplicates.items()
            if len(versions) > 1
        }

        return [{
            'file_path': file_path,
            'lock_type': 'npm',
            'package_manager_version': data.get('lockfileVersion'),
            'total_packages': len(packages),
            'duplicate_packages': duplicate_packages,
            'lock_file_version': str(data.get('lockfileVersion', '1'))
        }]

    def _collect_npm_v1_packages(self, deps: Dict, packages: Dict,
                                 duplicates: Dict):
        """Collect packages from npm lockfile v1 format (nested).

        Format:
        "dependencies": {
            "lodash": {
                "version": "4.17.21",
                "dependencies": { ... }
            }
        }
        """
        for name, info in deps.items():
            if not isinstance(info, dict):
                continue
            version = info.get('version', '')
            if version:
                packages[f"{name}@{version}"] = True
                duplicates[name].add(version)
            # Recurse for nested dependencies
            if 'dependencies' in info and isinstance(info['dependencies'], dict):
                self._collect_npm_v1_packages(info['dependencies'], packages, duplicates)

    def _collect_npm_v2_packages(self, pkgs: Dict, packages: Dict,
                                 duplicates: Dict):
        """Collect packages from npm lockfile v2+ format (flat).

        Format:
        "packages": {
            "node_modules/lodash": {
                "version": "4.17.21"
            }
        }
        """
        for pkg_path, info in pkgs.items():
            if pkg_path == "" or not isinstance(info, dict):
                # Root package or invalid entry
                continue
            # Extract name from path like "node_modules/lodash" or "node_modules/@babel/core"
            parts = pkg_path.split('node_modules/')
            if len(parts) > 1:
                name = parts[-1]
                version = info.get('version', '')
                if version:
                    packages[f"{name}@{version}"] = True
                    duplicates[name].add(version)

    def _parse_yarn_lock(self, file_path: str, content: str) -> List[Dict]:
        """Parse yarn.lock file.

        Yarn lock format is custom text format:
        "package@^1.0.0":
          version "1.2.3"

        Uses regex to extract package names and versions.
        """
        packages = {}
        duplicates = defaultdict(set)

        # Yarn lock format: "package@version:\n  version \"1.2.3\""
        # Match both quoted and unquoted package names
        pattern = r'^"?([^@"\n]+)@[^:]*:\s*\n\s*version\s+"([^"]+)"'
        matches = re.findall(pattern, content, re.MULTILINE)

        for name, version in matches:
            name = name.strip()
            packages[f"{name}@{version}"] = True
            duplicates[name].add(version)

        duplicate_packages = {
            name: sorted(list(versions))
            for name, versions in duplicates.items()
            if len(versions) > 1
        }

        return [{
            'file_path': file_path,
            'lock_type': 'yarn',
            'package_manager_version': None,  # Yarn lock doesn't store version
            'total_packages': len(packages),
            'duplicate_packages': duplicate_packages,
            'lock_file_version': '1'
        }]

    def _parse_pnpm_lock(self, file_path: str, content: str) -> List[Dict]:
        """Parse pnpm-lock.yaml file.

        pnpm format is YAML but uses simplified regex parsing:
        /package/version:
          resolution: ...

        This avoids requiring PyYAML dependency.
        """
        packages = {}
        duplicates = defaultdict(set)

        # pnpm format: "/package/version:" or "/@scope/package/version:"
        # Match both scoped and unscoped packages
        pattern = r'^\s*/(@?[^/\n]+)/([0-9][^:\n]+):'
        matches = re.findall(pattern, content, re.MULTILINE)

        for name, version in matches:
            name = name.strip()
            packages[f"{name}@{version}"] = True
            duplicates[name].add(version)

        duplicate_packages = {
            name: sorted(list(versions))
            for name, versions in duplicates.items()
            if len(versions) > 1
        }

        return [{
            'file_path': file_path,
            'lock_type': 'pnpm',
            'package_manager_version': None,
            'total_packages': len(packages),
            'duplicate_packages': duplicate_packages,
            'lock_file_version': '5'  # Current pnpm major version
        }]
