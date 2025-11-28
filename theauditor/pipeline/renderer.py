"""Rich-based pipeline renderer with parallel track buffering."""
import sys
from pathlib import Path
from typing import TextIO

from rich.console import Console
from rich.live import Live
from rich.table import Table

from theauditor.events import PipelineObserver
from .structures import PhaseResult, TaskStatus
from .ui import AUDITOR_THEME


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

    def _build_table(self) -> Table:
        """Build the status table."""
        table = Table(title="Pipeline Progress", expand=True)
        table.add_column("Phase", style="cyan", no_wrap=True)
        table.add_column("Status", style="green", width=12)
        table.add_column("Time", justify="right", width=8)
        return table

    def _update_table(self):
        """Rebuild table with current phase states."""
        if not self._table:
            return
        self._table = self._build_table()
        for name, info in self._phases.items():
            status = info.get('status', 'pending')
            elapsed = info.get('elapsed', 0)

            # UI TWEAK: Show 0.0s for running phases instead of -
            if status == "running" or elapsed > 0:
                time_str = f"{elapsed:.1f}s"
            else:
                time_str = "-"

            self._table.add_row(name, status, time_str)

        # CRITICAL FIX 1: Tell Live display about the new table object
        if self._live:
            self._live.update(self._table)

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
            self._table = self._build_table()
            self._live = Live(self._table, refresh_per_second=4, console=self.console)
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
        self._phases[name] = {'status': 'running', 'elapsed': 0}
        self._update_table()
        if not self._live:
            self._write(f"\n[Phase {index}/{total}] {name}")

    def on_phase_complete(self, name: str, elapsed: float) -> None:
        self._phases[name] = {'status': 'success', 'elapsed': elapsed}
        self._update_table()
        if not self._live:
            self._write(f"[OK] {name} completed in {elapsed:.1f}s")

    def on_phase_failed(self, name: str, error: str, exit_code: int) -> None:
        self._phases[name] = {'status': 'FAILED', 'elapsed': 0}
        self._update_table()
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
        self._phases[track_name] = {'status': 'running', 'elapsed': 0}
        self._update_table()

    def on_parallel_track_complete(self, track_name: str, elapsed: float) -> None:
        self._phases[track_name] = {'status': 'success', 'elapsed': elapsed}
        self._update_table()

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
