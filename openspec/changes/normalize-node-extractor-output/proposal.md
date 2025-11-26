# Proposal: Normalize Node Extractor Output

**Change ID:** `normalize-node-extractor-output`
**Status:** PROPOSED
**Author:** Lead Coder (Opus)
**Date:** 2025-11-26
**Risk Level:** HIGH
**Prerequisite:** `node-schema-normalization` (COMPLETE)

---

## Why

**The Split Brain Architecture Problem:**

Across 3 completed tickets (`node-fidelity-infrastructure`, `node-schema-normalization`), we built database infrastructure for 8 junction tables - but **ZERO extractor files in `theauditor/ast_extractors/javascript/` were ever modified.**

**Result:** The JavaScript extractors output NESTED JSON blobs, but the Python database layer expects FLAT arrays. The Python "shredder" code attempts to parse these blobs, but the extractors never actually produce the required fields.

**Evidence from Opus Agent Audit (2025-11-26):**

| Junction Table | Expected Source | Actual State |
|----------------|-----------------|--------------|
| `vue_component_props` | `framework_extractors.js` | EMPTY - extractor returns `props_definition` as raw JSON STRING |
| `vue_component_emits` | `framework_extractors.js` | EMPTY - extractor returns `emits_definition` as raw JSON STRING |
| `vue_component_setup_returns` | `framework_extractors.js` | EMPTY - extractor returns raw expression |
| `angular_component_styles` | `angular_extractors.js` | EMPTY - styleUrls NOT EXTRACTED at all |
| `angular_module_declarations` | `angular_extractors.js` | EMPTY - nested in `modules[].declarations` |
| `angular_module_imports` | `angular_extractors.js` | EMPTY - nested in `modules[].imports` |
| `angular_module_providers` | `angular_extractors.js` | EMPTY - nested in `modules[].providers` |
| `angular_module_exports` | `angular_extractors.js` | EMPTY - nested in `modules[].exports` |

**Data Loss Guarantee:** ALL 8 junction tables will remain PERMANENTLY EMPTY for any Vue/Angular project analyzed by TheAuditor.

**Root Cause Chain:**
1. `node-schema-normalization` created 8 junction tables in `node_schema.py` (CORRECT)
2. `node-schema-normalization` created 8 `add_*` methods in `node_database.py` (CORRECT)
3. `node_storage.py` passes junction params to `add_vue_component()` (CORRECT)
4. BUT `javascript.py` maps `vue_components` from `extracted_data` which lacks the fields (BROKEN)
5. AND `framework_extractors.js` returns `props_definition` as raw string, not parsed props (BROKEN)
6. AND `angular_extractors.js` returns nested module objects, not flat junction arrays (BROKEN)

---

## What Changes

### Phase 1: Vue Extractor Normalization (`framework_extractors.js`)

**Goal:** Transform Vue extraction from nested JSON blobs to flat junction arrays.

| Current Output | Target Output |
|----------------|---------------|
| `vue_components[].props_definition` (JSON string) | `vue_component_props[]` (flat array) |
| `vue_components[].emits_definition` (JSON string) | `vue_component_emits[]` (flat array) |
| `vue_components[].setup_return` (JSON string) | `vue_component_setup_returns[]` (flat array) |

**Technical Changes:**
1. Create `parseVuePropsDefinition(propsString, componentName)` - Parse `defineProps()` argument into prop records
2. Create `parseVueEmitsDefinition(emitsString, componentName)` - Parse `defineEmits()` argument into emit records
3. Create `parseSetupReturn(returnExpr, componentName)` - Extract return names from expression
4. Modify `extractVueComponents()` to return 4 separate arrays instead of nested objects
5. Remove `props_definition`, `emits_definition`, `setup_return` fields from component objects

### Phase 2: Angular Extractor Normalization (`angular_extractors.js`)

**Goal:** Transform Angular extraction from nested module objects to flat junction arrays.

| Current Output | Target Output |
|----------------|---------------|
| `modules[].declarations` (nested array) | `angular_module_declarations[]` (flat array) |
| `modules[].imports` (nested array) | `angular_module_imports[]` (flat array) |
| `modules[].providers` (nested array) | `angular_module_providers[]` (flat array) |
| `modules[].exports` (nested array) | `angular_module_exports[]` (flat array) |
| (NOT EXTRACTED) | `angular_component_styles[]` (NEW) |

