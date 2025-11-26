# Proposal: Normalize All Node.js Extractors

**Change ID:** `normalize-all-node-extractors`
**Status:** PROPOSED
**Author:** Lead Coder (Opus)
**Date:** 2025-11-26
**Risk Level:** HIGH
**Prerequisite:** `normalize-node-extractor-output` (COMPLETE - archived 2025-11-26)

---

## Why

### The Unfinished Business

The `normalize-node-extractor-output` ticket fixed Vue and Angular extractors, but **6 MORE FILES** still violate the ZERO FALLBACK / FLAT DATA architecture:

| File | Violations | Impact |
|------|------------|--------|
| `core_language.js` | 6 NESTED arrays | Function params, decorators lost |
| `data_flow.js` | 2 NESTED arrays | Taint propagation broken |
| `module_framework.js` | 3 NESTED + 4 MISSING | Import analysis incomplete |
| `security_extractors.js` | 1 NESTED + 2 MISSING | CDK security blind spots |
| `sequelize_extractors.js` | 4 MISSING | ORM schema invisible |
| `cfg_extractor.js` | 3 NESTED arrays | CFG queries impossible |

**Total: 26 violations across 6 files.**

### Why This Matters

1. **Junction Tables Already Exist** - Schema has `react_hook_dependencies`, `import_style_names` but extractors don't populate them
2. **Taint Analysis Blind** - `source_vars` and `return_vars` nested = can't query data flow
3. **Security Rules Broken** - CDK properties nested = can't detect misconfigurations
4. **ORM Invisible** - Sequelize model FIELDS not extracted = can't analyze schema

### Evidence (Opus Agent Audit 2025-11-26)

```
Agent 1 (4 files):
- bullmq_extractors.js: 0 violations (CLEAN)
- cfg_extractor.js: 3 violations (NESTED blocks/edges/statements)
- core_language.js: 6 violations (NESTED params/decorators)
- data_flow.js: 2 violations (NESTED source_vars/return_vars)

Agent 2 (3 files):
- security_extractors.js: 4 violations (NESTED CDK props, MISSING headers)
- sequelize_extractors.js: 4 violations (MISSING model fields)
- module_framework.js: 7 violations (NESTED specifiers/imported_names)
```

---

## What Changes

**Phase Mapping Note:** This proposal describes 8 implementation phases. The detailed `tasks.md` expands this to 10 phases with additional verification phases:
- Phase 0: Verification (COMPLETE - Opus agent audit)
- Phases 1-8: Implementation (described below as Phase 1-8)
- Phase 9: Batch + Storage (integration, described below as Phase 8)
- Phase 10: Verification & Testing

See `tasks.md` for the full 127-task breakdown with granular steps.

### Phase 1: Core Language (CRITICAL - Taint Analysis Foundation)

**Target:** `core_language.js` - Function parameters, decorators, type info

| Current | Target | Schema |
|---------|--------|--------|
| `functions[].parameters[]` nested | `func_params[]` flat | NEW TABLE |
| `functions[].decorators[]` nested | `func_decorators[]` flat | NEW TABLE |
| `decorators[].arguments[]` nested | `func_decorator_args[]` flat | NEW TABLE |
| `classes[].decorators[]` nested | `class_decorators[]` flat | NEW TABLE |

**Technical Changes:**
1. Create `flattenFunctionParams()` - Extract params to flat array
2. Create `flattenDecorators()` - Extract decorators to flat array
3. Modify `extractFunctions()` return structure
4. Modify `extractClasses()` return structure
5. Update `batch_templates.js` to aggregate new arrays

### Phase 2: React Framework (CRITICAL - Component Dependencies)

**Target:** `framework_extractors.js` - React hooks, hook dependencies

| Current | Target | Schema |
|---------|--------|--------|
| `components[].hooks_used[]` nested | `react_component_hooks[]` flat | EXISTS - NOT POPULATED |
| `hooks[].dependency_vars[]` nested | `react_hook_dependencies[]` flat | EXISTS - NOT POPULATED |

