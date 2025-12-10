"""Dependency parser for multiple ecosystems."""

import json
import platform
import re
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from theauditor.pipeline.ui import console
from theauditor.utils.logging import logger
from theauditor.utils.rate_limiter import RATE_LIMIT_BACKOFF, get_rate_limiter

from . import Dependency, get_manager


def _validate_package_name(name: str, manager: str) -> bool:
    """Validate package name format for a package manager."""
    if not name or len(name) > 214:
        return False
    if manager == "npm":
        return bool(re.match(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", name))
    elif manager == "py":
        return bool(re.match(r"^[a-zA-Z0-9][\w.-]*$", name))
    elif manager == "docker":
        return bool(re.match(r"^[a-z0-9][\w./:-]*$", name))
    return False


IS_WINDOWS = platform.system() == "Windows"


def _canonicalize_name(name: str) -> str:
    """Normalize package name to PyPI standards (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_dependencies(root_path: str = ".") -> list[dict[str, Any]]:
    """Parse dependencies from the indexed database."""
    import os

    root = Path(root_path)
    deps = []

    debug = os.environ.get("THEAUDITOR_DEBUG")

    db_path = root / ".pf" / "repo_index.db"

    if not db_path.exists():
        console.print("Error: Index not found at .pf/repo_index.db")
        console.print("Run 'aud full --index' first to index the project.")
        return []

    if debug:
        console.print(f"Debug: Reading npm dependencies from database: {db_path}", highlight=False)

    npm_deps = _read_npm_deps_from_database(db_path, root, debug)
    if npm_deps:
        if debug:
            console.print(
                f"Debug: Loaded {len(npm_deps)} npm dependencies from database", highlight=False
            )
        deps.extend(npm_deps)

    if debug:
        console.print(
            f"Debug: Reading Python dependencies from database: {db_path}", highlight=False
        )

    python_deps = _read_python_deps_from_database(db_path, root, debug)
    if python_deps:
        if debug:
            console.print(
                f"Debug: Loaded {len(python_deps)} Python dependencies from database",
                highlight=False,
            )
        deps.extend(python_deps)

    docker_mgr = get_manager("docker")
    if docker_mgr:
        docker_compose_files = list(root.glob("docker-compose*.yml")) + list(
            root.glob("docker-compose*.yaml")
        )
        if debug and docker_compose_files:
            console.print(
                f"Debug: Found Docker Compose files: {docker_compose_files}", highlight=False
            )
        for compose_file in docker_compose_files:
            deps.extend(d.to_dict() for d in docker_mgr.parse_manifest(compose_file))

        dockerfiles = list(root.glob("**/Dockerfile"))
        if debug and dockerfiles:
            console.print(f"Debug: Found Dockerfiles: {dockerfiles}", highlight=False)
        for dockerfile in dockerfiles:
            deps.extend(d.to_dict() for d in docker_mgr.parse_manifest(dockerfile))

    cargo_toml = root / "Cargo.toml"
    if cargo_toml.exists():
        if debug:
            console.print(f"Debug: Found {cargo_toml}", highlight=False)
        deps.extend(_parse_cargo_toml(cargo_toml))

    go_mgr = get_manager("go")
    if go_mgr:
        go_mod_files = list(root.glob("**/go.mod"))
        if debug and go_mod_files:
            console.print(f"Debug: Found go.mod files: {go_mod_files}", highlight=False)
        for go_mod in go_mod_files:
            deps.extend(d.to_dict() for d in go_mgr.parse_manifest(go_mod))

    if debug:
        console.print(f"Debug: Total dependencies found: {len(deps)}", highlight=False)

    return deps


def _read_npm_deps_from_database(db_path: Path, root: Path, debug: bool) -> list[dict[str, Any]]:
    """Read npm dependencies from normalized package_dependencies table."""
    import sqlite3

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT pd.file_path, pd.name, pd.version_spec, pd.is_dev, pd.is_peer
            FROM package_dependencies pd
        """)

        deps = []

        for file_path, name, version_spec, is_dev, is_peer in cursor.fetchall():
            workspace_package = file_path if file_path != "package.json" else None

            dep_obj = {
                "name": name,
                "version": version_spec or "*",
                "manager": "npm",
                "files": [],
                "source": file_path,
            }
            if is_dev:
                dep_obj["dev"] = True
            if is_peer:
                dep_obj["peer"] = True
            if workspace_package:
                dep_obj["workspace_package"] = workspace_package
            deps.append(dep_obj)

        conn.close()
        return deps

    except sqlite3.OperationalError as e:
        conn.close()

        if "no such table" in str(e):
            if debug:
                console.print("Debug: package_dependencies table not found (run indexer first)")
            return []

        raise


def _read_python_deps_from_database(db_path: Path, root: Path, debug: bool) -> list[dict[str, Any]]:
    """Read Python dependencies from normalized python_package_dependencies table."""
    import sqlite3

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT file_path, name, version_spec, is_dev, group_name, extras, git_url
            FROM python_package_dependencies
        """)

        deps = []

        for (
            file_path,
            name,
            version_spec,
            is_dev,
            group_name,
            extras_json,
            git_url,
        ) in cursor.fetchall():
            if not name:
                continue

            dep_obj = {
                "name": _canonicalize_name(name),
                "version": version_spec or "",
                "manager": "py",
                "files": [],
                "source": file_path,
            }

            if is_dev:
                dep_obj["dev"] = True

            if group_name:
                dep_obj["optional_group"] = group_name

            if extras_json:
                try:
                    dep_obj["extras"] = json.loads(extras_json)
                except json.JSONDecodeError:
                    pass

            if git_url:
                dep_obj["git_url"] = git_url

            deps.append(dep_obj)

        conn.close()
        return deps

    except sqlite3.OperationalError as e:
        conn.close()

        if "no such table" in str(e):
            if debug:
                console.print(
                    "Debug: python_package_dependencies table not found (run indexer first)"
                )
            return []

        raise


def _parse_python_dep_spec(spec: str) -> tuple[str, str | None]:
    """Parse a Python dependency specification."""

    spec = re.sub(r"\[.*?\]", "", spec)

    if "@" in spec and ("git+" in spec or "https://" in spec):
        name = spec.split("@")[0].strip()
        return (_canonicalize_name(name), "git")

    match = re.match(r"^([a-zA-Z0-9._-]+)\s*([><=~!]+)\s*(.+)$", spec)
    if match:
        name, op, version = match.groups()

        name = _canonicalize_name(name)

        if op == "==":
            return (name, version)

        return (name, version)

    name = spec.strip()
    if name:
        name = _canonicalize_name(name)
    return (name, None)


def _clean_version(version_spec: str) -> str:
    """Clean version specification to get actual version."""

    version = re.sub(r"^[><=~!^]+", "", version_spec)

    if " " in version:
        version = version.split()[0]
    return version.strip()


def _parse_cargo_deps(deps_dict: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    """Parse a Cargo.toml dependency section."""
    deps = []

    for name, spec in deps_dict.items():
        if isinstance(spec, str):
            version = _clean_version(spec)
            features = []
        elif isinstance(spec, dict):
            version = _clean_version(spec.get("version", "*"))
            features = spec.get("features", [])
        else:
            continue

        deps.append(
            {
                "name": name,
                "version": version,
                "manager": "cargo",
                "features": features,
                "kind": kind,
                "files": [],
                "source": "Cargo.toml",
            }
        )

    return deps


def _parse_cargo_toml(path: Path) -> list[dict[str, Any]]:
    """Parse dependencies from Cargo.toml."""

    deps = []
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            logger.warning(f"Cannot parse {path} - tomllib not available")
            return deps

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        deps.extend(_parse_cargo_deps(data.get("dependencies", {}), kind="normal"))
        deps.extend(_parse_cargo_deps(data.get("dev-dependencies", {}), kind="dev"))

    except Exception as e:
        logger.error(f"Could not parse {path}: {e}")

    return deps


async def _fetch_npm_async(client, name: str) -> str | None:
    """Fetch latest version from npm registry (async)."""
    if not _validate_package_name(name, "npm"):
        return None
    url = f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='')}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json().get("dist-tags", {}).get("latest")
    except Exception:
        pass
    return None


async def _fetch_pypi_async(client, name: str, allow_prerelease: bool) -> str | None:
    """Fetch latest version from PyPI (async)."""
    if not _validate_package_name(name, "py"):
        return None

    safe_name = urllib.parse.quote(_canonicalize_name(name), safe="")
    url = f"https://pypi.org/pypi/{safe_name}/json"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if allow_prerelease:
            return data.get("info", {}).get("version")

        releases = data.get("releases", {})
        stable = [v for v in releases if not _is_prerelease_version(v)]
        if stable:
            stable.sort(key=_parse_pypi_version, reverse=True)
            return stable[0]
        return data.get("info", {}).get("version")
    except Exception:
        pass
    return None


async def _check_latest_batch_async(
    deps_to_check: list[dict], allow_prerelease: bool
) -> dict[str, dict[str, Any]]:
    """Check latest versions for a batch of dependencies using async HTTP."""
    try:
        import httpx
    except ImportError:
        console.print("Error: 'httpx' not installed. Run: pip install httpx")
        return {}

    results = {}
    import asyncio

    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:

        async def check_one(dep: dict) -> tuple[str, str | None, str | None]:
            """Check a single dependency with rate limiting and 429 backoff."""

            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
            manager = dep["manager"]

            limiter = get_rate_limiter(manager)

            async with semaphore:
                max_retries = 3
                backoff = RATE_LIMIT_BACKOFF

                for attempt in range(max_retries):
                    try:
                        await limiter.acquire()

                        latest = None
                        if manager == "npm":
                            latest = await _fetch_npm_async(client, dep["name"])
                        elif manager == "py":
                            latest = await _fetch_pypi_async(client, dep["name"], allow_prerelease)
                        elif manager in ("docker", "cargo", "go"):
                            mgr = get_manager(manager)
                            if mgr:
                                dep_obj = Dependency.from_dict(dep)
                                latest = await mgr.fetch_latest_async(
                                    client, dep_obj, allow_prerelease
                                )

                        return key, latest, None

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(backoff)
                                backoff *= 2
                                continue
                            return key, None, "Rate limited (429) after retries"
                        return key, None, f"HTTP {e.response.status_code}"

                    except Exception as e:
                        return key, None, f"{type(e).__name__}: {str(e)[:50]}"

                return key, None, "Max retries exceeded"

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
    root_path: str = ".",
) -> dict[str, dict[str, Any]]:
    """Check latest versions from registries with caching."""
    if offline or not allow_net:
        cached_data = _load_deps_cache(root_path)
        if cached_data:
            for dep in deps:
                key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
                if key in cached_data:
                    locked_clean = _clean_version(dep["version"])
                    cached_data[key]["locked"] = locked_clean

                    latest = cached_data[key].get("latest")
                    if latest:
                        cached_data[key]["is_outdated"] = latest != locked_clean
                        cached_data[key]["delta"] = _calculate_version_delta(locked_clean, latest)
                    else:
                        cached_data[key]["is_outdated"] = False
                        cached_data[key]["delta"] = None
        return cached_data or {}

    cache = _load_deps_cache(root_path)
    latest_info = {}
    needs_check = []

    for dep in deps:
        key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"

        if key in latest_info:
            continue

        if key in cache and _is_cache_valid(cache[key], hours=24):
            locked_clean = _clean_version(dep["version"])
            cache[key]["locked"] = locked_clean

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

    if not needs_check:
        return latest_info

    import asyncio

    batch_results = asyncio.run(_check_latest_batch_async(needs_check, allow_prerelease))

    for dep in needs_check:
        key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
        result = batch_results.get(key, {})

        latest = result.get("latest")
        error_msg = result.get("error")
        locked = _clean_version(dep["version"])

        if latest:
            latest_info[key] = {
                "locked": locked,
                "latest": latest,
                "delta": _calculate_version_delta(locked, latest),
                "is_outdated": locked != latest,
                "last_checked": datetime.now().isoformat(),
            }
        else:
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
                    "last_checked": datetime.now().isoformat(),
                }

    _save_deps_cache(latest_info, root_path)

    return latest_info


def _load_deps_cache(root_path: str) -> dict[str, dict[str, Any]]:
    """Load the dependency version cache from repo_index.db."""
    import sqlite3

    db_path = Path(root_path) / ".pf" / "repo_index.db"

    if not db_path.exists():
        return {}

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT manager, package_name, locked_version, latest_version, delta, is_outdated, last_checked, error
            FROM dependency_versions
        """)

        cache = {}
        for row in cursor.fetchall():
            manager, pkg_name, locked, latest, delta, is_outdated, last_checked, error = row

            key = f"{manager}:{pkg_name}:{locked}"
            cache[key] = {
                "locked": locked,
                "latest": latest,
                "delta": delta,
                "is_outdated": bool(is_outdated),
                "last_checked": last_checked,
            }
            if error:
                cache[key]["error"] = error

        conn.close()
        return cache

    except sqlite3.OperationalError as e:
        conn.close()

        if "no such table" in str(e):
            return {}

        raise


