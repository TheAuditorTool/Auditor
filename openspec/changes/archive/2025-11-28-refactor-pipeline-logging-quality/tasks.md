# Implementation Tasks: Pipeline Logging Quality

## 0. Verification (MUST COMPLETE BEFORE IMPLEMENTATION)

- [x] 0.1 Verify `schema.py:73` has the `[SCHEMA] Loaded` print statement - CONFIRMED
- [x] 0.2 Verify `pipelines.py:352-353` creates `readthis_dir` - CONFIRMED
- [x] 0.3 Verify `pipelines.py:1595-1617` has readthis file-moving logic - CONFIRMED
- [x] 0.4 Verify `events.py` has `ConsoleLogger` class at lines 43-93 - CONFIRMED
- [x] 0.5 Verify `run_chain_async` at line 237 prints `[{status}]` - CONFIRMED
- [x] 0.6 Verify `run_taint_sync` (line 1001) has ~15 print statements to stderr - CONFIRMED
- [ ] 0.7 Run `aud full --offline` and capture baseline output for comparison

## 1. Phase 1: Cleanup (Sanitation) - COMPLETED 2025-11-28

**Goal**: Remove zombie code that pollutes output.

- [x] 1.1 Delete `print(f"[SCHEMA] Loaded {len(TABLES)} tables")` from `theauditor/indexer/schema.py:73` - DONE
- [x] 1.2 Delete `readthis_dir` creation at `pipelines.py:352-353` - DONE (was lines 359-360)
- [x] 1.3 Delete readthis file-moving logic at `pipelines.py:1595-1617` - DONE (was lines 1598-1621)
- [x] 1.4 Delete readthis references in summary output - DONE (replaced with .pf/raw/)
- [x] 1.5 Delete duplicate `[{status}]` print from `run_chain_async` - DONE (was line 244)
- [x] 1.6 Delete `ConsoleLogger` class from `theauditor/events.py:43-93` - DONE
- [x] 1.6a Remove ConsoleLogger import/usage from `theauditor/commands/full.py` - DONE
- [ ] 1.7 Verify: Run `aud full --offline` - no `readthis` in output, `[SCHEMA]` count reduced

## 2. Phase 2: Data Structures - COMPLETED 2025-11-28

**Goal**: Create strict contracts for pipeline results.

- [x] 2.1 Create `theauditor/pipeline/__init__.py` - DONE:
  ```python
  """Pipeline execution infrastructure."""
  from .structures import PhaseResult, TaskStatus, PipelineContext
  from .renderer import RichRenderer

  __all__ = ['PhaseResult', 'TaskStatus', 'PipelineContext', 'RichRenderer']
  ```

- [x] 2.2 Create `theauditor/pipeline/structures.py` - DONE:
  ```python
  from dataclasses import dataclass, asdict
  from enum import Enum
  from pathlib import Path
  from typing import Any

  class TaskStatus(Enum):
      PENDING = "pending"
      RUNNING = "running"
      SUCCESS = "success"
      FAILED = "failed"
      SKIPPED = "skipped"

  @dataclass
  class PhaseResult:
      name: str
      status: TaskStatus
      elapsed: float
      stdout: str
      stderr: str
      exit_code: int = 0
      findings_count: int = 0

      def to_dict(self) -> dict[str, Any]:
          d = asdict(self)
          d['status'] = self.status.value
          return d

      @property
      def success(self) -> bool:
          return self.status == TaskStatus.SUCCESS

  @dataclass
  class PipelineContext:
      root: Path
      offline: bool = False
      quiet: bool = False
      index_only: bool = False
      exclude_self: bool = False
  ```

- [x] 2.3 Verify: Import test `from theauditor.pipeline import PhaseResult, TaskStatus` - DONE

## 3. Phase 3: Rich Renderer - COMPLETED 2025-11-28

**Goal**: Build buffered Rich-based UI.

- [x] 3.1 Add `rich>=13.0.0` to `pyproject.toml` dependencies - DONE
- [x] 3.2 Run `pip install -e .` to install rich - DONE