**Technical Changes:**
1. Add `styleUrls` extraction from `@Component` decorator config
2. Modify `extractAngularComponents()` to return separate `angular_component_styles` array
3. Flatten module metadata into 4 separate junction arrays during extraction
4. Remove `declarations`, `imports`, `providers`, `exports` fields from module objects

### Phase 3: Batch Template Update (`batch_templates.js`)

**Goal:** Aggregate new flat arrays from extractors.

**Technical Changes:**
1. Add new keys to `extracted_data` aggregation:
   - `vue_component_props`
   - `vue_component_emits`
   - `vue_component_setup_returns`
   - `angular_component_styles`
   - `angular_module_declarations`
   - `angular_module_imports`
   - `angular_module_providers`
   - `angular_module_exports`
2. Update destructor calls for Vue and Angular extractors

### Phase 4: Python Storage Simplification

**Goal:** Remove shredder logic from Python - extractors now provide flat data.

**Technical Changes:**
1. Update `node_storage.py:_store_vue_components()` to iterate junction arrays directly
2. Update `node_storage.py:_store_angular_modules()` to iterate junction arrays directly
3. Remove JSON parsing logic from `node_database.py:add_vue_component()`
4. Remove JSON parsing logic from `node_database.py:add_angular_module()`

### Phase 5: Verification

**Goal:** Confirm data flows correctly end-to-end.

**Technical Changes:**
1. Update `scripts/audit_node_extractors.py` to verify flat output
2. Run `aud full --offline` on Vue/Angular project
3. Query junction tables - verify non-zero rows
4. Run `pytest tests/test_node_schema_contract.py -v`

---

## Impact

### Affected Files (10)

| File | Layer | Changes |
|------|-------|---------|
| `theauditor/ast_extractors/javascript/framework_extractors.js` | JS Extractor | Add parsing functions, flatten Vue output |
| `theauditor/ast_extractors/javascript/angular_extractors.js` | JS Extractor | Extract styleUrls, flatten module output |
| `theauditor/ast_extractors/javascript/batch_templates.js` | JS Orchestrator | Aggregate new junction arrays |
| `theauditor/indexer/storage/node_storage.py` | Python Storage | Iterate flat arrays |
| `theauditor/indexer/database/node_database.py` | Python Database | Remove JSON parsing |
| `theauditor/indexer/extractors/javascript.py` | Python Extractor | Map new keys from extracted_data |
| `scripts/audit_node_extractors.py` | Verification | Update to verify flat output |
| `node_extractor_truth.txt` | Documentation | Update expected structure |

### Polyglot Architecture Note

**This is a Node.js + Python change:**
- **Node.js (Source):** `framework_extractors.js`, `angular_extractors.js`, `batch_templates.js` - where data is EXTRACTED
- **Python (Consumer):** `node_storage.py`, `node_database.py`, `javascript.py` - where data is STORED
- **Orchestrator:** `batch_templates.js` IS the JavaScript orchestrator (aggregates extractor output)
- **Rust:** NOT REQUIRED (no Rust in extraction pipeline)

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking existing Vue/Angular extraction | HIGH | Junction tables currently empty - nothing to break |
| Parse errors for edge cases | MEDIUM | Robust error handling, skip unparseable definitions |
| Schema mismatch | LOW | Schema already defined and tested |

### Breaking Changes

**NONE** - This change ADDS data that was previously lost. No existing behavior is removed.

---

## Definition of Done

- [ ] `framework_extractors.js` returns `vue_component_props`, `vue_component_emits`, `vue_component_setup_returns` as flat arrays
- [ ] `angular_extractors.js` returns `angular_component_styles`, `angular_module_*` as flat arrays
- [ ] `batch_templates.js` aggregates all 8 new junction arrays
- [ ] `node_storage.py` iterates junction arrays directly (no JSON parsing)
- [ ] `audit_node_extractors.py` shows FLAT output for all junction tables
- [ ] `aud full --offline` completes without errors
- [ ] Junction tables populated with real data when processing Vue/Angular files
- [ ] `pytest tests/test_node_schema_contract.py -v` passes

---

## References

- **Audit Evidence:** Opus Agent reports from 2025-11-26 session
- **Infrastructure:** `node-schema-normalization` ticket (COMPLETE)
- **Receipts:** `node_receipts.md` in repo root
- **Python Pattern:** `python_schema.py` junction table implementation
- **teamsop.md:** v4.20 compliance verified
