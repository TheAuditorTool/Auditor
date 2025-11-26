# Verification Report: normalize-node-extractor-output

**Date:** 2025-11-26
**Auditor:** Lead Coder (Opus) with Opus Agent Support
**Protocol:** teamsop.md v4.20 Prime Directive (Verify Before Acting)
**Status:** COMPLETE - All hypotheses verified with source code evidence

---

## Executive Summary

Two Opus agents were dispatched to read 100% of JavaScript extractor files (50/50 split).
**Verdict:** Split Brain Architecture CONFIRMED. Infrastructure exists, data flow is broken.

---

## Files Audited

### Agent 1 (Files 1-5):
| File | Lines | Verdict |
|------|-------|---------|
| `angular_extractors.js` | 1-286 | **BROKEN** |
| `batch_templates.js` | 1-1095 | **NEEDS_REFACTOR** |
| `bullmq_extractors.js` | 1-103 | OK |
| `cfg_extractor.js` | 1-566 | OK |
| `core_language.js` | 1-819 | OK |

### Agent 2 (Files 6-10):
| File | Lines | Verdict |
|------|-------|---------|
| `data_flow.js` | 1-1043 | OK |
| `framework_extractors.js` | 1-681 | **BROKEN** |
| `security_extractors.js` | 1-1215 | OK (minor) |
| `sequelize_extractors.js` | 1-156 | OK |
| `module_framework.js` | 1-568 | OK |

---

## Hypothesis 1: Vue extractors return nested JSON blobs instead of flat arrays

**Verification:** CONFIRMED

**Evidence from `framework_extractors.js`:**

**Lines 295-296** - Raw macro calls stored as strings:
```javascript
const propsDefinition = findFirstVueMacroCall(functionCallArgs, 'defineProps');
const emitsDefinition = findFirstVueMacroCall(functionCallArgs, 'defineEmits');
```

**Lines 269-282** - `findFirstVueMacroCall()` returns raw `argument_expr`:
```javascript
function findFirstVueMacroCall(functionCallArgs, macroName) {
    ...
    if (call.argument_expr && call.argument_expr.trim()) {
        return truncateVueString(call.argument_expr.trim());  // RAW STRING BLOB
    }
    ...
}
```

**Lines 319-333** - Nested fields in component object:
```javascript
return {
    components: [{
        props_definition: propsDefinition,   // JSON STRING, NOT FLAT ARRAY
        emits_definition: emitsDefinition,   // JSON STRING, NOT FLAT ARRAY
        setup_return: setupReturnExpr        // JSON STRING, NOT FLAT ARRAY
    }]
};
```

**Impact:** `vue_component_props`, `vue_component_emits`, `vue_component_setup_returns` tables EMPTY.

---

## Hypothesis 2: Angular extractors return nested module objects instead of flat arrays

**Verification:** CONFIRMED

**Evidence from `angular_extractors.js`:**

**Lines 169-189** - Module returns nested arrays:
```javascript
results.modules.push({
    name: className,
    line: cls.line,
    ...moduleConfig  // Contains declarations[], imports[], providers[], exports[]
});
```

**Lines 176-179** - moduleConfig structure:
```javascript
moduleConfig.declarations = config.declarations || []
moduleConfig.imports = config.imports || []
moduleConfig.providers = config.providers || []
moduleConfig.exports = config.exports || []
```

**Impact:** `angular_module_declarations`, `angular_module_imports`, `angular_module_providers`, `angular_module_exports` tables EMPTY.

---

## Hypothesis 3: Angular component styleUrls are not extracted

**Verification:** CONFIRMED

**Evidence from `angular_extractors.js` lines 121-127:**
```javascript
results.components.push({
    name: className,
    line: cls.line,
    inputs_count: inputs.length,
    outputs_count: outputs.length,
    has_lifecycle_hooks: _detectAngularLifecycleHooks(cls, functions)
    // NO styleUrls extraction!
});
```

**Impact:** `angular_component_styles` table EMPTY.

---

## Hypothesis 4: batch_templates.js has no flattening logic

**Verification:** CONFIRMED

**Evidence from `batch_templates.js` lines 517-526:**
```javascript
angular_components: angularData.components || [],
angular_services: angularData.services || [],
angular_modules: angularData.modules || [],  // STILL NESTED
angular_guards: angularData.guards || [],
di_injections: angularData.di_injections || [],
```

**Impact:** Nested data passes straight through to Python with no transformation.

