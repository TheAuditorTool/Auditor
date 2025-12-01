# Design: Logging Infrastructure Migration to Loguru (Polyglot)

## Context

TheAuditor's logging is fragmented across 6 different mechanisms with 323+ raw print statements in Python and 18 console.error() calls in TypeScript. This is a polyglot system with 5 language extractors, requiring coordinated logging across Python and TypeScript.

### Stakeholders

- **Developers**: Need filterable debug output during development
- **CI/CD Systems**: Need structured logs for aggregation
- **End Users**: Need clean output (Rich pipeline UI preserved)
- **Future Observability**: Need foundation for OpenTelemetry integration

### Constraints

1. **Windows CP1252**: Cannot use emojis (per CLAUDE.md 1.3)
2. **ZERO FALLBACK**: No try/except hiding errors (per CLAUDE.md Section 4)
3. **Rich UI Preservation**: Pipeline progress display must remain unchanged
4. **Polyglot Consistency**: Python and TypeScript must use same env vars
5. **Automation Required**: 323 Python statements too many for manual refactoring
6. **Minimal TS Dependencies**: 18 statements not worth adding pino/winston

---

## Goals / Non-Goals

### Goals

1. Single logging library for Python (Loguru)
2. Lightweight custom logger for TypeScript (no npm dependency)
3. Runtime log level control via `THEAUDITOR_LOG_LEVEL` env var (both languages)
4. JSON structured output via `THEAUDITOR_LOG_JSON=1` (both languages)
5. Automatic file rotation for Python logs
6. Automated Python migration via LibCST codemod
7. Preserve Rich pipeline UI exactly as-is

### Non-Goals

