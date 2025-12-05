"""Centralized temporary file management for TheAuditor.

LEGACY/SPECIAL-CASE UTILITY
===========================
As of Python 3.13+, most subprocess capture use cases should use:

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    # result.stdout and result.stderr are immediately available

This TempManager class remains for edge cases where file-based capture is required:
- Very large outputs that may exceed memory limits
- Scenarios requiring persistent temp files across process boundaries
- Legacy code paths not yet migrated to capture_output=True

For new code, prefer subprocess.run(capture_output=True) unless you have a specific
reason documented in your code comments.
"""

import os
import uuid
from pathlib import Path


class TempManager:
    """Manages temporary files within project boundaries.

    WHEN TO USE:
    - Large subprocess outputs that may exceed memory
    - Cross-process temp file sharing
    - Legacy compatibility

    WHEN NOT TO USE (prefer capture_output=True):
    - Standard subprocess capture (pip, npm, git commands)
    - Any output under ~100MB
    - Single-process workflows
    """

    @staticmethod
    def get_temp_dir(root_path: str) -> Path:
        """Get the project-specific temp directory."""
        temp_dir = Path(root_path) / ".auditor_venv" / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    @staticmethod
    def create_temp_file(
        root_path: str, suffix: str = ".txt", prefix: str = "tmp"
    ) -> tuple[Path, int]:
        """Create a temporary file in project temp directory."""
        temp_dir = TempManager.get_temp_dir(root_path)

        unique_id = uuid.uuid4().hex[:8]
        filename = f"{prefix}_{unique_id}{suffix}"
        file_path = temp_dir / filename

        fd = os.open(str(file_path), os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)

        return file_path, fd

    @staticmethod
    def cleanup_temp_dir(root_path: str) -> None:
        """Clean up all temporary files in project temp directory.

        Raises:
            OSError: If cleanup fails (e.g., permission denied, file in use).
        """
        temp_dir = TempManager.get_temp_dir(root_path)

        if not temp_dir.exists():
            return

        for temp_file in temp_dir.iterdir():
            if temp_file.is_file():
                temp_file.unlink()

        temp_dir.rmdir()

    @staticmethod
    def create_temp_files_for_subprocess(
        root_path: str, tool_name: str = "process"
    ) -> tuple[Path, Path]:
        """Create stdout and stderr temp files for subprocess capture."""

        safe_tool_name = tool_name.replace("/", "_").replace("\\", "_").replace(":", "_")
        safe_tool_name = safe_tool_name.replace("(", "").replace(")", "").replace(" ", "_")

        safe_tool_name = safe_tool_name[:50]

        stdout_path, stdout_fd = TempManager.create_temp_file(
            root_path, suffix=f"_{safe_tool_name}_stdout.txt", prefix="subprocess"
        )
        os.close(stdout_fd)

        stderr_path, stderr_fd = TempManager.create_temp_file(
            root_path, suffix=f"_{safe_tool_name}_stderr.txt", prefix="subprocess"
        )
        os.close(stderr_fd)

        return stdout_path, stderr_path
