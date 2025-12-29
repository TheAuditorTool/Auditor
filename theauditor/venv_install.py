"""Pure Python venv creation and TheAuditor installation."""

import contextlib
import json
import os
import platform
import shutil
import subprocess
import tomllib
import venv
from importlib.resources import files
from pathlib import Path

from theauditor.package_managers.deps import check_latest_versions
from theauditor.pipeline.ui import console
from theauditor.utils.logging import logger

IS_WINDOWS = platform.system() == "Windows"


TRIGGER_START = "<!-- THEAUDITOR:START -->"
TRIGGER_END = "<!-- THEAUDITOR:END -->"


NODE_VERSION = "v20.11.1"
NODE_BASE_URL = "https://nodejs.org/dist"


NODE_CHECKSUMS = {
    "node-v20.11.1-win-x64.zip": "bc032628d77d206ffa7f133518a6225a9c5d6d9210ead30d67e294ff37044bda",
    "node-v20.11.1-linux-x64.tar.xz": "d8dab549b09672b03356aa2257699f3de3b58c96e74eb26a8b495fbdc9cf6fbe",
    "node-v20.11.1-linux-arm64.tar.xz": "c957f29eb4e341903520caf362534f0acd1db7be79c502ae8e283994eed07fe1",
    "node-v20.11.1-darwin-x64.tar.gz": "c52e7fb0709dbe63a4cbe08ac8af3479188692937a7bd8e776e0eedfa33bb848",
    "node-v20.11.1-darwin-arm64.tar.gz": "e0065c61f340e85106a99c4b54746c5cee09d59b08c5712f67f99e92aa44995d",
}


def _extract_pyproject_dependencies(pyproject_path: Path) -> list[str]:
    """Extract dependency strings from pyproject.toml for offline vulnerability DB seeding."""
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    dependencies: list[str] = []

    project = data.get("project")
    if isinstance(project, dict):
        proj_deps = project.get("dependencies")
        if isinstance(proj_deps, list):
            dependencies.extend(str(dep).strip() for dep in proj_deps if str(dep).strip())

    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            poetry_deps = poetry.get("dependencies")
            if isinstance(poetry_deps, dict):
                for name, spec in poetry_deps.items():
                    if str(name).lower() == "python":
                        continue
                    if isinstance(spec, str):
                        if spec.strip() in {"*", ""}:
                            dependencies.append(str(name))
                        else:
                            dependencies.append(f"{name} {spec.strip()}")
                    elif isinstance(spec, dict):
                        version = spec.get("version")
                        extras = spec.get("extras")
                        line = str(name)
                        if extras and isinstance(extras, list):
                            extras_str = ",".join(str(e) for e in extras if e)
                            if extras_str:
                                line += f"[{extras_str}]"
                        if version:
                            line += f" {version}"
                        dependencies.append(line)

    seen = set()
    unique_deps = []
    for dep in dependencies:
        norm = dep.strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique_deps.append(norm)

    return unique_deps


def _get_runtime_packages(pyproject_path: Path, package_names: list[str]) -> list[str]:
    """Extract specific package version specs from pyproject.toml optional dependencies."""
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = data.get("project", {})
        optional_deps = project.get("optional-dependencies", {})

        all_deps = []
        all_deps.extend(optional_deps.get("runtime", []))
        all_deps.extend(optional_deps.get("dev", []))

        package_map = {}
        for dep in all_deps:
            dep_str = str(dep).strip()

            for sep in ["==", ">=", "<=", "~=", ">", "<"]:
                if sep in dep_str:
                    pkg_name = dep_str.split(sep)[0].strip().lower()
                    package_map[pkg_name] = dep_str
                    break
            else:
                package_map[dep_str.lower()] = dep_str

        result = []
        for pkg_name in package_names:
            pkg_lower = pkg_name.lower()
            if pkg_lower in package_map:
                result.append(package_map[pkg_lower])
            else:
                result.append(pkg_name)

        return result
    except Exception:
        return list(package_names)


def find_theauditor_root() -> Path:
    """Find TheAuditor project root by walking up from __file__ to pyproject.toml.

    For editable installs: Returns project root containing pyproject.toml
    For pip installs: Returns site-packages directory (agents bundled in theauditor/)
    """
    current = Path(__file__).resolve().parent

    while current != current.parent:
        if (current / "pyproject.toml").exists():
            content = (current / "pyproject.toml").read_text()
            if "theauditor" in content.lower():
                return current
        current = current.parent

    # Fallback for pip-installed package: use importlib.resources
    # Returns site-packages path where theauditor package is installed
    try:
        package_path = files("theauditor")
        # files() returns a Traversable, convert to Path and get parent (site-packages)
        return Path(str(package_path)).parent
    except Exception as e:
        raise RuntimeError(
            f"Could not find TheAuditor installation root: {e}\n"
            f"Neither pyproject.toml nor importlib.resources could locate the package."
        ) from e


