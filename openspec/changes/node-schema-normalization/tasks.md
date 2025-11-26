## 0. Prerequisites

- [ ] **0.1** Verify `node-fidelity-infrastructure` ticket is COMPLETE
- [ ] **0.2** Run `aud full --offline` - confirm no DataFidelityError
- [ ] **0.3** Read `node_receipts.md` for context refresh
- [ ] **0.4** Read `python_schema.py` for junction table patterns

## 1. Phase 3: Schema Normalization (Junction Tables)

**Complete Method Signatures for All 8 Junction Tables:**

```python
# 1. Vue Component Props
def add_vue_component_prop(self, file: str, component_name: str, prop_name: str,
                           prop_type: str | None = None, is_required: bool = False,
                           default_value: str | None = None):
    """Add a Vue component prop to the batch."""
    self.generic_batches['vue_component_props'].append((
        file, component_name, prop_name, prop_type,
        1 if is_required else 0, default_value
    ))

# 2. Vue Component Emits
def add_vue_component_emit(self, file: str, component_name: str, emit_name: str,
                           payload_type: str | None = None):
    """Add a Vue component emit to the batch."""
    self.generic_batches['vue_component_emits'].append((
        file, component_name, emit_name, payload_type
    ))

# 3. Vue Component Setup Returns
def add_vue_component_setup_return(self, file: str, component_name: str,
                                   return_name: str, return_type: str | None = None):
    """Add a Vue component setup return to the batch."""
    self.generic_batches['vue_component_setup_returns'].append((
        file, component_name, return_name, return_type
    ))

# 4. Angular Component Styles
def add_angular_component_style(self, file: str, component_name: str, style_path: str):
    """Add an Angular component style path to the batch."""
    self.generic_batches['angular_component_styles'].append((
        file, component_name, style_path
    ))

# 5. Angular Module Declarations
def add_angular_module_declaration(self, file: str, module_name: str,
                                   declaration_name: str, declaration_type: str | None = None):
    """Add an Angular module declaration to the batch."""
    self.generic_batches['angular_module_declarations'].append((
        file, module_name, declaration_name, declaration_type
    ))

# 6. Angular Module Imports
def add_angular_module_import(self, file: str, module_name: str, imported_module: str):
    """Add an Angular module import to the batch."""
    self.generic_batches['angular_module_imports'].append((
        file, module_name, imported_module
    ))

# 7. Angular Module Providers
def add_angular_module_provider(self, file: str, module_name: str,
                                provider_name: str, provider_type: str | None = None):
    """Add an Angular module provider to the batch."""
    self.generic_batches['angular_module_providers'].append((
        file, module_name, provider_name, provider_type
    ))

# 8. Angular Module Exports
def add_angular_module_export(self, file: str, module_name: str, exported_name: str):
    """Add an Angular module export to the batch."""
    self.generic_batches['angular_module_exports'].append((
        file, module_name, exported_name
    ))
```

### 1.1 Vue Component Props Junction Table
- [ ] **1.1.1** Add `VUE_COMPONENT_PROPS` table to `node_schema.py`:
  ```python
  VUE_COMPONENT_PROPS = TableSchema(
      name='vue_component_props',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('component_name', 'TEXT NOT NULL'),
          Column('prop_name', 'TEXT NOT NULL'),
          Column('prop_type', 'TEXT'),
          Column('is_required', 'INTEGER DEFAULT 0'),
          Column('default_value', 'TEXT'),
      ],
      indexes=[
          ('idx_vue_component_props_file', ['file']),
          ('idx_vue_component_props_component', ['component_name']),
      ]
  )
  ```
- [ ] **1.1.2** Add `add_vue_component_prop()` method to `node_database.py`
- [ ] **1.1.3** Modify `add_vue_component()` to parse `props_definition` JSON and call `add_vue_component_prop()` for each
- [ ] **1.1.4** Remove `props_definition` column from `VUE_COMPONENTS` schema

### 1.2 Vue Component Emits Junction Table
- [ ] **1.2.1** Add `VUE_COMPONENT_EMITS` table to `node_schema.py`:
  ```python
  VUE_COMPONENT_EMITS = TableSchema(
      name='vue_component_emits',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('component_name', 'TEXT NOT NULL'),
          Column('emit_name', 'TEXT NOT NULL'),
          Column('payload_type', 'TEXT'),
      ],
      indexes=[
          ('idx_vue_component_emits_file', ['file']),
          ('idx_vue_component_emits_component', ['component_name']),
      ]
  )
  ```
- [ ] **1.2.2** Add `add_vue_component_emit()` method to `node_database.py`
- [ ] **1.2.3** Modify `add_vue_component()` to parse `emits_definition` JSON and call `add_vue_component_emit()` for each
- [ ] **1.2.4** Remove `emits_definition` column from `VUE_COMPONENTS` schema

