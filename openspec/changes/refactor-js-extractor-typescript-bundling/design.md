## Context

TheAuditor is a polyglot static analysis tool with Python orchestration and Node.js/TypeScript extraction. The JS extraction layer uses string concatenation at runtime to assemble 9 `.js` files into a single executable script. This was expedient for initial development but creates significant maintainability debt.

**Stakeholders:**
- Architect (Human): Approves architectural changes
- Lead Auditor (Gemini): Reviews implementation quality
- AI Coder (Opus): Implements changes following Prime Directive

**Constraints:**
- Must maintain 100% backward compatibility with Python ingestion layer
- Must not break existing extraction output format
- Must work in Windows + WSL environment
- Must integrate with existing `aud full --index` pipeline

## Goals / Non-Goals

### Goals
1. **Compile-time safety**: Catch typos, missing functions, signature mismatches at build time
2. **IDE support**: Enable ctrl+click navigation, autocomplete, refactoring across extractor files
3. **Data fidelity**: Validate extraction output shape INSIDE Node.js before Python receives it
4. **Debuggability**: Stack traces point to actual source files, not temp concatenation
5. **ESLint accuracy**: Eliminate 44+ false "unused variable" warnings

### Non-Goals
1. **Changing output format**: JSON shape remains identical to current output
2. **Adding new extractors**: This is infrastructure-only, not feature work
3. **Performance optimization**: Focus is correctness, not speed
4. **Micro-service architecture**: Keep simple subprocess model

## Decisions

### Decision 1: TypeScript + Zod over Plain JavaScript + JSDoc

**What:** Convert `.js` extractors to `.ts` with Zod runtime validation

**Why:**
- TypeScript provides compile-time type checking that JSDoc cannot enforce
- Zod provides runtime validation - if extraction output is malformed, error is thrown BEFORE Python
- Combined: compile-time + runtime safety eliminates silent data corruption

**Alternatives Considered:**
| Alternative | Rejected Because |
|-------------|------------------|
| JSDoc annotations only | No enforcement - just comments |
| JSON Schema validation | External file, harder to maintain in sync |
| Keep concatenation + add runtime checks | Still no compile-time safety |

### Decision 2: esbuild over Webpack/Rollup/tsc

**What:** Use esbuild for bundling TypeScript to single JS file

**Why:**
- esbuild is 10-100x faster than alternatives
- Single command: `esbuild src/main.ts --bundle --platform=node --outfile=dist/extractor.js`
- Zero configuration for basic use case
- Already proven in TheAuditor ecosystem (used for other builds)

**Build Command:**
```bash
esbuild src/main.ts --bundle --platform=node --target=node18 --format=esm --outfile=dist/extractor.js
```

**Alternatives Considered:**
| Alternative | Rejected Because |
|-------------|------------------|
| Webpack | Overkill, slow, complex config |
| Rollup | Good but more config needed |
| tsc + no bundling | Would require runtime import resolution |

### Decision 3: Keep Python Orchestrator Pattern

**What:** Python still spawns Node.js subprocess, but reads pre-compiled bundle

**Why:**
- Minimal change to existing architecture
- `ast_parser.py` unchanged - still calls `get_batch_helper()`
- Only `js_helper_templates.py` simplified

**Python Compatibility Boundary:**
- File: `theauditor/ast_extractors/js_helper_templates.py`
- Function: `get_batch_helper()` (line 48-89) - reads JS and returns as string
- Function: `_load_javascript_modules()` (line 15-46) - WILL BE REMOVED

**Alternatives Considered:**
| Alternative | Rejected Because |
|-------------|------------------|
| Embed V8 in Python | Major complexity, licensing issues |
| Python calls Node.js API directly | Requires persistent Node process |
| Convert extractors to Python | Lose TypeScript Compiler API |

### Decision 4: Schema Mirrors Python Domain Objects

**What:** Zod schema in `src/schema.ts` exactly mirrors what `javascript.py` expects

**Why:**
- Creates explicit contract between Node extraction and Python ingestion
- If schema changes, both sides must update together
- Validation failure in Node = immediate error, not silent corruption in Python

### Decision 5: Semantic Extraction via TypeChecker (from discussions.md)

**What:** Use TypeScript's semantic API (`ts.TypeChecker`) instead of text-based parsing

