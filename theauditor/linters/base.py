"""Base classes and types for linter implementations.

This module provides the foundation for the strategy pattern used by linter classes:
- Finding: Typed dataclass for lint results
- LinterResult: Typed dataclass for linter execution results (status + findings)
- BaseLinter: Abstract base class for all linter implementations
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from theauditor.utils.logging import logger

if TYPE_CHECKING:
    from theauditor.utils.toolbox import Toolbox


LINTER_TIMEOUT = 300


LinterStatus = Literal["SUCCESS", "SKIPPED", "FAILED"]


@dataclass
class Finding:
    """Typed representation of a lint finding.

    Attributes:
        tool: Name of the linter that produced this finding (e.g., "ruff", "eslint")
        file: Relative path to the file containing the issue
        line: Line number (1-indexed)
        column: Column number (1-indexed)
        rule: Rule identifier (e.g., "E501", "no-unused-vars")
        message: Human-readable description of the issue
        severity: One of "error", "warning", or "info"
        category: Classification (e.g., "lint", "type", "security")
        additional_info: Optional tool-specific metadata
    """

    tool: str
    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: Literal["error", "warning", "info"]
    category: str
    additional_info: dict | None = field(default=None)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization and database storage.

        Returns dict matching the legacy format for backward compatibility.
        """
        result = asdict(self)
        if result["additional_info"] is None:
            del result["additional_info"]
        return result


@dataclass
class LinterResult:
    """Result of a linter execution.

    Distinguishes between "no bugs found" (SUCCESS with empty findings)
    and "linter didn't run" (SKIPPED or FAILED).

    Attributes:
        tool: Name of the linter
        status: One of SUCCESS, SKIPPED, or FAILED
        findings: List of Finding objects (empty if SKIPPED/FAILED)
        duration: Execution time in seconds
        error_message: Explanation if SKIPPED or FAILED
    """

    tool: str
    status: LinterStatus
    findings: list[Finding]
    duration: float
    error_message: str | None = None

    @classmethod
    def success(cls, tool: str, findings: list[Finding], duration: float) -> LinterResult:
        """Create a SUCCESS result."""
        return cls(tool=tool, status="SUCCESS", findings=findings, duration=duration)

    @classmethod
    def skipped(cls, tool: str, reason: str) -> LinterResult:
        """Create a SKIPPED result (tool not installed, config missing, etc.)."""
        return cls(tool=tool, status="SKIPPED", findings=[], duration=0.0, error_message=reason)

    @classmethod
    def failed(cls, tool: str, error: str, duration: float = 0.0) -> LinterResult:
        """Create a FAILED result (timeout, crash, invalid output)."""
        return cls(tool=tool, status="FAILED", findings=[], duration=duration, error_message=error)


class BaseLinter(ABC):
    """Abstract base class for linter implementations.

    Each linter subclass handles a specific tool (Ruff, ESLint, Mypy, etc.)
    and implements the async run() method to execute the linter and parse output.

    Attributes:
        toolbox: Toolbox instance for path resolution
        root: Project root directory
    """

    def __init__(self, toolbox: Toolbox, root: Path):
        """Initialize linter with toolbox and project root.

        Args:
            toolbox: Toolbox instance for resolving binary and config paths
            root: Project root directory (all file paths are relative to this)
        """
        self.toolbox = toolbox
        self.root = Path(root).resolve()

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the linter name for logging and Finding.tool field."""
        ...

    @abstractmethod
    async def run(self, files: list[str]) -> LinterResult:
        """Run linter on files and return result with status.

        Args:
            files: List of file paths (relative to project root) to lint

        Returns:
            LinterResult with status (SUCCESS/SKIPPED/FAILED) and findings
        """
        ...

    def _normalize_path(self, path: str) -> str:
        """Normalize path to forward slashes and make relative to project root.

        Extracted from linters.py:454-473 for shared use across all linters.

        Args:
            path: File path from linter output (may be absolute or relative)

        Returns:
            Normalized path with forward slashes, relative to project root
        """
        path = path.replace("\\", "/")

        try:
            abs_path = Path(path)
            if abs_path.is_absolute():
                rel_path = abs_path.relative_to(self.root)

                if ".." in str(rel_path):
                    logger.warning(f"Path escapes root directory: {path}")
                    return path

                return str(rel_path).replace("\\", "/")
        except ValueError:
            pass
        except OSError as e:
            logger.warning(f"Path normalization failed for {path}: {e}")

        return path

    async def _run_command(
        self,
        cmd: list[str],
        *,
        cwd: Path | None = None,
        timeout: int = LINTER_TIMEOUT,
        capture_stderr: bool = True,
    ) -> tuple[int, str, str]:
        """Execute a subprocess command asynchronously.

        Provides a standardized way to run external linter binaries with
        proper timeout handling and output capture.

        Args:
            cmd: Command and arguments to execute
            cwd: Working directory (defaults to project root)
            timeout: Timeout in seconds (default: LINTER_TIMEOUT)
            capture_stderr: Whether to capture stderr (default: True)

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            asyncio.TimeoutError: If command exceeds timeout
        """
        work_dir = cwd or self.root

        logger.debug(f"[{self.name}] Running: {' '.join(cmd[:3])}...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE if capture_stderr else asyncio.subprocess.DEVNULL,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error(f"[{self.name}] Command timed out after {timeout}s")
            raise

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        return proc.returncode or 0, stdout, stderr