1. Changing Rich pipeline display (RichRenderer untouched)
2. Adding OpenTelemetry integration (future work)
3. Adding pino/winston to TypeScript (overhead for 18 statements)
4. Modifying Go/Rust/Bash extractors (they're Python modules)

---

## Decisions

### Decision 1: Loguru for Python

**Choice**: Use Loguru as the single Python logging library.

**Rationale**:
- Drop-in replacement for print() and logging module
- Built-in rotation, compression, retention
- Auto-detects terminal capabilities (color, encoding)
- Single import everywhere: `from loguru import logger`
- 50M+ downloads/month, battle-tested

**Alternatives Considered**:

| Alternative | Why Rejected |
|-------------|--------------|
| `structlog` | More complex API, requires more refactoring |
| `logging` (stdlib) | Already have it, doesn't solve the fragmentation |
| `rich.logging` | Only for Rich console, not general logging |
| Keep print() | Doesn't solve any problems |

**Code Pattern**:
```python
# BEFORE (current)
print(f"[TAINT] Starting analysis", file=sys.stderr)

# AFTER (loguru)
from theauditor.utils.logging import logger
logger.info("Starting analysis")
```

---

### Decision 2: Custom Logger for TypeScript (No npm Dependency)

**Choice**: Create a lightweight custom logger in TypeScript, NOT add pino/winston.

**Rationale**:
- Only 18 console.error() statements across 3 files
- Adding npm dependency for 18 statements is overkill
- Custom logger can match Python env vars exactly
- No build/bundle size increase
- No new dependency to maintain

**TypeScript Logger Implementation**:
```typescript
// theauditor/ast_extractors/javascript/src/utils/logger.ts
const LOG_LEVELS = { DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3 } as const;

const currentLevel = LOG_LEVELS[process.env.THEAUDITOR_LOG_LEVEL?.toUpperCase() as keyof typeof LOG_LEVELS] ?? LOG_LEVELS.INFO;
const jsonMode = process.env.THEAUDITOR_LOG_JSON === "1";

function formatMessage(level: string, message: string): string {
  const timestamp = new Date().toISOString().slice(11, 19);
  if (jsonMode) {
    return JSON.stringify({ time: timestamp, level, message });
  }
  return `${timestamp} | ${level.padEnd(8)} | ${message}`;
}

export const logger = {
  debug: (msg: string) => { if (currentLevel <= LOG_LEVELS.DEBUG) console.error(formatMessage("DEBUG", msg)); },
  info: (msg: string) => { if (currentLevel <= LOG_LEVELS.INFO) console.error(formatMessage("INFO", msg)); },
  warning: (msg: string) => { if (currentLevel <= LOG_LEVELS.WARNING) console.error(formatMessage("WARNING", msg)); },
  error: (msg: string) => { if (currentLevel <= LOG_LEVELS.ERROR) console.error(formatMessage("ERROR", msg)); },
};
```

**Why console.error() not console.log()**:
- TypeScript extractor writes JSON to stdout for Python to parse
- Logging MUST go to stderr to avoid corrupting JSON output
- This matches current behavior (all current logging is console.error)

---

### Decision 3: Production Migration Script (Already Written)

**Choice**: Use existing `scripts/loguru_migration.py` (847 lines) to transform all 323 Python print statements automatically.

**Script Location**: `scripts/loguru_migration.py`

**Usage**:
```bash
# Dry run - preview changes
python scripts/loguru_migration.py theauditor/ --dry-run

# Apply changes
python scripts/loguru_migration.py theauditor/

# Single file with diff
python scripts/loguru_migration.py theauditor/taint/core.py --dry-run --diff
```

**Features**:
- LibCST-based preserves formatting (comments, whitespace)
- Automatic import management (adds loguru import)
- Standalone CLI - no yaml/init required
- Dry-run mode with diff output
- Syntax validation via compile() before writing
- Multi-encoding support (utf-8, latin-1, cp1252)
- Edge case handling: end="", sep=, file=custom, eager eval protection, brace hazard

**Why not manual refactoring**:
- 323 statements across 51 files = days of tedious work
- High risk of human error in repetitive tasks
- No guarantee of consistency

---

### Decision 4: Tag-to-Level Mapping

**Choice**: Map existing `[TAG]` prefixes to appropriate log levels.

**Mapping**:

| Tag | Level | Rationale |
|-----|-------|-----------|
| `[DEBUG]`, `[INDEXER_DEBUG]`, `[TRACE]` | `debug` | Developer debugging |
| `[DEBUG JS BATCH]`, `[DEBUG JS]`, `[BATCH DEBUG]` | `debug` | TypeScript debugging |
| `[INFO]`, `[Indexer]`, `[TAINT]`, `[SCHEMA]` | `info` | Normal operation |
| `[DEDUP]` | `debug` | Internal deduplication logic |
| `[WARNING]`, `[WARN]` | `warning` | Non-fatal issues |
| `[ERROR]` | `error` | Recoverable errors |
| `[CRITICAL]`, `[FATAL]` | `critical` | Unrecoverable errors |
| No tag | `info` | Default for untagged prints |

---

### Decision 5: Preserve Rich Pipeline UI

**Choice**: Do NOT modify RichRenderer, pipeline/ui.py, or any Rich-based output.

**Rationale**:
- Rich pipeline UI was just refactored (`refactor-pipeline-logging-quality`)
- Users love the live progress table
- RichRenderer handles parallel track buffering correctly
- Loguru is for internal logging, Rich is for user-facing UI

**Boundary**:
```
┌─────────────────────────────────────────────────────────┐
│ LOGURU DOMAIN (Internal Logging - Python)               │
│  - Engine debug output                                  │
│  - Error diagnostics                                    │
│  - Trace information                                    │
│  - Goes to stderr + .pf/theauditor.log                 │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│ CUSTOM LOGGER DOMAIN (Internal Logging - TypeScript)   │
│  - Extractor debug output                              │
│  - Error diagnostics                                    │
│  - Goes to stderr only (no file in TS)                 │
└─────────────────────────────────────────────────────────┘
                          │
                          │ (separate concerns)
                          │
┌─────────────────────────────────────────────────────────┐
│ RICH DOMAIN (User-Facing UI) - UNCHANGED               │
│  - Pipeline progress table                              │
│  - Phase status updates                                 │
│  - Final summary panels                                 │
│  - Goes to stdout via Rich Console                     │
└─────────────────────────────────────────────────────────┘
```

---

### Decision 6: Debug Guard Elimination

**Choice**: Remove `if os.environ.get("THEAUDITOR_DEBUG")` guards and replace with `logger.debug()`.

**Rationale**:
- Loguru respects `THEAUDITOR_LOG_LEVEL` env var
- `logger.debug()` is no-op when level > DEBUG (zero overhead)
- Cleaner code without conditional blocks
- Consistent debug output control

**Transformation**:
```python
# BEFORE
if os.environ.get("THEAUDITOR_DEBUG"):
    print(f"[DEBUG] Processing file {idx}", file=sys.stderr)

# AFTER
logger.debug(f"Processing file {idx}")
```

---

### Decision 7: Centralized Configuration

**Choice**: Single configuration point in `theauditor/utils/logging.py`.

**Environment Variables (Shared by Python and TypeScript)**:
```
THEAUDITOR_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR  # Default: INFO
THEAUDITOR_LOG_JSON=0|1                        # Default: 0 (human-readable)
THEAUDITOR_LOG_FILE=path/to/file.log           # Optional, Python only
```

**Python Default Behavior**:
- Level: INFO (shows info, warning, error, critical)
- Output: stderr only (no file by default)
- Format: Human-readable with colors
- Rotation: 10 MB, 7 days retention (when file logging enabled)

**TypeScript Default Behavior**:
- Level: INFO
- Output: stderr only (cannot write files)
- Format: Human-readable (timestamp | level | message)
- No rotation (no file output)

---

### Decision 8: JSON Output Format

**Choice**: Same JSON format for Python and TypeScript when `THEAUDITOR_LOG_JSON=1`.

**Python (Loguru with serialize=True)**:
```json
{"time": "2025-12-01T10:30:45.123456", "level": "INFO", "message": "Processing file", "module": "orchestrator", "function": "run", "line": 123}
```

**TypeScript (Custom)**:
```json
{"time": "10:30:45", "level": "INFO", "message": "Processing file"}
```

Note: TypeScript format is simplified (no module/function/line) because the overhead of stack trace parsing is not worth it for 18 statements.

---

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Codemod misses edge case | Some prints not converted | Grep verification + manual review |
| Log level too verbose | Too much output | Default to INFO, document levels |
| Import statement placement | May not match style | LibCST auto-formats, ruff fixes rest |
| Performance overhead | Slightly slower than print | Negligible, loguru is optimized |
| TS logger too simple | Missing features | Can upgrade to pino later if needed |

---

## File Layout (Final State)

```
theauditor/
├── utils/
│   ├── logging.py              # NEW: Loguru configuration (Python)
│   └── logger.py               # DELETED: Replaced by logging.py
├── pipeline/
│   ├── renderer.py             # UNCHANGED: Rich UI
│   └── ui.py                   # UNCHANGED: Rich theme
├── taint/
│   ├── core.py                 # MODIFIED: print → logger
│   └── flow_resolver.py        # MODIFIED: print → logger
├── indexer/
│   ├── orchestrator.py         # MODIFIED: print → logger
│   └── ...
├── ast_extractors/
│   └── javascript/
│       └── src/
│           ├── utils/
│           │   └── logger.ts             # NEW: Custom TS logger
│           ├── main.ts                   # MODIFIED: console.error → logger
│           └── extractors/
│               ├── core_language.ts      # MODIFIED: console.error → logger
│               └── data_flow.ts          # MODIFIED: console.error → logger
│       (Full path: theauditor/ast_extractors/javascript/src/)
└── ...

scripts/
└── loguru_migration.py         # EXISTS: Production migration script (847 lines, standalone CLI)
```

---

## Open Questions

All resolved:

1. ~~Should we add JSON output option?~~ → YES, via THEAUDITOR_LOG_JSON=1
2. ~~Should debug guards be preserved as comments?~~ → NO, clean removal
3. ~~Should we add trace level for very verbose output?~~ → YES, for internal tracing
4. ~~Should TypeScript use pino/winston?~~ → NO, custom logger for 18 statements

---

## References

- `scripts/loguru_migration.py` - Production migration script (847 lines, standalone CLI)
- `scripts/libcst_faq.md` - LibCST best practices and patterns
- `theauditor/utils/logger.py` - Current logging facade (to be replaced)
- `theauditor/pipeline/renderer.py` - Rich UI (preserved)
- Loguru documentation: https://loguru.readthedocs.io/
- LibCST documentation: https://libcst.readthedocs.io/
