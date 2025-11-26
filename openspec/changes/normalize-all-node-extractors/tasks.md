# Tasks: Normalize All Node.js Extractors

**Change ID:** `normalize-all-node-extractors`
**Total Phases:** 10
**Total Tasks:** 124

---

## 0. Verification (BLOCKING)

**Status:** COMPLETE (Opus Agents audited 2025-11-26)

- [x] **0.1** Read all 10 JavaScript extractor files (FULL reads, no grep)
- [x] **0.2** Identify NESTED array violations (14 found)
- [x] **0.3** Identify STRING_BLOB violations (1 found)
- [x] **0.4** Identify MISSING extraction violations (11 found)
- [x] **0.5** Confirm bullmq_extractors.js is CLEAN (0 violations)
- [x] **0.6** Document all violations with line numbers
- [x] **0.7** Verify existing junction tables in node_schema.py

---

## 1. Phase 1: Schema Definitions

**Target File:** `theauditor/indexer/schemas/node_schema.py`
**Status:** PENDING

### 1.1 Function/Decorator Tables

- [ ] **1.1.1** Add `FUNC_PARAMS` TableSchema
  - Columns: file, function_line, function_name, param_index, param_name, param_type
  - Indexes: function composite, param_name

- [ ] **1.1.2** Add `FUNC_DECORATORS` TableSchema
  - Columns: file, function_line, function_name, decorator_index, decorator_name, decorator_line
  - Indexes: function composite, decorator_name

- [ ] **1.1.3** Add `FUNC_DECORATOR_ARGS` TableSchema
  - Columns: file, function_line, function_name, decorator_index, arg_index, arg_value
  - Indexes: decorator composite

- [ ] **1.1.4** Add `CLASS_DECORATORS` TableSchema
  - Columns: file, class_line, class_name, decorator_index, decorator_name, decorator_line
  - Indexes: class composite, decorator_name

- [ ] **1.1.5** Add `CLASS_DECORATOR_ARGS` TableSchema
  - Columns: file, class_line, class_name, decorator_index, arg_index, arg_value
  - Indexes: decorator composite

- [ ] **1.1.6** Add `FUNC_PARAM_DECORATORS` TableSchema
  - Columns: file, function_line, function_name, param_index, decorator_name, decorator_args
  - Indexes: function composite, decorator_name
  - Purpose: NestJS @Body(), @Param(), @Query() parameter decorators

### 1.2 Data Flow Tables

- [ ] **1.2.1** Add `ASSIGNMENT_SOURCE_VARS` TableSchema
  - Columns: file, line, target_var, source_var, var_index
  - Indexes: assignment composite, source_var

- [ ] **1.2.2** Add `RETURN_SOURCE_VARS` TableSchema
  - Columns: file, line, function_name, source_var, var_index
  - Indexes: return composite, source_var

### 1.3 Import Tables

- [ ] **1.3.1** Add `IMPORT_SPECIFIERS` TableSchema
  - Columns: file, import_line, specifier_name, original_name, is_default, is_namespace, is_named
  - Indexes: import composite, specifier_name

### 1.4 Security Tables

- [ ] **1.4.1** Add `CDK_CONSTRUCT_PROPERTIES` TableSchema
  - Columns: file, construct_line, construct_name, property_name, value_expr, value_type
  - Indexes: construct composite, property_name

### 1.5 ORM Tables

- [ ] **1.5.1** Add `SEQUELIZE_MODEL_FIELDS` TableSchema
  - Columns: file, model_name, field_name, data_type, is_primary_key, is_nullable, is_unique, default_value
  - Indexes: model composite, data_type

### 1.6 CFG Tables

- [ ] **1.6.1** Add `CFG_BLOCKS` TableSchema
  - Columns: file, function_name, block_id, block_type, start_line, end_line, condition_expr
  - Indexes: function composite

- [ ] **1.6.2** Add `CFG_EDGES` TableSchema
  - Columns: file, function_name, source_block_id, target_block_id, edge_type
  - Indexes: function composite, source, target

- [ ] **1.6.3** Add `CFG_BLOCK_STATEMENTS` TableSchema
  - Columns: file, function_name, block_id, statement_index, statement_type, line, text
  - Indexes: block composite

### 1.7 Registry Update

