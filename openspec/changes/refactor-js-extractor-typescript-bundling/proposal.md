## Why

The JavaScript/TypeScript AST extraction system has **TWO critical problems**:

### Problem 1: Fragile String Concatenation Architecture
9 separate `.js` files are concatenated at runtime by Python into a single script. This architecture has:

1. **ZERO compile-time safety** - Functions float in global scope, no imports/exports, typos caught only at runtime
2. **Debug nightmare** - Stack traces point to temp file line numbers, not source files
3. **False ESLint warnings** - 44+ "unused variable" warnings because ESLint analyzes files in isolation
4. **No IDE support** - Cannot ctrl+click to definition across extractor files
5. **Silent data corruption risk** - If function signature changes, Python ingestion may receive malformed data

### Problem 2: Dumb Extraction Logic (Semantic Blindness)
The current extractors use **text-based parsing** instead of TypeScript's semantic API:

1. **No inheritance resolution** - `extractClasses` doesn't resolve `extends BaseController` to actual parent class
2. **Anonymous caller bug** - `extractCalls` uses text reconstruction, can't resolve `db.User.findAll()` to actual model
3. **Recursion bomb** - `serializeNodeForCFG` builds 5000-level deep JSON, causing 512MB crash on large files
4. **CFG bloat** - Visits every node including Interfaces/Types, wastes 40% memory on TypeScript projects
5. **JSX stack overflow** - Creates thousands of CFG blocks for deeply nested JSX (`<div><div><div>...`)
6. **Python zombies** - `javascript.py` has 600+ lines of duplicate extraction logic that fights with JS layer

**Current Flow (Fragile):**
```
js_helper_templates.py -> Reads 9 JS files -> String concat "\n\n" -> temp.js -> Node subprocess -> JSON (unknown shape)
```

**Proposed Flow (Sane):**
```
TypeScript source + Zod schema -> Build step (esbuild) -> dist/extractor.js (sealed envelope)
Runtime: js_helper_templates.py -> Execs dist/extractor.js -> JSON (guaranteed shape via Zod)
```

## What Changes

### Node.js Extractors (MAJOR)
- **CONVERT** 9 JS files to TypeScript modules with explicit `export` statements
- **ADD** Zod schema (`src/schema.ts`) defining extraction output contract
- **ADD** Build pipeline (`esbuild`) producing single `dist/extractor.js` bundle
- **MOVE** `batch_templates.js` logic to `src/main.ts` as module entry point
- **ADD** Runtime validation: Zod validates output before Python receives it

### Semantic Extraction Upgrades (MAJOR - from discussions.md)
- **DELETE** `serializeNodeForCFG` function entirely (legacy recursion bomb)
- **REWRITE** `extractClasses` to use `checker.getDeclaredTypeOfSymbol()` for inheritance resolution
- **REWRITE** `extractCalls` to use `checker.getSymbolAtLocation()` for symbol resolution
- **OPTIMIZE** `extractCFG` to skip non-executable code (InterfaceDeclaration, TypeAliasDeclaration, ImportDeclaration)
- **OPTIMIZE** JSX handling to flatten deeply nested JSX into single CFG statement

### Python Cleanup (MEDIUM - from discussions.md)
- **DELETE** `_extract_sql_from_function_calls()` from `javascript.py` (zombie method)
- **DELETE** `_extract_jwt_from_function_calls()` from `javascript.py` (zombie method)
- **DELETE** `_extract_routes_from_ast()` from `javascript.py` (zombie method)
- **SIMPLIFY** `extract()` method to trust `extracted_data` without fallbacks

### Python Orchestrator (MINOR)
- **SIMPLIFY** `js_helper_templates.py` to read pre-compiled bundle instead of concatenating strings
- **REMOVE** `_JS_CACHE` dictionary and `_load_javascript_modules()` function
- **ADD** FileNotFoundError if `dist/extractor.js` missing (prompts `npm run build`)

### Build System (NEW)
- **ADD** `theauditor/ast_extractors/javascript/package.json` with esbuild build script
- **ADD** `theauditor/ast_extractors/javascript/tsconfig.json` for TypeScript compilation
- **ADD** CI step to build extractors before tests run

### Dependencies
- **ADD** `zod` (npm) for schema validation inside Node.js extractor
- **ADD** `esbuild` (npm dev dep) for bundling
- **ADD** `typescript` (npm dev dep) for type checking

## Impact

### Affected Specs
- `specs/indexer/spec.md` - Node extractor architecture changes

### Affected Code
| File | Change Type | Risk |
|------|-------------|------|
| `theauditor/ast_extractors/javascript/*.js` (9 files) | CONVERT to .ts | HIGH - Core extraction logic |
| `theauditor/ast_extractors/javascript/batch_templates.js` | REPLACE with src/main.ts | HIGH - Entry point |
| `theauditor/ast_extractors/javascript/core_language.js` | DELETE serializeNodeForCFG, REWRITE extractClasses | HIGH - Recursion bomb fix |
| `theauditor/ast_extractors/javascript/data_flow.js` | REWRITE extractCalls with TypeChecker | HIGH - Symbol resolution |
| `theauditor/ast_extractors/javascript/cfg_extractor.js` | OPTIMIZE visit + JSX handling | MEDIUM - Performance fix |
| `theauditor/indexer/extractors/javascript.py` | DELETE zombie methods | MEDIUM - Remove 600 lines |
| `theauditor/ast_extractors/js_helper_templates.py` | SIMPLIFY | MEDIUM - Python orchestrator |
| `theauditor/ast_extractors/javascript/package.json` | NEW | LOW - Build config |
| `theauditor/ast_extractors/javascript/tsconfig.json` | NEW | LOW - TS config |
| `theauditor/ast_extractors/javascript/src/schema.ts` | NEW | MEDIUM - Output contract |

### Risk Assessment
- **HIGH RISK**: Extraction output format must remain 100% compatible with Python ingestion layer (`javascript.py`)
- **HIGH RISK**: Semantic upgrades may change function call names (e.g., `User.init` -> `sequelize.Model.init`)
- **MEDIUM RISK**: Build step adds complexity to setup/CI
- **MEDIUM RISK**: Deleting Python zombie methods may expose gaps in JS extraction
- **LOW RISK**: TypeScript types are erased at runtime, no performance impact

### Breaking Changes
- **NONE for consumers** - JSON output shape unchanged (with richer semantic data)
- **BREAKING for contributors** - Must run `npm run build` after modifying extractors
- **OUTPUT CHANGE** - `extractClasses` will include `extends`, `implements`, `properties`, `methods` arrays
- **OUTPUT CHANGE** - `extractCalls` will include `defined_in` file path for resolved symbols

### Migration Path
1. Phase 1: Add TypeScript infrastructure (tsconfig, package.json, schema)
2. Phase 2: Convert extractors with semantic upgrades (core_language with TypeChecker, data_flow with symbol resolution)
3. Phase 3: Optimize CFG extractor (skip non-executable, flatten JSX)
4. Phase 4: Update batch_templates.js to src/main.ts with imports
5. Phase 5: Update Python orchestrator + DELETE zombie methods from javascript.py
6. Phase 6: Remove old .js files, update CI
