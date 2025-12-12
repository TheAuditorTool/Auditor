"""Centralized tool path management for TheAuditor's sandboxed tools."""

import platform
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"


class Toolbox:
    """Manages paths to sandboxed tools in .auditor_venv/.theauditor_tools."""

    def __init__(self, project_root: Path):
        """Initialize with project root directory."""
        self.root = Path(project_root).resolve()

        if not self.root.exists():
            raise ValueError(f"Project root does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Project root is not a directory: {self.root}")

        self.venv = self.root / ".auditor_venv"
        self.sandbox = self.venv / ".theauditor_tools"

    def get_venv_binary(self, name: str, required: bool = True) -> Path | None:
        """Get path to binary in main venv (Python linters)."""
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
        """Get path to bundled Node.js executable."""
        node_runtime = self.sandbox / "node-runtime"

        node_exe = node_runtime / "node.exe" if IS_WINDOWS else node_runtime / "bin" / "node"

        if node_exe.exists():
            return node_exe

        if required:
            raise FileNotFoundError(
                f"Node.js runtime not found at {node_runtime}. "
                f"Run 'aud setup-ai --target {self.root}' to download portable Node.js."
            )

        return None

    def get_npm_command(self, required: bool = True) -> list | None:
        """Get npm command for running npm operations."""
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
        """Get path to ESLint binary in sandbox."""
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
        """Get path to TypeScript compiler (tsc) in sandbox."""
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
        """Get path to OSV-Scanner binary in sandbox."""
        osv_dir = self.sandbox / "osv-scanner"
        bundled = osv_dir / "osv-scanner.exe" if IS_WINDOWS else osv_dir / "osv-scanner"

        if bundled.exists():
            return str(bundled)

        if required:
            raise FileNotFoundError(
                f"osv-scanner not found at {bundled}. "
                f"Run 'aud setup-ai --target {self.root}' to install vulnerability scanners."
            )

        return None

    def get_osv_database_dir(self) -> Path:
        """Get path to OSV-Scanner offline database directory."""
        return self.sandbox / "osv-scanner" / "db"

    def get_eslint_config(self) -> Path:
        """Get path to ESLint flat config in sandbox."""
        return self.sandbox / "eslint.config.cjs"

    def get_python_linter_config(self) -> Path:
        """Get path to Python linter config (pyproject.toml) in sandbox."""
        return self.sandbox / "pyproject.toml"

    def get_typescript_config(self) -> Path:
        """Get path to TypeScript config in sandbox."""
        return self.sandbox / "tsconfig.json"

    def get_golangci_lint(self, required: bool = False) -> Path | None:
        """Get path to golangci-lint binary in sandbox.

        Optional by default since not all projects use Go.

        Args:
            required: If True, raise FileNotFoundError when not found

        Returns:
            Path to golangci-lint binary, or None if not found and not required
        """
        bin_dir = self.sandbox / "bin"
        bundled = bin_dir / ("golangci-lint.exe" if IS_WINDOWS else "golangci-lint")

        if bundled.exists():
            return bundled

        if required:
            raise FileNotFoundError(
                f"golangci-lint not found at {bundled}. "
                f"Run 'aud setup-ai --target {self.root}' or install via: "
                f"go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"
            )

        return None

    def get_shellcheck(self, required: bool = False) -> Path | None:
        """Get path to shellcheck binary in sandbox.

        Optional by default since not all projects use Bash.

        Args:
            required: If True, raise FileNotFoundError when not found

        Returns:
            Path to shellcheck binary, or None if not found and not required
        """
        bin_dir = self.sandbox / "bin"
        bundled = bin_dir / ("shellcheck.exe" if IS_WINDOWS else "shellcheck")

        if bundled.exists():
            return bundled

        if required:
            raise FileNotFoundError(
                f"shellcheck not found at {bundled}. "
                f"Run 'aud setup-ai --target {self.root}' or install via: "
                f"apt install shellcheck / brew install shellcheck / scoop install shellcheck"
            )

        return None

    def get_temp_dir(self) -> Path:
        """Get path to temp directory for generated configs.

        Returns:
            Path to .pf/temp/ directory (may not exist yet)
        """
        return self.root / ".pf" / "temp"

    def get_generated_tsconfig(self) -> Path:
        """Get path to generated TypeScript config.

        Returns:
            Path to .pf/temp/tsconfig.json (may not exist yet)
        """
        return self.get_temp_dir() / "tsconfig.json"

    def get_generated_eslint_config(self) -> Path:
        """Get path to generated ESLint config.

        Returns:
            Path to .pf/temp/eslint.config.cjs (may not exist yet)
        """
        return self.get_temp_dir() / "eslint.config.cjs"
