"""Admin service - HOP 3: Business logic for admin operations.

Handles file operations with path traversal vulnerabilities.
"""

from app.processors.data_transformer import DataTransformer


class AdminService:
    """Admin business logic service.

    HOP 3: Receives tainted file paths from admin routes.
    """

    def __init__(self):
        self.transformer = DataTransformer()

    async def read_file(self, filename: str) -> dict:
        """Read a file by filename.

        HOP 3: Passes tainted filename to processor.

        Args:
            filename: TAINTED - path traversal vector

        VULNERABILITY: Path Traversal (10 hops)
        """
        return self.transformer.prepare_file_read(filename)

    async def read_log(self, logfile: str) -> dict:
        """Read a log file.

        Args:
            logfile: TAINTED - path traversal vector
        """
        return self.transformer.prepare_file_read(logfile)

    async def create_backup(self, destination: str) -> dict:
        """Create backup to destination.

        Args:
            destination: TAINTED - path traversal vector
        """
        return self.transformer.prepare_backup(destination)
