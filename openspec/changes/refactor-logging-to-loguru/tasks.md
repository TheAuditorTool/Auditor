# Implementation Tasks: Logging Migration to Loguru + Pino (Polyglot)

**IMPORTANT**: READ `specs/logging/spec.md` before implementing EACH language phase.

---

## 0. Verification (MUST COMPLETE BEFORE IMPLEMENTATION)

- [ ] 0.1 Verify `theauditor/utils/logger.py` exists and has ~24 lines
- [ ] 0.2 Count Python print statements: `grep -r "print.*\[" theauditor/ | wc -l` (expect ~323)
- [ ] 0.3 Count Python files with prints: `grep -rl "print.*\[" theauditor/ | wc -l` (expect ~51)
- [ ] 0.4 Count TypeScript console statements: `grep -r "console\." javascript/src/ | wc -l` (expect ~18)
- [ ] 0.5 Verify `theauditor/pipeline/renderer.py` exists (must NOT modify)
- [ ] 0.6 Verify `theauditor/pipeline/ui.py` exists (must NOT modify)
- [ ] 0.7 Run `aud full --index` and capture baseline output for comparison
- [ ] 0.8 Verify libcst 1.8.6 is available: `pip install libcst==1.8.6`
- [ ] 0.9 Verify `scripts/loguru_migration.py` exists (847 lines)

---

## PHASE 1: Python Infrastructure Setup

**READ**: specs/logging/spec.md "Python Requirements" before starting.

### 1.1 Add Dependencies

- [ ] 1.1.1 Add `loguru==0.7.3` to `pyproject.toml` runtime dependencies
- [ ] 1.1.2 Add `libcst==1.8.6` to `pyproject.toml` dev dependencies
- [ ] 1.1.3 Run `pip install -e ".[dev]"` to install dependencies
- [ ] 1.1.4 Verify: `python -c "import loguru; print(loguru.__version__)"` shows `0.7.3`
- [ ] 1.1.5 Verify: `python -c "import libcst; print(libcst.__version__)"` shows `1.8.6`

### 1.2 Create Python Logger Configuration (Pino-Compatible Sink)

- [ ] 1.2.1 Create `theauditor/utils/logging.py`:

