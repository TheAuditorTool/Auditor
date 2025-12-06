# Design: Pipeline Logging Quality with Rich UI

## Context

TheAuditor's `aud full` command runs 25 phases across 4 stages, with Stage 3 executing 3 parallel tracks. The current implementation has multiple code paths writing to stdout/stderr simultaneously, resulting in interleaved, unreadable output.

### Stakeholders

- **End Users**: Need clear progress indication during 2+ minute pipeline runs
- **AI Agents**: Need structured output for MCP integration
- **CI/CD Systems**: Need non-interactive fallback without crashes
- **Developers**: Need debuggable output when things fail

### Constraints

1. **Windows CP1252**: Cannot use emojis (per CLAUDE.md 1.3)
2. **ZERO FALLBACK**: No try/except hiding errors (per CLAUDE.md Section 4)
3. **Return Contract**: Must preserve `run_full_pipeline()` return dict structure
4. **Backward Compat**: `--quiet` flag must still work

---

## Goals / Non-Goals

### Goals

1. Single code path for all console output (RichRenderer)
2. Live dashboard showing phase progress during execution
3. Atomic output blocks for parallel tracks (no interleaving)
4. Clean fallback for non-TTY environments (CI/CD)
5. JSON-serializable PhaseResult for future MCP integration

### Non-Goals

1. Changing execution order or logic of phases
2. Fixing findings aggregation (separate `refactor-pipeline-reporting` change)
3. Adding new CLI flags beyond existing `--quiet`
4. Persisting Rich output to log files (log files remain plain text)

---

## Decisions

### Decision 1: Rich Library for Live Dashboard

**Choice**: Use Rich library with `Live` context manager for real-time table updates.

**Rationale**:
- Rich is battle-tested (30M+ downloads/month)
- Auto-detects terminal capabilities (TTY, encoding, width)
- Handles Windows console correctly
- Single dependency, no transitive bloat

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|--------------|
| Manual ANSI codes | Fragile, Windows issues, reinventing wheel |
| `tqdm` | Progress bars only, no tables/structured output |
| `blessed`/`curses` | Overkill for our use case, complex API |
| Plain text only | Doesn't solve the core UX problem |

**Code Pattern**:
```python
from rich.live import Live
from rich.table import Table

class RichRenderer:
    def __init__(self):
        self.table = Table(title="Pipeline Progress")
        self.table.add_column("Phase", style="cyan")
        self.table.add_column("Status", style="green")
        self.table.add_column("Time", justify="right")

    def run(self):
        with Live(self.table, refresh_per_second=4):
            # Updates to self.table are reflected live
            yield  # Pipeline runs here
```

---

### Decision 2: Buffer & Flush Strategy for Parallel Tracks

**Choice**: Buffer all parallel track output in memory, flush atomically when track completes.

**Rationale**:
- Parallel tracks CANNOT coordinate stdout access without locking
- Buffering is simpler and more robust than locks
- Memory cost is minimal (~100KB per track max)
- User sees complete track results, not fragments

**Implementation**:
```python
class RichRenderer:
    def __init__(self):
        self._parallel_buffers: dict[str, list[str]] = {}

    def on_parallel_track_start(self, track_name: str):
        """Start buffering for this track."""
        self._parallel_buffers[track_name] = []

    def buffer_parallel_output(self, track_name: str, line: str):
        """Add line to track's buffer (not printed yet)."""
        self._parallel_buffers[track_name].append(line)

    def on_parallel_track_complete(self, track_name: str, elapsed: float):
        """Flush entire buffer atomically."""
        buffer = self._parallel_buffers.pop(track_name, [])
        # Print all lines at once - no interleaving possible
        for line in buffer:
            self._write(line)
```

**Visual Flow**:
```
Stage 3 Execution:
  t=0:   Track A starts (buffer created)
  t=0:   Track B starts (buffer created)
  t=1:   Track A logs "Step 1" → buffer["A"].append()
  t=1:   Track B logs "Step 1" → buffer["B"].append()
  t=2:   Track A logs "Step 2" → buffer["A"].append()
  t=3:   Track B completes → FLUSH buffer["B"] atomically
  t=5:   Track A completes → FLUSH buffer["A"] atomically

Console sees:
  [Stage 3 header]
  --- Track B Complete ---
  Step 1
  Step 2
  (no interleaving)
  --- Track A Complete ---
  Step 1
  Step 2
  (clean separation)
```

---

### Decision 3: PhaseResult Data Class

**Choice**: Strongly-typed dataclass instead of loose dicts.

**Rationale**:
- Current code passes `{"success": True, "stdout": ...}` dicts everywhere
- Easy to forget keys, hard to validate
- PhaseResult enforces structure at compile time
- JSON-serializable for future MCP/AI consumption

**Structure**:
```python
from dataclasses import dataclass, asdict
from enum import Enum

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

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        d = asdict(self)
        d['status'] = self.status.value
        return d

    @property
    def success(self) -> bool:
        return self.status == TaskStatus.SUCCESS
```

---

### Decision 4: Silence Taint's Direct Prints

**Choice**: Redirect stdout/stderr to StringIO during `run_taint_sync()` execution.

**Rationale**:
- `run_taint_sync()` has ~30 `print(..., file=sys.stderr)` calls
- Rewriting all to use observer would be invasive and error-prone
- `contextlib.redirect_stdout/stderr` captures without code changes
- Captured output goes into PhaseResult.stdout for buffered display

