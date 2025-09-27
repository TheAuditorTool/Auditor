"""Linter detection module - discovers available linters in the repository."""

import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

# Detect if running on Windows for subprocess shell handling
IS_WINDOWS = platform.system() == "Windows"


def run_subprocess_safe(cmd, cwd=None, timeout=5, shell=IS_WINDOWS):
    """Helper to run subprocess with temp files to avoid buffer overflow."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt', encoding='utf-8') as stdout_fp, \
         tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt', encoding='utf-8') as stderr_fp:
        
        stdout_path = stdout_fp.name
        stderr_path = stderr_fp.name
        
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=stdout_fp,
            stderr=stderr_fp,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            shell=shell,
        )
    
    with open(stdout_path, 'r', encoding='utf-8', errors='replace') as f:
        result.stdout = f.read()
    with open(stderr_path, 'r', encoding='utf-8', errors='replace') as f:
        result.stderr = f.read()
    
    os.unlink(stdout_path)
    os.unlink(stderr_path)
    
    return result


def detect_linters(root_path: str, auto_fix: bool = False) -> dict[str, list[str]]:
    """
    Detect available linters in the repository.
    
    Args:
        root_path: Root directory to detect linters in
        auto_fix: DEPRECATED - No longer used. Kept for compatibility.
                  Users should run linters directly with their own --fix flags.
    
    Returns:
        Dict mapping tool name to command args
    """
    # DEPRECATED: Auto-fix functionality disabled to prevent version mismatch issues
    # between sandboxed tools and project-specific versions. Users should run
    # linters directly with their own auto-fix flags if desired.
    auto_fix = False  # Force disabled
    linters = {}
    root = Path(root_path)
    
    # Check for sandboxed JavaScript/TypeScript tools in .auditor_venv/.theauditor_tools
    # ONLY use TheAuditor's dedicated sandbox environment - no contamination from user's .venv
    venv_dir = root / ".auditor_venv"
    if venv_dir.exists():
        sandbox_dir = venv_dir / ".theauditor_tools"
    else:
        sandbox_dir = None
    
    # JavaScript/TypeScript linters - prefer sandboxed versions
    js_files_exist = any(root.glob("**/*.js")) or any(root.glob("**/*.jsx")) or any(root.glob("**/*.ts")) or any(root.glob("**/*.tsx"))
    
    if js_files_exist and sandbox_dir and sandbox_dir.exists():
        # Check if bundled Node.js is available before registering JS tools
        node_runtime_dir = sandbox_dir / "node-runtime"
        if IS_WINDOWS:
            bundled_node = node_runtime_dir / "node.exe"
        else:
            bundled_node = node_runtime_dir / "bin" / "node"
        
        if not bundled_node.exists():
            # No bundled Node.js, skip JavaScript tool detection
            print("    WARNING: Bundled Node.js not found. Run 'aud setup-claude --target .' to install.")
            sandbox_dir = None  # Disable JS tool detection
        
    if js_files_exist and sandbox_dir and sandbox_dir.exists():
        # Use sandboxed tools (isolated from project)
        bin_dir = sandbox_dir / "node_modules" / ".bin"
        
        # Check for ESLint in sandbox
        eslint_configs = list(root.glob(".eslintrc.*")) + list(root.glob("eslint.*"))
        eslint_cmd = "eslint.cmd" if IS_WINDOWS else "eslint"
        eslint_path = bin_dir / eslint_cmd
        if eslint_path.exists() and (eslint_configs or (root / "package.json").exists()):
            try:
                # Windows .cmd files need string command with shell=True
                if IS_WINDOWS:
                    result = run_subprocess_safe(f'"{str(eslint_path)}" --version')
                else:
                    result = run_subprocess_safe([str(eslint_path), "--version"])
                if result.returncode == 0:
                    # CRITICAL: Use our sandboxed ESLint v9 flat config to enforce strict rules
                    eslint_config = sandbox_dir / "eslint.config.cjs"  # .cjs forces CommonJS
                    # AUTO-FIX DEPRECATED: Always run in check-only mode
                    # if auto_fix:
                    #     linters["eslint"] = [str(eslint_path), "-c", str(eslint_config), "--fix", "--format", "json"]
                    # else:
                    linters["eslint"] = [str(eslint_path), "-c", str(eslint_config), "--format", "json"]
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                pass
        
        # TypeScript checking is handled by ESLint with @typescript-eslint plugin
        # TSC is a compiler, not a linter - it needs all project dependencies
        # which our sandbox doesn't have. ESLint provides better linting for TS.
        
        # Check for Prettier in sandbox
        prettier_configs = list(root.glob(".prettierrc*")) + list(root.glob("prettier.*"))
        prettier_cmd = "prettier.cmd" if IS_WINDOWS else "prettier"
        prettier_path = bin_dir / prettier_cmd
        if prettier_path.exists() and (prettier_configs or (root / "package.json").exists()):
            try:
                # Windows .cmd files need string command with shell=True
                if IS_WINDOWS:
                    result = run_subprocess_safe(f'"{str(prettier_path)}" --version')
                else:
                    result = run_subprocess_safe([str(prettier_path), "--version"])
                if result.returncode == 0:
                    # Use --no-config to ignore project's .prettierrc that may require plugins we don't have
                    # AUTO-FIX DEPRECATED: Always run in check-only mode
                    # if auto_fix:
                    #     linters["prettier"] = [str(prettier_path), "--write", "--no-config"]
                    # else:
                    linters["prettier"] = [str(prettier_path), "--check", "--no-config"]
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                pass
    
    # REMOVED: We no longer fall back to user's project tools
    # TheAuditor uses only its own sandboxed tools to avoid contamination
    # and ensure consistent, reproducible results across all environments.
    # If sandboxed tools are not available, user must run 'aud setup-claude'

    # Python linters - STRICT SANDBOX ONLY (like JavaScript)
    # Use a generator to avoid materializing the entire list for performance
    python_files_exist = any(root.glob("**/*.py"))
    if python_files_exist:
        # Check for sandboxed Python tools in .auditor_venv
        # ONLY use TheAuditor's dedicated sandbox environment - no contamination from global Python
        venv_dir = root / ".auditor_venv"
        if not venv_dir.exists():
            print("    WARNING: Python sandbox not found. Run 'aud setup-claude --target .' to install.")
            # Return empty - no fallback to global tools
            return linters

        # Platform-specific binary directory
        if IS_WINDOWS:
            venv_bin = venv_dir / "Scripts"
        else:
            venv_bin = venv_dir / "bin"

        if not venv_bin.exists():
            print("    WARNING: Python sandbox is corrupted (missing bin/Scripts). Run 'aud setup-claude --target . --sync' to repair.")
            return linters

        # Check for ruff in SANDBOX ONLY
        ruff_exe = "ruff.exe" if IS_WINDOWS else "ruff"
        sandbox_ruff = venv_bin / ruff_exe
        if sandbox_ruff.exists():
            try:
                # Verify it actually works
                result = run_subprocess_safe([str(sandbox_ruff), "--version"])
                if result.returncode == 0:
                    # Use config file from sandbox tools directory
                    config_path = venv_dir / ".theauditor_tools" / "pyproject.toml"
                    if config_path.exists():
                        linters["ruff"] = [str(sandbox_ruff), "check", "--config", str(config_path), "--output-format", "concise"]
                    else:
                        print(f"    WARNING: Python config not found at {config_path}. Run 'aud setup-claude --target . --sync' to repair.")
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                print(f"    WARNING: Sandbox ruff exists but failed to execute. Run 'aud setup-claude --target . --sync' to repair.")

        # Check for mypy in SANDBOX ONLY
        mypy_exe = "mypy.exe" if IS_WINDOWS else "mypy"
        sandbox_mypy = venv_bin / mypy_exe
        if sandbox_mypy.exists():
            try:
                result = run_subprocess_safe([str(sandbox_mypy), "--version"])
                if result.returncode == 0:
                    # Use config file for all mypy settings
                    config_path = venv_dir / ".theauditor_tools" / "pyproject.toml"
                    if config_path.exists():
                        linters["mypy"] = [str(sandbox_mypy), "--config-file", str(config_path)]
                    else:
                        print(f"    WARNING: Python config not found at {config_path}. Run 'aud setup-claude --target . --sync' to repair.")
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                print(f"    WARNING: Sandbox mypy exists but failed to execute. Run 'aud setup-claude --target . --sync' to repair.")

        # Check for black in SANDBOX ONLY
        black_exe = "black.exe" if IS_WINDOWS else "black"
        sandbox_black = venv_bin / black_exe
        if sandbox_black.exists():
            try:
                result = run_subprocess_safe([str(sandbox_black), "--version"])
                if result.returncode == 0:
                    # Black will read config from pyproject.toml
                    config_path = venv_dir / ".theauditor_tools" / "pyproject.toml"
                    if config_path.exists():
                        linters["black"] = [str(sandbox_black), "--check", "--diff", "--quiet", "--config", str(config_path)]
                    else:
                        print(f"    WARNING: Python config not found at {config_path}. Run 'aud setup-claude --target . --sync' to repair.")
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                print(f"    WARNING: Sandbox black exists but failed to execute. Run 'aud setup-claude --target . --sync' to repair.")

        # Check for bandit in SANDBOX ONLY
        bandit_exe = "bandit.exe" if IS_WINDOWS else "bandit"
        sandbox_bandit = venv_bin / bandit_exe
        if sandbox_bandit.exists():
            try:
                result = run_subprocess_safe([str(sandbox_bandit), "--version"])
                if result.returncode == 0:
                    # Use config file for comprehensive security scanning
                    config_path = venv_dir / ".theauditor_tools" / "pyproject.toml"
                    if config_path.exists():
                        linters["bandit"] = [
                            str(sandbox_bandit),
                            "-f", "json",  # JSON output for parsing
                            "--configfile", str(config_path)
                            # Config file controls severity/confidence levels
                        ]
                    else:
                        print(f"    WARNING: Python config not found at {config_path}. Run 'aud setup-claude --target . --sync' to repair.")
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                print(f"    WARNING: Sandbox bandit exists but failed to execute. Run 'aud setup-claude --target . --sync' to repair.")

        # NO FALLBACK TO GLOBAL TOOLS - Sandbox or nothing!

    # Go linters
    if (root / "go.mod").exists():
        # Check for golangci-lint
        try:
            result = run_subprocess_safe(["golangci-lint", "--version"])
            if result.returncode == 0:
                linters["golangci-lint"] = ["golangci-lint", "run", "--out-format", "line-number"]
            else:
                # Fall back to go vet
                try:
                    result = run_subprocess_safe(["go", "version"])
                    if result.returncode == 0:
                        linters["go-vet"] = ["go", "vet"]
                except (subprocess.SubprocessError, FileNotFoundError, OSError):
                    pass
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            # Try go vet as fallback
            try:
                result = run_subprocess_safe(["go", "version"])
                if result.returncode == 0:
                    linters["go-vet"] = ["go", "vet"]
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                pass

    # Java linters (basic detection)
    if (root / "pom.xml").exists() or (root / "build.gradle").exists():
        # Check for SpotBugs
        if (root / "spotbugs.xml").exists():
            linters["spotbugs"] = ["mvn", "spotbugs:check"]

        # Check for Checkstyle
        if (root / "checkstyle.xml").exists():
            linters["checkstyle"] = ["mvn", "checkstyle:check"]

    return linters


def check_package_json_has_eslint(package_json_path: Path) -> bool:
    """Check if package.json has ESLint configured."""
    try:
        with open(package_json_path) as f:
            pkg = json.load(f)

        # Check dependencies
        deps = pkg.get("devDependencies", {})
        deps.update(pkg.get("dependencies", {}))
        if any("eslint" in dep for dep in deps):
            return True

        # Check scripts
        scripts = pkg.get("scripts", {})
        if any("eslint" in script for script in scripts.values()):
            return True
    except (json.JSONDecodeError, KeyError):
        pass

    return False