def _save_deps_cache(latest_info: dict[str, dict[str, Any]], root_path: str) -> None:
    """Save the dependency version cache to repo_index.db."""
    import sqlite3

    db_path = Path(root_path) / ".pf" / "repo_index.db"

    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

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

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dependency_versions_outdated
        ON dependency_versions(is_outdated)
    """)

    for key, info in latest_info.items():
        parts = key.split(":")
        if len(parts) < 2:
            continue
        manager = parts[0]

        if len(parts) >= 3:
            pkg_name = ":".join(parts[1:-1]) if len(parts) > 3 else parts[1]
            version_from_key = parts[-1]
        else:
            pkg_name = parts[1]
            version_from_key = ""

        cursor.execute(
            """
            INSERT OR REPLACE INTO dependency_versions
            (manager, package_name, locked_version, latest_version, delta, is_outdated, last_checked, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                manager,
                pkg_name,
                info.get("locked", version_from_key),
                info.get("latest"),
                info.get("delta"),
                1 if info.get("is_outdated") else 0,
                info.get("last_checked", ""),
                info.get("error"),
            ),
        )

    conn.commit()
    conn.close()


def _is_cache_valid(cached_item: dict[str, Any], hours: int = 24) -> bool:
    """Check if a cached item is still valid based on age."""
    try:
        if "last_checked" not in cached_item:
            return False
        last_checked = datetime.fromisoformat(cached_item["last_checked"])
        age = datetime.now() - last_checked
        return age.total_seconds() < (hours * 3600)
    except (ValueError, KeyError):
        return False