def _inject_agents_md(target_dir: Path) -> None:
    """Inject TheAuditor agent trigger block into AGENTS.md and CLAUDE.md in target project root."""
    trigger_block = f"""{TRIGGER_START}
# TheAuditor Agent System

**Start every task with:** `/theauditor:start` or `aud blueprint --structure`

## Quick Route
| Intent | Slash Command |
|--------|---------------|
| Any task (orchestrator) | `/theauditor:start` |
| Plan changes | `/theauditor:planning` |
| Refactor code | `/theauditor:refactor` |
| Security audit | `/theauditor:security` |
| Trace dataflow | `/theauditor:dataflow` |
| Assess impact | `/theauditor:impact` |

## Command Cheat Sheet
| Need | Command |
|------|---------|
| Architecture overview | `aud blueprint --structure` (ALWAYS FIRST) |
| List symbols in file | `aud query --file X --list all` |
| Who calls this? | `aud query --symbol X --show-callers` |
| Validation boundaries | `aud boundaries` |
| Dead code | `aud deadcode` |
| Blast radius | `aud impact --symbol X` |
| Full context | `aud explain path/to/file.py` |

## The Rules
1. **Database First** - Query before reading files
2. **Check flags** - Run `aud <cmd> --help` before guessing
3. **Cite evidence** - Every claim backed by query result
4. **Autonomous** - Execute commands, don't ask permission

**Full docs:** @/.auditor_venv/.theauditor_tools/agents/AGENTS.md
**Reinstall:** `aud setup-ai --target . --sync`
{TRIGGER_END}
"""

    check_mark = "[OK]" if IS_WINDOWS else "✓"

    for filename in ["AGENTS.md", "CLAUDE.md"]:
        target_file = target_dir / filename

        if not target_file.exists():
            target_file.write_text(trigger_block + "\n", encoding="utf-8")
            logger.info(f"    {check_mark} Created {filename} with agent triggers")
        else:
            content = target_file.read_text(encoding="utf-8")
            if TRIGGER_START in content:
                logger.info(f"    {check_mark} {filename} already has agent triggers")
            else:
                new_content = trigger_block + "\n" + content
                target_file.write_text(new_content, encoding="utf-8")
                logger.info(f"    {check_mark} Injected agent triggers into {filename}")


def get_venv_paths(venv_path: Path) -> tuple[Path, Path]:
    """Get platform-specific paths for venv Python and aud executables."""
    if platform.system() == "Windows":
        python_exe = venv_path / "Scripts" / "python.exe"
        aud_exe = venv_path / "Scripts" / "aud.exe"
    else:
        python_exe = venv_path / "bin" / "python"
        aud_exe = venv_path / "bin" / "aud"

    return python_exe, aud_exe


def create_venv(target_dir: Path, force: bool = False) -> Path:
    """Create a Python virtual environment at target_dir/.venv."""
    venv_path = target_dir / ".auditor_venv"

    if venv_path.exists() and not force:
        python_exe, _ = get_venv_paths(venv_path)
        if python_exe.exists():
            check_mark = "[OK]"
            logger.info(f"{check_mark} Venv already exists: {venv_path}")
            return venv_path
        else:
            logger.warning(f"Venv exists but is broken (missing {python_exe})")
            logger.info("Removing broken venv and recreating...")
            try:
                shutil.rmtree(venv_path)
            except Exception as e:
                logger.error(f"Failed to remove broken venv: {e}")
                logger.info(f"Manually delete {venv_path} and retry")
                raise RuntimeError(f"Cannot remove broken venv: {e}") from e

    logger.info(f"Creating venv at {venv_path}...")

    builder = venv.EnvBuilder(
        system_site_packages=False,
        clear=force,
        symlinks=(platform.system() != "Windows"),
        upgrade=False,
        with_pip=True,
        prompt=f"[{target_dir.name}]",
    )

    builder.create(venv_path)
    check_mark = "[OK]"
    logger.info(f"{check_mark} Created venv: {venv_path}")

    return venv_path