### 1.3 Vue Component Setup Returns Junction Table
- [ ] **1.3.1** Add `VUE_COMPONENT_SETUP_RETURNS` table to `node_schema.py`:
  ```python
  VUE_COMPONENT_SETUP_RETURNS = TableSchema(
      name='vue_component_setup_returns',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('component_name', 'TEXT NOT NULL'),
          Column('return_name', 'TEXT NOT NULL'),
          Column('return_type', 'TEXT'),
      ],
      indexes=[
          ('idx_vue_component_setup_returns_file', ['file']),
          ('idx_vue_component_setup_returns_component', ['component_name']),
      ]
  )
  ```
- [ ] **1.3.2** Add `add_vue_component_setup_return()` method to `node_database.py`
- [ ] **1.3.3** Modify `add_vue_component()` to parse `setup_return` JSON and call `add_vue_component_setup_return()` for each
- [ ] **1.3.4** Remove `setup_return` column from `VUE_COMPONENTS` schema

### 1.4 Angular Component Styles Junction Table
- [ ] **1.4.1** Add `ANGULAR_COMPONENT_STYLES` table to `node_schema.py`:
  ```python
  ANGULAR_COMPONENT_STYLES = TableSchema(
      name='angular_component_styles',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('component_name', 'TEXT NOT NULL'),
          Column('style_path', 'TEXT NOT NULL'),
      ],
      indexes=[
          ('idx_angular_component_styles_file', ['file']),
          ('idx_angular_component_styles_component', ['component_name']),
      ]
  )
  ```
- [ ] **1.4.2** Add `add_angular_component_style()` method to `node_database.py`
- [ ] **1.4.3** Modify `add_angular_component()` to parse `style_paths` JSON and call `add_angular_component_style()` for each
- [ ] **1.4.4** Remove `style_paths` column from `ANGULAR_COMPONENTS` schema

### 1.5 Angular Module Declarations Junction Table
- [ ] **1.5.1** Add `ANGULAR_MODULE_DECLARATIONS` table to `node_schema.py`:
  ```python
  ANGULAR_MODULE_DECLARATIONS = TableSchema(
      name='angular_module_declarations',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('module_name', 'TEXT NOT NULL'),
          Column('declaration_name', 'TEXT NOT NULL'),
          Column('declaration_type', 'TEXT'),  # component, directive, pipe
      ],
      indexes=[
          ('idx_angular_module_declarations_file', ['file']),
          ('idx_angular_module_declarations_module', ['module_name']),
      ]
  )
  ```
- [ ] **1.5.2** Add `add_angular_module_declaration()` method to `node_database.py`

### 1.6 Angular Module Imports Junction Table
- [ ] **1.6.1** Add `ANGULAR_MODULE_IMPORTS` table to `node_schema.py`:
  ```python
  ANGULAR_MODULE_IMPORTS = TableSchema(
      name='angular_module_imports',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('module_name', 'TEXT NOT NULL'),
          Column('imported_module', 'TEXT NOT NULL'),
      ],
      indexes=[
          ('idx_angular_module_imports_file', ['file']),
          ('idx_angular_module_imports_module', ['module_name']),
      ]
  )
  ```
- [ ] **1.6.2** Add `add_angular_module_import()` method to `node_database.py`

### 1.7 Angular Module Providers Junction Table
- [ ] **1.7.1** Add `ANGULAR_MODULE_PROVIDERS` table to `node_schema.py`:
  ```python
  ANGULAR_MODULE_PROVIDERS = TableSchema(
      name='angular_module_providers',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('module_name', 'TEXT NOT NULL'),
          Column('provider_name', 'TEXT NOT NULL'),
          Column('provider_type', 'TEXT'),  # class, useValue, useFactory, useExisting
      ],
      indexes=[
          ('idx_angular_module_providers_file', ['file']),
          ('idx_angular_module_providers_module', ['module_name']),
      ]
  )
  ```
- [ ] **1.7.2** Add `add_angular_module_provider()` method to `node_database.py`

### 1.8 Angular Module Exports Junction Table
- [ ] **1.8.1** Add `ANGULAR_MODULE_EXPORTS` table to `node_schema.py`:
  ```python
  ANGULAR_MODULE_EXPORTS = TableSchema(
      name='angular_module_exports',
      columns=[
          Column('file', 'TEXT NOT NULL'),
          Column('module_name', 'TEXT NOT NULL'),
          Column('exported_name', 'TEXT NOT NULL'),
      ],
      indexes=[
          ('idx_angular_module_exports_file', ['file']),
          ('idx_angular_module_exports_module', ['module_name']),
      ]
  )
  ```
- [ ] **1.8.2** Add `add_angular_module_export()` method to `node_database.py`