**Technical Changes:**
1. Create `flattenReactComponentHooks()` - Extract component hooks
2. Create `flattenReactHookDependencies()` - Extract hook dependencies
3. Modify `extractReactComponents()` return structure
4. Wire extractors to existing (but empty) schema tables

### Phase 3: Data Flow (CRITICAL - Taint Propagation)

**Target:** `data_flow.js` - Assignment sources, return sources

| Current | Target | Schema |
|---------|--------|--------|
| `assignments[].source_vars[]` nested | `assignment_source_vars[]` flat | NEW TABLE |
| `returns[].return_vars[]` nested | `return_source_vars[]` flat | NEW TABLE |

**Technical Changes:**
1. Create `flattenAssignmentSources()` - Extract source vars
2. Create `flattenReturnSources()` - Extract return vars
3. Modify `extractAssignments()` return structure
4. Modify `extractReturns()` return structure

### Phase 4: Module Framework (Import Analysis)

**Target:** `module_framework.js` - Import specifiers, imported names

| Current | Target | Schema |
|---------|--------|--------|
| `imports[].specifiers[]` nested | `import_specifiers[]` flat | NEW TABLE |
| `import_styles[].imported_names[]` nested | Direct to `import_style_names` | EXISTS |

**Technical Changes:**
1. Create `flattenImportSpecifiers()` - Extract specifiers with alias info
2. Modify `extractImports()` return structure
3. Modify `extractImportStyles()` to call storage directly
4. Add `in_function`, `is_conditional` to dynamic imports

### Phase 5: Security Extractors (CDK/Validation)

**Target:** `security_extractors.js` - CDK properties

| Current | Target | Schema |
|---------|--------|--------|
| `cdk_constructs[].properties[]` nested | `cdk_construct_properties[]` flat | NEW TABLE |

**Technical Changes:**
1. Create `flattenCDKProperties()` - Extract construct properties
2. Modify `extractCDKConstructs()` return structure
3. Add `value_type` inference (boolean, string, variable)

### Phase 6: Sequelize (ORM Schema)

**Target:** `sequelize_extractors.js` - Model field definitions

| Current | Target | Schema |
|---------|--------|--------|
| Model fields NOT EXTRACTED | `sequelize_model_fields[]` flat | NEW TABLE |

**Technical Changes:**
1. Create `parseModelFields()` - Extract from Model.init() first arg
2. Modify `extractSequelizeModels()` return structure
3. Extract field types, constraints, defaults

### Phase 7: CFG Extractor (Graph Queries)

**Target:** `cfg_extractor.js` - Blocks, edges, statements

| Current | Target | Schema |
|---------|--------|--------|
| `cfg[].blocks[]` nested | `cfg_blocks[]` flat | NEW TABLE |
| `cfg[].edges[]` nested | `cfg_edges[]` flat | NEW TABLE |
| `blocks[].statements[]` nested | `cfg_block_statements[]` flat | NEW TABLE |

**Technical Changes:**
1. Flatten CFG structure to 4 separate arrays
2. Update `extractCFG()` return structure

### Phase 8: Batch Template + Python Storage

**Target:** `batch_templates.js`, `node_storage.py`, `node_database.py`, `javascript.py`

**Technical Changes:**
1. Update BOTH ES Module AND CommonJS versions in batch_templates.js
2. Add ~15 new storage handlers in node_storage.py
3. Add ~15 new database methods in node_database.py
4. Add key mappings in javascript.py
5. **REMOVE** deprecated nested fields from parent tables

---

## Impact

### New Schema Tables (14)

