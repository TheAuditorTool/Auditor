# Tasks: Taint Fidelity System

## Implementation Tasks

### Task 1: Create Fidelity Module
**File**: `theauditor/taint/fidelity.py`
**Status**: DONE

Create the new fidelity module with:
- [x] `TaintFidelityError` exception class
- [x] `create_discovery_manifest()` function
- [x] `create_analysis_manifest()` function
- [x] `create_dedup_manifest()` function
- [x] `create_db_output_receipt()` function
- [x] `create_json_output_receipt()` function
- [x] `reconcile_taint_fidelity()` function with env var check

**Acceptance Criteria**:
- [x] Module imports successfully
- [x] All functions have type hints
- [x] `strict=True` raises `TaintFidelityError` on failure
- [x] `strict=False` logs warning and continues
- [x] `TAINT_FIDELITY_STRICT=0` disables strict mode

---

### Task 2: Add Discovery Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: After `sinks = discovery.filter_framework_safe_sinks(sinks)`
**Status**: DONE

- [x] Import fidelity functions at top of file
- [x] Create discovery manifest after source/sink discovery
- [x] Call `reconcile_taint_fidelity()` with stage="discovery"
- [x] Log fidelity status with source/sink counts

**Acceptance Criteria**:
- [x] Warning logged if sources=0 or sinks=0
- [x] No change to existing discovery logic
- [x] Manifest includes counts from FidelityToken

---

### Task 3: Add Analysis Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: After IFDS loop, before `ifds_analyzer.close()`
**Status**: DONE

- [x] Create analysis manifest after loop
- [x] Include vulnerable_paths count
- [x] Include sanitized_paths count
- [x] Include sinks_analyzed count
- [x] Call `reconcile_taint_fidelity()` with stage="analysis"

**Acceptance Criteria**:
- [x] Error raised if 0 sinks analyzed but sinks exist
- [x] Manifest accurately reflects analysis results
- [x] No change to IFDS algorithm

---

### Task 4: Add Deduplication Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: After `unique_sanitized_paths = deduplicate_paths(all_sanitized_paths)`
**Status**: DONE

- [x] Calculate pre-dedup and post-dedup counts
- [x] Create dedup manifest with removal ratio
- [x] Call `reconcile_taint_fidelity()` with stage="dedup"
- [x] Log warning if removal > 50%

**Acceptance Criteria**:
- [x] Warning only, not error (dedup is expected to reduce)
- [x] Clear message explaining the removal ratio
- [x] No change to deduplication algorithm

---

### Task 5: Add DB Output Checkpoint
**File**: `theauditor/taint/core.py`
**Location**: After `conn.commit()` in `trace_taint()`
**Status**: DONE

- [x] Create DB output receipt with row counts
- [x] Call `reconcile_taint_fidelity()` with stage="db_output"
- [x] Log fidelity status

**Acceptance Criteria**:
- [x] Error raised if manifest_count > 0 but db_rows = 0
- [x] Warning if manifest_count != db_rows
- [x] Accurate row count after commit

---

### Task 6: Add JSON Output Checkpoint
**File**: `theauditor/commands/taint.py`
**Location**: Lines 524-546 (JSON output section)
**Status**: DONE

**Note**: The JSON output is written in the CLI command, not in `core.py`. The spec originally referenced a non-existent `save_taint_analysis()` function. Corrected to actual location.

- [x] Refactor JSON output to use `json.dumps()` + `f.write()` instead of `json.dump()`
- [x] Create JSON output receipt with count and bytes
- [x] Call `reconcile_taint_fidelity()` with stage="json_output"
- [x] Log fidelity status

**Acceptance Criteria**:
- [x] Error raised if paths_to_write > 0 but json_count = 0
- [x] Warning if paths_to_write != json_count
- [x] Accurate byte count for JSON output

---

### Task 7: Write Unit Tests
**File**: `tests/taint/test_fidelity.py`
**Status**: DONE

- [x] Test `create_discovery_manifest()` structure
- [x] Test `create_analysis_manifest()` structure
- [x] Test `create_dedup_manifest()` ratio calculation
- [x] Test `create_db_output_receipt()` structure
- [x] Test `create_json_output_receipt()` structure
- [x] Test `reconcile_taint_fidelity()` with OK result
- [x] Test `reconcile_taint_fidelity()` with WARNING result (dedup)
- [x] Test `reconcile_taint_fidelity()` with FAILED result (strict=True)
- [x] Test `reconcile_taint_fidelity()` with FAILED result (strict=False)
- [x] Test `TAINT_FIDELITY_STRICT=0` env var override
- [x] Test `TaintFidelityError` exception

**Acceptance Criteria**:
- [x] All tests pass (30/30)
- [x] Coverage > 90% for fidelity.py (97% achieved)
- [x] Tests use pytest classes

---

### Task 8: Write Integration Tests
**File**: `tests/taint/test_fidelity_integration.py`
**Status**: DONE

- [x] Test full pipeline simulation (all 5 stages)
- [x] Verify all checkpoints fire (discovery, analysis, dedup, db_output, json_output)
- [x] Test with TAINT_FIDELITY_STRICT=0 env var
- [x] Test that existing tests still pass
- [x] Test realistic scenarios (large codebase, clean codebase, no sources/sinks)

**Acceptance Criteria**:
- [x] Tests simulate realistic pipeline scenarios (12 tests)
- [x] All fidelity statuses verified (OK, WARNING, FAILED)
- [x] No false positives/negatives

---

## Pre-Implementation Verification

**Note**: Line numbers have shifted after implementation. These were the original verification points.

- [x] Discovery checkpoint: after `filter_framework_safe_sinks()` - NOW at core.py:576-585
- [x] Analysis checkpoint: after IFDS loop - NOW at core.py:705-716
- [x] Dedup checkpoint: after `deduplicate_paths()` calls - NOW at core.py:730-734
- [x] DB checkpoint: after `conn.commit()` - NOW at core.py:836-846
- [x] JSON checkpoint: **CORRECTED** - in `commands/taint.py:524-546` (not core.py)
- [x] `FidelityToken` import path: `theauditor.indexer.fidelity_utils.FidelityToken`
- [x] IFDS and FlowResolver are independent engines (no handoff needed)

**Spec Correction (2025-12-09)**: Original spec incorrectly referenced `save_taint_analysis()` in `core.py`. This function never existed. JSON output happens in `commands/taint.py`.

## Dependencies

- No external dependencies
- Uses existing `FidelityToken` from `indexer/fidelity_utils.py`
- Uses existing `logger` from `utils/logging.py`

## Rollout Plan

1. **Phase 1**: Create `taint/fidelity.py`, run unit tests in isolation - DONE
2. **Phase 2**: Add checkpoints 1-4 (Discovery, Analysis, Dedup) in `trace_taint()` - DONE
3. **Phase 3**: Add checkpoint 4a (DB) in `trace_taint()` - DONE
4. **Phase 4**: Add checkpoint 4b (JSON) in `commands/taint.py` - DONE (corrected location)
5. **Phase 5**: Write unit and integration tests - PENDING
6. **Phase 6**: Document in README and release notes - PENDING