def _is_prerelease_version(version: str) -> bool:
    """Detect if a version string is a pre-release."""
    version_lower = version.lower()

    prerelease_markers = [
        "a",
        "alpha",
        "b",
        "beta",
        "rc",
        "c",
        "dev",
        "pre",
    ]

    for marker in prerelease_markers:
        if re.search(rf"[.-]?{marker}\d", version_lower):
            return True

        if version_lower.endswith(f"-{marker}") or version_lower.endswith(f".{marker}"):
            return True

    return False


def _parse_pypi_version(version_str: str) -> tuple:
    """Parse PyPI version string into comparable tuple for semantic versioning."""

    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?", version_str)
    if match:
        parts = match.groups()

        return tuple(int(p) if p else 0 for p in parts)

    return (0, 0, 0, 0)


def _calculate_version_delta(locked: str, latest: str) -> str:
    """Calculate semantic version delta."""

    docker_mgr = get_manager("docker")
    if docker_mgr:
        locked_parsed = docker_mgr._parse_docker_tag(locked)
        latest_parsed = docker_mgr._parse_docker_tag(latest)
    else:
        locked_parsed = None
        latest_parsed = None

    if locked_parsed and latest_parsed:
        locked_parts = list(locked_parsed["version"])
        latest_parts = list(latest_parsed["version"])
    else:
        try:
            locked_clean = locked.split("-")[0]
            latest_clean = latest.split("-")[0]

            locked_parts = [int(x) for x in locked_clean.split(".")[:3]]
            latest_parts = [int(x) for x in latest_clean.split(".")[:3]]
        except (ValueError, IndexError):
            return "unknown"

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
        return "unknown"


