"""Pure Python venv creation and TheAuditor installation."""

import contextlib
import json
import os
import platform
import shutil
import subprocess
import venv
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore


from theauditor.deps import check_latest_versions
from theauditor.utils.temp_manager import TempManager

IS_WINDOWS = platform.system() == "Windows"


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
    """
    Extract specific package version specs from pyproject.toml optional dependencies.

    Single source of truth for package versions - reads from pyproject.toml instead of hardcoding.
    Searches both 'runtime' and 'dev' sections.

    Args:
        pyproject_path: Path to pyproject.toml
        package_names: List of package names to extract (e.g., ['tree-sitter', 'ruff'])

    Returns:
        List of package specs in pip format (e.g., ['tree-sitter==0.25.2', 'ruff==0.14.5'])
        Falls back to package names without versions if parsing fails.
    """
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
    """Find TheAuditor project root by walking up from __file__ to pyproject.toml."""
    current = Path(__file__).resolve().parent

    while current != current.parent:
        if (current / "pyproject.toml").exists():
            content = (current / "pyproject.toml").read_text()
            if "theauditor" in content.lower():
                return current
        current = current.parent

    raise RuntimeError("Could not find TheAuditor project root (pyproject.toml)")


def _inject_agents_md(target_dir: Path) -> None:
    """
    Inject TheAuditor agent trigger block into AGENTS.md and CLAUDE.md in target project root.

    Creates files if they don't exist, or injects trigger block if not already present.
    This tells AI assistants where to find specialized agent workflows.
    """
    TRIGGER_START = "<!-- THEAUDITOR:START -->"
    TRIGGER_END = "<!-- THEAUDITOR:END -->"

    TRIGGER_BLOCK = f"""{TRIGGER_START}
# TheAuditor Agent System

For full documentation, see: @/.auditor_venv/.theauditor_tools/agents/AGENTS.md

**Quick Route:**
| Intent | Agent | Triggers |
|--------|-------|----------|
| Plan changes | planning.md | plan, architecture, design, structure |
| Refactor code | refactor.md | refactor, split, extract, modularize |
| Security audit | security.md | security, vulnerability, XSS, SQLi, CSRF |
| Trace dataflow | dataflow.md | dataflow, trace, source, sink |

**The One Rule:** Database first. Always run `aud blueprint --structure` before planning.

**Agent Locations:**
- Full protocols: .auditor_venv/.theauditor_tools/agents/*.md
- Slash commands: /theauditor:planning, /theauditor:security, /theauditor:refactor, /theauditor:dataflow

**Setup:** Run `aud setup-ai --target . --sync` to reinstall agents.

{TRIGGER_END}
"""

    check_mark = "[OK]" if IS_WINDOWS else "✓"

    for filename in ["AGENTS.md", "CLAUDE.md"]:
        target_file = target_dir / filename

        if not target_file.exists():
            target_file.write_text(TRIGGER_BLOCK + "\n", encoding="utf-8")
            print(f"    {check_mark} Created {filename} with agent triggers")
        else:
            content = target_file.read_text(encoding="utf-8")
            if TRIGGER_START in content:
                print(f"    {check_mark} {filename} already has agent triggers")
            else:
                new_content = TRIGGER_BLOCK + "\n" + content
                target_file.write_text(new_content, encoding="utf-8")
                print(f"    {check_mark} Injected agent triggers into {filename}")


def get_venv_paths(venv_path: Path) -> tuple[Path, Path]:
    """
    Get platform-specific paths for venv Python and aud executables.

    Returns:
        (python_exe, aud_exe) paths
    """
    if platform.system() == "Windows":
        python_exe = venv_path / "Scripts" / "python.exe"
        aud_exe = venv_path / "Scripts" / "aud.exe"
    else:
        python_exe = venv_path / "bin" / "python"
        aud_exe = venv_path / "bin" / "aud"

    return python_exe, aud_exe


