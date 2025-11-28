"""Rich-based pipeline renderer with parallel track buffering."""
import sys
import time
from pathlib import Path
from typing import TextIO

from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.table import Table

from theauditor.events import PipelineObserver
from .structures import PhaseResult, TaskStatus
from .ui import AUDITOR_THEME


class DynamicTable:
    """Wrapper that builds a fresh table on each Rich render cycle.

    This enables live timer updates - Rich calls __rich_console__ on each
    refresh (4x/second), and we recalculate elapsed times dynamically.
    """

    def __init__(self, renderer: "RichRenderer"):
        self.renderer = renderer

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """Called by Rich on each refresh - return fresh table with live timers."""
        yield self.renderer._build_live_table()


class RichRenderer(PipelineObserver):
    """Live dashboard using Rich library.

    Sequential stages: Update table row immediately
    Parallel stages: Buffer output, flush atomically when track completes
    """

    def __init__(self, quiet: bool = False, log_file: Path | None = None):
        self.quiet = quiet
        self.log_file: TextIO | None = None
        if log_file:
            # Open with strict buffering to ensure logs are written immediately
            self.log_file = open(log_file, 'w', encoding='utf-8', buffering=1)

        self.is_tty = sys.stdout.isatty()
        # Own console for Live display, but shared theme for consistency
        self.console = Console(theme=AUDITOR_THEME, force_terminal=self.is_tty)

        # Parallel track buffering
        self._parallel_buffers: dict[str, list[str]] = {}
        self._in_parallel_mode = False
        self._current_track: str | None = None

        # Phase tracking for table
        self._phases: dict[str, dict] = {}
        self._current_phase: int = 0
        self._total_phases: int = 0

        # Live context (only in TTY mode)
        self._live: Live | None = None
        self._table: Table | None = None

    def _build_live_table(self) -> Table:
        """Build fresh table with current elapsed times (called on each refresh)."""
        table = Table(title="Pipeline Progress", expand=True)
        table.add_column("Phase", style="cyan", no_wrap=True)
        table.add_column("Status", style="green", width=12)
        table.add_column("Time", justify="right", width=8)

        now = time.time()
        for name, info in self._phases.items():
            status = info.get('status', 'pending')

            # Calculate elapsed: live calc for running, stored value for completed
            if status == "running":
                start_time = info.get('start_time', now)
                elapsed = now - start_time
                time_str = f"{elapsed:.1f}s"
            elif info.get('elapsed', 0) > 0:
                time_str = f"{info['elapsed']:.1f}s"
            else:
                time_str = "-"

            table.add_row(name, status, time_str)

        return table

    # Buffer truncation limit per spec requirement
    MAX_BUFFER_LINES = 50

    def _write(self, text: str, is_error: bool = False):
        """Central output handler."""
        if self.quiet and not is_error:
            return

        # Log file always gets output (no truncation - full record)
        if self.log_file:
            self.log_file.write(text + "\n")
            self.log_file.flush()

        # Console output logic
        if self._in_parallel_mode and self._current_track:
            # PARALLEL MODE: Buffer output
            buffer = self._parallel_buffers.get(self._current_track)
            if buffer is not None:
                if len(buffer) < self.MAX_BUFFER_LINES:
                    buffer.append(text)
                elif len(buffer) == self.MAX_BUFFER_LINES:
                    buffer.append("... [truncated, see .pf/pipeline.log for full output]")
                # else: already truncated, skip
        elif self._live:
            # CRITICAL FIX 2 (Live Mode): Print ABOVE the table using Live's console
            # This ensures logs/headers appear while table persists at bottom
            style = "bold red" if is_error else None
            self._live.console.print(text, style=style)
        else:
            # FALLBACK MODE: Direct print (Non-TTY)
            print(text, file=sys.stderr if is_error else sys.stdout, flush=True)

    def start(self):
        """Start the live display (call before pipeline runs)."""
        if self.is_tty and not self.quiet:
            # Use DynamicTable wrapper - Rich calls __rich_console__ on each refresh
            # This rebuilds the table with live elapsed times (ticking timer!)
            dynamic_table = DynamicTable(self)
            self._live = Live(dynamic_table, refresh_per_second=4, console=self.console)
            self._live.__enter__()

    def stop(self):
        """Stop the live display (call after pipeline completes)."""
        if self._live:
            self._live.__exit__(None, None, None)
            self._live = None
        if self.log_file:
            self.log_file.close()

    # PipelineObserver implementation

    def on_stage_start(self, stage_name: str, stage_num: int) -> None:
        header = f"\n{'=' * 60}\n[STAGE {stage_num}] {stage_name}\n{'=' * 60}"
        self._write(header)

    def on_phase_start(self, name: str, index: int, total: int) -> None:
        self._current_phase = index
        self._total_phases = total
        self._phases[name] = {'status': 'running', 'start_time': time.time()}
        # DynamicTable auto-refreshes - no manual update needed
        if not self._live:
            self._write(f"\n[Phase {index}/{total}] {name}")

    def on_phase_complete(self, name: str, elapsed: float) -> None:
        self._phases[name] = {'status': 'success', 'elapsed': elapsed}
        # DynamicTable auto-refreshes - no manual update needed
        if not self._live:
            self._write(f"[OK] {name} completed in {elapsed:.1f}s")

    def on_phase_failed(self, name: str, error: str, exit_code: int) -> None:
        self._phases[name] = {'status': 'FAILED', 'elapsed': 0}
        # DynamicTable auto-refreshes - no manual update needed
        self._write(f"[FAILED] {name} (exit code {exit_code})", is_error=True)
        if error:
            truncated = error[:200] + "..." if len(error) > 200 else error
            self._write(f"  Error: {truncated}", is_error=True)

    def on_log(self, message: str, is_error: bool = False) -> None:
        self._write(str(message) if message else "", is_error=is_error)

    def on_parallel_track_start(self, track_name: str) -> None:
        self._in_parallel_mode = True
        self._current_track = track_name
        self._parallel_buffers[track_name] = []
        self._phases[track_name] = {'status': 'running', 'start_time': time.time()}
        # DynamicTable auto-refreshes - no manual update needed

    def on_parallel_track_complete(self, track_name: str, elapsed: float) -> None:
        self._phases[track_name] = {'status': 'success', 'elapsed': elapsed}
        # DynamicTable auto-refreshes - no manual update needed

        # Flush buffer atomically
        buffer = self._parallel_buffers.pop(track_name, [])
        if buffer:
            header = f"\n{'=' * 60}\n[{track_name}] Complete ({elapsed:.1f}s)\n{'=' * 60}"

            if self._live:
                # CRITICAL FIX 3 (Ghost Pipeline): Print ABOVE the table seamlessy
                # DO NOT stop/start the Live display
                self._live.console.print(header)
                for line in buffer:
                    self._live.console.print(line)
            else:
                # FALLBACK: Standard print
                print(header, flush=True)
                for line in buffer:
                    print(line, flush=True)

        # Clear parallel mode if no more tracks
        if not self._parallel_buffers:
            self._in_parallel_mode = False
            self._current_track = None

    def print_summary(self, results: list[PhaseResult]):
        """Print final summary after pipeline completion."""
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success

        self._write(f"\n{'=' * 60}")
        if failed == 0:
            self._write(f"[OK] AUDIT COMPLETE - All {total} phases successful")
        else:
            self._write(f"[WARN] AUDIT COMPLETE - {failed} phases failed")
        self._write('=' * 60)
