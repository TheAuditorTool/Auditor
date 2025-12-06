"""Code snippet manager for reading source code lines with LRU caching."""

from collections import OrderedDict
from pathlib import Path

from theauditor.utils.logging import logger


class CodeSnippetManager:
    """Read source code lines with LRU caching and safety limits."""

    MAX_FILE_SIZE = 1_000_000
    MAX_CACHE_SIZE = 20
    MAX_SNIPPET_LINES = 15
    MAX_LINE_LENGTH = 120

    def __init__(self, root_dir: Path):
        """Initialize snippet manager."""
        self.root_dir = Path(root_dir)
        self._cache: OrderedDict[str, list[str]] = OrderedDict()

    def get_snippet(self, file_path: str, line: int, expand_block: bool = True) -> str:
        """Get code snippet for a line with optional block expansion."""
        lines = self._get_file_lines(file_path)

        if lines is None:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                return "[File not found on disk]"
            try:
                size = full_path.stat().st_size
                if size > self.MAX_FILE_SIZE:
                    return "[File too large to preview]"
            except OSError:
                pass
            return "[Binary file - no preview]"

        start_idx = line - 1
        if start_idx < 0 or start_idx >= len(lines):
            return f"[Line {line} out of range (file has {len(lines)} lines)]"

        end_idx = self._expand_block(lines, start_idx) if expand_block else start_idx

        return self._format_snippet(lines, start_idx, end_idx)

    def get_lines(self, file_path: str, start_line: int, end_line: int) -> str:
        """Get specific range of lines without block expansion."""
        lines = self._get_file_lines(file_path)

        if lines is None:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                return "[File not found on disk]"
            return "[Could not read file]"

        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines) - 1, end_line - 1)

        if start_idx > end_idx or start_idx >= len(lines):
            return f"[Lines {start_line}-{end_line} out of range]"

        if end_idx - start_idx + 1 > self.MAX_SNIPPET_LINES:
            end_idx = start_idx + self.MAX_SNIPPET_LINES - 1

        return self._format_snippet(lines, start_idx, end_idx)

    def _get_file_lines(self, file_path: str) -> list[str] | None:
        """Load file into cache, return lines or None on error."""

        cache_key = str(file_path).replace("\\", "/")

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        full_path = self.root_dir / file_path

        if not full_path.exists():
            logger.debug(f"File not found: {full_path}")
            return None

        try:
            if full_path.stat().st_size > self.MAX_FILE_SIZE:
                logger.debug(f"File too large: {full_path}")
                return None
        except OSError as e:
            logger.debug(f"Cannot stat file {full_path}: {e}")
            return None

        try:
            with open(full_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            logger.debug(f"Cannot read file {full_path}: {e}")
            return None

        lines = [line.rstrip("\n\r") for line in lines]

        if len(self._cache) >= self.MAX_CACHE_SIZE:
            self._cache.popitem(last=False)
        self._cache[cache_key] = lines

        return lines

    def _expand_block(self, lines: list[str], start_idx: int) -> int:
        """Expand from start_idx to include indented block, max 15 lines."""
        if start_idx >= len(lines):
            return start_idx

        start_line = lines[start_idx]
        start_indent = len(start_line) - len(start_line.lstrip())

        stripped = start_line.rstrip()
        is_block_start = stripped.endswith(("{", ":", "(", "["))

        end_idx = start_idx
        max_end = min(start_idx + self.MAX_SNIPPET_LINES, len(lines))

        for i in range(start_idx + 1, max_end):
            line = lines[i]

            if not line.strip():
                end_idx = i
                continue

            curr_indent = len(line) - len(line.lstrip())
            stripped_line = line.strip()

            if is_block_start:
                if curr_indent <= start_indent:
                    if stripped_line.startswith(
                        ("}", "]", ")", "end", "else", "elif", "except", "finally", "case")
                    ):
                        return i
                    return end_idx
                end_idx = i
            else:
                if curr_indent < start_indent:
                    return end_idx
                if curr_indent == start_indent and not stripped_line.startswith((".", ",", "+")):
                    return end_idx
                end_idx = i

        return end_idx

    def _format_snippet(self, lines: list[str], start_idx: int, end_idx: int) -> str:
        """Format lines with line numbers."""
        result = []

        max_line_num = end_idx + 1
        padding = len(str(max_line_num))

        for i in range(start_idx, end_idx + 1):
            line_num = i + 1
            line_content = lines[i]

            if len(line_content) > self.MAX_LINE_LENGTH:
                line_content = line_content[: self.MAX_LINE_LENGTH - 3] + "..."

            result.append(f"{line_num:>{padding}} | {line_content}")

        return "\n".join(result)

    def clear_cache(self):
        """Clear the file cache."""
        self._cache.clear()

    def cache_stats(self) -> dict:
        """Return cache statistics."""
        return {
            "cached_files": len(self._cache),
            "max_size": self.MAX_CACHE_SIZE,
            "files": list(self._cache.keys()),
        }
