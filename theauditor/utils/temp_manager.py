"""Centralized temporary file management for TheAuditor."""

import os
import uuid
from pathlib import Path


class TempManager:
    """Manages temporary files within project boundaries to avoid cross-filesystem issues."""

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
    def cleanup_temp_dir(root_path: str) -> bool:
        """Clean up all temporary files in project temp directory."""
        temp_dir = Path(root_path) / ".auditor_venv" / "tmp"

        if not temp_dir.exists():
            return True

        try:
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    try:
                        temp_file.unlink()
                    except (OSError, PermissionError):
                        pass

            try:
                temp_dir.rmdir()
            except OSError:
                pass

            return True

        except Exception:
            return False

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


def get_project_temp_dir(root_path: str) -> Path:
    """Get project-specific temp directory."""
    return TempManager.get_temp_dir(root_path)


def cleanup_project_temp(root_path: str) -> bool:
    """Clean up project temp directory."""
    return TempManager.cleanup_temp_dir(root_path)
