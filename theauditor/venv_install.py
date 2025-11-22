"""Pure Python venv creation and TheAuditor installation."""


import json
import os
import platform
import shutil
import subprocess
import sys
import venv
import contextlib
from pathlib import Path
from typing import Optional, Tuple, List

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore

# Import dependency checking functions for self-updating sandbox
from theauditor.deps import _check_npm_latest
# Import our custom temp manager to avoid WSL2/Windows issues
from theauditor.utils.temp_manager import TempManager

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"

# Node.js runtime configuration - UPDATE WHEN UPGRADING NODE.JS VERSION
NODE_VERSION = "v20.11.1"  # LTS version, update quarterly with checksums
NODE_BASE_URL = "https://nodejs.org/dist"

# Hardcoded SHA-256 checksums for Node.js v20.11.1
# Source: https://nodejs.org/download/release/v20.11.1/SHASUMS256.txt
# These are immutable - the checksum for a specific version never changes
NODE_CHECKSUMS = {
    "node-v20.11.1-win-x64.zip": "bc032628d77d206ffa7f133518a6225a9c5d6d9210ead30d67e294ff37044bda",
    "node-v20.11.1-linux-x64.tar.xz": "d8dab549b09672b03356aa2257699f3de3b58c96e74eb26a8b495fbdc9cf6fbe",
    "node-v20.11.1-linux-arm64.tar.xz": "c957f29eb4e341903520caf362534f0acd1db7be79c502ae8e283994eed07fe1",
    "node-v20.11.1-darwin-x64.tar.gz": "c52e7fb0709dbe63a4cbe08ac8af3479188692937a7bd8e776e0eedfa33bb848",
    "node-v20.11.1-darwin-arm64.tar.gz": "e0065c61f340e85106a99c4b54746c5cee09d59b08c5712f67f99e92aa44995d"
}


def _extract_pyproject_dependencies(pyproject_path: Path) -> list[str]:
    """Extract dependency strings from pyproject.toml for offline vulnerability DB seeding."""
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    dependencies: list[str] = []

    # PEP 621 project dependencies
    project = data.get("project")
    if isinstance(project, dict):
        proj_deps = project.get("dependencies")
        if isinstance(proj_deps, list):
            dependencies.extend(str(dep).strip() for dep in proj_deps if str(dep).strip())

    # Poetry dependencies
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

    # Remove duplicates while preserving order
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

        # Combine runtime and dev dependencies
        all_deps = []
        all_deps.extend(optional_deps.get("runtime", []))
        all_deps.extend(optional_deps.get("dev", []))

        # Build a map of package name -> version spec
        package_map = {}
        for dep in all_deps:
            dep_str = str(dep).strip()
            # Handle both "package==1.2.3" and "package>=1.2.3" formats
            for sep in ["==", ">=", "<=", "~=", ">", "<"]:
                if sep in dep_str:
                    pkg_name = dep_str.split(sep)[0].strip().lower()
                    package_map[pkg_name] = dep_str
                    break
            else:
                # No version specifier, just package name
                package_map[dep_str.lower()] = dep_str

        # Extract requested packages
        result = []
        for pkg_name in package_names:
            pkg_lower = pkg_name.lower()
            if pkg_lower in package_map:
                result.append(package_map[pkg_lower])
            else:
                # Fallback: return package name without version
                result.append(pkg_name)

        return result
    except Exception:
        # Fallback: return package names without versions
        return list(package_names)


def find_theauditor_root() -> Path:
    """Find TheAuditor project root by walking up from __file__ to pyproject.toml."""
    current = Path(__file__).resolve().parent

    # Walk up the directory tree
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            # Verify it's actually TheAuditor
            content = (current / "pyproject.toml").read_text()
            if "theauditor" in content.lower():
                return current
        current = current.parent

    raise RuntimeError("Could not find TheAuditor project root (pyproject.toml)")


