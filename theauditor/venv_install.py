"""Pure Python venv creation and TheAuditor installation."""

import json
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Optional, Tuple

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


def get_venv_paths(venv_path: Path) -> Tuple[Path, Path]:
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
            check_mark = "[OK]" if IS_WINDOWS else "✓"
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
    check_mark = "[OK]" if IS_WINDOWS else "✓"
    print(f"{check_mark} Created venv: {venv_path}")
    
    return venv_path


def install_theauditor_editable(venv_path: Path, theauditor_root: Optional[Path] = None) -> bool:
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
        
        with open(stdout_path, 'r', encoding='utf-8') as f:
            result.stdout = f.read()
        with open(stderr_path, 'r', encoding='utf-8') as f:
            result.stderr = f.read()
        
        # Clean up temp files
        try:
            Path(stdout_path).unlink()
            Path(stderr_path).unlink()
        except (OSError, PermissionError):
            pass
        
        if result.returncode == 0:
            check_mark = "[OK]" if IS_WINDOWS else "✓"
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
        "-e", str(theauditor_root)
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
        
        with open(stdout_path, 'r', encoding='utf-8') as f:
            result.stdout = f.read()
        with open(stderr_path, 'r', encoding='utf-8') as f:
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
        
        check_mark = "[OK]" if IS_WINDOWS else "✓"
        print(f"{check_mark} Installed TheAuditor (editable) from {theauditor_root}")
        
        # Verify installation
        if aud_exe.exists():
            check_mark = "[OK]" if IS_WINDOWS else "✓"
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
            
            with open(stdout_path, 'r', encoding='utf-8') as f:
                verify_result.stdout = f.read()
            with open(stderr_path, 'r', encoding='utf-8') as f:
                verify_result.stderr = f.read()
            
            # Clean up temp files
            try:
                Path(stdout_path).unlink()
                Path(stderr_path).unlink()
            except (OSError, PermissionError):
                pass
            
            if verify_result.returncode == 0:
                check_mark = "[OK]" if IS_WINDOWS else "✓"
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
        with open(package_json_path, 'r') as f:
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
                            check_mark = "[OK]" if IS_WINDOWS else "✓"
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
                            check_mark = "[OK]" if IS_WINDOWS else "✓"
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
        check_mark = "[OK]" if IS_WINDOWS else "✓"
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
        
        check_mark = "[OK]" if IS_WINDOWS else "✓"
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
        
        check_mark = "[OK]" if IS_WINDOWS else "✓"
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


def setup_project_venv(target_dir: Path, force: bool = False) -> Tuple[Path, bool]:
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
                
                with open(stdout_path, 'r', encoding='utf-8') as f:
                    result.stdout = f.read()
                with open(stderr_path, 'r', encoding='utf-8') as f:
                    result.stderr = f.read()
                
                # Clean up temp files
                try:
                    Path(stdout_path).unlink()
                    Path(stderr_path).unlink()
                except (OSError, PermissionError):
                    pass
                
                if result.returncode == 0:
                    check_mark = "[OK]" if IS_WINDOWS else "✓"
                    print(f"    {check_mark} Updated to latest package versions")
        except Exception as e:
            print(f"    ⚠ Could not update versions: {e}")
        
        # Install linters AND ast tools from pyproject.toml
        # AST tools (tree-sitter) are CRITICAL for proper pattern detection
        try:
            print("  Installing linters and AST tools from pyproject.toml...", flush=True)
            stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                str(target_dir), "pip_linters"
            )
            
            with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
                 open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
                
                result = subprocess.run(
                    [str(python_exe), "-m", "pip", "install", "-e", f"{theauditor_root}[linters,ast]"],
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=300  # Increased to 5 minutes for slower systems and compilation
                )
            
            with open(stdout_path, 'r', encoding='utf-8') as f:
                result.stdout = f.read()
            with open(stderr_path, 'r', encoding='utf-8') as f:
                result.stderr = f.read()
            
            # Clean up temp files
            try:
                Path(stdout_path).unlink()
                Path(stderr_path).unlink()
            except (OSError, PermissionError):
                pass
            
            if result.returncode == 0:
                check_mark = "[OK]" if IS_WINDOWS else "✓"
                print(f"    {check_mark} Python tools installed:")
                print(f"        - Linters: ruff, mypy, black, bandit, pylint")
                print(f"        - AST analysis: tree-sitter (Python/JS/TS), sqlparse, dockerfile-parse")
            else:
                print(f"    ⚠ Some tools failed to install: {result.stderr[:200]}")
        except Exception as e:
            print(f"    ⚠ Error installing linters: {e}")
        
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
            check_mark = "[OK]" if IS_WINDOWS else "✓"
            print(f"    {check_mark} ESLint v9 flat config copied to sandbox")
        else:
            print(f"    ⚠ ESLint config not found at {eslint_config_source}")
        
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
            
            with open(stdout_path, 'r', encoding='utf-8') as f:
                result.stdout = f.read()
            with open(stderr_path, 'r', encoding='utf-8') as f:
                result.stderr = f.read()
            
            # Clean up temp files
            try:
                Path(stdout_path).unlink()
                Path(stderr_path).unlink()
            except (OSError, PermissionError):
                pass
            
            if result.returncode == 0:
                check_mark = "[OK]" if IS_WINDOWS else "✓"
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
        
    
    return venv_path, success