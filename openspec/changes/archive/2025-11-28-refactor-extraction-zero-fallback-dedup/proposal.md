# Proposal: Refactor Extraction Pipeline for ZERO FALLBACK Compliance

## Why

TheAuditor's extraction pipeline currently optimizes for "not crashing" instead of "correctness." Silent deduplication in `core_storage.py` and `core_database.py` masks extractor bugs, causing incomplete taint analysis, orphaned call graphs, and false negatives in security findings. For a SAST tool, **a crash is better than a lie**.

### Root Cause Analysis

The extraction pipeline has three fallback patterns that violate CLAUDE.md's ZERO FALLBACK POLICY:

1. **Storage-level deduplication** (`core_storage.py:351-364, 456-469, 615-628`): Silently drops duplicate assignments, returns, and env_var_usage instead of failing on extractor bugs
2. **Database-level deduplication** (`core_database.py:15-24`): `add_file()` checks `if not any(item[0] == path...)` before appending
3. **Database-level deduplication** (`infrastructure_database.py:119-122`): `add_nginx_config()` checks `if not any(b[:3] == batch_key...)` before appending
4. **Dead validation code** (`generated_validators.py`): Validators exist but are never called - worse than no validation

### Impact of Current Behavior

| Symptom | Consequence |
|---------|-------------|
| Duplicate assignment silently dropped | Taint flow from second occurrence is lost |
| Duplicate symbol silently dropped | Callers to that definition become orphans |
| Foreign keys disabled | Referential integrity violations go undetected |

## What Changes

### Phase 1: Truth Serum - Remove Deduplication Fallbacks
- **BREAKING**: Remove silent deduplication in `core_storage.py` (3 locations)
- **BREAKING**: Remove deduplication check in `core_database.py:add_file()`
- Replace `continue` with `raise ValueError` for duplicate detection
- Expected: Pipeline will crash on extractor bugs (this is correct behavior)

### Phase 2: Bouncer - Add Type Assertions at Storage Boundary
- Add explicit `isinstance` checks to all `_store_*` methods in `core_storage.py`
- Validate required fields (name, line, type) are correct types before database insert
- Delete `generated_validators.py` (dead code cleanup)

### Phase 3: Lockdown - Enable Foreign Key Enforcement
- Add `PRAGMA foreign_keys = ON` to `base_database.py`
- Verify and enforce flush order: `files` -> `symbols` -> `assignments` -> `function_calls`
- Translate SQLite integrity errors to actionable developer messages

### NOT Changing
- Schema definitions (no migrations)
- Extractor interfaces (contract unchanged)
- Database table structure
- CLI commands (no user-facing changes)

## Impact

### Affected Specs
- `indexer` capability (new spec created by this change)

### Affected Code
| File | Changes |
|------|---------|
| `theauditor/indexer/storage/core_storage.py` | Remove dedup (3 locations), add type assertions |
| `theauditor/indexer/database/core_database.py` | Remove `add_file` dedup check |
| `theauditor/indexer/database/infrastructure_database.py` | Remove `add_nginx_config` dedup check |
| `theauditor/indexer/database/base_database.py` | Add FK pragma, enforce flush order, enhance errors |
| `theauditor/indexer/schemas/generated_validators.py` | **DELETE** |

### POLYGLOT Impact - Extractors That May Need Fixes
When deduplication is removed, ANY extractor producing duplicates will crash. Use language-appropriate fix patterns:

| Language | Files | AST Pattern |
|----------|-------|-------------|
| TypeScript | `ast_extractors/typescript_impl.py` | `node.get("line"), node.get("kind")` |
| JavaScript | `ast_extractors/javascript/*.js` (10 files) | `node.loc.start.line, node.type` |
| Python | `ast_extractors/python_impl.py` + `python/*.py` (30+ files) | `node.lineno, type(node).__name__` |
| Rust | `ast_extractors/rust_impl.py` | `node.start_point[0], node.type` |
| HCL | `ast_extractors/hcl_impl.py` | tree-sitter convention |

### Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Phase 1 crashes on every file | HIGH | HIGH | Fix extractor bugs immediately per crash |
| FK violations on flush | MEDIUM | MEDIUM | Enforce flush order before enabling FKs |
| Performance regression | LOW | LOW | Assertions are O(1) per item |

### Rollback Strategy
```bash
# Phase 1: Revert storage changes
git checkout HEAD -- theauditor/indexer/storage/core_storage.py
git checkout HEAD -- theauditor/indexer/database/core_database.py

# Phase 3: Disable FK pragma (single line removal)
```