def _create_versioned_backup(path: Path) -> Path:
    """Create a versioned backup that won't overwrite existing backups."""
    base_backup = path.with_suffix(path.suffix + ".bak")

    if not base_backup.exists():
        shutil.copy2(path, base_backup)
        return base_backup

    counter = 1
    while True:
        versioned_backup = Path(f"{base_backup}.{counter}")
        if not versioned_backup.exists():
            shutil.copy2(path, versioned_backup)
            return versioned_backup
        counter += 1

        if counter > 100:
            raise RuntimeError(f"Too many backup files for {path}")


def upgrade_all_deps(
    root_path: str,
    latest_info: dict[str, dict[str, Any]],
    deps_list: list[dict[str, Any]],
    ecosystems: list[str] | None = None,
) -> dict[str, Any]:
    """Upgrade dependencies to latest versions. Returns detailed per-file info."""
    root = Path(root_path)
    # New structure: {"package.json": [{"path": "...", "count": N, "changes": [...]}], ...}
    upgraded = {
        "requirements.txt": [],
        "package.json": [],
        "pyproject.toml": [],
        "docker-compose": [],
        "dockerfile": [],
        "Cargo.toml": [],
        "go.mod": [],
    }

    if ecosystems is None:
        ecosystems = ["py", "npm", "docker", "cargo", "go"]

    deps_by_source = {}
    for dep in deps_list:
        if dep.get("manager") == "npm" and "workspace_package" in dep:
            source_key = dep["workspace_package"]
        else:
            source_key = dep.get("source", "")

        if source_key not in deps_by_source:
            deps_by_source[source_key] = []
        deps_by_source[source_key].append(dep)

    if "py" in ecosystems:
        all_req_files = list(root.glob("requirements*.txt"))
        all_req_files.extend(root.glob("*/requirements*.txt"))
        all_req_files.extend(root.glob("services/*/requirements*.txt"))
        all_req_files.extend(root.glob("apps/*/requirements*.txt"))

        for req_file in all_req_files:
            try:
                rel_path = req_file.relative_to(root)
                source_key = str(rel_path).replace("\\", "/")
            except ValueError:
                source_key = req_file.name

            if source_key in deps_by_source:
                count = _upgrade_requirements_txt(req_file, latest_info, deps_by_source[source_key])
                if count > 0:
                    upgraded["requirements.txt"].append({"path": source_key, "count": count})
            elif req_file.name in deps_by_source:
                count = _upgrade_requirements_txt(
                    req_file, latest_info, deps_by_source[req_file.name]
                )
                if count > 0:
                    upgraded["requirements.txt"].append({"path": source_key, "count": count})

    if "npm" in ecosystems:
        for source_key, source_deps in deps_by_source.items():
            if not source_deps or source_deps[0].get("manager") != "npm":
                continue

            if source_key == "package.json":
                package_path = root / "package.json"
            elif source_key.endswith("package.json"):
                package_path = root / source_key
            else:
                continue

            if package_path.exists():
                result = _upgrade_package_json(package_path, latest_info, source_deps)
                if result["count"] > 0:
                    # Use relative path for display
                    try:
                        rel_path = package_path.relative_to(root)
                        result["path"] = str(rel_path).replace("\\", "/")
                    except ValueError:
                        pass
                    upgraded["package.json"].append(result)

    if "py" in ecosystems:
        all_pyproject_files = (
            [root / "pyproject.toml"] if (root / "pyproject.toml").exists() else []
        )
        all_pyproject_files.extend(root.glob("*/pyproject.toml"))
        all_pyproject_files.extend(root.glob("services/*/pyproject.toml"))
        all_pyproject_files.extend(root.glob("apps/*/pyproject.toml"))

        for pyproject_file in all_pyproject_files:
            try:
                rel_path = pyproject_file.relative_to(root)
                source_key = str(rel_path).replace("\\", "/")
            except ValueError:
                source_key = "pyproject.toml"

            if source_key in deps_by_source:
                count = _upgrade_pyproject_toml(
                    pyproject_file, latest_info, deps_by_source[source_key]
                )
                if count > 0:
                    upgraded["pyproject.toml"].append({"path": source_key, "count": count})
            elif "pyproject.toml" in deps_by_source and pyproject_file == root / "pyproject.toml":
                count = _upgrade_pyproject_toml(
                    pyproject_file, latest_info, deps_by_source["pyproject.toml"]
                )
                if count > 0:
                    upgraded["pyproject.toml"].append({"path": source_key, "count": count})

    if "docker" in ecosystems:
        docker_mgr = get_manager("docker")
        if docker_mgr:
            docker_compose_files = list(root.glob("docker-compose*.yml")) + list(
                root.glob("docker-compose*.yaml")
            )

            for compose_file in docker_compose_files:
                try:
                    rel_path = compose_file.relative_to(root)
                    source_key = str(rel_path).replace("\\", "/")
                except ValueError:
                    source_key = compose_file.name

                docker_deps = []
                for source_key_check in [source_key, compose_file.name]:
                    if source_key_check in deps_by_source:
                        docker_deps = [
                            d
                            for d in deps_by_source[source_key_check]
                            if d.get("manager") == "docker"
                        ]
                        break

                if docker_deps:
                    _create_versioned_backup(compose_file)
                    dep_objs = [Dependency.from_dict(d) for d in docker_deps]
                    count = docker_mgr.upgrade_file(compose_file, latest_info, dep_objs)
                    if count > 0:
                        upgraded["docker-compose"].append({"path": source_key, "count": count})

            dockerfiles = list(root.glob("**/Dockerfile"))

            for dockerfile in dockerfiles:
                try:
                    rel_path = dockerfile.relative_to(root)
                    source_key = str(rel_path).replace("\\", "/")
                except ValueError:
                    source_key = str(dockerfile)

                docker_deps = []
                if source_key in deps_by_source:
                    docker_deps = [
                        d for d in deps_by_source[source_key] if d.get("manager") == "docker"
                    ]

                if docker_deps:
                    _create_versioned_backup(dockerfile)
                    dep_objs = [Dependency.from_dict(d) for d in docker_deps]
                    count = docker_mgr.upgrade_file(dockerfile, latest_info, dep_objs)
                    if count > 0:
                        upgraded["dockerfile"].append({"path": source_key, "count": count})

    if "cargo" in ecosystems:
        cargo_mgr = get_manager("cargo")
        if cargo_mgr:
            cargo_toml_files = list(root.glob("**/Cargo.toml"))

            for cargo_toml in cargo_toml_files:
                try:
                    rel_path = cargo_toml.relative_to(root)
                    source_key = str(rel_path).replace("\\", "/")
                except ValueError:
                    source_key = str(cargo_toml)

                cargo_deps = []
                if source_key in deps_by_source:
                    cargo_deps = [
                        d for d in deps_by_source[source_key] if d.get("manager") == "cargo"
                    ]
                elif "Cargo.toml" in deps_by_source:
                    cargo_deps = [
                        d for d in deps_by_source["Cargo.toml"] if d.get("manager") == "cargo"
                    ]

                if cargo_deps:
                    _create_versioned_backup(cargo_toml)
                    dep_objs = [Dependency.from_dict(d) for d in cargo_deps]
                    count = cargo_mgr.upgrade_file(cargo_toml, latest_info, dep_objs)
                    if count > 0:
                        upgraded["Cargo.toml"].append({"path": source_key, "count": count})

    if "go" in ecosystems:
        go_mgr = get_manager("go")
        if go_mgr:
            go_mod_files = list(root.glob("**/go.mod"))

            for go_mod in go_mod_files:
                try:
                    rel_path = go_mod.relative_to(root)
                    source_key = str(rel_path).replace("\\", "/")
                except ValueError:
                    source_key = str(go_mod)

                go_deps = []
                if source_key in deps_by_source:
                    go_deps = [d for d in deps_by_source[source_key] if d.get("manager") == "go"]

                if go_deps:
                    _create_versioned_backup(go_mod)
                    dep_objs = [Dependency.from_dict(d) for d in go_deps]
                    count = go_mgr.upgrade_file(go_mod, latest_info, dep_objs)
                    if count > 0:
                        upgraded["go.mod"].append({"path": source_key, "count": count})

    return upgraded


