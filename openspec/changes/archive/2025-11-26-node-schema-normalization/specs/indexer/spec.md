## ADDED Requirements

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