- [ ] **1.7.1** Add all 14 new tables to `NODE_TABLES` registry dict

---

## 2. Phase 2: Core Language Extractor

**Target File:** `theauditor/ast_extractors/javascript/core_language.js`
**Lines to Modify:** 179-411 (functions and classes extraction)
**Status:** PENDING

### 2.1 Parameter Flattening

- [ ] **2.1.1** Create `flattenFunctionParams(params, functionName, functionLine)` helper
  - Location: Before `extractFunctions()`
  - Input: Array of parameter objects from AST
  - Output: Array of `{ function_name, function_line, param_index, param_name, param_type }`

- [ ] **2.1.2** Handle parameter destructuring patterns
  - `{ a, b }` -> extract both `a` and `b` as params
  - `[x, y]` -> extract with index-based names

- [ ] **2.1.3** Extract parameter decorators (NestJS @Body, @Param, etc.)
  - Create `extractParamDecorators(params, functionName)`
  - Output: `{ function_name, param_index, decorator_name, decorator_args }`

### 2.2 Decorator Flattening

- [ ] **2.2.1** Create `flattenDecorators(decorators, targetName, targetLine, targetType)` helper
  - Input: Array of decorator objects from AST
  - Output: Array of `{ target_name, target_line, decorator_index, decorator_name, decorator_line }`

- [ ] **2.2.2** Create `flattenDecoratorArgs(decorators, targetName, targetLine)` helper
  - Input: Array of decorator objects from AST
  - Output: Array of `{ target_name, decorator_index, arg_index, arg_value }`

### 2.3 Modify extractFunctions()

- [ ] **2.3.1** Call flattening helpers after function parsing
- [ ] **2.3.2** Add `func_params`, `func_decorators`, `func_decorator_args` to return
- [ ] **2.3.3** Remove `parameters` array from function objects (ZERO FALLBACK)
- [ ] **2.3.4** Remove `decorators` array from function objects (ZERO FALLBACK)

### 2.4 Modify extractClasses()

- [ ] **2.4.1** Call flattening helpers after class parsing
- [ ] **2.4.2** Add `class_decorators`, `class_decorator_args` to return
- [ ] **2.4.3** Remove `decorators` array from class objects (ZERO FALLBACK)

---

## 3. Phase 3: React Framework Extractor (framework_extractors.js)

**Target File:** `theauditor/ast_extractors/javascript/framework_extractors.js`
**Lines to Modify:** 39-161 (React component and hooks extraction)
- `extractReactComponents()`: lines 39-130
- `extractReactHooks()`: lines 161+
**Status:** PENDING

**Note:** Schema tables `react_component_hooks` and `react_hook_dependencies` ALREADY EXIST but extractors don't populate them. Storage handlers CONFIRMED MISSING (verified via grep).

### 3.1 React Component Hooks Flattening

- [ ] **3.1.1** Create `flattenReactComponentHooks(components)` helper
  - Input: Array of React components with nested `hooks_used` array
  - Output: Array of `{ component_file, component_name, hook_name }`

- [ ] **3.1.2** Modify `extractReactComponents()` to return `react_component_hooks` flat array

- [ ] **3.1.3** Remove `hooks_used` array from component objects (ZERO FALLBACK)

### 3.2 React Hook Dependencies Flattening

- [ ] **3.2.1** Create `flattenReactHookDependencies(hooks)` helper
  - Input: Array of React hooks with nested `dependency_vars` array
  - Output: Array of `{ hook_file, hook_line, hook_component, dependency_name }`

- [ ] **3.2.2** Modify React hooks extraction to return `react_hook_dependencies` flat array

- [ ] **3.2.3** Remove `dependency_vars` array from hook objects (ZERO FALLBACK)

### 3.3 Add Storage Handlers (CONFIRMED MISSING)

Storage handlers for existing schema tables are CONFIRMED MISSING (verified via `grep _store_react node_storage.py` = no matches).

- [ ] **3.3.1** Add `_store_react_component_hooks()` handler to node_storage.py
  - Iterate `react_component_hooks` array
  - Call `db.add_react_component_hook()` for each record
  - Increment `self.counts['react_component_hooks']`

- [ ] **3.3.2** Add `_store_react_hook_dependencies()` handler to node_storage.py
  - Iterate `react_hook_dependencies` array
  - Call `db.add_react_hook_dependency()` for each record
  - Increment `self.counts['react_hook_dependencies']`

