"""Data contracts for pipeline execution."""
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(Enum):
    """Status of a pipeline phase."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseResult:
    """Result of a single pipeline phase execution.

    Provides strongly-typed return value instead of loose dicts.
    JSON-serializable for MCP/AI consumption.
    """
    name: str
    status: TaskStatus
    elapsed: float
    stdout: str
    stderr: str
    exit_code: int = 0
    findings_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d['status'] = self.status.value
        return d

    @property
    def success(self) -> bool:
        """True if phase completed successfully."""
        return self.status == TaskStatus.SUCCESS


@dataclass
class PipelineContext:
    """Context for pipeline execution.

    Encapsulates configuration that flows through the pipeline.
    """
    root: Path
    offline: bool = False
    quiet: bool = False
    index_only: bool = False
    exclude_self: bool = False
