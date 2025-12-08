# Tasks: Taint Fidelity System

## Implementation Tasks

### Task 1: Create Fidelity Module
**File**: `theauditor/taint/fidelity.py`
**Status**: PENDING

Create the new fidelity module with:
- [ ] `TaintFidelityError` exception class
- [ ] `create_discovery_manifest()` function
- [ ] `create_analysis_manifest()` function
- [ ] `create_dedup_manifest()` function
- [ ] `create_db_output_receipt()` function
- [ ] `create_json_output_receipt()` function
- [ ] `reconcile_taint_fidelity()` function with env var check

**Acceptance Criteria**:
- Module imports successfully
- All functions have type hints
- `strict=True` raises `TaintFidelityError` on failure
- `strict=False` logs warning and continues
- `TAINT_FIDELITY_STRICT=0` disables strict mode

---

### Task 2: Add Discovery Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: Line 567, insert after line 566 `sinks = discovery.filter_framework_safe_sinks(sinks)`
**Status**: PENDING

- [ ] Import fidelity functions at top of file
- [ ] Create discovery manifest after source/sink discovery
- [ ] Call `reconcile_taint_fidelity()` with stage="discovery"
- [ ] Log fidelity status with source/sink counts

**Acceptance Criteria**:
- Warning logged if sources=0 or sinks=0
- No change to existing discovery logic
- Manifest includes counts from FidelityToken

---

### Task 3: Add Analysis Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: Line 686, insert after line 685 `all_sanitized_paths.extend(sanitized)`, before line 686 `ifds_analyzer.close()`
**Status**: PENDING

- [ ] Create analysis manifest after loop
- [ ] Include vulnerable_paths count
- [ ] Include sanitized_paths count
- [ ] Include sinks_analyzed count
- [ ] Call `reconcile_taint_fidelity()` with stage="analysis"

**Acceptance Criteria**:
- Error raised if 0 sinks analyzed but sinks exist
- Manifest accurately reflects analysis results
- No change to IFDS algorithm

---

### Task 4: Add Deduplication Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: Line 697, insert after line 696 `unique_sanitized_paths = deduplicate_paths(all_sanitized_paths)`
**Status**: PENDING

- [ ] Calculate pre-dedup and post-dedup counts
- [ ] Create dedup manifest with removal ratio
- [ ] Call `reconcile_taint_fidelity()` with stage="dedup"
- [ ] Log warning if removal > 50%

**Acceptance Criteria**:
- Warning only, not error (dedup is expected to reduce)
- Clear message explaining the removal ratio
- No change to deduplication algorithm

---

### Task 5: Add DB Output Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: Line 797, insert after line 796 `conn.commit()` in `trace_taint()`
**Status**: PENDING

- [ ] Create DB output receipt with row counts
- [ ] Call `reconcile_taint_fidelity()` with stage="db_output"
- [ ] Log fidelity status

**Acceptance Criteria**:
- Error raised if manifest_count > 0 but db_rows = 0
- Warning if manifest_count != db_rows
- Accurate row count after commit

---

### Task 6: Refactor save_taint_analysis() with JSON Output Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: Lines 955-973, replace entire `save_taint_analysis()` function
**Status**: PENDING

**Important**: This is a SEPARATE function from `trace_taint()`. The current implementation uses `json.dump()` directly to file handle, which doesn't allow capturing byte count. Must refactor to use `json.dumps()` + `f.write()` pattern.

- [ ] Refactor `save_taint_analysis()` to use `json.dumps()` + `f.write()` instead of `json.dump()`
- [ ] Create JSON output receipt with count and bytes
- [ ] Call `reconcile_taint_fidelity()` with stage="json_output"
- [ ] Log fidelity status

**Acceptance Criteria**:
- Error raised if paths_to_write > 0 but json_count = 0
- Warning if paths_to_write != json_count
- Accurate byte count for JSON output

---

### Task 7: Write Unit Tests
**File**: `tests/taint/test_fidelity.py`
**Status**: PENDING

- [ ] Test `create_discovery_manifest()` structure
- [ ] Test `create_analysis_manifest()` structure
- [ ] Test `create_dedup_manifest()` ratio calculation
- [ ] Test `create_db_output_receipt()` structure
- [ ] Test `create_json_output_receipt()` structure
- [ ] Test `reconcile_taint_fidelity()` with OK result
- [ ] Test `reconcile_taint_fidelity()` with WARNING result (dedup)
- [ ] Test `reconcile_taint_fidelity()` with FAILED result (strict=True)
- [ ] Test `reconcile_taint_fidelity()` with FAILED result (strict=False)
- [ ] Test `TAINT_FIDELITY_STRICT=0` env var override
- [ ] Test `TaintFidelityError` exception

**Acceptance Criteria**:
- All tests pass
- Coverage > 90% for fidelity.py
- Tests use pytest fixtures

---

### Task 8: Write Integration Tests
**File**: `tests/taint/test_fidelity_integration.py`
**Status**: PENDING

- [ ] Test full pipeline with test project
- [ ] Verify all 4 checkpoints fire
- [ ] Test with TAINT_FIDELITY_STRICT=0 env var
- [ ] Test that existing tests still pass

**Acceptance Criteria**:
- Tests use real test project fixture
- All fidelity statuses verified
- No false positives/negatives

---

## Pre-Implementation Verification

These have been verified during spec creation (2025-12-08):

- [x] `core.py:566` - Discovery: line 566 is `sinks = discovery.filter_framework_safe_sinks(sinks)`
- [x] `core.py:685-686` - Analysis: line 685 is `all_sanitized_paths.extend(sanitized)`, line 686 is `ifds_analyzer.close()`
- [x] `core.py:694-696` - Dedup: lines 694 and 696 are `deduplicate_paths()` calls
- [x] `core.py:796` - DB: line 796 is `conn.commit()`
- [x] `core.py:971-972` - JSON: line 971-972 is `json.dump()` inside `save_taint_analysis()`
- [x] `FidelityToken` import path: `theauditor.indexer.fidelity_utils.FidelityToken`
- [x] IFDS and FlowResolver are independent engines (no handoff needed)
- [x] `save_taint_analysis()` uses `json.dump()` directly - must refactor to `json.dumps()` + `f.write()` for byte tracking

## Dependencies

- No external dependencies
- Uses existing `FidelityToken` from `indexer/fidelity_utils.py`
- Uses existing `logger` from `utils/logging.py`

## Rollout Plan

1. **Phase 1**: Create `taint/fidelity.py`, run unit tests in isolation
2. **Phase 2**: Add checkpoints 1-3 in `trace_taint()`
3. **Phase 3**: Add checkpoint 4a (DB) in `trace_taint()`
4. **Phase 4**: Add checkpoint 4b (JSON) in `save_taint_analysis()`
5. **Phase 5**: Full integration test on plant/plantflow
6. **Phase 6**: Document in README and release notes
