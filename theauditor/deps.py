"""Dependency parser for multiple ecosystems."""


import glob
import http.client
import json
import platform
import re
import shutil
import time
import urllib.error
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from theauditor import __version__
from theauditor.security import sanitize_path, sanitize_url_component, validate_package_name, SecurityError

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"

# Rate limiting configuration - optimized for minimal runtime
# Based on actual API rate limits and industry standards
RATE_LIMIT_NPM = 0.1      # npm registry: 600 req/min (well under any limit)
RATE_LIMIT_PYPI = 0.2     # PyPI: 300 req/min (safe margin) 
RATE_LIMIT_DOCKER = 0.2   # Docker Hub: 300 req/min for tag checks
RATE_LIMIT_BACKOFF = 15   # Backoff on 429/disconnect (15s gives APIs time to reset)


def parse_dependencies(root_path: str = ".") -> list[dict[str, Any]]:
    """
    Parse dependencies from various package managers.

    Architecture:
    - Primary: Read from package_configs table (populated by indexer)
    - Fallback: Parse files directly (for standalone 'aud deps' without 'aud index')

    Returns list of dependency objects with structure:
    {
        "name": str,
        "version": str,
        "manager": "npm"|"py",
        "files": [paths that import it],
        "source": "package.json|pyproject.toml|requirements.txt"
    }
    """
    import os
    import sqlite3
    root = Path(root_path)
    deps = []

    # Debug mode
    debug = os.environ.get("THEAUDITOR_DEBUG")

    # =========================================================================
    # DATABASE-FIRST: Try to read npm dependencies from package_configs table
    # =========================================================================
    db_path = root / ".pf" / "repo_index.db"
    npm_deps_from_db = []

    if db_path.exists():
        if debug:
            print(f"Debug: Reading npm dependencies from database: {db_path}")

        npm_deps_from_db = _read_npm_deps_from_database(db_path, root, debug)

        if npm_deps_from_db:
            if debug:
                print(f"Debug: Loaded {len(npm_deps_from_db)} npm dependencies from database")
            deps.extend(npm_deps_from_db)
        elif debug:
            print("Debug: package_configs table empty, falling back to file parsing for npm")
    elif debug:
        print("Debug: Database not found, parsing npm dependencies from files")

    # =========================================================================
    # FALLBACK: Parse npm dependencies from files if database didn't have them
    # =========================================================================
    if not npm_deps_from_db:
        # Parse Node dependencies from files
        try:
            package_json = sanitize_path("package.json", root_path)
            if package_json.exists():
                if debug:
                    print(f"Debug: Found {package_json}")
                deps.extend(_parse_package_json(package_json))
        except SecurityError as e:
            if debug:
                print(f"Debug: Security error checking package.json: {e}")

        # Check for package.json in common monorepo patterns
        npm_patterns = [
            "*/package.json",           # backend/package.json, frontend/package.json
            "packages/*/package.json",   # packages/core/package.json
            "apps/*/package.json",       # apps/web/package.json
            "services/*/package.json",   # services/api/package.json
        ]

        package_files = []
        for pattern in npm_patterns:
            package_files.extend(root.glob(pattern))

        # Process all discovered package.json files
        for pkg_file in package_files:
            try:
                safe_pkg = sanitize_path(str(pkg_file), root_path)
                if debug:
                    print(f"Debug: Found {safe_pkg}")
                # Parse this package.json directly without workspace detection
                pkg_deps = _parse_standalone_package_json(safe_pkg)
                # Set the workspace_package field to reflect the actual path
                try:
                    rel_path = safe_pkg.relative_to(Path(root_path).resolve())
                    workspace_path = str(rel_path).replace("\\", "/")
                except ValueError:
                    workspace_path = str(safe_pkg)

                for dep in pkg_deps:
                    dep["workspace_package"] = workspace_path

                deps.extend(pkg_deps)
            except SecurityError as e:
                if debug:
                    print(f"Debug: Security error with {pkg_file}: {e}")

    # =========================================================================
    # DATABASE-FIRST: Try to read Python dependencies from python_package_configs table
    # =========================================================================
    python_deps_from_db = []

    if db_path.exists():
        if debug:
            print(f"Debug: Reading Python dependencies from database: {db_path}")

        python_deps_from_db = _read_python_deps_from_database(db_path, root, debug)

        if python_deps_from_db:
            if debug:
                print(f"Debug: Loaded {len(python_deps_from_db)} Python dependencies from database")
            deps.extend(python_deps_from_db)
        elif debug:
            print("Debug: python_package_configs table empty, falling back to file parsing for Python")
    elif debug:
        print("Debug: Database not found, parsing Python dependencies from files")

    # =========================================================================
    # FALLBACK: Parse Python dependencies from files if database didn't have them
    # =========================================================================
    if not python_deps_from_db:
        # Parse Python dependencies
        try:
            pyproject = sanitize_path("pyproject.toml", root_path)
            if pyproject.exists():
                if debug:
                    print(f"Debug: Found {pyproject}")
                deps.extend(_parse_pyproject_toml(pyproject))
        except SecurityError as e:
            if debug:
                print(f"Debug: Security error checking pyproject.toml: {e}")

        # Parse requirements files (including in subdirectories for monorepos)
        # Check root first
        req_files = list(root.glob("requirements*.txt"))
        # Also check common Python monorepo patterns
        req_files.extend(root.glob("*/requirements*.txt"))  # backend/requirements.txt
        req_files.extend(root.glob("services/*/requirements*.txt"))  # services/api/requirements.txt
        req_files.extend(root.glob("apps/*/requirements*.txt"))  # apps/web/requirements.txt

        # Also check for pyproject.toml in subdirectories (Python monorepos)
        pyproject_files = list(root.glob("*/pyproject.toml"))  # backend/pyproject.toml
        pyproject_files.extend(root.glob("services/*/pyproject.toml"))
        pyproject_files.extend(root.glob("apps/*/pyproject.toml"))

        # Process all pyproject.toml files found
        for pyproject_file in pyproject_files:
            try:
                safe_pyproject = sanitize_path(str(pyproject_file), root_path)
                if debug:
                    print(f"Debug: Found {safe_pyproject}")
                deps.extend(_parse_pyproject_toml(safe_pyproject))
            except SecurityError as e:
                if debug:
                    print(f"Debug: Security error with {pyproject_file}: {e}")

        if debug and req_files:
            print(f"Debug: Found requirements files: {req_files}")
        for req_file in req_files:
            try:
                # Validate the path is within project root
                safe_req_file = sanitize_path(str(req_file), root_path)
                deps.extend(_parse_requirements_txt(safe_req_file))
            except SecurityError as e:
                if debug:
                    print(f"Debug: Security error with {req_file}: {e}")
    
    # Parse Docker Compose files
    docker_compose_files = list(root.glob("docker-compose*.yml")) + list(root.glob("docker-compose*.yaml"))
    if debug and docker_compose_files:
        print(f"Debug: Found Docker Compose files: {docker_compose_files}")
    for compose_file in docker_compose_files:
        try:
            safe_compose_file = sanitize_path(str(compose_file), root_path)
            deps.extend(_parse_docker_compose(safe_compose_file))
        except SecurityError as e:
            if debug:
                print(f"Debug: Security error with {compose_file}: {e}")
    
    # Parse Dockerfiles
    dockerfiles = list(root.glob("**/Dockerfile"))
    if debug and dockerfiles:
        print(f"Debug: Found Dockerfiles: {dockerfiles}")
    for dockerfile in dockerfiles:
        try:
            safe_dockerfile = sanitize_path(str(dockerfile), root_path)
            deps.extend(_parse_dockerfile(safe_dockerfile))
        except SecurityError as e:
            if debug:
                print(f"Debug: Security error with {dockerfile}: {e}")

    # Parse Cargo.toml for Rust dependencies
    try:
        cargo_toml = sanitize_path("Cargo.toml", root_path)
        if cargo_toml.exists():
            if debug:
                print(f"Debug: Found {cargo_toml}")
            deps.extend(_parse_cargo_toml(cargo_toml))
    except SecurityError as e:
        if debug:
            print(f"Debug: Security error checking Cargo.toml: {e}")

    if debug:
        print(f"Debug: Total dependencies found: {len(deps)}")

    return deps


