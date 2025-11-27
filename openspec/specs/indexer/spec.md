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

#### Scenario: Contract test detects JSON blob column
- **WHEN** `test_no_json_blob_columns` runs against Node schema
- **THEN** test passes if no JSON blob columns exist
- **AND** test fails if any JSON blob column is found

#### Scenario: Contract test verifies handler methods
- **WHEN** `test_all_handlers_use_batched_methods` runs
- **THEN** test passes if no `cursor.execute` calls found in node_storage.py
- **AND** test fails if direct cursor access is detected

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

