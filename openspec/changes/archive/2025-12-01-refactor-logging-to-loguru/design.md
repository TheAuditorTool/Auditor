# Design: Logging Infrastructure Migration to Loguru + Pino (Polyglot)

## Context

TheAuditor's logging is fragmented across 6 different mechanisms with 323+ raw print statements in Python and 18 console.error() calls in TypeScript. This is a polyglot system with 5 language extractors, requiring coordinated logging across Python and TypeScript with unified output format.

### Stakeholders

- **Developers**: Need filterable debug output during development
- **CI/CD Systems**: Need structured logs for aggregation
- **End Users**: Need clean output (Rich pipeline UI preserved)
- **Future Observability**: Need foundation for OpenTelemetry integration

### Constraints

1. **Windows CP1252**: Cannot use emojis (per CLAUDE.md 1.3)
2. **ZERO FALLBACK**: No try/except hiding errors (per CLAUDE.md Section 4)
3. **Rich UI Preservation**: Pipeline progress display must remain unchanged
4. **Polyglot Consistency**: Python and TypeScript must use same env vars AND same JSON format
5. **Automation Required**: 323 Python statements too many for manual refactoring
6. **Industry Standard for TS**: Use Pino, not custom logger (18 statements still warrant proper tooling)

---

## Goals / Non-Goals

### Goals

1. Single logging library for Python (Loguru 0.7.3)
2. Industry-standard logging for TypeScript (Pino 10.1.0)
3. **Unified NDJSON format** - Both languages output identical JSON structure
4. Runtime log level control via `THEAUDITOR_LOG_LEVEL` env var (both languages)
5. JSON structured output via `THEAUDITOR_LOG_JSON=1` (both languages)
6. **Cross-language correlation** via `THEAUDITOR_REQUEST_ID`
7. Automatic file rotation for Python logs
8. Automated Python migration via LibCST 1.8.6 codemod
9. Preserve Rich pipeline UI exactly as-is
10. Developer experience via `pino-pretty` for human-readable logs

### Non-Goals

