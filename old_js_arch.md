# JavaScript Extractor Architecture - Handoff Document

**Date:** 2025-11-28
**Status:** Technical Debt - Works But Fragile

---

## What It Is

TheAuditor's JavaScript/TypeScript AST extraction uses a **string concatenation architecture** where 9 separate `.js` files are concatenated into a single script at runtime.

## How It Works

```
Python Orchestrator (js_helper_templates.py)
    │
    ├── Reads 9 JS files as raw text strings
    │   ├── core_language.js      (functions, classes, scope)
    │   ├── data_flow.js          (assignments, calls, returns)
    │   ├── module_framework.js   (imports, env vars, ORM)
    │   ├── security_extractors.js
    │   ├── framework_extractors.js
    │   ├── sequelize_extractors.js
    │   ├── bullmq_extractors.js
    │   ├── angular_extractors.js
    │   └── cfg_extractor.js
    │
    ├── Concatenates them with "\n\n"
    │
    ├── Appends batch_templates.js (the main() function)
    │
    ├── Writes to temp file
    │
    └── Executes via Node.js subprocess
```

The `batch_templates.js` contains a `main()` function that **directly calls functions by name** from the concatenated fragments:

```javascript
// These functions must exist in the concatenated output
const scopeMap = buildScopeMap(sourceFile, ts);
const importData = extractImports(sourceFile, ts, filePath);
const funcData = extractFunctions(sourceFile, checker, ts);
// ... 30+ more function calls
```

## Why This Is Fragile

| Risk | Impact | Likelihood |
|------|--------|------------|
| Rename a function | Runtime crash, cryptic "undefined is not a function" | Medium |
| Change function signature | Silent data corruption or runtime crash | Medium |
| Typo in function name | Only caught at runtime | High |
| Missing function | Only caught at runtime | Medium |
| Concatenation order change | Potential variable shadowing | Low |

### No Compile-Time Safety

- **No TypeScript** - Everything is plain JS
- **No imports/exports** - Functions float in global scope
- **No type checking** - Parameter mismatches caught at runtime only
- **No IDE support** - Can't ctrl+click to definition across files
- **No ESLint accuracy** - Reports false "unused" warnings because it analyzes files in isolation

### Debug Nightmare

Stack traces point to line numbers in the **temp file**, not the source files. You have to manually calculate which fragment the error came from.

## Current State

**It works** because:
1. Nobody has renamed functions
2. The concatenation order is hardcoded and hasn't changed
3. Manual testing catches obvious breaks

**ESLint reports 44 "unused variable" warnings** - these are FALSE POSITIVES because ESLint doesn't know about the concatenation. The functions ARE used, just in `batch_templates.js` after assembly.

## The Contract (Implicit)

`batch_templates.js` expects these functions to exist:

```
From core_language.js:
  - extractFunctions()
  - extractClasses()
  - extractClassProperties()
  - buildScopeMap()
  - countNodes()

From data_flow.js:
  - extractCalls()
  - extractAssignments()
  - extractFunctionCallArgs()
  - extractReturns()
  - extractObjectLiterals()
  - extractVariableUsage()

From module_framework.js:
  - extractImports()
  - extractEnvVarUsage()
  - extractORMRelationships()
  - extractImportStyles()
  - extractRefs()

From security_extractors.js:
  - extractORMQueries()
  - extractAPIEndpoints()
  - extractValidationFrameworkUsage()
  - extractSchemaDefinitions()
  - extractSQLQueries()
  - extractCDKConstructs()
  - extractFrontendApiCalls()

From framework_extractors.js:
  - extractReactComponents()
  - extractReactHooks()
  - extractVueComponents()
  - extractVueHooks()
  - extractVueDirectives()
  - extractVueProvideInject()

From sequelize_extractors.js:
  - extractSequelizeModels()

From bullmq_extractors.js:
  - extractBullMQJobs()

From angular_extractors.js:
  - extractAngularComponents()

From cfg_extractor.js:
  - extractCFG()
```

## Options to Fix

### Option 1: Do Nothing (Current)
- Pros: Works, no effort
- Cons: Tech debt accumulates, debugging is painful

### Option 2: Add ESLint Ignores
- Pros: Silences false warnings
- Cons: Masks real issues, doesn't fix architecture

### Option 3: Add Contract Verification
```javascript
// Add to batch_templates.js before main()
const REQUIRED_FUNCTIONS = [
  'extractFunctions', 'extractClasses', 'buildScopeMap', ...
];
for (const fn of REQUIRED_FUNCTIONS) {
  if (typeof global[fn] !== 'function') {
    throw new Error(`Missing required function: ${fn}`);
  }
}
```
- Pros: Fails fast with clear error
- Cons: Still no compile-time safety

### Option 4: Proper Module Bundling
Convert to ES modules with proper imports, use esbuild/rollup to bundle:
```javascript
// core_language.js
export function extractFunctions(...) { }

// batch_templates.js
import { extractFunctions } from './core_language.js';
```
Then bundle: `esbuild batch_templates.js --bundle --outfile=dist/extractor.js`

- Pros: Full type safety, IDE support, proper error messages
- Cons: Significant refactor, need build step

### Option 5: TypeScript Migration
Write extractors in TypeScript, compile to single JS bundle.
- Pros: Maximum safety, best tooling
- Cons: Largest effort

## Recommendation

**Short term:** Option 3 (contract verification) - 30 minutes of work, catches breaks immediately.

**Medium term:** Option 4 (module bundling) - 1-2 days, proper architecture without full rewrite.

**Long term:** Option 5 if JS extraction grows significantly.

---

## Files Reference

| File | Location | Purpose |
|------|----------|---------|
| `js_helper_templates.py` | `theauditor/ast_extractors/` | Python orchestrator that concatenates |
| `batch_templates.js` | `theauditor/ast_extractors/javascript/` | Main entry point with main() |
| `*.js` (9 files) | `theauditor/ast_extractors/javascript/` | Extractor fragments |
| `eslint.config.mjs` | Root | ESLint config (ignores batch_templates.js) |
