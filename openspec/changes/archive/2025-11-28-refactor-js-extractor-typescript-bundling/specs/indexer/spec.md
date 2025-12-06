## ADDED Requirements

### Requirement: TypeScript Extractor Build Pipeline

The Node.js extractor system SHALL use TypeScript source files compiled to a single JavaScript bundle via esbuild.

### Requirement: Semantic Extraction via TypeChecker (from discussions.md)

The TypeScript extractors SHALL use `ts.TypeChecker` for semantic analysis instead of text-based parsing.

Semantic extraction SHALL:
- Use `checker.getDeclaredTypeOfSymbol()` to resolve class inheritance
- Use `checker.getSymbolAtLocation()` to resolve function call targets
- Use `checker.getFullyQualifiedName()` to get canonical symbol names
- Include `defined_in` field for cross-file symbol resolution

#### Scenario: Class inheritance resolved semantically
- **WHEN** a class `UserController extends BaseController` is extracted
- **THEN** `extractClasses` returns `extends: ["BaseController"]` (resolved type, not text)
- **AND** `properties` array includes inherited properties from BaseController
- **AND** `methods` array includes inherited methods from BaseController

#### Scenario: Function call resolved semantically
- **WHEN** a call `db.User.findAll()` is extracted
- **THEN** `extractCalls` returns `name: "User.findAll"` (resolved symbol)
- **AND** `original_text: "db.User.findAll"` (for debugging)
- **AND** `defined_in: "/models/User.ts"` (file where function is defined)

### Requirement: Delete serializeNodeForCFG (from discussions.md)

The `serializeNodeForCFG` function SHALL be deleted from `core_language.js`.

Deletion rationale:
- Function is a "recursion bomb" that walks entire AST
- Builds 5000-level deep JSON causing 512MB crash on large files
- Legacy code from before structured extraction tables existed
- Python no longer needs raw AST tree - receives flat extraction tables

#### Scenario: serializeNodeForCFG not called
- **WHEN** extraction runs on any file
- **THEN** `batch_templates.js` sets `ast: null`
- **AND** no code path invokes `serializeNodeForCFG`

### Requirement: CFG Optimization (from discussions.md)

The CFG extractor SHALL skip non-executable code and flatten JSX to prevent memory issues.

CFG optimization SHALL:
- Skip `InterfaceDeclaration`, `TypeAliasDeclaration`, `ImportDeclaration`, `ModuleDeclaration`
- Flatten JSX to single `jsx_root` statement per tree
- Keep `depth > 500` guard for safety
- Reduce memory usage by ~40% on TypeScript projects

#### Scenario: Non-executable code skipped
- **WHEN** CFG extraction encounters an `InterfaceDeclaration`
- **THEN** the interface is NOT traversed for CFG blocks
- **AND** no CFG blocks or edges are created for type definitions

#### Scenario: JSX flattened
- **WHEN** CFG extraction encounters deeply nested JSX (`<div><div><div>...`)
- **THEN** only ONE `jsx_root` statement is recorded for the outermost element
- **AND** child JSX elements do NOT create additional CFG blocks
- **AND** embedded functions (onClick handlers) ARE still extracted

### Requirement: Python Zombie Method Deletion (from discussions.md)

The Python extractor (`javascript.py`) SHALL NOT contain duplicate extraction logic.

Python zombie cleanup SHALL:
- DELETE `_extract_sql_from_function_calls()` method
- DELETE `_extract_jwt_from_function_calls()` method
- DELETE `_extract_routes_from_ast()` method
- DELETE any `if not extracted_data: ... traverse AST` fallback blocks
- SIMPLIFY `extract()` to trust `extracted_data` without fallbacks

#### Scenario: No Python fallback extraction
- **WHEN** `extract()` is called with valid `extracted_data`
- **THEN** data is consumed directly from `extracted_data`
- **AND** NO Python AST traversal is performed
- **AND** if data is missing, error is logged (bug is in JS)

#### Scenario: javascript_resolvers.py unchanged
- **WHEN** cross-file resolution is needed
- **THEN** `javascript_resolvers.py` performs SQL-based linking
- **AND** NO new Python extraction logic is added to resolvers
- **AND** if resolvers fail, fix JS extraction that feeds them

The build pipeline SHALL:
- Read TypeScript source from `theauditor/ast_extractors/javascript/src/`
- Compile using TypeScript strict mode
- Bundle using esbuild to `theauditor/ast_extractors/javascript/dist/extractor.js`
- Validate output shape using Zod schemas before JSON serialization

#### Scenario: Build produces single bundle
- **WHEN** `npm run build` is executed in the javascript directory
- **THEN** `dist/extractor.js` is created as a single self-contained file
- **AND** the bundle includes all extractor logic from 9 source modules

#### Scenario: Build fails on type errors
- **WHEN** TypeScript source contains type errors
- **THEN** `npm run typecheck` fails with descriptive error messages
- **AND** no bundle is produced until errors are fixed

