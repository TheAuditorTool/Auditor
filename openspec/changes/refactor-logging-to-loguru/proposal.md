# Refactor Logging Infrastructure to Loguru + Pino (Polyglot)

**Status**: PROPOSAL - Awaiting Architect Approval
**Change ID**: `refactor-logging-to-loguru`
**Complexity**: HIGH (~550 lines modified across 54 files, automated via LibCST + manual TS)
**Breaking**: NO - Internal logging only, no API changes
**Risk Level**: MEDIUM - Automated transformation with verification, Rich UI preserved

---

## Why

### Problem Statement

TheAuditor's logging infrastructure is a fragmented disaster held together by duct tape, hopes, and prayers. There are 5+ different logging mechanisms scattered across 51 Python files and 3 TypeScript files with zero standardization, making debugging impossible and professional observability non-existent.

### Verified Problems (Quantified Evidence)

**Python Core (51 files):**

| Problem | Count | Files | Evidence |
|---------|-------|-------|----------|
| Raw `print("[TAG]...")` statements | 323 | 51 | `grep -r "print.*\[" theauditor/` |
| Proper `logger.*` calls | 189 | 36 | Only 36/51 files use the logger |
| Manual `file=sys.stderr` routing | 209 | 32 | No centralized output routing |
| Debug-gated prints `if os.environ.get("THEAUDITOR_DEBUG")` | ~20 | 8 | Manual env var checks everywhere |

**TypeScript Extractor (3 files):**

| Problem | Count | Files | Evidence |
|---------|-------|-------|----------|
| `console.error()` statements | 18 | 3 | `grep -r "console\." javascript/src/` |
| Same tag patterns as Python | 18 | 3 | `[DEBUG JS BATCH]`, `[BATCH DEBUG]`, etc. |

**Go/Rust/Bash Extractors:**
- Written IN Python using tree-sitter - NO separate logging
- Zero logging statements in `go_impl.py`, `rust_impl.py`, `bash_impl.py`
- These use Python's logging through the orchestrator

### Current Logging Mechanisms (5 Parallel Universes)

**Python:**
1. **utils/logger.py** - Facade that only 36 files use
2. **Raw print statements** - 323 occurrences with hardcoded `[TAG]` prefixes
3. **RichRenderer** - Pipeline UI only (pipelines.py)
4. **sys.stderr direct** - 209 manual `file=sys.stderr` calls
5. **Rich Console** - Commands layer final output only

**TypeScript:**
6. **console.error()** - 18 statements with same tag patterns

### User Impact

1. **Cannot debug issues** - No log levels, no filtering, no timestamps on 323+ statements
2. **Cannot aggregate logs** - No structured logging (JSON) for ELK/Splunk/DataDog
3. **Cannot trace requests** - No correlation IDs across pipeline phases
4. **Cannot configure at runtime** - Log levels hardcoded, no `THEAUDITOR_LOG_LEVEL` env var

### Why LibCST Automation for Python

Manual refactoring of 323 print statements across 51 files is:
- Error-prone (easy to miss edge cases)
- Time-consuming (days of tedious work)
- Risky (human errors in repetitive tasks)

**Production script exists**: `scripts/loguru_migration.py` (847 lines, standalone CLI)

The script provides:
- Automated pattern matching and transformation via LibCST
- Preserves all formatting (comments, whitespace)
- Automatic import management (adds loguru import)
- Dry-run mode with diff output for verification
- Syntax validation via compile() before writing any file
- Edge case handling: end="", sep=, file=custom, eager eval protection, brace hazard
- Multi-encoding support (utf-8, latin-1, cp1252)

### Why Pino for TypeScript

**Pino** is the spiritual equivalent of Loguru in the Node.js ecosystem:
- Industry standard for fast, JSON-native logging in Node
- 10M+ weekly downloads, battle-tested in production
- Native NDJSON output compatible with log aggregators
- Child logger pattern for correlation ID threading
- `pino-pretty` for developer experience during local debugging

---

## What Changes

### Summary

