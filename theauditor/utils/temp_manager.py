"""Centralized temporary file management for TheAuditor.

This module provides a custom temporary directory solution that avoids
WSL2/Windows permission issues by creating temp files within the project's
.auditor_venv directory instead of system temp.
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple


class TempManager:
    """Manages temporary files within project boundaries to avoid cross-filesystem issues."""
    
    @staticmethod
    def get_temp_dir(root_path: str) -> Path:
        """Get the project-specific temp directory.
        
        Args:
            root_path: Project root directory
            
        Returns:
            Path to temp directory (.auditor_venv/tmp/)
        """
        temp_dir = Path(root_path) / ".auditor_venv" / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    @staticmethod
    def create_temp_file(root_path: str, suffix: str = ".txt", prefix: str = "tmp") -> Tuple[Path, int]:
        """Create a temporary file in project temp directory.
        
        Args:
            root_path: Project root directory
            suffix: File suffix (e.g., "_stdout.txt")
            prefix: File prefix (e.g., "tmp")
            
        Returns:
            Tuple of (file_path, file_descriptor)
        """
        temp_dir = TempManager.get_temp_dir(root_path)
        
        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{prefix}_{unique_id}{suffix}"
        file_path = temp_dir / filename
        
        # Create and open file
        fd = os.open(str(file_path), os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        
        return file_path, fd
    
    @staticmethod
    def cleanup_temp_dir(root_path: str) -> bool:
        """Clean up all temporary files in project temp directory.
        
        Args:
            root_path: Project root directory
            
        Returns:
            True if cleanup successful, False otherwise
        """
        temp_dir = Path(root_path) / ".auditor_venv" / "tmp"
        
        if not temp_dir.exists():
            return True
        
        try:
            # Remove all files in temp directory
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    try:
                        temp_file.unlink()
                    except (OSError, PermissionError):
                        # Continue even if some files can't be deleted
                        pass
            
            # Try to remove directory if empty
            try:
                temp_dir.rmdir()
            except OSError:
                # Directory not empty or in use
                pass
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def create_temp_files_for_subprocess(root_path: str, tool_name: str = "process") -> Tuple[Path, Path]:
        """Create stdout and stderr temp files for subprocess capture.
        
        Args:
            root_path: Project root directory  
            tool_name: Name of tool/process (for filename)
            
        Returns:
            Tuple of (stdout_path, stderr_path)
        """
        # Sanitize tool name for safe filenames (remove problematic chars)
        safe_tool_name = tool_name.replace('/', '_').replace('\\', '_').replace(':', '_')
        safe_tool_name = safe_tool_name.replace('(', '').replace(')', '').replace(' ', '_')
        # Limit length to avoid path too long errors
        safe_tool_name = safe_tool_name[:50]
        
        stdout_path, stdout_fd = TempManager.create_temp_file(
            root_path, 
            suffix=f"_{safe_tool_name}_stdout.txt",
            prefix="subprocess"
        )
        os.close(stdout_fd)  # Close fd, we'll open with Python's file handling
        
        stderr_path, stderr_fd = TempManager.create_temp_file(
            root_path,
            suffix=f"_{safe_tool_name}_stderr.txt", 
            prefix="subprocess"
        )
        os.close(stderr_fd)  # Close fd, we'll open with Python's file handling
        
        return stdout_path, stderr_path


# Convenience function for backward compatibility
def get_project_temp_dir(root_path: str) -> Path:
    """Get project-specific temp directory.
    
    Args:
        root_path: Project root directory
        
    Returns:
        Path to temp directory
    """
    return TempManager.get_temp_dir(root_path)


def cleanup_project_temp(root_path: str) -> bool:
    """Clean up project temp directory.
    
    Args:
        root_path: Project root directory
        
    Returns:
        True if successful
    """
    return TempManager.cleanup_temp_dir(root_path)