### Requirement: Zod Schema Validation

The Node.js extractor SHALL validate extraction output against Zod schemas before returning JSON to Python.

Validation SHALL:
- Define schemas for all 50+ extraction data types
- Mirror Python storage handler expected column names
- Throw descriptive error if validation fails
- Allow Python to receive only validated, well-formed JSON

#### Scenario: Valid extraction passes validation
- **WHEN** file extraction produces conforming data
- **THEN** Zod validation passes silently
- **AND** JSON output matches expected schema

#### Scenario: Malformed extraction fails fast
- **WHEN** file extraction produces non-conforming data (e.g., string where number expected)
- **THEN** Zod validation throws ZodError
- **AND** error message identifies which field failed and why
- **AND** Python receives error response, not corrupt data

### Requirement: Simplified Python Orchestrator

The Python orchestrator (`js_helper_templates.py`) SHALL read the pre-compiled bundle instead of concatenating JavaScript strings at runtime.

The simplified orchestrator SHALL:
- Read `dist/extractor.js` directly as a single file
- Raise FileNotFoundError with build instructions if bundle missing
- Remove all runtime string concatenation logic
- Remove the `_JS_CACHE` dictionary and lazy loading

#### Scenario: Bundle exists
- **WHEN** `get_batch_helper()` is called
- **AND** `dist/extractor.js` exists
- **THEN** the function returns the bundle content as string

#### Scenario: Bundle missing
- **WHEN** `get_batch_helper()` is called
- **AND** `dist/extractor.js` does not exist
- **THEN** FileNotFoundError is raised
- **AND** error message includes: "Run 'npm run build' in theauditor/ast_extractors/javascript"

### Requirement: ES Module Extractor Exports

Each TypeScript extractor module SHALL explicitly export all functions used by the main entry point.

Exports SHALL:
- Use named exports (not default exports)
- Include TypeScript type annotations on all parameters and return values
- Be importable by `src/main.ts`

#### Scenario: Extractor function exported
- **WHEN** `src/extractors/core_language.ts` is compiled
- **THEN** `extractFunctions`, `extractClasses`, `buildScopeMap`, `extractClassProperties`, `countNodes` are all exported
- **AND** each function has TypeScript parameter and return types

#### Scenario: Import resolves correctly
- **WHEN** `src/main.ts` imports from `./extractors/core_language`
- **THEN** all named exports are available
- **AND** TypeScript can verify call signatures at compile time

### Requirement: Extractor Type Definitions

The TypeScript extractor system SHALL define interfaces for all extraction data structures in `src/types/index.ts`.

Type definitions SHALL:
- Mirror the column structure of corresponding database tables
- Be shared across all extractor modules
- Be compatible with Zod schema definitions

#### Scenario: Function type matches database schema
- **WHEN** `IFunction` interface is defined
- **THEN** properties match `node_functions` table columns: name, line, end_line, type, async, generator, etc.
- **AND** TypeScript enforces these properties on extracted function objects

## MODIFIED Requirements

### Requirement: Node Schema Contract Tests

The codebase SHALL include contract tests that verify Node schema structure and prevent drift.

Contract tests SHALL verify:
- Expected number of Node tables exists
- No JSON blob columns remain (props_definition, emits_definition, setup_return, style_paths, declarations, imports, providers, exports)
- All junction tables have appropriate indexes
- All storage handlers use batched database methods
- **TypeScript Zod schemas match Python storage handler expected keys**

#### Scenario: Contract test detects JSON blob column
- **WHEN** `test_no_json_blob_columns` runs against Node schema
- **THEN** test passes if no JSON blob columns exist
- **AND** test fails if any JSON blob column is found

#### Scenario: Contract test verifies handler methods
- **WHEN** `test_all_handlers_use_batched_methods` runs
- **THEN** test passes if no `cursor.execute` calls found in node_storage.py
- **AND** test fails if direct cursor access is detected

#### Scenario: Contract test verifies Zod-Python schema sync
- **WHEN** `test_zod_schema_matches_python_handlers` runs
- **THEN** test compares Zod schema keys against Python storage handler dictionary keys
- **AND** test fails if any mismatch detected between Node output and Python expectations

#### Scenario: Contract test verifies semantic extraction fields (from discussions.md)
- **WHEN** `test_semantic_extraction_fields` runs
- **THEN** test verifies `ClassSchema` includes `extends`, `implements`, `properties`, `methods` arrays
- **AND** test verifies `CallSymbolSchema` includes `name`, `original_text`, `defined_in` fields
- **AND** test fails if semantic fields are missing from Zod schemas

#### Scenario: Contract test verifies serializeNodeForCFG deleted (from discussions.md)
- **WHEN** `test_no_serialize_node_for_cfg` runs
- **THEN** test searches for `serializeNodeForCFG` in codebase
- **AND** test fails if function exists in any extractor file
- **AND** test verifies `batch_templates.js` sets `ast: null`
