# Refactor Pipeline Logging Quality with Rich UI

**Status**: PROPOSAL - Awaiting Architect Approval
**Change ID**: `refactor-pipeline-logging-quality`
**Complexity**: HIGH (~400 lines added, ~200 lines deleted, 5 files)
**Breaking**: NO - Return dict unchanged, only visual output changes
**Risk Level**: HIGH - Touches core pipeline execution, parallel track coordination

---

## Why

### Problem Statement

The `aud full` pipeline output is a visual disaster. When running 25 phases across 3 parallel tracks, the console output becomes an unreadable "hotpot" of interleaved messages, duplicate status lines, and out-of-order results. This makes it impossible to understand what's happening during execution or debug failures.

### Verified Problems (6 Distinct Issues)

| # | Problem | Root Cause | Location | Evidence |
|---|---------|-----------|----------|----------|
| 1 | `[SCHEMA] Loaded 155 tables` appears 20+ times | Module-level print at import time | `schema.py:81` | Every subprocess imports schema module |
| 2 | Taint output appears AFTER "COMPLETE" message | Thread buffer flushes late from `asyncio.to_thread()` | `pipelines.py:954-1142` | `run_taint_sync()` prints to stderr, buffer flushes after gather() |
| 3 | Duplicate `[COMPLETED] Track B` messages | Both `run_chain_async` AND observer print completion | `pipelines.py:234` + `events.py:90` | Two different code paths print same event |
| 4 | Interleaved `[STATUS] Track A/B` messages | Parallel tracks print to stderr without coordination | `pipelines.py:187-190, 961-1134` | No buffering, race condition on stdout |
| 5 | `readthis/` folder still created | Zombie code not cleaned up per pipeline.md | `pipelines.py:305-306, 1547-1570` | Directory created then referenced in tips |
| 6 | Mixed observer/direct prints | Half-migrated to observer pattern | Throughout `pipelines.py` | ~100 direct print() calls alongside observer calls |

### User Impact

1. **Cannot monitor progress** - Status messages interleave making it impossible to know which track is where
2. **Cannot debug failures** - Error context lost in noise
3. **Professional appearance** - Tool looks broken/amateur despite solid functionality
4. **AI agent confusion** - When used via MCP, garbled output confuses AI interpretation

### Architectural Debt

The existing `PipelineObserver` protocol in `events.py` is a good start but:
- Only partially adopted (pipelines.py still has ~100 direct prints)
- No buffering strategy for parallel tracks
- No Rich integration for live status
- `ConsoleLogger` just wraps print() without intelligence

---

## What Changes

### Summary

| Component | Action | Lines | Risk |
|-----------|--------|-------|------|
| `theauditor/pipeline/structures.py` | CREATE | +80 | LOW |
| `theauditor/pipeline/renderer.py` | CREATE | +250 | MEDIUM |
| `theauditor/pipelines.py` | MODIFY | -200/+100 | HIGH |
| `theauditor/events.py` | MODIFY | -50/+20 | MEDIUM |
| `theauditor/indexer/schema.py` | MODIFY | -1 | LOW |
| `pyproject.toml` | MODIFY | +1 | LOW |

### High-Level Architecture

```
BEFORE (Current):
┌─────────────────────────────────────────────────────────┐
│ run_full_pipeline()                                      │
│   ├── print() ──────────────────────────────► STDOUT    │
│   ├── observer.on_log() ─► ConsoleLogger ───► STDOUT    │
│   ├── run_chain_async() ─► print() ─────────► STDERR    │
│   └── run_taint_sync() ──► print() ─────────► STDERR    │
│                                                          │
│   Result: 4 code paths racing to console = HOTPOT       │
└─────────────────────────────────────────────────────────┘

AFTER (Proposed):
┌─────────────────────────────────────────────────────────┐
│ run_full_pipeline()                                      │
│   └── RichRenderer (single authority)                    │
│         ├── Sequential stages: Live table update        │
│         ├── Parallel stages: Buffer per track           │
│         └── Completion: Atomic flush + summary          │
│                                                          │
│   Result: 1 code path, coordinated output = CLEAN       │
└─────────────────────────────────────────────────────────┘
```

### New Files

**1. `theauditor/pipeline/structures.py`** - Data contracts

```python
# The "envelope" for all pipeline results
@dataclass
class PhaseResult:
    name: str
    status: TaskStatus  # PENDING, RUNNING, SUCCESS, FAILED, SKIPPED
    elapsed: float
    stdout: str  # Captured output (not printed during execution)
    stderr: str
    exit_code: int = 0
    findings_count: int = 0

    def to_dict(self) -> dict:
        """JSON-serializable for MCP/AI consumption."""
        ...
```

**2. `theauditor/pipeline/renderer.py`** - Rich-based UI

```python
class RichRenderer(PipelineObserver):
    """Live dashboard using Rich library.

    Sequential stages: Update table row immediately
    Parallel stages: Buffer output, flush atomically when track completes
    """

    def __init__(self, quiet: bool = False, log_file: Path | None = None):
        self.live = Live(self._build_table(), refresh_per_second=4)
        self._parallel_buffers: dict[str, list[str]] = {}
        ...
```

### Modified Files

**3. `theauditor/pipelines.py`** - Core refactor

