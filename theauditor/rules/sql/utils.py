"""SQL rules shared utilities."""

import re
from sqlite3 import Connection


def register_regexp(conn: Connection) -> None:
    """Register REGEXP function for SQLite connection.

    SQLite doesn't have built-in REGEXP support. This registers a Python
    function to handle REGEXP queries in SQL rule checks.
    """

    def _regexp(pattern: str, value: str | None) -> bool:
        if value is None:
            return False
        try:
            return re.search(pattern, value, re.IGNORECASE) is not None
        except re.error:
            return False

    conn.create_function("REGEXP", 2, _regexp)


def truncate(text: str, max_len: int = 100) -> str:
    """Truncate text with ellipsis if too long.

    Args:
        text: Text to truncate
        max_len: Maximum length before truncation

    Returns:
        Original text or truncated with "..." suffix
    """
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
