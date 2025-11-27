# indexer Specification Delta

## ADDED Requirements

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

## PRE-EXISTING (Not in Scope)

The following tables already exist in other schema files:

### CDK Construct Properties
- **Location:** infrastructure_schema.py:259
- **Status:** Already populated

### CFG Tables
- **Location:** core_schema.py:382-417
- **Tables:** cfg_blocks, cfg_edges, cfg_block_statements
- **Status:** Already populated via core_storage.py

### React Junction Tables
- **Location:** node_schema.py:78, 123
- **Tables:** react_component_hooks, react_hook_dependencies
- **Status:** Already populated via add_react_component(), add_react_hook()

### Import Style Names
- **Location:** node_schema.py:497
- **Status:** Already populated via database method

---

## PENDING Requirements

### Requirement: Database Methods for Junction Tables
The Node.js database layer SHALL provide add methods for all junction tables.

#### Scenario: Function parameter database method
- **WHEN** `add_func_param()` is called
- **THEN** a record SHALL be added to the `func_params` batch
- **AND** the method SHALL NOT perform JSON parsing
- **STATUS:** PENDING (Phase 9)

#### Scenario: Decorator database methods
- **WHEN** `add_func_decorator()` or `add_class_decorator()` is called
- **THEN** a record SHALL be added to the respective decorator batch
- **AND** the method SHALL NOT perform JSON parsing
- **STATUS:** PENDING (Phase 9)

#### Scenario: Data flow database methods
- **WHEN** `add_assignment_source_var()` or `add_return_source_var()` is called
- **THEN** a record SHALL be added to the respective batch
- **AND** the method SHALL NOT perform JSON parsing
- **STATUS:** PENDING (Phase 9)

#### Scenario: Import specifier database method
- **WHEN** `add_import_specifier()` is called
- **THEN** a record SHALL be added to the `import_specifiers` batch
- **AND** the method SHALL NOT perform JSON parsing
- **STATUS:** PENDING (Phase 9)

#### Scenario: Sequelize field database method
- **WHEN** `add_sequelize_model_field()` is called
- **THEN** a record SHALL be added to the `sequelize_model_fields` batch
- **AND** the method SHALL NOT perform JSON parsing
- **STATUS:** PENDING (Phase 9)

### Requirement: Storage Handlers for Junction Tables
The Node.js storage layer SHALL provide handlers for all junction tables.

#### Scenario: Parameter decorator database method
- **WHEN** `add_func_param_decorator()` is called
- **THEN** a record SHALL be added to the `func_param_decorators` batch
- **AND** the method SHALL NOT perform JSON parsing
- **STATUS:** PENDING (Phase 9)

#### Scenario: Storage handler registration
- **WHEN** NodeStorage is initialized
- **THEN** handlers SHALL be registered for all 10 new junction array keys
- **AND** handlers SHALL iterate arrays directly without JSON parsing
- **STATUS:** PENDING (Phase 9)

#### Scenario: Storage handler behavior
- **WHEN** a junction array handler processes data
- **THEN** it SHALL call the corresponding database `add_*` method for each record
- **AND** it SHALL increment the appropriate count in `self.counts`
- **STATUS:** PENDING (Phase 9)
