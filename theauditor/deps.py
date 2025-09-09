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
from theauditor.security import sanitize_path, sanitize_url_component, validate_package_name, SecurityError

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"

# Rate limiting configuration - optimized for minimal runtime
# Based on actual API rate limits and industry standards
RATE_LIMIT_NPM = 0.1      # npm registry: 600 req/min (well under any limit)
RATE_LIMIT_PYPI = 0.2     # PyPI: 300 req/min (safe margin) 
RATE_LIMIT_DOCKER = 0.2   # Docker Hub: 300 req/min for tag checks
RATE_LIMIT_BACKOFF = 15   # Backoff on 429/disconnect (15s gives APIs time to reset)


def parse_dependencies(root_path: str = ".") -> List[Dict[str, Any]]:
    """
    Parse dependencies from various package managers.
    
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
    root = Path(root_path)
    deps = []
    
    # Debug mode
    debug = os.environ.get("THEAUDITOR_DEBUG")
    
    # Parse Node dependencies
    try:
        package_json = sanitize_path("package.json", root_path)
        if package_json.exists():
            if debug:
                print(f"Debug: Found {package_json}")
            deps.extend(_parse_package_json(package_json))
    except SecurityError as e:
        if debug:
            print(f"Debug: Security error checking package.json: {e}")
    
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
    
    if debug:
        print(f"Debug: Total dependencies found: {len(deps)}")
    
    return deps


def _parse_package_json(path: Path) -> List[Dict[str, Any]]:
    """Parse dependencies from package.json, with monorepo support."""
    deps = []
    processed_packages = set()  # Track processed packages to avoid duplicates
    
    def parse_single_package(pkg_path: Path, workspace_path: str = "package.json") -> List[Dict[str, Any]]:
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


def _parse_pyproject_toml(path: Path) -> List[Dict[str, Any]]:
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


def _parse_requirements_txt(path: Path) -> List[Dict[str, Any]]:
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


def _parse_python_dep_spec(spec: str) -> tuple[str, Optional[str]]:
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
    ^1.2.3 -> 1.2.3
    ~1.2.3 -> 1.2.3
    >=1.2.3 -> 1.2.3
    """
    # Remove common prefixes
    version = re.sub(r'^[~^>=<]+', '', version_spec)
    # Handle ranges (use first version)
    if " " in version:
        version = version.split()[0]
    return version.strip()


def _parse_docker_compose(path: Path) -> List[Dict[str, Any]]:
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


def _parse_dockerfile(path: Path) -> List[Dict[str, Any]]:
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


def write_deps_json(deps: List[Dict[str, Any]], output_path: str = "./.pf/deps.json") -> None:
    """Write dependencies to JSON file."""
    try:
        output = sanitize_path(output_path, ".")
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, "w", encoding="utf-8") as f:
            json.dump(deps, f, indent=2, sort_keys=True)
    except SecurityError as e:
        raise SecurityError(f"Invalid output path: {e}")


