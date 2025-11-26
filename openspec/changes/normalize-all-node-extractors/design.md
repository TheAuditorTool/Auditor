# Design: Normalize All Node.js Extractors

**Change ID:** `normalize-all-node-extractors`
**Author:** Lead Coder (Opus)
**Date:** 2025-11-26

---

## Context

### Background

TheAuditor's Node.js extraction pipeline has a "Split Brain Architecture" where:
1. **JavaScript extractors** produce NESTED arrays and STRING BLOBS
2. **Python storage** expects FLAT arrays for junction table insertion
3. **Result:** 26 violations across 6 files causing data loss

### Prerequisite Work

The `normalize-node-extractor-output` ticket (2025-11-26) established the pattern:
1. Normalization happens at SOURCE (JavaScript extractors)
2. Python storage iterates flat arrays directly
3. No JSON parsing in database layer
4. No try/except fallbacks (ZERO FALLBACK)

### Stakeholders

- **Taint Analysis:** Needs `source_vars`, `return_vars` for propagation
- **Security Rules:** Needs CDK properties for misconfiguration detection
- **ORM Analysis:** Needs Sequelize model fields for schema queries
- **Graph Analysis:** Needs flat CFG for efficient traversal

---

## Goals / Non-Goals

### Goals

1. **Complete Normalization:** ALL Node.js extractors produce flat arrays
2. **Zero Data Loss:** Every nested array becomes a junction table
3. **ZERO FALLBACK:** Single code path, no fallbacks, no compatibility shims
4. **Pattern Consistency:** Same pattern as Vue/Angular normalization

### Non-Goals

1. **Python Extractor Changes:** Python extractors already normalized
2. **New Features:** No new extraction capabilities, only format change
3. **Performance Optimization:** Format change should be perf-neutral
4. **Rust Changes:** Rust not involved in extraction pipeline

---

## Decisions

### Decision 1: Phase Order by Impact

**Choice:** Order phases by taint analysis impact:
1. Core Language (function params/decorators) - enables security rule queries
2. Data Flow (source_vars/return_vars) - enables taint propagation
3. Module Framework - enables import tracking
4. Security Extractors - enables CDK analysis
5. Sequelize - enables ORM schema queries
6. CFG - enables graph queries

**Rationale:** Core Language and Data Flow are CRITICAL for taint analysis. Other phases can be done in any order.

### Decision 2: Schema Design Pattern

**Choice:** Junction tables with composite foreign keys, same as Vue/Angular.

**Pattern:**
```python
FUNC_PARAMS = TableSchema(
    name="func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),  # Order matters
        Column("param_name", "TEXT", nullable=False),
        Column("param_type", "TEXT"),  # TypeScript type annotation
    ],
    indexes=[
        ("idx_func_params_function", ["file", "function_line"]),
        ("idx_func_params_name", ["param_name"]),
    ]
)
```

**Rationale:**
- Composite FK (file, line) allows joining to parent symbols table
- `param_index` preserves parameter order (critical for call matching)
- Matches existing pattern from Vue/Angular junction tables

### Decision 3: Decorator Flattening Strategy

**Choice:** Three-level hierarchy: Function -> Decorator -> Argument

**Structure:**
```
functions (parent)
  └── func_decorators (junction level 1)
        └── func_decorator_args (junction level 2)
```

**Example:**
```typescript
@Get('/users/:id')
@Auth({ role: 'admin', level: 2 })
async getUser(@Param('id') id: string) { }
```

Becomes:
```
func_decorators: [
  { function_name: 'getUser', decorator_index: 0, decorator_name: 'Get', line: 1 },
  { function_name: 'getUser', decorator_index: 1, decorator_name: 'Auth', line: 2 }
]
func_decorator_args: [
  { function_name: 'getUser', decorator_index: 0, arg_index: 0, arg_value: '/users/:id' },
  { function_name: 'getUser', decorator_index: 1, arg_index: 0, arg_value: '{ role: ... }' }
]
```

