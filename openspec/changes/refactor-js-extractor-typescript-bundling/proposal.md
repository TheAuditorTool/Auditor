## Why

The JavaScript/TypeScript AST extraction system uses a **fragile string concatenation architecture** where 9 separate `.js` files are concatenated at runtime by Python into a single script. This architecture has:

1. **ZERO compile-time safety** - Functions float in global scope, no imports/exports, typos caught only at runtime
2. **Debug nightmare** - Stack traces point to temp file line numbers, not source files
3. **False ESLint warnings** - 44+ "unused variable" warnings because ESLint analyzes files in isolation
4. **No IDE support** - Cannot ctrl+click to definition across extractor files
5. **Silent data corruption risk** - If function signature changes, Python ingestion may receive malformed data

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
| `theauditor/ast_extractors/js_helper_templates.py` | SIMPLIFY | MEDIUM - Python orchestrator |
| `theauditor/ast_extractors/javascript/package.json` | NEW | LOW - Build config |
| `theauditor/ast_extractors/javascript/tsconfig.json` | NEW | LOW - TS config |
| `theauditor/ast_extractors/javascript/src/schema.ts` | NEW | MEDIUM - Output contract |

### Risk Assessment
- **HIGH RISK**: Extraction output format must remain 100% compatible with Python ingestion layer (`javascript.py`)
- **MEDIUM RISK**: Build step adds complexity to setup/CI
- **LOW RISK**: TypeScript types are erased at runtime, no performance impact

### Breaking Changes
- **NONE for consumers** - JSON output shape unchanged
- **BREAKING for contributors** - Must run `npm run build` after modifying extractors

### Migration Path
1. Phase 1: Add TypeScript infrastructure (tsconfig, package.json, schema)
2. Phase 2: Convert extractors one-by-one (core_language first, then data_flow, etc.)
3. Phase 3: Update batch_templates.js to src/main.ts with imports
4. Phase 4: Update Python orchestrator to use compiled bundle
5. Phase 5: Remove old .js files, update CI
