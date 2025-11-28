# indexer Specification

## Purpose
TBD - created by archiving change node-schema-normalization. Update Purpose after archive.
## Requirements
### Requirement: Vue Component Props Junction Table

The Node schema SHALL include a `vue_component_props` junction table to store individual prop definitions extracted from Vue components.

The table SHALL contain columns for: file, component_name, prop_name, prop_type, is_required, default_value.

#### Scenario: Vue component with multiple props stored as junction records
- **WHEN** a Vue component with `props: { name: String, age: Number }` is extracted
- **THEN** two records are inserted into `vue_component_props`
- **AND** each record contains the file, component_name, and individual prop details

### Requirement: Vue Component Emits Junction Table

The Node schema SHALL include a `vue_component_emits` junction table to store individual emit definitions extracted from Vue components.

The table SHALL contain columns for: file, component_name, emit_name, payload_type.

#### Scenario: Vue component with emits stored as junction records
- **WHEN** a Vue component with `emits: ['update', 'delete']` is extracted
- **THEN** two records are inserted into `vue_component_emits`
- **AND** each record contains the file, component_name, and emit name

### Requirement: Vue Component Setup Returns Junction Table

The Node schema SHALL include a `vue_component_setup_returns` junction table to store individual setup return values extracted from Vue components.

The table SHALL contain columns for: file, component_name, return_name, return_type.

#### Scenario: Vue component with setup returns stored as junction records
- **WHEN** a Vue component with `setup() { return { count, increment } }` is extracted
- **THEN** two records are inserted into `vue_component_setup_returns`
- **AND** each record contains the file, component_name, and return details

### Requirement: Angular Component Styles Junction Table

The Node schema SHALL include an `angular_component_styles` junction table to store individual style paths extracted from Angular components.

The table SHALL contain columns for: file, component_name, style_path.

#### Scenario: Angular component with multiple styleUrls stored as junction records
- **WHEN** an Angular component with `styleUrls: ['./app.css', './theme.css']` is extracted
- **THEN** two records are inserted into `angular_component_styles`
- **AND** each record contains the file, component_name, and individual style path

### Requirement: Angular Module Declarations Junction Table

The Node schema SHALL include an `angular_module_declarations` junction table to store individual declaration entries from Angular modules.

The table SHALL contain columns for: file, module_name, declaration_name, declaration_type.

#### Scenario: Angular module with declarations stored as junction records
- **WHEN** an Angular module with `declarations: [AppComponent, HeaderComponent]` is extracted
- **THEN** two records are inserted into `angular_module_declarations`
- **AND** each record contains the file, module_name, and declaration details

### Requirement: Angular Module Imports Junction Table

The Node schema SHALL include an `angular_module_imports` junction table to store individual import entries from Angular modules.

The table SHALL contain columns for: file, module_name, imported_module.

#### Scenario: Angular module with imports stored as junction records
- **WHEN** an Angular module with `imports: [CommonModule, FormsModule]` is extracted
- **THEN** two records are inserted into `angular_module_imports`
- **AND** each record contains the file, module_name, and imported module name

### Requirement: Angular Module Providers Junction Table

The Node schema SHALL include an `angular_module_providers` junction table to store individual provider entries from Angular modules.

The table SHALL contain columns for: file, module_name, provider_name, provider_type.

#### Scenario: Angular module with providers stored as junction records
- **WHEN** an Angular module with `providers: [AuthService, { provide: API_URL, useValue: '/api' }]` is extracted
- **THEN** two records are inserted into `angular_module_providers`
- **AND** each record contains the file, module_name, provider name, and provider type

### Requirement: Angular Module Exports Junction Table

The Node schema SHALL include an `angular_module_exports` junction table to store individual export entries from Angular modules.

The table SHALL contain columns for: file, module_name, exported_name.

#### Scenario: Angular module with exports stored as junction records
- **WHEN** an Angular module with `exports: [SharedComponent, SharedDirective]` is extracted
- **THEN** two records are inserted into `angular_module_exports`
- **AND** each record contains the file, module_name, and exported name

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