| Component | Action | Lines | Risk |
|-----------|--------|-------|------|
| `pyproject.toml` | ADD dependency (loguru==0.7.3) | +1 | LOW |
| `theauditor/utils/logging.py` | CREATE (Pino-compatible sink) | +80 | LOW |
| `scripts/loguru_migration.py` | EXISTS (847 lines) | 0 | LOW |
| `theauditor/**/*.py` (51 files) | MODIFY via codemod | ~-323/+323 | MEDIUM |
| `theauditor/utils/logger.py` | DELETE (replaced) | -24 | LOW |
| `theauditor/ast_extractors/javascript/package.json` | ADD pino@10.1.0 | +2 | LOW |
| `theauditor/ast_extractors/javascript/src/utils/logger.ts` | CREATE (Pino wrapper) | +50 | LOW |
| `theauditor/ast_extractors/javascript/src/*.ts` (3 files) | MODIFY manually | ~-18/+18 | LOW |
| `theauditor/pipeline/renderer.py` | PRESERVE | 0 | NONE |
| `theauditor/pipeline/ui.py` | PRESERVE | 0 | NONE |

### High-Level Architecture

```
BEFORE (Current - 6 Code Paths):
+-------------------------------------------------------------+
| Python (theauditor/**/*.py)                                 |
|   +-- print("[TAG] msg") ---------------------> STDOUT       |
|   +-- print("[TAG] msg", file=sys.stderr) ---> STDERR       |
|   +-- logger.info("msg") --> utils/logger.py --> STDERR     |
|   +-- if DEBUG: print(...) ------------------> STDERR       |
|   +-- RichRenderer.on_log() -----------------> Rich Console |
+-------------------------------------------------------------+
| TypeScript (javascript/src/*.ts)                            |
|   +-- console.error("[TAG] msg") ------------> STDERR       |
|                                                              |
|   Result: 6 code paths, no filtering, no structure = CHAOS  |
+-------------------------------------------------------------+

AFTER (Proposed - 3 Code Paths, Unified NDJSON):
+-------------------------------------------------------------+
| Python (theauditor/**/*.py)                                 |
|   +-- logger.info/debug/error("msg")                        |
|       |                                                     |
|       +--> Loguru (Pino-compatible sink) --> STDERR         |
|       |         |                                           |
|       |         +--> {"level":30,"time":1715...,"msg":""}   |
|       |         +--> File (.pf/) with rotation              |
|       |                                                     |
|   +-- RichRenderer (PRESERVED) -----------> Rich Console    |
+-------------------------------------------------------------+
| TypeScript (javascript/src/*.ts)                            |
|   +-- logger.info/debug/error("msg")                        |
|       |                                                     |
|       +--> Pino --------------------------> STDERR          |
|                 |                                           |
|                 +--> {"level":30,"time":1715...,"msg":""}   |
|                                                              |
|   Result: 3 code paths, unified NDJSON, structured logs     |
+-------------------------------------------------------------+
                              |
                              v
                  +-------------------------+
                  | UNIFIED NDJSON OUTPUT   |
                  | (Same format from both) |
                  +-------------------------+
                              |
              +---------------+---------------+
              |                               |
              v                               v
      pino-pretty (dev)              Log Aggregator (prod)
      Human-readable                 ELK/Splunk/DataDog
```

### Key Design Decisions

1. **Loguru for Python** - Simple API, drop-in replacement, built-in rotation
2. **Pino for TypeScript** - Industry standard, JSON-native, fast
3. **Unified NDJSON format** - Loguru outputs Pino-compatible JSON
4. **REQUEST_ID correlation** - Thread ID from Python to TypeScript subprocess
5. **Preserve Rich pipeline UI** - RichRenderer stays exactly as-is for `aud full` progress
6. **LibCST automation for Python** - Script the migration, don't hand-edit 323 statements
7. **Tag-to-level mapping** - `[DEBUG]` -> `logger.debug()`, `[ERROR]` -> `logger.error()`, etc.
8. **pino-pretty for dev** - Human-readable output during development

### Unified JSON Format (NDJSON)

Both Python (Loguru) and TypeScript (Pino) output identical JSON structure:

```json
{"level":30,"time":1715629847123,"msg":"Processing file","pid":12345,"request_id":"abc-123"}
{"level":20,"time":1715629847456,"msg":"Debug info","pid":12345,"request_id":"abc-123"}
```

