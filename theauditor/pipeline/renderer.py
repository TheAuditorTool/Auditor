"""Rich-based pipeline renderer with parallel track buffering."""

import re
import sys
import time
from pathlib import Path
from typing import TextIO

from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.table import Table
from rich.text import Text

from theauditor.utils.logging import logger, restore_stderr_sink, swap_to_rich_sink

from .events import PipelineObserver
from .structures import PhaseResult
from .ui import console as shared_console

_NUMBER_COLORIZE_RE = re.compile(r"(?<!\x1b\[)(\d+)(?!\d*m)")


class DynamicTable:
    """Wrapper that builds a fresh table on each Rich render cycle."""

    def __init__(self, renderer: RichRenderer):
        self.renderer = renderer

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """Called by Rich on each refresh - return fresh table with live timers."""
        yield self.renderer._build_live_table()


class RichRenderer(PipelineObserver):
    """Live dashboard using Rich library."""

    def __init__(self, quiet: bool = False, log_file: Path | None = None):
        self.quiet = quiet
        self.log_file: TextIO | None = None
        if log_file:
            self.log_file = open(log_file, "w", encoding="utf-8", buffering=1)  # noqa: SIM115

        self.is_tty = sys.stdout.isatty()

        self.console = shared_console

        self._parallel_buffers: dict[str, list[str]] = {}
        self._in_parallel_mode = False
        self._current_track: str | None = None

        self._phases: dict[str, dict] = {}
        self._current_phase: int = 0
        self._total_phases: int = 0

        self._live: Live | None = None
        self._table: Table | None = None

        self._pipeline_start_time: float | None = None

        self._loguru_handler_id: int | None = None

    def _build_live_table(self) -> Table:
        """Build fresh table with current elapsed times (called on each refresh)."""
        table = Table(title="Pipeline Progress", expand=True)
        table.add_column("Phase", style="cyan", no_wrap=True)
        table.add_column("Status", style="green", width=12)
        table.add_column("Time", justify="right", width=8)

        now = time.time()
        for name, info in self._phases.items():
            status = info.get("status", "pending")

            if status == "running":
                start_time = info.get("start_time", now)
                elapsed = now - start_time
                time_str = f"{elapsed:.1f}s"
            elif info.get("elapsed", 0) > 0:
                time_str = f"{info['elapsed']:.1f}s"
            else:
                time_str = "-"

            table.add_row(name, status, time_str)

        if self._pipeline_start_time:
            total_elapsed = now - self._pipeline_start_time
            table.add_section()
            table.add_row("[bold]Total[/bold]", "", f"[bold]{total_elapsed:.1f}s[/bold]")

        return table

    MAX_BUFFER_LINES = 50

    def _write(self, text: str, is_error: bool = False):
        """Central output handler."""
        if self.quiet and not is_error:
            return

        if self.log_file:
            self.log_file.write(text + "\n")
            self.log_file.flush()

        if self._in_parallel_mode and self._current_track:
            buffer = self._parallel_buffers.get(self._current_track)
            if buffer is not None:
                if len(buffer) < self.MAX_BUFFER_LINES:
                    buffer.append(text)
                elif len(buffer) == self.MAX_BUFFER_LINES:
                    buffer.append("... [truncated, see .pf/pipeline.log for full output]")

        else:
            try:
                plain_text = Text.from_markup(text).plain
            except Exception:
                plain_text = text

            if is_error:
                logger.error(plain_text)
            else:
                logger.info(plain_text)

    def log_message(self, message):
        """Loguru sink that routes logs through Rich console safely.

        This is the bridge between loguru and Rich Live display.
        When Live is active, logs appear ABOVE the live table.
        When Live is inactive, logs go directly to console.

        Usage:
            logger.add(renderer.log_message, format="{message}", level="INFO")
        """

        text = str(message).rstrip("\n")

        if self.quiet:
            return

        if " - " in text:
            prefix, msg = text.split(" - ", 1)

            msg = _NUMBER_COLORIZE_RE.sub(lambda m: f"\x1b[36m{m.group(1)}\x1b[0m", msg)
            text = f"{prefix} - {msg}"

        rich_text = Text.from_ansi(text)

        if self._live:
            self._live.console.print(rich_text)
        else:
            self.console.print(rich_text)

    def start(self):
        """Start the live display (call before pipeline runs)."""
        self._pipeline_start_time = time.time()
        if self.is_tty and not self.quiet:
            dynamic_table = DynamicTable(self)
            self._live = Live(dynamic_table, refresh_per_second=4, console=self.console)
            self._live.__enter__()

            self._loguru_handler_id = swap_to_rich_sink(self.log_message)

    def stop(self):
        """Stop the live display (call after pipeline completes)."""
        if self._live:
            self._live.__exit__(None, None, None)
            self._live = None

            restore_stderr_sink(self._loguru_handler_id)
            self._loguru_handler_id = None

        if self.log_file:
            self.log_file.close()

    def on_stage_start(self, stage_name: str, stage_num: int) -> None:
        self._write("")
        self._write(
            f"[bold magenta]Stage {stage_num}[/bold magenta]  [bold cyan]{stage_name}[/bold cyan]"
        )

    def on_phase_start(self, name: str, index: int, total: int) -> None:
        self._current_phase = index
        self._total_phases = total
        self._phases[name] = {"status": "running", "start_time": time.time()}

        if not self._live:
            self._write(f"\n[Phase {index}/{total}] {name}")

    def on_phase_complete(self, name: str, elapsed: float) -> None:
        self._phases[name] = {"status": "success", "elapsed": elapsed}

        if not self._live:
            self._write(f"[green]OK[/green]  {name}  [dim]{elapsed:.1f}s[/dim]")

    def on_phase_failed(self, name: str, error: str, exit_code: int) -> None:
        self._phases[name] = {"status": "FAILED", "elapsed": 0}

        self._write(
            f"[bold red]FAILED[/bold red]  {name}  [dim]exit {exit_code}[/dim]", is_error=True
        )
        if error:
            truncated = error[:200] + "..." if len(error) > 200 else error
            self._write(f"  Error: {truncated}", is_error=True)

    def on_log(self, message: str, is_error: bool = False) -> None:
        self._write(str(message) if message else "", is_error=is_error)

    def on_parallel_track_start(self, track_name: str) -> None:
        self._in_parallel_mode = True
        self._current_track = track_name
        self._parallel_buffers[track_name] = []
        self._phases[track_name] = {"status": "running", "start_time": time.time()}

    def on_parallel_track_complete(self, track_name: str, elapsed: float) -> None:
        self._phases[track_name] = {"status": "success", "elapsed": elapsed}

        self._parallel_buffers.pop(track_name, None)

        if not self._parallel_buffers:
            self._in_parallel_mode = False
            self._current_track = None

    def print_summary(self, results: list[PhaseResult]):
        """Print final summary after pipeline completion."""
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success

        total_time = ""
        if self._pipeline_start_time:
            elapsed = time.time() - self._pipeline_start_time
            total_time = f"[dim]{elapsed:.1f}s[/dim]"

        self._write("")
        if failed == 0:
            self._write(
                f"[bold green]AUDIT COMPLETE[/bold green]  All {total} phases successful  {total_time}"
            )
        else:
            self._write(
                f"[bold yellow]AUDIT COMPLETE[/bold yellow]  {failed} phases failed  {total_time}"
            )
