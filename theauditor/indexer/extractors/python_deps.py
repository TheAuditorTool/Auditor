"""Python dependency extraction for pyproject.toml and requirements.txt.

Extracts Python package dependencies from:
- pyproject.toml (using tomllib)
- requirements.txt and requirements-*.txt files

Stores in python_package_configs table for fast dependency checking.
"""
from __future__ import annotations


import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseExtractor

# Python 3.11+ is REQUIRED (per pyproject.toml)
# If tomllib is missing, environment is broken - HARD FAIL (ZERO FALLBACK POLICY)
import tomllib


def _parse_dep_spec(spec: str) -> dict[str, str]:
    """Parse a dependency specification into components.

    Handles formats:
    - package==1.0.0
    - package>=1.0,<2.0
    - package~=1.4.2
    - package[extra1,extra2]==1.0
    - git+https://github.com/user/repo.git
    - -e git+https://github.com/user/repo.git#egg=package

    Args:
        spec: Dependency specification string

    Returns:
        Dict with name, version, extras, git_url
    """
    result = {
        'name': '',
        'version': '',
        'extras': [],
        'git_url': ''
    }

    # Handle git URLs (-e prefix)
    if spec.startswith('-e '):
        spec = spec[3:].strip()

    # Git URL format: git+https://github.com/user/repo.git#egg=package
    if spec.startswith('git+'):
        result['git_url'] = spec
        # Extract package name from egg= if present
        if '#egg=' in spec:
            egg_part = spec.split('#egg=')[1]
            result['name'] = egg_part.split('&')[0].strip()
        return result

    # Handle extras: package[extra1,extra2]==1.0
    if '[' in spec and ']' in spec:
        match = re.match(r'^([a-zA-Z0-9_-]+)\[([^\]]+)\](.*)$', spec)
        if match:
            result['name'] = match.group(1).strip()
            extras_str = match.group(2)
            result['extras'] = [e.strip() for e in extras_str.split(',')]
            version_part = match.group(3).strip()
        else:
            # Malformed, treat as regular spec
            version_part = spec
    else:
        # Regular format: package==1.0.0 or package>=1.0
        # Split on version operators
        for op in ['===', '==', '!=', '~=', '>=', '<=', '>', '<']:
            if op in spec:
                parts = spec.split(op, 1)
                result['name'] = parts[0].strip()
                result['version'] = f"{op}{parts[1].strip()}"
                return result

        # No version specified
        result['name'] = spec.strip()
        version_part = ''

    if version_part:
        result['version'] = version_part.strip()

    return result


def _extract_from_requirements(content: str, file_path: str) -> dict[str, Any]:
    """Extract dependencies from requirements.txt format.

    Args:
        content: File content
        file_path: Path to requirements file

    Returns:
        Dict with file_path, file_type, dependencies
    """
    dependencies = []

    for line in content.splitlines():
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue

        # Skip directives (-r, -e, -c, --hash, etc.)
        # But handle -e git+... specially
        if line.startswith('-r') or line.startswith('-c'):
            continue

        # Strip inline comments
        if '#' in line and not line.startswith('git+'):
            line = line.split('#')[0].strip()

        # Parse the dependency
        dep_info = _parse_dep_spec(line)
        if dep_info['name']:
            dependencies.append(dep_info)

    return {
        'file_path': file_path,
        'file_type': 'requirements',
        'project_name': None,
        'project_version': None,
        'dependencies': dependencies,
        'optional_dependencies': {},
        'build_system': None
    }


def _extract_from_pyproject(content: str, file_path: str) -> dict[str, Any]:
    """Extract dependencies from pyproject.toml.

    Args:
        content: File content
        file_path: Path to pyproject.toml

    Returns:
        Dict with file_path, file_type, dependencies, optional_dependencies
    """
    try:
        data = tomllib.loads(content)
    except Exception:
        # Malformed TOML - return empty
        return {
            'file_path': file_path,
            'file_type': 'pyproject',
            'project_name': None,
            'project_version': None,
            'dependencies': [],
            'optional_dependencies': {},
            'build_system': None
        }

    # Extract project metadata
    project = data.get('project', {})
    project_name = project.get('name')
    project_version = project.get('version')

    # Extract dependencies
    dependencies = []
    deps_list = project.get('dependencies', [])
    for dep_spec in deps_list:
        dep_info = _parse_dep_spec(dep_spec)
        if dep_info['name']:
            dependencies.append(dep_info)

    # Extract optional dependencies (dev, docs, test groups)
    optional_dependencies = {}
    optional_deps = project.get('optional-dependencies', {})
    for group_name, group_deps in optional_deps.items():
        group_list = []
        for dep_spec in group_deps:
            dep_info = _parse_dep_spec(dep_spec)
            if dep_info['name']:
                group_list.append(dep_info)
        optional_dependencies[group_name] = group_list

    # Extract build system
    build_system = None
    build_sys = data.get('build-system', {})
    if build_sys:
        build_system = {
            'requires': build_sys.get('requires', []),
            'build-backend': build_sys.get('build-backend')
        }

    return {
        'file_path': file_path,
        'file_type': 'pyproject',
        'project_name': project_name,
        'project_version': project_version,
        'dependencies': dependencies,
        'optional_dependencies': optional_dependencies,
        'build_system': build_system
    }


def extract_python_dependencies(file_path: str, content: str) -> dict[str, Any] | None:
    """Extract Python dependencies from pyproject.toml or requirements.txt.

    Main entry point for Python dependency extraction.

    Args:
        file_path: Path to dependency file
        content: File content

    Returns:
        Dict with parsed dependencies or None if not a dependency file
    """
    path = Path(file_path)

    # Check file type
    if path.name == 'pyproject.toml':
        return _extract_from_pyproject(content, file_path)
    elif path.name.startswith('requirements') and path.suffix == '.txt':
        return _extract_from_requirements(content, file_path)

    return None


class PythonDepsExtractor(BaseExtractor):
    """Extractor for Python dependency files (pyproject.toml, requirements.txt)."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return ['.toml', '.txt']  # Will be filtered by should_extract

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.

        Args:
            file_path: Path to the file

        Returns:
            True if this is a Python dependency file
        """
        path = Path(file_path)
        file_name = path.name

        # Match pyproject.toml
        if file_name == 'pyproject.toml':
            return True

        # Match requirements*.txt files
        if file_name.startswith('requirements') and path.suffix == '.txt':
            return True

        return False

    def extract(self, file_info: dict[str, Any], content: str,
                tree: Any | None = None) -> dict[str, Any]:
        """Extract Python dependencies and store to database.

        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree (not used for deps)

        Returns:
            Dict with extracted dependency data
        """
        file_path = str(file_info['path'])

        # Extract dependencies using helper function
        deps_data = extract_python_dependencies(file_path, content)

        if not deps_data:
            return {}

        # Store directly to database
        self.db_manager.add_python_package_config(
            file_path=deps_data['file_path'],
            file_type=deps_data['file_type'],
            project_name=deps_data.get('project_name'),
            project_version=deps_data.get('project_version'),
            dependencies=json.dumps(deps_data['dependencies']),
            optional_dependencies=json.dumps(deps_data.get('optional_dependencies', {})),
            build_system=json.dumps(deps_data.get('build_system')) if deps_data.get('build_system') else None
        )

        # Return minimal dict for indexer compatibility
        return {}