def create_venv(target_dir: Path, force: bool = False) -> Path:
    """
    Create a Python virtual environment at target_dir/.venv.

    Args:
        target_dir: Project root directory
        force: If True, recreate even if exists

    Returns:
        Path to the created venv directory
    """
    venv_path = target_dir / ".auditor_venv"

    if venv_path.exists() and not force:
        python_exe, _ = get_venv_paths(venv_path)
        if python_exe.exists():
            check_mark = "[OK]"
            print(f"{check_mark} Venv already exists: {venv_path}")
            return venv_path
        else:
            print(f"[WARN] Venv exists but is broken (missing {python_exe})")
            print("[INFO] Removing broken venv and recreating...")
            try:
                shutil.rmtree(venv_path)
            except Exception as e:
                print(f"[ERROR] Failed to remove broken venv: {e}")
                print(f"[TIP] Manually delete {venv_path} and retry")
                raise RuntimeError(f"Cannot remove broken venv: {e}") from e

    print(f"Creating venv at {venv_path}...", flush=True)

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
    print(f"{check_mark} Created venv: {venv_path}")

    return venv_path


def install_theauditor_editable(venv_path: Path, theauditor_root: Path | None = None) -> bool:
    """
    Install TheAuditor in editable mode into the venv.

    Args:
        venv_path: Path to the virtual environment
        theauditor_root: Path to TheAuditor source (auto-detected if None)

    Returns:
        True if installation succeeded
    """
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
        stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
            str(venv_path.parent), "pip_show"
        )

        with (
            open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
            open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
        ):
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "show", "theauditor"],
                stdout=stdout_fp,
                stderr=stderr_fp,
                text=True,
                timeout=30,
            )

        with open(stdout_path, encoding="utf-8") as f:
            result.stdout = f.read()
        with open(stderr_path, encoding="utf-8") as f:
            result.stderr = f.read()

        try:
            Path(stdout_path).unlink()
            Path(stderr_path).unlink()
        except (OSError, PermissionError):
            pass

        if result.returncode == 0:
            check_mark = "[OK]"
            print(f"{check_mark} TheAuditor already installed in {venv_path}")

            print("  Upgrading to ensure latest version...")
    except subprocess.TimeoutExpired:
        print("Warning: pip show timed out, proceeding with install")

    print(f"Installing TheAuditor from {theauditor_root}...", flush=True)

    cmd = [
        str(python_exe),
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "-e",
        f"{theauditor_root}[all]",
    ]

    try:
        stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
            str(venv_path.parent), "pip_install"
        )

        with (
            open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
            open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
        ):
            result = subprocess.run(
                cmd,
                stdout=stdout_fp,
                stderr=stderr_fp,
                text=True,
                timeout=120,
                cwd=str(venv_path.parent),
            )

        with open(stdout_path, encoding="utf-8") as f:
            result.stdout = f.read()
        with open(stderr_path, encoding="utf-8") as f:
            result.stderr = f.read()

        try:
            Path(stdout_path).unlink()
            Path(stderr_path).unlink()
        except (OSError, PermissionError):
            pass

        if result.returncode != 0:
            print("Error installing TheAuditor:")
            print(result.stderr)
            return False

        check_mark = "[OK]"
        print(f"{check_mark} Installed TheAuditor (editable) from {theauditor_root}")

        if aud_exe.exists():
            check_mark = "[OK]"
            print(f"{check_mark} Executable available: {aud_exe}")
        else:
            stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                str(venv_path.parent), "verify"
            )

            with (
                open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
                open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
            ):
                verify_result = subprocess.run(
                    [str(python_exe), "-m", "theauditor.cli", "--version"],
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=10,
                )

            with open(stdout_path, encoding="utf-8") as f:
                verify_result.stdout = f.read()
            with open(stderr_path, encoding="utf-8") as f:
                verify_result.stderr = f.read()

            try:
                Path(stdout_path).unlink()
                Path(stderr_path).unlink()
            except (OSError, PermissionError):
                pass

            if verify_result.returncode == 0:
                check_mark = "[OK]"
                print(f"{check_mark} Module available: python -m theauditor.cli")
            else:
                print("Warning: Could not verify TheAuditor installation")

        return True

    except subprocess.TimeoutExpired:
        print("Error: Installation timed out after 120 seconds")
        return False
    except Exception as e:
        print(f"Error during installation: {e}")
        return False