**Why:**
- Text parsing (`node.getText()`) loses semantic information (aliases, inheritance, cross-file references)
- TypeChecker provides "God View" - resolves symbols, types, inheritance across entire program
- Fixes the "anonymous caller" bug where `db.User.findAll()` couldn't be traced to actual model

**Semantic Upgrades Required:**

| Function | Current (Text-Based) | New (Semantic) |
|----------|---------------------|----------------|
| `extractClasses` | `node.heritageClauses.getText()` | `checker.getDeclaredTypeOfSymbol(symbol).getBaseTypes()` |
| `extractCalls` | `buildName(node.expression)` | `checker.getFullyQualifiedName(symbol)` |
| `getScopeChain` | Line-number based scope map | `checker.getSymbolAtLocation()` parent chain |

**Implementation Pattern:**
```typescript
// OLD (Text-based) - loses semantic info
const extendsType = node.heritageClauses?.[0]?.types?.[0]?.expression?.getText();

// NEW (Semantic) - resolves actual types
const symbol = checker.getSymbolAtLocation(node.name);
const instanceType = checker.getDeclaredTypeOfSymbol(symbol);
const baseTypes = instanceType.getBaseTypes() || [];
const extendsTypes = baseTypes.map(t => checker.typeToString(t));
```

### Decision 6: Delete serializeNodeForCFG (from discussions.md)

**What:** DELETE the `serializeNodeForCFG` function from `core_language.js` entirely

**Why:**
- This function is a "Recursion Bomb" - walks entire AST and builds 5000-level deep JSON
- Causes 512MB crash on large files when `JSON.stringify()` runs
- Legacy code from before structured extraction tables existed
- Python no longer needs raw AST tree - it receives flat extraction tables

**Risk Mitigation:**
- Verify `batch_templates.js` sets `ast: null` (line 440)
- Ensure no other code paths call `serializeNodeForCFG`

### Decision 7: CFG Optimization - Skip Non-Executable Code (from discussions.md)

**What:** Modify CFG traversal to skip Interfaces, Types, Imports, and flatten JSX

**Why:**
- CFG only cares about *executable* code (functions, control flow)
- Current code visits every node including `InterfaceDeclaration`, `TypeAliasDeclaration`
- Wastes ~40% memory on TypeScript projects
- JSX creates thousands of useless CFG blocks for deeply nested HTML

**Optimizations:**
1. **Skip non-executable nodes:** InterfaceDeclaration, TypeAliasDeclaration, ImportDeclaration, ModuleDeclaration
2. **Flatten JSX:** Only record root of JSX tree, not every child element
3. **Depth limit:** Keep existing `depth > 500` guard

**JSX Optimization Pattern:**
```typescript
} else if (kind.startsWith("Jsx")) {
   // Only add CFG statement for ROOT of JSX tree
   const parentKind = node.parent ? ts.SyntaxKind[node.parent.kind] : "";
   if (!parentKind.startsWith("Jsx")) {
       addStatementToBlock(currentId, "jsx_root", line + 1, "<JSX>");
   }
   // Continue traversing to find embedded functions/expressions
   ...
}
```

### Decision 8: Delete Python Zombie Methods (from discussions.md)

**What:** Delete duplicate extraction logic from `javascript.py`

**Why:**
- Python layer has 600+ lines of "fallback" extraction that duplicates JS logic
- Creates "Double Vision" - two extraction engines fighting each other
- If JS extraction is missing data, fix JS, don't add Python workarounds

**Methods to DELETE from `javascript.py`:**
- `_extract_sql_from_function_calls()` - ~100 lines
- `_extract_jwt_from_function_calls()` - ~80 lines
- `_extract_routes_from_ast()` - ~200 lines
- Any `if not extracted_data: ... traverse AST` fallback blocks

**New Pattern:**
```python
def extract(self, file_info, content, tree):
    if isinstance(tree, dict) and "extracted_data" in tree:
        data = tree["extracted_data"]
        result["sql_queries"] = data.get("sql_queries", [])  # Trust JS!
        result["routes"] = data.get("routes", [])            # Trust JS!
        # NO FALLBACK. If data missing, bug is in JS.
    return result
```

### Decision 9: Keep javascript_resolvers.py (Linker Layer)

**What:** Keep `javascript_resolvers.py` unchanged - it's the cross-file "linker"

**Why:**
- This file runs AFTER extraction, uses SQL to connect dots across files
- `resolve_cross_file_parameters()` - maps `arg0` to actual param names using `symbols` table
- `resolve_router_mount_hierarchy()` - reconstructs Express.js route trees
- This is correct architecture: Frontend (JS) -> IR (SQLite) -> Backend (Python Resolvers)

