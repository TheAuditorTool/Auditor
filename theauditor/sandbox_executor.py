"""Bundled runtime isolation for TheAuditor."""

import platform
from pathlib import Path


def find_bundled_venv(root_path: Path = None) -> Path | None:
    """Find .auditor_venv in current directory or parent directories."""
    if root_path is None:
        root_path = Path.cwd()

    current = Path(root_path).resolve()

    for _ in range(10):
        venv = current / ".auditor_venv"
        if venv.exists() and venv.is_dir():
            return venv

        if current == current.parent:
            break

        current = current.parent

    return None


def get_bundled_python(root_path: Path = None) -> Path:
    """Get path to bundled Python executable."""
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\nRun: aud setup-ai --target ."
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
    """Get path to bundled Node.js executable."""
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\nRun: aud setup-ai --target ."
        )

    toolbox = venv / "toolbox"
    node_exe = toolbox / "node.exe" if platform.system() == "Windows" else toolbox / "bin" / "node"

    if not node_exe.exists():
        raise RuntimeError(
            f"Bundled Node.js not found: {node_exe}\n"
            f"Recreate bundled runtime: aud setup-ai --target . --sync"
        )

    return node_exe


def get_bundled_npm(root_path: Path = None) -> Path:
    """Get path to bundled npm executable."""
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\nRun: aud setup-ai --target ."
        )

    toolbox = venv / "toolbox"
    npm_exe = toolbox / "npm.cmd" if platform.system() == "Windows" else toolbox / "bin" / "npm"

    if not npm_exe.exists():
        raise RuntimeError(
            f"Bundled npm not found: {npm_exe}\n"
            f"Recreate bundled runtime: aud setup-ai --target . --sync"
        )

    return npm_exe


def get_bundled_tool(tool_name: str, root_path: Path = None) -> Path:
    """Get path to a bundled npm tool (TypeScript, ESLint, etc.)."""
    venv = find_bundled_venv(root_path)
    if not venv:
        raise RuntimeError(
            "Bundled runtime not found (.auditor_venv)\nRun: aud setup-ai --target ."
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
