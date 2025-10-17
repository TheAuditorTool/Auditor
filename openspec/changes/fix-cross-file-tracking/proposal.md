# Fix Cross-File Taint Tracking

## Why

Cross-file taint tracking infrastructure was added in the 9-hour refactor (worklist, file tracking, cross-file guards removed) but **0 cross-file paths are detected** out of 880 total vulnerabilities.

**Root Cause**: Symbol lookup query filters for `type = 'function'` only, but 92.4% of symbols (22,427/24,375) have `type = 'call'`. JavaScript/TypeScript method calls like `db.query`, `app.post`, `res.send` are filtered out. Query returns NULL → silent fallback to same-file → cross-file tracking never happens.

**Evidence**: Database validation shows query succeeds 25% of time (broken) vs 100% (fixed). Zero inter-procedural step types (`argument_pass`, `return_flow`, `call`) exist in taint_paths.

## What Changes

- **Fix symbol query** (2 locations): Change `type = 'function'` to `type IN ('function', 'call', 'property')` in `interprocedural.py:132` and `interprocedural.py:453`
- **Remove silent fallback** (2 locations): Change `callee_file = callee_location[0] if callee_location else current_file` to hard failure with debug logging
- **BREAKING**: Enforces CLAUDE.md prohibition on fallback logic - system MUST crash if symbols table incomplete

**Impact**: Enables true cross-file tracking for Controller → Service → Model patterns. Fixes 75% symbol lookup failures.

## Impact

- **Affected specs**: `taint-analysis` (cross-file tracking)
- **Affected code**:
  - `theauditor/taint/interprocedural.py:130-137` (flow-insensitive)
  - `theauditor/taint/interprocedural.py:452-456` (CFG-based)
- **Breaking changes**: **YES** - removes silent fallback, will expose indexer bugs
- **Performance impact**: Neutral (same analysis paths, better accuracy)
- **False positives**: May increase temporarily if indexer has gaps

## Non-Goals

- Fix indexer to populate all symbols (separate issue if needed)
- Add cross-file caching (performance optimization, not correctness)
- Support dynamic imports/requires (out of scope)