- [ ] **3.3.3** Add `_store_import_style_names()` handler to node_storage.py
  - Iterate `import_style_names` array
  - Call `db.add_import_style_name()` for each record
  - Increment `self.counts['import_style_names']`

- [ ] **3.3.4** Register all 3 handlers in `self.handlers` dict:
  ```python
  self.handlers['react_component_hooks'] = self._store_react_component_hooks
  self.handlers['react_hook_dependencies'] = self._store_react_hook_dependencies
  self.handlers['import_style_names'] = self._store_import_style_names
  ```

- [ ] **3.3.5** Add corresponding database methods to node_database.py:
  - `add_react_component_hook(component_file, component_name, hook_name)`
  - `add_react_hook_dependency(hook_file, hook_line, hook_component, dependency_name)`
  - `add_import_style_name(import_file, import_line, imported_name)`

---

## 4. Phase 4: Data Flow Extractor

**Target File:** `theauditor/ast_extractors/javascript/data_flow.js`
**Lines to Modify:** 349-844 (assignments and returns)
**Status:** PENDING

### 4.1 Assignment Source Flattening

- [ ] **4.1.1** Create `flattenAssignmentSources(assignments)` helper
  - Input: Array of assignment objects with nested `source_vars`
  - Output: Array of `{ file, line, target_var, source_var, var_index }`

- [ ] **4.1.2** Preserve variable order with `var_index`

### 4.2 Return Source Flattening

- [ ] **4.2.1** Create `flattenReturnSources(returns)` helper
  - Input: Array of return objects with nested `return_vars`
  - Output: Array of `{ file, line, function_name, source_var, var_index }`

### 4.3 Modify extractAssignments()

- [ ] **4.3.1** Call `flattenAssignmentSources()` after extraction
- [ ] **4.3.2** Add `assignment_source_vars` to return
- [ ] **4.3.3** Remove `source_vars` array from assignment objects (ZERO FALLBACK)

### 4.4 Modify extractReturns()

- [ ] **4.4.1** Call `flattenReturnSources()` after extraction
- [ ] **4.4.2** Add `return_source_vars` to return
- [ ] **4.4.3** Remove `return_vars` array from return objects (ZERO FALLBACK)

---

## 5. Phase 5: Module Framework Extractor

**Target File:** `theauditor/ast_extractors/javascript/module_framework.js`
**Lines to Modify:** 47-118, 475-516 (imports and import styles)
**Status:** PENDING

### 5.1 Import Specifier Flattening

- [ ] **5.1.1** Create `flattenImportSpecifiers(imports)` helper
  - Input: Array of import objects with nested `specifiers`
  - Output: Array of `{ file, import_line, specifier_name, original_name, is_default, is_namespace, is_named }`

- [ ] **5.1.2** Handle aliased imports: `{ useState as useS }` -> original_name='useState', specifier_name='useS'

- [ ] **5.1.3** Handle namespace imports: `import * as React` -> is_namespace=1

- [ ] **5.1.4** Handle default imports: `import axios` -> is_default=1

### 5.2 Import Style Names

- [ ] **5.2.1** Verify `import_style_names` table already exists in schema
- [ ] **5.2.2** Create `flattenImportStyleNames(importStyles)` helper
  - Input: Array of import_style objects with nested `imported_names`
  - Output: Array of `{ import_file, import_line, imported_name }`

### 5.3 Modify extractImports()

- [ ] **5.3.1** Call `flattenImportSpecifiers()` after extraction
- [ ] **5.3.2** Add `import_specifiers` to return
- [ ] **5.3.3** Remove `specifiers` array from import objects (ZERO FALLBACK)

### 5.4 Modify extractImportStyles()

- [ ] **5.4.1** Call `flattenImportStyleNames()` after extraction
- [ ] **5.4.2** Add `import_style_names` to return
- [ ] **5.4.3** Remove `imported_names` array from import_style objects (ZERO FALLBACK)

### 5.5 Dynamic Import Enhancement

- [ ] **5.5.1** Add `in_function` field to dynamic imports
- [ ] **5.5.2** Add `is_conditional` field (inside if/switch/ternary)

---

## 6. Phase 6: Security Extractors

