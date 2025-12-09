"""File storage adapter - HOP 10: File operations.

Performs file I/O with path traversal vulnerability.
"""

import os

from app.utils.path_utils import build_path


class FileStorageAdapter:
    """File storage adapter.

    HOP 10: Performs file operations with user-controlled paths.

    VULNERABILITY: Path Traversal - User can escape upload directory.
    """

    def __init__(self):
        self.base_path = "/tmp/uploads"

    def read_file(self, filename: str) -> dict:
        """Read file contents.

        HOP 10: PATH TRAVERSAL SINK - user-controlled filename.

        Args:
            filename: TAINTED filename - path traversal vector
                      e.g., "../../etc/passwd"
        """
        # VULNERABLE: No path traversal protection
        # build_path does NOT sanitize .. sequences
        path = build_path(self.base_path, filename)  # filename is TAINTED

        try:
            with open(path, "rb") as f:  # SINK: Opening user-controlled path
                content = f.read()
                return {"filename": filename, "content": content.decode("utf-8", errors="replace")}
        except FileNotFoundError:
            return {"error": "File not found", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def write_file(self, filename: str, content: bytes) -> dict:
        """Write file contents.

        PATH TRAVERSAL SINK - writes to user-controlled path.

        Args:
            filename: TAINTED filename - path traversal vector
            content: Content to write
        """
        # VULNERABLE: No path traversal protection
        path = build_path(self.base_path, filename)  # filename is TAINTED

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:  # SINK: Writing to user-controlled path
                f.write(content)
            return {"filename": filename, "size": len(content), "status": "written"}
        except Exception as e:
            return {"error": str(e)}

    def list_files(self, directory: str) -> dict:
        """List files in directory.

        Args:
            directory: TAINTED directory path
        """
        path = build_path(self.base_path, directory)  # TAINTED
        try:
            files = os.listdir(path)  # SINK: Listing user-controlled directory
            return {"directory": directory, "files": files}
        except Exception as e:
            return {"error": str(e)}