def _read_npm_deps_from_database(db_path: Path, root: Path, debug: bool) -> list[dict[str, Any]]:
    """Read npm dependencies from package_configs table.

    Args:
        db_path: Path to repo_index.db
        root: Project root path
        debug: Debug mode flag

    Returns:
        List of dependency dictionaries in deps.py format
    """
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if package_configs table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='package_configs'
        """)

        if not cursor.fetchone():
            conn.close()
            return []

        # Read all package.json files from database
        cursor.execute("""
            SELECT file_path, package_name, version, dependencies, dev_dependencies
            FROM package_configs
        """)

        deps = []

        for file_path, pkg_name, pkg_version, deps_json, dev_deps_json in cursor.fetchall():
            if not deps_json:
                continue

            try:
                dependencies = json.loads(deps_json)
                dev_dependencies = json.loads(dev_deps_json) if dev_deps_json else {}

                # Determine workspace_package path (for monorepo support)
                workspace_package = file_path if file_path != "package.json" else None

                # Convert to deps.py format (maintains compatibility with downstream code)
                for name, version in dependencies.items():
                    dep_obj = {
                        "name": name,
                        "version": version,
                        "manager": "npm",
                        "files": [],  # TODO: Could join with refs table for actual usage
                        "source": file_path
                    }
                    if workspace_package:
                        dep_obj["workspace_package"] = workspace_package
                    deps.append(dep_obj)

                # Include devDependencies (marked separately)
                for name, version in dev_dependencies.items():
                    dep_obj = {
                        "name": name,
                        "version": version,
                        "manager": "npm",
                        "files": [],
                        "source": file_path,
                        "dev": True
                    }
                    if workspace_package:
                        dep_obj["workspace_package"] = workspace_package
                    deps.append(dep_obj)

            except json.JSONDecodeError:
                if debug:
                    print(f"Debug: Failed to parse dependencies JSON from {file_path}")
                continue

        conn.close()
        return deps

    except (sqlite3.Error, Exception) as e:
        if debug:
            print(f"Debug: Database read error: {e}")
        return []


def _read_python_deps_from_database(db_path: Path, root: Path, debug: bool) -> list[dict[str, Any]]:
    """Read Python dependencies from python_package_configs table.

    Args:
        db_path: Path to repo_index.db
        root: Project root path
        debug: Debug mode flag

    Returns:
        List of dependency dictionaries in deps.py format
    """
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if python_package_configs table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='python_package_configs'
        """)

        if not cursor.fetchone():
            conn.close()
            return []

        # Read all Python dependency files from database
        cursor.execute("""
            SELECT file_path, file_type, project_name, project_version,
                   dependencies, optional_dependencies
            FROM python_package_configs
        """)

        deps = []

        for file_path, file_type, proj_name, proj_version, deps_json, optional_deps_json in cursor.fetchall():
            if not deps_json:
                continue

            try:
                dependencies = json.loads(deps_json)
                optional_dependencies = json.loads(optional_deps_json) if optional_deps_json else {}

                # Convert to deps.py format (maintains compatibility with downstream code)
                for dep_info in dependencies:
                    dep_obj = {
                        "name": dep_info.get('name', ''),
                        "version": dep_info.get('version', ''),
                        "manager": "py",
                        "files": [],  # TODO: Could join with refs table for actual usage
                        "source": file_path
                    }

                    # Add extras if present
                    if dep_info.get('extras'):
                        dep_obj['extras'] = dep_info['extras']

                    # Add git URL if present
                    if dep_info.get('git_url'):
                        dep_obj['git_url'] = dep_info['git_url']

                    deps.append(dep_obj)

                # Include optional dependencies (marked with group name)
                for group_name, group_deps in optional_dependencies.items():
                    for dep_info in group_deps:
                        dep_obj = {
                            "name": dep_info.get('name', ''),
                            "version": dep_info.get('version', ''),
                            "manager": "py",
                            "files": [],
                            "source": file_path,
                            "optional_group": group_name
                        }

                        if dep_info.get('extras'):
                            dep_obj['extras'] = dep_info['extras']

                        if dep_info.get('git_url'):
                            dep_obj['git_url'] = dep_info['git_url']

                        deps.append(dep_obj)

            except json.JSONDecodeError:
                if debug:
                    print(f"Debug: Failed to parse Python dependencies JSON from {file_path}")
                continue

        conn.close()
        return deps

    except (sqlite3.Error, Exception) as e:
        if debug:
            print(f"Debug: Python database read error: {e}")
        return []


def _parse_standalone_package_json(path: Path) -> list[dict[str, Any]]:
    """Parse dependencies from a single package.json file without workspace detection."""
    deps = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        
        # Combine dependencies and devDependencies
        all_deps = {}
        if "dependencies" in data:
            all_deps.update(data["dependencies"])
        if "devDependencies" in data:
            all_deps.update(data["devDependencies"])
        
        for name, version_spec in all_deps.items():
            # Clean version spec (remove ^, ~, >=, etc.)
            version = _clean_version(version_spec)
            deps.append({
                "name": name,
                "version": version,
                "manager": "npm",
                "files": [],  # Will be populated by workset scan
                "source": "package.json",
                "workspace_package": "package.json"  # Will be overridden by caller
            })
    except (json.JSONDecodeError, KeyError) as e:
        # Log but don't fail - package.json might be malformed
        print(f"Warning: Could not parse {path}: {e}")
    
    return deps


def _parse_package_json(path: Path) -> list[dict[str, Any]]:
    """Parse dependencies from package.json, with monorepo support."""
    deps = []
    processed_packages = set()  # Track processed packages to avoid duplicates
    
    def parse_single_package(pkg_path: Path, workspace_path: str = "package.json") -> list[dict[str, Any]]:
        """Parse a single package.json file."""
        local_deps = []
        try:
            with open(pkg_path, encoding="utf-8") as f:
                data = json.load(f)
            
            # Combine dependencies and devDependencies
            all_deps = {}
            if "dependencies" in data:
                all_deps.update(data["dependencies"])
            if "devDependencies" in data:
                all_deps.update(data["devDependencies"])
            
            for name, version_spec in all_deps.items():
                # Clean version spec (remove ^, ~, >=, etc.)
                version = _clean_version(version_spec)
                local_deps.append({
                    "name": name,
                    "version": version,
                    "manager": "npm",
                    "files": [],  # Will be populated by workset scan
                    "source": "package.json",
                    "workspace_package": workspace_path  # Track which package.json this came from
                })
        except (json.JSONDecodeError, KeyError) as e:
            # Log but don't fail - package.json might be malformed
            print(f"Warning: Could not parse {pkg_path}: {e}")
        
        return local_deps
    
    # Parse the root package.json first
    root_dir = path.parent
    deps.extend(parse_single_package(path, "package.json"))
    processed_packages.add(str(path.resolve()))
    
    # Check for monorepo workspaces
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        
        # Check for workspaces field (Yarn/npm workspaces)
        workspaces = data.get("workspaces", [])
        
        # Handle different workspace formats
        if isinstance(workspaces, dict):
            # npm 7+ format: {"packages": ["packages/*"]}
            workspaces = workspaces.get("packages", [])
        
        if workspaces and isinstance(workspaces, list):
            # This is a monorepo - expand workspace patterns
            for pattern in workspaces:
                # Convert workspace pattern to absolute path pattern
                abs_pattern = str(root_dir / pattern)
                
                # Handle glob patterns like "packages/*" or "apps/**"
                if "*" in abs_pattern:
                    # Use glob to find matching directories
                    matched_paths = glob.glob(abs_pattern)
                    
                    for matched_path in matched_paths:
                        matched_dir = Path(matched_path)
                        if matched_dir.is_dir():
                            # Look for package.json in this directory
                            workspace_pkg = matched_dir / "package.json"
                            if workspace_pkg.exists():
                                # Skip if already processed
                                if str(workspace_pkg.resolve()) in processed_packages:
                                    continue
                                
                                # Calculate relative path for workspace_package field
                                try:
                                    rel_path = workspace_pkg.relative_to(root_dir)
                                    workspace_path = str(rel_path).replace("\\", "/")
                                except ValueError:
                                    # If relative path fails, use absolute path
                                    workspace_path = str(workspace_pkg)
                                
                                # Parse this workspace package
                                workspace_deps = parse_single_package(workspace_pkg, workspace_path)
                                deps.extend(workspace_deps)
                                processed_packages.add(str(workspace_pkg.resolve()))
                else:
                    # Direct path without glob
                    workspace_dir = root_dir / pattern
                    if workspace_dir.is_dir():
                        workspace_pkg = workspace_dir / "package.json"
                        if workspace_pkg.exists():
                            # Skip if already processed
                            if str(workspace_pkg.resolve()) in processed_packages:
                                continue
                            
                            # Calculate relative path for workspace_package field
                            try:
                                rel_path = workspace_pkg.relative_to(root_dir)
                                workspace_path = str(rel_path).replace("\\", "/")
                            except ValueError:
                                workspace_path = str(workspace_pkg)
                            
                            # Parse this workspace package
                            workspace_deps = parse_single_package(workspace_pkg, workspace_path)
                            deps.extend(workspace_deps)
                            processed_packages.add(str(workspace_pkg.resolve()))
        
        # Also check for Lerna configuration (lerna.json)
        lerna_json = root_dir / "lerna.json"
        if lerna_json.exists():
            try:
                with open(lerna_json, encoding="utf-8") as f:
                    lerna_data = json.load(f)
                
                lerna_packages = lerna_data.get("packages", [])
                for pattern in lerna_packages:
                    abs_pattern = str(root_dir / pattern)
                    if "*" in abs_pattern:
                        matched_paths = glob.glob(abs_pattern)
                        for matched_path in matched_paths:
                            matched_dir = Path(matched_path)
                            if matched_dir.is_dir():
                                workspace_pkg = matched_dir / "package.json"
                                if workspace_pkg.exists() and str(workspace_pkg.resolve()) not in processed_packages:
                                    try:
                                        rel_path = workspace_pkg.relative_to(root_dir)
                                        workspace_path = str(rel_path).replace("\\", "/")
                                    except ValueError:
                                        workspace_path = str(workspace_pkg)
                                    
                                    workspace_deps = parse_single_package(workspace_pkg, workspace_path)
                                    deps.extend(workspace_deps)
                                    processed_packages.add(str(workspace_pkg.resolve()))
            except (json.JSONDecodeError, KeyError):
                # Lerna.json parsing failed, continue without it
                pass
        
        # Check for pnpm-workspace.yaml
        pnpm_workspace = root_dir / "pnpm-workspace.yaml"
        if pnpm_workspace.exists():
            try:
                with open(pnpm_workspace, encoding="utf-8") as f:
                    pnpm_data = yaml.safe_load(f)
                
                pnpm_packages = pnpm_data.get("packages", [])
                for pattern in pnpm_packages:
                    abs_pattern = str(root_dir / pattern)
                    if "*" in abs_pattern:
                        matched_paths = glob.glob(abs_pattern)
                        for matched_path in matched_paths:
                            matched_dir = Path(matched_path)
                            if matched_dir.is_dir():
                                workspace_pkg = matched_dir / "package.json"
                                if workspace_pkg.exists() and str(workspace_pkg.resolve()) not in processed_packages:
                                    try:
                                        rel_path = workspace_pkg.relative_to(root_dir)
                                        workspace_path = str(rel_path).replace("\\", "/")
                                    except ValueError:
                                        workspace_path = str(workspace_pkg)
                                    
                                    workspace_deps = parse_single_package(workspace_pkg, workspace_path)
                                    deps.extend(workspace_deps)
                                    processed_packages.add(str(workspace_pkg.resolve()))
            except (yaml.YAMLError, KeyError):
                # pnpm-workspace.yaml parsing failed, continue without it
                pass
    
    except (json.JSONDecodeError, KeyError) as e:
        # Root package.json parsing for workspaces failed, but we already have root deps
        pass
    
    return deps


