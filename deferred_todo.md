# Deferred Improvements

Architectural improvements identified during validation. Verified against source code **2025-11-24**.

---

## 1. ZERO FALLBACK Policy Violations

**Discovery Date**: 2025-11-22
**Verified**: 2025-11-24
**Priority**: P0 (architectural integrity violation)

### Current Problem

The codebase states "ZERO FALLBACK POLICY" as its most important rule in CLAUDE.md, but violates this extensively.

### Verified Violations

#### 1.1 fce.py:465-476 - Table existence check returns empty list

```python
# Lines 465-476 - ZERO FALLBACK VIOLATION
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='findings_consolidated'
""")
if not cursor.fetchone():
    print("[FCE] Warning: findings_consolidated table not found")
    conn.close()
    return []  # <- Should hard fail, not return empty
```

**Fix**: Remove table check, let query fail naturally with clear error.

#### 1.2 boundary_analyzer.py:88-92,109,126 - Table existence checks

```python
# Lines 88-89 - Checks which tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('python_routes', 'js_routes', 'api_endpoints')")
existing_tables = {row[0] for row in cursor.fetchall()}

# Line 92 - Conditional execution
if 'python_routes' in existing_tables:
    # ... only runs if table exists

# Line 109
if 'js_routes' in existing_tables:

# Line 126
if 'api_endpoints' in existing_tables:
```

**Fix**: Remove table checks, query directly, let missing tables crash.

#### 1.3 commands/blueprint.py - 13 bare `except:` blocks

Lines: 245, 477, 484, 491, 501, 516, 533, 539, 545, 567, 591, 599, 605

All follow this pattern:
```python
try:
    cursor.execute("SELECT ...")
except:
    pass  # <- Swallows ALL errors silently
```

**Fix**: Either use specific exception types or let errors propagate.

#### 1.4 context/query.py - Multiple OperationalError silent handlers

Pattern throughout file:
```python
except sqlite3.OperationalError:
    continue  # <- Silently skips on any DB error
```

**Fix**: Audit each occurrence, let errors propagate where appropriate.

### Philosophical Decision Required

Either:
1. **Enforce the policy** - Remove all fallbacks, let failures crash hard
2. **Abandon the policy** - Remove "ZERO FALLBACK" doctrine from CLAUDE.md

### Estimated Effort

| Task | Hours |
|------|-------|
| Fix fce.py table check | 1 |
| Fix boundary_analyzer.py table checks | 2 |
| Replace 13 bare except blocks in blueprint.py | 4 |
| Audit context/query.py OperationalError handlers | 6 |
| Update tests for new behavior | 8 |
| **TOTAL** | **21 hours** |

---

## 2. Backup Files Deletion

**Discovery Date**: 2025-11-22
**Verified**: 2025-11-24
**Priority**: P1 (dead code in VCS)

### Current Problem

Directory `theauditor/taint/backup/` contains dead backup files:

| File | Size |
|------|------|
| `cfg_integration.py.bak` | 37,210 bytes |
| `interprocedural.py.bak` | 43,982 bytes |
| `interprocedural_cfg.py.bak` | 36,547 bytes |
| `__pycache__/*.pyc` | ~94,000 bytes |

**Total**: ~212KB of dead code committed to VCS.

### Action

```bash
rm -rf theauditor/taint/backup/
```

### Estimated Effort

| Task | Hours |
|------|-------|
| Delete directory | 0.1 |
| **TOTAL** | **0.1 hours** |

---

## 3. OSV Database Download: Move from Setup to Deps Phase

**Discovery Date**: 2025-11-22
**Verified**: 2025-11-24 (venv_install.py lines 790-794)
**Priority**: P2 (nice to have)

### Current Problem

`venv_install.py` hardcodes subdirectory names when searching for lockfiles:

```python
# Lines 790-794 - only checks these 5 directories
for subdir in ['backend', 'frontend', 'server', 'client', 'web']:
    lock = target_dir / subdir / name
```

Projects with non-standard structures (e.g., `rai/raicalc/package-lock.json`) don't get detected.

### Proposed Solution

Split responsibility:
1. **`aud setup-ai`** - Download OSV-Scanner binary ONLY
2. **`aud full` deps phase** - Query database for lockfiles, download databases on first run

### Estimated Effort

| Task | Hours |
|------|-------|
| Move DB download to deps phase | 2 |
| Query lockfiles from database | 1 |
| Handle first-run DB download | 2 |
| Test on multiple projects | 2 |
| **TOTAL** | **7 hours** |

### Workaround (Current)

Hardcoded list covers ~95% of monorepo structures. Online mode works as fallback.

---

## 4. Monolithic Files Refactoring

**Discovery Date**: 2025-11-22
**Verified**: 2025-11-24
**Priority**: P3 (maintainability)

### Current Problem

Four files exceed reasonable size thresholds:

| File | Lines (Verified) |
|------|------------------|
| `theauditor/indexer/storage/python_storage.py` | 2,486 |
| `theauditor/fce.py` | 1,845 |
| `theauditor/pipelines.py` | 1,805 |
| `theauditor/commands/query.py` | 1,237 |

### Proposed Refactoring (When Opportunity Arises)

**pipelines.py** - Split into pipeline_stages.py + pipeline_core.py
**fce.py** - Split into fce_loaders.py + fce_correlation.py + fce_core.py
**python_storage.py** - Extract method groups into mixins
**query.py** - Break into subcommand modules

### Estimated Effort

| Task | Hours |
|------|-------|
| pipelines.py refactor | 16 |
| fce.py refactor | 12 |
| python_storage.py refactor | 20 |
| query.py refactor | 8 |
| **TOTAL** | **56 hours** |

---

## 5. Test Coverage for Security Rules

**Discovery Date**: 2025-11-22
**Verified**: 2025-11-24
**Priority**: P3 (quality)

### Current Problem

- **114 rule files** in `theauditor/rules/`
- **1 test file** specifically testing rules
- Coverage: ~1%

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

---

## RESOLVED

### Polyglot Monorepo Support in manifest_parser.py

**Status**: RESOLVED (2025-11-23)

Added Cargo.toml parsing, workspace dependency resolution, and monorepo manifest discovery. Validated on project_anarchy with 8/8 Rust files indexed and 19 framework detections.

---

## REMOVED (Stale/False Claims)

The following items were in the original document but verified as **FALSE** on 2025-11-24:

1. **extraction.py removal** - File already deleted, does not exist
2. **Dead `_build_function_ranges()` in 7 files** - Function does not exist anywhere in codebase
3. **input_validation_analyzer.py table check** - Wrong filename (actual: boundary_analyzer.py)

---

**File Created**: 2025-11-22
**Last Verified**: 2025-11-24 (full source code audit by Opus)
