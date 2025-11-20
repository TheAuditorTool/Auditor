"""Execute TheAuditor commands in sandboxed environment.

ARCHITECTURE: True Sandboxing
==============================
TheAuditor uses a two-tier execution model:

1. GLOBAL INSTALL (pip install theauditor):
   - Only installs click (CLI framework)
   - Provides bootstrap commands: --help, setup-ai
   - CANNOT run analysis commands (full, lint, taint, etc.)

2. SANDBOX EXECUTION (.auditor_venv/):
   - Contains ALL runtime dependencies (PyYAML, sqlparse, numpy, etc.)
   - Contains portable Node.js + npm packages (TypeScript, ESLint, etc.)
   - Analysis commands MUST run from here

This module handles delegation from global CLI → sandbox execution.
"""
from __future__ import annotations


import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def find_sandbox_venv(root_path: Path) -> Path | None:
    """
    Find .auditor_venv in current directory or parent directories.

    Walks up the directory tree to find the nearest sandbox.
    This allows running commands from subdirectories.

    Args:
        root_path: Starting directory (usually cwd)

    Returns:
        Path to .auditor_venv or None if not found
    """
    current = Path(root_path).resolve()

    # Walk up directory tree (max 10 levels to avoid infinite loops)
    for _ in range(10):
        venv = current / ".auditor_venv"
        if venv.exists() and venv.is_dir():
            return venv

        # Stop at filesystem root
        if current == current.parent:
            break

        current = current.parent

    return None


def get_sandbox_python(sandbox_venv: Path) -> Path:
    """
    Get path to Python executable in sandbox.

    Handles platform differences (Windows vs Unix).

    Args:
        sandbox_venv: Path to .auditor_venv directory

    Returns:
        Path to python executable

    Raises:
        RuntimeError: If python executable not found
    """
    if platform.system() == "Windows":
        python_exe = sandbox_venv / "Scripts" / "python.exe"
    else:
        python_exe = sandbox_venv / "bin" / "python"

    if not python_exe.exists():
        raise RuntimeError(
            f"Sandbox Python not found: {python_exe}\n"
            f"The sandbox appears to be broken. Recreate it:\n"
            f"  aud setup-ai --target . --sync"
        )

    return python_exe


def execute_in_sandbox(command: str, args: list[str], root: str = ".") -> int:
    """
    Execute TheAuditor command in sandbox Python environment.

    This is the main delegation function that:
    1. Finds the sandbox (.auditor_venv/)
    2. Executes the command using sandbox Python
    3. Returns the exit code

    Args:
        command: Command name (e.g., 'full', 'lint', 'taint')
        args: Command arguments (e.g., ['--quiet', '--offline'])
        root: Root directory to search for sandbox

    Returns:
        Exit code from sandboxed command

    Raises:
        SystemExit: If sandbox not found (prints helpful error message)
    """
    sandbox_venv = find_sandbox_venv(Path(root))

    if not sandbox_venv:
        print("=" * 70, file=sys.stderr)
        print("ERROR: TheAuditor sandbox not found!", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("", file=sys.stderr)
        print("TheAuditor requires a sandboxed environment to run analysis.", file=sys.stderr)
        print("This keeps your Python environment clean and isolated.", file=sys.stderr)
        print("", file=sys.stderr)
        print("SETUP SANDBOX (one-time, ~2 minutes):", file=sys.stderr)
        print(f"  cd {Path(root).resolve()}", file=sys.stderr)
        print("  aud setup-ai --target .", file=sys.stderr)
        print("", file=sys.stderr)
        print("This will create .auditor_venv/ with:", file=sys.stderr)
        print("  - Python dependencies (PyYAML, sqlparse, numpy, etc.)", file=sys.stderr)
        print("  - Portable Node.js runtime (no system install needed!)", file=sys.stderr)
        print("  - JavaScript/TypeScript analysis tools", file=sys.stderr)
        print("", file=sys.stderr)
        print("After setup, run your command again:", file=sys.stderr)
        print(f"  aud {command} {' '.join(args)}", file=sys.stderr)
        print("", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(1)

    # Get sandbox Python executable
    try:
        python_exe = get_sandbox_python(sandbox_venv)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Set environment variable to indicate we're in sandbox
    # This prevents infinite recursion if command delegates again
    env = os.environ.copy()
    env["THEAUDITOR_IN_SANDBOX"] = "1"

    # Build command to execute
    # Execute the aud CLI with the same arguments
    # The sandbox's aud will have THEAUDITOR_IN_SANDBOX set,
    # so it won't delegate again (avoiding infinite recursion)
    sandbox_aud = sandbox_venv / ("Scripts/aud.exe" if platform.system() == "Windows" else "bin/aud")

    cmd = [str(sandbox_aud), command] + args

    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] Executing in sandbox: {' '.join(cmd)}", file=sys.stderr)
        print(f"[DEBUG] Sandbox Python: {python_exe}", file=sys.stderr)

    # Execute command in sandbox
    # Use subprocess.run to inherit stdio (user sees output in real-time)
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            env=env
        )
        return result.returncode
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"ERROR: Failed to execute command: {e}", file=sys.stderr)
        return 1


def is_in_sandbox() -> bool:
    """
    Check if currently running inside sandbox.

    Returns:
        True if THEAUDITOR_IN_SANDBOX environment variable is set
    """
    return os.environ.get("THEAUDITOR_IN_SANDBOX") == "1"