def _parse_pyproject_toml(path: Path) -> list[dict[str, Any]]:
    """Parse dependencies from pyproject.toml."""
    deps = []
    try:
        import tomllib
    except ImportError:
        # Python < 3.11
        try:
            import tomli as tomllib
        except ImportError:
            # Can't parse TOML without library
            print(f"Warning: Cannot parse {path} - tomllib not available")
            return deps
    
    # Calculate source path (relative if in subdirectory)
    try:
        source_path = path.relative_to(Path.cwd())
        source = str(source_path).replace("\\", "/")
    except ValueError:
        source = "pyproject.toml"
    
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        
        # Get project dependencies
        project_deps = data.get("project", {}).get("dependencies", [])
        for dep_spec in project_deps:
            name, version = _parse_python_dep_spec(dep_spec)
            if name:
                deps.append({
                    "name": name,
                    "version": version or "latest",
                    "manager": "py",
                    "files": [],
                    "source": source
                })
        
        # Also check optional dependencies
        optional = data.get("project", {}).get("optional-dependencies", {})
        for group_deps in optional.values():
            for dep_spec in group_deps:
                name, version = _parse_python_dep_spec(dep_spec)
                if name:
                    deps.append({
                        "name": name,
                        "version": version or "latest",
                        "manager": "py",
                        "files": [],
                        "source": source
                    })
    except Exception as e:
        print(f"Warning: Could not parse {path}: {e}")
    
    return deps


def _parse_requirements_txt(path: Path) -> list[dict[str, Any]]:
    """Parse dependencies from requirements.txt."""
    deps = []
    try:
        # Calculate source path (relative if in subdirectory)
        try:
            source_path = path.relative_to(Path.cwd())
            source = str(source_path).replace("\\", "/")
        except ValueError:
            source = path.name
        
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                # Skip special directives
                if line.startswith("-"):
                    continue
                
                # Strip inline comments and trailing whitespace
                if "#" in line:
                    line = line.split("#")[0].strip()
                
                name, version = _parse_python_dep_spec(line)
                if name:
                    deps.append({
                        "name": name,
                        "version": version or "latest",
                        "manager": "py",
                        "files": [],
                        "source": source
                    })
    except Exception as e:
        print(f"Warning: Could not parse {path}: {e}")
    
    return deps


def _parse_python_dep_spec(spec: str) -> tuple[str, str | None]:
    """
    Parse a Python dependency specification.
    Returns (name, version) tuple.
    """
    # Handle various formats:
    # package==1.2.3
    # package>=1.2.3
    # package~=1.2.3
    # package[extra]==1.2.3
    # package @ git+https://...
    
    # Remove extras
    spec = re.sub(r'\[.*?\]', '', spec)
    
    # Handle git URLs
    if "@" in spec and ("git+" in spec or "https://" in spec):
        name = spec.split("@")[0].strip()
        return (name, "git")
    
    # Parse version specs (allow dots, underscores, hyphens in package names)
    match = re.match(r'^([a-zA-Z0-9._-]+)\s*([><=~!]+)\s*(.+)$', spec)
    if match:
        name, op, version = match.groups()
        # For pinned versions, use exact version
        if op == "==":
            return (name, version)
        # For other operators, use the specified version as hint
        return (name, version)
    
    # No version specified
    return (spec.strip(), None)


def _clean_version(version_spec: str) -> str:
    """
    Clean version specification to get actual version.
    Handles Python (PEP 440) and npm (semver) operators.

    Examples:
    ^1.2.3 -> 1.2.3 (npm caret)
    ~1.2.3 -> 1.2.3 (npm/Python tilde)
    >=1.2.3 -> 1.2.3 (greater or equal)
    ==1.2.3 -> 1.2.3 (Python exact)
    !=1.2.3 -> 1.2.3 (Python not equal)
    ~=1.2.3 -> 1.2.3 (Python compatible)
    ===1.2.3 -> 1.2.3 (Python arbitrary)
    """
    # Remove ALL version operators (Python + npm)
    # Operators: ==, >=, <=, >, <, ~=, !=, ===, ^, ~, =
    version = re.sub(r'^[><=~!^]+', '', version_spec)
    # Handle ranges (use first version)
    if " " in version:
        version = version.split()[0]
    return version.strip()


def _parse_docker_compose(path: Path) -> list[dict[str, Any]]:
    """Parse Docker base images from docker-compose.yml files."""
    deps = []
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # Check if services key exists
        if not data or "services" not in data:
            return deps
        
        # Iterate through services
        for service_name, service_config in data["services"].items():
            if not isinstance(service_config, dict):
                continue
            
            # Extract image if present
            if "image" in service_config:
                image_spec = service_config["image"]
                # Parse image:tag format
                if ":" in image_spec:
                    name, tag = image_spec.rsplit(":", 1)
                else:
                    name = image_spec
                    tag = "latest"
                
                # Handle registry prefixes (e.g., docker.io/library/postgres)
                if "/" in name:
                    # Take the last part as the image name
                    name_parts = name.split("/")
                    if len(name_parts) >= 2:
                        # If it's library/image, use just image
                        if name_parts[-2] == "library":
                            name = name_parts[-1]
                        else:
                            # Keep org/image format
                            name = "/".join(name_parts[-2:])
                
                deps.append({
                    "name": name,
                    "version": tag,
                    "manager": "docker",
                    "files": [],
                    "source": path.name
                })
    except (yaml.YAMLError, KeyError, AttributeError) as e:
        print(f"Warning: Could not parse {path}: {e}")
    
    return deps


