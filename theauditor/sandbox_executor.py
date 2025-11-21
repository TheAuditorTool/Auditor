"""Bundled runtime isolation for TheAuditor.

ARCHITECTURE: Bundled Runtime Isolation
========================================
TheAuditor bundles all external tool dependencies in .auditor_venv/:

BUNDLED RUNTIMES:
  - Python venv with all analysis dependencies (PyYAML, sqlparse, numpy, etc.)
  - Portable Node.js runtime (no system Node.js required)
  - npm packages (TypeScript parser, ESLint, etc.)

This module provides path helpers to use bundled tools instead of system installations.
Users don't need npm/node/pip packages installed globally - everything runs from .auditor_venv/.

USAGE:
  from theauditor.sandbox_executor import get_bundled_node, get_bundled_npm

  node_path = get_bundled_node()
  subprocess.run([str(node_path), 'script.js'])
"""


import platform
import sys
from pathlib import Path


def find_bundled_venv(root_path: Path = None) -> Path | None:
    """
    Find .auditor_venv in current directory or parent directories.

    Walks up the directory tree to find the nearest bundled runtime venv.
    This allows running commands from subdirectories.

    Args:
        root_path: Starting directory (defaults to cwd)

    Returns:
        Path to .auditor_venv or None if not found
    """
    if root_path is None:
        root_path = Path.cwd()

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


def get_bundled_python(root_path: Path = None) -> Path:
    """
    Get path to bundled Python executable.

    Handles platform differences (Windows vs Unix).

    Args:
        root_path: Starting directory to search for .auditor_venv (defaults to cwd)

    Returns:
        Path to python executable

    Raises:
        RuntimeError: If .auditor_venv or python not found
    """
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\n"
            "Run: aud setup-ai --target ."
        )

    if platform.system() == "Windows":
        python_exe = venv / "Scripts" / "python.exe"
    else:
        python_exe = venv / "bin" / "python"

    if not python_exe.exists():
        raise RuntimeError(
            f"Bundled Python not found: {python_exe}\n"
            f"Recreate bundled runtime: aud setup-ai --target . --sync"
        )

    return python_exe


def get_bundled_node(root_path: Path = None) -> Path:
    """
    Get path to bundled Node.js executable.

    Args:
        root_path: Starting directory to search for .auditor_venv (defaults to cwd)

    Returns:
        Path to node executable

    Raises:
        RuntimeError: If .auditor_venv or node not found
    """
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\n"
            "Run: aud setup-ai --target ."
        )

    toolbox = venv / "toolbox"
    if platform.system() == "Windows":
        node_exe = toolbox / "node.exe"
    else:
        node_exe = toolbox / "bin" / "node"

    if not node_exe.exists():
        raise RuntimeError(
            f"Bundled Node.js not found: {node_exe}\n"
            f"Recreate bundled runtime: aud setup-ai --target . --sync"
        )

    return node_exe


def get_bundled_npm(root_path: Path = None) -> Path:
    """
    Get path to bundled npm executable.

    Args:
        root_path: Starting directory to search for .auditor_venv (defaults to cwd)

    Returns:
        Path to npm executable (or npm.cmd on Windows)

    Raises:
        RuntimeError: If .auditor_venv or npm not found
    """
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\n"
            "Run: aud setup-ai --target ."
        )

    toolbox = venv / "toolbox"
    if platform.system() == "Windows":
        npm_exe = toolbox / "npm.cmd"
    else:
        npm_exe = toolbox / "bin" / "npm"

    if not npm_exe.exists():
        raise RuntimeError(
            f"Bundled npm not found: {npm_exe}\n"
            f"Recreate bundled runtime: aud setup-ai --target . --sync"
        )

    return npm_exe


def get_bundled_tool(tool_name: str, root_path: Path = None) -> Path:
    """
    Get path to a bundled npm tool (TypeScript, ESLint, etc.).

    Args:
        tool_name: Name of the npm tool (e.g., 'typescript', 'eslint')
        root_path: Starting directory to search for .auditor_venv (defaults to cwd)

    Returns:
        Path to the tool's node_modules/.bin directory

    Raises:
        RuntimeError: If .auditor_venv not found
    """
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\n"
            "Run: aud setup-ai --target ."
        )

    if platform.system() == "Windows":
        tool_path = venv / "toolbox" / "node_modules" / ".bin" / f"{tool_name}.cmd"
    else:
        tool_path = venv / "toolbox" / "node_modules" / ".bin" / tool_name

    if not tool_path.exists():
        raise RuntimeError(
            f"Bundled tool '{tool_name}' not found: {tool_path}\n"
            f"Install it: Run from .auditor_venv/toolbox/: npm install {tool_name}"
        )

    return tool_path