### 1.9 Update Angular Module Handler
- [ ] **1.9.1** Modify `add_angular_module()` to:
  - Parse `declarations` JSON and call `add_angular_module_declaration()` for each
  - Parse `imports` JSON and call `add_angular_module_import()` for each
  - Parse `providers` JSON and call `add_angular_module_provider()` for each
  - Parse `exports` JSON and call `add_angular_module_export()` for each
- [ ] **1.9.2** Remove JSON columns from `ANGULAR_MODULES` schema
- [ ] **1.9.3** Update `_store_angular_modules` handler if needed

### 1.10 Register New Tables
- [ ] **1.10.1** Add all 8 new tables to `NODE_TABLES` registry in `node_schema.py`

**Note:** `generic_batches` uses `defaultdict(list)` - no initialization needed. New table keys work automatically.

## 2. Phase 4: Contract Tests

### 2.1 Create Test File
- [ ] **2.1.1** Create `tests/test_node_schema_contract.py`
- [ ] **2.1.2** Add test: `test_node_table_count` - verify expected number of tables
- [ ] **2.1.3** Add test: `test_no_json_blob_columns` - grep schema for TEXT columns named *_definition, *_paths, declarations, imports, providers, exports
- [ ] **2.1.4** Add test: `test_junction_tables_have_fks` - verify junction tables reference parent tables
- [ ] **2.1.5** Add test: `test_all_handlers_use_batched_methods` - grep node_storage.py for cursor.execute (expect 0)
- [ ] **2.1.6** Add test: `test_vue_component_props_schema` - verify junction table columns
- [ ] **2.1.7** Add test: `test_angular_module_junction_schemas` - verify all 4 junction tables
- [ ] **2.1.8** Add test: `test_storage_handler_registry_complete` - verify all data types have handlers
- [ ] **2.1.9** Add test: `test_database_methods_exist` - verify all add_* methods exist
- [ ] **2.1.10** Add test: `test_generic_batches_has_all_tables` - verify batch keys exist

### 2.2 Run Tests
- [ ] **2.2.1** Run `pytest tests/test_node_schema_contract.py -v`
- [ ] **2.2.2** Fix any failures
- [ ] **2.2.3** Target: 10+ passing tests

## 3. Extractor Audit Script

### 3.1 Create Audit Script
- [ ] **3.1.1** Create `scripts/audit_node_extractors.py` (mirror `scripts/audit_extractors.py`)
- [ ] **3.1.2** Add code sample for JS/TS (React component, Vue component, Angular module)
- [ ] **3.1.3** Extract using `JavaScriptExtractor`
- [ ] **3.1.4** Print extracted data structure with field names
- [ ] **3.1.5** Add VALUE SAMPLES for discriminator fields

### 3.2 Generate Ground Truth
- [ ] **3.2.1** Run `python scripts/audit_node_extractors.py > node_extractor_truth.txt`
- [ ] **3.2.2** Review output for accuracy
- [ ] **3.2.3** Commit `node_extractor_truth.txt` to repo

## 4. Two-Discriminator Pattern (If Applicable)

### 4.1 Analyze Tables
- [ ] **4.1.1** Review Python schema for two-discriminator pattern usage
- [ ] **4.1.2** Identify Node tables that consolidate multiple types
- [ ] **4.1.3** Document which tables need `*_kind` + `*_type` columns

### 4.2 Apply Pattern (if tables identified)
- [ ] **4.2.1** Add discriminator columns to identified tables
- [ ] **4.2.2** Update storage handlers to populate discriminators
- [ ] **4.2.3** Add contract tests for discriminator values

## 5. Codegen Regeneration

- [ ] **5.1** Run `python -m theauditor.indexer.schemas.codegen`
- [ ] **5.2** Verify `generated_types.py` updated with new tables
- [ ] **5.3** Verify `generated_cache.py` updated
- [ ] **5.4** Verify `generated_accessors.py` updated
- [ ] **5.5** Run `ruff check theauditor/indexer/schemas/generated_*.py`

## 6. Final Validation

- [ ] **6.1** Run `aud full --offline` on Node-heavy codebase
- [ ] **6.2** Query junction tables - verify data populated:
  ```sql
  SELECT COUNT(*) FROM vue_component_props;
  SELECT COUNT(*) FROM angular_module_declarations;
  ```
- [ ] **6.3** Query removed columns don't exist:
  ```sql
  PRAGMA table_info(vue_components);  -- no props_definition
  PRAGMA table_info(angular_modules);  -- no declarations
  ```
- [ ] **6.4** Run all tests: `pytest tests/test_node_schema_contract.py tests/test_schema_contract.py -v`
- [ ] **6.5** Run `ruff check theauditor/`

## 7. Documentation Update

- [ ] **7.1** Update `node_receipts.md` to mark Phases 3-4 as COMPLETE
- [ ] **7.2** Update `CLAUDE.md` database table counts
- [ ] **7.3** Update `Architecture.md` if schema significantly changed