def check_latest_versions(
    deps: List[Dict[str, Any]], 
    allow_net: bool = True,
    offline: bool = False,
    cache_file: str = "./.pf/deps_cache.json"
) -> Dict[str, Dict[str, Any]]:
    """
    Check latest versions from registries with caching.
    
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
                key = f"{dep['manager']}:{dep['name']}"
                if key in cached_data:
                    cached_data[key]["locked"] = dep["version"]
                    cached_data[key]["is_outdated"] = cached_data[key]["latest"] != dep["version"]
                    cached_data[key]["delta"] = _calculate_version_delta(dep["version"], cached_data[key]["latest"])
        return cached_data or {}
    
    # Load existing cache
    cache = _load_deps_cache(cache_file)
    latest_info = {}
    needs_check = []
    
    # FIRST PASS: Check what's in cache and still valid
    for dep in deps:
        key = f"{dep['manager']}:{dep['name']}"
        if key in latest_info:
            continue  # Already processed
        
        # Check if we have valid cached data (24 hours for deps)
        if key in cache and _is_cache_valid(cache[key], hours=24):
            # Update locked version from current deps
            cache[key]["locked"] = dep["version"]
            cache[key]["is_outdated"] = cache[key]["latest"] != dep["version"]
            cache[key]["delta"] = _calculate_version_delta(dep["version"], cache[key]["latest"])
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
                latest = _check_pypi_latest(dep["name"])
            elif dep["manager"] == "docker":
                latest = _check_dockerhub_latest(dep["name"])
            else:
                continue
            
            if latest:
                locked = dep["version"]
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
                latest_info[key] = {
                    "locked": dep["version"],
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


def _load_deps_cache(cache_file: str) -> Dict[str, Dict[str, Any]]:
    """
    Load the dependency cache from disk.
    Returns empty dict if cache doesn't exist or is invalid.
    """
    try:
        cache_path = Path(cache_file)
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_deps_cache(latest_info: Dict[str, Dict[str, Any]], cache_file: str) -> None:
    """
    Save the dependency cache to disk.
    Merges with existing cache to preserve data for packages not in current check.
    """
    try:
        cache_path = Path(cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache to merge
        existing = _load_deps_cache(cache_file)
        
        # Merge new data into existing (new data takes precedence)
        existing.update(latest_info)
        
        # Write merged cache
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, sort_keys=True)
    except OSError:
        pass  # Fail silently if can't write cache


def _is_cache_valid(cached_item: Dict[str, Any], hours: int = 24) -> bool:
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


def _check_npm_latest(package_name: str) -> Optional[str]:
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


def _check_pypi_latest(package_name: str) -> Optional[str]:
    """Fetch latest version from PyPI."""
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
            return data.get("info", {}).get("version")
    except (urllib.error.URLError, http.client.RemoteDisconnected, json.JSONDecodeError, KeyError):
        return None


def _check_dockerhub_latest(image_name: str) -> Optional[str]:
    """Fetch latest version from Docker Hub."""
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
    
    # Docker Hub API endpoint for tags
    url = f"https://hub.docker.com/v2/repositories/{safe_image_name}/tags"
    
    try:
        # Create request with proper headers
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'TheAuditor/0.1.0')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            
            # Parse the results to find latest stable version
            tags = data.get("results", [])
            if not tags:
                return None
            
            # Filter and sort tags to find the best "latest" version
            version_tags = []
            for tag in tags:
                tag_name = tag.get("name", "")
                # Skip non-version tags
                if tag_name in ["latest", "alpine", "slim", "bullseye", "bookworm"]:
                    continue
                # Look for semantic version-like tags
                if re.match(r'^\d+(\.\d+)*', tag_name):
                    version_tags.append(tag_name)
            
            if version_tags:
                # Sort versions (simple string sort for now)
                # More sophisticated version comparison could be added
                version_tags.sort(reverse=True)
                return version_tags[0]
            
            # Fallback to "latest" if no version tags found
            for tag in tags:
                if tag.get("name") == "latest":
                    return "latest"
            
            return None
            
    except (urllib.error.URLError, http.client.RemoteDisconnected, json.JSONDecodeError, KeyError) as e:
        # Docker Hub API might require auth or have rate limits
        return None


def _calculate_version_delta(locked: str, latest: str) -> str:
    """
    Calculate semantic version delta.
    Returns: "major", "minor", "patch", "equal", or "unknown"
    """
    try:
        locked_parts = [int(x) for x in locked.split(".")[:3]]
        latest_parts = [int(x) for x in latest.split(".")[:3]]
        
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
    except (ValueError, IndexError):
        return "unknown"


def write_deps_latest_json(
    latest_info: Dict[str, Dict[str, Any]], 
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
    latest_info: Dict[str, Dict[str, Any]],
    deps_list: List[Dict[str, Any]]
) -> Dict[str, int]:
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
    
    return upgraded


def _upgrade_requirements_txt(
    path: Path,
    latest_info: Dict[str, Dict[str, Any]],
    deps: List[Dict[str, Any]]
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
    with open(safe_path, "r", encoding="utf-8") as f:
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
    latest_info: Dict[str, Dict[str, Any]],
    deps: List[Dict[str, Any]]
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
    with open(safe_path, "r", encoding="utf-8") as f:
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
    latest_info: Dict[str, Dict[str, Any]],
    deps: List[Dict[str, Any]]
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
    with open(safe_path, "r", encoding="utf-8") as f:
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