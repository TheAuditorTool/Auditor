# pipeline Specification Delta

## ADDED Requirements

### Requirement: Core Language Function Parameter Extraction
The JavaScript extractor pipeline SHALL extract function parameters as flat arrays suitable for direct database insertion.

#### Scenario: Function parameters produce flat records
- **WHEN** a JavaScript/TypeScript function has parameters
- **THEN** the extractor SHALL produce a `func_params` array
- **AND** each record SHALL contain `function_name`, `function_line`, `param_index`, `param_name`, `param_type`

#### Scenario: Destructured parameters handled
- **WHEN** a function parameter uses destructuring (object or array)
- **THEN** the extractor SHALL produce records for each destructured binding
- **AND** `param_name` SHALL reflect the binding name, not the pattern

#### Scenario: Parameter decorators extracted
- **WHEN** a function parameter has decorators (e.g., NestJS @Body, @Param)
- **THEN** the extractor SHALL produce `func_param_decorators` records
- **AND** each record SHALL contain `function_name`, `param_index`, `decorator_name`, `decorator_args`

### Requirement: Function Decorator Extraction
The JavaScript extractor pipeline SHALL extract function decorators as flat arrays.

#### Scenario: Function decorators produce flat records
- **WHEN** a function has decorators (e.g., @Get, @Auth)
- **THEN** the extractor SHALL produce a `func_decorators` array
- **AND** each record SHALL contain `function_name`, `function_line`, `decorator_index`, `decorator_name`, `decorator_line`

#### Scenario: Decorator arguments produce flat records
- **WHEN** a decorator has arguments (e.g., @Get('/users'))
- **THEN** the extractor SHALL produce `func_decorator_args` records
- **AND** each record SHALL contain `function_name`, `decorator_index`, `arg_index`, `arg_value`

### Requirement: Class Decorator Extraction
The JavaScript extractor pipeline SHALL extract class decorators as flat arrays.

#### Scenario: Class decorators produce flat records
- **WHEN** a class has decorators (e.g., @Injectable, @Controller)
- **THEN** the extractor SHALL produce a `class_decorators` array
- **AND** each record SHALL contain `class_name`, `class_line`, `decorator_index`, `decorator_name`

### Requirement: Assignment Source Variable Extraction
The JavaScript extractor pipeline SHALL extract assignment source variables as flat arrays for taint propagation.

#### Scenario: Assignment sources produce flat records
- **WHEN** an assignment references multiple source variables (e.g., `const result = a + b * c`)
- **THEN** the extractor SHALL produce `assignment_source_vars` records
- **AND** each record SHALL contain `file`, `line`, `target_var`, `source_var`, `var_index`

#### Scenario: Variable order preserved
- **WHEN** multiple source variables are extracted
- **THEN** `var_index` SHALL preserve the order of appearance in the expression

### Requirement: Return Source Variable Extraction
The JavaScript extractor pipeline SHALL extract return statement source variables as flat arrays.

#### Scenario: Return sources produce flat records
- **WHEN** a return statement references variables (e.g., `return { x, y, z }`)
- **THEN** the extractor SHALL produce `return_source_vars` records
- **AND** each record SHALL contain `file`, `line`, `function_name`, `source_var`, `var_index`

### Requirement: Import Specifier Extraction
The JavaScript extractor pipeline SHALL extract ES6 import specifiers as flat arrays.

#### Scenario: Named imports produce flat records
- **WHEN** an import uses named specifiers (e.g., `import { a, b } from 'mod'`)
- **THEN** the extractor SHALL produce `import_specifiers` records
- **AND** each record SHALL contain `file`, `import_line`, `specifier_name`, `is_named=1`

#### Scenario: Aliased imports capture original name
- **WHEN** an import uses aliases (e.g., `import { foo as bar }`)
- **THEN** `specifier_name` SHALL be 'bar' (local name)
- **AND** `original_name` SHALL be 'foo' (exported name)

#### Scenario: Default imports identified
- **WHEN** an import uses default (e.g., `import axios from 'axios'`)
- **THEN** `is_default` SHALL be 1

#### Scenario: Namespace imports identified
- **WHEN** an import uses namespace (e.g., `import * as React`)
- **THEN** `is_namespace` SHALL be 1

### Requirement: CDK Construct Property Extraction
The JavaScript extractor pipeline SHALL extract AWS CDK construct properties as flat arrays.

#### Scenario: CDK properties produce flat records
- **WHEN** a CDK construct has configuration properties
- **THEN** the extractor SHALL produce `cdk_construct_properties` records
- **AND** each record SHALL contain `construct_name`, `construct_line`, `property_name`, `value_expr`, `value_type`

#### Scenario: Property type inference
- **WHEN** a property value is extracted
- **THEN** `value_type` SHALL indicate: 'boolean', 'string', 'number', 'array', 'object', or 'variable'