**Implementation**:
```python
import io
import contextlib

def run_taint_sync() -> PhaseResult:
    """Run taint analysis with captured output."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with contextlib.redirect_stdout(stdout_capture), \
         contextlib.redirect_stderr(stderr_capture):
        # All print() calls inside here go to StringIO
        # ... existing taint logic unchanged ...

    return PhaseResult(
        name="Taint Analysis",
        status=TaskStatus.SUCCESS,
        elapsed=elapsed,
        stdout=stdout_capture.getvalue(),
        stderr=stderr_capture.getvalue(),
    )
```

**Why not rewrite print() calls?**
- `run_taint_sync()` is 190 lines with complex control flow
- 30+ print statements scattered throughout
- Capture approach is non-invasive and guaranteed complete

---

### Decision 5: Non-TTY Fallback Mode

**Choice**: Detect non-TTY environment and use simple sequential prints instead of Rich Live.

**Rationale**:
- CI/CD systems often have non-TTY stdout
- Rich's Live mode can misbehave without TTY
- Simple fallback ensures universal compatibility

**Detection**:
```python
import sys

class RichRenderer:
    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.is_tty = sys.stdout.isatty()

        if self.is_tty and not quiet:
            # Full Rich experience
            self.live = Live(self._build_table(), refresh_per_second=4)
        else:
            # Simple mode - no Live, just prints
            self.live = None

    def _write(self, text: str):
        if self.quiet:
            return
        if self.live:
            # Rich handles it
            self.console.print(text)
        else:
            # Fallback to plain print
            print(text, flush=True)
```

---

### Decision 6: Delete ConsoleLogger

**Choice**: Remove `ConsoleLogger` from `events.py` entirely.

**Rationale**:
- `ConsoleLogger` is just `print()` with extra steps
- `RichRenderer` replaces it completely
- No known external consumers of `ConsoleLogger`
- Keeping both creates confusion about which to use

**Migration**:
```python
# BEFORE (events.py)
class ConsoleLogger:  # DELETE THIS
    def on_log(self, message: str, is_error: bool = False):
        print(msg, file=sys.stderr if is_error else sys.stdout)

# AFTER (renderer.py)
class RichRenderer(PipelineObserver):
    def on_log(self, message: str, is_error: bool = False):
        if self._in_parallel_mode:
            self.buffer_parallel_output(self._current_track, message)
        else:
            self._write(message, is_error=is_error)
```

---

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rich import time | +50ms startup | Lazy import only when running full pipeline |
| Memory for buffers | ~100KB per track | Acceptable, tracks limited to 3 |
| Breaking ConsoleLogger users | External code breaks | Document migration, no known external users |
| Windows encoding issues | Garbled output | Rich auto-detects, we already ban emojis |

---

## Migration Plan

### Step-by-Step

1. **Phase 0**: Delete zombie code (readthis, schema print)
2. **Phase 1**: Add structures.py with PhaseResult
3. **Phase 2**: Add renderer.py with RichRenderer
4. **Phase 3**: Refactor run_command_async → return PhaseResult
5. **Phase 4**: Refactor run_chain_async → silent mode
6. **Phase 5**: Wrap run_taint_sync with redirect
7. **Phase 6**: Wire RichRenderer into run_full_pipeline
8. **Phase 7**: Delete ConsoleLogger, direct prints

### Rollback

Single commit with all changes. Rollback = `git revert <commit>`.

---

## File Layout (Final State)

```
theauditor/
├── pipeline/                    # NEW PACKAGE
│   ├── __init__.py
│   ├── structures.py           # PhaseResult, TaskStatus, PipelineContext
│   └── renderer.py             # RichRenderer implementing PipelineObserver
├── events.py                    # PipelineObserver protocol (ConsoleLogger deleted)
├── pipelines.py                 # Refactored to use RichRenderer
└── indexer/
    └── schema.py               # Line 81 print deleted
```

---

## Open Questions

1. **Should `--verbose` flag show unbuffered parallel output?** (Current: No, always buffer)
2. **Should Rich table persist after completion or clear?** (Current: Persists for review)
3. **Should we add `--no-rich` flag for explicit fallback?** (Current: Auto-detect TTY)

---

## Visual Mockup

### During Execution (Stage 3)

```
============================================================
[STAGE 3] HEAVY PARALLEL ANALYSIS
============================================================

+----------------------------+----------+--------+
| Phase                      | Status   | Time   |
+----------------------------+----------+--------+
| Track A: Taint Analysis    | Running  | 12.3s  |
| Track B: Static Analysis   | Step 3/8 | 45.2s  |
| Track C: Network I/O       | Skipped  |   -    |
+----------------------------+----------+--------+

[Live updating, no flickering]
```

### After Stage 3 Completion

```
============================================================
[STAGE 3 RESULTS]
============================================================

--- Track A: Taint Analysis (1.5s) ---
[TAINT] Initializing security analysis infrastructure...
[TAINT] Found 0 infrastructure issues
[TAINT] Registry now has 265 sinks, 763 sources
[TAINT] Total vulnerabilities found: 0

--- Track B: Static Analysis (61.5s) ---
[OK] 3. Scan dependencies for vulnerabilities (12.5s)
[OK] 8. Detect patterns (41.3s)
  Found 343 files to scan...
  Processing 245 files with AST analysis...
[OK] 15. Analyze graph (1.3s)
...

============================================================
[STAGE 4] FINAL AGGREGATION
============================================================
```

---

## References

- `theauditor/pipelines.py` - Core pipeline implementation
- `theauditor/events.py` - Current PipelineObserver protocol
- `pipeline.md` (project root) - Original analysis document
- Rich documentation: https://rich.readthedocs.io/en/stable/live.html
