# Design: Normalize Node Extractor Output

**Change ID:** `normalize-node-extractor-output`
**Author:** Lead Coder (Opus)
**Date:** 2025-11-26

---

## Context

### Background

TheAuditor uses a polyglot extraction pipeline:
1. **TypeScript Compiler API** parses JS/TS/Vue/Angular files
2. **JavaScript extractors** (`ast_extractors/javascript/*.js`) extract semantic data
3. **batch_templates.js** aggregates extractor output into JSON
4. **Python extractor** (`javascript.py`) receives JSON and routes to storage
5. **Python storage** (`node_storage.py`) calls database methods
6. **Python database** (`node_database.py`) batches inserts

### Problem

The `node-schema-normalization` ticket created database junction tables expecting FLAT arrays.
The JavaScript extractors still produce NESTED objects and RAW STRINGS.
The Python "shredder" tries to parse these but fails silently.

### Stakeholders

- **Architects** need correct schema for taint analysis queries
- **Users** analyzing Vue/Angular projects get incomplete results
- **Downstream tools** (FCE, graph) receive empty junction tables

---

## Goals / Non-Goals

### Goals

1. **Data Completeness:** All 8 junction tables populated with real data
2. **Single Source of Truth:** Normalization happens at extraction (source), not storage (sink)
3. **Zero Data Loss:** Every Vue prop, emit, setup return; every Angular style, declaration, import, provider, export
4. **Backward Compatibility:** No breaking changes to existing output format for working extractors

### Non-Goals

1. **Schema Changes:** Schema is already correct (from `node-schema-normalization`)
2. **New Features:** No new extraction capabilities beyond wiring existing data
3. **Performance Optimization:** Performance is acceptable, focus is correctness
4. **TypeScript Parser Changes:** Parser layer is correct, only post-processing changes

---

## Decisions

### Decision 1: Normalize at Source (JavaScript), Not Sink (Python)

**Choice:** Modify JavaScript extractors to output flat arrays.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **A: Normalize in JS extractors** | Single transformation, close to AST | Requires JS code changes |
| B: Normalize in Python storage | No JS changes needed | Double serialization, fragile parsing |
| C: Normalize in batch_templates.js | Centralized transformation | Additional layer of complexity |

**Rationale:**
- The AST information is available in JavaScript extractors
- Parsing raw strings in Python is fragile (not valid JSON)
- The "shredder" pattern violates single responsibility
- Normalizing at source follows the Python extractor pattern

### Decision 2: Vue Props Parsing Strategy

**Choice:** Parse `defineProps()` TypeScript argument into structured records.

**Technical Approach:**
```javascript
// Input: "{ userId: String, userName: { type: String, required: true } }"
// Output: [
//   { prop_name: "userId", prop_type: "String", is_required: false, default_value: null },
//   { prop_name: "userName", prop_type: "String", is_required: true, default_value: null }
// ]

function parseVuePropsDefinition(propsString, componentName) {
    if (!propsString) return [];

    const props = [];
    // Use regex or simple parser for TypeScript object literal syntax
    // Handle: shorthand (String), object form ({ type: String, required: true })
    // Graceful degradation: if unparseable, log warning and return empty

    return props;
}
```

**Edge Cases:**
- Empty props: Return empty array
- Array syntax (`['userId', 'userName']`): Extract names only, type unknown
- Complex types (`PropType<User>`): Extract raw type string
- Computed props: Skip (dynamic, not static)

### Decision 3: Angular Module Flattening Strategy

**Choice:** Extract module metadata during initial traversal, not as post-processing.

**Technical Approach:**
```javascript
// Current (nested):
results.modules.push({
    name: className,
    declarations: ['ComponentA', 'ComponentB'],
    imports: ['CommonModule', 'RouterModule']
});

// Target (flat):
results.modules.push({ name: className, line: cls.line });
results.angular_module_declarations.push(
    { module_name: className, declaration_name: 'ComponentA', declaration_type: 'component' },
    { module_name: className, declaration_name: 'ComponentB', declaration_type: 'component' }
);
results.angular_module_imports.push(
    { module_name: className, imported_module: 'CommonModule' },
    { module_name: className, imported_module: 'RouterModule' }
);
```

### Decision 4: Error Handling - Graceful Degradation

**Choice:** Log warnings for unparseable data, don't crash extraction.

**Rationale:**
- Better to have partial data than no data
- Edge cases will exist in real-world code
- Warnings provide visibility without blocking pipeline

**Pattern:**
```javascript
try {
    const parsed = parseVuePropsDefinition(propsString, componentName);
    return parsed;
} catch (e) {
    console.warn(`[WARNING] Could not parse props for ${componentName}: ${e.message}`);
    return [];  // Graceful degradation
}
```

### Decision 5: Backward Compatibility

**Choice:** Add new keys alongside existing keys, deprecate old keys.

**Migration Path:**
1. **Phase 1:** Add `vue_component_props` etc. as NEW keys in output
2. **Phase 2:** Python storage checks for new keys first, falls back to old
3. **Phase 3:** (Future ticket) Remove deprecated keys from JS extractors
4. **Phase 4:** (Future ticket) Remove fallback logic from Python