### Requirement: Sequelize Model Field Extraction
The JavaScript extractor pipeline SHALL extract Sequelize model field definitions as flat arrays.

#### Scenario: Model fields produce flat records
- **WHEN** a Sequelize model uses `Model.init()` with field definitions
- **THEN** the extractor SHALL produce `sequelize_model_fields` records
- **AND** each record SHALL contain `model_name`, `field_name`, `data_type`, `is_primary_key`, `is_nullable`, `default_value`

#### Scenario: DataTypes parsed correctly
- **WHEN** a field uses DataTypes (STRING, INTEGER, ENUM, etc.)
- **THEN** `data_type` SHALL contain the type name without 'DataTypes.' prefix

### Requirement: CFG Flat Structure Extraction
The JavaScript extractor pipeline SHALL extract Control Flow Graphs as flat arrays.

#### Scenario: CFG blocks produce flat records
- **WHEN** a function's CFG is extracted
- **THEN** the extractor SHALL produce `cfg_blocks` records
- **AND** each record SHALL contain `function_name`, `block_id`, `block_type`, `start_line`, `end_line`

#### Scenario: CFG edges produce flat records
- **WHEN** a function's CFG has control flow edges
- **THEN** the extractor SHALL produce `cfg_edges` records
- **AND** each record SHALL contain `function_name`, `source_block_id`, `target_block_id`, `edge_type`

#### Scenario: CFG block statements produce flat records
- **WHEN** a CFG block contains statements
- **THEN** the extractor SHALL produce `cfg_block_statements` records
- **AND** each record SHALL contain `function_name`, `block_id`, `statement_index`, `statement_type`, `line`

### Requirement: Batch Aggregation of All Junction Arrays
The JavaScript batch template SHALL aggregate all junction arrays from all extractors.

#### Scenario: Core language junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `func_params`, `func_decorators`, `func_decorator_args`, `class_decorators`, `class_decorator_args`

#### Scenario: Data flow junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `assignment_source_vars`, `return_source_vars`

#### Scenario: Module framework junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `import_specifiers`, `import_style_names`

#### Scenario: Security junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `cdk_construct_properties`

#### Scenario: ORM junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `sequelize_model_fields`

#### Scenario: CFG junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `cfg_blocks`, `cfg_edges`, `cfg_block_statements`

#### Scenario: React junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `react_component_hooks`, `react_hook_dependencies`

### Requirement: React Component Hook Extraction
The JavaScript extractor pipeline SHALL extract React component hooks as flat arrays.

#### Scenario: Component hooks produce flat records
- **WHEN** a React component uses hooks (useState, useEffect, etc.)
- **THEN** the extractor SHALL produce `react_component_hooks` records
- **AND** each record SHALL contain `component_file`, `component_name`, `hook_name`

#### Scenario: Hook dependencies produce flat records
- **WHEN** a React hook has dependency array (useEffect, useMemo, etc.)
- **THEN** the extractor SHALL produce `react_hook_dependencies` records
- **AND** each record SHALL contain `hook_file`, `hook_line`, `hook_component`, `dependency_name`

## MODIFIED Requirements

### Requirement: Python Storage Direct Iteration
The Python storage layer SHALL iterate junction arrays directly without JSON parsing.

#### Scenario: Core language junction storage
- **WHEN** `func_params` array is provided to storage
- **THEN** storage SHALL call `add_func_param()` for each record
- **AND** storage SHALL NOT parse JSON strings

#### Scenario: Data flow junction storage
- **WHEN** `assignment_source_vars` array is provided to storage
- **THEN** storage SHALL call `add_assignment_source_var()` for each record
- **AND** storage SHALL NOT parse JSON strings

#### Scenario: Import junction storage
- **WHEN** `import_specifiers` array is provided to storage
- **THEN** storage SHALL call `add_import_specifier()` for each record
- **AND** storage SHALL NOT parse JSON strings

#### Scenario: CDK junction storage
- **WHEN** `cdk_construct_properties` array is provided to storage
- **THEN** storage SHALL call `add_cdk_construct_property()` for each record
- **AND** storage SHALL NOT parse JSON strings

#### Scenario: Sequelize junction storage
- **WHEN** `sequelize_model_fields` array is provided to storage
- **THEN** storage SHALL call `add_sequelize_model_field()` for each record
- **AND** storage SHALL NOT parse JSON strings

#### Scenario: CFG junction storage
- **WHEN** CFG junction arrays are provided to storage
- **THEN** storage SHALL call respective `add_cfg_*()` methods
- **AND** storage SHALL NOT parse JSON strings

#### Scenario: React junction storage
- **WHEN** `react_component_hooks` and `react_hook_dependencies` arrays are provided to storage
- **THEN** storage SHALL call respective `add_react_*()` methods
- **AND** storage SHALL NOT parse JSON strings
