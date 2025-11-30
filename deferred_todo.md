# Deferred Improvements

Architectural improvements identified during validation. Last verified **2025-11-30**.

---

## 1. Test Coverage for Security Rules

**Discovery Date**: 2025-11-22
**Verified**: 2025-11-30
**Priority**: P3 (quality) - PARTIALLY ADDRESSED

### Current State

- **114 rule files** in `theauditor/rules/`
- **3 test files** for new language security rules:
  - `tests/test_bash_security_rules.py` - 25 tests (injection, quoting, dangerous patterns)
  - `tests/test_go_*.py` - Go security rule coverage
  - `tests/test_rust_*.py` - Rust security rule coverage

### Remaining Gap

Legacy Python/Node security rules still lack dedicated tests:
- SQL injection detection
- XSS detection
- Authentication bypass
- Hardcoded secrets
- Taint flow

### Status

**PARTIALLY ADDRESSED** - New language implementations (Bash/Go/Rust) have security rule tests. Legacy rules remain untested pending engine rewrite.

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

## Known Issues (Verified 2025-11-30)

### Database
1. **Foreign keys disabled**: SQLite defaults to OFF, needs `PRAGMA foreign_keys = ON` added to base_database.py (see OpenSpec: refactor-extraction-zero-fallback-dedup)

### Extraction Bugs (Must Fix)
2. **TypeScript interfaces**: BUG - `core_language.js:390` only extracts `ClassDeclaration`, never `InterfaceDeclaration`. Fix: add interface check, set `type: "interface"`. Also fix `typescript_impl_structure.py:848` (hardcodes "class") and `javascript.py:301` (overwrites type).

### Extraction Gaps (Future Work)
3. **Redux**: Not extracted - stores, actions, reducers, selectors
4. **Webpack/Vite configs**: Not extracted - aliases, entry points, loaders
5. **NestJS**: Not implemented (0 tables exist)
6. **FastAPI dependencies**: Needs verification when FastAPI projects indexed