**Rationale:** Security rules need to query "all @Auth decorators with role=admin". Flat structure enables this.

### Decision 4: Data Flow Source Variables

**Choice:** Separate `assignment_source_vars` and `return_source_vars` tables.

**Example:**
```typescript
const result = foo + bar * baz;  // source_vars: ['foo', 'bar', 'baz']
return { x, y, z };              // return_vars: ['x', 'y', 'z']
```

Becomes:
```
assignment_source_vars: [
  { file, line, target_var: 'result', source_var: 'foo', var_index: 0 },
  { file, line, target_var: 'result', source_var: 'bar', var_index: 1 },
  { file, line, target_var: 'result', source_var: 'baz', var_index: 2 }
]
return_source_vars: [
  { file, line, function_name, source_var: 'x', var_index: 0 },
  { file, line, function_name, source_var: 'y', var_index: 1 },
  { file, line, function_name, source_var: 'z', var_index: 2 }
]
```

**Rationale:** Taint analysis needs to trace "what variables flow into this assignment" and "what variables are returned". Index preserves order for positional matching.

### Decision 5: Import Specifier Aliases

**Choice:** Capture BOTH original name and local alias.

**Example:**
```typescript
import { useState as useS, useEffect } from 'react';
import axios, { AxiosError as AE } from 'axios';
```

Becomes:
```
import_specifiers: [
  { import_line: 1, specifier_name: 'useS', original_name: 'useState', is_default: 0, is_named: 1 },
  { import_line: 1, specifier_name: 'useEffect', original_name: 'useEffect', is_default: 0, is_named: 1 },
  { import_line: 2, specifier_name: 'axios', original_name: null, is_default: 1, is_named: 0 },
  { import_line: 2, specifier_name: 'AE', original_name: 'AxiosError', is_default: 0, is_named: 1 }
]
```

**Rationale:** Security rules need to know both "what symbol is imported" (original_name) and "what symbol is used in code" (specifier_name).

### Decision 6: CDK Property Type Inference

**Choice:** Infer `value_type` from syntax analysis.

**Type Detection:**
```javascript
function inferPropertyType(value) {
    if (value === 'true' || value === 'false') return 'boolean';
    if (/^['"]/.test(value)) return 'string';
    if (/^\d+$/.test(value)) return 'number';
    if (/^\[/.test(value)) return 'array';
    if (/^\{/.test(value)) return 'object';
    return 'variable';  // References a variable
}
```

**Rationale:** CDK security rules need to distinguish `publicReadAccess: true` (boolean literal - DANGEROUS) from `publicReadAccess: envConfig.isPublic` (variable - needs further analysis).

### Decision 7: Sequelize Model Field Extraction

**Choice:** Parse first argument of `Model.init()` call.

**Example:**
```typescript
User.init({
  id: { type: DataTypes.INTEGER, primaryKey: true },
  email: { type: DataTypes.STRING, allowNull: false, unique: true },
  role: { type: DataTypes.ENUM('admin', 'user'), defaultValue: 'user' }
}, { tableName: 'users', sequelize });
```

Becomes:
```
sequelize_model_fields: [
  { model_name: 'User', field_name: 'id', data_type: 'INTEGER', is_primary_key: 1, is_nullable: 1, default_value: null },
  { model_name: 'User', field_name: 'email', data_type: 'STRING', is_primary_key: 0, is_nullable: 0, default_value: null },
  { model_name: 'User', field_name: 'role', data_type: 'ENUM', is_primary_key: 0, is_nullable: 1, default_value: "'user'" }
]
```

**Rationale:** Security rules need to query "all models with email field" or "all fields that allow null without default".

### Decision 8: CFG Flattening Strategy

**Choice:** Four separate tables: cfgs, cfg_blocks, cfg_edges, cfg_block_statements

**Rationale:** Graph queries need to:
- Find all blocks in a function (cfg_blocks)
- Traverse edges (cfg_edges with source/target)
- Analyze statements per block (cfg_block_statements)

Nested structure makes all these queries require JSON parsing. Flat structure enables SQL joins.

