"""Event system for pipeline observers."""

from typing import Protocol


class PipelineObserver(Protocol):
    """Observer interface for pipeline events."""

    def on_phase_start(self, name: str, index: int, total: int) -> None:
        """Called when a phase begins."""
        ...

    def on_phase_complete(self, name: str, elapsed: float) -> None:
        """Called when a phase succeeds."""
        ...

    def on_phase_failed(self, name: str, error: str, exit_code: int) -> None:
        """Called when a phase fails."""
        ...

    def on_stage_start(self, stage_name: str, stage_num: int) -> None:
        """Called when a logical stage (1-4) begins."""
        ...

    def on_log(self, message: str, is_error: bool = False) -> None:
        """Called for generic log messages (e.g., from sub-tools)."""
        ...

    def on_parallel_track_start(self, track_name: str) -> None:
        """Called when a parallel track (A/B/C) starts."""
        ...

    def on_parallel_track_complete(self, track_name: str, elapsed: float) -> None:
        """Called when a parallel track finishes."""
        ...
