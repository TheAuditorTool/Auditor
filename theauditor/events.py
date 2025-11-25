"""Event system for pipeline observers.

Decouples pipeline execution from presentation logic.
Adheres to ZERO FALLBACK POLICY: Observers must handle their own exceptions.
"""

import sys
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


class ConsoleLogger:
    """ASCII-safe console logger (Windows CP1252 compatible).

    This is the DEFAULT observer. It replicates the original 'print' behavior
    exactly, ensuring no visual regression.
    """

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def on_phase_start(self, name: str, index: int, total: int) -> None:
        if not self.quiet:
            print(f"\n[Phase {index}/{total}] {name}", flush=True)

    def on_phase_complete(self, name: str, elapsed: float) -> None:
        if not self.quiet:
            print(f"[OK] {name} completed in {elapsed:.1f}s", flush=True)

    def on_phase_failed(self, name: str, error: str, exit_code: int) -> None:
        # Errors print even in quiet mode
        print(f"[FAILED] {name} failed (exit code {exit_code})", file=sys.stderr, flush=True)
        if error:
            # Clean up error message for display
            display_err = error.strip()[:200]
            if len(error) > 200:
                display_err += "..."
            print(f"  Error: {display_err}", file=sys.stderr, flush=True)

    def on_stage_start(self, stage_name: str, stage_num: int) -> None:
        if not self.quiet:
            print("\n" + "="*60, flush=True)
            print(f"[STAGE {stage_num}] {stage_name}", flush=True)
            print("="*60, flush=True)

    def on_log(self, message: str, is_error: bool = False) -> None:
        if not self.quiet or is_error:
            # Avoid printing raw None
            msg = str(message) if message is not None else ""
            print(msg, file=sys.stderr if is_error else sys.stdout, flush=True)

    def on_parallel_track_start(self, track_name: str) -> None:
        if not self.quiet:
            try:
                print(f"[START] {track_name}...", flush=True)
            except OSError:
                pass  # Windows console buffer issue - ignore

    def on_parallel_track_complete(self, track_name: str, elapsed: float) -> None:
        if not self.quiet:
            try:
                print(f"[COMPLETED] {track_name} ({elapsed:.1f}s)", flush=True)
            except OSError:
                pass  # Windows console buffer issue - ignore
