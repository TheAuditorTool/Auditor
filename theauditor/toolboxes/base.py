"""Common utilities for toolbox implementations."""

import gzip
import platform
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import urllib.error
from theauditor import __version__


def download_file(url: str, dest: Path, timeout: int = 30) -> None:
    """
    Download file from URL to destination path.

    Args:
        url: URL to download from
        dest: Destination file path
        timeout: Request timeout in seconds

    Raises:
        urllib.error.URLError: If download fails
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url)
    req.add_header('User-Agent', f'TheAuditor/{__version__}')

    with urllib.request.urlopen(req, timeout=timeout) as response:
        with open(dest, 'wb') as f:
            shutil.copyfileobj(response, f)


def decompress_gz(src: Path, dest: Path) -> None:
    """
    Decompress .gz file to destination.

    Args:
        src: Source .gz file path
        dest: Destination file path
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(src, 'rb') as f_in:
        with open(dest, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)


def decompress_zip(src: Path, dest_dir: Path, binary_name: str) -> Path:
    """
    Extract binary from .zip file.

    Args:
        src: Source .zip file path
        dest_dir: Destination directory
        binary_name: Name of binary to extract

    Returns:
        Path to extracted binary

    Raises:
        FileNotFoundError: If binary not found in archive
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(src, 'r') as zip_ref:
        # Find binary in archive
        for name in zip_ref.namelist():
            if binary_name in name:
                zip_ref.extract(name, dest_dir)
                return dest_dir / name

    raise FileNotFoundError(f"{binary_name} not found in {src}")


def get_sandbox_dir() -> Path:
    """
    Get sandbox directory for tools.

    Returns:
        Path to ~/.auditor_venv/.theauditor_tools/
    """
    sandbox_dir = Path.home() / '.auditor_venv' / '.theauditor_tools'
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    return sandbox_dir


def detect_platform() -> Dict[str, str]:
    """
    Detect current platform and architecture.

    Returns:
        Dict with 'os', 'machine', and 'is_windows' keys
        Example: {'os': 'darwin', 'machine': 'arm64', 'is_windows': False}
    """
    os_name = platform.system().lower()
    machine = platform.machine().lower()

    return {
        'os': os_name,
        'machine': machine,
        'is_windows': os_name == 'windows'
    }