```python
"""Centralized logging configuration using Loguru with Pino-compatible output.

This module provides a unified logging interface that outputs NDJSON compatible
with Pino (Node.js logging library), enabling unified log viewing across
Python and TypeScript components.

Usage:
    from theauditor.utils.logging import logger
    logger.info("Message")
    logger.debug("Debug message")  # Only shows if THEAUDITOR_LOG_LEVEL=DEBUG

Environment Variables:
    THEAUDITOR_LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
    THEAUDITOR_LOG_JSON: 0|1 (default: 0, human-readable)
    THEAUDITOR_LOG_FILE: path to log file (optional)
    THEAUDITOR_REQUEST_ID: correlation ID for cross-language tracing
"""
import json
import os
import sys
import uuid
from pathlib import Path

from loguru import logger

# Remove default handler
logger.remove()

# Pino-compatible numeric levels
PINO_LEVELS = {
    "TRACE": 10,
    "DEBUG": 20,
    "INFO": 30,
    "WARNING": 40,
    "ERROR": 50,
    "CRITICAL": 60,
}

# Get configuration from environment
_log_level = os.environ.get("THEAUDITOR_LOG_LEVEL", "INFO").upper()
_json_mode = os.environ.get("THEAUDITOR_LOG_JSON", "0") == "1"
_log_file = os.environ.get("THEAUDITOR_LOG_FILE")
_request_id = os.environ.get("THEAUDITOR_REQUEST_ID") or str(uuid.uuid4())


def pino_compatible_sink(message):
    """Format log records as Pino-compatible NDJSON.

    Output format matches Pino exactly for unified log viewing:
    {"level":30,"time":1715629847123,"msg":"...","pid":12345,"request_id":"..."}
    """
    record = message.record

    pino_log = {
        "level": PINO_LEVELS.get(record["level"].name, 30),
        "time": int(record["time"].timestamp() * 1000),
        "msg": record["message"],
        "pid": record["process"].id,
        "request_id": record["extra"].get("request_id", _request_id),
    }

    # Add any extra context fields
    for key, value in record["extra"].items():
        if key not in ("request_id",):
            pino_log[key] = value

    # Add exception info if present (Pino err format)
    if record["exception"]:
        pino_log["err"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else "Error",
            "message": str(record["exception"].value) if record["exception"].value else "",
        }

    # Write to stderr (no emojis - Windows CP1252 compatibility)
    print(json.dumps(pino_log), file=sys.stderr)


# Human-readable format (no emojis - Windows CP1252 compatibility)
_human_format = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# Console handler - choose format based on JSON mode
if _json_mode:
    logger.add(
        pino_compatible_sink,
        level=_log_level,
        colorize=False,
    )
else:
    logger.add(
        sys.stderr,
        level=_log_level,
        format=_human_format,
        colorize=True,
    )

# Optional file handler (always NDJSON for machine parsing)
if _log_file:
    logger.add(
        pino_compatible_sink,
        level="DEBUG",  # File always captures everything
    )


def configure_file_logging(log_dir: Path, level: str = "DEBUG") -> None:
    """Add rotating file handler for persistent logs.

    Args:
        log_dir: Directory for log files (e.g., Path(".pf"))
        level: Minimum log level for file output
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "theauditor.log"

    # File logging uses human-readable format (for manual inspection)
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


def get_request_id() -> str:
    """Get the current request ID for correlation."""
    return _request_id


def get_subprocess_env() -> dict:
    """Get environment dict with REQUEST_ID for subprocess calls.

    Use this when spawning TypeScript extractor or other subprocesses
    to maintain log correlation.

    Example:
        env = get_subprocess_env()
        subprocess.run(["node", "extractor.js"], env=env)
    """
    env = os.environ.copy()
    env["THEAUDITOR_REQUEST_ID"] = _request_id
    return env


__all__ = ["logger", "configure_file_logging", "get_request_id", "get_subprocess_env"]
```

- [ ] 1.2.2 Verify: `python -c "from theauditor.utils.logging import logger; logger.info('test')"` works
- [ ] 1.2.3 Verify JSON mode: `THEAUDITOR_LOG_JSON=1 python -c "from theauditor.utils.logging import logger; logger.info('test')"` outputs NDJSON

---

## PHASE 2: Verify Migration Script

**IMPORTANT**: The migration script already exists at `scripts/loguru_migration.py` (847 lines).
Do NOT create a new script. Use the existing production-ready script.

### 2.1 Verify Script Exists

- [ ] 2.1.1 Verify `scripts/loguru_migration.py` exists and has ~847 lines
- [ ] 2.1.2 Verify script has standalone CLI: `python scripts/loguru_migration.py --help`
- [ ] 2.1.3 Review edge case handling in script docstring (lines 27-37)

### 2.2 Understand Script Capabilities

The script handles these edge cases (already implemented):

| Edge Case | Behavior | Script Line |
|-----------|----------|-------------|
| `end=""` or `end="\r"` | SKIPPED (progress bars) | 307-314 |
| `sep=","` | Separator preserved in format string | 359-369 |
| `sep=my_var` (dynamic) | SKIPPED (cannot build static format) | 366-368 |
| `file=sys.stderr` | Defaults to logger.error | 349-351 |
| `file=custom_handle` | SKIPPED (data loss prevention) | 329-331 |
| Multi-arg prints | Format string `"{} {}"` injected | 431-436 |
| Brace hazard `{regex}` | Format injection to prevent crash | 417-429 |
| Debug guards | Unwrapped if safe, kept if eager eval risk | 176-200, 493-522 |
| `traceback.print_exc()` | Converted to `logger.exception("")` | 577-592 |

### 2.3 Script Usage Reference

```bash
# Dry run - preview changes without modifying files
python scripts/loguru_migration.py theauditor/ --dry-run

# Apply changes to directory
python scripts/loguru_migration.py theauditor/

# Single file with diff output
python scripts/loguru_migration.py theauditor/taint/core.py --dry-run --diff

# Multiple specific files
python scripts/loguru_migration.py file1.py file2.py file3.py
```