def _upgrade_requirements_txt(
    path: Path, latest_info: dict[str, dict[str, Any]], deps: list[dict[str, Any]]
) -> int:
    """Upgrade a requirements.txt file to latest versions."""
    _create_versioned_backup(path)

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    # Build name->latest lookup from latest_info (keys are "py:name:version")
    latest_versions = {}
    for key, info in latest_info.items():
        if key.startswith("py:") and info.get("latest"):
            parts = key.split(":")
            if len(parts) >= 3:
                pkg_name = parts[1]  # "py:requests:2.28.0" -> "requests"
            else:
                pkg_name = parts[1] if len(parts) > 1 else ""
            latest_versions[pkg_name] = info["latest"]

    updated_lines = []
    count = 0

    for line in lines:
        original_line = line
        line = line.strip()

        if not line or line.startswith("#") or line.startswith("-"):
            updated_lines.append(original_line)
            continue

        name, _ = _parse_python_dep_spec(line)

        if name and name in latest_versions:
            updated_lines.append(f"{name}=={latest_versions[name]}\n")
            count += 1
        else:
            updated_lines.append(original_line)

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    return count


def _upgrade_package_json(
    path: Path, latest_info: dict[str, dict[str, Any]], deps: list[dict[str, Any]]
) -> dict[str, Any]:
    """Upgrade package.json to latest versions. Returns detailed change info."""
    _create_versioned_backup(path)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    changes = []  # List of (name, old_version, new_version, delta)

    # Build name->(latest, old, delta) lookup from latest_info (keys are "npm:name:version")
    npm_latest = {}
    for key, info in latest_info.items():
        if key.startswith("npm:") and info.get("latest"):
            # Extract package name from "npm:name:version" or "npm:@scope/name:version"
            parts = key.split(":")
            if len(parts) >= 3:
                pkg_name = ":".join(parts[1:-1])  # Handle @scope/name
            else:
                pkg_name = parts[1] if len(parts) > 1 else ""
            npm_latest[pkg_name] = {
                "latest": info["latest"],
                "locked": info.get("locked", ""),
                "delta": info.get("delta", ""),
            }

    if "dependencies" in data:
        for name, current_ver in list(data["dependencies"].items()):
            if name in npm_latest:
                info = npm_latest[name]
                # Only count as change if version actually differs
                if current_ver != info["latest"]:
                    data["dependencies"][name] = info["latest"]
                    changes.append((name, current_ver, info["latest"], info["delta"]))

    if "devDependencies" in data:
        for name, current_ver in list(data["devDependencies"].items()):
            if name in npm_latest:
                info = npm_latest[name]
                # Only count as change if version actually differs
                if current_ver != info["latest"]:
                    data["devDependencies"][name] = info["latest"]
                    changes.append((name, current_ver, info["latest"], info["delta"]))

    if changes:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    return {"path": str(path), "count": len(changes), "changes": changes}


