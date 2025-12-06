# pipeline Specification Delta

## PENDING Requirements

### Requirement: Core Language Function Parameter Extraction
The JavaScript extractor pipeline SHALL extract function parameters as flat arrays suitable for direct database insertion.

#### Scenario: Function parameters produce flat records
- **WHEN** a JavaScript/TypeScript function has parameters
- **THEN** the extractor SHALL produce a `func_params` array
- **AND** each record SHALL contain `function_name`, `function_line`, `param_index`, `param_name`, `param_type`
- **STATUS:** PENDING (Phase 2)

#### Scenario: Destructured parameters handled
- **WHEN** a function parameter uses destructuring (object or array)
- **THEN** the extractor SHALL produce records for each destructured binding
- **AND** `param_name` SHALL reflect the binding name, not the pattern
- **STATUS:** PENDING (Phase 2)

#### Scenario: Parameter decorators extracted
- **WHEN** a function parameter has decorators (e.g., NestJS @Body, @Param)
- **THEN** the extractor SHALL produce `func_param_decorators` records
- **AND** each record SHALL contain `function_name`, `param_index`, `decorator_name`, `decorator_args`
- **STATUS:** PENDING (Phase 2)

### Requirement: Function Decorator Extraction
The JavaScript extractor pipeline SHALL extract function decorators as flat arrays.

#### Scenario: Function decorators produce flat records
- **WHEN** a function has decorators (e.g., @Get, @Auth)
- **THEN** the extractor SHALL produce a `func_decorators` array
- **AND** each record SHALL contain `function_name`, `function_line`, `decorator_index`, `decorator_name`, `decorator_line`
- **STATUS:** PENDING (Phase 2)

#### Scenario: Decorator arguments produce flat records
- **WHEN** a decorator has arguments (e.g., @Get('/users'))
- **THEN** the extractor SHALL produce `func_decorator_args` records
- **AND** each record SHALL contain `function_name`, `decorator_index`, `arg_index`, `arg_value`
- **STATUS:** PENDING (Phase 2)

### Requirement: Class Decorator Extraction
The JavaScript extractor pipeline SHALL extract class decorators as flat arrays.

#### Scenario: Class decorators produce flat records
- **WHEN** a class has decorators (e.g., @Injectable, @Controller)
- **THEN** the extractor SHALL produce a `class_decorators` array
- **AND** each record SHALL contain `class_name`, `class_line`, `decorator_index`, `decorator_name`
- **STATUS:** PENDING (Phase 2)

### Requirement: Assignment Source Variable Extraction
The JavaScript extractor pipeline SHALL extract assignment source variables as flat arrays for taint propagation.

#### Scenario: Assignment sources produce flat records
- **WHEN** an assignment references multiple source variables (e.g., `const result = a + b * c`)
- **THEN** the extractor SHALL produce `assignment_source_vars` records
- **AND** each record SHALL contain `file`, `line`, `target_var`, `source_var`, `var_index`
- **STATUS:** PENDING (Phase 4)

#### Scenario: Variable order preserved
- **WHEN** multiple source variables are extracted
- **THEN** `var_index` SHALL preserve the order of appearance in the expression
- **STATUS:** PENDING (Phase 4)

### Requirement: Return Source Variable Extraction
The JavaScript extractor pipeline SHALL extract return statement source variables as flat arrays.

#### Scenario: Return sources produce flat records
- **WHEN** a return statement references variables (e.g., `return { x, y, z }`)
- **THEN** the extractor SHALL produce `return_source_vars` records
- **AND** each record SHALL contain `file`, `line`, `function_name`, `source_var`, `var_index`
- **STATUS:** PENDING (Phase 4)

### Requirement: Import Specifier Extraction
The JavaScript extractor pipeline SHALL extract ES6 import specifiers as flat arrays.