**Rule:** If `javascript_resolvers.py` fails, fix the JS extraction that feeds it, not the resolver.

### Decision 10: Directory Structure for TypeScript Migration

**What:** New `src/` directory for TypeScript, `dist/` for compiled output

**Structure:**
```
theauditor/ast_extractors/javascript/
├── package.json          # Build scripts
├── tsconfig.json         # TypeScript config
├── src/
│   ├── main.ts           # Entry point (from batch_templates.js)
│   ├── schema.ts         # Zod validation schemas
│   ├── extractors/
│   │   ├── core_language.ts
│   │   ├── data_flow.ts
│   │   ├── module_framework.ts
│   │   ├── security_extractors.ts
│   │   ├── framework_extractors.ts
│   │   ├── sequelize_extractors.ts
│   │   ├── bullmq_extractors.ts
│   │   ├── angular_extractors.ts
│   │   └── cfg_extractor.ts
│   └── types/            # Shared TypeScript interfaces
│       └── index.ts
├── dist/
│   └── extractor.js      # Compiled bundle (gitignored)
└── [OLD] *.js            # Legacy files (removed after migration)
```

**Why this structure:**
- `src/` clearly separates source from output
- `extractors/` groups related modules
- `types/` provides shared interfaces
- `dist/` is gitignored - built on setup/CI

### Decision 11: Single ESNext Bundle (Consolidate from Dual)

**What:** Produce single ESNext bundle, drop CommonJS variant

**Why:**
- TheAuditor requires Node.js 18+ which fully supports ESM
- Dual bundles add maintenance burden
- esbuild `--format=esm` is simpler

**Impact:**
- Remove `// === COMMONJS_BATCH ===` section from migration
- `js_helper_templates.py` `module_type` parameter becomes obsolete (always ESM)
- Python orchestrator simplified to single code path

## Resolved Decisions

These were "Open Questions" - now resolved:

### 1. vitest for TypeScript tests?
**Decision:** NO for initial migration. Add in follow-up proposal.
**Rationale:** Keep scope minimal. Python integration tests sufficient for correctness verification. TypeScript compile-time checks provide additional safety.

### 2. Commit dist/ or build on install?
**Decision:** Build on install via `aud setup-ai` and CI.
**Rationale:**
- Cleaner git history (no binary blobs)
- Forces build step awareness
- CI always runs fresh build

### 3. Vue compiler static imports?
**Decision:** Keep dynamic imports with try/catch.
**Rationale:**
- Vue support is optional - not all projects use Vue
- Dynamic loading is correct pattern for optional dependencies
- TypeScript conversion maintains same pattern with proper typing

## Function Export Contract

Complete list of functions that MUST be exported from each extractor module:

### core_language.ts (5 exports) - UPDATED per discussions.md
| Function | Line | Return Type | Notes |
|----------|------|-------------|-------|
| ~~`serializeNodeForCFG`~~ | ~~1~~ | ~~`SerializedNode \| null`~~ | **DELETED - Recursion bomb** |
| `extractFunctions` | 74 | `{ functions, func_params, func_decorators, func_decorator_args, func_param_decorators }` | |
| `extractClasses` | 381 | `{ classes, class_decorators, class_decorator_args }` | **REWRITE with TypeChecker** - now includes `extends[]`, `implements[]`, `properties[]`, `methods[]` |
| `extractClassProperties` | 618 | `ClassProperty[]` | |
| `buildScopeMap` | 711 | `Map<number, string>` | Consider replacing with `getScopeChain()` using TypeChecker |
| `countNodes` | 873 | `number` | |

### data_flow.ts (6 exports) - UPDATED per discussions.md
| Function | Line | Return Type | Notes |
|----------|------|-------------|-------|
| `extractCalls` | 3 | `CallSymbol[]` | **REWRITE with TypeChecker** - use `checker.getFullyQualifiedName()`, add `defined_in` field |
| `extractAssignments` | 226 | `{ assignments, assignment_source_vars }` | |
| `extractFunctionCallArgs` | 454 | `FunctionCallArg[]` | |
| `extractReturns` | 649 | `{ returns, return_source_vars }` | |
| `extractObjectLiterals` | 838 | `ObjectLiteral[]` | |
| `extractVariableUsage` | 1008 | `VariableUsage[]` | |