### Decision 9: Error Handling - Reconciling ZERO FALLBACK

**Problem:** CLAUDE.md mandates ZERO FALLBACK, but AST parsing can fail on complex TypeScript.

**Resolution:** Distinguish between ERROR TYPES:

| Error Type | Source | Policy | Example |
|------------|--------|--------|---------|
| STRUCTURAL | Our code | HARD FAIL | Missing table, wrong column, bad FK |
| EXTERNAL | Input code | GRACEFUL SKIP | Unparseable TS syntax, malformed decorator |

**ZERO FALLBACK applies to STRUCTURAL errors:**
- If table doesn't exist → crash (our schema bug)
- If column mismatch → crash (our code bug)
- If FK constraint fails → crash (our data integrity bug)
- NO try/except to hide these. NO fallback queries.

**GRACEFUL SKIP for EXTERNAL parse errors:**
- If decorator AST can't be parsed → log warning, return empty array for THAT decorator
- If TypeScript type is too complex → skip THAT type, continue file
- Partial data > no data (external code quality is not our bug)

**Implementation Pattern:**
```javascript
// CORRECT: Skip unparseable item, continue processing
function flattenDecorators(decorators, functionName, functionLine) {
    const result = [];
    for (const dec of decorators) {
        try {
            result.push(extractDecoratorData(dec, functionName, functionLine));
        } catch (e) {
            // EXTERNAL parse error - log and skip THIS decorator
            console.warn(`[WARN] Could not parse decorator at ${functionLine}: ${e.message}`);
            // Continue processing other decorators
        }
    }
    return result;
}
```

**Anti-Pattern (BANNED):**
```javascript
// WRONG: Catch-all hiding STRUCTURAL errors
try {
    db.add_func_decorator(data);  // STRUCTURAL - should crash on failure
} catch (e) {
    // BANNED - this hides schema/FK bugs
    return [];
}
```

**Rationale:** ZERO FALLBACK prevents hiding OUR bugs. Graceful skip handles THEIR malformed code without crashing the entire pipeline.

---

## Risks / Trade-offs

### Risk 1: Large Number of New Tables

**Risk:** ~15 new tables increases schema complexity.

**Mitigation:**
- Tables are logically grouped by extractor domain
- Same pattern as existing junction tables (Vue/Angular)
- No migration needed (new tables, no data loss)

### Risk 2: Breaking Existing Queries

**Risk:** Code querying `functions[].parameters` will break.

**Mitigation:**
- This is INTENTIONAL (ZERO FALLBACK policy)
- Failures will be LOUD (expose hidden dependencies)
- All known consumers are internal (no external API)

### Risk 3: Parse Errors in JS Extractors

**Risk:** Complex TypeScript syntax may not parse correctly.

**Mitigation:**
- Same pattern as Vue/Angular: log warning, return empty array
- Partial data better than no data
- Contract tests verify common patterns

---

## Migration Plan

### Phase 1: Schema First

1. Add all ~15 new TableSchema definitions to `node_schema.py`
2. Run `aud full --index` to create tables
3. Verify tables exist with PRAGMA queries

### Phase 2: Extractor Changes (Per File)