#### Scenario: Named imports produce flat records
- **WHEN** an import uses named specifiers (e.g., `import { a, b } from 'mod'`)
- **THEN** the extractor SHALL produce `import_specifiers` records
- **AND** each record SHALL contain `file`, `import_line`, `specifier_name`, `is_named=1`
- **STATUS:** PENDING (Phase 5)

#### Scenario: Aliased imports capture original name
- **WHEN** an import uses aliases (e.g., `import { foo as bar }`)
- **THEN** `specifier_name` SHALL be 'bar' (local name)
- **AND** `original_name` SHALL be 'foo' (exported name)
- **STATUS:** PENDING (Phase 5)

#### Scenario: Default imports identified
- **WHEN** an import uses default (e.g., `import axios from 'axios'`)
- **THEN** `is_default` SHALL be 1
- **STATUS:** PENDING (Phase 5)

#### Scenario: Namespace imports identified
- **WHEN** an import uses namespace (e.g., `import * as React`)
- **THEN** `is_namespace` SHALL be 1
- **STATUS:** PENDING (Phase 5)

### Requirement: Sequelize Model Field Extraction
The JavaScript extractor pipeline SHALL extract Sequelize model field definitions as flat arrays.

#### Scenario: Model fields produce flat records
- **WHEN** a Sequelize model uses `Model.init()` with field definitions
- **THEN** the extractor SHALL produce `sequelize_model_fields` records
- **AND** each record SHALL contain `model_name`, `field_name`, `data_type`, `is_primary_key`, `is_nullable`, `default_value`
- **STATUS:** PENDING (Phase 7)

#### Scenario: DataTypes parsed correctly
- **WHEN** a field uses DataTypes (STRING, INTEGER, ENUM, etc.)
- **THEN** `data_type` SHALL contain the type name without 'DataTypes.' prefix
- **STATUS:** PENDING (Phase 7)

### Requirement: Batch Aggregation of All Junction Arrays
The JavaScript batch template SHALL aggregate all junction arrays from all extractors.

#### Scenario: Core language junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `func_params`, `func_decorators`, `func_decorator_args`, `class_decorators`, `class_decorator_args`
- **STATUS:** PENDING (Phase 9)

#### Scenario: Data flow junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `assignment_source_vars`, `return_source_vars`
- **STATUS:** PENDING (Phase 9)

#### Scenario: Module framework junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `import_specifiers`
- **STATUS:** PENDING (Phase 9)

#### Scenario: ORM junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `sequelize_model_fields`
- **STATUS:** PENDING (Phase 9)

---

## PRE-EXISTING (Not in Scope)

The following already work via existing mechanisms:

### CFG Flat Structure
- **Tables:** cfg_blocks, cfg_edges, cfg_block_statements
- **Location:** core_schema.py
- **Mechanism:** cfg_extractor.js produces nested, core_storage.py flattens

### CDK Construct Properties
- **Table:** cdk_construct_properties
- **Location:** infrastructure_schema.py
- **Status:** Already populated

### React Component Hooks
- **Tables:** react_component_hooks, react_hook_dependencies
- **Location:** node_schema.py
- **Mechanism:** add_react_component(), add_react_hook() flatten internally

### Import Style Names
- **Table:** import_style_names
- **Location:** node_schema.py
- **Status:** Already populated via database method

---

## MODIFIED Requirements

### Requirement: Python Storage Direct Iteration
The Python storage layer SHALL iterate junction arrays directly without JSON parsing.

#### Scenario: Core language junction storage
- **WHEN** `func_params` array is provided to storage
- **THEN** storage SHALL call `add_func_param()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)

#### Scenario: Data flow junction storage
- **WHEN** `assignment_source_vars` array is provided to storage
- **THEN** storage SHALL call `add_assignment_source_var()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)

#### Scenario: Import junction storage
- **WHEN** `import_specifiers` array is provided to storage
- **THEN** storage SHALL call `add_import_specifier()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)

#### Scenario: Sequelize junction storage
- **WHEN** `sequelize_model_fields` array is provided to storage
- **THEN** storage SHALL call `add_sequelize_model_field()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)