- [ ] 2.3.1 Run help to verify CLI works: `python scripts/loguru_migration.py --help`

---

## PHASE 3: Python Migration Dry Run

### 3.1 Single File Test

- [ ] 3.1.1 Dry run on `theauditor/taint/core.py` (has many prints):
```bash
python scripts/loguru_migration.py theauditor/taint/core.py --dry-run --diff
```
- [ ] 3.1.2 Review the diff output
- [ ] 3.1.3 Verify tag-to-level mapping is correct
- [ ] 3.1.4 Verify imports are added correctly

### 3.2 Full Dry Run

- [ ] 3.2.1 Dry run on all theauditor files:
```bash
python scripts/loguru_migration.py theauditor/ --dry-run
```
- [ ] 3.2.2 Review summary output (files modified, transformations count)
- [ ] 3.2.3 Note any edge cases skipped (end="", file=custom, etc.)
- [ ] 3.2.4 Verify no syntax errors reported

---

## PHASE 4: Python Migration Application

### 4.1 Apply Transformation

- [ ] 4.1.1 Apply migration to all files:
```bash
python scripts/loguru_migration.py theauditor/
```

### 4.2 Post-Transform Cleanup

- [ ] 4.2.1 Run ruff to fix formatting:
```bash
ruff check --fix theauditor/
ruff format theauditor/
```
- [ ] 4.2.2 Verify transformation count:
```bash
# Should be 0 or near-0 (only untagged prints remain)
grep -r "print.*\[" theauditor/ | wc -l
```
- [ ] 4.2.3 Verify imports added correctly:
```bash
grep -r "from theauditor.utils.logging import logger" theauditor/ | wc -l
```

---

## PHASE 5: Python Cleanup

### 5.1 Remove Old Logger

- [ ] 5.1.1 Delete old logger.py: `rm theauditor/utils/logger.py`
- [ ] 5.1.2 Update any remaining imports of old logger:
```bash
# Find files still importing from old location
grep -r "from theauditor.utils.logger import" theauditor/
# Replace with new import
```

### 5.2 Update Old Logger References (22 files)

The following files use `setup_logger` and need import migration:

**theauditor/commands/** (8 files):
- [ ] 5.2.1 `cdk.py` - lines 12, 14
- [ ] 5.2.2 `cfg.py` - lines 8, 10
- [ ] 5.2.3 `graphql.py` - lines 8, 10
- [ ] 5.2.4 `workflows.py` - lines 15, 17
- [ ] 5.2.5 `planning.py` - lines 13, 15
- [ ] 5.2.6 `metadata.py` - lines 5, 7
- [ ] 5.2.7 `lint.py` - lines 12, 14
- [ ] 5.2.8 `terraform.py` - lines 12, 14

**theauditor/utils/** (3 files):
- [ ] 5.2.9 `memory.py` - lines 13, 15
- [ ] 5.2.10 `helpers.py` - lines 8, 10
- [ ] 5.2.11 `code_snippets.py` - lines 6, 8

**theauditor/linters/** (1 file):
- [ ] 5.2.12 `linters.py` - lines 11, 13

**theauditor/terraform/** (2 files):
- [ ] 5.2.13 `graph.py` - lines 11, 13
- [ ] 5.2.14 `analyzer.py` - lines 10, 12

**theauditor/indexer/extractors/** (4 files):
- [ ] 5.2.15 `terraform.py` - lines 8, 11
- [ ] 5.2.16 `rust.py` - lines 7, 10
- [ ] 5.2.17 `go.py` - lines 6, 9
- [ ] 5.2.18 `bash.py` - lines 5, 8

**theauditor/taint/** (1 file):
- [ ] 5.2.19 `flow_resolver.py` - lines 7, 11

**theauditor/** (1 file):
- [ ] 5.2.20 `vulnerability_scanner.py` - lines 13, 17

**theauditor/utils/__init__.py** (re-export):
- [ ] 5.2.21 Update `__init__.py` - remove `setup_logger` from `__all__` (lines 33, 56)
- [ ] 5.2.22 Add `logger` export from new logging.py

**Replacement pattern for each file:**
```python
# OLD (2 lines)
from theauditor.utils.logger import setup_logger
logger = setup_logger(__name__)

# NEW (1 line)
from theauditor.utils.logging import logger
```

- [ ] 5.2.23 Verify all 22 files updated:
```bash
grep -r "setup_logger" theauditor/ | grep -v "__pycache__"  # Should return nothing
```

---

## PHASE 6: Python Testing

### 6.1 Functional Tests

- [ ] 6.1.1 Run test suite: `python -m pytest tests/ -v`
- [ ] 6.1.2 Fix any test failures

### 6.2 Log Level Tests

- [ ] 6.2.1 Default (INFO) - should show info and above:
```bash
aud full --index
```
- [ ] 6.2.2 Debug - should show all logs:
```bash
THEAUDITOR_LOG_LEVEL=DEBUG aud full --index
```
- [ ] 6.2.3 Error only - should show minimal output:
```bash
THEAUDITOR_LOG_LEVEL=ERROR aud full --index
```

### 6.3 JSON Output Tests (Pino-Compatible NDJSON)

- [ ] 6.3.1 Verify JSON output:
```bash
THEAUDITOR_LOG_JSON=1 aud full --index 2>&1 | head -5
```
- [ ] 6.3.2 Validate JSON is parseable:
```bash
THEAUDITOR_LOG_JSON=1 aud full --index 2>&1 | python -c "import sys,json; [json.loads(l) for l in sys.stdin]"
```
- [ ] 6.3.3 Verify Pino format (level is int, time is epoch ms, msg not message):
```bash
THEAUDITOR_LOG_JSON=1 python -c "from theauditor.utils.logging import logger; logger.info('test')" 2>&1
# Should output: {"level":30,"time":1715...,"msg":"test","pid":...,"request_id":"..."}
```

### 6.4 Rich UI Verification

- [ ] 6.4.1 Run full pipeline and verify live table still works:
```bash
aud full --offline
```
- [ ] 6.4.2 Compare output to baseline captured in 0.7

---

## PHASE 7: TypeScript Migration (Pino 10.1.0)

**READ**: specs/logging/spec.md "TypeScript Requirements" before starting.

### 7.1 Add Pino Dependencies

- [ ] 7.1.1 Navigate to JavaScript extractor directory:
```bash
cd theauditor/ast_extractors/javascript
```
- [ ] 7.1.2 Add Pino as dependency:
```bash
npm install pino@10.1.0
```
- [ ] 7.1.3 Add pino-pretty as dev dependency:
```bash
npm install --save-dev pino-pretty@13.0.0
```
- [ ] 7.1.4 Verify package.json has correct versions:
```json
{
  "dependencies": {
    "pino": "10.1.0"
  },
  "devDependencies": {
    "pino-pretty": "13.0.0"
  }
}
```

### 7.2 Create TypeScript Logger (Pino Wrapper)

- [ ] 7.2.1 Create directory: `mkdir -p theauditor/ast_extractors/javascript/src/utils`
- [ ] 7.2.2 Create `theauditor/ast_extractors/javascript/src/utils/logger.ts`:

```typescript
/**
 * Pino logger for TypeScript extractor.
 *
 * Outputs NDJSON to stderr (preserving stdout for JSON data output).
 * Respects same environment variables as Python (Loguru):
 * - THEAUDITOR_LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
 * - THEAUDITOR_REQUEST_ID: Correlation ID passed from Python orchestrator
 *
 * Format matches Python exactly for unified log viewing:
 * {"level":30,"time":1715629847123,"msg":"...","pid":12345,"request_id":"..."}
 */
import pino from "pino";

// Map env var names to Pino level names
const LOG_LEVEL_MAP: Record<string, pino.Level> = {
  DEBUG: "debug",
  INFO: "info",
  WARNING: "warn",
  WARN: "warn",
  ERROR: "error",
};

// Get level from environment, default to info
const envLevel = process.env.THEAUDITOR_LOG_LEVEL?.toUpperCase() || "INFO";
const pinoLevel = LOG_LEVEL_MAP[envLevel] || "info";

// Get request ID from environment (passed by Python orchestrator)
const requestId = process.env.THEAUDITOR_REQUEST_ID || "unknown";

