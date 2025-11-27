"""Centralized tool path management for TheAuditor's sandboxed tools.

This module provides a single source of truth for locating binaries in the
.auditor_venv/.theauditor_tools sandbox, eliminating path construction duplication
across venv_install.py, linters.py, and vulnerability_scanner.py.

PHILOSOPHY:
- DRY: One place to update when sandbox structure changes
- Fail-fast: Raise FileNotFoundError with helpful messages
- Platform-aware: Handle Windows/Unix path differences
- Fallback support: Check system PATH as secondary option
"""

import platform
import shutil
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"


class Toolbox:
    """Manages paths to sandboxed tools in .auditor_venv/.theauditor_tools."""

    def __init__(self, project_root: Path):
        """Initialize with project root directory.

        Args:
            project_root: Path to project root (where .auditor_venv exists)

        Raises:
            ValueError: If project_root doesn't exist or isn't a directory
        """
        self.root = Path(project_root).resolve()

        if not self.root.exists():
            raise ValueError(f"Project root does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Project root is not a directory: {self.root}")

        self.venv = self.root / ".auditor_venv"
        self.sandbox = self.venv / ".theauditor_tools"

    def get_venv_binary(self, name: str, required: bool = True) -> Path | None:
        """Get path to binary in main venv (Python linters).

        Args:
            name: Binary name (e.g., 'ruff', 'mypy', 'black')
            required: If True, raise FileNotFoundError when missing

        Returns:
            Path to binary, or None if not required and not found

        Raises:
            FileNotFoundError: If required=True and binary not found
        """
        venv_bin = self.venv / ("Scripts" if IS_WINDOWS else "bin")
        binary = venv_bin / (f"{name}.exe" if IS_WINDOWS else name)

        if binary.exists():
            return binary

        if required:
            raise FileNotFoundError(
                f"{name} not found at {binary}. "
                f"Run 'aud setup-ai --target {self.root}' to install Python linters."
            )

        return None

    def get_node_runtime(self, required: bool = True) -> Path | None:
        """Get path to bundled Node.js executable.

        Args:
            required: If True, raise FileNotFoundError when missing

        Returns:
            Path to node executable, or None if not required and not found

        Raises:
            FileNotFoundError: If required=True and not found
        """
        node_runtime = self.sandbox / "node-runtime"

        if IS_WINDOWS:
            node_exe = node_runtime / "node.exe"
        else:
            node_exe = node_runtime / "bin" / "node"

        if node_exe.exists():
            return node_exe

        if required:
            raise FileNotFoundError(
                f"Node.js runtime not found at {node_runtime}. "
                f"Run 'aud setup-ai --target {self.root}' to download portable Node.js."
            )

        return None

    def get_npm_command(self, required: bool = True) -> list | None:
        """Get npm command for running npm operations.

        Args:
            required: If True, raise FileNotFoundError when missing

        Returns:
            List of command components to run npm, or None if not required and not found

        Raises:
            FileNotFoundError: If required=True and not found
        """
        node_runtime = self.sandbox / "node-runtime"

        if IS_WINDOWS:
            node_exe = node_runtime / "node.exe"
            npm_cli = node_runtime / "node_modules" / "npm" / "bin" / "npm-cli.js"

            if npm_cli.exists() and node_exe.exists():
                return [str(node_exe), str(npm_cli)]

            npm_cmd = node_runtime / "npm.cmd"
            if npm_cmd.exists():
                return [str(npm_cmd)]
        else:
            npm_exe = node_runtime / "bin" / "npm"
            if npm_exe.exists():
                return [str(npm_exe)]

        if required:
            raise FileNotFoundError(
                f"npm not found in Node.js runtime at {node_runtime}. "
                f"Run 'aud setup-ai --target {self.root}' to download portable Node.js."
            )

        return None

    def get_eslint(self, required: bool = True) -> Path | None:
        """Get path to ESLint binary in sandbox.

        Args:
            required: If True, raise FileNotFoundError when missing

        Returns:
            Path to ESLint binary, or None if not required and not found

        Raises:
            FileNotFoundError: If required=True and not found
        """
        node_modules = self.sandbox / "node_modules" / ".bin"
        eslint = node_modules / ("eslint.cmd" if IS_WINDOWS else "eslint")

        if eslint.exists():
            return eslint

        if required:
            raise FileNotFoundError(
                f"ESLint not found at {eslint}. "
                f"Run 'aud setup-ai --target {self.root}' to install JS/TS linters."
            )

        return None

    def get_typescript_compiler(self, required: bool = True) -> Path | None:
        """Get path to TypeScript compiler (tsc) in sandbox.

        Args:
            required: If True, raise FileNotFoundError when missing

        Returns:
            Path to tsc binary, or None if not required and not found

        Raises:
            FileNotFoundError: If required=True and not found
        """
        node_modules = self.sandbox / "node_modules" / ".bin"
        tsc = node_modules / ("tsc.cmd" if IS_WINDOWS else "tsc")

        if tsc.exists():
            return tsc

        if required:
            raise FileNotFoundError(
                f"TypeScript compiler not found at {tsc}. "
                f"Run 'aud setup-ai --target {self.root}' to install JS/TS tools."
            )

        return None

    def get_osv_scanner(self, required: bool = True) -> str | None:
        """Get path to OSV-Scanner binary.

        Args:
            required: If True, raise FileNotFoundError when missing

        Returns:
            Path to osv-scanner executable, or None if not required and not found

        Raises:
            FileNotFoundError: If required=True and not found in either location
        """
        osv_dir = self.sandbox / "osv-scanner"

        if IS_WINDOWS:
            bundled = osv_dir / "osv-scanner.exe"
        else:
            bundled = osv_dir / "osv-scanner"

        if bundled.exists():
            return str(bundled)

        system_osv = shutil.which("osv-scanner")
        if system_osv:
            return system_osv

        if required:
            raise FileNotFoundError(
                f"osv-scanner not found at {bundled} or in system PATH. "
                f"Run 'aud setup-ai --target {self.root}' to install vulnerability scanners."
            )

        return None

    def get_osv_database_dir(self) -> Path:
        """Get path to OSV-Scanner offline database directory.

        Returns:
            Path to database directory (may not exist yet)
        """
        return self.sandbox / "osv-scanner" / "db"

    def get_eslint_config(self) -> Path:
        """Get path to ESLint flat config in sandbox.

        Returns:
            Path to eslint.config.cjs
        """
        return self.sandbox / "eslint.config.cjs"

    def get_python_linter_config(self) -> Path:
        """Get path to Python linter config (pyproject.toml) in sandbox.

        Returns:
            Path to pyproject.toml
        """
        return self.sandbox / "pyproject.toml"

    def get_typescript_config(self) -> Path:
        """Get path to TypeScript config in sandbox.

        Returns:
            Path to tsconfig.json
        """
        return self.sandbox / "tsconfig.json"