| Field | Type | Description |
|-------|------|-------------|
| `level` | integer | Pino-compatible: 10=trace, 20=debug, 30=info, 40=warn, 50=error |
| `time` | integer | Unix epoch milliseconds |
| `msg` | string | Log message |
| `pid` | integer | Process ID |
| `request_id` | string | Correlation ID passed from Python to TypeScript |

### New Environment Variables

| Variable | Values | Default | Purpose |
|----------|--------|---------|---------|
| `THEAUDITOR_LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR | INFO | Filter log output |
| `THEAUDITOR_LOG_JSON` | 0, 1 | 0 | Enable JSON structured output |
| `THEAUDITOR_LOG_FILE` | path | None | Optional file output location |
| `THEAUDITOR_REQUEST_ID` | uuid | auto-generated | Correlation ID for pipeline tracing |

---

## Polyglot Assessment

**CRITICAL: This is a polyglot system with 5 language extractors.**

| Language | Extractor Location | Implementation | Logging Solution |
|----------|-------------------|----------------|------------------|
| **Python** | `theauditor/ast_extractors/python/` | Python (tree-sitter) | Loguru (Pino-compatible sink) |
| **TypeScript/JS** | `theauditor/ast_extractors/javascript/src/` | TypeScript (standalone) | **Pino 10.1.0** |
| **Go** | `theauditor/ast_extractors/go_impl.py` | Python (tree-sitter) | Loguru (via orchestrator) |
| **Rust** | `theauditor/ast_extractors/rust_impl.py` | Python (tree-sitter) | Loguru (via orchestrator) |
| **Bash** | `theauditor/ast_extractors/bash_impl.py` | Python (tree-sitter) | Loguru (via orchestrator) |

**Orchestrator**: `theauditor/indexer/orchestrator.py` calls all extractors. Go/Rust/Bash extractors are Python modules imported directly. TypeScript extractor runs as subprocess via Node.js with `THEAUDITOR_REQUEST_ID` passed as env var.

### What This Means

1. **Python logging migration** affects ALL extractors except TypeScript
2. **TypeScript extractor** uses Pino with REQUEST_ID from env var
3. **No Go/Rust/Bash-specific logging work** needed - they're Python modules
4. **Unified NDJSON** enables cross-language log correlation

---

## Impact

### Affected Specs

| Spec | Requirement | Change Type |
|------|-------------|-------------|
| `logging` | NEW: Centralized Logging Configuration | ADDED |
| `logging` | NEW: Runtime Log Level Control | ADDED |
| `logging` | NEW: Structured JSON Output (NDJSON) | ADDED |
| `logging` | NEW: Log Rotation | ADDED |
| `logging` | NEW: Polyglot Logging Consistency (Pino format) | ADDED |
| `logging` | NEW: Cross-Language Correlation (REQUEST_ID) | ADDED |

### Affected Code by Language

**Python (via LibCST codemod):**

| Directory | Files | Transformation |
|-----------|-------|----------------|
| `theauditor/taint/` | 4 | ~38 prints -> logger calls |
| `theauditor/indexer/` | 12 | ~45 prints -> logger calls |
| `theauditor/commands/` | 8 | ~25 prints -> logger calls |
| `theauditor/ast_extractors/` | 15 | ~80 prints -> logger calls |
| `theauditor/graph/` | 5 | ~20 prints -> logger calls |
| `theauditor/rules/` | 7 | ~35 prints -> logger calls |
| Other | - | ~80 prints -> logger calls |

**TypeScript (manual with Pino):**

| File | Statements | Transformation |
|------|------------|----------------|
| `theauditor/ast_extractors/javascript/src/main.ts` | 15 | console.error -> logger calls |
| `theauditor/ast_extractors/javascript/src/extractors/core_language.ts` | 1 | console.error -> logger calls |
| `theauditor/ast_extractors/javascript/src/extractors/data_flow.ts` | 2 | console.error -> logger calls |

### Dependencies Added

| Package | Version | Size | Language | Why |
|---------|---------|------|----------|-----|
| `loguru` | 0.7.3 | ~500KB | Python | Structured logging with rotation |
| `libcst` | 1.8.6 | ~3MB | Python | Migration script dependency (dev only) |
| `pino` | 10.1.0 | ~150KB | Node.js | Industry-standard JSON logging |
| `pino-pretty` | 13.0.0 | ~100KB | Node.js | Dev dependency for human-readable logs |

---

## Risk Assessment

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Codemod misses edge case | MEDIUM | LOW | Dry-run + grep verification |
| Import conflicts | LOW | LOW | LibCST handles imports automatically |
| Windows CP1252 encoding | LOW | MEDIUM | Loguru auto-detects, we ban emojis per CLAUDE.md |
| Performance regression | LOW | LOW | Both Loguru and Pino are faster than print()/console |
| Rich UI breaks | NONE | - | RichRenderer not modified |
| TS extractor output parsing | LOW | LOW | Pino writes to stderr, stdout unchanged |
| NDJSON format mismatch | LOW | LOW | Both configured identically at setup |

### ZERO FALLBACK COMPLIANCE

This change introduces NO fallback patterns:
- Single logging path per language (Python: Loguru, TS: Pino)
- No try/except falling back to print()
- No "if loguru available else print()" patterns
- Configuration fails hard if invalid (no silent defaults)
- REQUEST_ID missing = hard fail, not silent fallback

### Rollback Plan

**Python:**
```bash
git revert <commit>  # Single commit with all Python changes
```

**TypeScript:**
```bash
git checkout -- javascript/src/  # Revert TS changes
npm install  # Restore original package.json
```

Time to rollback: ~2 minutes

---

## Success Criteria

All criteria MUST pass before marking complete:

**Python:**
- [ ] `grep -r "print.*\[" theauditor/` returns 0 matches
- [ ] `THEAUDITOR_LOG_LEVEL=DEBUG aud full --index` shows debug output
- [ ] `THEAUDITOR_LOG_LEVEL=ERROR aud full --index` shows only errors
- [ ] `THEAUDITOR_LOG_JSON=1 aud full --index` produces valid NDJSON
- [ ] NDJSON format matches Pino: `{"level":30,"time":...,"msg":"..."}`
- [ ] `.pf/theauditor.log` file created with rotation working
- [ ] `aud full` Rich pipeline UI unchanged (visual regression test)
- [ ] All existing tests pass

**TypeScript:**
- [ ] `grep -r "console\." javascript/src/ | grep -v logger.ts` returns 0 matches
- [ ] `THEAUDITOR_LOG_LEVEL=DEBUG` shows TS debug output via Pino
- [ ] `THEAUDITOR_LOG_JSON=1` produces valid NDJSON from Pino
- [ ] NDJSON format matches Python output exactly
- [ ] REQUEST_ID appears in TypeScript logs when passed from Python

**Integration:**
- [ ] `(python orchestrator.py | node extractor.js) 2>&1 | npx pino-pretty` shows unified logs
- [ ] REQUEST_ID threads correctly from Python to TypeScript
- [ ] Log aggregator (if tested) receives unified format from both

---

## Task References

**READ THE SPEC before implementing each language phase.**

| Phase | Language | Task File Section | Spec Reference |
|-------|----------|-------------------|----------------|
| 1 | Python | tasks.md SS1-SS6 | specs/logging/spec.md "Python Requirements" |
| 2 | TypeScript | tasks.md SS7 | specs/logging/spec.md "TypeScript Requirements" |
| 3 | Verification | tasks.md SS8 | specs/logging/spec.md "All Requirements" |

---

## Approval Required

### Architect Decision Points

1. **Loguru 0.7.3 as hard dependency** - Adds ~500KB, provides 2025-standard logging
2. **Pino 10.1.0 for TypeScript** - Industry standard, replaces custom logger
3. **LibCST 1.8.6 in dev deps** - Used by existing `scripts/loguru_migration.py`
4. **Delete utils/logger.py** - Replaced by utils/logging.py with Loguru
5. **Pino-compatible sink** - Loguru outputs NDJSON matching Pino format exactly
6. **REQUEST_ID correlation** - Thread correlation ID from Python to TypeScript
7. **pino-pretty dev dependency** - Human-readable logs during development

---

**Next Step**: Architect reviews and approves/denies this proposal