def install_theauditor_editable(venv_path: Path, theauditor_root: Path | None = None) -> bool:
    """Install TheAuditor in editable mode into the venv."""
    if theauditor_root is None:
        theauditor_root = find_theauditor_root()

    python_exe, aud_exe = get_venv_paths(venv_path)

    if not python_exe.exists():
        raise RuntimeError(
            f"Venv Python not found: {python_exe}\n"
            f"The venv appears to be broken. Try running with --sync flag to recreate it:\n"
            f"  aud setup-ai --target . --sync"
        )

    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "show", "theauditor"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode == 0:
            check_mark = "[OK]"
            logger.info(f"{check_mark} TheAuditor already installed in {venv_path}")
            logger.info("  Upgrading to ensure latest version...")
    except subprocess.TimeoutExpired:
        logger.info("Warning: pip show timed out, proceeding with install")

    is_source_tree = (theauditor_root / "pyproject.toml").exists()

    cmd = [str(python_exe), "-m", "pip", "install", "--no-cache-dir"]

    if is_source_tree:
        logger.info(f"Installing TheAuditor (editable) from {theauditor_root}...")
        cmd.extend(["-e", f"{theauditor_root}[all]"])
    else:
        from theauditor import __version__

        logger.info(
            f"Source config not found (user mode). Installing v{__version__} from PyPI..."
        )
        cmd.append(f"theauditor[all]=={__version__}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(venv_path.parent) if is_source_tree else None,
        )

        if result.returncode != 0:
            logger.info("Error installing TheAuditor:")
            logger.info(result.stderr)
            return False

        check_mark = "[OK]"
        if is_source_tree:
            logger.info(f"{check_mark} Installed TheAuditor (editable) from {theauditor_root}")
        else:
            logger.info(f"{check_mark} Installed TheAuditor from PyPI")

        if aud_exe.exists():
            check_mark = "[OK]"
            logger.info(f"{check_mark} Executable available: {aud_exe}")
        else:
            verify_result = subprocess.run(
                [str(python_exe), "-m", "theauditor.cli", "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if verify_result.returncode == 0:
                check_mark = "[OK]"
                logger.info(f"{check_mark} Module available: python -m theauditor.cli")
            else:
                logger.info("Warning: Could not verify TheAuditor installation")

        return True

    except subprocess.TimeoutExpired:
        logger.info("Error: Installation timed out after 120 seconds")
        return False
    except Exception as e:
        logger.info(f"Error during installation: {e}")
        return False


def _self_update_package_json(package_json_path: Path) -> int:
    """Self-update package.json with latest versions from npm registry."""
    try:
        with open(package_json_path) as f:
            data = json.load(f)

        deps_to_check = []

        if "dependencies" in data:
            for name, version in data["dependencies"].items():
                deps_to_check.append(
                    {
                        "name": name,
                        "version": version.lstrip("^~>="),
                        "manager": "npm",
                        "source": str(package_json_path),
                        "section": "dependencies",
                    }
                )

        if "devDependencies" in data:
            for name, version in data["devDependencies"].items():
                deps_to_check.append(
                    {
                        "name": name,
                        "version": version.lstrip("^~>="),
                        "manager": "npm",
                        "source": str(package_json_path),
                        "section": "devDependencies",
                    }
                )

        if not deps_to_check:
            logger.info("    No dependencies to check")
            return 0

        logger.info(f"    Checking {len(deps_to_check)} npm packages...")
        latest_info = check_latest_versions(
            deps_to_check,
            allow_net=True,
            offline=False,
            allow_prerelease=False,
            root_path=str(package_json_path.parent),
        )

        updated_count = 0
        check_mark = "[OK]" if IS_WINDOWS else "[OK]"
        arrow = "->" if IS_WINDOWS else "->"

        for dep in deps_to_check:
            key = f"{dep['manager']}:{dep['name']}:{dep['version']}"
            info = latest_info.get(key, {})

            if info.get("is_outdated") and info.get("latest"):
                section = dep["section"]
                name = dep["name"]
                current = data[section][name]
                latest = info["latest"]

                data[section][name] = f"^{latest}"
                updated_count += 1
                logger.info(f"      {check_mark} {name}: {current} {arrow} ^{latest}")

        if updated_count > 0:
            with open(package_json_path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            logger.info(f"    Updated {updated_count} packages to latest versions")
        else:
            logger.info("    All packages already at latest versions")

        return updated_count

    except Exception as e:
        logger.warning(f"Could not self-update package.json: {e}")
        return 0


def download_portable_node(sandbox_dir: Path) -> Path:
    """Download and extract portable Node.js runtime with integrity verification."""
    import hashlib
    import tarfile
    import urllib.error
    import urllib.request
    import zipfile

    node_runtime_dir = sandbox_dir / "node-runtime"

    system = platform.system()
    machine = platform.machine().lower()

    if system == "Windows":
        node_exe = node_runtime_dir / "node.exe"
        archive_name = f"node-{NODE_VERSION}-win-x64.zip"
        archive_type = "zip"
    elif system == "Linux":
        node_exe = node_runtime_dir / "bin" / "node"
        if "arm" in machine or "aarch" in machine:
            archive_name = f"node-{NODE_VERSION}-linux-arm64.tar.xz"
        else:
            archive_name = f"node-{NODE_VERSION}-linux-x64.tar.xz"
        archive_type = "tar"
    elif system == "Darwin":
        node_exe = node_runtime_dir / "bin" / "node"
        if "arm" in machine:
            archive_name = f"node-{NODE_VERSION}-darwin-arm64.tar.gz"
        else:
            archive_name = f"node-{NODE_VERSION}-darwin-x64.tar.gz"
        archive_type = "tar"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    if node_exe.exists():
        check_mark = "[OK]"
        logger.info(f"    {check_mark} Node.js runtime already installed at {node_runtime_dir}")
        return node_exe

    expected_checksum = NODE_CHECKSUMS.get(archive_name)

    if not expected_checksum:
        raise RuntimeError(
            f"No checksum available for {archive_name}. Update NODE_CHECKSUMS in venv_install.py"
        )

    node_url = f"{NODE_BASE_URL}/{NODE_VERSION}/{archive_name}"
    logger.info(f"    Downloading Node.js {NODE_VERSION} for {system} {machine}...")
    logger.info(f"    URL: {node_url}")

    try:
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            TextColumn,
            TransferSpeedColumn,
        )

        download_path = sandbox_dir / "node_download"

        with urllib.request.urlopen(node_url) as response:
            total_size = int(response.headers.get("Content-Length", 0))

            with Progress(
                TextColumn("    "),
                BarColumn(bar_width=40),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=console,
                transient=False,
            ) as progress:
                task = progress.add_task("Downloading", total=total_size)

                with open(download_path, "wb") as f:
                    chunk_size = 8192
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))

        logger.info("    Verifying SHA-256 checksum...")
        sha256_hash = hashlib.sha256()
        with open(download_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        actual_checksum = sha256_hash.hexdigest()
        if actual_checksum != expected_checksum:
            download_path.unlink()
            raise RuntimeError(
                f"Checksum verification failed!\n"
                f"    Expected: {expected_checksum}\n"
                f"    Actual:   {actual_checksum}\n"
                f"    This may indicate a corrupted download or security issue."
            )

        check_mark = "[OK]"
        logger.info(f"    {check_mark} Checksum verified: {actual_checksum[:16]}...")

        logger.info("    Extracting Node.js runtime...")
        if archive_type == "zip":
            with zipfile.ZipFile(download_path) as zf:
                temp_extract = sandbox_dir / "temp_node"
                temp_extract.mkdir(exist_ok=True)
                zf.extractall(temp_extract)

                extracted = list(temp_extract.glob("node-*"))[0]

                shutil.move(str(extracted), str(node_runtime_dir))
                if temp_extract.exists():
                    temp_extract.rmdir()
        else:
            with tarfile.open(download_path, "r:*") as tf:
                temp_extract = sandbox_dir / "temp_node"
                temp_extract.mkdir(exist_ok=True)
                tf.extractall(temp_extract)

                extracted = list(temp_extract.glob("node-*"))[0]

                shutil.move(str(extracted), str(node_runtime_dir))
                if temp_extract.exists():
                    temp_extract.rmdir()

        download_path.unlink()

        check_mark = "[OK]"
        logger.info(f"    {check_mark} Node.js runtime installed at {node_runtime_dir}")
        return node_exe

    except urllib.error.URLError as e:
        logger.info(f"    \\[X] Network error downloading Node.js: {e}")
        raise RuntimeError(f"Failed to download Node.js: {e}") from e
    except Exception as e:
        logger.info(f"    \\[X] Failed to install Node.js: {e}")

        if "download_path" in locals() and download_path.exists():
            download_path.unlink()
        raise RuntimeError(f"Failed to install Node.js: {e}") from e


def setup_osv_scanner(sandbox_dir: Path) -> Path | None:
    """Download and install OSV-Scanner binary for vulnerability detection."""
    import urllib.error
    import urllib.request

    logger.info("  Setting up OSV-Scanner (Google's vulnerability scanner)...")

    osv_dir = sandbox_dir / "osv-scanner"
    osv_dir.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    if system == "Windows":
        binary_name = "osv-scanner.exe"
        download_filename = "osv-scanner_windows_amd64.exe"
    elif system == "Darwin":
        binary_name = "osv-scanner"
        download_filename = "osv-scanner_darwin_amd64"
    else:
        binary_name = "osv-scanner"
        download_filename = "osv-scanner_linux_amd64"

    binary_path = osv_dir / binary_name
    db_dir = osv_dir / "db"
    db_dir.mkdir(exist_ok=True)

    check_mark = "[OK]"
    temp_files: list[Path] = []

    if binary_path.exists():
        logger.info(f"    {check_mark} OSV-Scanner already installed at {osv_dir}")
    else:
        url = f"https://github.com/google/osv-scanner/releases/latest/download/{download_filename}"
        logger.info("    Downloading OSV-Scanner from GitHub releases...")
        logger.info(f"    URL: {url}")

        try:
            urllib.request.urlretrieve(url, str(binary_path))

            if system != "Windows":
                import stat

                st = binary_path.stat()
                binary_path.chmod(st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            logger.info(f"    {check_mark} OSV-Scanner binary downloaded successfully")
        except urllib.error.URLError as e:
            logger.warning(f"Network error downloading OSV-Scanner: {e}")
            logger.warning(
                "You can manually download from: https://github.com/google/osv-scanner/releases"
            )
            return None
        except Exception as e:
            logger.warning(f"Failed to install OSV-Scanner: {e}")
            if binary_path.exists():
                binary_path.unlink()
            return None

    logger.info(f"    {check_mark} Database cache directory: {db_dir}")

    try:
        logger.info("")
        logger.info("    Downloading offline vulnerability databases...")
        logger.info("    This may take 5-10 minutes and use 100-500MB disk space")
        logger.info("    Downloading databases for: npm, PyPI")

        try:
            env = {**os.environ, "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": str(db_dir)}

            lockfiles = {}
            target_dir = sandbox_dir.parent.parent

            npm_lockfile_names = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
            for name in npm_lockfile_names:
                lock = target_dir / name
                if lock.exists():
                    lockfiles["npm"] = lock
                    break

                found_locks = list(target_dir.glob(f"*/{name}"))
                if found_locks:
                    found_locks.sort(key=lambda p: len(str(p)))
                    lockfiles["npm"] = found_locks[0]
                    break

            if "npm" not in lockfiles:
                pkg_json = target_dir / "package.json"
                if pkg_json.exists():
                    logger.info(
                        "package.json found but no package-lock.json (npm install not run) - skipping npm database"
                    )

            python_lockfile_names = ["requirements.txt", "Pipfile.lock", "poetry.lock"]
            for name in python_lockfile_names:
                req = target_dir / name
                if req.exists():
                    lockfiles["PyPI"] = req
                    break

                found_reqs = list(target_dir.glob(f"*/{name}"))
                if found_reqs:
                    found_reqs.sort(key=lambda p: len(str(p)))
                    lockfiles["PyPI"] = found_reqs[0]
                    break

            if "PyPI" not in lockfiles:
                pyproject = target_dir / "pyproject.toml"
                if pyproject.exists():
                    deps = _extract_pyproject_dependencies(pyproject)
                    if deps:
                        temp_req = sandbox_dir / "pyproject_requirements.txt"
                        temp_req.write_text("\n".join(deps), encoding="utf-8")
                        lockfiles["PyPI"] = temp_req
                        temp_files.append(temp_req)
                        logger.info("    ℹ Generated temporary requirements from pyproject.toml")

            cmd = [str(binary_path), "scan"]

            for _ecosystem, lockfile in lockfiles.items():
                cmd.extend(["-L", str(lockfile)])

            if not lockfiles:
                logger.info("    ℹ No lockfiles found - skipping vulnerability database download")
                return binary_path
            else:
                ecosystems = ", ".join(lockfiles.keys())
                logger.info(f"    Found lockfiles for: {ecosystems}")

            cmd.extend(
                [
                    "--offline-vulnerabilities",
                    "--download-offline-databases",
                    "--format",
                    "json",
                    "--allow-no-lockfiles",
                ]
            )

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(target_dir),
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode > 1:
                logger.warning(f"\\ OSV-Scanner failed with exit code {result.returncode}")
                if result.stderr:
                    logger.info("    Error output (first 15 lines):")
                    for line in result.stderr.split("\n")[:15]:
                        if line.strip():
                            logger.info(f"      {line}")
            elif result.returncode == 1:
                if result.stderr:
                    for line in result.stderr.split("\n")[:3]:
                        if "scanned" in line.lower() or "found" in line.lower():
                            logger.info(f"    {line.strip()}")
            else:
                if result.stdout and "packages" in result.stdout.lower():
                    for line in result.stdout.split("\n")[:5]:
                        if "scanned" in line.lower() or "packages" in line.lower():
                            logger.info(f"    {line.strip()}")

            npm_db = db_dir / "osv-scanner" / "npm" / "all.zip"
            pypi_db = db_dir / "osv-scanner" / "PyPI" / "all.zip"

            if npm_db.exists():
                npm_size = npm_db.stat().st_size / (1024 * 1024)
                logger.info(
                    f"    {check_mark} npm vulnerability database downloaded ({npm_size:.1f} MB)"
                )
            else:
                if "npm" in lockfiles:
                    logger.info(
                        "    [warning]npm database download failed - online mode will use API[/warning]"
                    )
                else:
                    logger.info("    ℹ No npm lockfile found - npm database not needed")

            if pypi_db.exists():
                pypi_size = pypi_db.stat().st_size / (1024 * 1024)
                logger.info(
                    f"    {check_mark} PyPI vulnerability database downloaded ({pypi_size:.1f} MB)"
                )
            else:
                if "PyPI" in lockfiles:
                    logger.info(
                        "    [warning]PyPI database download failed - online mode will use API[/warning]"
                    )
                else:
                    logger.info("    ℹ No Python lockfile found - PyPI database not needed")

            if npm_db.exists() or pypi_db.exists():
                logger.info(f"    {check_mark} Offline vulnerability scanning ready")
            else:
                logger.info(
                    "    [warning]Database download failed - scanner will use online API mode[/warning]"
                )
                logger.info("    [warning]To retry manually, run:[/warning]")
                logger.info(f"      export OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY={db_dir}")
                logger.info(
                    f"      {binary_path} scan -r . --offline-vulnerabilities --download-offline-databases"
                )

        except subprocess.TimeoutExpired:
            logger.info("    [warning]Database download timed out after 10 minutes[/warning]")
            logger.info("    [warning]Scanner will use online API mode[/warning]")
            logger.warning(f"\\ To retry: delete {db_dir} and run setup again")
        except Exception as e:
            logger.warning(f"\\ Database download failed: {e}")
            logger.info("    [warning]Scanner will use online API mode[/warning]")
            logger.info("    [warning]To retry manually:[/warning]")
            logger.info(f"      export OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY={db_dir}")
            logger.info(
                f"      {binary_path} scan -r . --offline-vulnerabilities --download-offline-databases"
            )
        finally:
            for tmp in temp_files:
                with contextlib.suppress(OSError):
                    if tmp.exists():
                        tmp.unlink()

        return binary_path

    except urllib.error.URLError as e:
        logger.warning(f"\\ Network error downloading OSV-Scanner: {e}")
        logger.info(
            "    [warning]You can manually download from: https://github.com/google/osv-scanner/releases[/warning]"
        )
        return None
    except Exception as e:
        logger.warning(f"\\ Failed to install OSV-Scanner: {e}")

        if binary_path.exists():
            binary_path.unlink()
        return None


def setup_project_venv(target_dir: Path, force: bool = False) -> tuple[Path, bool]:
    """Complete venv setup: create and install TheAuditor + ALL linting tools."""
    target_dir = Path(target_dir).resolve()

    if not target_dir.exists():
        raise ValueError(f"Target directory does not exist: {target_dir}")

    try:
        venv_path = create_venv(target_dir, force)
    except RuntimeError as e:
        logger.error(f"Failed to create venv: {e}")
        return target_dir / ".auditor_venv", False

    success = install_theauditor_editable(venv_path)

    if success:
        logger.info("\nInstalling Python linting tools...")
        python_exe, aud_exe = get_venv_paths(venv_path)
        theauditor_root = find_theauditor_root()

        logger.info("  Checking for latest linter versions...")
        try:
            if aud_exe.exists():
                result = subprocess.run(
                    [str(aud_exe), "deps", "--upgrade-all", "--root", str(theauditor_root)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )
                if result.returncode == 0:
                    check_mark = "[OK]"
                    logger.info(f"    {check_mark} Updated to latest package versions")
        except Exception as e:
            logger.warning(f"\\ Could not update versions: {e}")

        try:
            logger.info("  Installing linters and AST tools from pyproject.toml...")

            pyproject_path = theauditor_root / "pyproject.toml"
            linter_packages = _get_runtime_packages(
                pyproject_path,
                [
                    "ruff",
                    "mypy",
                    "black",
                    "bandit",
                    "pylint",
                    "sqlparse",
                    "dockerfile-parse",
                    # Mypy plugins for framework-specific type checking
                    "pydantic>=2.0",  # Includes pydantic.mypy plugin
                    "django-stubs>=5.0.0",  # Includes mypy_django_plugin.main
                    "sqlalchemy[mypy]>=2.0",  # Includes sqlalchemy.ext.mypy.plugin
                ],
            )

            result = subprocess.run(
                [str(python_exe), "-m", "pip", "install"] + linter_packages,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )

            if result.returncode == 0:
                check_mark = "[OK]"
                logger.info(f"    {check_mark} Python linters installed")

                logger.info("  Installing tree-sitter AST tools...")

                ast_packages = _get_runtime_packages(
                    pyproject_path, ["tree-sitter", "tree-sitter-language-pack"]
                )

                result2 = subprocess.run(
                    [str(python_exe), "-m", "pip", "install"] + ast_packages,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )

                if result2.returncode == 0:
                    logger.info(f"    {check_mark} AST tools installed")
                    logger.info(f"    {check_mark} All Python tools ready:")
                    logger.info("        - Linters: ruff, mypy, black, bandit, pylint")
                    logger.info("        - Parsers: sqlparse, dockerfile-parse")
                    logger.info("        - AST analysis: tree-sitter (Python/JS/TS)")
                else:
                    logger.warning(f"\\ Tree-sitter installation failed: {result2.stderr[:200]}")
            else:
                logger.warning(f"\\ Some linters failed to install: {result.stderr[:200]}")
        except Exception as e:
            logger.warning(f"\\ Error installing tools: {e}")

        logger.info("\nSetting up JavaScript/TypeScript tools in sandboxed environment...")

        sandbox_dir = venv_path / ".theauditor_tools"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        sandbox_package_json = sandbox_dir / "package.json"

        logger.info(f"  Creating sandboxed tools directory: {sandbox_dir}")

        package_source = theauditor_root / "theauditor" / "linters" / "package.json"

        if package_source.exists():
            with open(package_source) as f:
                package_data = json.load(f)
        else:
            logger.warning(f"\\ Package.json not found at {package_source}, using minimal config")
            package_data = {
                "name": "theauditor-tools",
                "version": "1.0.0",
                "private": True,
                "description": "Sandboxed tools for TheAuditor static analysis",
                "devDependencies": {
                    "eslint": "^9.14.0",
                    "@eslint/js": "^9.14.0",
                    "typescript": "^5.6.3",
                },
            }

        with open(sandbox_package_json, "w") as f:
            json.dump(package_data, f, indent=2)

        # ESLint config is now generated dynamically by ConfigGenerator to .pf/temp/
        # No need to copy a static config - it was removed in commit f88e2995

        python_config_source = theauditor_root / "theauditor" / "linters" / "pyproject_template.toml"
        python_config_dest = sandbox_dir / "pyproject.toml"

        if python_config_source.exists():
            shutil.copy2(str(python_config_source), str(python_config_dest))
            check_mark = "[OK]"
            logger.info(f"    {check_mark} Python linter config (pyproject.toml) copied to sandbox")
        else:
            logger.warning(f"\\ Python config not found at {python_config_source}")

        # Try file path first (editable install), then importlib.resources (pip install)
        agents_source = theauditor_root / "theauditor" / "agents"
        agents_dest = sandbox_dir / "agents"

        agent_files = []
        if agents_source.exists() and agents_source.is_dir():
            agent_files = list(agents_source.glob("*.md"))
        else:
            # Pip-installed package: use importlib.resources
            try:
                agents_package = files("theauditor.agents")
                agents_dest.mkdir(exist_ok=True)
                for item in agents_package.iterdir():
                    if item.name.endswith(".md"):
                        dest_file = agents_dest / item.name
                        dest_file.write_text(item.read_text(), encoding="utf-8")
                        agent_files.append(dest_file)
            except Exception as e:
                logger.warning(f"\\ Could not access agents via importlib.resources: {e}")

        if agent_files:
            agents_dest.mkdir(exist_ok=True)

            # Copy files if using file path approach
            if agents_source.exists():
                for agent_file in agent_files:
                    dest_file = agents_dest / agent_file.name
                    shutil.copy2(str(agent_file), str(dest_file))

            check_mark = "[OK]"
            logger.info(
                f"    {check_mark} Planning agents copied to sandbox ({len(agent_files)} agents)"
            )
            logger.info(f"        -> {agents_dest}")

            _inject_agents_md(target_dir)
        else:
            logger.warning(f"\\ No agent files found in {agents_source}")

        # Try file path first (editable install), then importlib.resources (pip install)
        commands_source = theauditor_root / "theauditor" / "agents" / "commands"
        commands_dest = target_dir / ".claude" / "commands" / "theauditor"

        command_files = []
        if commands_source.exists() and commands_source.is_dir():
            command_files = list(commands_source.glob("*.md"))
        else:
            # Pip-installed package: use importlib.resources
            try:
                commands_package = files("theauditor.agents.commands")
                commands_dest.mkdir(parents=True, exist_ok=True)
                for item in commands_package.iterdir():
                    if item.name.endswith(".md"):
                        dest_file = commands_dest / item.name
                        dest_file.write_text(item.read_text(), encoding="utf-8")
                        command_files.append(dest_file)
            except Exception as e:
                logger.warning(f"\\ Could not access commands via importlib.resources: {e}")

        if command_files:
            commands_dest.mkdir(parents=True, exist_ok=True)

            # Copy files if using file path approach
            if commands_source.exists():
                for command_file in command_files:
                    dest_file = commands_dest / command_file.name
                    shutil.copy2(str(command_file), str(dest_file))

            check_mark = "[OK]" if IS_WINDOWS else "✓"
            logger.info(
                f"    {check_mark} Slash commands copied to project ({len(command_files)} commands)"
            )
            logger.info(f"        -> {commands_dest}")
            logger.info(
                "        Available: /theauditor:planning, /theauditor:security, /theauditor:refactor, /theauditor:dataflow"
            )
        else:
            logger.warning(f"\\ No command files found in {commands_source}")

        tsconfig = sandbox_dir / "tsconfig.json"
        tsconfig_data = {
            "compilerOptions": {
                "target": "ES2020",
                "module": "commonjs",
                "lib": ["ES2020"],
                "strict": True,
                "noImplicitAny": True,
                "strictNullChecks": True,
                "strictFunctionTypes": True,
                "strictBindCallApply": True,
                "strictPropertyInitialization": True,
                "noImplicitThis": True,
                "alwaysStrict": True,
                "noUnusedLocals": True,
                "noUnusedParameters": True,
                "noImplicitReturns": True,
                "noFallthroughCasesInSwitch": True,
                "esModuleInterop": True,
                "skipLibCheck": True,
                "forceConsistentCasingInFileNames": True,
            },
            "include": ["**/*"],
            "exclude": ["node_modules", ".auditor_venv"],
        }
        with open(tsconfig, "w") as f:
            json.dump(tsconfig_data, f, indent=2)

        import concurrent.futures

        node_exe = None
        node_error = None

        def track_a_package_updates():
            """Track A: Update package.json with latest versions."""
            logger.debug("Checking for latest tool versions...")
            _self_update_package_json(sandbox_package_json)

        def track_b_node_download():
            """Track B: ONLY download Node.js, nothing else."""
            nonlocal node_exe, node_error
            try:
                logger.debug("Setting up portable Node.js runtime...")
                node_exe = download_portable_node(sandbox_dir)
            except Exception as e:
                node_error = e

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            track_a_future = executor.submit(track_a_package_updates)
            track_b_future = executor.submit(track_b_node_download)

            concurrent.futures.wait([track_a_future, track_b_future])

        if node_error:
            raise RuntimeError(f"Failed to download Node.js: {node_error}")
        if not node_exe:
            raise RuntimeError("Node.js download completed but executable not found")

        try:
            node_runtime_dir = sandbox_dir / "node-runtime"

            if os.name == "nt":
                npm_cli = node_runtime_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"
                if npm_cli.exists():
                    npm_cmd = [str(node_exe), str(npm_cli)]
                else:
                    npm_cmd_path = node_runtime_dir / "npm.cmd"
                    npm_cmd = [str(npm_cmd_path)]
            else:
                npm_script = node_runtime_dir / "bin" / "npm"
                npm_cmd = [str(npm_script)]

            logger.info("  Installing JS/TS linters using bundled Node.js...")
            full_cmd = npm_cmd + ["install"]

            result = subprocess.run(
                full_cmd,
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                shell=False,
            )

            if result.returncode == 0:
                check_mark = "[OK]"
                logger.info(f"    {check_mark} JavaScript/TypeScript tools installed in sandbox")
                logger.info(f"    {check_mark} Tools isolated from project: {sandbox_dir}")
                logger.info(f"    {check_mark} Using bundled Node.js - no system dependency!")

                eslint_path = (
                    sandbox_dir
                    / "node_modules"
                    / ".bin"
                    / ("eslint.cmd" if os.name == "nt" else "eslint")
                )
                if eslint_path.exists():
                    logger.info(f"    {check_mark} ESLint verified at: {eslint_path}")
            else:
                logger.warning(f"\\ npm install failed: {result.stderr[:500]}")
                logger.info(
                    "    [warning]This may be a network issue. Try running setup again.[/warning]"
                )

            extractor_dir = Path(__file__).parent / "ast_extractors" / "javascript"
            if extractor_dir.exists():
                logger.info("  Installing JS extractor dependencies using bundled Node.js...")
                extractor_result = subprocess.run(
                    full_cmd,
                    cwd=str(extractor_dir),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    shell=False,
                )
                if extractor_result.returncode == 0:
                    check_mark = "[OK]"
                    logger.info(f"    {check_mark} JS extractor dependencies installed")
                else:
                    logger.warning(
                        f"\\ npm install failed (js extractor): {extractor_result.stderr[:500]}"
                    )
                    logger.info(
                        "    [warning]JS extractor rebuilds will fail without dependencies[/warning]"
                    )
            else:
                logger.warning(f"\\ JS extractor package not found: {extractor_dir}")

        except RuntimeError as e:
            logger.warning(f"\\ Could not set up bundled Node.js: {e}")
            logger.info(
                "    [warning]JavaScript/TypeScript linting will not be available[/warning]"
            )
            logger.info("    [warning]To retry: Delete .auditor_venv and run setup again[/warning]")
        except Exception as e:
            logger.warning(f"\\ Unexpected error setting up JS tools: {e}")

        logger.info("\nSetting up vulnerability scanning tools...")

        osv_scanner_path = setup_osv_scanner(sandbox_dir)
        if osv_scanner_path:
            check_mark = "[OK]"
            logger.info(f"{check_mark} OSV-Scanner ready for vulnerability detection")
        else:
            logger.info(
                "[warning]OSV-Scanner setup failed - vulnerability detection may be limited[/warning]"
            )

    return venv_path, success