For each of the 6 files:
1. Add flattening helper functions
2. Modify return structure to include new flat arrays
3. Keep parent record structure (don't remove yet)
4. Test with `npm test` in ast_extractors directory

### Phase 3: Batch Template Update

1. Update ES Module version to aggregate new keys
2. Update CommonJS version (MUST mirror ES Module)
3. Verify both versions produce identical output

### Phase 4: Python Storage

1. Add database methods to `node_database.py`
2. Add storage handlers to `node_storage.py`
3. Add key mappings to `javascript.py`
4. Run contract tests

### Phase 5: Cleanup

1. Remove deprecated nested fields from parent records
2. Update any code querying old structure
3. Run full pipeline verification

### Rollback Plan

**Fully Reversible:**
1. Revert JS extractor changes (old nested format restored)
2. New tables remain but are unused (no harm)
3. No data loss (tables were empty before)

---

## Open Questions

### Resolved

1. **Q: Should we parallelize Phase 1 and 2?**
   A: Yes, Core Language and Data Flow can execute in parallel.

2. **Q: Should cfg_block_statements include AST node type?**
   A: Yes, include `statement_type` for control flow analysis.

3. **Q: Should we track import specifier order?**
   A: No, order doesn't matter for imports. Index not needed.

### Resolved

4. **Q: Should we add React hook dependency tracking?**
   A: YES. Schema already has `react_component_hooks` and `react_hook_dependencies` tables but extractors don't populate them. This ticket normalizes ALL extractors, React included. Add to Phase 2 (framework_extractors.js was partially fixed for Vue in previous ticket, now complete React section).

---

## Appendix: Complete Schema Definitions

### func_params
```python
FUNC_PARAMS = TableSchema(
    name="func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("param_type", "TEXT"),
    ],
    indexes=[
        ("idx_func_params_function", ["file", "function_line", "function_name"]),
        ("idx_func_params_name", ["param_name"]),
    ]
)
```

### func_decorators
```python
FUNC_DECORATORS = TableSchema(
    name="func_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_line", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_func_decorators_function", ["file", "function_line"]),
        ("idx_func_decorators_name", ["decorator_name"]),
    ]
)
```

### func_decorator_args
```python
FUNC_DECORATOR_ARGS = TableSchema(
    name="func_decorator_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("arg_index", "INTEGER", nullable=False),
        Column("arg_value", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_func_decorator_args_decorator", ["file", "function_line", "decorator_index"]),
    ]
)
```

### assignment_source_vars
```python
ASSIGNMENT_SOURCE_VARS = TableSchema(
    name="assignment_source_vars",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_var", "TEXT", nullable=False),
        Column("source_var", "TEXT", nullable=False),
        Column("var_index", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_assignment_source_vars_assignment", ["file", "line", "target_var"]),
        ("idx_assignment_source_vars_source", ["source_var"]),
    ]
)
```

### return_source_vars
```python
RETURN_SOURCE_VARS = TableSchema(
    name="return_source_vars",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("source_var", "TEXT", nullable=False),
        Column("var_index", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_return_source_vars_return", ["file", "line"]),
        ("idx_return_source_vars_source", ["source_var"]),
    ]
)
```

### import_specifiers
```python
IMPORT_SPECIFIERS = TableSchema(
    name="import_specifiers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("import_line", "INTEGER", nullable=False),
        Column("specifier_name", "TEXT", nullable=False),
        Column("original_name", "TEXT"),  # For aliased imports
        Column("is_default", "INTEGER", default="0"),
        Column("is_namespace", "INTEGER", default="0"),
        Column("is_named", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_import_specifiers_import", ["file", "import_line"]),
        ("idx_import_specifiers_name", ["specifier_name"]),
    ]
)
```

### cdk_construct_properties
```python
CDK_CONSTRUCT_PROPERTIES = TableSchema(
    name="cdk_construct_properties",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("construct_line", "INTEGER", nullable=False),
        Column("construct_name", "TEXT", nullable=False),
        Column("property_name", "TEXT", nullable=False),
        Column("value_expr", "TEXT", nullable=False),
        Column("value_type", "TEXT"),  # boolean, string, number, array, object, variable
    ],
    indexes=[
        ("idx_cdk_construct_properties_construct", ["file", "construct_line"]),
        ("idx_cdk_construct_properties_name", ["property_name"]),
    ]
)
```

### sequelize_model_fields
```python
SEQUELIZE_MODEL_FIELDS = TableSchema(
    name="sequelize_model_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("data_type", "TEXT", nullable=False),
        Column("is_primary_key", "INTEGER", default="0"),
        Column("is_nullable", "INTEGER", default="1"),
        Column("is_unique", "INTEGER", default="0"),
        Column("default_value", "TEXT"),
    ],
    indexes=[
        ("idx_sequelize_model_fields_model", ["file", "model_name"]),
        ("idx_sequelize_model_fields_type", ["data_type"]),
    ]
)
```

### cfg_blocks
```python
CFG_BLOCKS = TableSchema(
    name="cfg_blocks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("block_id", "INTEGER", nullable=False),
        Column("block_type", "TEXT", nullable=False),  # entry, exit, basic, condition, loop, etc.
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("condition_expr", "TEXT"),  # For condition/loop blocks
    ],
    indexes=[
        ("idx_cfg_blocks_function", ["file", "function_name"]),
    ]
)
```

### cfg_edges
```python
CFG_EDGES = TableSchema(
    name="cfg_edges",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("source_block_id", "INTEGER", nullable=False),
        Column("target_block_id", "INTEGER", nullable=False),
        Column("edge_type", "TEXT", nullable=False),  # normal, true, false, exception, back_edge
    ],
    indexes=[
        ("idx_cfg_edges_function", ["file", "function_name"]),
        ("idx_cfg_edges_source", ["source_block_id"]),
        ("idx_cfg_edges_target", ["target_block_id"]),
    ]
)
```

### class_decorators
```python
CLASS_DECORATORS = TableSchema(
    name="class_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("class_line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_line", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_class_decorators_class", ["file", "class_line"]),
        ("idx_class_decorators_name", ["decorator_name"]),
    ]
)
```

### class_decorator_args
```python
CLASS_DECORATOR_ARGS = TableSchema(
    name="class_decorator_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("class_line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("arg_index", "INTEGER", nullable=False),
        Column("arg_value", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_class_decorator_args_decorator", ["file", "class_line", "decorator_index"]),
    ]
)
```

### func_param_decorators
```python
FUNC_PARAM_DECORATORS = TableSchema(
    name="func_param_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_args", "TEXT"),  # Stringified args like "'id'" or "{ transform: parseInt }"
    ],
    indexes=[
        ("idx_func_param_decorators_function", ["file", "function_line", "function_name"]),
        ("idx_func_param_decorators_decorator", ["decorator_name"]),
    ]
)
```

### cfg_block_statements
```python
CFG_BLOCK_STATEMENTS = TableSchema(
    name="cfg_block_statements",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("block_id", "INTEGER", nullable=False),
        Column("statement_index", "INTEGER", nullable=False),
        Column("statement_type", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("text", "TEXT"),
    ],
    indexes=[
        ("idx_cfg_block_statements_block", ["file", "function_name", "block_id"]),
    ]
)
```

---

## Appendix: EXISTING Schema Definitions (To Wire, Not Create)

These tables ALREADY EXIST in `node_schema.py` but extractors don't populate them. This ticket wires them.

### react_component_hooks (EXISTS - lines 77-97)
```python
REACT_COMPONENT_HOOKS = TableSchema(
    name="react_component_hooks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("component_file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),  # 1 row per hook used
    ],
    indexes=[
        ("idx_react_comp_hooks_component", ["component_file", "component_name"]),
        ("idx_react_comp_hooks_hook", ["hook_name"]),
        ("idx_react_comp_hooks_file", ["component_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["component_file", "component_name"],
            foreign_table="react_components",
            foreign_columns=["file", "name"]
        )
    ]
)
```

### react_hook_dependencies (EXISTS - lines 122-142)
```python
REACT_HOOK_DEPENDENCIES = TableSchema(
    name="react_hook_dependencies",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("hook_file", "TEXT", nullable=False),
        Column("hook_line", "INTEGER", nullable=False),
        Column("hook_component", "TEXT", nullable=False),
        Column("dependency_name", "TEXT", nullable=False),  # 1 row per dependency variable
    ],
    indexes=[
        ("idx_react_hook_deps_hook", ["hook_file", "hook_line", "hook_component"]),
        ("idx_react_hook_deps_name", ["dependency_name"]),
        ("idx_react_hook_deps_file", ["hook_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["hook_file", "hook_line", "hook_component"],
            foreign_table="react_hooks",
            foreign_columns=["file", "line", "component_name"]
        )
    ]
)
```

### import_style_names (EXISTS - lines 496-516)
```python
IMPORT_STYLE_NAMES = TableSchema(
    name="import_style_names",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("import_file", "TEXT", nullable=False),
        Column("import_line", "INTEGER", nullable=False),
        Column("imported_name", "TEXT", nullable=False),  # 1 row per imported name
    ],
    indexes=[
        ("idx_import_style_names_import", ["import_file", "import_line"]),
        ("idx_import_style_names_name", ["imported_name"]),
        ("idx_import_style_names_file", ["import_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["import_file", "import_line"],
            foreign_table="import_styles",
            foreign_columns=["file", "line"]
        )
    ]
)
```

---

## Appendix: javascript.py Key Mapping Pattern

**Location:** `theauditor/indexer/extractors/javascript.py` lines 144-172

The Python extractor maps JavaScript extraction keys to Python result keys. This is how data flows from JS → Python.

### Current Pattern (from javascript.py)
```python
# Map all new Phase 5 keys
key_mappings = {
    'import_styles': 'import_styles',
    'resolved_imports': 'resolved_imports',
    'react_components': 'react_components',
    'react_hooks': 'react_hooks',
    'vue_components': 'vue_components',
    # Vue junction arrays (normalize-node-extractor-output)
    'vue_component_props': 'vue_component_props',
    'vue_component_emits': 'vue_component_emits',
    'vue_component_setup_returns': 'vue_component_setup_returns',
    # Angular junction arrays (normalize-node-extractor-output)
    'angular_component_styles': 'angular_component_styles',
    'angular_module_declarations': 'angular_module_declarations',
    # ... more mappings
}

for js_key, python_key in key_mappings.items():
    if js_key in extracted_data:
        result[python_key] = extracted_data[js_key]
```

### NEW Mappings to Add (This Ticket)
```python
# Add to key_mappings dict in javascript.py:
key_mappings = {
    # ... existing mappings ...

    # Core Language junction arrays (normalize-all-node-extractors)
    'func_params': 'func_params',
    'func_decorators': 'func_decorators',
    'func_decorator_args': 'func_decorator_args',
    'func_param_decorators': 'func_param_decorators',
    'class_decorators': 'class_decorators',
    'class_decorator_args': 'class_decorator_args',

    # Data Flow junction arrays
    'assignment_source_vars': 'assignment_source_vars',
    'return_source_vars': 'return_source_vars',

    # Module Framework junction arrays
    'import_specifiers': 'import_specifiers',
    'import_style_names': 'import_style_names',

    # Security junction arrays
    'cdk_construct_properties': 'cdk_construct_properties',

    # ORM junction arrays
    'sequelize_model_fields': 'sequelize_model_fields',

    # CFG junction arrays
    'cfg_blocks': 'cfg_blocks',
    'cfg_edges': 'cfg_edges',
    'cfg_block_statements': 'cfg_block_statements',

    # React junction arrays (wiring existing tables)
    'react_component_hooks': 'react_component_hooks',
    'react_hook_dependencies': 'react_hook_dependencies',
}
```

### Also Add to result Dict Initialization (lines 50-104)
```python
result = {
    # ... existing keys ...

    # Core Language junction arrays (normalize-all-node-extractors)
    'func_params': [],
    'func_decorators': [],
    'func_decorator_args': [],
    'func_param_decorators': [],
    'class_decorators': [],
    'class_decorator_args': [],

    # Data Flow junction arrays
    'assignment_source_vars': [],
    'return_source_vars': [],

    # Module Framework junction arrays
    'import_specifiers': [],
    'import_style_names': [],

    # Security junction arrays
    'cdk_construct_properties': [],

    # ORM junction arrays
    'sequelize_model_fields': [],

    # CFG junction arrays
    'cfg_blocks': [],
    'cfg_edges': [],
    'cfg_block_statements': [],

    # React junction arrays (wiring existing tables)
    'react_component_hooks': [],
    'react_hook_dependencies': [],
}
```