def _upgrade_pyproject_toml(
    path: Path, latest_info: dict[str, dict[str, Any]], deps: list[dict[str, Any]]
) -> int:
    """Upgrade pyproject.toml to latest versions - handles ALL sections."""
    _create_versioned_backup(path)

    with open(path, encoding="utf-8") as f:
        content = f.read()

    count = 0
    updated_packages = {}

    for key, info in latest_info.items():
        if not key.startswith("py:"):
            continue

        # Extract package name from "py:name:version" format
        parts = key.split(":")
        if len(parts) >= 3:
            package_name = parts[1]  # "py:requests:2.28.0" -> "requests"
        else:
            package_name = parts[1] if len(parts) > 1 else ""
        latest_version = info.get("latest")

        if not latest_version:
            continue

        escaped_package_name = re.escape(package_name)

        pattern_pep621 = rf'"{escaped_package_name}(\[.*?\])?([><=~!]+)([^"]+)"'

        def replacer_pep621(match, *, _pkg=package_name, _latest=latest_version):
            extras = match.group(1) or ""
            old_operator = match.group(2)
            old_version = match.group(3)
            if old_version != _latest:
                if _pkg not in updated_packages:
                    updated_packages[_pkg] = []
                updated_packages[_pkg].append((old_version, _latest))
                return f'"{_pkg}{extras}{old_operator}{_latest}"'
            return match.group(0)

        pattern_poetry = (
            rf'(?:^|\n)"?{escaped_package_name}"?\s*=\s*["\']([><=~!^]*)([\d][^"\']*)["\']'
        )

        def replacer_poetry(match, *, _pkg=package_name, _latest=latest_version):
            old_operator = match.group(1) or ""
            old_version = match.group(2)
            if old_version != _latest:
                if _pkg not in updated_packages:
                    updated_packages[_pkg] = []
                updated_packages[_pkg].append((old_version, _latest))

                quote_char = '"'
                return f"{_pkg} = {quote_char}{old_operator}{_latest}{quote_char}"
            return match.group(0)

        new_content = re.sub(pattern_pep621, replacer_pep621, content)

        new_content = re.sub(pattern_poetry, replacer_poetry, new_content, flags=re.MULTILINE)

        if package_name in updated_packages and content != new_content:
            count += 1
            content = new_content

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    total_occurrences = 0

    check_mark = "[OK]" if IS_WINDOWS else "✓"
    arrow = "->" if IS_WINDOWS else "→"
    for package, updates in updated_packages.items():
        total_occurrences += len(updates)
        if len(updates) == 1:
            console.print(
                f"  {check_mark} {package}: {updates[0][0]} {arrow} {updates[0][1]}",
                highlight=False,
            )
        else:
            console.print(
                f"  {check_mark} {package}: {updates[0][0]} {arrow} {updates[0][1]} ({len(updates)} occurrences)",
                highlight=False,
            )

    return total_occurrences