| Table | Purpose | Parent FK |
|-------|---------|-----------|
| `func_params` | Function parameters | symbols.file,line |
| `func_decorators` | Function decorators | symbols.file,line |
| `func_decorator_args` | Decorator arguments | func_decorators.file,line,idx |
| `func_param_decorators` | Parameter decorators (@Body, @Param) | func_params.file,line,idx |
| `class_decorators` | Class decorators | symbols.file,line |
| `class_decorator_args` | Decorator arguments | class_decorators.file,line,idx |
| `assignment_source_vars` | Assignment data flow | assignments.file,line |
| `return_source_vars` | Return data flow | returns.file,line |
| `import_specifiers` | ES6 import specifiers | imports.file,line |
| `cdk_construct_properties` | CDK construct props | cdk_constructs.file,line |
| `sequelize_model_fields` | ORM field definitions | sequelize_models.file,model |
| `cfg_blocks` | CFG basic blocks | cfgs.file,function |
| `cfg_edges` | CFG control flow | cfgs.file,function |
| `cfg_block_statements` | Block statements | cfg_blocks.file,function,id |

### Files Modified (~16)

| Layer | File | Changes |
|-------|------|---------|
| JS Extractor | `core_language.js` | Add flattening, modify returns |
| JS Extractor | `framework_extractors.js` | Wire React hooks to existing schema |
| JS Extractor | `data_flow.js` | Add flattening, modify returns |
| JS Extractor | `module_framework.js` | Add flattening, modify returns |
| JS Extractor | `security_extractors.js` | Add flattening, modify returns |
| JS Extractor | `sequelize_extractors.js` | Add field extraction |
| JS Extractor | `cfg_extractor.js` | Flatten CFG structure |
| JS Orchestrator | `batch_templates.js` | Aggregate all new arrays (BOTH versions) |
| Python Schema | `node_schema.py` | Add 14 new TableSchema definitions |
| Python Database | `node_database.py` | Add 14 new add_* methods |
| Python Storage | `node_storage.py` | Add 14 new _store_* handlers (+ wire 2 existing) |
| Python Extractor | `javascript.py` | Add key mappings |

### Polyglot Architecture Note

**This is Node.js (Source) + Python (Consumer) + NO Rust:**
- **Node.js:** `*.js` extractors produce flat data
- **Python:** Schema, Database, Storage consume flat data
- **Orchestrator:** `batch_templates.js` aggregates (no Python orchestrator changes)
- **Rust:** NOT REQUIRED (extraction pipeline doesn't use Rust)

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Schema migration | HIGH | Tables are NEW, no migration needed |
| Breaking existing queries | MEDIUM | Old nested fields removed, queries must update |
| Parse errors in extractors | MEDIUM | Graceful skip with warning, continue extraction |
| Large PR size | MEDIUM | Can split into 6 PRs per phase if needed |

### Breaking Changes

**YES - Intentional:**
- `functions[].parameters` REMOVED - use `func_params` table
- `functions[].decorators` REMOVED - use `func_decorators` table
- `assignments[].source_vars` REMOVED - use `assignment_source_vars` table
- `returns[].return_vars` REMOVED - use `return_source_vars` table
- `imports[].specifiers` REMOVED - use `import_specifiers` table
- `cdk_constructs[].properties` REMOVED - use `cdk_construct_properties` table

---

## Definition of Done

- [ ] All 6 JS extractors produce flat arrays (no nested arrays in returns)
- [ ] 14 new schema tables defined in `node_schema.py`
- [ ] 14 new database methods in `node_database.py`
- [ ] 14 new storage handlers in `node_storage.py`
- [ ] `batch_templates.js` aggregates ALL new keys (BOTH ES + CommonJS)
- [ ] `javascript.py` maps ALL new keys
- [ ] `aud full --offline` completes without errors
- [ ] `pytest tests/test_node_schema_contract.py -v` passes
- [ ] `ruff check theauditor/indexer/` passes
- [ ] Junction tables populated when processing real projects

---

## References

- **Prerequisite:** `normalize-node-extractor-output` (archived 2025-11-26)
- **Audit Evidence:** Opus Agent reports from 2025-11-26 session
- **Architecture:** CLAUDE.md ZERO FALLBACK POLICY (lines 235-289)
- **Protocol:** teamsop.md v4.20 Prime Directive
