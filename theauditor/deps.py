"""Dependency parser for multiple ecosystems."""


import json
import platform
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from theauditor import __version__
from theauditor.security import sanitize_path, sanitize_url_component, validate_package_name, SecurityError

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"


def _canonicalize_name(name: str) -> str:
    """
    Normalize package name to PyPI standards (PEP 503).
    Converts 'PyYAML' -> 'pyyaml', 'My-Package.Cool' -> 'my-package-cool'
    """
    return re.sub(r"[-_.]+", "-", name).lower()


# Rate limiting configuration - optimized for minimal runtime
# Based on actual API rate limits and industry standards
RATE_LIMIT_NPM = 0.1      # npm registry: 600 req/min (well under any limit)
RATE_LIMIT_PYPI = 0.2     # PyPI: 300 req/min (safe margin) 
RATE_LIMIT_DOCKER = 0.2   # Docker Hub: 300 req/min for tag checks
RATE_LIMIT_BACKOFF = 15   # Backoff on 429/disconnect (15s gives APIs time to reset)


def parse_dependencies(root_path: str = ".") -> list[dict[str, Any]]:
    """
    Parse dependencies from the indexed database.

    Architecture:
    - DB-ONLY: Reads from package_configs and python_package_configs tables
    - NO FALLBACKS: If DB doesn't exist, fail loudly
    - Docker/Cargo: Still parsed from files (not yet indexed)

    Returns list of dependency objects with structure:
    {
        "name": str,
        "version": str,
        "manager": "npm"|"py"|"docker"|"cargo",
        "files": [paths that import it],
        "source": "package.json|pyproject.toml|requirements.txt"
    }

    Requires: Run 'aud full --index' first to populate the database.
    """
    import os
    import sqlite3
    root = Path(root_path)
    deps = []

    # Debug mode
    debug = os.environ.get("THEAUDITOR_DEBUG")

    # =========================================================================
    # GUARD CLAUSE: Fail loudly if index doesn't exist (Tweak 1)
    # =========================================================================
    db_path = root / ".pf" / "repo_index.db"

    if not db_path.exists():
        print("Error: Index not found at .pf/repo_index.db")
        print("Run 'aud full --index' first to index the project.")
        return []

    # =========================================================================
    # DATABASE-ONLY: Read npm dependencies from package_configs table
    # =========================================================================
    if debug:
        print(f"Debug: Reading npm dependencies from database: {db_path}")

    npm_deps = _read_npm_deps_from_database(db_path, root, debug)
    if npm_deps:
        if debug:
            print(f"Debug: Loaded {len(npm_deps)} npm dependencies from database")
        deps.extend(npm_deps)

    # =========================================================================
    # DATABASE-ONLY: Read Python dependencies from python_package_configs table
    # =========================================================================
    if debug:
        print(f"Debug: Reading Python dependencies from database: {db_path}")

    python_deps = _read_python_deps_from_database(db_path, root, debug)
    if python_deps:
        if debug:
            print(f"Debug: Loaded {len(python_deps)} Python dependencies from database")
        deps.extend(python_deps)
    
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

    Raises:
        sqlite3.Error: On unexpected database errors (not missing tables)
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # NO TABLE CHECK: Just query directly, let it fail if table missing
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

    except sqlite3.OperationalError as e:
        conn.close()
        # Table doesn't exist - valid empty state (indexer hasn't run for npm yet)
        if "no such table" in str(e):
            if debug:
                print("Debug: package_configs table not found (run indexer first)")
            return []
        # Unexpected DB error - crash loudly
        raise


