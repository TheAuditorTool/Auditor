## Why

Node.js extraction has **ZERO DATA FIDELITY CONTROLS**. 9 of 17 storage handlers bypass the database mixin and use direct `cursor.execute()` - the exact pattern that caused 22MB silent data loss in Python (fixed in `python-extractor-consolidation-fidelity` ticket). Node has this bug RIGHT NOW.

**Evidence from Lead Auditor Verification (2025-11-26):**
- `node_storage.py` lines 126-307: 9 handlers access `self.db_manager.conn.cursor()` directly
- `node_database.py`: Missing 9 corresponding `add_*()` methods
- `javascript.py:49-93` initializes result dict, `line 805` returns it - NO manifest generation
- Partial counting creates FALSE CONFIDENCE - items counted but inserts fail silently

**Risk:** Production data loss with zero detection mechanism. Same 22MB bug that hit Python.

## What Changes

### Phase 1: Fidelity Infrastructure (The Accountant)
1. **Modify `javascript.py`** - Add `_extraction_manifest` generation at end of `extract()`
   - Copy exact pattern from `theauditor/ast_extractors/python_impl.py:1180-1204`
   - Count all list items, add `_total`, `_timestamp`, `_file` metadata

2. **Verify orchestrator wiring** - `orchestrator.py:767` already calls `reconcile_fidelity()` if manifest exists
   - Node uses same `_store_extracted_data()` method as Python
   - Simply adding manifest in `javascript.py` activates the check automatically

### Phase 2: Storage Architecture Repair (The Plumbing)
1. **Add 9 missing methods to `node_database.py`:**
   - `add_sequelize_model()` - use `self.generic_batches['sequelize_models']`
   - `add_sequelize_association()` - use `self.generic_batches['sequelize_associations']`
   - `add_bullmq_queue()` - use `self.generic_batches['bullmq_queues']`
   - `add_bullmq_worker()` - use `self.generic_batches['bullmq_workers']`
   - `add_angular_component()` - use `self.generic_batches['angular_components']`
   - `add_angular_service()` - use `self.generic_batches['angular_services']`
   - `add_angular_module()` - use `self.generic_batches['angular_modules']`
   - `add_angular_guard()` - use `self.generic_batches['angular_guards']`
   - `add_di_injection()` - use `self.generic_batches['di_injections']`

2. **Refactor 9 handlers in `node_storage.py`:**
   - `_store_sequelize_models` (line 126) -> call `self.db_manager.add_sequelize_model()`
   - `_store_sequelize_associations` (line 152) -> call `self.db_manager.add_sequelize_association()`
   - `_store_bullmq_queues` (line 173) -> call `self.db_manager.add_bullmq_queue()`
   - `_store_bullmq_workers` (line 191) -> call `self.db_manager.add_bullmq_worker()`
   - `_store_angular_components` (line 210) -> call `self.db_manager.add_angular_component()`
   - `_store_angular_services` (line 231) -> call `self.db_manager.add_angular_service()`
   - `_store_angular_modules` (line 250) -> call `self.db_manager.add_angular_module()`
   - `_store_angular_guards` (line 271) -> call `self.db_manager.add_angular_guard()`
   - `_store_di_injections` (line 290) -> call `self.db_manager.add_di_injection()`

3. **Remove ALL direct cursor access** from `node_storage.py`
   - Grep for `cursor = self.db_manager.conn.cursor()` - should return 0 results after refactor

## Impact

### Affected Files (5)
| File | Purpose | Changes |
|------|---------|---------|
| `theauditor/indexer/extractors/javascript.py` | JS orchestrator | Add manifest generation (~25 lines) |
| `theauditor/indexer/database/node_database.py` | Node DB mixin | Add 9 `add_*()` methods (~150 lines) |
| `theauditor/indexer/storage/node_storage.py` | Node storage handlers | Refactor 9 handlers (~90 lines changed) |
| `theauditor/indexer/fidelity.py` | Fidelity control | NO CHANGES (already implemented) |
| `theauditor/indexer/orchestrator.py` | Main orchestrator | NO CHANGES (already wired) |

### Affected Specs
- `indexer` capability - MODIFIED (fidelity control extended to Node pipeline)

### Risk Assessment
- **HIGH** - This changes the data flow for ALL Node/JS/TS extraction
- **Mitigation:** Crash-first design - install fidelity FIRST so it catches our migration mistakes
- **Rollback:** Git revert single commit

## Definition of Done

- [x] `javascript.py` generates `_extraction_manifest` (count verification) - DONE (lines 806-830)
- [x] All 9 storage handlers call `db_manager.add_*()` (grep for cursor.execute = 0 results) - VERIFIED
- [x] All 9 `add_*()` methods use `self.generic_batches` (batching verification) - VERIFIED
- [x] `aud full --offline` on Node-heavy codebase (React+Express) completes without DataFidelityError - PASSED
- [x] `ruff check theauditor/indexer/` passes - PASSED (fixed N806, SIM102, B033 in javascript.py)

## References

- Pre-implementation briefing: `node_receipts.md` (root)
- Python reference implementation: `python-extractor-consolidation-fidelity` (archived)
- teamsop.md v4.20 compliance: VERIFIED
- Prime Directive compliance: VERIFIED (Lead Auditor verification completed 2025-11-26)
