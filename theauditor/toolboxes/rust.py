"""Rust language toolbox for TheAuditor.

================== PRESERVATION NOTICE ==================
STATUS: Currently unused (tree-sitter doesn't need rust-analyzer)
PRESERVED FOR: Potential future hybrid approach

This toolbox downloads and manages rust-analyzer binary for LSP-based
semantic analysis.

CURRENT USAGE: None (extractor uses tree-sitter, not LSP)
POTENTIAL FUTURE USE: Hybrid LSP (types) + tree-sitter (AST) approach

If future hybrid approach is implemented:
- This toolbox provides binary management
- See lsp/rust_analyzer_client.py for LSP client
- See indexer/extractors/rust_lsp_backup.py for integration example

PRESERVED: 2025-10-11
===========================================================
"""
from __future__ import annotations


import os
import subprocess
import urllib.error
from pathlib import Path
from typing import Dict, Any

from theauditor import __version__
from . import LanguageToolbox
from .base import get_sandbox_dir, detect_platform


class RustToolbox(LanguageToolbox):
    """Toolbox for Rust projects using rust-analyzer LSP."""

    @staticmethod
    def _verify_binary(binary_path: Path, timeout: int = 5) -> tuple[bool, str]:
        """Verify binary works by running --version.

        Args:
            binary_path: Path to binary to verify
            timeout: Command timeout in seconds

        Returns:
            Tuple of (success: bool, version_or_error: str)
        """
        try:
            result = subprocess.run(
                [str(binary_path), '--version'],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, result.stderr
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _build_result(status: str, path: Path = None, version: str = '',
                      cached: bool = False, message: str = '') -> dict[str, Any]:
        """Build installation result dict.

        Args:
            status: 'success', 'cached', or 'error'
            path: Path to installed binary (for success/cached)
            version: Binary version string (for success/cached)
            cached: Whether binary was already installed
            message: Error message (for error status)

        Returns:
            Installation result dict
        """
        result = {'status': status}
        if path:
            result['path'] = str(path)
        if version:
            result['version'] = version
        if status in ['success', 'cached']:
            result['cached'] = cached
        if message:
            result['message'] = message
        return result

    def detect_project(self, project_dir: Path) -> bool:
        """
        Detect if project is a Rust project by checking for Cargo.toml.

        Args:
            project_dir: Path to project root directory

        Returns:
            True if Cargo.toml exists in project root
        """
        cargo_toml = project_dir / 'Cargo.toml'
        return cargo_toml.exists()

    def install(self, force: bool = False) -> dict[str, Any]:
        """
        Install rust-analyzer to sandbox directory.

        Downloads rust-analyzer binary from GitHub releases and installs
        to ~/.auditor_venv/.theauditor_tools/rust/

        Args:
            force: If True, re-download even if cached

        Returns:
            Installation result dict:
            {
                'status': 'success' | 'cached' | 'error',
                'path': str,
                'version': str,
                'cached': bool
            }
        """
        import gzip
        import json
        import urllib.request
        import zipfile

        from .base import download_file, decompress_gz, decompress_zip

        try:
            sandbox_dir = get_sandbox_dir() / 'rust'
            sandbox_dir.mkdir(parents=True, exist_ok=True)

            # Detect platform
            platform_info = self._detect_platform()
            if 'error' in platform_info:
                return self._build_result('error', message=platform_info['message'])

            binary_name = platform_info['binary_name']
            binary_path = sandbox_dir / binary_name

            # Check if already installed
            if binary_path.exists() and not force:
                success, version = self._verify_binary(binary_path)
                if success:
                    return self._build_result('cached', binary_path, version, cached=True)
                # Binary exists but doesn't work, will re-install

            # Get latest release tag from GitHub API
            api_url = 'https://api.github.com/repos/rust-lang/rust-analyzer/releases/latest'
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', f'TheAuditor/{__version__}')

            with urllib.request.urlopen(req, timeout=30) as response:
                release_data = json.loads(response.read())
                tag = release_data['tag_name']

            # Construct download URL
            arch = platform_info['arch']
            is_windows = platform_info['os'] == 'windows'

            if is_windows:
                filename = f'rust-analyzer-{arch}.zip'
            else:
                filename = f'rust-analyzer-{arch}.gz'

            url = f'https://github.com/rust-lang/rust-analyzer/releases/download/{tag}/{filename}'

            # Download compressed file
            compressed_path = sandbox_dir / filename
            download_file(url, compressed_path)

            # Decompress
            if is_windows:
                decompress_zip(compressed_path, sandbox_dir, binary_name)
            else:
                decompress_gz(compressed_path, binary_path)

            # Clean up compressed file
            compressed_path.unlink()

            # Make executable on Unix
            if not is_windows:
                os.chmod(binary_path, 0o755)

            # Verify binary works
            success, version = self._verify_binary(binary_path)

            if not success:
                return self._build_result('error',
                    message=f'rust-analyzer binary verification failed: {version}')

            return self._build_result('success', binary_path, version, cached=False)

        except (OSError, subprocess.CalledProcessError, urllib.error.URLError) as e:
            return self._build_result('error', message=f'{type(e).__name__}: {str(e)}')

    def _detect_platform(self) -> dict[str, str]:
        """
        Detect current platform and architecture for rust-analyzer.

        Returns:
            Dict with os, arch, and binary_name fields
        """
        platform_info = detect_platform()
        os_name = platform_info['os']
        machine = platform_info['machine']

        # Map to rust-analyzer platform names
        if os_name == 'darwin':
            if machine in ['arm64', 'aarch64']:
                arch = 'aarch64-apple-darwin'
            else:
                arch = 'x86_64-apple-darwin'
        elif os_name == 'linux':
            arch = 'x86_64-unknown-linux-gnu'
        elif os_name == 'windows':
            arch = 'x86_64-pc-windows-msvc'
        else:
            return {
                'error': 'UnsupportedPlatform',
                'message': f'Platform {os_name} not supported'
            }

        binary_name = 'rust-analyzer.exe' if platform_info['is_windows'] else 'rust-analyzer'

        return {
            'os': os_name,
            'arch': arch,
            'binary_name': binary_name
        }


def get_rust_analyzer_path() -> Path:
    """
    Get path to rust-analyzer binary in sandbox.

    Returns:
        Path to rust-analyzer binary

    Raises:
        FileNotFoundError: If rust-analyzer not installed
    """
    sandbox_dir = get_sandbox_dir() / 'rust'
    binary_path = sandbox_dir / 'rust-analyzer'

    if not binary_path.exists():
        raise FileNotFoundError(
            "rust-analyzer not installed. Run: aud setup-ai --target ."
        )

    return binary_path
