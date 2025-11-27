# Proposal: Normalize All Node.js Extractors

**Change ID:** `normalize-all-node-extractors`
**Status:** PROPOSED
**Author:** Lead Coder (Opus)
**Date:** 2025-11-26
**Risk Level:** MEDIUM
**Prerequisite:** `normalize-node-extractor-output` (COMPLETE - archived 2025-11-26)

---

## Why

### The Unfinished Business

The `normalize-node-extractor-output` ticket fixed Vue and Angular extractors, but **6 MORE FILES** still have nested arrays that should be flattened for consistency:

| File | Issue | Impact |
|------|-------|--------|
| `core_language.js` | Parameters/decorators nested | Function metadata queries require JSON parsing |
| `data_flow.js` | source_vars/return_vars nested | Taint propagation requires JSON parsing |
| `module_framework.js` | Import specifiers nested | Import analysis requires JSON parsing |
| `security_extractors.js` | Some nested structures | CDK analysis affected |
| `sequelize_extractors.js` | Model fields not extracted | ORM schema invisible |
| `cfg_extractor.js` | Already flattened at storage layer | No action needed |

### Current State (Verified 2025-11-26)

**Tables that ALREADY EXIST and are POPULATED:**
- `cfg_blocks`, `cfg_edges`, `cfg_block_statements` - core_schema.py (storage layer flattens)
- `cdk_construct_properties` - infrastructure_schema.py
- `react_component_hooks`, `react_hook_dependencies` - node_schema.py (database methods flatten)
- `import_style_names` - node_schema.py

**Tables that need to be CREATED:**
- `func_params` - function parameters
- `func_decorators` - function decorators
- `func_decorator_args` - decorator arguments
- `func_param_decorators` - parameter decorators (@Body, @Param)
- `class_decorators` - class decorators
- `class_decorator_args` - class decorator arguments
- `assignment_source_vars` - assignment data flow
- `return_source_vars` - return data flow
- `import_specifiers` - ES6 import specifiers
- `sequelize_model_fields` - ORM field definitions

**Total: 10 new tables needed.**

---

## What Changes

### Phase 1: Schema Definitions (10 new tables in node_schema.py)

Add TableSchema definitions for:
1. `func_params` - function parameters with index, name, type
2. `func_decorators` - function decorators with index, name
3. `func_decorator_args` - decorator arguments
4. `func_param_decorators` - NestJS @Body, @Param decorators
5. `class_decorators` - class decorators
6. `class_decorator_args` - class decorator arguments
7. `assignment_source_vars` - assignment source variables
8. `return_source_vars` - return source variables
9. `import_specifiers` - ES6 import specifiers with alias tracking
10. `sequelize_model_fields` - ORM field definitions

### Phase 2: Core Language Extractor

**Target:** `core_language.js`

Changes:
1. Add flattening helpers for parameters and decorators
2. Return flat `func_params[]`, `func_decorators[]`, `func_decorator_args[]` arrays
3. Return flat `class_decorators[]`, `class_decorator_args[]` arrays

### Phase 3: Data Flow Extractor

**Target:** `data_flow.js`

Changes:
1. Add flattening helpers for source variables
2. Return flat `assignment_source_vars[]` array
3. Return flat `return_source_vars[]` array

### Phase 4: Module Framework Extractor

**Target:** `module_framework.js`

Changes:
1. Add flattening helper for import specifiers
2. Return flat `import_specifiers[]` array with alias info

### Phase 5: Sequelize Extractor

**Target:** `sequelize_extractors.js`

Changes:
1. Add `parseModelFields()` to extract from Model.init()
2. Return flat `sequelize_model_fields[]` array

### Phase 6: Batch Templates + Python Storage

**Targets:** `batch_templates.js`, `node_storage.py`, `node_database.py`, `javascript.py`

Changes:
1. Update batch_templates.js (BOTH ES Module AND CommonJS) to aggregate new keys
2. Add 10 storage handlers in node_storage.py
3. Add 10 database methods in node_database.py
4. Add key mappings in javascript.py

---

## NOT IN SCOPE (Already Working)

The following are NOT part of this ticket - they already exist and function correctly:

| Component | Location | Status |
|-----------|----------|--------|
| CFG tables | core_schema.py | Populated via core_storage.py flattening |
| CDK properties | infrastructure_schema.py | Populated |
| React hooks junction | node_schema.py | Populated via add_react_component() |
| React dependencies junction | node_schema.py | Populated via add_react_hook() |
| Import style names | node_schema.py | Populated |

---

## Impact

### New Schema Tables (10)

| Table | Purpose |
|-------|---------|
| `func_params` | Function parameters |
| `func_decorators` | Function decorators |
| `func_decorator_args` | Decorator arguments |
| `func_param_decorators` | Parameter decorators |
| `class_decorators` | Class decorators |
| `class_decorator_args` | Class decorator arguments |
| `assignment_source_vars` | Assignment data flow |
| `return_source_vars` | Return data flow |
| `import_specifiers` | ES6 import specifiers |
| `sequelize_model_fields` | ORM field definitions |

### Files Modified (~10)

| Layer | File | Changes |
|-------|------|---------|
| JS Extractor | `core_language.js` | Add flattening, new return keys |
| JS Extractor | `data_flow.js` | Add flattening, new return keys |
| JS Extractor | `module_framework.js` | Add flattening, new return keys |
| JS Extractor | `sequelize_extractors.js` | Add field extraction |
| JS Orchestrator | `batch_templates.js` | Aggregate new keys (BOTH versions) |
| Python Schema | `node_schema.py` | Add 10 TableSchema definitions |
| Python Database | `node_database.py` | Add 10 add_* methods |
| Python Storage | `node_storage.py` | Add 10 _store_* handlers |
| Python Extractor | `javascript.py` | Add key mappings |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Schema additions | LOW | New tables, no migration needed |
| Breaking nested field consumers | MEDIUM | Search for existing usages first |
| Parse errors in extractors | LOW | Graceful skip with warning |

---

## Definition of Done

- [ ] All 10 new schema tables defined in `node_schema.py`
- [ ] All 10 database methods in `node_database.py`
- [ ] All 10 storage handlers in `node_storage.py`
- [ ] `batch_templates.js` aggregates all new keys (BOTH ES + CommonJS)
- [ ] `javascript.py` maps all new keys
- [ ] `aud full --offline` completes without errors
- [ ] `ruff check theauditor/indexer/` passes

---

## References

- **Prerequisite:** `normalize-node-extractor-output` (archived 2025-11-26)
- **Architecture:** CLAUDE.md ZERO FALLBACK POLICY
- **Protocol:** teamsop.md v4.20 Prime Directive
