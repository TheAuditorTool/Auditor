# Refactor Logging Infrastructure to Loguru (Polyglot)

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

### Why Manual for TypeScript

Only 18 statements across 3 files - scripting overhead not justified.

---

## What Changes

### Summary

| Component | Action | Lines | Risk |
|-----------|--------|-------|------|
| `pyproject.toml` | ADD dependency | +1 | LOW |
| `theauditor/utils/logging.py` | CREATE (replaces logger.py) | +100 | LOW |
| `scripts/loguru_migration.py` | EXISTS (847 lines) | 0 | LOW |
| `theauditor/**/*.py` (51 files) | MODIFY via codemod | ~-323/+323 | MEDIUM |
| `theauditor/utils/logger.py` | DELETE (replaced) | -24 | LOW |
| `theauditor/ast_extractors/javascript/src/*.ts` (3 files) | MODIFY manually | ~-18/+18 | LOW |
| `theauditor/ast_extractors/javascript/src/utils/logger.ts` | CREATE | +40 | LOW |
| `theauditor/pipeline/renderer.py` | PRESERVE | 0 | NONE |
| `theauditor/pipeline/ui.py` | PRESERVE | 0 | NONE |

### High-Level Architecture

```
BEFORE (Current - 6 Code Paths):
┌─────────────────────────────────────────────────────────────┐
│ Python (theauditor/**/*.py)                                 │
│   ├── print("[TAG] msg") ────────────────────► STDOUT       │
│   ├── print("[TAG] msg", file=sys.stderr) ───► STDERR       │
│   ├── logger.info("msg") ─► utils/logger.py ─► STDERR       │
│   ├── if DEBUG: print(...) ──────────────────► STDERR       │
│   └── RichRenderer.on_log() ─────────────────► Rich Console │
├─────────────────────────────────────────────────────────────┤
│ TypeScript (javascript/src/*.ts)                            │
│   └── console.error("[TAG] msg") ────────────► STDERR       │
│                                                              │
│   Result: 6 code paths, no filtering, no structure = CHAOS  │
└─────────────────────────────────────────────────────────────┘

AFTER (Proposed - 3 Code Paths):
┌─────────────────────────────────────────────────────────────┐
│ Python (theauditor/**/*.py)                                 │
│   ├── logger.info/debug/error("msg") ─► Loguru ─► STDERR    │
│   │                                         │               │
│   │                                         ├──► File (.pf/)│
│   │                                         └──► JSON (opt) │
│   │                                                         │
│   └── RichRenderer (PRESERVED) ──────────────► Rich Console │
├─────────────────────────────────────────────────────────────┤
│ TypeScript (javascript/src/*.ts)                            │
│   └── logger.info/debug/error("msg") ─► Custom ──► STDERR   │
│                                             │               │
│                                             └──► JSON (opt) │
│                                                              │
│   Result: 3 code paths, centralized config, structured logs │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Loguru for Python** - Simple API, drop-in replacement, built-in rotation
2. **Custom logger for TypeScript** - Lightweight, no npm dependency (18 statements not worth pino)
3. **Preserve Rich pipeline UI** - RichRenderer stays exactly as-is for `aud full` progress
4. **LibCST automation for Python** - Script the migration, don't hand-edit 323 statements
5. **Manual migration for TypeScript** - Only 18 statements, scripting overhead not justified
6. **Tag-to-level mapping** - `[DEBUG]` → `logger.debug()`, `[ERROR]` → `logger.error()`, etc.
7. **JSON output option** - `THEAUDITOR_LOG_JSON=1` for log aggregation systems

### New Environment Variables

| Variable | Values | Default | Purpose |
|----------|--------|---------|---------|
| `THEAUDITOR_LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR | INFO | Filter log output |
| `THEAUDITOR_LOG_JSON` | 0, 1 | 0 | Enable JSON structured output |
| `THEAUDITOR_LOG_FILE` | path | None | Optional file output location |

---

## Polyglot Assessment

**CRITICAL: This is a polyglot system with 5 language extractors.**

| Language | Extractor Location | Implementation | Logging Issue |
|----------|-------------------|----------------|---------------|
| **Python** | `theauditor/ast_extractors/python/` | Python (tree-sitter) | Uses Python orchestrator logging |
| **TypeScript/JS** | `theauditor/ast_extractors/javascript/src/` | TypeScript (standalone) | **18 `console.error()` - NEEDS MIGRATION** |
| **Go** | `theauditor/ast_extractors/go_impl.py` | Python (tree-sitter) | Uses Python orchestrator logging |
| **Rust** | `theauditor/ast_extractors/rust_impl.py` | Python (tree-sitter) | Uses Python orchestrator logging |
| **Bash** | `theauditor/ast_extractors/bash_impl.py` | Python (tree-sitter) | Uses Python orchestrator logging |

**Orchestrator**: `theauditor/indexer/orchestrator.py` calls all extractors. Go/Rust/Bash extractors are Python modules imported directly. TypeScript extractor runs as subprocess via Node.js.

### What This Means