def _self_update_package_json(package_json_path: Path) -> int:
    """
    Self-update package.json with latest versions from npm registry.

    Uses the modern async batch engine from deps.py for efficient parallel fetching.

    This function is called BEFORE npm install to ensure we always
    get the latest versions of our tools, solving the paradox of
    needing to update dependencies that are in excluded directories.

    Args:
        package_json_path: Path to the package.json file to update

    Returns:
        Number of packages updated
    """
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
            print("    No dependencies to check")
            return 0

        print(f"    Checking {len(deps_to_check)} npm packages...")
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
                print(f"      {check_mark} {name}: {current} {arrow} ^{latest}")

        if updated_count > 0:
            with open(package_json_path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            print(f"    Updated {updated_count} packages to latest versions")
        else:
            print("    All packages already at latest versions")

        return updated_count

    except Exception as e:
        print(f"    [WARN] Could not self-update package.json: {e}")
        return 0


def download_portable_node(sandbox_dir: Path) -> Path:
    """
    Download and extract portable Node.js runtime with integrity verification.

    Args:
        sandbox_dir: Directory to install Node.js into (.auditor_venv/.theauditor_tools)

    Returns:
        Path to node executable

    Raises:
        RuntimeError: If download fails or checksum doesn't match
    """
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
        print(f"    {check_mark} Node.js runtime already installed at {node_runtime_dir}")
        return node_exe

    expected_checksum = NODE_CHECKSUMS.get(archive_name)

    if not expected_checksum:
        raise RuntimeError(
            f"No checksum available for {archive_name}. Update NODE_CHECKSUMS in venv_install.py"
        )

    node_url = f"{NODE_BASE_URL}/{NODE_VERSION}/{archive_name}"
    print(f"    Downloading Node.js {NODE_VERSION} for {system} {machine}...", flush=True)
    print(f"    URL: {node_url}")

    try:
        download_path = sandbox_dir / "node_download"

        def download_hook(block_num, block_size, total_size):
            """Progress indicator for download."""
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, (downloaded / total_size) * 100)
                bar_length = 40
                filled = int(bar_length * percent / 100)
                bar = "=" * filled + "-" * (bar_length - filled)
                print(f"\r    Progress: [{bar}] {percent:.1f}%", end="", flush=True)

        urllib.request.urlretrieve(node_url, str(download_path), reporthook=download_hook)
        print()

        print("    Verifying SHA-256 checksum...")
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
        print(f"    {check_mark} Checksum verified: {actual_checksum[:16]}...")

        print("    Extracting Node.js runtime...", flush=True)
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
        print(f"    {check_mark} Node.js runtime installed at {node_runtime_dir}")
        return node_exe

    except urllib.error.URLError as e:
        print(f"    ❌ Network error downloading Node.js: {e}")
        raise RuntimeError(f"Failed to download Node.js: {e}") from e
    except Exception as e:
        print(f"    ❌ Failed to install Node.js: {e}")

        if "download_path" in locals() and download_path.exists():
            download_path.unlink()
        raise RuntimeError(f"Failed to install Node.js: {e}") from e