def _parse_dockerfile(path: Path) -> list[dict[str, Any]]:
    """Parse Docker base images from Dockerfile."""
    deps = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Look for FROM instructions
                if line.upper().startswith("FROM "):
                    # Extract image spec after FROM
                    image_spec = line[5:].strip()
                    
                    # Handle multi-stage builds (FROM image AS stage)
                    if " AS " in image_spec.upper():
                        image_spec = image_spec.split(" AS ")[0].strip()
                    elif " as " in image_spec:
                        image_spec = image_spec.split(" as ")[0].strip()
                    
                    # Skip scratch and build stages
                    if image_spec.lower() in ["scratch", "builder"]:
                        continue
                    
                    # Parse image:tag format
                    if ":" in image_spec:
                        name, tag = image_spec.rsplit(":", 1)
                    else:
                        name = image_spec
                        tag = "latest"
                    
                    # Handle registry prefixes
                    if "/" in name:
                        name_parts = name.split("/")
                        if len(name_parts) >= 2:
                            if name_parts[-2] == "library":
                                name = name_parts[-1]
                            else:
                                name = "/".join(name_parts[-2:])
                    
                    deps.append({
                        "name": name,
                        "version": tag,
                        "manager": "docker",
                        "files": [],
                        "source": str(path.relative_to(Path.cwd()))
                    })
    except Exception as e:
        print(f"Warning: Could not parse {path}: {e}")
    
    return deps