def generate_grouped_report(
    deps: list[dict[str, Any]], latest_info: dict[str, dict[str, Any]], hide_up_to_date: bool = True
) -> None:
    """Print a report grouped by SOURCE FILE path."""
    from collections import defaultdict

    arrow = "->" if IS_WINDOWS else "->"
    check = "[OK]" if IS_WINDOWS else "[OK]"
    folder = "[FILE]" if IS_WINDOWS else "[FILE]"

    files_map = defaultdict(list)
    for dep in deps:
        source = dep.get("workspace_package") or dep.get("source", "unknown")
        files_map[source].append(dep)

    def sort_key(path: str) -> tuple:
        """Sort real code first, test fixtures last."""
        is_test = any(
            x in path.lower()
            for x in [
                "test",
                "fixture",
                "mock",
                "example",
                "node_modules",
                "venv",
                ".venv",
                "__pycache__",
                "dist",
                "build",
            ]
        )
        return (is_test, path.lower())

    sorted_files = sorted(files_map.keys(), key=sort_key)

    console.print("\n" + "=" * 80, markup=False)
    console.print("DEPENDENCY HEALTH REPORT (GROUPED BY FILE)")
    console.rule()

    total_outdated = 0
    total_outdated_real = 0
    ghost_files_detected = 0
    files_with_issues = 0

    for source_file in sorted_files:
        file_deps = files_map[source_file]

        ghost_markers = [
            "test",
            "fixture",
            "mock",
            "example",
            "sample",
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            "dist",
            "build",
            "vendor",
            "third_party",
        ]
        is_ghost = any(marker in source_file.lower() for marker in ghost_markers)

        outdated_in_file = []
        for dep in file_deps:
            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
            info = latest_info.get(key)

            if info and info.get("is_outdated"):
                outdated_in_file.append((dep, info))

        if hide_up_to_date and not outdated_in_file:
            continue

        if outdated_in_file:
            files_with_issues += 1
            if is_ghost:
                ghost_files_detected += 1

        if is_ghost:
            logger.info(f"\n{folder} {source_file}")
        else:
            console.print(f"\n{folder} {source_file}", highlight=False)

        if not outdated_in_file:
            console.print(f"  {check} All dependencies up to date", highlight=False)
            continue

        for dep, info in outdated_in_file:
            total_outdated += 1
            if not is_ghost:
                total_outdated_real += 1

            name = dep["name"]
            current = info["locked"]
            latest = info["latest"]
            delta = info.get("delta", "unknown")

            if delta == "major":
                label = "[MAJOR!]"
            elif delta == "minor":
                label = "[minor]"
            elif delta == "patch":
                label = "[patch]"
            else:
                label = ""

            if is_ghost:
                console.print(
                    f"    (test) {name}: {current} {arrow} {latest} {label}", highlight=False
                )
            else:
                console.print(f"  - {name}: {current} {arrow} {latest} {label}", highlight=False)

    console.print("\n" + "-" * 80, markup=False)
    console.print("SUMMARY")
    console.rule()

    if total_outdated == 0:
        console.print("All dependencies are up to date!")
    else:
        console.print(
            f"Total outdated: {total_outdated} packages across {files_with_issues} files",
            highlight=False,
        )

        if ghost_files_detected > 0:
            real_files = files_with_issues - ghost_files_detected
            console.print(
                f"  - Real code: {total_outdated_real} packages in {real_files} files",
                highlight=False,
            )
            console.print(
                f"  - Test fixtures: {total_outdated - total_outdated_real} packages in {ghost_files_detected} files",
                highlight=False,
            )

    console.print("=" * 80 + "\n", markup=False)