### module_framework.ts (5 exports)
| Function | Line | Return Type |
|----------|------|-------------|
| `extractImports` | 1 | `{ imports, import_specifiers }` |
| `extractEnvVarUsage` | 203 | `EnvVarUsage[]` |
| `extractORMRelationships` | 382 | `ORMRelationship[]` |
| `extractImportStyles` | 512 | `{ import_styles, import_style_names }` |
| `extractRefs` | 568 | `Record<string, string>` |

### security_extractors.ts (8 exports)
| Function | Line | Return Type |
|----------|------|-------------|
| `extractORMQueries` | 1 | `ORMQuery[]` |
| `extractAPIEndpoints` | 52 | `{ endpoints, middlewareChains }` |
| `extractValidationFrameworkUsage` | 139 | `ValidationCall[]` |
| `extractSchemaDefinitions` | 203 | `SchemaDefinition[]` |
| `extractSQLQueries` | 604 | `SQLQuery[]` |
| `extractCDKConstructs` | 678 | `{ cdk_constructs, cdk_construct_properties }` |
| `extractFrontendApiCalls` | 945 | `FrontendApiCall[]` |

### framework_extractors.ts (10 exports)
| Function | Line | Return Type |
|----------|------|-------------|
| `extractReactComponents` | 1 | `{ react_components, react_component_hooks }` |
| `extractReactHooks` | 114 | `{ react_hooks, react_hook_dependencies }` |
| `extractVueComponents` | 443 | `{ vue_components, vue_component_props, vue_component_emits, vue_component_setup_returns, primaryName }` |
| `extractVueHooks` | 521 | `VueHook[]` |
| `extractVueProvideInject` | 577 | `VueProvideInject[]` |
| `extractVueDirectives` | 614 | `VueDirective[]` |
| `extractApolloResolvers` | 681 | `{ graphql_resolvers, graphql_resolver_params }` |
| `extractNestJSResolvers` | 748 | `{ graphql_resolvers, graphql_resolver_params }` |
| `extractTypeGraphQLResolvers` | 858 | `{ graphql_resolvers, graphql_resolver_params }` |

### sequelize_extractors.ts, bullmq_extractors.ts, angular_extractors.ts
See `batch_templates.js` for function lists (these files have 1-3 exports each).

### cfg_extractor.ts - UPDATED per discussions.md
| Function | Return Type | Notes |
|----------|-------------|-------|
| `extractCFG` | `{ cfg_blocks, cfg_edges, cfg_block_statements }` | **OPTIMIZE** - skip non-executable code, flatten JSX |

**CFG Optimizations Required:**
1. Skip `InterfaceDeclaration`, `TypeAliasDeclaration`, `ImportDeclaration`, `ModuleDeclaration`
2. Flatten JSX - only record root of JSX tree, not every child element
3. Keep `depth > 500` guard for safety

## Complete Zod Schema Definition

The following schema MUST be implemented in `src/schema.ts`. This mirrors the 50 database tables used by Node.js extraction:

```typescript
import { z } from "zod";

// === CORE EXTRACTION SCHEMAS ===

export const SymbolSchema = z.object({
  path: z.string(),
  name: z.string(),
  type: z.string(),
  line: z.number(),
  col: z.number(),
  jsx_mode: z.string().nullable(),
  extraction_pass: z.number().nullable(),
});

export const FunctionSchema = z.object({
  name: z.string(),
  line: z.number(),
  col: z.number().optional(),
  column: z.number().optional(),
  kind: z.string().optional(),
  type: z.literal("function"),
  type_annotation: z.string().optional(),
  is_any: z.boolean().optional(),
  is_unknown: z.boolean().optional(),
  is_generic: z.boolean().optional(),
  return_type: z.string().optional(),
  extends_type: z.string().optional(),
});

export const ClassSchema = z.object({
  name: z.string(),
  line: z.number(),
  col: z.number().optional(),
  column: z.number().optional(),
  type: z.literal("class"),
  kind: z.string().optional(),
  type_annotation: z.string().optional(),
  extends_type: z.string().nullable().optional(),
  has_type_params: z.boolean().optional(),
  type_params: z.string().optional(),
  // NEW: Semantic fields from TypeChecker (Decision 5)
  extends: z.array(z.string()).optional(),      // Resolved base types
  implements: z.array(z.string()).optional(),   // Interface contracts
  properties: z.array(z.object({
    name: z.string(),
    type: z.string(),
    inherited: z.boolean(),
  })).optional(),
  methods: z.array(z.object({
    name: z.string(),
    signature: z.string(),
    inherited: z.boolean(),
  })).optional(),
});

export const AssignmentSchema = z.object({
  file: z.string(),
  line: z.number(),
  target_var: z.string(),
  source_expr: z.string(),
  in_function: z.string(),
  property_path: z.string().nullable().optional(),
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

export const FunctionReturnSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  function_name: z.string(),
  return_expr: z.string(),
  has_jsx: z.boolean(),
  returns_component: z.boolean(),
  cleanup_operations: z.string().nullable().optional(),
  return_index: z.number().optional(),
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

export const FunctionCallArgSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  caller_function: z.string(),
  callee_function: z.string(),
  argument_index: z.number().nullable(),
  argument_expr: z.string().nullable(),
  param_name: z.string().nullable(),
  callee_file_path: z.string().nullable().optional(),
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

// === JUNCTION TABLE SCHEMAS ===

export const FuncParamSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  param_index: z.number(),
  param_name: z.string(),
  param_type: z.string().nullable(),
});

export const FuncDecoratorSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  decorator_index: z.number(),
  decorator_name: z.string(),
  decorator_line: z.number(),
});

export const FuncDecoratorArgSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  decorator_index: z.number(),
  arg_index: z.number(),
  arg_value: z.string(),
});

export const FuncParamDecoratorSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  param_index: z.number(),
  decorator_name: z.string(),
  decorator_args: z.string().nullable(),
});

export const ClassDecoratorSchema = z.object({
  file: z.string().optional(),
  class_line: z.number(),
  class_name: z.string(),
  decorator_index: z.number(),
  decorator_name: z.string(),
  decorator_line: z.number(),
});

export const ClassDecoratorArgSchema = z.object({
  file: z.string().optional(),
  class_line: z.number(),
  class_name: z.string(),
  decorator_index: z.number(),
  arg_index: z.number(),
  arg_value: z.string(),
});

export const ClassPropertySchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  class_name: z.string(),
  property_name: z.string(),
  property_type: z.string().nullable(),
  is_optional: z.boolean(),
  is_readonly: z.boolean(),
  access_modifier: z.string().nullable(),
  has_declare: z.boolean(),
  initializer: z.string().nullable(),
});

export const ImportSpecifierSchema = z.object({
  file: z.string(),
  import_line: z.number(),
  specifier_name: z.string(),
  original_name: z.string(),
  is_default: z.number(), // 0 or 1
  is_namespace: z.number(),
  is_named: z.number(),
});

export const AssignmentSourceVarSchema = z.object({
  file: z.string(),
  line: z.number(),
  target_var: z.string(),
  source_var: z.string(),
  var_index: z.number(),
});

export const ReturnSourceVarSchema = z.object({
  file: z.string(),
  line: z.number(),
  function_name: z.string(),
  source_var: z.string(),
  var_index: z.number(),
});

// === FRAMEWORK SCHEMAS ===

export const ReactComponentSchema = z.object({
  file: z.string().optional(),
  name: z.string(),
  type: z.enum(["function", "class"]),
  start_line: z.number(),
  end_line: z.number(),
  has_jsx: z.boolean(),
  props_type: z.string().nullable(),
});

export const ReactHookSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  component_name: z.string(),
  hook_name: z.string(),
  dependency_array: z.string().nullable().optional(),
  callback_body: z.string().nullable().optional(),
  has_cleanup: z.boolean().optional(),
  cleanup_type: z.string().nullable().optional(),
  is_custom: z.boolean().optional(),
  argument_count: z.number().optional(),
});

export const VueComponentSchema = z.object({
  file: z.string().optional(),
  name: z.string(),
  type: z.enum(["script-setup", "composition-api", "options-api"]),
  start_line: z.number(),
  end_line: z.number(),
  has_template: z.boolean(),
  has_style: z.boolean(),
  composition_api_used: z.boolean(),
});

export const VueComponentPropSchema = z.object({
  file: z.string().optional(),
  component_name: z.string(),
  prop_name: z.string(),
  prop_type: z.string().nullable(),
  is_required: z.number(), // 0 or 1
  default_value: z.string().nullable(),
});

export const VueComponentEmitSchema = z.object({
  file: z.string().optional(),
  component_name: z.string(),
  emit_name: z.string(),
  payload_type: z.string().nullable(),
});

export const VueComponentSetupReturnSchema = z.object({
  file: z.string().optional(),
  component_name: z.string(),
  return_name: z.string(),
  return_type: z.string().nullable(),
});

export const AngularComponentSchema = z.object({
  file: z.string(),
  line: z.number(),
  component_name: z.string(),
  selector: z.string().nullable(),
  template_path: z.string().nullable(),
  has_lifecycle_hooks: z.boolean(),
});

export const SequelizeModelSchema = z.object({
  file: z.string(),
  line: z.number(),
  model_name: z.string(),
  table_name: z.string().nullable(),
  extends_model: z.string().nullable(),
});

export const SequelizeModelFieldSchema = z.object({
  file: z.string(),
  model_name: z.string(),
  field_name: z.string(),
  data_type: z.string(),
  is_primary_key: z.boolean(),
  is_nullable: z.boolean(),
  is_unique: z.boolean(),
  default_value: z.string().nullable(),
});

export const BullMQQueueSchema = z.object({
  file: z.string(),
  line: z.number(),
  queue_name: z.string(),
  redis_config: z.string().nullable(),
});

export const BullMQWorkerSchema = z.object({
  file: z.string(),
  line: z.number(),
  queue_name: z.string(),
  worker_function: z.string().nullable(),
  processor_path: z.string().nullable(),
});

// === NEW: Call Symbol Schema with Semantic Data (Decision 5) ===

export const CallSymbolSchema = z.object({
  line: z.number(),
  column: z.number().optional(),
  name: z.string(),               // Resolved: "User.findAll" or "sequelize.Model.findAll"
  original_text: z.string().optional(),  // Raw: "db.users.findAll"
  defined_in: z.string().nullable().optional(),  // File path where function is defined
  arguments: z.array(z.string()).optional(),
  caller_function: z.string().optional(),
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

// === EXTRACTION RECEIPT (TOP-LEVEL OUTPUT) ===

export const ExtractedDataSchema = z.object({
  // Core
  symbols: z.array(SymbolSchema).optional(),
  functions: z.array(FunctionSchema).optional(),
  classes: z.array(ClassSchema).optional(),
  calls: z.array(CallSymbolSchema).optional(),  // NEW: Semantic call data
  assignments: z.array(AssignmentSchema).optional(),
  returns: z.array(FunctionReturnSchema).optional(),
  function_call_args: z.array(FunctionCallArgSchema).optional(),
  object_literals: z.array(z.any()).optional(),
  variable_usage: z.array(z.any()).optional(),

  // Junction tables
  func_params: z.array(FuncParamSchema).optional(),
  func_decorators: z.array(FuncDecoratorSchema).optional(),
  func_decorator_args: z.array(FuncDecoratorArgSchema).optional(),
  func_param_decorators: z.array(FuncParamDecoratorSchema).optional(),
  class_decorators: z.array(ClassDecoratorSchema).optional(),
  class_decorator_args: z.array(ClassDecoratorArgSchema).optional(),
  class_properties: z.array(ClassPropertySchema).optional(),
  imports: z.array(z.any()).optional(),
  import_specifiers: z.array(ImportSpecifierSchema).optional(),
  assignment_source_vars: z.array(AssignmentSourceVarSchema).optional(),
  return_source_vars: z.array(ReturnSourceVarSchema).optional(),

  // React
  react_components: z.array(ReactComponentSchema).optional(),
  react_component_hooks: z.array(z.any()).optional(),
  react_hooks: z.array(ReactHookSchema).optional(),
  react_hook_dependencies: z.array(z.any()).optional(),

  // Vue
  vue_components: z.array(VueComponentSchema).optional(),
  vue_component_props: z.array(VueComponentPropSchema).optional(),
  vue_component_emits: z.array(VueComponentEmitSchema).optional(),
  vue_component_setup_returns: z.array(VueComponentSetupReturnSchema).optional(),
  vue_hooks: z.array(z.any()).optional(),
  vue_directives: z.array(z.any()).optional(),
  vue_provide_inject: z.array(z.any()).optional(),

  // Angular
  angular_components: z.array(AngularComponentSchema).optional(),
  angular_modules: z.array(z.any()).optional(),
  angular_services: z.array(z.any()).optional(),
  angular_guards: z.array(z.any()).optional(),
  angular_component_styles: z.array(z.any()).optional(),
  angular_module_declarations: z.array(z.any()).optional(),
  angular_module_imports: z.array(z.any()).optional(),
  angular_module_providers: z.array(z.any()).optional(),
  angular_module_exports: z.array(z.any()).optional(),

  // ORM
  sequelize_models: z.array(SequelizeModelSchema).optional(),
  sequelize_associations: z.array(z.any()).optional(),
  sequelize_model_fields: z.array(SequelizeModelFieldSchema).optional(),
  orm_relationships: z.array(z.any()).optional(),
  orm_queries: z.array(z.any()).optional(),

  // Jobs
  bullmq_queues: z.array(BullMQQueueSchema).optional(),
  bullmq_workers: z.array(BullMQWorkerSchema).optional(),

  // Security
  api_endpoints: z.array(z.any()).optional(),
  middleware_chains: z.array(z.any()).optional(),
  validation_calls: z.array(z.any()).optional(),
  schema_definitions: z.array(z.any()).optional(),
  sql_queries: z.array(z.any()).optional(),
  cdk_constructs: z.array(z.any()).optional(),
  cdk_construct_properties: z.array(z.any()).optional(),
  frontend_api_calls: z.array(z.any()).optional(),

  // GraphQL
  graphql_resolvers: z.array(z.any()).optional(),
  graphql_resolver_params: z.array(z.any()).optional(),

  // Misc
  env_vars: z.array(z.any()).optional(),
  import_styles: z.array(z.any()).optional(),
  import_style_names: z.array(z.any()).optional(),
  refs: z.record(z.string()).optional(),
  cfg_blocks: z.array(z.any()).optional(),
  cfg_edges: z.array(z.any()).optional(),
  cfg_block_statements: z.array(z.any()).optional(),
});

export const FileResultSchema = z.object({
  success: z.boolean(),
  extracted_data: ExtractedDataSchema.optional(),
  error: z.string().optional(),
});

export const ExtractionReceiptSchema = z.record(z.string(), FileResultSchema);
```