**Target File:** `theauditor/ast_extractors/javascript/security_extractors.js`
**Lines to Modify:** 843-976 (CDK constructs)
**Status:** PENDING

### 6.1 CDK Property Flattening

- [ ] **6.1.1** Create `flattenCDKProperties(constructs)` helper
  - Input: Array of CDK construct objects with nested `properties`
  - Output: Array of `{ file, construct_line, construct_name, property_name, value_expr, value_type }`

- [ ] **6.1.2** Create `inferPropertyType(valueExpr)` helper
  - Returns: 'boolean', 'string', 'number', 'array', 'object', or 'variable'

### 6.2 Modify extractCDKConstructs()

- [ ] **6.2.1** Call `flattenCDKProperties()` after extraction
- [ ] **6.2.2** Add `cdk_construct_properties` to return
- [ ] **6.2.3** Remove `properties` array from construct objects (ZERO FALLBACK)

---

## 7. Phase 7: Sequelize Extractor

**Target File:** `theauditor/ast_extractors/javascript/sequelize_extractors.js`
**Lines to Modify:** 56-68 (Model.init parsing)
**Status:** PENDING

### 7.1 Model Field Extraction

- [ ] **7.1.1** Create `parseModelFields(modelName, initCall)` helper
  - Input: Model.init() call with first argument (fields object)
  - Output: Array of `{ model_name, field_name, data_type, is_primary_key, is_nullable, is_unique, default_value }`

- [ ] **7.1.2** Parse DataTypes: STRING, INTEGER, BOOLEAN, DATE, ENUM, JSON, etc.

- [ ] **7.1.3** Parse field options: primaryKey, allowNull, unique, defaultValue

### 7.2 Modify extractSequelizeModels()

- [ ] **7.2.1** Find Model.init() calls and extract first argument
- [ ] **7.2.2** Call `parseModelFields()` for each model
- [ ] **7.2.3** Add `sequelize_model_fields` to return

---

## 8. Phase 8: CFG Extractor

**Target File:** `theauditor/ast_extractors/javascript/cfg_extractor.js`
**Lines to Modify:** 509-510 (CFG return structure)
**Status:** PENDING

### 8.1 CFG Flattening

- [ ] **8.1.1** Create `flattenCFGs(cfgs, filePath)` helper
  - Input: Array of CFG objects with nested blocks/edges
  - Output: `{ cfgs, cfg_blocks, cfg_edges, cfg_block_statements }`

- [ ] **8.1.2** Flatten blocks with function_name reference
- [ ] **8.1.3** Flatten edges with function_name reference
- [ ] **8.1.4** Flatten statements with block_id reference

### 8.2 Modify extractCFG()

- [ ] **8.2.1** Call `flattenCFGs()` after extraction
- [ ] **8.2.2** Return 4 separate arrays instead of nested structure
- [ ] **8.2.3** Remove nested `blocks`, `edges`, `statements` (ZERO FALLBACK)

---

## 9. Phase 9: Batch Templates + Python Storage

**Status:** PENDING

### 9.1 Batch Templates (ES Module)

**Target:** `batch_templates.js` lines 1-560

- [ ] **9.1.1** Add core_language junction keys to extracted_data:
  - `func_params`, `func_decorators`, `func_decorator_args`
  - `func_param_decorators`, `class_decorators`, `class_decorator_args`

- [ ] **9.1.2** Add data_flow junction keys:
  - `assignment_source_vars`, `return_source_vars`

- [ ] **9.1.3** Add module_framework junction keys:
  - `import_specifiers`, `import_style_names`

- [ ] **9.1.4** Add security junction keys:
  - `cdk_construct_properties`

- [ ] **9.1.5** Add sequelize junction keys:
  - `sequelize_model_fields`

- [ ] **9.1.6** Add CFG junction keys:
  - `cfg_blocks`, `cfg_edges`, `cfg_block_statements`

- [ ] **9.1.7** Add React junction keys:
  - `react_component_hooks`, `react_hook_dependencies`

### 9.2 Batch Templates (CommonJS)

**Target:** `batch_templates.js` lines 561-1095

**CRITICAL: MIRROR ALL CHANGES FROM ES MODULE**