**This ticket implements Phase 1-2 only.**

---

## Risks / Trade-offs

### Risk 1: Parse Errors for Edge Cases

**Risk:** Complex TypeScript syntax may not parse correctly.

**Mitigation:**
- Use defensive parsing with try/catch
- Log warnings for unparseable props
- Return partial data rather than failing completely
- Contract tests verify common patterns work

### Risk 2: Performance Regression

**Risk:** Additional parsing adds CPU overhead.

**Mitigation:**
- Parsing is O(n) on prop count, not file size
- Vue components typically have <20 props
- No benchmark regression expected
- If needed, can cache parsed results

### Risk 3: Breaking Existing Behavior

**Risk:** Changes to extractor output could break downstream consumers.

**Mitigation:**
- Junction tables are currently EMPTY - nothing to break
- Add new keys alongside old keys (backward compatible)
- Python storage already has fallback logic
- Run full test suite before merge

---

## Migration Plan

### Phase 1: JavaScript Extractor Changes

1. Modify `framework_extractors.js`:
   - Add `parseVuePropsDefinition()` function
   - Add `parseVueEmitsDefinition()` function
   - Add `parseSetupReturn()` function
   - Update `extractVueComponents()` return structure

2. Modify `angular_extractors.js`:
   - Add `styleUrls` extraction to `extractAngularComponents()`
   - Flatten module metadata in `extractAngularComponents()`
   - Return new junction arrays

3. Modify `batch_templates.js`:
   - Add 8 new keys to `extracted_data` aggregation

### Phase 2: Python Storage Simplification

1. Modify `javascript.py`:
   - Add new key mappings for junction arrays

2. Modify `node_storage.py`:
   - Add handlers for new junction arrays
   - Keep existing handlers as fallback

3. Modify `node_database.py`:
   - Remove JSON parsing from `add_vue_component()`
   - Remove nested loop from `add_angular_module()`

### Rollback Plan

**Fully Reversible:**
1. Revert JS extractor changes (old output format restored)
2. Revert Python mapping changes
3. Junction tables return to empty state (no data loss - was already empty)

---

## Open Questions

### Resolved

1. **Q: Should we parse defineProps at compile time or runtime?**
   A: Compile time (during extraction). Runtime is not available.

2. **Q: What about Vue 2 vs Vue 3 syntax differences?**
   A: Focus on Vue 3 Composition API. Options API uses different patterns (already working).

3. **Q: Should angular_module_declarations include the type (component/directive/pipe)?**
   A: Yes, include `declaration_type` where inferrable. Default to null if unknown.

### Deferred

1. **Q: Should we add React hook dependency parsing?**
   A: Out of scope for this ticket. `react_hook_dependencies` table exists but is separate concern.

---

## Schema Reference (from node_schema.py)

### Junction Tables

| Table | Columns | Types |
|-------|---------|-------|
| `vue_component_props` | file, component_name, prop_name, prop_type, is_required, default_value | TEXT, TEXT, TEXT, TEXT, INTEGER(0/1), TEXT |
| `vue_component_emits` | file, component_name, emit_name, payload_type | TEXT, TEXT, TEXT, TEXT |
| `vue_component_setup_returns` | file, component_name, return_name, return_type | TEXT, TEXT, TEXT, TEXT |
| `angular_component_styles` | file, component_name, style_path | TEXT, TEXT, TEXT |
| `angular_module_declarations` | file, module_name, declaration_name, declaration_type | TEXT, TEXT, TEXT, TEXT |
| `angular_module_imports` | file, module_name, imported_module | TEXT, TEXT, TEXT |
| `angular_module_providers` | file, module_name, provider_name, provider_type | TEXT, TEXT, TEXT, TEXT |
| `angular_module_exports` | file, module_name, exported_name | TEXT, TEXT, TEXT |

**Note:** `is_required` uses INTEGER (0/1) for SQLite boolean compatibility.

---

## Database Method Signatures (from node_database.py)

These methods ALREADY EXIST. Storage handlers must call them with correct parameters.

### Vue Methods (lines 227-248)

```python
def add_vue_component_prop(self, file: str, component_name: str, prop_name: str,
                           prop_type: str | None = None, is_required: bool = False,
                           default_value: str | None = None)

def add_vue_component_emit(self, file: str, component_name: str, emit_name: str,
                           payload_type: str | None = None)

def add_vue_component_setup_return(self, file: str, component_name: str,
                                   return_name: str, return_type: str | None = None)
```

### Angular Methods (lines 416-450)

```python
def add_angular_component_style(self, file: str, component_name: str, style_path: str)

def add_angular_module_declaration(self, file: str, module_name: str,
                                   declaration_name: str, declaration_type: str | None = None)

def add_angular_module_import(self, file: str, module_name: str, imported_module: str)

def add_angular_module_provider(self, file: str, module_name: str,
                                provider_name: str, provider_type: str | None = None)

def add_angular_module_export(self, file: str, module_name: str, exported_name: str)
```

---

## Current Function Signatures (framework_extractors.js)

### extractVueComponents() - Line 288