1. Changing Rich pipeline display (RichRenderer untouched)
2. Adding OpenTelemetry integration (future work)
3. Custom TypeScript logger (replaced by Pino - industry standard)
4. Modifying Go/Rust/Bash extractors (they're Python modules)

---

## Decisions

### Decision 1: Loguru 0.7.3 for Python

**Choice**: Use Loguru 0.7.3 (exact version) as the single Python logging library.

**Rationale**:
- Drop-in replacement for print() and logging module
- Built-in rotation, compression, retention
- Auto-detects terminal capabilities (color, encoding)
- Single import everywhere: `from loguru import logger`
- 50M+ downloads/month, battle-tested
- Version 0.7.3 is latest stable, tested with our migration script

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

# AFTER (loguru with Pino-compatible sink)
from theauditor.utils.logging import logger
logger.info("Starting analysis")
# Output: {"level":30,"time":1715629847123,"msg":"Starting analysis","pid":12345}
```

---

### Decision 2: Pino 10.1.0 for TypeScript

**Choice**: Use Pino 10.1.0 (industry standard) for TypeScript logging.

**Rationale**:
- Pino is the spiritual equivalent of Loguru in Node.js
- Industry standard for fast, JSON-native logging
- 10M+ weekly downloads, battle-tested in production
- Native NDJSON output compatible with log aggregators
- Child logger pattern for correlation ID threading
- `pino-pretty` for developer experience
- Version 10.1.0 is latest stable

**Why NOT a custom logger**:
- Even 18 statements warrant proper tooling
- Custom logger requires maintenance
- Pino is faster, more reliable, better tested
- Child logger pattern solves REQUEST_ID threading elegantly
- pino-pretty provides instant DX improvement

**TypeScript Logger Implementation**:
```typescript
// theauditor/ast_extractors/javascript/src/utils/logger.ts
import pino from "pino";

// Pino level mapping (matches Python numeric levels)
const LOG_LEVELS: Record<string, string> = {
  DEBUG: "debug",    // 20
  INFO: "info",      // 30
  WARNING: "warn",   // 40
  ERROR: "error",    // 50
};

// Get level from env, default to info
const envLevel = process.env.THEAUDITOR_LOG_LEVEL?.toUpperCase() || "INFO";
const pinoLevel = LOG_LEVELS[envLevel] || "info";

// Create base logger
const baseLogger = pino({
  level: pinoLevel,
  // Pino default format is already NDJSON - no configuration needed
  // Output goes to stderr to preserve stdout for JSON data
  transport: undefined, // Raw JSON to stderr
});

// Bind REQUEST_ID from environment (passed by Python orchestrator)
export const logger = baseLogger.child({
  request_id: process.env.THEAUDITOR_REQUEST_ID || "unknown",
});

// Re-export for convenience
export default logger;
```

**Why console.error() underneath**:
- TypeScript extractor writes JSON to stdout for Python to parse
- Logging MUST go to stderr to avoid corrupting JSON output
- Pino defaults to stdout, we configure destination to stderr

---

### Decision 3: Unified NDJSON Format (Pino-Compatible)

**Choice**: Make Loguru output Pino-compatible JSON so both languages produce identical format.

**Rationale**:
- Single format for log aggregation systems
- Enables unified viewing via `pino-pretty`
- Simpler tooling (one parser, one schema)
- Easier correlation across languages

**Unified Format**:
```json
{"level":30,"time":1715629847123,"msg":"Processing file","pid":12345,"request_id":"abc-123"}
```

| Field | Type | Python (Loguru) | TypeScript (Pino) |
|-------|------|-----------------|-------------------|
| `level` | int | Custom sink maps level | Native Pino format |
| `time` | int | Epoch milliseconds | Native Pino format |
| `msg` | string | Custom sink renames `message` | Native Pino format |
| `pid` | int | `record["process"].id` | Native Pino format |
| `request_id` | string | From context | From child logger |

**Python Pino-Compatible Sink**:
```python
# theauditor/utils/logging.py
import json
import os
import sys
from loguru import logger

# Pino level mapping
PINO_LEVELS = {
    "TRACE": 10,
    "DEBUG": 20,
    "INFO": 30,
    "WARNING": 40,
    "ERROR": 50,
    "CRITICAL": 60,
}

def pino_compatible_sink(message):
    """Format log records as Pino-compatible NDJSON."""
    record = message.record

    pino_log = {
        "level": PINO_LEVELS.get(record["level"].name, 30),
        "time": int(record["time"].timestamp() * 1000),
        "msg": record["message"],
        "pid": record["process"].id,
    }

    # Add request_id if present in context
    if "request_id" in record["extra"]:
        pino_log["request_id"] = record["extra"]["request_id"]

    # Add any extra context fields
    for key, value in record["extra"].items():
        if key != "request_id":
            pino_log[key] = value

    # Add exception info if present
    if record["exception"]:
        pino_log["err"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else "Error",
            "message": str(record["exception"].value) if record["exception"].value else "",
        }

    print(json.dumps(pino_log), file=sys.stderr)
```

---

### Decision 4: REQUEST_ID Correlation Threading

**Choice**: Pass correlation ID from Python to TypeScript via `THEAUDITOR_REQUEST_ID` environment variable.

**Rationale**:
- TypeScript extractor runs as subprocess from Python orchestrator
- Environment variables are the cleanest subprocess communication method
- No need to parse command line arguments
- Works with any subprocess spawning method

**Python Side (Orchestrator)**:
```python
import os
import uuid
from loguru import logger

# Generate or retrieve request ID
request_id = os.environ.get("THEAUDITOR_REQUEST_ID") or str(uuid.uuid4())

# Bind to logger context
with logger.contextualize(request_id=request_id):
    logger.info("Starting TypeScript extraction")

    # Pass to subprocess
    env = os.environ.copy()
    env["THEAUDITOR_REQUEST_ID"] = request_id

    subprocess.run(["node", "extractor.js"], env=env)
```

**TypeScript Side (Extractor)**:
```typescript
import { logger } from "./utils/logger";

// logger already has request_id bound from environment
logger.info("Processing file");
// Output includes: "request_id": "abc-123-..."
```

---

### Decision 5: Production Migration Script (Already Written)

**Choice**: Use existing `scripts/loguru_migration.py` (847 lines) with LibCST 1.8.6 to transform all 323 Python print statements automatically.

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
- LibCST 1.8.6 based - preserves formatting (comments, whitespace)
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

### Decision 6: Tag-to-Level Mapping

**Choice**: Map existing `[TAG]` prefixes to appropriate log levels.

**Mapping**:

| Tag | Level | Pino Numeric | Rationale |
|-----|-------|--------------|-----------|
| `[DEBUG]`, `[INDEXER_DEBUG]`, `[TRACE]` | `debug` | 20 | Developer debugging |
| `[DEBUG JS BATCH]`, `[DEBUG JS]`, `[BATCH DEBUG]` | `debug` | 20 | TypeScript debugging |
| `[INFO]`, `[Indexer]`, `[TAINT]`, `[SCHEMA]` | `info` | 30 | Normal operation |
| `[DEDUP]` | `debug` | 20 | Internal deduplication logic |
| `[WARNING]`, `[WARN]` | `warning` | 40 | Non-fatal issues |
| `[ERROR]` | `error` | 50 | Recoverable errors |
| `[CRITICAL]`, `[FATAL]` | `critical` | 60 | Unrecoverable errors |
| No tag | `info` | 30 | Default for untagged prints |

---

### Decision 7: Preserve Rich Pipeline UI

**Choice**: Do NOT modify RichRenderer, pipeline/ui.py, or any Rich-based output.

**Rationale**:
- Rich pipeline UI was just refactored (`refactor-pipeline-logging-quality`)
- Users love the live progress table
- RichRenderer handles parallel track buffering correctly
- Loguru/Pino are for internal logging, Rich is for user-facing UI

**Boundary**:
```
+-------------------------------------------------------------+
| LOGURU DOMAIN (Internal Logging - Python)                   |
|  - Engine debug output                                      |
|  - Error diagnostics                                        |
|  - Trace information                                        |
|  - Goes to stderr + .pf/theauditor.log                     |
|  - Format: NDJSON (Pino-compatible)                         |
+-------------------------------------------------------------+
                          |
+-------------------------------------------------------------+
| PINO DOMAIN (Internal Logging - TypeScript)                 |
|  - Extractor debug output                                   |
|  - Error diagnostics                                        |
|  - Goes to stderr only (no file in TS)                     |
|  - Format: NDJSON (native Pino)                             |
+-------------------------------------------------------------+
                          |
                          | (separate concerns)
                          |
+-------------------------------------------------------------+
| RICH DOMAIN (User-Facing UI) - UNCHANGED                    |
|  - Pipeline progress table                                  |
|  - Phase status updates                                     |
|  - Final summary panels                                     |
|  - Goes to stdout via Rich Console                         |
+-------------------------------------------------------------+
```

---

### Decision 8: Debug Guard Elimination

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

### Decision 9: Centralized Configuration

**Choice**: Single configuration point in `theauditor/utils/logging.py` for Python, `src/utils/logger.ts` for TypeScript.

**Environment Variables (Shared by Python and TypeScript)**:
```
THEAUDITOR_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR  # Default: INFO
THEAUDITOR_LOG_JSON=0|1                        # Default: 0 (human-readable)
THEAUDITOR_LOG_FILE=path/to/file.log           # Optional, Python only
THEAUDITOR_REQUEST_ID=uuid                     # Auto-generated if not set
```

**Python Default Behavior**:
- Level: INFO (shows info, warning, error, critical)
- Output: stderr only (no file by default)
- Format: NDJSON when JSON mode, human-readable with colors otherwise
- Rotation: 10 MB, 7 days retention (when file logging enabled)

**TypeScript Default Behavior**:
- Level: INFO
- Output: stderr only (cannot write files, preserves stdout for data)
- Format: NDJSON always (Pino native format)
- No rotation (no file output)

---

### Decision 10: pino-pretty for Developer Experience

**Choice**: Add `pino-pretty` as dev dependency for human-readable log viewing.

**Rationale**:
- NDJSON is great for machines, terrible for humans
- pino-pretty parses NDJSON and outputs colorful, readable logs
- Works with BOTH Python (Loguru Pino sink) and TypeScript (Pino) output
- Single tool for unified log viewing during development

**Usage**:
```bash
# View logs from Python
aud full --index 2>&1 | npx pino-pretty

# View logs from TypeScript extractor
node extractor.js 2>&1 | npx pino-pretty

# View unified logs from both
(python orchestrator.py 2>&1 & node extractor.js 2>&1) | npx pino-pretty
```

---

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Codemod misses edge case | Some prints not converted | Grep verification + manual review |
| Log level too verbose | Too much output | Default to INFO, document levels |
| Import statement placement | May not match style | LibCST auto-formats, ruff fixes rest |
| Performance overhead | Slightly slower than print | Negligible, both Loguru and Pino are optimized |
| Pino adds npm dependency | Larger node_modules | ~150KB, worth it for proper logging |
| NDJSON format differences | Format mismatch between languages | Pino-compatible sink ensures identical output |

---

## File Layout (Final State)

```
theauditor/
+-- utils/
|   +-- logging.py              # NEW: Loguru config with Pino-compatible sink
|   +-- logger.py               # DELETED: Replaced by logging.py
+-- pipeline/
|   +-- renderer.py             # UNCHANGED: Rich UI
|   +-- ui.py                   # UNCHANGED: Rich theme
+-- taint/
|   +-- core.py                 # MODIFIED: print -> logger
|   +-- flow_resolver.py        # MODIFIED: print -> logger
+-- indexer/
|   +-- orchestrator.py         # MODIFIED: print -> logger, REQUEST_ID threading
|   +-- ...
+-- ast_extractors/
|   +-- javascript/
|       +-- package.json        # MODIFIED: +pino@10.1.0, +pino-pretty (dev)
|       +-- src/
|           +-- utils/
|           |   +-- logger.ts   # NEW: Pino logger with REQUEST_ID binding
|           +-- main.ts         # MODIFIED: console.error -> logger
|           +-- extractors/
|               +-- core_language.ts  # MODIFIED: console.error -> logger
|               +-- data_flow.ts      # MODIFIED: console.error -> logger
+-- ...

scripts/
+-- loguru_migration.py         # EXISTS: Production migration script (847 lines)

pyproject.toml                  # MODIFIED: +loguru==0.7.3, +libcst==1.8.6 (dev)
```

---

## Open Questions

All resolved:

1. ~~Should we add JSON output option?~~ -> YES, via THEAUDITOR_LOG_JSON=1
2. ~~Should debug guards be preserved as comments?~~ -> NO, clean removal
3. ~~Should we add trace level for very verbose output?~~ -> YES, for internal tracing
4. ~~Should TypeScript use pino/winston?~~ -> YES, Pino 10.1.0 (industry standard)
5. ~~Should we use custom TypeScript logger?~~ -> NO, Pino is the right choice
6. ~~How to correlate logs across languages?~~ -> THEAUDITOR_REQUEST_ID env var

---

## References

- `scripts/loguru_migration.py` - Production migration script (847 lines, LibCST 1.8.6)
- `scripts/libcst_faq.md` - LibCST best practices and patterns
- `theauditor/utils/logger.py` - Current logging facade (to be replaced)
- `theauditor/pipeline/renderer.py` - Rich UI (preserved)
- Loguru documentation: https://loguru.readthedocs.io/
- LibCST documentation: https://libcst.readthedocs.io/
- Pino documentation: https://getpino.io/
- pino-pretty: https://github.com/pinojs/pino-pretty