## Dependency Versions

Pinned versions for reproducibility:

```json
{
  "dependencies": {
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "esbuild": "^0.19.11",
    "@types/node": "^20.10.0"
  }
}
```

## Risks / Trade-offs

### Risk 1: Build Step Complexity
**Risk:** Developers must run `npm run build` after modifying extractors
**Mitigation:**
- Add check in `js_helper_templates.py` that fails fast if bundle missing
- CI runs build before tests
- `aud setup-ai` includes build step

### Risk 2: Schema Drift
**Risk:** Zod schema diverges from Python expectations over time
**Mitigation:**
- Contract tests compare schema fields against Python storage handler keys
- CI test: extract sample files, validate output matches expected structure

### Risk 3: Migration Period Breakage
**Risk:** During migration, some extractors converted, others not
**Mitigation:**
- Phased approach: one extractor at a time
- Each phase: convert, test, commit
- Feature branch until complete

### Risk 4: Windows Path Issues
**Risk:** esbuild/TypeScript may have issues with Windows paths
**Mitigation:**
- Use forward slashes in all configs (works in Node.js on Windows)
- Test on Windows before merging

### Risk 5: Semantic Upgrade Name Changes (from discussions.md)
**Risk:** `checker.getFullyQualifiedName()` may return different names than text parsing
- Example: `User.init` might become `sequelize.Model.init`
**Mitigation:**
- Run extraction on test fixtures before/after, compare output
- Update downstream extractors (`sequelize_extractors.js`) if patterns change
- Keep `original_text` field for debugging