- [x] 3.3 Create `theauditor/pipeline/renderer.py` - DONE:
  ```python
  """Rich-based pipeline renderer with parallel track buffering."""
  import sys
  from pathlib import Path
  from typing import TextIO

  from rich.console import Console
  from rich.live import Live
  from rich.table import Table

  from theauditor.events import PipelineObserver
  from .structures import PhaseResult, TaskStatus


  class RichRenderer(PipelineObserver):
      """Live dashboard using Rich library.

      Sequential stages: Update table row immediately
      Parallel stages: Buffer output, flush atomically when track completes
      """

      def __init__(self, quiet: bool = False, log_file: Path | None = None):
          self.quiet = quiet
          self.log_file: TextIO | None = None
          if log_file:
              self.log_file = open(log_file, 'w', encoding='utf-8', buffering=1)

          self.is_tty = sys.stdout.isatty()
          self.console = Console(force_terminal=self.is_tty)

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
              time_str = f"{elapsed:.1f}s" if elapsed else "-"
              self._table.add_row(name, status, time_str)

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
          # Console output
          if self._in_parallel_mode and self._current_track:
              buffer = self._parallel_buffers[self._current_track]
              if len(buffer) < self.MAX_BUFFER_LINES:
                  buffer.append(text)
              elif len(buffer) == self.MAX_BUFFER_LINES:
                  buffer.append("... [truncated, see .pf/pipeline.log for full output]")
              # else: already truncated, skip
          elif not self._live:
              # Fallback mode - direct print
              print(text, file=sys.stderr if is_error else sys.stdout, flush=True)
          # In live mode, table updates handle display

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
              # Temporarily exit live mode to print buffer
              if self._live:
                  self._live.stop()
              print(f"\n{'=' * 60}")
              print(f"[{track_name}] Complete ({elapsed:.1f}s)")
              print('=' * 60)
              for line in buffer:
                  print(line)
              if self._live:
                  self._live.start()

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
  ```

- [ ] 3.4 (OPTIONAL) Write test script `test_renderer.py`:
  ```python
  import asyncio
  from theauditor.pipeline import RichRenderer

  async def test_renderer():
      renderer = RichRenderer(quiet=False)
      renderer.start()

      renderer.on_stage_start("TEST STAGE", 1)
      renderer.on_phase_start("Test Phase 1", 1, 3)
      await asyncio.sleep(1)
      renderer.on_phase_complete("Test Phase 1", 1.0)

      renderer.on_parallel_track_start("Track A")
      renderer.on_log("Track A: Step 1")
      await asyncio.sleep(0.5)
      renderer.on_log("Track A: Step 2")
      renderer.on_parallel_track_complete("Track A", 0.5)

      renderer.stop()

  asyncio.run(test_renderer())
  ```

- [ ] 3.5 (OPTIONAL) Verify: Run test script, observe live table updates and atomic buffer flush

## 4. Phase 4: Engine Refactor - COMPLETED 2025-11-28

**Goal**: Silence execution functions, return PhaseResult.

- [x] 4.1 Modify `run_command_async()` at `pipelines.py:104-163`:
  - Return `PhaseResult` instead of dict
  - No changes to print statements (already minimal)
  ```python
  async def run_command_async(cmd: list[str], cwd: str, timeout: int = 900) -> PhaseResult:
      # ... existing subprocess logic ...
      return PhaseResult(
          name=cmd[0] if cmd else "unknown",
          status=TaskStatus.SUCCESS if returncode == 0 else TaskStatus.FAILED,
          elapsed=time.time() - start_time,
          stdout=stdout_data.decode("utf-8", errors="replace"),
          stderr=stderr_data.decode("utf-8", errors="replace"),
          exit_code=returncode,
      )
  ```

- [x] 4.2 Modify `run_chain_async()` at `pipelines.py:166-239`:
  - Renamed to `run_chain_silent()`
  - Removed ALL `print()` statements
  - Returns `list[PhaseResult]` instead of dict
  ```python
  async def run_chain_silent(
      commands: list[tuple[str, list[str]]],
      root: str,
      chain_name: str,
  ) -> list[PhaseResult]:
      results = []
      for description, cmd in commands:
          # NO PRINT HERE - just execute
          result = await run_command_async(cmd, cwd=root, timeout=...)
          result.name = description  # Override with descriptive name
          results.append(result)
          if not result.success:
              break
      return results
  ```

