# Deferred Improvements

Architectural improvements identified during validation. Last verified **2025-11-28**.

---

## 1. Test Coverage for Security Rules

**Discovery Date**: 2025-11-22
**Verified**: 2025-11-28
**Priority**: P3 (quality) - DEFERRED pending engine rewrite

### Current Problem

- **114 rule files** in `theauditor/rules/`
- **0 test files** specifically testing rules
- Coverage: 0%

### Scope

Need tests for critical security rules:
- SQL injection detection
- XSS detection
- Authentication bypass
- Hardcoded secrets
- Taint flow

### Estimated Effort

| Task | Hours |
|------|-------|
| Test framework setup | 8 |
| Tests for 20 critical rules | 40 |
| Tests for remaining rules | 120 |
| **TOTAL** | **168 hours** |

### Status

**DEFERRED** - Engine rewrite planned; tests will be written after new architecture is finalized.

---

## RESOLVED (2025-11-28)

### boundary_analyzer.py table existence checks

**Status**: RESOLVED

Table existence checks removed. Now queries `python_routes`, `js_routes`, and `api_endpoints` directly without checking sqlite_master first.

### blueprint.py exception handlers

**Status**: RESOLVED

All 22+ `except Exception:` blocks removed. Queries now fail loud on errors. Only `sqlite3.OperationalError` handlers remain for genuinely optional tables (frameworks, refactor_history, dependency_versions).

### Backup files directory

**Status**: RESOLVED

Directory `theauditor/taint/backup/` deleted (contained `.bak` files and `__pycache__`).

### venv_install.py hardcoded subdirectories

**Status**: RESOLVED

Replaced hardcoded subdirectory list with glob patterns. Now uses `target_dir.glob("*/{lockfile}")` to find lockfiles in any first-level subdirectory, handling non-standard monorepo structures.

### fce.py table existence check

**Status**: RESOLVED

The table existence check no longer exists in fce.py. The file now explicitly states "NO FALLBACKS ALLOWED" in its header.

### context/query.py OperationalError handlers

**Status**: RESOLVED

No `OperationalError` handlers exist in `theauditor/context/query.py`. The 14 claimed handlers have been removed.

### Monolithic Files Refactoring

**Status**: RESOLVED - Files significantly refactored

| File | Old Lines | Current Lines | Reduction |
|------|-----------|---------------|-----------|
| `python_storage.py` | 2,486 | 1,033 | -58% |
| `fce.py` | 1,845 | 1,609 | -13% |
| `pipelines.py` | 1,805 | 1,677 | -7% |
| `commands/query.py` | 1,237 | 491 | -60% |

All files now below 1,700 lines. No longer a priority issue.

### Polyglot Monorepo Support in manifest_parser.py

**Status**: RESOLVED

Added Cargo.toml parsing, workspace dependency resolution, and monorepo manifest discovery.

---

## REMOVED (Stale/False Claims)

The following items were verified as **FALSE** on 2025-11-28:

1. **fce.py:465-476 table check** - Code no longer exists
2. **context/query.py OperationalError handlers** - Zero handlers found
3. **extraction.py removal** - File already deleted
4. **Dead `_build_function_ranges()` in 7 files** - Function does not exist
5. **input_validation_analyzer.py** - Wrong filename (actual: boundary_analyzer.py)
6. **Empty tables claim** - python_celery_task_calls and python_crypto_operations tables DON'T EXIST (not empty)
7. **1,137/1,138 unclassified flows** - taint_flows table has 0 rows total
8. **NestJS 3 tables exist** - Zero NestJS tables exist in current schema

---

## Known Issues (Verified 2025-11-28)

### Windows
1. **Path handling**: Always use full Windows paths with drive letters

### Database
2. **Foreign keys**: PRAGMA foreign_keys = 0 by design
3. **TypeScript interfaces**: Intentionally excluded from extraction (0 tables)

### Framework Extraction Gaps (Future Work)
4. **Redux**: Not extracted - stores, actions, reducers, selectors
5. **Webpack/Vite configs**: Not extracted - aliases, entry points, loaders
6. **NestJS**: Not implemented (0 tables exist)
7. **FastAPI dependencies**: Needs verification when FastAPI projects indexed