- DELETE: All direct `print()` calls (~100 instances)
- DELETE: `readthis_dir` creation (lines 305-306)
- DELETE: `readthis` file-moving logic (lines 1547-1570)
- MODIFY: `run_command_async()` - Return `PhaseResult` instead of dict
- MODIFY: `run_chain_async()` → `run_chain_silent()` - No prints, return `List[PhaseResult]`
- MODIFY: `run_taint_sync()` - Capture output to StringIO, return in PhaseResult
- MODIFY: `run_full_pipeline()` - Use `RichRenderer` exclusively

**4. `theauditor/events.py`** - Protocol update

- DELETE: `ConsoleLogger` class (replaced by `RichRenderer`)
- MODIFY: `PipelineObserver` protocol - Add `on_parallel_buffer()` method

**5. `theauditor/indexer/schema.py`** - Silence spam

- DELETE: Line 81 `print(f"[SCHEMA] Loaded {len(TABLES)} tables")`

**6. `pyproject.toml`** - Add dependency

- ADD: `rich>=13.0.0` to dependencies

---

## Impact

### Affected Specs

| Spec | Requirement | Change Type |
|------|-------------|-------------|
| `pipeline` | NEW: Console Output Rendering | ADDED |
| `pipeline` | NEW: Parallel Track Buffering | ADDED |
| `pipeline` | NEW: Rich Live Dashboard | ADDED |
| `pipeline` | Graceful Degradation on Missing Files | REMOVED (readthis cleanup) |

### Affected Code (Beyond Direct Changes)

| File | Impact | Risk |
|------|--------|------|
| `theauditor/commands/full.py` | Consumes `run_full_pipeline()` return - NO CHANGE to return structure | LOW |
| `theauditor/journal.py` | Records pipeline events - observer calls unchanged | LOW |
| Any code importing `ConsoleLogger` | BREAKING - must use `RichRenderer` | MEDIUM |

### What Does NOT Change

| Component | Why Unchanged |
|-----------|---------------|
| Return dict structure from `run_full_pipeline()` | Contract with consumers (full.py, journal.py) |
| Execution order of phases | Only presentation changes |
| Findings aggregation logic | Separate concern (refactor-pipeline-reporting) |
| Database writes | Not related to logging |
| Exit codes | Determined by findings, not presentation |

### Dependencies Added

| Package | Version | Size | Why |
|---------|---------|------|-----|
| `rich` | >=13.0.0 | ~3MB | Live dashboard, tables, progress bars |

---

## Risk Assessment

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Rich breaks Windows CP1252 | LOW | HIGH | Rich auto-detects encoding, falls back to ASCII |
| Parallel buffer memory | LOW | MEDIUM | Buffers are strings, ~100KB max per track |
| Import time regression | MEDIUM | LOW | Lazy import Rich only when needed |
| Observer contract break | LOW | HIGH | Keep Protocol interface stable, add methods |
| CI/CD non-interactive mode | MEDIUM | MEDIUM | Detect `not sys.stdout.isatty()`, use simple mode |

### Edge Cases

1. **Non-TTY output (CI/CD)**: Detect via `sys.stdout.isatty()`, fall back to simple sequential prints
2. **Windows Command Prompt**: Rich handles encoding; we already ban emojis in CLAUDE.md
3. **Keyboard interrupt during parallel**: Rich handles cleanup in `__exit__`
4. **Very long phase output**: Truncate to 50 lines in buffer, full output to log file

### Rollback Plan

1. `git revert <commit>` - Single commit with all changes
2. Remove `rich` from pyproject.toml
3. Restore `ConsoleLogger` from git history
4. Time to rollback: ~5 minutes

---

## Success Criteria

All criteria MUST pass before marking complete:

- [ ] `aud full --offline` shows live Rich table updating per phase
- [ ] Parallel track outputs appear as atomic blocks (no interleaving)
- [ ] `[SCHEMA] Loaded` message appears 0 times (was 20+)
- [ ] Taint output appears IN ORDER with its track (not after COMPLETE)
- [ ] No `[COMPLETED] Track X` duplicates
- [ ] `readthis/` folder NOT created
- [ ] CI/CD mode (non-TTY) falls back gracefully without Rich crashes
- [ ] Return dict from `run_full_pipeline()` unchanged (contract preserved)
- [ ] `--quiet` flag still suppresses output

---

## Polyglot Assessment

**This change is Python-only.** No Node/TypeScript/Rust involvement.

| Component | Language | Affected? |
|-----------|----------|-----------|
| Pipeline orchestration | Python | YES |
| Extractors (JS/TS) | Node | NO - they write to DB, don't log to pipeline |
| Schema loading | Python | YES (silence print) |
| CLI commands | Python | NO - just call run_full_pipeline() |

**No orchestrator needed** - this is a presentation-layer refactor within Python.

---

## Related Changes

| Change | Relationship |
|--------|--------------|
| `refactor-pipeline-reporting` | COMPLEMENTARY - fixes data accuracy, this fixes visual presentation |
| `refactor-extraction-zero-fallback` | INDEPENDENT - extractor internals, not pipeline logging |

---

## Approval Required

### Architect Decision Points

1. **Rich as hard dependency** - Adds ~3MB to install, but provides professional UI
2. **Delete ConsoleLogger** - Breaking change for any external code using it
3. **Readthis folder removal** - Confirms pipeline.md Phase 0 cleanup
4. **Non-TTY fallback strategy** - Simple prints vs Rich's auto-detection

---

**Next Step**: Architect reviews and approves/denies this proposal
