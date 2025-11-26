# indexer Specification Delta

## ADDED Requirements

### Requirement: Function Parameter Junction Table
The Node.js schema SHALL include a junction table for function parameters.

#### Scenario: func_params table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_params` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, param_index, param_name, param_type
- **AND** indexes SHALL exist for function lookup and param_name search

### Requirement: Function Decorator Junction Tables
The Node.js schema SHALL include junction tables for function decorators and their arguments.

#### Scenario: func_decorators table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_decorators` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, decorator_index, decorator_name, decorator_line

#### Scenario: func_decorator_args table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_decorator_args` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, decorator_index, arg_index, arg_value

### Requirement: Function Parameter Decorator Junction Table
The Node.js schema SHALL include a junction table for function parameter decorators (NestJS @Body, @Param, etc.).

#### Scenario: func_param_decorators table schema
- **WHEN** the database schema is initialized
- **THEN** the `func_param_decorators` table SHALL exist
- **AND** columns SHALL include: file, function_line, function_name, param_index, decorator_name, decorator_args
- **AND** indexes SHALL exist for function lookup and decorator_name search

### Requirement: Class Decorator Junction Tables
The Node.js schema SHALL include junction tables for class decorators and their arguments.

#### Scenario: class_decorators table schema
- **WHEN** the database schema is initialized
- **THEN** the `class_decorators` table SHALL exist
- **AND** columns SHALL include: file, class_line, class_name, decorator_index, decorator_name, decorator_line

#### Scenario: class_decorator_args table schema
- **WHEN** the database schema is initialized
- **THEN** the `class_decorator_args` table SHALL exist
- **AND** columns SHALL include: file, class_line, class_name, decorator_index, arg_index, arg_value

### Requirement: Assignment Source Variables Junction Table
The Node.js schema SHALL include a junction table for assignment source variables.

#### Scenario: assignment_source_vars table schema
- **WHEN** the database schema is initialized
- **THEN** the `assignment_source_vars` table SHALL exist
- **AND** columns SHALL include: file, line, target_var, source_var, var_index
- **AND** indexes SHALL exist for assignment lookup and source_var search

### Requirement: Return Source Variables Junction Table
The Node.js schema SHALL include a junction table for return statement source variables.

#### Scenario: return_source_vars table schema
- **WHEN** the database schema is initialized
- **THEN** the `return_source_vars` table SHALL exist
- **AND** columns SHALL include: file, line, function_name, source_var, var_index
- **AND** indexes SHALL exist for return lookup and source_var search

### Requirement: Import Specifiers Junction Table
The Node.js schema SHALL include a junction table for ES6 import specifiers.

#### Scenario: import_specifiers table schema
- **WHEN** the database schema is initialized
- **THEN** the `import_specifiers` table SHALL exist
- **AND** columns SHALL include: file, import_line, specifier_name, original_name, is_default, is_namespace, is_named
- **AND** indexes SHALL exist for import lookup and specifier_name search

### Requirement: CDK Construct Properties Junction Table
The Node.js schema SHALL include a junction table for AWS CDK construct properties.

#### Scenario: cdk_construct_properties table schema
- **WHEN** the database schema is initialized
- **THEN** the `cdk_construct_properties` table SHALL exist
- **AND** columns SHALL include: file, construct_line, construct_name, property_name, value_expr, value_type
- **AND** indexes SHALL exist for construct lookup and property_name search

### Requirement: Sequelize Model Fields Junction Table
The Node.js schema SHALL include a junction table for Sequelize ORM model field definitions.

#### Scenario: sequelize_model_fields table schema
- **WHEN** the database schema is initialized
- **THEN** the `sequelize_model_fields` table SHALL exist
- **AND** columns SHALL include: file, model_name, field_name, data_type, is_primary_key, is_nullable, is_unique, default_value
- **AND** indexes SHALL exist for model lookup and data_type search

### Requirement: CFG Blocks Junction Table
The Node.js schema SHALL include a junction table for Control Flow Graph blocks.

#### Scenario: cfg_blocks table schema
- **WHEN** the database schema is initialized
- **THEN** the `cfg_blocks` table SHALL exist
- **AND** columns SHALL include: file, function_name, block_id, block_type, start_line, end_line, condition_expr
- **AND** indexes SHALL exist for function lookup

### Requirement: CFG Edges Junction Table
The Node.js schema SHALL include a junction table for Control Flow Graph edges.

#### Scenario: cfg_edges table schema
- **WHEN** the database schema is initialized
- **THEN** the `cfg_edges` table SHALL exist
- **AND** columns SHALL include: file, function_name, source_block_id, target_block_id, edge_type
- **AND** indexes SHALL exist for function lookup, source lookup, and target lookup

### Requirement: CFG Block Statements Junction Table
The Node.js schema SHALL include a junction table for CFG block statements.

#### Scenario: cfg_block_statements table schema
- **WHEN** the database schema is initialized
- **THEN** the `cfg_block_statements` table SHALL exist
- **AND** columns SHALL include: file, function_name, block_id, statement_index, statement_type, line, text
- **AND** indexes SHALL exist for block lookup

### Requirement: Database Methods for Junction Tables
The Node.js database layer SHALL provide add methods for all junction tables.

#### Scenario: Function parameter database method
- **WHEN** `add_func_param()` is called
- **THEN** a record SHALL be added to the `func_params` batch
- **AND** the method SHALL NOT perform JSON parsing

#### Scenario: Decorator database methods
- **WHEN** `add_func_decorator()` or `add_class_decorator()` is called
- **THEN** a record SHALL be added to the respective decorator batch
- **AND** the method SHALL NOT perform JSON parsing

#### Scenario: Data flow database methods
- **WHEN** `add_assignment_source_var()` or `add_return_source_var()` is called
- **THEN** a record SHALL be added to the respective batch
- **AND** the method SHALL NOT perform JSON parsing

#### Scenario: Import specifier database method
- **WHEN** `add_import_specifier()` is called
- **THEN** a record SHALL be added to the `import_specifiers` batch
- **AND** the method SHALL NOT perform JSON parsing

#### Scenario: CDK property database method
- **WHEN** `add_cdk_construct_property()` is called
- **THEN** a record SHALL be added to the `cdk_construct_properties` batch
- **AND** the method SHALL NOT perform JSON parsing

#### Scenario: Sequelize field database method
- **WHEN** `add_sequelize_model_field()` is called
- **THEN** a record SHALL be added to the `sequelize_model_fields` batch
- **AND** the method SHALL NOT perform JSON parsing

#### Scenario: CFG database methods
- **WHEN** `add_cfg_block()`, `add_cfg_edge()`, or `add_cfg_block_statement()` is called
- **THEN** a record SHALL be added to the respective CFG batch
- **AND** the method SHALL NOT perform JSON parsing

### Requirement: Storage Handlers for Junction Tables
The Node.js storage layer SHALL provide handlers for all junction tables.

#### Scenario: Parameter decorator database method
- **WHEN** `add_func_param_decorator()` is called
- **THEN** a record SHALL be added to the `func_param_decorators` batch
- **AND** the method SHALL NOT perform JSON parsing

#### Scenario: Storage handler registration
- **WHEN** NodeStorage is initialized
- **THEN** handlers SHALL be registered for all 14 new junction array keys
- **AND** handlers SHALL iterate arrays directly without JSON parsing

#### Scenario: Storage handler behavior
- **WHEN** a junction array handler processes data
- **THEN** it SHALL call the corresponding database `add_*` method for each record
- **AND** it SHALL increment the appropriate count in `self.counts`