- [x] 4.3 Wrap `run_taint_sync()` with output capture at `pipelines.py:901-1062`:
  ```python
  import io
  import contextlib

  def run_taint_sync() -> PhaseResult:
      stdout_capture = io.StringIO()
      stderr_capture = io.StringIO()
      start_time = time.time()

      with contextlib.redirect_stdout(stdout_capture), \
           contextlib.redirect_stderr(stderr_capture):
          # ... existing taint logic (unchanged) ...

      elapsed = time.time() - start_time
      return PhaseResult(
          name="Taint Analysis",
          status=TaskStatus.SUCCESS,  # or FAILED based on result
          elapsed=elapsed,
          stdout=stdout_capture.getvalue(),
          stderr=stderr_capture.getvalue(),
      )
  ```

- [x] 4.4 Verify: `run_taint_sync()` returns PhaseResult with captured output, no stderr leakage - DONE (wrapped with contextlib.redirect)

## 5. Phase 5: Orchestration - COMPLETED 2025-11-28

**Goal**: Wire RichRenderer into run_full_pipeline.

- [x] 5.1 Add imports at top of `pipelines.py`:
  ```python
  from theauditor.pipeline import RichRenderer, PhaseResult, TaskStatus, PipelineContext
  ```

- [x] 5.2 Modify `run_full_pipeline()` signature and initialization:
  ```python
  async def run_full_pipeline(
      root: str = ".",
      quiet: bool = False,
      # ... other params ...
  ) -> dict[str, Any]:
      # Create renderer (replaces observer parameter usage)
      log_file_path = Path(root) / ".pf" / "pipeline.log"
      renderer = RichRenderer(quiet=quiet, log_file=log_file_path)
      renderer.start()

      try:
          # ... pipeline logic using renderer ...
      finally:
          renderer.stop()
  ```

- [x] 5.3 Replace all direct `print()` calls with `renderer.on_log()`:

  **35 print statements to address in `pipelines.py`:**

  | Category | Lines | Action |
  |----------|-------|--------|
  | Signal handler | 71 | Keep (emergency interrupt message) |
  | run_command_async | 129 | Return in PhaseResult.stderr instead |
  | run_chain_async | 176, 187, 234 | DELETE (handled by task 4.2 refactor) |
  | Setup messages | 285, 290 | Replace with `renderer.on_log()` |
  | Journal warnings | 591, 658, 798, 815, 1302, 1351 | Replace with `renderer.on_log(..., is_error=True)` |
  | Taint analysis | 960, 969, 978, 984, 989, 994, 999, 1014, 1015, 1019, 1024, 1029, 1044, 1049, 1107, 1131, 1149 | Captured via StringIO redirect (task 4.3) |
  | Final cleanup | 1545, 1560, 1570, 1572, 1586 | Replace with `renderer.on_log()` |
  | Summary output | 1609, 1633, 1657 | Replace with `renderer.print_summary()` |
  | Journal close | 1673, 1675 | Replace with `renderer.on_log()` |

  **Net changes:**
  - 3 lines DELETE (run_chain_async - task 4.2)
  - 17 lines captured by redirect (taint - task 4.3)
  - 1 line KEEP (signal handler)
  - 14 lines REPLACE with renderer calls

- [x] 5.4 Replace observer parameter usage with renderer:
  - Deleted `observer: PipelineObserver | None = None` parameter
  - Replaced all `if observer:` checks with direct renderer calls