def setup_osv_scanner(sandbox_dir: Path) -> Path | None:
    """
    Download and install OSV-Scanner binary for vulnerability detection.

    OSV-Scanner is Google's official tool for scanning dependencies against
    the OSV (Open Source Vulnerabilities) database. It provides offline
    scanning capabilities once the database is downloaded.

    FACTS (from installation.md - DO NOT HALLUCINATE):
    - Binary source: https://github.com/google/osv-scanner/releases
    - File naming: osv-scanner_{version}_{platform}_{arch}
    - Single executable, no dependencies required
    - SLSA3 compliant with provenance verification
    - Offline database: {local_db_dir}/osv-scanner/{ecosystem}/all.zip

    Args:
        sandbox_dir: Directory to install OSV-Scanner (.auditor_venv/.theauditor_tools)

    Returns:
        Path to osv-scanner executable, or None if installation failed
    """
    import urllib.error
    import urllib.request

    print("  Setting up OSV-Scanner (Google's vulnerability scanner)...", flush=True)

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
        print(f"    {check_mark} OSV-Scanner already installed at {osv_dir}")
    else:
        url = f"https://github.com/google/osv-scanner/releases/latest/download/{download_filename}"
        print("    Downloading OSV-Scanner from GitHub releases...", flush=True)
        print(f"    URL: {url}")

        try:
            urllib.request.urlretrieve(url, str(binary_path))

            if system != "Windows":
                import stat

                st = binary_path.stat()
                binary_path.chmod(st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            print(f"    {check_mark} OSV-Scanner binary downloaded successfully")
        except urllib.error.URLError as e:
            print(f"    [WARN] Network error downloading OSV-Scanner: {e}")
            print(
                "    [WARN] You can manually download from: https://github.com/google/osv-scanner/releases"
            )
            return None
        except Exception as e:
            print(f"    [WARN] Failed to install OSV-Scanner: {e}")
            if binary_path.exists():
                binary_path.unlink()
            return None

    print(f"    {check_mark} Database cache directory: {db_dir}")

    try:
        print("")
        print("    Downloading offline vulnerability databases...", flush=True)
        print("    This may take 5-10 minutes and use 100-500MB disk space", flush=True)
        print("    Downloading databases for: npm, PyPI", flush=True)

        try:
            env = {**os.environ, "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": str(db_dir)}

            lockfiles = {}
            target_dir = sandbox_dir.parent.parent

            for name in ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]:
                lock = target_dir / name
                if lock.exists():
                    lockfiles["npm"] = lock
                    break

                for subdir in ["backend", "frontend", "server", "client", "web"]:
                    lock = target_dir / subdir / name
                    if lock.exists():
                        lockfiles["npm"] = lock
                        break
                if "npm" in lockfiles:
                    break

            if "npm" not in lockfiles:
                pkg_json = target_dir / "package.json"
                if pkg_json.exists():
                    print(
                        "    ℹ package.json found but no package-lock.json (npm install not run) - skipping npm database"
                    )

            for name in ["requirements.txt", "Pipfile.lock", "poetry.lock"]:
                req = target_dir / name
                if req.exists():
                    lockfiles["PyPI"] = req
                    break

                for subdir in ["backend", "server", "api"]:
                    req = target_dir / subdir / name
                    if req.exists():
                        lockfiles["PyPI"] = req
                        break
                if "PyPI" in lockfiles:
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
                        print("    ℹ Generated temporary requirements from pyproject.toml")

            cmd = [str(binary_path), "scan"]

            for _ecosystem, lockfile in lockfiles.items():
                cmd.extend(["-L", str(lockfile)])

            if not lockfiles:
                print("    ℹ No lockfiles found - skipping vulnerability database download")
                return binary_path
            else:
                ecosystems = ", ".join(lockfiles.keys())
                print(f"    Found lockfiles for: {ecosystems}")

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
                cmd, env=env, capture_output=True, text=True, timeout=600, cwd=str(target_dir)
            )

            if result.returncode > 1:
                print(f"    ⚠ OSV-Scanner failed with exit code {result.returncode}")
                if result.stderr:
                    print("    Error output (first 15 lines):")
                    for line in result.stderr.split("\n")[:15]:
                        if line.strip():
                            print(f"      {line}")
            elif result.returncode == 1:
                if result.stderr:
                    for line in result.stderr.split("\n")[:3]:
                        if "scanned" in line.lower() or "found" in line.lower():
                            print(f"    {line.strip()}")
            else:
                if result.stdout and "packages" in result.stdout.lower():
                    for line in result.stdout.split("\n")[:5]:
                        if "scanned" in line.lower() or "packages" in line.lower():
                            print(f"    {line.strip()}")

            npm_db = db_dir / "osv-scanner" / "npm" / "all.zip"
            pypi_db = db_dir / "osv-scanner" / "PyPI" / "all.zip"

            if npm_db.exists():
                npm_size = npm_db.stat().st_size / (1024 * 1024)
                print(f"    {check_mark} npm vulnerability database downloaded ({npm_size:.1f} MB)")
            else:
                if "npm" in lockfiles:
                    print("    ⚠ npm database download failed - online mode will use API")
                else:
                    print("    ℹ No npm lockfile found - npm database not needed")

            if pypi_db.exists():
                pypi_size = pypi_db.stat().st_size / (1024 * 1024)
                print(
                    f"    {check_mark} PyPI vulnerability database downloaded ({pypi_size:.1f} MB)"
                )
            else:
                if "PyPI" in lockfiles:
                    print("    ⚠ PyPI database download failed - online mode will use API")
                else:
                    print("    ℹ No Python lockfile found - PyPI database not needed")

            if npm_db.exists() or pypi_db.exists():
                print(f"    {check_mark} Offline vulnerability scanning ready")
            else:
                print("    ⚠ Database download failed - scanner will use online API mode")
                print("    ⚠ To retry manually, run:")
                print(f"      export OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY={db_dir}")
                print(
                    f"      {binary_path} scan -r . --offline-vulnerabilities --download-offline-databases"
                )

        except subprocess.TimeoutExpired:
            print("    ⚠ Database download timed out after 10 minutes")
            print("    ⚠ Scanner will use online API mode")
            print(f"    ⚠ To retry: delete {db_dir} and run setup again")
        except Exception as e:
            print(f"    ⚠ Database download failed: {e}")
            print("    ⚠ Scanner will use online API mode")
            print("    ⚠ To retry manually:")
            print(f"      export OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY={db_dir}")
            print(
                f"      {binary_path} scan -r . --offline-vulnerabilities --download-offline-databases"
            )
        finally:
            for tmp in temp_files:
                with contextlib.suppress(OSError):
                    if tmp.exists():
                        tmp.unlink()

        return binary_path

    except urllib.error.URLError as e:
        print(f"    ⚠ Network error downloading OSV-Scanner: {e}")
        print(
            "    ⚠ You can manually download from: https://github.com/google/osv-scanner/releases"
        )
        return None
    except Exception as e:
        print(f"    ⚠ Failed to install OSV-Scanner: {e}")

        if binary_path.exists():
            binary_path.unlink()
        return None


