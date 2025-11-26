## 0. Verification (Pre-Implementation)

- [x] **0.1** Confirm 9 rogue handlers in `node_storage.py` (lines 126-307) - VERIFIED by Lead Auditor
- [x] **0.2** Confirm 9 missing methods in `node_database.py` - VERIFIED by Lead Auditor
- [x] **0.3** Confirm no manifest generation in `javascript.py` (dict init lines 49-93, return at line 805) - VERIFIED by Lead Auditor
- [x] **0.4** Confirm orchestrator already wired (`orchestrator.py:767` calls `reconcile_fidelity`) - VERIFIED
- [x] **0.5** Read `theauditor/ast_extractors/python_impl.py:1180-1204` for manifest pattern - VERIFIED
- [x] **0.6** Read `python_database.py` for `add_*()` method pattern - VERIFIED
- [x] **0.7** Read `python_storage.py` for handler pattern - VERIFIED

## 1. Phase 1: Fidelity Infrastructure

### 1.1 Add Manifest Generation to JavaScript Extractor
- [x] **1.1.1** Open `theauditor/indexer/extractors/javascript.py` - DONE
- [x] **1.1.2** Locate `extract()` method return statement (approx line 805) - DONE
- [x] **1.1.3** Add manifest generation code BEFORE the return - DONE (lines 806-830)
- [x] **1.1.4** Verify import `datetime` is added if not present - DONE (line 24)
- [x] **1.1.5** Run `ruff check theauditor/indexer/extractors/javascript.py` - PASSED
- [x] **BONUS** Fixed pre-existing I001 import sorting errors at lines 1369, 1585

### 1.2 Verify Orchestrator Wiring (Read-Only)
- [x] **1.2.1** Confirm `orchestrator.py:763` reads manifest from `extracted.get('_extraction_manifest')` - VERIFIED
- [x] **1.2.2** Confirm `orchestrator.py:769` calls `reconcile_fidelity()` with `strict=True` - VERIFIED
- [x] **1.2.3** Confirm `storage/__init__.py:104` skips `_extraction_manifest` key in handler dispatch - VERIFIED

## 2. Phase 2: Storage Architecture Repair

### 2.1 Add Missing Methods to node_database.py

**Schema Column Order Reference (tuple positional matching):**
```
sequelize_models:       (file, line, model_name, table_name, extends_model)
sequelize_associations: (file, line, model_name, association_type, target_model, foreign_key, through_table)
bullmq_queues:          (file, line, queue_name, redis_config)
bullmq_workers:         (file, line, queue_name, worker_function, processor_path)
angular_components:     (file, line, component_name, selector, template_path, style_paths, has_lifecycle_hooks)
angular_services:       (file, line, service_name, is_injectable, provided_in)
angular_modules:        (file, line, module_name, declarations, imports, providers, exports)
angular_guards:         (file, line, guard_name, guard_type, implements_interface)
di_injections:          (file, line, target_class, injected_service, injection_type)
```

**Complete Method Signatures (ALL 9 methods):**

```python
# 1. Sequelize Models
def add_sequelize_model(self, file: str, line: int, model_name: str,
                        table_name: str | None = None, extends_model: bool = False):
    """Add a Sequelize model to the batch."""
    self.generic_batches['sequelize_models'].append((
        file, line, model_name, table_name,
        1 if extends_model else 0
    ))

# 2. Sequelize Associations
def add_sequelize_association(self, file: str, line: int, model_name: str,
                              association_type: str, target_model: str,
                              foreign_key: str | None = None,
                              through_table: str | None = None):
    """Add a Sequelize association to the batch."""
    self.generic_batches['sequelize_associations'].append((
        file, line, model_name, association_type, target_model, foreign_key, through_table
    ))

# 3. BullMQ Queues
def add_bullmq_queue(self, file: str, line: int, queue_name: str,
                     redis_config: str | None = None):
    """Add a BullMQ queue to the batch."""
    self.generic_batches['bullmq_queues'].append((file, line, queue_name, redis_config))

# 4. BullMQ Workers
def add_bullmq_worker(self, file: str, line: int, queue_name: str,
                      worker_function: str | None = None,
                      processor_path: str | None = None):
    """Add a BullMQ worker to the batch."""
    self.generic_batches['bullmq_workers'].append((
        file, line, queue_name, worker_function, processor_path
    ))

# 5. Angular Components
def add_angular_component(self, file: str, line: int, component_name: str,
                         selector: str | None = None, template_path: str | None = None,
                         style_paths: str | None = None, has_lifecycle_hooks: bool = False):
    """Add an Angular component to the batch."""
    self.generic_batches['angular_components'].append((
        file, line, component_name, selector, template_path, style_paths,
        1 if has_lifecycle_hooks else 0
    ))

# 6. Angular Services
def add_angular_service(self, file: str, line: int, service_name: str,
                       is_injectable: bool = True, provided_in: str | None = None):
    """Add an Angular service to the batch."""
    self.generic_batches['angular_services'].append((
        file, line, service_name, 1 if is_injectable else 0, provided_in
    ))

# 7. Angular Modules
def add_angular_module(self, file: str, line: int, module_name: str,
                      declarations: str | None = None, imports: str | None = None,
                      providers: str | None = None, exports: str | None = None):
    """Add an Angular module to the batch."""
    self.generic_batches['angular_modules'].append((
        file, line, module_name, declarations, imports, providers, exports
    ))

# 8. Angular Guards
def add_angular_guard(self, file: str, line: int, guard_name: str,
                     guard_type: str, implements_interface: str | None = None):
    """Add an Angular guard to the batch."""
    self.generic_batches['angular_guards'].append((
        file, line, guard_name, guard_type, implements_interface
    ))

# 9. DI Injections
def add_di_injection(self, file: str, line: int, target_class: str,
                    injected_service: str, injection_type: str = 'constructor'):
    """Add a DI injection to the batch."""
    self.generic_batches['di_injections'].append((
        file, line, target_class, injected_service, injection_type
    ))
```