def _read_python_deps_from_database(db_path: Path, root: Path, debug: bool) -> list[dict[str, Any]]:
    """Read Python dependencies from python_package_configs table.

    Args:
        db_path: Path to repo_index.db
        root: Project root path
        debug: Debug mode flag

    Returns:
        List of dependency dictionaries in deps.py format

    Raises:
        sqlite3.Error: On unexpected database errors (not missing tables)
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # NO TABLE CHECK: Just query directly, let it fail if table missing
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
                    # Normalize package name immediately when reading from DB
                    # This ensures cache keys match regardless of how indexer stored the name
                    raw_name = dep_info.get('name', '')
                    dep_obj = {
                        "name": _canonicalize_name(raw_name) if raw_name else '',
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
                        # Normalize package name for optional deps too
                        raw_name = dep_info.get('name', '')
                        dep_obj = {
                            "name": _canonicalize_name(raw_name) if raw_name else '',
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

    except sqlite3.OperationalError as e:
        conn.close()
        # Table doesn't exist - valid empty state (indexer hasn't run for Python yet)
        if "no such table" in str(e):
            if debug:
                print("Debug: python_package_configs table not found (run indexer first)")
            return []
        # Unexpected DB error - crash loudly
        raise


def _parse_python_dep_spec(spec: str) -> tuple[str, str | None]:
    """
    Parse a Python dependency specification.
    Returns (name, version) tuple.

    Package names are normalized to PyPI canonical form (PEP 503):
    - PyYAML -> pyyaml
    - My_Package -> my-package
    """
    # Handle various formats:
    # package==1.2.3
    # package>=1.2.3
    # package~=1.2.3
    # package[extra]==1.2.3
    # package @ git+https://...

    # Remove extras (but preserve for future use if needed)
    spec = re.sub(r'\[.*?\]', '', spec)

    # Handle git URLs
    if "@" in spec and ("git+" in spec or "https://" in spec):
        name = spec.split("@")[0].strip()
        return (_canonicalize_name(name), "git")

    # Parse version specs (allow dots, underscores, hyphens in package names)
    match = re.match(r'^([a-zA-Z0-9._-]+)\s*([><=~!]+)\s*(.+)$', spec)
    if match:
        name, op, version = match.groups()
        # Normalize package name to PyPI canonical form
        name = _canonicalize_name(name)
        # For pinned versions, use exact version
        if op == "==":
            return (name, version)
        # For other operators, use the specified version as hint
        return (name, version)

    # No version specified - still normalize the name
    name = spec.strip()
    if name:
        name = _canonicalize_name(name)
    return (name, None)


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
    """
    Parse Docker base images from Dockerfile.
    Ignores multi-stage build aliases to prevent false "Not found" errors.

    Multi-stage builds like:
        FROM node:18 AS base
        FROM base AS build

    The second FROM references the "base" stage, NOT an external image.
    We track these aliases and skip them.
    """
    deps = []
    # Track build stages (e.g., "FROM python AS builder")
    # We shouldn't audit "builder" as an external dependency later
    stages = set()

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Look for FROM instructions
                if line.upper().startswith("FROM "):
                    # Extract image spec after FROM
                    # Format: FROM <image> [AS <name>]
                    parts = line[5:].strip().split()
                    image_part = parts[0]

                    # Check if this is a reference to a previous stage
                    # e.g., "FROM builder" -> Skip (it's not an external image)
                    if image_part in stages:
                        continue

                    # Handle stage aliasing
                    # e.g., "FROM python:3.9 AS builder" -> Record "builder"
                    if len(parts) >= 3 and parts[1].upper() == "AS":
                        stages.add(parts[2])

                    # Skip scratch (empty base)
                    if image_part.lower() == "scratch":
                        continue

                    # Parse image:tag format
                    if ":" in image_part:
                        name, tag = image_part.rsplit(":", 1)
                    else:
                        name = image_part
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
        # Don't crash on read errors, just warn
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


# =============================================================================
# ASYNC HTTP ENGINE - Modern dependency checking with httpx
# =============================================================================


async def _fetch_npm_async(client, name: str) -> str | None:
    """Fetch latest version from npm registry (async)."""
    if not validate_package_name(name, "npm"):
        return None
    url = f"https://registry.npmjs.org/{sanitize_url_component(name)}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json().get("dist-tags", {}).get("latest")
    except Exception:
        pass
    return None


async def _fetch_pypi_async(client, name: str, allow_prerelease: bool) -> str | None:
    """Fetch latest version from PyPI (async)."""
    if not validate_package_name(name, "py"):
        return None
    # Ensure canonical name for URL
    safe_name = sanitize_url_component(_canonicalize_name(name))
    url = f"https://pypi.org/pypi/{safe_name}/json"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if allow_prerelease:
            return data.get("info", {}).get("version")

        # Filter to stable versions only
        releases = data.get("releases", {})
        stable = [v for v in releases.keys() if not _is_prerelease_version(v)]
        if stable:
            stable.sort(key=_parse_pypi_version, reverse=True)
            return stable[0]
        return data.get("info", {}).get("version")
    except Exception:
        pass
    return None


async def _fetch_docker_async(client, name: str, current_tag: str, allow_prerelease: bool) -> str | None:
    """Fetch latest Docker tag from Docker Hub (async)."""
    if not validate_package_name(name, "docker"):
        return None
    if "/" not in name:
        name = f"library/{name}"

    url = f"https://hub.docker.com/v2/repositories/{name}/tags?page_size=100"
    try:
        resp = await client.get(url, headers={"User-Agent": f"TheAuditor/{__version__}"})
        if resp.status_code != 200:
            return None

        data = resp.json()
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
            # Fallback to "latest" if no parseable versions
            for tag in tags:
                if tag.get("name") == "latest":
                    return "latest"
            return None

        # Filter by stability
        if allow_prerelease:
            candidates = parsed_tags
        else:
            candidates = [t for t in parsed_tags if t['stability'] == 'stable']
            if not candidates:
                candidates = [t for t in parsed_tags if t['stability'] in ['stable', 'rc']]
            if not candidates:
                candidates = parsed_tags

        # Filter by base image preference
        if current_tag:
            base_preference = _extract_base_preference(current_tag)
            if base_preference:
                matching_base = [t for t in candidates if base_preference in t['variant'].lower()]
                if matching_base:
                    candidates = matching_base
                else:
                    return None  # Don't suggest upgrade with different base

        # Sort by semantic version
        candidates.sort(key=lambda x: x['version'], reverse=True)
        return candidates[0]['tag'] if candidates else None
    except Exception:
        pass
    return None


async def _check_latest_batch_async(
    deps_to_check: list[dict],
    allow_prerelease: bool
) -> dict[str, dict[str, Any]]:
    """
    Check latest versions for a batch of dependencies using async HTTP.

    This is the modern async engine that replaces the slow synchronous loop.
    Uses httpx with a semaphore to limit concurrent requests.

    Args:
        deps_to_check: List of dependency objects to check
        allow_prerelease: Allow pre-release versions

    Returns:
        Dict keyed by universal key with {latest, error} values
    """
    try:
        import httpx
    except ImportError:
        print("Error: 'httpx' not installed. Run: pip install httpx")
        return {}

    results = {}
    # Semaphore: limit to 10 concurrent requests to be polite to registries
    import asyncio
    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:

        async def check_one(dep: dict) -> tuple[str, str | None, str | None]:
            """Check a single dependency and return (key, latest, error)."""
            # Universal key format
            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"

            async with semaphore:
                try:
                    latest = None
                    if dep["manager"] == "npm":
                        latest = await _fetch_npm_async(client, dep["name"])
                    elif dep["manager"] == "py":
                        latest = await _fetch_pypi_async(client, dep["name"], allow_prerelease)
                    elif dep["manager"] == "docker":
                        current_tag = dep.get("version", "")
                        latest = await _fetch_docker_async(client, dep["name"], current_tag, allow_prerelease)

                    return key, latest, None
                except Exception as e:
                    return key, None, f"{type(e).__name__}: {str(e)[:50]}"

        # Fire off all tasks concurrently
        tasks = [check_one(dep) for dep in deps_to_check]
        batch_results = await asyncio.gather(*tasks)

        for key, latest, error in batch_results:
            results[key] = {"latest": latest, "error": error}

    return results


def check_latest_versions(
    deps: list[dict[str, Any]],
    allow_net: bool = True,
    offline: bool = False,
    allow_prerelease: bool = False,
    root_path: str = "."
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
        cached_data = _load_deps_cache(root_path)
        if cached_data:
            # Update locked versions from current deps
            for dep in deps:
                # UNIVERSAL KEY: Include version for ALL managers (Tweak 2)
                # Fixes multi-version collision (requests==2.20 vs requests==2.30 in monorepo)
                key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
                if key in cached_data:
                    # Clean version to remove operators (==, >=, etc.)
                    locked_clean = _clean_version(dep["version"])
                    cached_data[key]["locked"] = locked_clean
                    # Guard against None latest (cache entry with error/not found)
                    latest = cached_data[key].get("latest")
                    if latest:
                        cached_data[key]["is_outdated"] = latest != locked_clean
                        cached_data[key]["delta"] = _calculate_version_delta(locked_clean, latest)
                    else:
                        cached_data[key]["is_outdated"] = False
                        cached_data[key]["delta"] = None
        return cached_data or {}

    # Load existing cache
    cache = _load_deps_cache(root_path)
    latest_info = {}
    needs_check = []
    
    # FIRST PASS: Check what's in cache and still valid
    for dep in deps:
        # UNIVERSAL KEY: Include version for ALL managers (Tweak 2)
        # Fixes multi-version collision (requests==2.20 vs requests==2.30 in monorepo)
        key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"

        if key in latest_info:
            continue  # Already processed

        # Check if we have valid cached data (24 hours for deps)
        if key in cache and _is_cache_valid(cache[key], hours=24):
            # Update locked version from current deps
            # Clean version to remove operators (==, >=, etc.)
            locked_clean = _clean_version(dep["version"])
            cache[key]["locked"] = locked_clean
            # Guard against None latest (cache entry with error/not found)
            cached_latest = cache[key].get("latest")
            if cached_latest:
                cache[key]["is_outdated"] = cached_latest != locked_clean
                cache[key]["delta"] = _calculate_version_delta(locked_clean, cached_latest)
            else:
                cache[key]["is_outdated"] = False
                cache[key]["delta"] = None
            latest_info[key] = cache[key]
        else:
            needs_check.append(dep)
    
    # Early exit if everything is cached
    if not needs_check:
        return latest_info

    # SECOND PASS: Async batch processing (replaces slow synchronous loop)
    import asyncio

    # Run the async engine
    batch_results = asyncio.run(_check_latest_batch_async(needs_check, allow_prerelease))

    # Process results
    for dep in needs_check:
        key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
        result = batch_results.get(key, {})

        latest = result.get("latest")
        error_msg = result.get("error")
        locked = _clean_version(dep["version"])

        if latest:
            # Success - package found with latest version
            latest_info[key] = {
                "locked": locked,
                "latest": latest,
                "delta": _calculate_version_delta(locked, latest),
                "is_outdated": locked != latest,
                "last_checked": datetime.now().isoformat()
            }
        else:
            # Failure - use cached data if available, otherwise mark as error
            if key in cache:
                latest_info[key] = cache[key]
                if error_msg:
                    latest_info[key]["error"] = error_msg
            else:
                latest_info[key] = {
                    "locked": locked,
                    "latest": None,
                    "delta": None,
                    "is_outdated": False,
                    "error": error_msg or "Not found",
                    "last_checked": datetime.now().isoformat()
                }
    
    # Save updated cache
    _save_deps_cache(latest_info, root_path)

    return latest_info


def _load_deps_cache(root_path: str) -> dict[str, dict[str, Any]]:
    """
    Load the dependency version cache from repo_index.db.

    Returns empty dict if database doesn't exist or table is empty.
    Key format: "manager:package_name:locked_version" (Universal Keys - Tweak 2)
    """
    import sqlite3

    db_path = Path(root_path) / ".pf" / "repo_index.db"

    if not db_path.exists():
        return {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Load all cache entries from dependency_versions table
        cursor.execute("""
            SELECT manager, package_name, locked_version, latest_version, delta, is_outdated, last_checked, error
            FROM dependency_versions
        """)

        cache = {}
        for row in cursor.fetchall():
            manager, pkg_name, locked, latest, delta, is_outdated, last_checked, error = row
            # UNIVERSAL KEY: Include version for ALL managers (Tweak 2)
            key = f"{manager}:{pkg_name}:{locked}"
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

    except sqlite3.OperationalError as e:
        conn.close()
        # Table doesn't exist - valid empty state
        if "no such table" in str(e):
            return {}
        # Unexpected DB error - crash loudly
        raise


def _save_deps_cache(latest_info: dict[str, dict[str, Any]], root_path: str) -> None:
    """
    Save the dependency version cache to repo_index.db.
    Uses INSERT OR REPLACE to update existing entries.
    Creates table if it doesn't exist (for standalone aud deps usage).

    Key format: "manager:package_name:locked_version" (Universal Keys - Tweak 2)
    """
    import sqlite3

    db_path = Path(root_path) / ".pf" / "repo_index.db"

    if not db_path.exists():
        # Create .pf directory and database for standalone usage
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table if it doesn't exist (schema contract)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dependency_versions (
            manager TEXT NOT NULL,
            package_name TEXT NOT NULL,
            locked_version TEXT NOT NULL,
            latest_version TEXT,
            delta TEXT,
            is_outdated INTEGER NOT NULL DEFAULT 0,
            last_checked TEXT NOT NULL,
            error TEXT,
            PRIMARY KEY (manager, package_name, locked_version)
        )
    """)

    # Create indexes if they don't exist
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dependency_versions_outdated
        ON dependency_versions(is_outdated)
    """)

    # Upsert each entry into dependency_versions table
    for key, info in latest_info.items():
        # Parse UNIVERSAL KEY format: "manager:package_name:version" (Tweak 2)
        parts = key.split(":")
        if len(parts) < 2:
            continue
        manager = parts[0]
        # Handle package names that might contain colons (rare but possible)
        # Join everything after manager except last part (version)
        if len(parts) >= 3:
            pkg_name = ":".join(parts[1:-1]) if len(parts) > 3 else parts[1]
            version_from_key = parts[-1]
        else:
            pkg_name = parts[1]
            version_from_key = ""

        cursor.execute("""
            INSERT OR REPLACE INTO dependency_versions
            (manager, package_name, locked_version, latest_version, delta, is_outdated, last_checked, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            manager,
            pkg_name,
            info.get("locked", version_from_key),
            info.get("latest"),
            info.get("delta"),
            1 if info.get("is_outdated") else 0,
            info.get("last_checked", ""),
            info.get("error")
        ))

    conn.commit()
    conn.close()


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

        # Escape special regex characters in package name (dots, etc.)
        escaped_package_name = re.escape(package_name)

        # Pattern to match this package anywhere in the file
        # Matches: "package==X.Y.Z" OR "package>=X.Y.Z" OR "package[extra]>=X.Y.Z"
        # Group 1: Optional extras notation [dev], [test], etc.
        # Group 2: Version operator (>=, ==, ~=, etc.)
        # Group 3: Version number
        pattern = rf'"{escaped_package_name}(\[.*?\])?([><=~!]+)([^"]+)"'

        # Replace ALL occurrences at once using re.sub with a function
        def replacer(match):
            extras = match.group(1) or ""  # [extra] or empty string
            old_operator = match.group(2)  # >=, ==, ~=, etc.
            old_version = match.group(3)
            if old_version != latest_version:
                # Track the update
                if package_name not in updated_packages:
                    updated_packages[package_name] = []
                updated_packages[package_name].append((old_version, latest_version))
                # Keep the original operator and extras notation
                return f'"{package_name}{extras}{old_operator}{latest_version}"'
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