### Risk 6: Python Zombie Deletion Exposes Gaps (from discussions.md)
**Risk:** Deleting Python fallback methods may reveal missing JS extraction
**Mitigation:**
- This is intentional - forces us to fix JS extraction
- If gap found, add to JS extraction, NOT Python
- Test full pipeline after deletion

### Risk 7: Recursion Bomb Removal (from discussions.md)
**Risk:** Code that depends on `serializeNodeForCFG` will break
**Mitigation:**
- Verify `batch_templates.js` sets `ast: null` before deletion
- Search codebase for any calls to `serializeNodeForCFG`
- If called anywhere, refactor callers first

## Migration Plan

### Phase 1: Infrastructure (LOW RISK)
1. Create `package.json` with dependencies: `zod@^3.22.4`, `typescript@^5.3.3`, `esbuild@^0.19.11`
2. Create `tsconfig.json` with strict mode
3. Create empty `src/schema.ts` and `src/main.ts`
4. Add build script to package.json
5. Update `.gitignore` to exclude `dist/`

### Phase 2: Schema Definition (MEDIUM RISK)
1. Define Zod schemas mirroring current JSON output (see schema above)
2. Create contract test comparing schema to Python storage handler
3. Verify schema matches all 50 extraction data types

### Phase 3: Extractor Conversion WITH Semantic Upgrades (HIGH RISK)
Convert in dependency order with implementation fixes from discussions.md:

1. `core_language.js` -> `src/extractors/core_language.ts` (foundation)
   - **DELETE `serializeNodeForCFG`** - recursion bomb
   - **REWRITE `extractClasses`** to use `checker.getDeclaredTypeOfSymbol()` for inheritance
   - Add `extends[]`, `implements[]`, `properties[]`, `methods[]` to output

2. `data_flow.js` -> `src/extractors/data_flow.ts`
   - **REWRITE `extractCalls`** to use `checker.getSymbolAtLocation()` and `checker.getFullyQualifiedName()`
   - Add `defined_in` field for resolved symbol file paths
   - Keep `original_text` for debugging

3. `module_framework.js` -> `src/extractors/module_framework.ts`

4. `security_extractors.js` -> `src/extractors/security_extractors.ts`

5. `framework_extractors.js` -> `src/extractors/framework_extractors.ts`

6. `sequelize_extractors.js` -> `src/extractors/sequelize_extractors.ts`
   - Update string matching if semantic names changed (e.g., `sequelize.Model.init` vs `User.init`)

7. `bullmq_extractors.js` -> `src/extractors/bullmq_extractors.ts`

8. `angular_extractors.js` -> `src/extractors/angular_extractors.ts`

9. `cfg_extractor.js` -> `src/extractors/cfg_extractor.ts`
   - **OPTIMIZE `visit`** - skip InterfaceDeclaration, TypeAliasDeclaration, ImportDeclaration, ModuleDeclaration
   - **OPTIMIZE JSX** - only record root of JSX tree, not every child element

Each conversion:
- Add `export` to each function
- Add TypeScript types to parameters and return values
- Add `import` statements for dependencies
- Apply semantic upgrades where noted
- Build and test before committing

### Phase 4: Entry Point Migration (HIGH RISK)
1. Convert `batch_templates.js` to `src/main.ts`
2. Replace global function calls with imports
3. Add Zod validation before JSON output
4. Build and verify output matches previous format

### Phase 5: Orchestrator Update (MEDIUM RISK)
1. Update `js_helper_templates.py` to read `dist/extractor.js`
2. Remove `_JS_CACHE`, `_load_javascript_modules()`
3. Add FileNotFoundError if bundle missing
4. Test full `aud full --index` pipeline

### Phase 5.3: Python Zombie Cleanup (MEDIUM RISK) - from discussions.md
Delete duplicate extraction logic from `javascript.py`:

1. **DELETE** `_extract_sql_from_function_calls()` method (~100 lines)
2. **DELETE** `_extract_jwt_from_function_calls()` method (~80 lines)
3. **DELETE** `_extract_routes_from_ast()` method (~200 lines)
4. **DELETE** any `if not extracted_data: ... traverse AST` fallback blocks
5. **SIMPLIFY** `extract()` method to trust `extracted_data`:
   ```python
   def extract(self, file_info, content, tree):
       if isinstance(tree, dict) and "extracted_data" in tree:
           data = tree["extracted_data"]
           result["sql_queries"] = data.get("sql_queries", [])  # Trust JS!
           result["routes"] = data.get("routes", [])            # Trust JS!
           # NO FALLBACK. If data missing, bug is in JS.
       return result
   ```
6. Test full pipeline - if anything missing, fix JS extraction, NOT Python

**NOTE:** Keep `javascript_resolvers.py` unchanged - it's the cross-file linker layer (correct architecture).

### Phase 6: Cleanup (LOW RISK)
1. Delete old `.js` files
2. Update ESLint config (remove legacy ignores)
3. Update documentation
4. Update CI to build before tests

### Rollback Plan
At any phase:
1. Revert to previous commit
2. Delete `dist/` directory
3. System uses old concatenation approach

Full rollback:
- `git checkout HEAD~N -- theauditor/ast_extractors/javascript/`
- Delete `src/`, `dist/`, `package.json`, `tsconfig.json`