def setup_project_venv(target_dir: Path, force: bool = False) -> tuple[Path, bool]:
    """
    Complete venv setup: create and install TheAuditor + ALL linting tools.

    Args:
        target_dir: Project root directory
        force: If True, recreate venv even if exists

    Returns:
        (venv_path, success) tuple
    """
    target_dir = Path(target_dir).resolve()

    if not target_dir.exists():
        raise ValueError(f"Target directory does not exist: {target_dir}")

    try:
        venv_path = create_venv(target_dir, force)
    except RuntimeError as e:
        print(f"[ERROR] Failed to create venv: {e}")
        return target_dir / ".auditor_venv", False

    success = install_theauditor_editable(venv_path)

    if success:
        print("\nInstalling Python linting tools...", flush=True)
        python_exe, aud_exe = get_venv_paths(venv_path)
        theauditor_root = find_theauditor_root()

        print("  Checking for latest linter versions...", flush=True)
        try:
            if aud_exe.exists():
                stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                    str(target_dir), "deps_upgrade"
                )

                with (
                    open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
                    open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
                ):
                    result = subprocess.run(
                        [str(aud_exe), "deps", "--upgrade-all", "--root", str(theauditor_root)],
                        stdout=stdout_fp,
                        stderr=stderr_fp,
                        text=True,
                        timeout=300,
                    )

                with open(stdout_path, encoding="utf-8") as f:
                    result.stdout = f.read()
                with open(stderr_path, encoding="utf-8") as f:
                    result.stderr = f.read()

                try:
                    Path(stdout_path).unlink()
                    Path(stderr_path).unlink()
                except (OSError, PermissionError):
                    pass

                if result.returncode == 0:
                    check_mark = "[OK]"
                    print(f"    {check_mark} Updated to latest package versions")
        except Exception as e:
            print(f"    ⚠ Could not update versions: {e}")

        try:
            print("  Installing linters and AST tools from pyproject.toml...", flush=True)

            pyproject_path = theauditor_root / "pyproject.toml"
            linter_packages = _get_runtime_packages(
                pyproject_path,
                ["ruff", "mypy", "black", "bandit", "pylint", "sqlparse", "dockerfile-parse"],
            )

            stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                str(target_dir), "pip_linters"
            )

            with (
                open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
                open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
            ):
                result = subprocess.run(
                    [str(python_exe), "-m", "pip", "install"] + linter_packages,
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=300,
                )

            with open(stdout_path, encoding="utf-8") as f:
                result.stdout = f.read()
            with open(stderr_path, encoding="utf-8") as f:
                result.stderr = f.read()

            try:
                Path(stdout_path).unlink()
                Path(stderr_path).unlink()
            except (OSError, PermissionError):
                pass

            if result.returncode == 0:
                check_mark = "[OK]"
                print(f"    {check_mark} Python linters installed")

                print("  Installing tree-sitter AST tools...", flush=True)

                ast_packages = _get_runtime_packages(
                    pyproject_path, ["tree-sitter", "tree-sitter-language-pack"]
                )

                stdout_path2, stderr_path2 = TempManager.create_temp_files_for_subprocess(
                    str(target_dir), "pip_ast"
                )

                with (
                    open(stdout_path2, "w+", encoding="utf-8") as stdout_fp,
                    open(stderr_path2, "w+", encoding="utf-8") as stderr_fp,
                ):
                    result2 = subprocess.run(
                        [str(python_exe), "-m", "pip", "install"] + ast_packages,
                        stdout=stdout_fp,
                        stderr=stderr_fp,
                        text=True,
                        timeout=300,
                    )

                with open(stdout_path2, encoding="utf-8") as f:
                    result2.stdout = f.read()
                with open(stderr_path2, encoding="utf-8") as f:
                    result2.stderr = f.read()

                try:
                    Path(stdout_path2).unlink()
                    Path(stderr_path2).unlink()
                except (OSError, PermissionError):
                    pass

                if result2.returncode == 0:
                    print(f"    {check_mark} AST tools installed")
                    print(f"    {check_mark} All Python tools ready:")
                    print("        - Linters: ruff, mypy, black, bandit, pylint")
                    print("        - Parsers: sqlparse, dockerfile-parse")
                    print("        - AST analysis: tree-sitter (Python/JS/TS)")
                else:
                    print(f"    ⚠ Tree-sitter installation failed: {result2.stderr[:200]}")
            else:
                print(f"    ⚠ Some linters failed to install: {result.stderr[:200]}")
        except Exception as e:
            print(f"    ⚠ Error installing tools: {e}")

        print("\nSetting up JavaScript/TypeScript tools in sandboxed environment...", flush=True)

        sandbox_dir = venv_path / ".theauditor_tools"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        sandbox_package_json = sandbox_dir / "package.json"

        print(f"  Creating sandboxed tools directory: {sandbox_dir}", flush=True)

        package_source = theauditor_root / "theauditor" / "linters" / "package.json"

        if package_source.exists():
            with open(package_source) as f:
                package_data = json.load(f)
        else:
            print(f"    ⚠ Package.json not found at {package_source}, using minimal config")
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

        eslint_config_source = theauditor_root / "theauditor" / "linters" / "eslint.config.cjs"
        eslint_config_dest = sandbox_dir / "eslint.config.cjs"

        if eslint_config_source.exists():
            import shutil

            shutil.copy2(str(eslint_config_source), str(eslint_config_dest))
            check_mark = "[OK]"
            print(f"    {check_mark} ESLint v9 flat config copied to sandbox")
        else:
            print(f"    ⚠ ESLint config not found at {eslint_config_source}")

        python_config_source = theauditor_root / "theauditor" / "linters" / "pyproject.toml"
        python_config_dest = sandbox_dir / "pyproject.toml"

        if python_config_source.exists():
            shutil.copy2(str(python_config_source), str(python_config_dest))
            check_mark = "[OK]"
            print(f"    {check_mark} Python linter config (pyproject.toml) copied to sandbox")
        else:
            print(f"    ⚠ Python config not found at {python_config_source}")

        agents_source = theauditor_root / "agents"
        agents_dest = sandbox_dir / "agents"

        if agents_source.exists() and agents_source.is_dir():
            agents_dest.mkdir(exist_ok=True)

            agent_files = list(agents_source.glob("*.md"))
            if agent_files:
                for agent_file in agent_files:
                    dest_file = agents_dest / agent_file.name
                    shutil.copy2(str(agent_file), str(dest_file))

                check_mark = "[OK]"
                print(
                    f"    {check_mark} Planning agents copied to sandbox ({len(agent_files)} agents)"
                )
                print(f"        → {agents_dest}")

                _inject_agents_md(target_dir)
            else:
                print(f"    ⚠ No agent files found in {agents_source}")
        else:
            print(f"    ⚠ Agents directory not found at {agents_source}")

        commands_source = theauditor_root / "agents" / "commands"
        commands_dest = target_dir / ".claude" / "commands" / "theauditor"

        if commands_source.exists() and commands_source.is_dir():
            commands_dest.mkdir(parents=True, exist_ok=True)

            command_files = list(commands_source.glob("*.md"))
            if command_files:
                for command_file in command_files:
                    dest_file = commands_dest / command_file.name
                    shutil.copy2(str(command_file), str(dest_file))

                check_mark = "[OK]" if IS_WINDOWS else "✓"
                print(
                    f"    {check_mark} Slash commands copied to project ({len(command_files)} commands)"
                )
                print(f"        → {commands_dest}")
                print(
                    "        Available: /theauditor:planning, /theauditor:security, /theauditor:refactor, /theauditor:dataflow"
                )
            else:
                print(f"    ⚠ No command files found in {commands_source}")
        else:
            print(f"    ⚠ Commands directory not found at {commands_source}")

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
            print("  [Track A] Checking for latest tool versions...", flush=True)
            _self_update_package_json(sandbox_package_json)

        def track_b_node_download():
            """Track B: ONLY download Node.js, nothing else."""
            nonlocal node_exe, node_error
            try:
                print("  [Track B] Setting up portable Node.js runtime...", flush=True)
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

            print("  Installing JS/TS linters using bundled Node.js...", flush=True)
            stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                str(target_dir), "npm_install"
            )

            with (
                open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
                open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
            ):
                full_cmd = npm_cmd + ["install"]

                result = subprocess.run(
                    full_cmd,
                    cwd=str(sandbox_dir),
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=120,
                    shell=False,
                )

            with open(stdout_path, encoding="utf-8") as f:
                result.stdout = f.read()
            with open(stderr_path, encoding="utf-8") as f:
                result.stderr = f.read()

            try:
                Path(stdout_path).unlink()
                Path(stderr_path).unlink()
            except (OSError, PermissionError):
                pass

            if result.returncode == 0:
                check_mark = "[OK]"
                print(f"    {check_mark} JavaScript/TypeScript tools installed in sandbox")
                print(f"    {check_mark} Tools isolated from project: {sandbox_dir}")
                print(f"    {check_mark} Using bundled Node.js - no system dependency!")

                eslint_path = (
                    sandbox_dir
                    / "node_modules"
                    / ".bin"
                    / ("eslint.cmd" if os.name == "nt" else "eslint")
                )
                if eslint_path.exists():
                    print(f"    {check_mark} ESLint verified at: {eslint_path}")
            else:
                print(f"    ⚠ npm install failed: {result.stderr[:500]}")
                print("    ⚠ This may be a network issue. Try running setup again.")

        except RuntimeError as e:
            print(f"    ⚠ Could not set up bundled Node.js: {e}")
            print("    ⚠ JavaScript/TypeScript linting will not be available")
            print("    ⚠ To retry: Delete .auditor_venv and run setup again")
        except Exception as e:
            print(f"    ⚠ Unexpected error setting up JS tools: {e}")

        print("\nSetting up vulnerability scanning tools...", flush=True)

        osv_scanner_path = setup_osv_scanner(sandbox_dir)
        if osv_scanner_path:
            check_mark = "[OK]"
            print(f"{check_mark} OSV-Scanner ready for vulnerability detection")
        else:
            print("⚠ OSV-Scanner setup failed - vulnerability detection may be limited")

    return venv_path, success