# =============================================================================
# GROUPED REPORTING ENGINE - Solves "Where is this coming from?" problem
# =============================================================================


def generate_grouped_report(
    deps: list[dict[str, Any]],
    latest_info: dict[str, dict[str, Any]],
    hide_up_to_date: bool = True
) -> None:
    """
    Print a report grouped by SOURCE FILE path.

    This solves the "Where the f*** is this coming from?" problem by organizing
    dependencies by their origin file and clearly marking test fixtures.

    Args:
        deps: List of dependency objects from parse_dependencies()
        latest_info: Dict from check_latest_versions() with version info
        hide_up_to_date: If True, skip files with no outdated deps (default: True)
    """
    from collections import defaultdict

    # Windows-safe symbols
    arrow = "->" if IS_WINDOWS else "->"
    check = "[OK]" if IS_WINDOWS else "[OK]"
    folder = "[FILE]" if IS_WINDOWS else "[FILE]"

    # 1. Group dependencies by their source file
    files_map = defaultdict(list)
    for dep in deps:
        # Use workspace_package if available (monorepos), else source file
        source = dep.get("workspace_package") or dep.get("source", "unknown")
        files_map[source].append(dep)

    # 2. Sort files: real code first, then test fixtures
    def sort_key(path: str) -> tuple:
        """Sort real code first, test fixtures last."""
        is_test = any(x in path.lower() for x in [
            "test", "fixture", "mock", "example", "node_modules",
            "venv", ".venv", "__pycache__", "dist", "build"
        ])
        return (is_test, path.lower())

    sorted_files = sorted(files_map.keys(), key=sort_key)

    # 3. Print the report header
    print("\n" + "=" * 80)
    print("DEPENDENCY HEALTH REPORT (GROUPED BY FILE)")
    print("=" * 80)

    total_outdated = 0
    total_outdated_real = 0  # Excluding test fixtures
    ghost_files_detected = 0
    files_with_issues = 0

    for source_file in sorted_files:
        file_deps = files_map[source_file]

        # Check if this looks like a test/fixture (The "Ghost" Detector)
        ghost_markers = [
            "test", "fixture", "mock", "example", "sample",
            "node_modules", "venv", ".venv", "__pycache__",
            "dist", "build", "vendor", "third_party"
        ]
        is_ghost = any(marker in source_file.lower() for marker in ghost_markers)

        # Filter for outdated deps in this file
        outdated_in_file = []
        for dep in file_deps:
            # UNIVERSAL KEY: manager:name:version
            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
            info = latest_info.get(key)

            if info and info.get("is_outdated"):
                outdated_in_file.append((dep, info))

        # Skip printing if file is healthy and we are hiding up-to-date
        if hide_up_to_date and not outdated_in_file:
            continue

        # Count stats
        if outdated_in_file:
            files_with_issues += 1
            if is_ghost:
                ghost_files_detected += 1

        # Header for the file
        if is_ghost:
            # Mark test fixtures clearly
            print(f"\n{folder} {source_file} [TEST/FIXTURE]")
        else:
            # Real code - highlight it
            print(f"\n{folder} {source_file}")

        if not outdated_in_file:
            print(f"  {check} All dependencies up to date")
            continue

        # Print the deps for this specific file
        for dep, info in outdated_in_file:
            total_outdated += 1
            if not is_ghost:
                total_outdated_real += 1

            name = dep['name']
            current = info['locked']
            latest = info['latest']
            delta = info.get('delta', 'unknown')

            # Label based on severity
            if delta == "major":
                label = "[MAJOR!]"
            elif delta == "minor":
                label = "[minor]"
            elif delta == "patch":
                label = "[patch]"
            else:
                label = ""

            # Indent test fixture output to de-emphasize
            if is_ghost:
                print(f"    (test) {name}: {current} {arrow} {latest} {label}")
            else:
                print(f"  - {name}: {current} {arrow} {latest} {label}")

    # Summary section
    print("\n" + "-" * 80)
    print("SUMMARY")
    print("-" * 80)

    if total_outdated == 0:
        print("All dependencies are up to date!")
    else:
        print(f"Total outdated: {total_outdated} packages across {files_with_issues} files")

        if ghost_files_detected > 0:
            real_files = files_with_issues - ghost_files_detected
            print(f"  - Real code: {total_outdated_real} packages in {real_files} files")
            print(f"  - Test fixtures: {total_outdated - total_outdated_real} packages in {ghost_files_detected} files")

    print("=" * 80 + "\n")