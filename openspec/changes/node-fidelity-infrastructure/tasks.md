## 0. Verification (Pre-Implementation)

- [x] **0.1** Confirm 9 rogue handlers in `node_storage.py` (lines 126-307) - VERIFIED by Lead Auditor
- [x] **0.2** Confirm 9 missing methods in `node_database.py` - VERIFIED by Lead Auditor
- [x] **0.3** Confirm no manifest generation in `javascript.py` line 93 - VERIFIED by Lead Auditor
- [x] **0.4** Confirm orchestrator already wired (`orchestrator.py:767` calls `reconcile_fidelity`) - VERIFIED
- [x] **0.5** Read `python_impl.py:1180-1204` for manifest pattern - VERIFIED
- [x] **0.6** Read `python_database.py` for `add_*()` method pattern - VERIFIED
- [x] **0.7** Read `python_storage.py` for handler pattern - VERIFIED

## 1. Phase 1: Fidelity Infrastructure

### 1.1 Add Manifest Generation to JavaScript Extractor
- [ ] **1.1.1** Open `theauditor/indexer/extractors/javascript.py`
- [ ] **1.1.2** Locate `extract()` method return statement (approx line 805)
- [ ] **1.1.3** Add manifest generation code BEFORE the return:
  ```python
  # DATA FIDELITY: GENERATE EXTRACTION MANIFEST
  manifest = {}
  total_items = 0

  for key, value in result.items():
      if key.startswith('_') or not isinstance(value, list):
          continue
      count = len(value)
      if count > 0:
          manifest[key] = count
          total_items += count

  from datetime import datetime
  manifest['_total'] = total_items
  manifest['_timestamp'] = datetime.utcnow().isoformat()
  manifest['_file'] = file_info.get('path', 'unknown')

  result['_extraction_manifest'] = manifest
  ```
- [ ] **1.1.4** Verify import `datetime` is added if not present
- [ ] **1.1.5** Run `ruff check theauditor/indexer/extractors/javascript.py`

### 1.2 Verify Orchestrator Wiring (Read-Only)
- [ ] **1.2.1** Confirm `orchestrator.py:763` reads manifest from `extracted.get('_extraction_manifest')`
- [ ] **1.2.2** Confirm `orchestrator.py:769` calls `reconcile_fidelity()` with `strict=True`
- [ ] **1.2.3** Confirm `storage/__init__.py:103` skips `_extraction_manifest` key in handler dispatch

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

- [ ] **2.1.1** Add `add_sequelize_model()` method
- [ ] **2.1.2** Add `add_sequelize_association()` method
- [ ] **2.1.3** Add `add_bullmq_queue()` method
- [ ] **2.1.4** Add `add_bullmq_worker()` method
- [ ] **2.1.5** Add `add_angular_component()` method
- [ ] **2.1.6** Add `add_angular_service()` method
- [ ] **2.1.7** Add `add_angular_module()` method
- [ ] **2.1.8** Add `add_angular_guard()` method
- [ ] **2.1.9** Add `add_di_injection()` method
- [ ] **2.1.10** Run `ruff check theauditor/indexer/database/node_database.py`

### 2.2 Refactor Storage Handlers

**Handler Pattern (before -> after):**

BEFORE (WRONG - direct cursor):
```python
def _store_sequelize_models(self, file_path: str, sequelize_models: list, jsx_pass: bool):
    cursor = self.db_manager.conn.cursor()
    for model in sequelize_models:
        cursor.execute("""INSERT...""", (...))
        self.counts['sequelize_models'] += 1
```

AFTER (CORRECT - batched method):
```python
def _store_sequelize_models(self, file_path: str, sequelize_models: list, jsx_pass: bool):
    for model in sequelize_models:
        if isinstance(model, str):
            model_data = {'model_name': model, 'line': 0}
        else:
            model_data = model
        self.db_manager.add_sequelize_model(
            file_path,
            model_data.get('line', 0),
            model_data.get('model_name', ''),
            model_data.get('table_name'),
            model_data.get('extends_model', False)
        )
        self.counts['sequelize_models'] = self.counts.get('sequelize_models', 0) + 1
```

- [ ] **2.2.1** Refactor `_store_sequelize_models` (line 126)
- [ ] **2.2.2** Refactor `_store_sequelize_associations` (line 152)
- [ ] **2.2.3** Refactor `_store_bullmq_queues` (line 173)
- [ ] **2.2.4** Refactor `_store_bullmq_workers` (line 191)
- [ ] **2.2.5** Refactor `_store_angular_components` (line 210)
- [ ] **2.2.6** Refactor `_store_angular_services` (line 231)
- [ ] **2.2.7** Refactor `_store_angular_modules` (line 250)
- [ ] **2.2.8** Refactor `_store_angular_guards` (line 271)
- [ ] **2.2.9** Refactor `_store_di_injections` (line 290)
- [ ] **2.2.10** Run `ruff check theauditor/indexer/storage/node_storage.py`

### 2.3 Verify No Direct Cursor Access Remains
- [ ] **2.3.1** Run: `grep -n "cursor = self.db_manager.conn.cursor()" node_storage.py` - expect 0 results
- [ ] **2.3.2** Run: `grep -n "cursor.execute" node_storage.py` - expect 0 results

## 3. Integration Testing

### 3.1 Smoke Test
- [ ] **3.1.1** Run `pytest tests/test_schema_contract.py` - Python still works
- [ ] **3.1.2** Create test file with Sequelize model, run single-file index
- [ ] **3.1.3** Create test file with Angular component, run single-file index

### 3.2 Full Pipeline Test
- [ ] **3.2.1** Run `aud full --offline` on a Node-heavy codebase (React+Express)
- [ ] **3.2.2** Verify no `DataFidelityError` raised
- [ ] **3.2.3** Verify counts are non-zero for Node tables:
  ```sql
  SELECT 'sequelize_models', COUNT(*) FROM sequelize_models
  UNION SELECT 'angular_components', COUNT(*) FROM angular_components
  UNION SELECT 'react_hooks', COUNT(*) FROM react_hooks;
  ```

### 3.3 Fidelity Verification
- [ ] **3.3.1** Set `THEAUDITOR_DEBUG=1`, run `aud full --offline`
- [ ] **3.3.2** Grep logs for "Fidelity" - should see OK status for JS/TS files
- [ ] **3.3.3** Verify manifest counts match receipt counts in debug output

## 4. Code Quality

- [ ] **4.1** Run `ruff check theauditor/indexer/` - all files pass
- [ ] **4.2** Run `ruff check theauditor/ast_extractors/` - all files pass
- [ ] **4.3** Verify no new TODO/FIXME comments introduced
- [ ] **4.4** Verify no fallback patterns introduced (grep for "if not result:")

## 5. Documentation

- [ ] **5.1** Update `node_receipts.md` to mark Phase 0-2 as COMPLETE
- [ ] **5.2** Update `CLAUDE.md` database table counts if changed