1. **Python logging migration** affects ALL extractors except TypeScript
2. **TypeScript extractor** needs separate migration (standalone process)
3. **No Go/Rust/Bash-specific logging work** needed - they're Python modules

---

## Impact

### Affected Specs

| Spec | Requirement | Change Type |
|------|-------------|-------------|
| `logging` | NEW: Centralized Logging Configuration | ADDED |
| `logging` | NEW: Runtime Log Level Control | ADDED |
| `logging` | NEW: Structured JSON Output | ADDED |
| `logging` | NEW: Log Rotation | ADDED |
| `logging` | NEW: Polyglot Logging Consistency | ADDED |

### Affected Code by Language

**Python (via LibCST codemod):**

| Directory | Files | Transformation |
|-----------|-------|----------------|
| `theauditor/taint/` | 4 | ~38 prints → logger calls |
| `theauditor/indexer/` | 12 | ~45 prints → logger calls |
| `theauditor/commands/` | 8 | ~25 prints → logger calls |
| `theauditor/ast_extractors/` | 15 | ~80 prints → logger calls |
| `theauditor/graph/` | 5 | ~20 prints → logger calls |
| `theauditor/rules/` | 7 | ~35 prints → logger calls |
| Other | - | ~80 prints → logger calls |

**TypeScript (manual):**

| File | Statements | Transformation |
|------|------------|----------------|
| `theauditor/ast_extractors/javascript/src/main.ts` | 15 | console.error → logger calls |
| `theauditor/ast_extractors/javascript/src/extractors/core_language.ts` | 1 | console.error → logger calls |
| `theauditor/ast_extractors/javascript/src/extractors/data_flow.ts` | 2 | console.error → logger calls |

### Dependencies Added

| Package | Version | Size | Language | Why |
|---------|---------|------|----------|-----|
| `loguru` | >=0.7.0 | ~500KB | Python | Structured logging with rotation |
| `libcst` | >=1.0.0 | ~3MB | Python | Migration script dependency (already in dev deps) |

---

## Risk Assessment

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Codemod misses edge case | MEDIUM | LOW | Dry-run + grep verification |
| Import conflicts | LOW | LOW | LibCST handles imports automatically |
| Windows CP1252 encoding | LOW | MEDIUM | Loguru auto-detects, we ban emojis per CLAUDE.md |
| Performance regression | LOW | LOW | Loguru is faster than print() |
| Rich UI breaks | NONE | - | RichRenderer not modified |
| TS extractor output parsing | LOW | LOW | Logger writes to stderr, stdout unchanged |

### ZERO FALLBACK COMPLIANCE

This change introduces NO fallback patterns:
- Single logging path per language (Python: loguru, TS: custom logger)
- No try/except falling back to print()
- No "if loguru available else print()" patterns
- Configuration fails hard if invalid (no silent defaults)

### Rollback Plan

**Python:**
```bash
git revert <commit>  # Single commit with all Python changes
```

**TypeScript:**
```bash
git checkout -- javascript/src/  # Revert TS changes
```

Time to rollback: ~2 minutes

---

## Success Criteria

All criteria MUST pass before marking complete:

**Python:**
- [ ] `grep -r "print.*\[" theauditor/` returns 0 matches
- [ ] `THEAUDITOR_LOG_LEVEL=DEBUG aud full --index` shows debug output
- [ ] `THEAUDITOR_LOG_LEVEL=ERROR aud full --index` shows only errors
- [ ] `THEAUDITOR_LOG_JSON=1 aud full --index` produces valid JSON lines
- [ ] `.pf/theauditor.log` file created with rotation working
- [ ] `aud full` Rich pipeline UI unchanged (visual regression test)
- [ ] All existing tests pass

**TypeScript:**
- [ ] `grep -r "console\." javascript/src/ | grep -v logger.ts` returns 0 matches
- [ ] `THEAUDITOR_LOG_LEVEL=DEBUG` shows TS debug output
- [ ] `THEAUDITOR_LOG_JSON=1` produces valid JSON from TS extractor

---

## Task References

**READ THE SPEC before implementing each language phase.**

| Phase | Language | Task File Section | Spec Reference |
|-------|----------|-------------------|----------------|
| 1 | Python | tasks.md §1-§6 | specs/logging/spec.md "Python Requirements" |
| 2 | TypeScript | tasks.md §7 | specs/logging/spec.md "TypeScript Requirements" |
| 3 | Verification | tasks.md §8 | specs/logging/spec.md "All Requirements" |

---

## Approval Required

### Architect Decision Points

1. **Loguru as hard dependency** - Adds ~500KB, provides 2025-standard logging
2. **LibCST already in dev deps** - Used by existing `scripts/loguru_migration.py` (847 lines, production-ready)
3. **Delete utils/logger.py** - Replaced by utils/logging.py with Loguru
4. **Tag-to-level mapping** - Proposed mapping in codemod (can be adjusted)
5. **JSON output option** - `THEAUDITOR_LOG_JSON=1` for ELK/Splunk integration
6. **No npm dependency for TS** - Custom lightweight logger (18 statements not worth pino)

---

**Next Step**: Architect reviews and approves/denies this proposal