- [ ] **9.2.1** Mirror all core_language junction keys
- [ ] **9.2.2** Mirror all data_flow junction keys
- [ ] **9.2.3** Mirror all module_framework junction keys
- [ ] **9.2.4** Mirror all security junction keys
- [ ] **9.2.5** Mirror all sequelize junction keys
- [ ] **9.2.6** Mirror all CFG junction keys
- [ ] **9.2.7** Mirror all React junction keys

### 9.3 Python Database Methods

**Target:** `theauditor/indexer/database/node_database.py`

- [ ] **9.3.1** Add `add_func_param()` method
- [ ] **9.3.2** Add `add_func_decorator()` method
- [ ] **9.3.3** Add `add_func_decorator_arg()` method
- [ ] **9.3.4** Add `add_func_param_decorator()` method
- [ ] **9.3.5** Add `add_class_decorator()` method
- [ ] **9.3.6** Add `add_class_decorator_arg()` method
- [ ] **9.3.7** Add `add_assignment_source_var()` method
- [ ] **9.3.8** Add `add_return_source_var()` method
- [ ] **9.3.9** Add `add_import_specifier()` method
- [ ] **9.3.10** Add `add_cdk_construct_property()` method
- [ ] **9.3.11** Add `add_sequelize_model_field()` method
- [ ] **9.3.12** Add `add_cfg_block()` method
- [ ] **9.3.13** Add `add_cfg_edge()` method
- [ ] **9.3.14** Add `add_cfg_block_statement()` method

### 9.4 Python Storage Handlers

**Target:** `theauditor/indexer/storage/node_storage.py`

- [ ] **9.4.1** Add `_store_func_params()` handler
- [ ] **9.4.2** Add `_store_func_decorators()` handler
- [ ] **9.4.3** Add `_store_func_decorator_args()` handler
- [ ] **9.4.4** Add `_store_func_param_decorators()` handler
- [ ] **9.4.5** Add `_store_class_decorators()` handler
- [ ] **9.4.6** Add `_store_class_decorator_args()` handler
- [ ] **9.4.7** Add `_store_assignment_source_vars()` handler
- [ ] **9.4.8** Add `_store_return_source_vars()` handler
- [ ] **9.4.9** Add `_store_import_specifiers()` handler
- [ ] **9.4.10** Add `_store_cdk_construct_properties()` handler
- [ ] **9.4.11** Add `_store_sequelize_model_fields()` handler
- [ ] **9.4.12** Add `_store_cfg_blocks()` handler
- [ ] **9.4.13** Add `_store_cfg_edges()` handler
- [ ] **9.4.14** Add `_store_cfg_block_statements()` handler
- [ ] **9.4.15** Register all 14 handlers in `self.handlers` dict

### 9.5 Python Extractor Mapping

**Target:** `theauditor/indexer/extractors/javascript.py`

- [ ] **9.5.1** Add all 14 new key mappings to result dict initialization
- [ ] **9.5.2** Add all 14 key mappings to `key_mappings` dict

---

## 10. Phase 10: Verification & Testing

**Status:** PENDING

### 10.1 Schema Verification

- [ ] **10.1.1** Run `aud full --offline` to create new tables
- [ ] **10.1.2** Verify all 14 new tables exist via PRAGMA
- [ ] **10.1.3** Verify column definitions match schema

### 10.2 Contract Tests

- [ ] **10.2.1** Run `pytest tests/test_node_schema_contract.py -v`
- [ ] **10.2.2** All tests must pass (current: 24 tests)

### 10.3 Integration Testing

- [ ] **10.3.1** Run `aud full --offline` on TheAuditor itself
- [ ] **10.3.2** Query each new junction table for row counts using verification SQL:

```sql
-- Verification queries for all 14 NEW + 3 EXISTING junction tables
-- Run against .pf/repo_index.db after aud full --offline

-- Core Language (NEW)
SELECT 'func_params' as tbl, COUNT(*) as cnt FROM func_params;
SELECT 'func_decorators' as tbl, COUNT(*) as cnt FROM func_decorators;
SELECT 'func_decorator_args' as tbl, COUNT(*) as cnt FROM func_decorator_args;
SELECT 'func_param_decorators' as tbl, COUNT(*) as cnt FROM func_param_decorators;
SELECT 'class_decorators' as tbl, COUNT(*) as cnt FROM class_decorators;
SELECT 'class_decorator_args' as tbl, COUNT(*) as cnt FROM class_decorator_args;

-- Data Flow (NEW)
SELECT 'assignment_source_vars' as tbl, COUNT(*) as cnt FROM assignment_source_vars;
SELECT 'return_source_vars' as tbl, COUNT(*) as cnt FROM return_source_vars;

-- Module Framework (NEW)
SELECT 'import_specifiers' as tbl, COUNT(*) as cnt FROM import_specifiers;

-- Security (NEW)
SELECT 'cdk_construct_properties' as tbl, COUNT(*) as cnt FROM cdk_construct_properties;

-- ORM (NEW)
SELECT 'sequelize_model_fields' as tbl, COUNT(*) as cnt FROM sequelize_model_fields;

-- CFG (NEW)
SELECT 'cfg_blocks' as tbl, COUNT(*) as cnt FROM cfg_blocks;
SELECT 'cfg_edges' as tbl, COUNT(*) as cnt FROM cfg_edges;
SELECT 'cfg_block_statements' as tbl, COUNT(*) as cnt FROM cfg_block_statements;

-- React (EXISTING - now wired)
SELECT 'react_component_hooks' as tbl, COUNT(*) as cnt FROM react_component_hooks;
SELECT 'react_hook_dependencies' as tbl, COUNT(*) as cnt FROM react_hook_dependencies;

-- Import Styles (EXISTING - now wired)
SELECT 'import_style_names' as tbl, COUNT(*) as cnt FROM import_style_names;
```

- [ ] **10.3.3** Verify non-zero rows in critical tables:
  - `func_params` (functions have params) - EXPECTED: 100+ for any Node.js project
  - `func_decorators` (decorators exist) - EXPECTED: 10+ if NestJS/Angular
  - `assignment_source_vars` (assignments have sources) - EXPECTED: 500+
  - `import_specifiers` (imports have specifiers) - EXPECTED: 1000+
  - `react_component_hooks` (React hooks used) - EXPECTED: 50+ if React project
  - `import_style_names` (import names) - EXPECTED: 500+

### 10.4 Code Quality

- [ ] **10.4.1** Run `ruff check theauditor/indexer/`
- [ ] **10.4.2** Run `ruff check theauditor/indexer/schemas/`
- [ ] **10.4.3** Verify no direct cursor access in node_storage.py

---

## Progress Summary

| Phase | Tasks | Complete | Status |
|-------|-------|----------|--------|
| 0. Verification | 7 | 7 | DONE |
| 1. Schema | 15 | 0 | PENDING |
| 2. Core Language | 11 | 0 | PENDING |
| 3. React Framework | 12 | 0 | PENDING |
| 4. Data Flow | 8 | 0 | PENDING |
| 5. Module Framework | 11 | 0 | PENDING |
| 6. Security | 4 | 0 | PENDING |
| 7. Sequelize | 5 | 0 | PENDING |
| 8. CFG | 5 | 0 | PENDING |
| 9. Batch + Storage | 38 | 0 | PENDING |
| 10. Verification | 11 | 0 | PENDING |

**Total: 127 tasks, 7 complete (6%)**

---

## CRITICAL: Execution Order

1. **Phase 1 MUST complete first** - Schema tables required before storage
2. **Phases 2-8 CAN run in parallel** - Independent extractor changes
3. **Phase 9 MUST wait for Phases 2-8** - Aggregates extractor output
4. **Phase 10 MUST be last** - Verification requires all changes

**Parallel Opportunity:**
- Phase 2 (Core Language) + Phase 3 (React) + Phase 4 (Data Flow) + Phase 5 (Module Framework)
- Phase 6 (Security) + Phase 7 (Sequelize) + Phase 8 (CFG)

---

## Definition of Done Checklist

- [ ] All 124 tasks marked complete
- [ ] All 14 new tables exist in repo_index.db
- [ ] All 14 storage handlers registered
- [ ] React junction tables populated (react_component_hooks, react_hook_dependencies)
- [ ] `aud full --offline` completes without errors
- [ ] Junction tables populated with real data
- [ ] `pytest tests/test_node_schema_contract.py -v` passes
- [ ] `ruff check theauditor/indexer/` passes
- [ ] No nested arrays in ANY extractor return values
- [ ] No try/except fallbacks in storage layer