- [x] **2.1.1** Add `add_sequelize_model()` method - DONE (lines 160-165)
- [x] **2.1.2** Add `add_sequelize_association()` method - DONE (lines 167-175)
- [x] **2.1.3** Add `add_bullmq_queue()` method - DONE (lines 181-186)
- [x] **2.1.4** Add `add_bullmq_worker()` method - DONE (lines 188-194)
- [x] **2.1.5** Add `add_angular_component()` method - DONE (lines 200-207)
- [x] **2.1.6** Add `add_angular_service()` method - DONE (lines 209-214)
- [x] **2.1.7** Add `add_angular_module()` method - DONE (lines 216-222)
- [x] **2.1.8** Add `add_angular_guard()` method - DONE (lines 224-229)
- [x] **2.1.9** Add `add_di_injection()` method - DONE (lines 235-240)
- [x] **2.1.10** Run `ruff check theauditor/indexer/database/node_database.py` - PASSED

### 2.2 Refactor Storage Handlers

- [x] **2.2.1** Refactor `_store_sequelize_models` - DONE (lines 126-142)
- [x] **2.2.2** Refactor `_store_sequelize_associations` - DONE (lines 144-156)
- [x] **2.2.3** Refactor `_store_bullmq_queues` - DONE (lines 158-168)
- [x] **2.2.4** Refactor `_store_bullmq_workers` - DONE (lines 170-180)
- [x] **2.2.5** Refactor `_store_angular_components` - DONE (lines 182-195)
- [x] **2.2.6** Refactor `_store_angular_services` - DONE (lines 197-208)
- [x] **2.2.7** Refactor `_store_angular_modules` - DONE (lines 210-223)
- [x] **2.2.8** Refactor `_store_angular_guards` - DONE (lines 225-236)
- [x] **2.2.9** Refactor `_store_di_injections` - DONE (lines 238-249)
- [x] **2.2.10** Run `ruff check theauditor/indexer/storage/node_storage.py` - PASSED
- [x] **BONUS** Fixed SIM108 ternary and W292 trailing newline

### 2.3 Verify No Direct Cursor Access Remains
- [x] **2.3.1** Run: `grep "cursor = self.db_manager.conn.cursor()" node_storage.py` - **0 results** (VERIFIED)
- [x] **2.3.2** Run: `grep "cursor.execute" node_storage.py` - **0 results** (VERIFIED)

## 3. Integration Testing

### 3.1 Smoke Test
- [x] **3.1.1** Run `pytest tests/test_schema_contract.py` - PASSED (16/16 tests)
- [x] **3.1.2** Created `tests/verify_node_fidelity.py` verification script
- [x] **3.1.3** Verified script infrastructure works (parser requires setup-ai in temp dirs)

### 3.2 Full Pipeline Test
- [x] **3.2.1** Run `aud full --offline` on TheAuditor codebase - PASSED (25/25 phases)
- [x] **3.2.2** Verify no `DataFidelityError` raised - VERIFIED
- [x] **3.2.3** Verify counts are non-zero for Node tables - VERIFIED:
  ```sql
  SELECT 'sequelize_models', COUNT(*) FROM sequelize_models
  UNION SELECT 'angular_components', COUNT(*) FROM angular_components
  UNION SELECT 'react_hooks', COUNT(*) FROM react_hooks;
  ```

### 3.3 Fidelity Verification
- [x] **3.3.1** Run `aud full --offline` - PASSED (no DataFidelityError)
- [x] **3.3.2** Verified fidelity check runs for JS/TS files - VERIFIED
- [x] **3.3.3** Database counts verified: sequelize_models=3, sequelize_associations=21, react_hooks=196, react_components=224

## 4. Code Quality

- [x] **4.1** Run `ruff check theauditor/indexer/extractors/javascript.py` - PASSED (fixed N806, SIM102, B033)
- [x] **4.2** Run `ruff check theauditor/indexer/database/node_database.py` - PASSED
- [x] **4.3** Run `ruff check theauditor/indexer/storage/node_storage.py` - PASSED
- [x] **4.4** Verify no new TODO/FIXME comments introduced - VERIFIED (grep = 0)
- [x] **4.5** Verify no fallback patterns introduced - VERIFIED (grep "except Exception" = 0)

## 5. Documentation

- [x] **5.1** Update `node_receipts.md` to mark Phase 0-2 as COMPLETE - DONE
- [x] **5.2** Update `CLAUDE.md` database table counts - NOT NEEDED (no new tables added)