def _inject_agents_md(target_dir: Path) -> None:
    """
    Inject TheAuditor agent trigger block into AGENTS.md in target project root.

    Creates AGENTS.md if it doesn't exist, or injects trigger block if not already present.
    This tells AI assistants where to find specialized agent workflows.
    """
    TRIGGER_START = "<!-- THEAUDITOR:START -->"
    TRIGGER_END = "<!-- THEAUDITOR:END -->"

    TRIGGER_BLOCK = f"""{TRIGGER_START}
# TheAuditor Planning Agent System

When user mentions planning, refactoring, security, or dataflow keywords, load specialized agents:

**Agent Triggers:**
- "refactor", "split", "extract", "merge", "modularize" => @/.auditor_venv/.theauditor_tools/agents/refactor.md
- "security", "vulnerability", "XSS", "SQL injection", "CSRF", "taint", "sanitize" => @/.auditor_venv/.theauditor_tools/agents/security.md
- "plan", "architecture", "design", "organize", "structure", "approach" => @/.auditor_venv/.theauditor_tools/agents/planning.md
- "dataflow", "trace", "track", "flow", "source", "sink", "propagate" => @/.auditor_venv/.theauditor_tools/agents/dataflow.md

**Agent Purpose:**
These agents enforce query-driven workflows using TheAuditor's database:
- NO file reading - use `aud query`, `aud blueprint`, `aud context`
- NO guessing patterns - follow detected precedents from blueprint
- NO assuming conventions - match detected naming/frameworks
- MANDATORY sequence: blueprint => query => synthesis
- ALL recommendations cite database query results

**Agent Files Location:**
Agents are located at .auditor_venv/.theauditor_tools/agents/
Copied during `aud setup-ai` from TheAuditor source.

{TRIGGER_END}
"""

    agents_md = target_dir / "AGENTS.md"
    check_mark = "[OK]" if IS_WINDOWS else "✓"

    if not agents_md.exists():
        # Create new AGENTS.md with trigger block
        agents_md.write_text(TRIGGER_BLOCK + "\n", encoding="utf-8")
        print(f"    {check_mark} Created AGENTS.md with agent triggers")
    else:
        # Check if trigger already exists
        content = agents_md.read_text(encoding="utf-8")
        if TRIGGER_START in content:
            print(f"    {check_mark} AGENTS.md already has agent triggers")
        else:
            # Inject at beginning of file
            new_content = TRIGGER_BLOCK + "\n" + content
            agents_md.write_text(new_content, encoding="utf-8")
            print(f"    {check_mark} Injected agent triggers into AGENTS.md")


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
    
    # Check if venv exists AND is functional (has python executable)
    if venv_path.exists() and not force:
        python_exe, _ = get_venv_paths(venv_path)
        if python_exe.exists():
            check_mark = "[OK]"
            print(f"{check_mark} Venv already exists: {venv_path}")
            return venv_path
        else:
            # Venv is broken (exists but no python.exe) - recreate it
            print(f"[WARN] Venv exists but is broken (missing {python_exe})")
            print(f"[INFO] Removing broken venv and recreating...")
            try:
                shutil.rmtree(venv_path)
            except Exception as e:
                print(f"[ERROR] Failed to remove broken venv: {e}")
                print(f"[TIP] Manually delete {venv_path} and retry")
                raise RuntimeError(f"Cannot remove broken venv: {e}")
    
    print(f"Creating venv at {venv_path}...", flush=True)
    
    # Create venv using stdlib
    builder = venv.EnvBuilder(
        system_site_packages=False,
        clear=force,
        symlinks=(platform.system() != "Windows"),
        upgrade=False,
        with_pip=True,
        prompt=f"[{target_dir.name}]"
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
            f"  aud setup-claude --target . --sync"
        )
    
    # Check if already installed
    try:
        stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
            str(venv_path.parent), "pip_show"
        )
        
        with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
             open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
            
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "show", "theauditor"],
                stdout=stdout_fp,
                stderr=stderr_fp,
                text=True,
                timeout=30
            )
        
        with open(stdout_path, encoding='utf-8') as f:
            result.stdout = f.read()
        with open(stderr_path, encoding='utf-8') as f:
            result.stderr = f.read()
        
        # Clean up temp files
        try:
            Path(stdout_path).unlink()
            Path(stderr_path).unlink()
        except (OSError, PermissionError):
            pass
        
        if result.returncode == 0:
            check_mark = "[OK]"
            print(f"{check_mark} TheAuditor already installed in {venv_path}")
            # Upgrade to ensure latest
            print("  Upgrading to ensure latest version...")
    except subprocess.TimeoutExpired:
        print("Warning: pip show timed out, proceeding with install")
    
    # Install in editable mode
    print(f"Installing TheAuditor from {theauditor_root}...", flush=True)
    
    cmd = [
        str(python_exe),
        "-m", "pip",
        "install",
        "--no-cache-dir",
        # Install with [all] extra to get BOTH runtime AND dev dependencies
        # This ensures the sandbox has everything needed for analysis + development
        f"-e", f"{theauditor_root}[all]"
    ]
    
    try:
        stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
            str(venv_path.parent), "pip_install"
        )
        
        with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
             open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
            
            result = subprocess.run(
                cmd,
                stdout=stdout_fp,
                stderr=stderr_fp,
                text=True,
                timeout=120,
                cwd=str(venv_path.parent)
            )
        
        with open(stdout_path, encoding='utf-8') as f:
            result.stdout = f.read()
        with open(stderr_path, encoding='utf-8') as f:
            result.stderr = f.read()
        
        # Clean up temp files
        try:
            Path(stdout_path).unlink()
            Path(stderr_path).unlink()
        except (OSError, PermissionError):
            pass
        
        if result.returncode != 0:
            print(f"Error installing TheAuditor:")
            print(result.stderr)
            return False
        
        check_mark = "[OK]"
        print(f"{check_mark} Installed TheAuditor (editable) from {theauditor_root}")
        
        # Verify installation
        if aud_exe.exists():
            check_mark = "[OK]"
            print(f"{check_mark} Executable available: {aud_exe}")
        else:
            # Fallback check for module
            stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                str(venv_path.parent), "verify"
            )
            
            with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
                 open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
                
                verify_result = subprocess.run(
                    [str(python_exe), "-m", "theauditor.cli", "--version"],
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=10
                )
            
            with open(stdout_path, encoding='utf-8') as f:
                verify_result.stdout = f.read()
            with open(stderr_path, encoding='utf-8') as f:
                verify_result.stderr = f.read()
            
            # Clean up temp files
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
    
    This function is called BEFORE npm install to ensure we always
    get the latest versions of our tools, solving the paradox of
    needing to update dependencies that are in excluded directories.
    
    Args:
        package_json_path: Path to the package.json file to update
        
    Returns:
        Number of packages updated
    """
    try:
        # Read current package.json
        with open(package_json_path) as f:
            data = json.load(f)
        
        updated_count = 0
        
        # Update dependencies if present
        if "dependencies" in data:
            for name in list(data["dependencies"].keys()):
                try:
                    latest = _check_npm_latest(name)
                    if latest:
                        current = data["dependencies"][name]
                        # Clean current version for comparison
                        current_clean = current.lstrip('^~>=')
                        if current_clean != latest:
                            data["dependencies"][name] = f"^{latest}"
                            updated_count += 1
                            check_mark = "[OK]"
                            print(f"      {check_mark} Updated {name}: {current} → ^{latest}")
                except Exception as e:
                    # If we can't get latest, keep current version
                    print(f"      ⚠ Could not check {name}: {e}")
                    continue
        
        # Update devDependencies if present
        if "devDependencies" in data:
            for name in list(data["devDependencies"].keys()):
                try:
                    latest = _check_npm_latest(name)
                    if latest:
                        current = data["devDependencies"][name]
                        # Clean current version for comparison
                        current_clean = current.lstrip('^~>=')
                        if current_clean != latest:
                            data["devDependencies"][name] = f"^{latest}"
                            updated_count += 1
                            check_mark = "[OK]"
                            print(f"      {check_mark} Updated {name}: {current} → ^{latest}")
                except Exception as e:
                    # If we can't get latest, keep current version
                    print(f"      ⚠ Could not check {name}: {e}")
                    continue
        
        # Write updated package.json
        if updated_count > 0:
            with open(package_json_path, 'w') as f:
                json.dump(data, f, indent=2)
                f.write("\n")  # Add trailing newline
            print(f"    Updated {updated_count} packages to latest versions")
        else:
            print(f"    All packages already at latest versions")
        
        return updated_count
        
    except Exception as e:
        print(f"    ⚠ Could not self-update package.json: {e}")
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
    import urllib.request
    import urllib.error
    import hashlib
    import zipfile
    import tarfile
    
    node_runtime_dir = sandbox_dir / "node-runtime"
    
    # Determine platform and architecture
    system = platform.system()
    machine = platform.machine().lower()
    
    # Build archive name based on platform
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
    
    # Check if already installed
    if node_exe.exists():
        check_mark = "[OK]"
        print(f"    {check_mark} Node.js runtime already installed at {node_runtime_dir}")
        return node_exe
    
    # Use hardcoded checksums (immutable for a specific version)
    expected_checksum = NODE_CHECKSUMS.get(archive_name)
    
    if not expected_checksum:
        raise RuntimeError(
            f"No checksum available for {archive_name}. "
            f"Update NODE_CHECKSUMS in venv_install.py"
        )
    
    # Build download URL
    node_url = f"{NODE_BASE_URL}/{NODE_VERSION}/{archive_name}"
    print(f"    Downloading Node.js {NODE_VERSION} for {system} {machine}...", flush=True)
    print(f"    URL: {node_url}")
    
    try:
        download_path = sandbox_dir / "node_download"
        
        # Download with progress indicator
        def download_hook(block_num, block_size, total_size):
            """Progress indicator for download."""
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, (downloaded / total_size) * 100)
                bar_length = 40
                filled = int(bar_length * percent / 100)
                bar = '=' * filled + '-' * (bar_length - filled)
                print(f"\r    Progress: [{bar}] {percent:.1f}%", end='', flush=True)
        
        urllib.request.urlretrieve(node_url, str(download_path), reporthook=download_hook)
        print()  # New line after progress bar
        
        # Verify SHA-256 checksum for security
        print(f"    Verifying SHA-256 checksum...")
        sha256_hash = hashlib.sha256()
        with open(download_path, "rb") as f:
            # Read in 8KB chunks for memory efficiency
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        
        actual_checksum = sha256_hash.hexdigest()
        if actual_checksum != expected_checksum:
            download_path.unlink()  # Remove corrupted/tampered download
            raise RuntimeError(
                f"Checksum verification failed!\n"
                f"    Expected: {expected_checksum}\n"
                f"    Actual:   {actual_checksum}\n"
                f"    This may indicate a corrupted download or security issue."
            )
        
        check_mark = "[OK]"
        print(f"    {check_mark} Checksum verified: {actual_checksum[:16]}...")
        
        # Extract based on archive type
        print(f"    Extracting Node.js runtime...", flush=True)
        if archive_type == "zip":
            with zipfile.ZipFile(download_path) as zf:
                # Extract to temp directory first
                temp_extract = sandbox_dir / "temp_node"
                temp_extract.mkdir(exist_ok=True)
                zf.extractall(temp_extract)
                # Node.js zips contain node-vX.Y.Z-platform/ directory
                extracted = list(temp_extract.glob("node-*"))[0]
                # Move contents to final location
                shutil.move(str(extracted), str(node_runtime_dir))
                if temp_extract.exists():
                    temp_extract.rmdir()
        else:
            with tarfile.open(download_path, "r:*") as tf:
                # Extract to temp directory first
                temp_extract = sandbox_dir / "temp_node"
                temp_extract.mkdir(exist_ok=True)
                tf.extractall(temp_extract)
                # Find extracted folder (node-vX.Y.Z-platform/)
                extracted = list(temp_extract.glob("node-*"))[0]
                # Move to final location
                shutil.move(str(extracted), str(node_runtime_dir))
                if temp_extract.exists():
                    temp_extract.rmdir()
        
        # Clean up download file
        download_path.unlink()
        
        check_mark = "[OK]"
        print(f"    {check_mark} Node.js runtime installed at {node_runtime_dir}")
        return node_exe
        
    except urllib.error.URLError as e:
        print(f"    ❌ Network error downloading Node.js: {e}")
        raise RuntimeError(f"Failed to download Node.js: {e}")
    except Exception as e:
        print(f"    ❌ Failed to install Node.js: {e}")
        # Clean up partial downloads
        if 'download_path' in locals() and download_path.exists():
            download_path.unlink()
        raise RuntimeError(f"Failed to install Node.js: {e}")


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
    import urllib.request
    import urllib.error

    print("  Setting up OSV-Scanner (Google's vulnerability scanner)...", flush=True)

    osv_dir = sandbox_dir / "osv-scanner"
    osv_dir.mkdir(parents=True, exist_ok=True)

    # Determine platform-specific binary name
    # FACTS from atomic_vuln_impl.md - DO NOT CHANGE
    system = platform.system()
    if system == "Windows":
        binary_name = "osv-scanner.exe"
        download_filename = "osv-scanner_windows_amd64.exe"
    elif system == "Darwin":
        binary_name = "osv-scanner"
        download_filename = "osv-scanner_darwin_amd64"
    else:  # Linux
        binary_name = "osv-scanner"
        download_filename = "osv-scanner_linux_amd64"

    binary_path = osv_dir / binary_name
    db_dir = osv_dir / "db"
    db_dir.mkdir(exist_ok=True)

    # Architect approved: dont early return, databases may need downloading
    # Binary download is conditional, but database download always runs
    check_mark = "[OK]"
    temp_files: list[Path] = []

    if binary_path.exists():
        print(f"    {check_mark} OSV-Scanner already installed at {osv_dir}")
    else:
        # Download from GitHub releases (latest)
        # FACT: Release page at https://github.com/google/osv-scanner/releases
        url = f"https://github.com/google/osv-scanner/releases/latest/download/{download_filename}"
        print(f"    Downloading OSV-Scanner from GitHub releases...", flush=True)
        print(f"    URL: {url}")

        try:
            # Download binary
            urllib.request.urlretrieve(url, str(binary_path))

            # Make executable on Unix systems
            if system != "Windows":
                import stat
                st = binary_path.stat()
                binary_path.chmod(st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            print(f"    {check_mark} OSV-Scanner binary downloaded successfully")
        except urllib.error.URLError as e:
            print(f"    [WARN] Network error downloading OSV-Scanner: {e}")
            print(f"    [WARN] You can manually download from: https://github.com/google/osv-scanner/releases")
            return None
        except Exception as e:
            print(f"    [WARN] Failed to install OSV-Scanner: {e}")
            if binary_path.exists():
                binary_path.unlink()
            return None

    print(f"    {check_mark} Database cache directory: {db_dir}")

    # Always run database download section (even if binary already existed)
    try:

        # Download offline vulnerability databases (NOT optional - required for offline mode)
        print(f"")
        print(f"    Downloading offline vulnerability databases...", flush=True)
        print(f"    This may take 5-10 minutes and use 100-500MB disk space", flush=True)
        print(f"    Downloading databases for: npm, PyPI", flush=True)

        try:
            # Set environment variable for database location
            # IMPORTANT: Merge with system environment to preserve PATH, etc.
            env = {**os.environ, "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": str(db_dir)}

            # Find real lockfiles from target project (filesystem search, not database)
            # This runs BEFORE aud index, so database doesn't exist yet
            lockfiles = {}
            target_dir = sandbox_dir.parent.parent  # Go up from .auditor_venv/.theauditor_tools to project root

            # npm lockfiles - check in order of preference
            for name in ['package-lock.json', 'yarn.lock', 'pnpm-lock.yaml']:
                # Check root directory first
                lock = target_dir / name
                if lock.exists():
                    lockfiles['npm'] = lock
                    break
                # Check common monorepo locations
                for subdir in ['backend', 'frontend', 'server', 'client', 'web']:
                    lock = target_dir / subdir / name
                    if lock.exists():
                        lockfiles['npm'] = lock
                        break
                if 'npm' in lockfiles:
                    break

            # If package.json exists but no lockfile, user hasn't run npm install
            # OSV-Scanner requires lockfiles - skip npm database download
            if 'npm' not in lockfiles:
                pkg_json = target_dir / 'package.json'
                if pkg_json.exists():
                    print("    ℹ package.json found but no package-lock.json (npm install not run) - skipping npm database")

            # Python requirements - check in order of preference
            for name in ['requirements.txt', 'Pipfile.lock', 'poetry.lock']:
                # Check root directory first
                req = target_dir / name
                if req.exists():
                    lockfiles['PyPI'] = req
                    break
                # Check common locations
                for subdir in ['backend', 'server', 'api']:
                    req = target_dir / subdir / name
                    if req.exists():
                        lockfiles['PyPI'] = req
                        break
                if 'PyPI' in lockfiles:
                    break

            # Support pyproject.toml by synthesizing a temporary requirements file
            if 'PyPI' not in lockfiles:
                pyproject = target_dir / "pyproject.toml"
                if pyproject.exists():
                    deps = _extract_pyproject_dependencies(pyproject)
                    if deps:
                        temp_req = sandbox_dir / "pyproject_requirements.txt"
                        temp_req.write_text("\n".join(deps), encoding="utf-8")
                        lockfiles['PyPI'] = temp_req
                        temp_files.append(temp_req)
                        print("    ℹ Generated temporary requirements from pyproject.toml")

            # Build OSV-Scanner command with real lockfiles
            cmd = [str(binary_path), "scan"]

            # Add found lockfiles
            for ecosystem, lockfile in lockfiles.items():
                cmd.extend(["-L", str(lockfile)])

            # If NO lockfiles at all, skip scan
            if not lockfiles:
                print("    ℹ No lockfiles found - skipping vulnerability database download")
                return binary_path
            else:
                ecosystems = ', '.join(lockfiles.keys())
                print(f"    Found lockfiles for: {ecosystems}")

            # Add offline database flags
            cmd.extend([
                "--offline-vulnerabilities",
                "--download-offline-databases",
                "--format", "json",
                "--allow-no-lockfiles"
            ])

            # Download databases using OSV-Scanner
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes max for database download
                cwd=str(target_dir)
            )

            # Show OSV-Scanner output for debugging
            # Exit codes: 0 = no vulns, 1 = vulns found (normal), >1 = actual error
            if result.returncode > 1:
                # Actual error (network failure, invalid file, etc.)
                print(f"    ⚠ OSV-Scanner failed with exit code {result.returncode}")
                if result.stderr:
                    print("    Error output (first 15 lines):")
                    for line in result.stderr.split('\n')[:15]:
                        if line.strip():
                            print(f"      {line}")
            elif result.returncode == 1:
                # Exit code 1 = vulnerabilities found during scan (normal)
                if result.stderr:
                    # Show package scan info (proves download worked)
                    for line in result.stderr.split('\n')[:3]:
                        if "scanned" in line.lower() or "found" in line.lower():
                            print(f"    {line.strip()}")
            else:
                # Exit code 0 = success, no vulnerabilities
                if result.stdout and "packages" in result.stdout.lower():
                    for line in result.stdout.split('\n')[:5]:
                        if "scanned" in line.lower() or "packages" in line.lower():
                            print(f"    {line.strip()}")

            # Verify databases were downloaded
            # OSV-Scanner stores databases in: {db_dir}/osv-scanner/{ecosystem}/all.zip
            npm_db = db_dir / "osv-scanner" / "npm" / "all.zip"
            pypi_db = db_dir / "osv-scanner" / "PyPI" / "all.zip"

            if npm_db.exists():
                npm_size = npm_db.stat().st_size / (1024 * 1024)  # MB
                print(f"    {check_mark} npm vulnerability database downloaded ({npm_size:.1f} MB)")
            else:
                if 'npm' in lockfiles:
                    print(f"    ⚠ npm database download failed - online mode will use API")
                else:
                    print(f"    ℹ No npm lockfile found - npm database not needed")

            if pypi_db.exists():
                pypi_size = pypi_db.stat().st_size / (1024 * 1024)  # MB
                print(f"    {check_mark} PyPI vulnerability database downloaded ({pypi_size:.1f} MB)")
            else:
                # Check if Python lockfile was found
                if 'PyPI' in lockfiles:
                    print(f"    ⚠ PyPI database download failed - online mode will use API")
                else:
                    print(f"    ℹ No Python lockfile found - PyPI database not needed")

            if npm_db.exists() or pypi_db.exists():
                print(f"    {check_mark} Offline vulnerability scanning ready")
            else:
                print(f"    ⚠ Database download failed - scanner will use online API mode")
                print(f"    ⚠ To retry manually, run:")
                print(f"      export OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY={db_dir}")
                print(f"      {binary_path} scan -r . --offline-vulnerabilities --download-offline-databases")

        except subprocess.TimeoutExpired:
            print(f"    ⚠ Database download timed out after 10 minutes")
            print(f"    ⚠ Scanner will use online API mode")
            print(f"    ⚠ To retry: delete {db_dir} and run setup again")
        except Exception as e:
            print(f"    ⚠ Database download failed: {e}")
            print(f"    ⚠ Scanner will use online API mode")
            print(f"    ⚠ To retry manually:")
            print(f"      export OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY={db_dir}")
            print(f"      {binary_path} scan -r . --offline-vulnerabilities --download-offline-databases")
        finally:
            for tmp in temp_files:
                with contextlib.suppress(OSError):
                    if tmp.exists():
                        tmp.unlink()

        return binary_path

    except urllib.error.URLError as e:
        print(f"    ⚠ Network error downloading OSV-Scanner: {e}")
        print(f"    ⚠ You can manually download from: https://github.com/google/osv-scanner/releases")
        return None
    except Exception as e:
        print(f"    ⚠ Failed to install OSV-Scanner: {e}")
        # Clean up partial download
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
        # Create venv (will auto-fix broken venvs)
        venv_path = create_venv(target_dir, force)
    except RuntimeError as e:
        # If venv creation fails completely, return failure
        print(f"[ERROR] Failed to create venv: {e}")
        return target_dir / ".auditor_venv", False
    
    # Install TheAuditor
    success = install_theauditor_editable(venv_path)
    
    if success:
        # Install Python linting tools from pyproject.toml
        print("\nInstalling Python linting tools...", flush=True)
        python_exe, aud_exe = get_venv_paths(venv_path)
        theauditor_root = find_theauditor_root()
        
        # First, run aud deps --upgrade-all to get latest versions!
        print("  Checking for latest linter versions...", flush=True)
        try:
            # Update pyproject.toml with latest versions
            if aud_exe.exists():
                stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                    str(target_dir), "deps_upgrade"
                )
                
                with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
                     open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
                    
                    result = subprocess.run(
                        [str(aud_exe), "deps", "--upgrade-all", "--root", str(theauditor_root)],
                        stdout=stdout_fp,
                        stderr=stderr_fp,
                        text=True,
                        timeout=300  # Increased to 5 minutes for checking many dependencies
                    )
                
                with open(stdout_path, encoding='utf-8') as f:
                    result.stdout = f.read()
                with open(stderr_path, encoding='utf-8') as f:
                    result.stderr = f.read()
                
                # Clean up temp files
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
        
        # Install linters AND ast tools as separate packages (not extras)
        # This avoids version conflicts with already-installed TheAuditor
        try:
            print("  Installing linters and AST tools from pyproject.toml...", flush=True)

            # Read package versions from pyproject.toml (single source of truth)
            pyproject_path = theauditor_root / "pyproject.toml"
            linter_packages = _get_runtime_packages(
                pyproject_path,
                ["ruff", "mypy", "black", "bandit", "pylint", "sqlparse", "dockerfile-parse"]
            )

            stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                str(target_dir), "pip_linters"
            )

            with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
                 open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:

                # Install linters as separate packages
                result = subprocess.run(
                    [str(python_exe), "-m", "pip", "install"] + linter_packages,
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=300  # Increased to 5 minutes for slower systems
                )
            
            with open(stdout_path, encoding='utf-8') as f:
                result.stdout = f.read()
            with open(stderr_path, encoding='utf-8') as f:
                result.stderr = f.read()
            
            # Clean up temp files
            try:
                Path(stdout_path).unlink()
                Path(stderr_path).unlink()
            except (OSError, PermissionError):
                pass
            
            if result.returncode == 0:
                check_mark = "[OK]"
                print(f"    {check_mark} Python linters installed")

                # Now install tree-sitter packages separately
                print("  Installing tree-sitter AST tools...", flush=True)
                # Read versions from pyproject.toml (single source of truth)
                ast_packages = _get_runtime_packages(
                    pyproject_path,
                    ["tree-sitter", "tree-sitter-language-pack"]
                )

                stdout_path2, stderr_path2 = TempManager.create_temp_files_for_subprocess(
                    str(target_dir), "pip_ast"
                )

                with open(stdout_path2, 'w+', encoding='utf-8') as stdout_fp, \
                     open(stderr_path2, 'w+', encoding='utf-8') as stderr_fp:

                    result2 = subprocess.run(
                        [str(python_exe), "-m", "pip", "install"] + ast_packages,
                        stdout=stdout_fp,
                        stderr=stderr_fp,
                        text=True,
                        timeout=300
                    )

                with open(stdout_path2, encoding='utf-8') as f:
                    result2.stdout = f.read()
                with open(stderr_path2, encoding='utf-8') as f:
                    result2.stderr = f.read()

                # Clean up temp files
                try:
                    Path(stdout_path2).unlink()
                    Path(stderr_path2).unlink()
                except (OSError, PermissionError):
                    pass

                if result2.returncode == 0:
                    print(f"    {check_mark} AST tools installed")
                    print(f"    {check_mark} All Python tools ready:")
                    print(f"        - Linters: ruff, mypy, black, bandit, pylint")
                    print(f"        - Parsers: sqlparse, dockerfile-parse")
                    print(f"        - AST analysis: tree-sitter (Python/JS/TS)")
                else:
                    print(f"    ⚠ Tree-sitter installation failed: {result2.stderr[:200]}")
            else:
                print(f"    ⚠ Some linters failed to install: {result.stderr[:200]}")
        except Exception as e:
            print(f"    ⚠ Error installing tools: {e}")
        
        # ALWAYS install JavaScript tools in SANDBOXED location
        # These are core TheAuditor tools needed for any project analysis
        print("\nSetting up JavaScript/TypeScript tools in sandboxed environment...", flush=True)
        
        # Create sandboxed directory inside venv for TheAuditor's tools
        sandbox_dir = venv_path / ".theauditor_tools"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        sandbox_package_json = sandbox_dir / "package.json"
        
        # Copy package.json from TheAuditor source
        print(f"  Creating sandboxed tools directory: {sandbox_dir}", flush=True)
        
        # Look for package.json in linters directory
        package_source = theauditor_root / "theauditor" / "linters" / "package.json"
        
        if package_source.exists():
            # Copy the package.json file
            with open(package_source) as f:
                package_data = json.load(f)
        else:
            # Fallback if source not found
            print(f"    ⚠ Package.json not found at {package_source}, using minimal config")
            package_data = {
                "name": "theauditor-tools",
                "version": "1.0.0",
                "private": True,
                "description": "Sandboxed tools for TheAuditor static analysis",
                "devDependencies": {
                    "eslint": "^9.14.0",
                    "@eslint/js": "^9.14.0",
                    "typescript": "^5.6.3"
                }
            }
        
        # Write package.json to sandboxed location
        with open(sandbox_package_json, "w") as f:
            json.dump(package_data, f, indent=2)
        
        # Copy ESLint v9 flat config from TheAuditor source
        eslint_config_source = theauditor_root / "theauditor" / "linters" / "eslint.config.cjs"
        eslint_config_dest = sandbox_dir / "eslint.config.cjs"
        
        if eslint_config_source.exists():
            # Copy the ESLint v9 flat config file
            import shutil
            shutil.copy2(str(eslint_config_source), str(eslint_config_dest))
            check_mark = "[OK]"
            print(f"    {check_mark} ESLint v9 flat config copied to sandbox")
        else:
            print(f"    ⚠ ESLint config not found at {eslint_config_source}")

        # Copy Python linter config from TheAuditor source
        python_config_source = theauditor_root / "theauditor" / "linters" / "pyproject.toml"
        python_config_dest = sandbox_dir / "pyproject.toml"

        if python_config_source.exists():
            # Copy the Python linter config file
            shutil.copy2(str(python_config_source), str(python_config_dest))
            check_mark = "[OK]"
            print(f"    {check_mark} Python linter config (pyproject.toml) copied to sandbox")
        else:
            print(f"    ⚠ Python config not found at {python_config_source}")

        # Copy planning agents from TheAuditor source
        agents_source = theauditor_root / "agents"
        agents_dest = sandbox_dir / "agents"

        if agents_source.exists() and agents_source.is_dir():
            # Create agents directory in sandbox
            agents_dest.mkdir(exist_ok=True)

            # Copy all agent .md files
            agent_files = list(agents_source.glob("*.md"))
            if agent_files:
                for agent_file in agent_files:
                    dest_file = agents_dest / agent_file.name
                    shutil.copy2(str(agent_file), str(dest_file))

                check_mark = "[OK]"
                print(f"    {check_mark} Planning agents copied to sandbox ({len(agent_files)} agents)")
                print(f"        → {agents_dest}")

                # Auto-inject AGENTS.md trigger in target project root
                _inject_agents_md(target_dir)
            else:
                print(f"    ⚠ No agent files found in {agents_source}")
        else:
            print(f"    ⚠ Agents directory not found at {agents_source}")

        # Create strict TypeScript configuration for sandboxed tools
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
                "forceConsistentCasingInFileNames": True
            },
            "include": ["**/*"],
            "exclude": ["node_modules", ".auditor_venv"]
        }
        with open(tsconfig, "w") as f:
            json.dump(tsconfig_data, f, indent=2)
        
        # PARALLEL EXECUTION: Track A does package updates, Track B downloads Node.js
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
        
        # Run both tracks in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            track_a_future = executor.submit(track_a_package_updates)
            track_b_future = executor.submit(track_b_node_download)
            
            # Wait for both to complete
            concurrent.futures.wait([track_a_future, track_b_future])
        
        # Check if Node.js download failed
        if node_error:
            raise RuntimeError(f"Failed to download Node.js: {node_error}")
        if not node_exe:
            raise RuntimeError("Node.js download completed but executable not found")
        
        try:
            node_runtime_dir = sandbox_dir / "node-runtime"
            
            # Platform-specific npm command construction
            if os.name == "nt":
                # Windows: node.exe runs npm-cli.js directly
                # npm is bundled with Node.js in node_modules/npm
                npm_cli = node_runtime_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"
                if npm_cli.exists():
                    npm_cmd = [str(node_exe), str(npm_cli)]
                else:
                    # Fallback: npm.cmd in node-runtime directory
                    npm_cmd_path = node_runtime_dir / "npm.cmd"
                    npm_cmd = [str(npm_cmd_path)]
            else:
                # Unix: use npm shell script from Node.js bundle
                npm_script = node_runtime_dir / "bin" / "npm"
                npm_cmd = [str(npm_script)]
            
            print(f"  Installing JS/TS linters using bundled Node.js...", flush=True)
            stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                str(target_dir), "npm_install"
            )
            
            with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
                 open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
                
                # Build full command with "install" argument
                full_cmd = npm_cmd + ["install"]
                
                result = subprocess.run(
                    full_cmd,
                    cwd=str(sandbox_dir),  # Install in sandbox, NOT in user's project!
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=120,
                    shell=False  # No shell needed with absolute paths!
                )
            
            with open(stdout_path, encoding='utf-8') as f:
                result.stdout = f.read()
            with open(stderr_path, encoding='utf-8') as f:
                result.stderr = f.read()
            
            # Clean up temp files
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
                
                # Verify tools are installed
                eslint_path = sandbox_dir / "node_modules" / ".bin" / ("eslint.cmd" if os.name == "nt" else "eslint")
                if eslint_path.exists():
                    print(f"    {check_mark} ESLint verified at: {eslint_path}")
            else:
                print(f"    ⚠ npm install failed: {result.stderr[:500]}")
                print(f"    ⚠ This may be a network issue. Try running setup again.")
                
        except RuntimeError as e:
            print(f"    ⚠ Could not set up bundled Node.js: {e}")
            print("    ⚠ JavaScript/TypeScript linting will not be available")
            print("    ⚠ To retry: Delete .auditor_venv and run setup again")
        except Exception as e:
            print(f"    ⚠ Unexpected error setting up JS tools: {e}")

        # Setup vulnerability scanning tools (OSV-Scanner)
        # These are needed by the vulnerability_scanner.py module
        print("\nSetting up vulnerability scanning tools...", flush=True)

        # OSV-Scanner for cross-platform vulnerability detection
        osv_scanner_path = setup_osv_scanner(sandbox_dir)
        if osv_scanner_path:
            check_mark = "[OK]"
            print(f"{check_mark} OSV-Scanner ready for vulnerability detection")
        else:
            print("⚠ OSV-Scanner setup failed - vulnerability detection may be limited")


    return venv_path, success