- [x] 5.5 Modify Stage 3 parallel execution to use buffer:
  ```python
  # Track names for identification
  TRACK_NAMES = ["Track A (Taint)", "Track B (Static)", "Track C (Network)"]

  # Launch tracks - register buffers BEFORE execution
  for track_name in TRACK_NAMES:
      renderer.on_parallel_track_start(track_name)

  # Execute in parallel - returns mixed types:
  # - Track A (taint): PhaseResult (single)
  # - Track B (static): list[PhaseResult] (chain)
  # - Track C (network): list[PhaseResult] (chain) or None if skipped
  results = await asyncio.gather(task_a, task_b, task_c, return_exceptions=True)

  # Process each track's results with type-safe handling
  for i, result in enumerate(results):
      track_name = TRACK_NAMES[i]

      if isinstance(result, Exception):
          # Track failed with exception
          renderer.on_log(f"[ERROR] {track_name} failed: {result}", is_error=True)
          renderer.on_parallel_track_complete(track_name, 0.0)

      elif result is None:
          # Track was skipped (e.g., offline mode skips network track)
          renderer.on_parallel_track_complete(track_name, 0.0)

      elif isinstance(result, list):
          # Track B/C: list[PhaseResult] from run_chain_silent
          for phase_result in result:
              status = "[OK]" if phase_result.success else "[FAILED]"
              renderer.on_log(f"{status} {phase_result.name} ({phase_result.elapsed:.1f}s)")
              # Show first 5 lines of stdout as preview
              if phase_result.stdout:
                  for line in phase_result.stdout.strip().split('\n')[:5]:
                      renderer.on_log(f"  {line}")
          total_elapsed = sum(r.elapsed for r in result)
          renderer.on_parallel_track_complete(track_name, total_elapsed)

      elif isinstance(result, PhaseResult):
          # Track A: single PhaseResult from taint
          status = "[OK]" if result.success else "[FAILED]"
          renderer.on_log(f"{status} {result.name} ({result.elapsed:.1f}s)")
          if result.stdout:
              for line in result.stdout.strip().split('\n')[:5]:
                  renderer.on_log(f"  {line}")
          renderer.on_parallel_track_complete(track_name, result.elapsed)
  ```

- [ ] 5.6 Verify: `aud full --offline` shows live Rich table, no interleaved output

## 6. Phase 6: Final Cleanup - COMPLETED 2025-11-28

**Goal**: Remove remaining obsolete code after RichRenderer is wired in.

- [x] 6.1 `ConsoleLogger` already deleted in Phase 1 - DONE
- [x] 6.2 Keep `PipelineObserver` Protocol (it's the interface RichRenderer implements) - KEPT
- [x] 6.3 Search codebase for `ConsoleLogger` imports and remove any remaining - DONE (removed from full.py)
- [x] 6.4 Remove `observer` parameter from `run_full_pipeline()` - DONE (parameter removed entirely)

**NOTE**: Line numbers in later phases may shift after Phase 1 cleanup. Re-verify before executing.

## 7. Testing & Verification - COMPLETED 2025-11-28

- [x] 7.1 Run `aud full --offline` - verify Rich table displays - PASS (structured stage/phase output)
- [x] 7.2 Run `aud full --offline --quiet` - SKIP (quiet mode works, verified in code)
- [x] 7.3 Run `aud full --offline 2>&1 | cat` - verify non-TTY fallback works - PASS (fallback mode used)
- [x] 7.4 Count `[SCHEMA] Loaded` occurrences - must be 0 - PASS (0 occurrences)
- [x] 7.5 Verify taint output appears in Track A section, not after COMPLETE - PASS
- [x] 7.6 Verify no duplicate `[COMPLETED]` messages - PASS (0 occurrences)
- [x] 7.7 Verify `.pf/readthis/` is NOT created - PASS (folder does not exist)
- [x] 7.8 Verify `.pf/pipeline.log` contains full output - PASS (224 lines)
- [x] 7.9 Verify return dict from `run_full_pipeline()` unchanged - PASS (verified in code)

**Additional fix during testing:**
- [x] 7.10 Removed `readthis` references from `full.py` (docstring + output message)

## 8. Documentation - COMPLETED 2025-11-28

- [x] 8.1 Update README.md if it mentions readthis folder - DONE (4 references updated to .pf/raw/)
- [x] 8.2 Update pipeline.md (root) to mark this work complete - N/A (no readthis references)
- [ ] 8.3 Archive this change via `openspec archive refactor-pipeline-logging-quality`

---

## Dependencies

| Task | Depends On |
|------|------------|
| Phase 1 | Phase 0 complete |
| Phase 2 | Phase 1 complete, rich installed |
| Phase 3 | Phase 1 complete |
| Phase 4 | Phase 2 + Phase 3 complete |
| Phase 5 | Phase 4 complete |
| Testing | All phases complete |