### Requirement: Function Parameter Junction Table
The Node.js schema SHALL include a junction table for function parameters.

#### Scenario: func_params table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_params` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, param_index, param_name, param_type
- **AND** indexes SHALL exist for function lookup and param_name search
- **STATUS:** IMPLEMENTED (node_schema.py:750-764)

### Requirement: Function Decorator Junction Tables
The Node.js schema SHALL include junction tables for function decorators and their arguments.

#### Scenario: func_decorators table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_decorators` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, decorator_index, decorator_name, decorator_line
- **STATUS:** IMPLEMENTED (node_schema.py:766-781)

#### Scenario: func_decorator_args table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_decorator_args` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, decorator_index, arg_index, arg_value
- **STATUS:** IMPLEMENTED (node_schema.py:783-797)

### Requirement: Function Parameter Decorator Junction Table
The Node.js schema SHALL include a junction table for function parameter decorators (NestJS @Body, @Param, etc.).

#### Scenario: func_param_decorators table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_param_decorators` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, param_index, decorator_name, decorator_args
- **AND** indexes SHALL exist for function lookup and decorator_name search
- **STATUS:** IMPLEMENTED (node_schema.py:799-814)

### Requirement: Class Decorator Junction Tables
The Node.js schema SHALL include junction tables for class decorators and their arguments.

#### Scenario: class_decorators table schema
- **WHEN** the database schema is initialized
- **THEN** the `class_decorators` table SHALL exist
- **AND** columns SHALL include: file, class_line, class_name, decorator_index, decorator_name, decorator_line
- **STATUS:** IMPLEMENTED (node_schema.py:816-831)

#### Scenario: class_decorator_args table schema
- **WHEN** the database schema is initialized
- **THEN** the `class_decorator_args` table SHALL exist
- **AND** columns SHALL include: file, class_line, class_name, decorator_index, arg_index, arg_value
- **STATUS:** IMPLEMENTED (node_schema.py:833-847)

### Requirement: Assignment Source Variables Junction Table
The Node.js schema SHALL include a junction table for assignment source variables.

#### Scenario: assignment_source_vars table schema
- **WHEN** the database schema is initialized
- **THEN** the `assignment_source_vars` table SHALL exist
- **AND** columns SHALL include: file, line, target_var, source_var, var_index
- **AND** indexes SHALL exist for assignment lookup and source_var search
- **STATUS:** IMPLEMENTED (node_schema.py:854-868)

### Requirement: Return Source Variables Junction Table
The Node.js schema SHALL include a junction table for return statement source variables.

#### Scenario: return_source_vars table schema
- **WHEN** the database schema is initialized
- **THEN** the `return_source_vars` table SHALL exist
- **AND** columns SHALL include: file, line, function_name, source_var, var_index
- **AND** indexes SHALL exist for return lookup and source_var search
- **STATUS:** IMPLEMENTED (node_schema.py:870-884)

### Requirement: Import Specifiers Junction Table
The Node.js schema SHALL include a junction table for ES6 import specifiers.

#### Scenario: import_specifiers table schema
- **WHEN** the database schema is initialized
- **THEN** the `import_specifiers` table SHALL exist
- **AND** columns SHALL include: file, import_line, specifier_name, original_name, is_default, is_namespace, is_named
- **AND** indexes SHALL exist for import lookup and specifier_name search
- **STATUS:** IMPLEMENTED (node_schema.py:891-907)

### Requirement: Sequelize Model Fields Junction Table
The Node.js schema SHALL include a junction table for Sequelize ORM model field definitions.

#### Scenario: sequelize_model_fields table schema
- **WHEN** the database schema is initialized
- **THEN** the `sequelize_model_fields` table SHALL exist
- **AND** columns SHALL include: file, model_name, field_name, data_type, is_primary_key, is_nullable, is_unique, default_value
- **AND** indexes SHALL exist for model lookup and data_type search
- **STATUS:** IMPLEMENTED (node_schema.py:914-931)

---

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