---

## Hypothesis 5: Python storage expects flat junction arrays

**Verification:** CONFIRMED

**Evidence from `node_storage.py` lines 60-78:**
```python
def _store_vue_components(self, file_path: str, vue_components: list, jsx_pass: bool):
    for component in vue_components:
        self.db_manager.add_vue_component(
            file_path,
            component['name'],
            component['type'],
            component['start_line'],
            component['end_line'],
            component.get('has_template', False),
            component.get('has_style', False),
            component.get('composition_api_used', False),
            component.get('props_definition'),     # <- WILL BE None or raw string
            component.get('emits_definition'),     # <- WILL BE None or raw string
            component.get('setup_return')          # <- WILL BE None or raw string
        )
```

**Evidence from `node_database.py` junction dispatchers:**
The `add_vue_component()` method has logic to parse `props_definition` string into junction table records - but this only works if the string is parseable JSON, which the extractor doesn't guarantee.

---

## Hypothesis 6: Database junction methods exist and are correct

**Verification:** CONFIRMED

**Evidence from `node_database.py`:**
- `add_vue_component_prop()` - EXISTS (added by node-schema-normalization)
- `add_vue_component_emit()` - EXISTS
- `add_vue_component_setup_return()` - EXISTS
- `add_angular_component_style()` - EXISTS
- `add_angular_module_declaration()` - EXISTS
- `add_angular_module_import()` - EXISTS
- `add_angular_module_provider()` - EXISTS
- `add_angular_module_export()` - EXISTS

**All 8 methods use `self.generic_batches` pattern correctly.**

---

## Root Cause Analysis

### Surface Symptom
8 junction tables are permanently empty for all Vue/Angular projects.

### Problem Chain
1. `node-schema-normalization` ticket scoped ONLY database layer changes
2. Task list had "Modify `add_vue_component()` to parse `props_definition` JSON" (task 1.1.3)
3. This assumes extractors provide parseable JSON - **THEY DON'T**
4. Extractors return raw TypeScript expression strings like `"{ userId: String }"`
5. These strings are NOT valid JSON, so parsing fails silently
6. Junction table methods receive None, store nothing

### Actual Root Cause
**Ticket scope creep prevention:** The `node-schema-normalization` ticket explicitly avoided modifying JavaScript files to keep scope bounded. This was the correct decision for ticket isolation, but created a dependency gap.

### Why This Happened
- **Design Decision:** Keep database-layer and extractor-layer tickets separate
- **Missing Safeguard:** No cross-ticket dependency tracking for "data must flow"
- **Good News:** The infrastructure is correct - only the data source needs fixing

---

## Discrepancies Found

| Prompt Assumption | Reality |
|-------------------|---------|
| "Junction tables replace JSON blobs" | Junction tables EXIST but are EMPTY |
| "Extractors produce props_definition" | Extractors produce raw STRINGS, not parsed props |
| "add_vue_component() parses JSON" | Parsing logic exists but strings aren't valid JSON |
| "Angular modules have junction data" | Module objects have NESTED arrays, not flat arrays |

---

## Verification Conclusion

**ALL 6 HYPOTHESES CONFIRMED.**

The Split Brain Architecture is real:
- **Right Brain (Database):** 8 junction tables with correct schema, 8 add_* methods with correct batching
- **Left Brain (Extractors):** Output format unchanged, producing nested/string data incompatible with junction tables

**The fix is clear:** Move normalization LEFT into the JavaScript extractors.

---

## Files Requiring Changes

| File | Location | Change Type |
|------|----------|-------------|
| `framework_extractors.js` | `theauditor/ast_extractors/javascript/` | MODIFY - Parse Vue macros into flat arrays |
| `angular_extractors.js` | `theauditor/ast_extractors/javascript/` | MODIFY - Flatten module data, add styleUrls |
| `batch_templates.js` | `theauditor/ast_extractors/javascript/` | MODIFY - Aggregate new junction keys |
| `node_storage.py` | `theauditor/indexer/storage/` | SIMPLIFY - Remove JSON parsing |
| `node_database.py` | `theauditor/indexer/database/` | SIMPLIFY - Remove shredder logic |
| `javascript.py` | `theauditor/indexer/extractors/` | MODIFY - Map new junction keys |

---

*Verification completed per teamsop.md v4.20 Prime Directive*
*Evidence gathered by 2 Opus agents reading 100% of extractor source code*