```javascript
function extractVueComponents(vueMeta, filePath, functionCallArgs, returns) {
    // vueMeta: { descriptor, hasStyle } from vue-sfc-parser
    // filePath: string - current file path
    // functionCallArgs: Array - all function call arguments from file
    // returns: Array - all return statements from file

    // CURRENT RETURN (lines 319-333):
    return {
        components: [{
            name, type, start_line, end_line,
            has_template, has_style, composition_api_used,
            props_definition,    // <- RAW STRING (to be removed)
            emits_definition,    // <- RAW STRING (to be removed)
            setup_return         // <- RAW STRING (to be removed)
        }],
        primaryName: string
    };
}
```

### extractAngularComponents() - angular_extractors.js Line 97

```javascript
function extractAngularComponents(classes, decorators, functions) {
    // classes: Array - class declarations from AST
    // decorators: Array - decorator metadata from AST
    // functions: Array - function declarations from AST

    // CURRENT RETURN (nested module objects):
    return {
        components: [...],
        services: [...],
        modules: [{
            name, line,
            declarations: [...],  // <- NESTED (to be flattened)
            imports: [...],       // <- NESTED (to be flattened)
            providers: [...],     // <- NESTED (to be flattened)
            exports: [...]        // <- NESTED (to be flattened)
        }],
        guards: [...],
        di_injections: [...]
    };
}
```

---

## Data Flow Diagram

```
BEFORE (Broken):
================
framework_extractors.js
    extractVueComponents()
        -> { components: [{ props_definition: "{ foo: String }" }] }  // STRING BLOB
            |
            v
batch_templates.js
    -> { vue_components: [{ props_definition: "{ foo: String }" }] }  // PASSES THROUGH
            |
            v
javascript.py
    -> maps 'vue_components' key
            |
            v
node_storage.py
    -> _store_vue_components()
        -> db_manager.add_vue_component(..., props_definition="{ foo: String }")
            |
            v
node_database.py
    -> add_vue_component() tries to parse "{ foo: String }" as JSON
        -> FAILS (not valid JSON)
        -> Junction table methods never called
            |
            v
vue_component_props table: EMPTY


AFTER (Fixed):
==============
framework_extractors.js
    extractVueComponents()
        -> {
             vue_components: [{ name, type, start_line, end_line, ... }],  // FLAT
             vue_component_props: [{ component_name, prop_name, prop_type, ... }]  // FLAT
           }
            |
            v
batch_templates.js
    -> { vue_components: [...], vue_component_props: [...] }  // BOTH FLAT
            |
            v
javascript.py
    -> maps 'vue_components' AND 'vue_component_props' keys
            |
            v
node_storage.py
    -> _store_vue_components() handles parent
    -> _store_vue_component_props() handles junction (NEW)
            |
            v
node_database.py
    -> add_vue_component() stores parent only
    -> add_vue_component_prop() stores junction records
            |
            v
vue_component_props table: POPULATED
```

---

## Appendix: Expected Output Structures

### Vue Components (After)

```javascript
// extractVueComponents() return value
{
    vue_components: [
        {
            name: "MyComponent",
            type: "composition",
            start_line: 1,
            end_line: 50,
            has_template: true,
            has_style: true,
            composition_api_used: true
            // NO props_definition, emits_definition, setup_return
        }
    ],
    vue_component_props: [
        {
            component_name: "MyComponent",
            prop_name: "userId",
            prop_type: "String",
            is_required: false,
            default_value: null
        },
        {
            component_name: "MyComponent",
            prop_name: "userName",
            prop_type: "String",
            is_required: true,
            default_value: "'Guest'"
        }
    ],
    vue_component_emits: [
        {
            component_name: "MyComponent",
            emit_name: "update",
            payload_type: "string"
        }
    ],
    vue_component_setup_returns: [
        {
            component_name: "MyComponent",
            return_name: "count",
            return_type: "Ref<number>"
        }
    ]
}
```

### Angular Modules (After)

```javascript
// extractAngularComponents() return value
{
    components: [
        {
            name: "AppComponent",
            line: 10,
            selector: "app-root",
            template_path: "./app.component.html",
            has_lifecycle_hooks: true
            // NO style_paths
        }
    ],
    angular_component_styles: [
        {
            component_name: "AppComponent",
            style_path: "./app.component.scss"
        }
    ],
    modules: [
        {
            name: "AppModule",
            line: 1
            // NO declarations, imports, providers, exports
        }
    ],
    angular_module_declarations: [
        {
            module_name: "AppModule",
            declaration_name: "AppComponent",
            declaration_type: "component"
        }
    ],
    angular_module_imports: [
        {
            module_name: "AppModule",
            imported_module: "BrowserModule"
        },
        {
            module_name: "AppModule",
            imported_module: "RouterModule"
        }
    ],
    angular_module_providers: [
        {
            module_name: "AppModule",
            provider_name: "AuthService",
            provider_type: "class"
        }
    ],
    angular_module_exports: [
        {
            module_name: "AppModule",
            exported_name: "SharedComponent"
        }
    ],
    services: [...],
    guards: [...],
    di_injections: [...]
}
```