// Create base logger writing to stderr (stdout reserved for JSON data)
// Using pino.destination for stderr
const baseLogger = pino(
  {
    level: pinoLevel,
    // Pino outputs level as number and time as epoch ms by default
    // msg is also default key - perfect match for our Python sink
  },
  pino.destination(2) // fd 2 = stderr
);

// Create child logger with request_id bound
export const logger = baseLogger.child({ request_id: requestId });

// Re-export for convenience
export default logger;
```

### 7.3 Migrate main.ts (15 statements)

- [ ] 7.3.1 Add import at top of file: `import { logger } from "./utils/logger";`
- [ ] 7.3.2 Replace line 33: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.3 Replace line 44: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.4 Replace line 149: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.5 Replace line 242: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.6 Replace line 360: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.7 Replace line 460: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.8 Replace line 469: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.9 Replace line 483: `console.error(\`[DEBUG JS BATCH]...\`)` -> `logger.debug(...)`
- [ ] 7.3.10 Replace line 746: `console.error(\`[DEBUG JS BATCH]...\`)` -> `logger.debug(...)`
- [ ] 7.3.11 Replace line 825: `console.error(\`[DEBUG JS BATCH]...\`)` -> `logger.debug(...)`
- [ ] 7.3.12 Replace line 851: `console.error("[BATCH DEBUG]...")` -> `logger.debug(...)`
- [ ] 7.3.13 Replace line 854: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.14 Replace line 857: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.15 Replace line 866: `console.error(...)` -> `logger.error(...)`
- [ ] 7.3.16 Replace line 878: `console.error(...)` -> `logger.error(...)`

**Tag-to-Level Mapping for TypeScript:**
| Original Tag | New Method |
|--------------|------------|
| `[DEBUG JS BATCH]` | `logger.debug(...)` |
| `[DEBUG JS]` | `logger.debug(...)` |
| `[BATCH DEBUG]` | `logger.debug(...)` |
| No tag (errors) | `logger.error(...)` |

### 7.4 Migrate core_language.ts (1 statement)

- [ ] 7.4.1 Add import: `import { logger } from "../utils/logger";`
- [ ] 7.4.2 Replace line 350: `console.error(...)` -> `logger.error(...)`

### 7.5 Migrate data_flow.ts (2 statements)

- [ ] 7.5.1 Add import: `import { logger } from "../utils/logger";`
- [ ] 7.5.2 Replace line 184: `console.error(...)` -> `logger.error(...)`
- [ ] 7.5.3 Replace line 189: `console.error(\`[DEBUG JS]...\`)` -> `logger.debug(...)`

### 7.6 Rebuild TypeScript

- [ ] 7.6.1 Build: `cd theauditor/ast_extractors/javascript && npm run build`
- [ ] 7.6.2 Verify no build errors
- [ ] 7.6.3 Verify no remaining console.error (except in logger.ts):
```bash
grep -r "console\." theauditor/ast_extractors/javascript/src/ | grep -v logger.ts
```

### 7.7 Test Pino Output

- [ ] 7.7.1 Test logger directly:
```bash
cd theauditor/ast_extractors/javascript
node -e "const {logger} = require('./dist/utils/logger'); logger.info('test')"
# Should output: {"level":30,"time":...,"msg":"test",...}
```
- [ ] 7.7.2 Test with pino-pretty:
```bash
node -e "const {logger} = require('./dist/utils/logger'); logger.info('test')" 2>&1 | npx pino-pretty
```
- [ ] 7.7.3 Test REQUEST_ID threading:
```bash
THEAUDITOR_REQUEST_ID=abc-123 node -e "const {logger} = require('./dist/utils/logger'); logger.info('test')"
# Should include: "request_id":"abc-123"
```

---

## PHASE 8: Final Verification

**READ**: specs/logging/spec.md "All Requirements" before verifying.

### 8.1 Python Verification

- [ ] 8.1.1 Zero tagged prints remaining:
```bash
grep -r "print.*\[" theauditor/ | wc -l  # Should be 0
```
- [ ] 8.1.2 Logger imports present:
```bash
grep -r "from theauditor.utils.logging import logger" theauditor/ | wc -l  # Should be ~51
```
- [ ] 8.1.3 All tests pass:
```bash
python -m pytest tests/ -v
```

### 8.2 TypeScript Verification

- [ ] 8.2.1 Zero console.error remaining (except logger.ts):
```bash
grep -r "console\." theauditor/ast_extractors/javascript/src/ | grep -v logger.ts  # Should be empty
```
- [ ] 8.2.2 Logger import present in all modified files
- [ ] 8.2.3 TypeScript builds without errors

### 8.3 NDJSON Format Verification

- [ ] 8.3.1 Python NDJSON format correct:
```bash
THEAUDITOR_LOG_JSON=1 python -c "from theauditor.utils.logging import logger; logger.info('test')" 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); assert 'level' in d and isinstance(d['level'],int); assert 'msg' in d; assert 'time' in d"
```
- [ ] 8.3.2 TypeScript NDJSON format correct:
```bash
cd theauditor/ast_extractors/javascript && node -e "const {logger} = require('./dist/utils/logger'); logger.info('test')" 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); assert 'level' in d and isinstance(d['level'],int); assert 'msg' in d; assert 'time' in d"
```
- [ ] 8.3.3 Unified pino-pretty works for both:
```bash
# Python
THEAUDITOR_LOG_JSON=1 python -c "from theauditor.utils.logging import logger; logger.info('Python log')" 2>&1 | npx pino-pretty
# TypeScript
cd theauditor/ast_extractors/javascript && node -e "const {logger} = require('./dist/utils/logger'); logger.info('TypeScript log')" 2>&1 | npx pino-pretty
```

### 8.4 Integration Verification

- [ ] 8.4.1 Full pipeline works:
```bash
aud full --offline
```
- [ ] 8.4.2 Log level filtering works across both languages:
```bash
THEAUDITOR_LOG_LEVEL=DEBUG aud full --index
THEAUDITOR_LOG_LEVEL=ERROR aud full --index
```
- [ ] 8.4.3 JSON output works:
```bash
THEAUDITOR_LOG_JSON=1 aud full --index 2>&1 | head -10
```
- [ ] 8.4.4 Rich UI unchanged (visual comparison)
- [ ] 8.4.5 REQUEST_ID threads from Python to TypeScript:
```bash
# Run a command that invokes TypeScript extractor
# Check that logs from both have same request_id
THEAUDITOR_LOG_JSON=1 aud full --index 2>&1 | grep request_id | head -5
```

### 8.5 Cleanup

- [ ] 8.5.1 Remove any debug code added during implementation
- [ ] 8.5.2 Verify no `.pyc` or build artifacts committed
- [ ] 8.5.3 Final ruff check: `ruff check theauditor/`
- [ ] 8.5.4 Final TypeScript lint: `cd theauditor/ast_extractors/javascript && npm run lint`

---

## Task Dependencies

| Phase | Depends On |
|-------|------------|
| Phase 1 | Phase 0 verification |
| Phase 2 | Phase 1 (dependencies installed) |
| Phase 3 | Phase 2 (codemod verified) |
| Phase 4 | Phase 3 (dry run verified) |
| Phase 5 | Phase 4 (transformation applied) |
| Phase 6 | Phase 5 (cleanup done) |
| Phase 7 | Phase 1 (can run in parallel with Phases 2-6) |
| Phase 8 | Phase 6 AND Phase 7 |

**Note**: Phase 7 (TypeScript/Pino) can run in parallel with Phases 2-6 (Python/Loguru).

---

## Rollback Procedure

If anything goes wrong:

**Python:**
```bash
git checkout -- theauditor/
rm theauditor/utils/logging.py
```

**TypeScript:**
```bash
git checkout -- theauditor/ast_extractors/javascript/src/
git checkout -- theauditor/ast_extractors/javascript/package.json
git checkout -- theauditor/ast_extractors/javascript/package-lock.json
rm -rf theauditor/ast_extractors/javascript/src/utils/
npm install  # Restore original dependencies
```

**Note**: `scripts/loguru_migration.py` is a standalone tool - no cleanup needed.

**Full rollback time**: ~2 minutes