def _parse_cargo_deps(deps_dict: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    """Parse a Cargo.toml dependency section.

    Args:
        deps_dict: Dictionary from [dependencies] or [dev-dependencies]
        kind: 'normal' or 'dev'

    Returns:
        List of dependency dicts
    """
    deps = []

    for name, spec in deps_dict.items():
        if isinstance(spec, str):
            # Simple version: dep = "1.0"
            version = _clean_version(spec)
            features = []
        elif isinstance(spec, dict):
            # Dict format: dep = { version = "1.0", features = ["derive"] }
            version = _clean_version(spec.get("version", "*"))
            features = spec.get("features", [])
        else:
            continue

        deps.append({
            "name": name,
            "version": version,
            "manager": "cargo",
            "features": features,
            "kind": kind,
            "files": [],
            "source": "Cargo.toml"
        })

    return deps


def _parse_cargo_toml(path: Path) -> list[dict[str, Any]]:
    """Parse dependencies from Cargo.toml."""
    import logging
    logger = logging.getLogger(__name__)

    deps = []
    try:
        import tomllib
    except ImportError:
        # Python < 3.11
        try:
            import tomli as tomllib
        except ImportError:
            # Can't parse TOML without library
            logger.warning(f"Cannot parse {path} - tomllib not available")
            return deps

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        # Parse [dependencies] and [dev-dependencies]
        deps.extend(_parse_cargo_deps(data.get("dependencies", {}), kind="normal"))
        deps.extend(_parse_cargo_deps(data.get("dev-dependencies", {}), kind="dev"))

    except Exception as e:
        logger.error(f"Could not parse {path}: {e}")

    return deps


def write_deps_json(deps: list[dict[str, Any]], output_path: str = "./.pf/deps.json") -> None:
    """Write dependencies to JSON file."""
    try:
        output = sanitize_path(output_path, ".")
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(deps, f, indent=2, sort_keys=True)
    except SecurityError as e:
        raise SecurityError(f"Invalid output path: {e}")


def check_latest_versions(
    deps: list[dict[str, Any]],
    allow_net: bool = True,
    offline: bool = False,
    cache_file: str = "./.pf/deps_cache.json",
    allow_prerelease: bool = False
) -> dict[str, dict[str, Any]]:
    """
    Check latest versions from registries with caching.

    Args:
        deps: List of dependency objects
        allow_net: Whether network access is allowed
        offline: Force offline mode
        cache_file: Path to cache file
        allow_prerelease: Allow alpha/beta/rc versions (default: stable only)

    Returns dict keyed by "manager:name" with:
    {
        "locked": str,
        "latest": str,
        "delta": str,
        "is_outdated": bool,
        "last_checked": str (ISO timestamp)
    }
    """
    if offline or not allow_net:
        # Try to load from cache in offline mode
        cached_data = _load_deps_cache(cache_file)
        if cached_data:
            # Update locked versions from current deps
            for dep in deps:
                # For Docker, include version in key
                if dep['manager'] == 'docker':
                    key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
                else:
                    key = f"{dep['manager']}:{dep['name']}"
                if key in cached_data:
                    # Clean version to remove operators (==, >=, etc.)
                    locked_clean = _clean_version(dep["version"])
                    cached_data[key]["locked"] = locked_clean
                    cached_data[key]["is_outdated"] = cached_data[key]["latest"] != locked_clean
                    cached_data[key]["delta"] = _calculate_version_delta(locked_clean, cached_data[key]["latest"])
        return cached_data or {}
    
    # Load existing cache
    cache = _load_deps_cache(cache_file)
    latest_info = {}
    needs_check = []
    
    # FIRST PASS: Check what's in cache and still valid
    for dep in deps:
        # For Docker, include version in key since different tags need different checks
        if dep['manager'] == 'docker':
            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
        else:
            key = f"{dep['manager']}:{dep['name']}"

        if key in latest_info:
            continue  # Already processed

        # Check if we have valid cached data (24 hours for deps)
        if key in cache and _is_cache_valid(cache[key], hours=24):
            # Update locked version from current deps
            # Clean version to remove operators (==, >=, etc.)
            locked_clean = _clean_version(dep["version"])
            cache[key]["locked"] = locked_clean
            cache[key]["is_outdated"] = cache[key]["latest"] != locked_clean
            cache[key]["delta"] = _calculate_version_delta(locked_clean, cache[key]["latest"])
            latest_info[key] = cache[key]
        else:
            needs_check.append(dep)
    
    # Early exit if everything is cached
    if not needs_check:
        return latest_info
    
    # SECOND PASS: Check only what needs updating, with per-service rate limiting
    npm_rate_limited_until = 0
    pypi_rate_limited_until = 0
    docker_rate_limited_until = 0
    
    for dep in needs_check:
        # For Docker, include version in key since different tags have different upgrade paths
        # (e.g., python:3.11-slim vs python:3.12-alpine need separate checks)
        if dep['manager'] == 'docker':
            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
        else:
            key = f"{dep['manager']}:{dep['name']}"
        current_time = time.time()
        
        # Skip if this service is rate limited
        if dep["manager"] == "npm" and current_time < npm_rate_limited_until:
            # Use cached data if available, even if expired
            if key in cache:
                latest_info[key] = cache[key]
            continue
        elif dep["manager"] == "py" and current_time < pypi_rate_limited_until:
            if key in cache:
                latest_info[key] = cache[key]
            continue
        elif dep["manager"] == "docker" and current_time < docker_rate_limited_until:
            if key in cache:
                latest_info[key] = cache[key]
            continue
        
        try:
            if dep["manager"] == "npm":
                latest = _check_npm_latest(dep["name"])
            elif dep["manager"] == "py":
                # Pass allow_prerelease flag for pre-release filtering
                latest = _check_pypi_latest(dep["name"], allow_prerelease)
            elif dep["manager"] == "docker":
                # Pass current tag for base image matching and allow_prerelease flag
                current_tag = dep.get("version", "")
                latest = _check_dockerhub_latest(dep["name"], current_tag, allow_prerelease)
            else:
                continue
            
            if latest:
                # Clean version to remove operators (==, >=, etc.)
                locked = _clean_version(dep["version"])
                delta = _calculate_version_delta(locked, latest)
                latest_info[key] = {
                    "locked": locked,
                    "latest": latest,
                    "delta": delta,
                    "is_outdated": locked != latest,
                    "last_checked": datetime.now().isoformat()
                }
                # Rate limiting: service-specific delays for optimal performance
                if dep["manager"] == "npm":
                    time.sleep(RATE_LIMIT_NPM)  # 0.1s for npm
                elif dep["manager"] == "py":
                    time.sleep(RATE_LIMIT_PYPI)  # 0.2s for PyPI
                elif dep["manager"] == "docker":
                    time.sleep(RATE_LIMIT_DOCKER)  # 0.2s for Docker Hub
        except (urllib.error.URLError, urllib.error.HTTPError, http.client.RemoteDisconnected,
                TimeoutError, json.JSONDecodeError, KeyError, ValueError) as e:
            error_msg = f"{type(e).__name__}: {str(e)[:50]}"
            
            # Handle rate limiting and connection errors specifically
            if ("429" in str(e) or "rate" in str(e).lower() or 
                "RemoteDisconnected" in str(e) or "closed connection" in str(e).lower()):
                # Set rate limit expiry for this service
                if dep["manager"] == "npm":
                    npm_rate_limited_until = current_time + RATE_LIMIT_BACKOFF
                elif dep["manager"] == "py":
                    pypi_rate_limited_until = current_time + RATE_LIMIT_BACKOFF
                elif dep["manager"] == "docker":
                    docker_rate_limited_until = current_time + RATE_LIMIT_BACKOFF
            
            # Use cached data if available, even if expired
            if key in cache:
                latest_info[key] = cache[key]
                latest_info[key]["error"] = error_msg
            else:
                # Clean version to remove operators (==, >=, etc.)
                locked = _clean_version(dep["version"])
                latest_info[key] = {
                    "locked": locked,
                    "latest": None,
                    "delta": None,
                    "is_outdated": False,
                    "error": error_msg,
                    "last_checked": datetime.now().isoformat()
                }
            continue
    
    # Save updated cache
    _save_deps_cache(latest_info, cache_file)
    
    return latest_info


def _load_deps_cache(cache_file: str) -> dict[str, dict[str, Any]]:
    """
    Load the dependency cache from runtime database.

    ARCHITECTURE NOTE:
    Cache is stored in .pf/runtime.db (NOT repo_index.db) to avoid interference
    with `aud full` which regenerates repo_index.db from scratch.

    Separation of concerns:
    - .pf/repo_index.db: Indexer-managed, wiped on `aud full`
    - .pf/graphs.db: Graph-managed, regenerated on graph build
    - .pf/runtime.db: Runtime-managed, persistent across runs (THIS)

    Returns empty dict if cache doesn't exist or is invalid.
    """
    import sqlite3

    # Use runtime.db instead of JSON file
    # cache_file is typically "./.pf/deps_cache.json"
    # Extract .pf directory and use it for runtime.db
    cache_path = Path(cache_file)
    pf_dir = cache_path.parent  # ./.pf
    db_path = pf_dir / "runtime.db"

    try:
        if not db_path.exists():
            return {}

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='dependency_cache'
        """)

        if not cursor.fetchone():
            conn.close()
            return {}

        # Load all cache entries
        cursor.execute("""
            SELECT cache_key, locked, latest, delta, is_outdated, last_checked, error
            FROM dependency_cache
        """)

        cache = {}
        for row in cursor.fetchall():
            key, locked, latest, delta, is_outdated, last_checked, error = row
            cache[key] = {
                "locked": locked,
                "latest": latest,
                "delta": delta,
                "is_outdated": bool(is_outdated),
                "last_checked": last_checked
            }
            if error:
                cache[key]["error"] = error

        conn.close()
        return cache

    except (sqlite3.Error, OSError):
        return {}


def _save_deps_cache(latest_info: dict[str, dict[str, Any]], cache_file: str) -> None:
    """
    Save the dependency cache to runtime database.
    Merges with existing cache to preserve data for packages not in current check.

    Uses UPSERT (INSERT OR REPLACE) to handle updates atomically.
    """
    import sqlite3

    # Use runtime.db instead of JSON file
    # cache_file is typically "./.pf/deps_cache.json"
    # Extract .pf directory and use it for runtime.db
    cache_path = Path(cache_file)
    pf_dir = cache_path.parent  # ./.pf
    db_path = pf_dir / "runtime.db"

    try:
        # Ensure .pf directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table if not exists (schema)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependency_cache (
                cache_key TEXT PRIMARY KEY,
                locked TEXT NOT NULL,
                latest TEXT,
                delta TEXT,
                is_outdated INTEGER NOT NULL,
                last_checked TEXT NOT NULL,
                error TEXT
            )
        """)

        # Upsert each entry (merge new data with existing)
        for key, info in latest_info.items():
            cursor.execute("""
                INSERT OR REPLACE INTO dependency_cache
                (cache_key, locked, latest, delta, is_outdated, last_checked, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                key,
                info.get("locked", ""),
                info.get("latest"),
                info.get("delta"),
                1 if info.get("is_outdated") else 0,
                info.get("last_checked", ""),
                info.get("error")
            ))

        conn.commit()
        conn.close()

    except (sqlite3.Error, OSError):
        pass  # Fail silently if can't write cache


def _is_cache_valid(cached_item: dict[str, Any], hours: int = 24) -> bool:
    """
    Check if a cached item is still valid based on age.
    Default is 24 hours for dependency version checks.
    """
    try:
        if "last_checked" not in cached_item:
            return False
        last_checked = datetime.fromisoformat(cached_item["last_checked"])
        age = datetime.now() - last_checked
        return age.total_seconds() < (hours * 3600)
    except (ValueError, KeyError):
        return False


def _check_npm_latest(package_name: str) -> str | None:
    """Fetch latest version from npm registry."""
    import urllib.request
    import urllib.error
    
    # Validate and sanitize package name
    if not validate_package_name(package_name, "npm"):
        return None
    
    # URL-encode the package name for safety
    safe_package_name = sanitize_url_component(package_name)
    url = f"https://registry.npmjs.org/{safe_package_name}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            return data.get("dist-tags", {}).get("latest")
    except (urllib.error.URLError, http.client.RemoteDisconnected, json.JSONDecodeError, KeyError):
        return None


def _is_prerelease_version(version: str) -> bool:
    """
    Detect if a version string is a pre-release.

    Checks for common pre-release markers:
    - alpha: 1.0a1, 1.0.0a1, 1.0-alpha1
    - beta: 1.0b1, 1.0.0b1, 1.0-beta1
    - rc: 1.0rc1, 1.0.0rc1, 1.0-rc1
    - dev: 1.0.dev0, 1.0-dev

    Args:
        version: Version string to check

    Returns:
        True if pre-release, False if stable
    """
    version_lower = version.lower()

    # PEP 440 pre-release markers
    prerelease_markers = [
        'a', 'alpha',   # Alpha
        'b', 'beta',    # Beta
        'rc', 'c',      # Release candidate
        'dev',          # Development
        'pre',          # Pre-release
    ]

    for marker in prerelease_markers:
        # Check for marker followed by a digit (e.g., "a1", "rc2")
        if re.search(rf'[.-]?{marker}\d', version_lower):
            return True
        # Check for standalone marker at end (e.g., "1.0-dev")
        if version_lower.endswith(f'-{marker}') or version_lower.endswith(f'.{marker}'):
            return True

    return False


def _parse_pypi_version(version_str: str) -> tuple:
    """
    Parse PyPI version string into comparable tuple for semantic versioning.

    Handles standard formats: X.Y.Z, X.Y, X
    Handles date-based versions: YYYYMMDD, YYYY.MM.DD

    Args:
        version_str: Version string from PyPI

    Returns:
        Tuple of integers for comparison, e.g., (1, 18, 2)

    Examples:
        "1.18.2" -> (1, 18, 2)
        "25.11.0" -> (25, 11, 0)
        "2.9" -> (2, 9, 0)
        "4" -> (4, 0, 0)
    """
    # Extract numeric parts only (ignore suffixes like .post1, etc.)
    # Match up to 4 numeric parts (major.minor.patch.micro)
    match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?', version_str)
    if match:
        parts = match.groups()
        # Convert to integers, default to 0 for missing parts
        return tuple(int(p) if p else 0 for p in parts)

    # Fallback: return (0, 0, 0, 0) for unparseable versions
    return (0, 0, 0, 0)


def _check_pypi_latest(package_name: str, allow_prerelease: bool = False) -> str | None:
    """
    Fetch latest stable version from PyPI using semantic version comparison.

    Args:
        package_name: Package name
        allow_prerelease: If True, allow pre-release versions

    Returns:
        Latest version string, or None if unavailable
    """
    import urllib.request
    import urllib.error

    # Validate package name
    if not validate_package_name(package_name, "py"):
        return None

    # Normalize package name for PyPI (replace underscores with hyphens)
    normalized_name = package_name.replace('_', '-')
    # Sanitize for URL
    safe_package_name = sanitize_url_component(normalized_name)
    url = f"https://pypi.org/pypi/{safe_package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

            # If allow_prerelease, just return the latest version
            if allow_prerelease:
                return data.get("info", {}).get("version")

            # Otherwise, filter to stable versions only
            # Get all releases
            releases = data.get("releases", {})
            if not releases:
                # Fallback to info.version if no releases list
                version = data.get("info", {}).get("version")
                # Check if it's stable
                if version and not _is_prerelease_version(version):
                    return version
                return None

            # Filter to stable versions only
            stable_versions = []
            for version_str in releases.keys():
                if not _is_prerelease_version(version_str):
                    stable_versions.append(version_str)

            if not stable_versions:
                # No stable versions found, return None
                return None

            # Return the highest stable version using SEMANTIC COMPARISON
            # Sort by parsed version tuple, not string comparison
            stable_versions.sort(key=_parse_pypi_version, reverse=True)
            return stable_versions[0]

    except (urllib.error.URLError, http.client.RemoteDisconnected, json.JSONDecodeError, KeyError):
        return None


def _parse_docker_tag(tag: str) -> dict[str, Any] | None:
    """
    Parse Docker tag into semantic components for proper version comparison.

    Args:
        tag: Docker tag string (e.g., "17-alpine3.21", "3.15.0a1-windowsservercore")

    Returns:
        Dict with version tuple, variant, and stability, or None if unparseable
        {
            'tag': str,              # Original tag
            'version': tuple,        # (major, minor, patch) for semantic comparison
            'variant': str,          # Base image variant (alpine, bookworm, etc)
            'stability': str         # 'stable', 'alpha', 'beta', 'rc', 'dev'
        }
    """
    # Skip meta tags
    if tag in ["latest", "alpine", "slim", "bullseye", "bookworm", "main", "master"]:
        return None

    # Extract semantic version (major.minor.patch) FIRST
    # Matches: "17", "17.2", "17.2.1", "3.15.0a1", etc.
    match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', tag)
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)

    # Extract variant (everything after version)
    variant = tag[match.end():].lstrip('-')
    variant_lower = variant.lower()

    # Detect stability markers ONLY in the variant/suffix (NOT the whole tag)
    # This prevents "alpine" from triggering "a" marker
    stability = 'stable'

    # Check for pre-release markers (CRITICAL for production safety)
    # Only check the variant portion to avoid false positives like "alpine"
    if variant_lower.startswith('a') or any(marker in variant_lower for marker in ['alpha', 'a1', 'a2', 'a3']):
        # Check if it's actually "alpine" (which is stable, not alpha)
        if not variant_lower.startswith('alpine'):
            stability = 'alpha'
    elif variant_lower.startswith('b') or any(marker in variant_lower for marker in ['beta', 'b1', 'b2']):
        # Check if it's "bookworm" or "bullseye" (stable debian releases)
        if not (variant_lower.startswith('bookworm') or variant_lower.startswith('bullseye') or variant_lower.startswith('buster')):
            stability = 'beta'
    elif 'rc' in variant_lower or any(marker in variant_lower for marker in ['rc1', 'rc2', 'rc3']):
        stability = 'rc'
    elif any(marker in variant_lower for marker in ['nightly', 'dev', 'snapshot', 'edge']):
        stability = 'dev'

    return {
        'tag': tag,
        'version': (major, minor, patch),
        'variant': variant,
        'stability': stability
    }


def _extract_base_preference(current_tag: str) -> str:
    """
    Extract base image preference from current tag.

    Args:
        current_tag: Current Docker tag (e.g., "17-alpine3.21")

    Returns:
        Base type: 'alpine', 'bookworm', 'bullseye', 'windowsservercore', etc.
        Empty string if no recognizable base.
    """
    tag_lower = current_tag.lower()

    # Check for base image types (order matters - most specific first)
    base_types = [
        'windowsservercore', 'nanoserver',       # Windows bases
        'alpine', 'slim', 'distroless',          # Linux lightweight
        'bookworm', 'bullseye', 'buster',        # Debian bases
        'jammy', 'focal', 'bionic',              # Ubuntu bases
        'trixie', 'sid',                         # Debian unstable
    ]

    for base in base_types:
        if base in tag_lower:
            return base

    return ''  # No recognizable base


def _check_dockerhub_latest(image_name: str, current_tag: str = "", allow_prerelease: bool = False) -> str | None:
    """
    Fetch latest stable version from Docker Hub with semantic version comparison.

    CRITICAL: This function prevents production disasters by:
    1. Using semantic version comparison (not string sort)
    2. Filtering pre-release versions (alpha/beta/rc)
    3. Preserving base image consistency (alpine stays alpine)

    Args:
        image_name: Docker image name (e.g., "postgres", "python")
        current_tag: Current tag to extract base preference (e.g., "17-alpine3.21")
        allow_prerelease: If True, allow alpha/beta/rc versions

    Returns:
        Best matching tag, or None if unavailable
    """
    import urllib.request
    import urllib.error

    # Validate image name
    if not validate_package_name(image_name, "docker"):
        return None
    
    # For official images, use library/ prefix
    if "/" not in image_name:
        image_name = f"library/{image_name}"

    # Sanitize image name for URL
    safe_image_name = sanitize_url_component(image_name)

    # Docker Hub API endpoint for tags (fetch 100 tags to ensure we get latest versions)
    url = f"https://hub.docker.com/v2/repositories/{safe_image_name}/tags?page_size=100"

    try:
        # Create request with proper headers
        req = urllib.request.Request(url)
        req.add_header('User-Agent', f'TheAuditor/{__version__}')

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())

            # Parse the results to find latest stable version
            tags = data.get("results", [])
            if not tags:
                return None

            # Parse all tags with semantic version parser
            parsed_tags = []
            for tag in tags:
                tag_name = tag.get("name", "")
                parsed = _parse_docker_tag(tag_name)
                if parsed:
                    parsed_tags.append(parsed)

            if not parsed_tags:
                # No parseable version tags found, fallback to "latest"
                for tag in tags:
                    if tag.get("name") == "latest":
                        return "latest"
                return None

            # Filter by stability (CRITICAL for production safety)
            if allow_prerelease:
                # Allow all stability levels
                candidates = parsed_tags
            else:
                # Filter to stable only
                stable = [t for t in parsed_tags if t['stability'] == 'stable']
                if not stable:
                    # No stable versions, allow RC with warning (better than nothing)
                    stable = [t for t in parsed_tags if t['stability'] in ['stable', 'rc']]
                    if not stable:
                        # Last resort: use any version (shouldn't happen for official images)
                        stable = parsed_tags
                candidates = stable

            # Extract base image preference from current tag
            if current_tag:
                base_preference = _extract_base_preference(current_tag)
                if base_preference:
                    # Filter to matching base images
                    matching_base = [t for t in candidates if base_preference in t['variant'].lower()]
                    if matching_base:
                        candidates = matching_base
                    else:
                        # No matching base found - don't suggest upgrade with different base
                        # This prevents alpine -> bookworm drift
                        return None

            # Sort by semantic version tuple (FIXED: no more string sort!)
            # Sort order: (major DESC, minor DESC, patch DESC)
            candidates.sort(key=lambda x: x['version'], reverse=True)

            # Return best match
            return candidates[0]['tag']

    except (urllib.error.URLError, http.client.RemoteDisconnected, json.JSONDecodeError, KeyError) as e:
        # Docker Hub API might require auth or have rate limits
        return None


def _calculate_version_delta(locked: str, latest: str) -> str:
    """
    Calculate semantic version delta.
    Returns: "major", "minor", "patch", "equal", or "unknown"

    Handles both simple versions (1.2.3) and Docker tags (17-alpine3.21).
    """
    # Try Docker tag parsing first (handles "17-alpine3.21" format)
    locked_parsed = _parse_docker_tag(locked)
    latest_parsed = _parse_docker_tag(latest)

    if locked_parsed and latest_parsed:
        # Use parsed Docker tag versions
        locked_parts = list(locked_parsed['version'])
        latest_parts = list(latest_parsed['version'])
    else:
        # Fall back to simple version parsing
        try:
            # Extract just the numeric parts before any hyphen (for Docker tags)
            locked_clean = locked.split('-')[0]
            latest_clean = latest.split('-')[0]

            locked_parts = [int(x) for x in locked_clean.split(".")[:3]]
            latest_parts = [int(x) for x in latest_clean.split(".")[:3]]
        except (ValueError, IndexError):
            return "unknown"

    # Pad with zeros if needed
    while len(locked_parts) < 3:
        locked_parts.append(0)
    while len(latest_parts) < 3:
        latest_parts.append(0)

    if locked_parts == latest_parts:
        return "equal"
    elif latest_parts[0] > locked_parts[0]:
        return "major"
    elif latest_parts[1] > locked_parts[1]:
        return "minor"
    elif latest_parts[2] > locked_parts[2]:
        return "patch"
    else:
        return "unknown"  # locked is newer than latest?


def write_deps_latest_json(
    latest_info: dict[str, dict[str, Any]], 
    output_path: str = "./.pf/deps_latest.json"
) -> None:
    """Write latest version info to JSON file."""
    try:
        output = sanitize_path(output_path, ".")
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, "w", encoding="utf-8") as f:
            json.dump(latest_info, f, indent=2, sort_keys=True)
    except SecurityError as e:
        raise SecurityError(f"Invalid output path: {e}")


def _create_versioned_backup(path: Path) -> Path:
    """
    Create a versioned backup that won't overwrite existing backups.
    
    Creates backups like:
    - package.json.bak (first backup)
    - package.json.bak.1 (second backup)
    - package.json.bak.2 (third backup)
    
    Returns the path to the created backup.
    """
    import shutil
    
    base_backup = path.with_suffix(path.suffix + ".bak")
    
    # If no backup exists, use the base name
    if not base_backup.exists():
        shutil.copy2(path, base_backup)
        return base_backup
    
    # Find the next available backup number
    counter = 1
    while True:
        versioned_backup = Path(f"{base_backup}.{counter}")
        if not versioned_backup.exists():
            shutil.copy2(path, versioned_backup)
            return versioned_backup
        counter += 1
        # Safety limit to prevent infinite loops
        if counter > 100:
            raise RuntimeError(f"Too many backup files for {path}")


def upgrade_all_deps(
    root_path: str,
    latest_info: dict[str, dict[str, Any]],
    deps_list: list[dict[str, Any]]
) -> dict[str, int]:
    """
    YOLO MODE: Upgrade all dependencies to latest versions.
    Rewrites requirements.txt, package.json, and pyproject.toml with latest versions.
    
    Returns dict with counts of upgraded packages per file type.
    """
    import shutil
    from datetime import datetime
    
    root = Path(root_path)
    upgraded = {
        "requirements.txt": 0,
        "package.json": 0,
        "pyproject.toml": 0
    }
    
    # Group deps by source file (including workspace path for monorepos)
    deps_by_source = {}
    for dep in deps_list:
        # For npm deps in workspaces, use workspace_package field if available
        if dep.get("manager") == "npm" and "workspace_package" in dep:
            source_key = dep["workspace_package"]
        else:
            source_key = dep.get("source", "")
        
        if source_key not in deps_by_source:
            deps_by_source[source_key] = []
        deps_by_source[source_key].append(dep)
    
    # Upgrade requirements*.txt files (including in subdirectories)
    all_req_files = list(root.glob("requirements*.txt"))
    all_req_files.extend(root.glob("*/requirements*.txt"))
    all_req_files.extend(root.glob("services/*/requirements*.txt"))
    all_req_files.extend(root.glob("apps/*/requirements*.txt"))
    
    for req_file in all_req_files:
        # Use relative path as key for deps_by_source
        try:
            rel_path = req_file.relative_to(root)
            source_key = str(rel_path).replace("\\", "/")
        except ValueError:
            source_key = req_file.name
        
        if source_key in deps_by_source:
            count = _upgrade_requirements_txt(req_file, latest_info, deps_by_source[source_key])
            upgraded["requirements.txt"] += count
        elif req_file.name in deps_by_source:
            # Fallback to just filename for backward compatibility
            count = _upgrade_requirements_txt(req_file, latest_info, deps_by_source[req_file.name])
            upgraded["requirements.txt"] += count
    
    # Upgrade all package.json files (root and workspaces)
    for source_key, source_deps in deps_by_source.items():
        # Skip non-npm dependencies
        if not source_deps or source_deps[0].get("manager") != "npm":
            continue
            
        # Determine the actual file path
        if source_key == "package.json":
            # Root package.json
            package_path = root / "package.json"
        elif source_key.endswith("package.json"):
            # Workspace package.json (e.g., "backend/package.json")
            package_path = root / source_key
        else:
            continue
            
        if package_path.exists():
            count = _upgrade_package_json(package_path, latest_info, source_deps)
            upgraded["package.json"] += count
    
    # Upgrade all pyproject.toml files (root and subdirectories)
    all_pyproject_files = [root / "pyproject.toml"] if (root / "pyproject.toml").exists() else []
    all_pyproject_files.extend(root.glob("*/pyproject.toml"))
    all_pyproject_files.extend(root.glob("services/*/pyproject.toml"))
    all_pyproject_files.extend(root.glob("apps/*/pyproject.toml"))

    for pyproject_file in all_pyproject_files:
        # Use relative path as key
        try:
            rel_path = pyproject_file.relative_to(root)
            source_key = str(rel_path).replace("\\", "/")
        except ValueError:
            source_key = "pyproject.toml"

        if source_key in deps_by_source:
            count = _upgrade_pyproject_toml(pyproject_file, latest_info, deps_by_source[source_key])
            upgraded["pyproject.toml"] += count
        elif "pyproject.toml" in deps_by_source and pyproject_file == root / "pyproject.toml":
            # Backward compatibility for root pyproject.toml
            count = _upgrade_pyproject_toml(pyproject_file, latest_info, deps_by_source["pyproject.toml"])
            upgraded["pyproject.toml"] += count

    # Upgrade Docker Compose files
    docker_compose_files = list(root.glob("docker-compose*.yml")) + list(root.glob("docker-compose*.yaml"))
    upgraded["docker-compose"] = 0

    for compose_file in docker_compose_files:
        # Use relative path as key
        try:
            rel_path = compose_file.relative_to(root)
            source_key = str(rel_path).replace("\\", "/")
        except ValueError:
            source_key = compose_file.name

        # Collect all Docker deps from this file
        docker_deps = []
        for source_key_check in [source_key, compose_file.name]:
            if source_key_check in deps_by_source:
                docker_deps = [d for d in deps_by_source[source_key_check] if d.get("manager") == "docker"]
                break

        if docker_deps:
            count = _upgrade_docker_compose(compose_file, latest_info, docker_deps)
            upgraded["docker-compose"] += count

    # Upgrade Dockerfiles
    dockerfiles = list(root.glob("**/Dockerfile"))
    upgraded["dockerfile"] = 0

    for dockerfile in dockerfiles:
        # Use relative path as key
        try:
            rel_path = dockerfile.relative_to(root)
            source_key = str(rel_path).replace("\\", "/")
        except ValueError:
            source_key = str(dockerfile)

        # Collect Docker deps from this file
        docker_deps = []
        if source_key in deps_by_source:
            docker_deps = [d for d in deps_by_source[source_key] if d.get("manager") == "docker"]

        if docker_deps:
            count = _upgrade_dockerfile(dockerfile, latest_info, docker_deps)
            upgraded["dockerfile"] += count

    return upgraded


def _upgrade_requirements_txt(
    path: Path,
    latest_info: dict[str, dict[str, Any]],
    deps: list[dict[str, Any]]
) -> int:
    """Upgrade a requirements.txt file to latest versions."""
    # Sanitize path
    try:
        safe_path = sanitize_path(str(path), ".")
    except SecurityError:
        return 0  # Skip files outside project root
    
    # Create versioned backup
    backup_path = _create_versioned_backup(safe_path)
    
    # Read current file
    with open(safe_path, encoding="utf-8") as f:
        lines = f.readlines()
    
    # Build package name to latest version map
    latest_versions = {}
    for dep in deps:
        key = f"py:{dep['name']}"
        if key in latest_info:
            latest_versions[dep['name']] = latest_info[key]['latest']
    
    # Rewrite lines with latest versions
    updated_lines = []
    count = 0
    
    for line in lines:
        original_line = line
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith("#") or line.startswith("-"):
            updated_lines.append(original_line)
            continue
        
        # Parse package name
        name, _ = _parse_python_dep_spec(line)
        
        if name and name in latest_versions:
            # Replace with latest version
            updated_lines.append(f"{name}=={latest_versions[name]}\n")
            count += 1
        else:
            updated_lines.append(original_line)
    
    # Write updated file
    with open(safe_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)
    
    return count


def _upgrade_package_json(
    path: Path,
    latest_info: dict[str, dict[str, Any]],
    deps: list[dict[str, Any]]
) -> int:
    """Upgrade package.json to latest versions."""
    import shutil
    
    # Sanitize path
    try:
        safe_path = sanitize_path(str(path), ".")
    except SecurityError:
        return 0  # Skip files outside project root
    
    # Create versioned backup
    backup_path = _create_versioned_backup(safe_path)
    
    # Read current file
    with open(safe_path, encoding="utf-8") as f:
        data = json.load(f)
    
    count = 0
    
    # Update dependencies
    if "dependencies" in data:
        for name in data["dependencies"]:
            key = f"npm:{name}"
            if key in latest_info:
                data["dependencies"][name] = latest_info[key]["latest"]
                count += 1
    
    # Update devDependencies
    if "devDependencies" in data:
        for name in data["devDependencies"]:
            key = f"npm:{name}"
            if key in latest_info:
                data["devDependencies"][name] = latest_info[key]["latest"]
                count += 1
    
    # Write updated file
    with open(safe_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Add trailing newline
    
    return count


def _upgrade_pyproject_toml(
    path: Path,
    latest_info: dict[str, dict[str, Any]],
    deps: list[dict[str, Any]]
) -> int:
    """Upgrade pyproject.toml to latest versions - handles ALL sections."""
    import shutil
    import re
    
    # Sanitize path
    try:
        safe_path = sanitize_path(str(path), ".")
    except SecurityError:
        return 0  # Skip files outside project root
    
    # Create versioned backup
    backup_path = _create_versioned_backup(safe_path)
    
    # Read entire file as string for regex replacement
    with open(safe_path, encoding="utf-8") as f:
        content = f.read()
    
    count = 0
    updated_packages = {}  # Track all updates: package -> [(old, new)]
    
    # For each package in latest_info
    for key, info in latest_info.items():
        if not key.startswith("py:"):
            continue
        
        package_name = key[3:]  # Remove "py:" prefix
        latest_version = info.get("latest")
        
        if not latest_version:
            continue
        
        # Pattern to match this package anywhere in the file
        # Matches: "package==X.Y.Z" with any version number
        pattern = rf'"{package_name}==([^"]+)"'
        
        # Replace ALL occurrences at once using re.sub with a function
        def replacer(match):
            old_version = match.group(1)
            if old_version != latest_version:
                # Track the update
                if package_name not in updated_packages:
                    updated_packages[package_name] = []
                updated_packages[package_name].append((old_version, latest_version))
                return f'"{package_name}=={latest_version}"'
            return match.group(0)  # No change
        
        # Replace all occurrences in one pass
        new_content = re.sub(pattern, replacer, content)
        
        # Update count only if package was actually updated
        if package_name in updated_packages and content != new_content:
            count += 1
            content = new_content
    
    # Write updated content
    with open(safe_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    # Report what was updated
    total_occurrences = 0
    # Use ASCII characters on Windows
    check_mark = "[OK]" if IS_WINDOWS else "✓"
    arrow = "->" if IS_WINDOWS else "→"
    for package, updates in updated_packages.items():
        total_occurrences += len(updates)
        if len(updates) == 1:
            print(f"  {check_mark} {package}: {updates[0][0]} {arrow} {updates[0][1]}")
        else:
            print(f"  {check_mark} {package}: {updates[0][0]} {arrow} {updates[0][1]} ({len(updates)} occurrences)")
    
    # Return total occurrences updated, not just unique packages
    return total_occurrences


def _upgrade_docker_compose(
    path: Path,
    latest_info: dict[str, dict[str, Any]],
    deps: list[dict[str, Any]]
) -> int:
    """Upgrade docker-compose.yml to latest Docker image versions."""
    # Sanitize path
    try:
        safe_path = sanitize_path(str(path), ".")
    except SecurityError:
        return 0  # Skip files outside project root

    # Create versioned backup
    backup_path = _create_versioned_backup(safe_path)

    # Read current file
    with open(safe_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Build image name to latest version map
    latest_versions = {}
    for dep in deps:
        # Docker images use "docker:name:version" as key
        key = f"docker:{dep['name']}:{dep.get('version', '')}"
        if key in latest_info:
            latest_versions[dep['name']] = latest_info[key]['latest']

    # Rewrite lines with latest versions
    updated_lines = []
    count = 0
    updated_images = {}  # Track what was updated: image -> (old_tag, new_tag)

    for line in lines:
        original_line = line
        stripped = line.strip()

        # Look for image: lines
        if stripped.startswith("image:"):
            # Extract image spec
            image_spec = stripped[6:].strip()

            # Parse image:tag format
            if ":" in image_spec:
                # Handle registry prefixes (e.g., docker.io/library/postgres:17)
                name_part, tag = image_spec.rsplit(":", 1)

                # Extract base image name (last part of path)
                if "/" in name_part:
                    name_parts = name_part.split("/")
                    if len(name_parts) >= 2 and name_parts[-2] == "library":
                        base_name = name_parts[-1]
                    else:
                        base_name = "/".join(name_parts[-2:])
                else:
                    base_name = name_part

                # Check if we have a latest version for this image
                if base_name in latest_versions:
                    new_tag = latest_versions[base_name]
                    old_tag = tag
                    if old_tag != new_tag:
                        # Track the update
                        updated_images[base_name] = (old_tag, new_tag)
                        # Replace with new tag, preserving indentation and registry prefix
                        new_image_spec = f"{name_part}:{new_tag}"
                        indent = len(line) - len(line.lstrip())
                        updated_lines.append(" " * indent + f"image: {new_image_spec}\n")
                        count += 1
                    else:
                        updated_lines.append(original_line)
                else:
                    updated_lines.append(original_line)
            else:
                updated_lines.append(original_line)
        else:
            updated_lines.append(original_line)

    # Write updated file
    with open(safe_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    # Print what was updated
    check_mark = "[OK]" if IS_WINDOWS else "✓"
    arrow = "->" if IS_WINDOWS else "→"
    for image, (old_tag, new_tag) in updated_images.items():
        print(f"  {check_mark} {image}: {old_tag} {arrow} {new_tag}")

    return count


def _upgrade_dockerfile(
    path: Path,
    latest_info: dict[str, dict[str, Any]],
    deps: list[dict[str, Any]]
) -> int:
    """Upgrade Dockerfile to latest Docker base image versions."""
    # Sanitize path
    try:
        safe_path = sanitize_path(str(path), ".")
    except SecurityError:
        return 0  # Skip files outside project root

    # Create versioned backup
    backup_path = _create_versioned_backup(safe_path)

    # Read current file
    with open(safe_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Build image name to latest version map
    latest_versions = {}
    for dep in deps:
        # Docker images use "docker:name:version" as key
        key = f"docker:{dep['name']}:{dep.get('version', '')}"
        if key in latest_info:
            latest_versions[dep['name']] = latest_info[key]['latest']

    # Rewrite lines with latest versions
    updated_lines = []
    count = 0
    updated_images = {}  # Track what was updated: image -> (old_tag, new_tag)

    for line in lines:
        original_line = line
        stripped = line.strip().upper()

        # Look for FROM instructions
        if stripped.startswith("FROM "):
            # Extract image spec after FROM
            image_spec = line[5:].strip()

            # Handle multi-stage builds (FROM image AS stage)
            if " AS " in image_spec.upper():
                image_part, as_part = image_spec.split(" AS ", 1)
                image_spec = image_part.strip()
                as_clause = f" AS {as_part}"
            elif " as " in image_spec:
                image_part, as_part = image_spec.split(" as ", 1)
                image_spec = image_part.strip()
                as_clause = f" as {as_part}"
            else:
                as_clause = ""

            # Skip scratch and build stages
            if image_spec.lower() in ["scratch", "builder"]:
                updated_lines.append(original_line)
                continue

            # Parse image:tag format
            if ":" in image_spec:
                name_part, tag = image_spec.rsplit(":", 1)

                # Extract base image name
                if "/" in name_part:
                    name_parts = name_part.split("/")
                    if len(name_parts) >= 2 and name_parts[-2] == "library":
                        base_name = name_parts[-1]
                    else:
                        base_name = "/".join(name_parts[-2:])
                else:
                    base_name = name_part

                # Check if we have a latest version for this image
                if base_name in latest_versions:
                    new_tag = latest_versions[base_name]
                    old_tag = tag
                    if old_tag != new_tag:
                        # Track the update
                        updated_images[base_name] = (old_tag, new_tag)
                        # Replace with new tag, preserving registry prefix
                        new_image_spec = f"{name_part}:{new_tag}"
                        updated_lines.append(f"FROM {new_image_spec}{as_clause}\n")
                        count += 1
                    else:
                        updated_lines.append(original_line)
                else:
                    updated_lines.append(original_line)
            else:
                updated_lines.append(original_line)
        else:
            updated_lines.append(original_line)

    # Write updated file
    with open(safe_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    # Print what was updated
    check_mark = "[OK]" if IS_WINDOWS else "✓"
    arrow = "->" if IS_WINDOWS else "→"
    for image, (old_tag, new_tag) in updated_images.items():
        print(f"  {check_mark} {image}: {old_tag} {arrow} {new_tag}")

    return count