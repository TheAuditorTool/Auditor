# Junction Tables Specification

## ADDED Requirements

### Requirement: Junction Table Architecture

The system SHALL use junction tables to normalize JSON array columns, enabling SQL JOINs.

#### Scenario: Junction table structure follows pattern
- **WHEN** a junction table is created
- **THEN** it contains: id (PK), file (denormalized), parent_id (FK), item_name, item_order
- **AND** foreign key references parent table with ON DELETE CASCADE

#### Scenario: Junction tables have required indexes
- **WHEN** a junction table is created
- **THEN** indexes exist on: file, parent_id, item_name

#### Scenario: Junction tables added to flush order
- **WHEN** `flush_batch()` is called
- **THEN** all 5 junction tables are flushed after their parent tables

---

### Requirement: Protocol Methods Junction Table

The system SHALL store protocol implemented methods in `python_protocol_methods` junction table.

#### Scenario: Protocol methods queryable via JOIN
- **WHEN** `extract_iterator_protocol` produces methods `['__iter__', '__next__']`
- **THEN** two rows are inserted into `python_protocol_methods`
- **AND** each row contains method_name and protocol_id foreign key

#### Scenario: Find protocols by method
- **WHEN** querying `SELECT p.* FROM python_protocols p JOIN python_protocol_methods pm ON p.id = pm.protocol_id WHERE pm.method_name = '__iter__'`
- **THEN** all protocols implementing `__iter__` are returned

#### Scenario: Method order preserved
- **WHEN** methods are stored
- **THEN** `method_order` column preserves original array order

---

### Requirement: TypedDict Fields Junction Table

The system SHALL store TypedDict field definitions in `python_typeddict_fields` junction table.

#### Scenario: TypedDict fields queryable via JOIN
- **WHEN** `extract_typed_dicts` produces fields `{'name': 'str', 'age': 'int'}`
- **THEN** two rows are inserted into `python_typeddict_fields`
- **AND** each row contains field_name, field_type, and typeddict_id foreign key

#### Scenario: Find TypedDicts by field name
- **WHEN** querying for TypedDicts containing a 'user_id' field
- **THEN** JOIN on `python_typeddict_fields WHERE field_name = 'user_id'` returns matching TypedDicts

#### Scenario: Required field tracking
- **WHEN** TypedDict has required fields
- **THEN** `required` column indicates whether field is required (1) or optional (0)

---

### Requirement: Fixture Parameters Junction Table

The system SHALL store pytest fixture parameters in `python_fixture_params` junction table.

#### Scenario: Fixture params queryable via JOIN
- **WHEN** `extract_pytest_fixtures` produces fixture with params `['db', 'cache']`
- **THEN** two rows are inserted into `python_fixture_params`
- **AND** each row contains param_name and fixture_id foreign key

#### Scenario: Find fixtures with specific dependency
- **WHEN** querying for fixtures that depend on 'db'
- **THEN** JOIN on `python_fixture_params WHERE param_name = 'db'` returns matching fixtures

---

### Requirement: Schema Validators Junction Table

The system SHALL store validation schema validators in `python_schema_validators` junction table.

#### Scenario: Validators queryable via JOIN
- **WHEN** `extract_marshmallow_schemas` produces validators `['validate_email', 'validate_phone']`
- **THEN** two rows are inserted into `python_schema_validators`
- **AND** each row contains validator_name and schema_id foreign key

#### Scenario: Find schemas using validator
- **WHEN** querying for schemas using 'validate_email'
- **THEN** JOIN on `python_schema_validators WHERE validator_name = 'validate_email'` returns matching schemas

---

### Requirement: Framework Methods Junction Table

The system SHALL store framework config methods in `python_framework_methods` junction table.

#### Scenario: Framework methods queryable via JOIN
- **WHEN** `extract_django_middleware` produces methods `['process_request', 'process_response']`
- **THEN** two rows are inserted into `python_framework_methods`
- **AND** each row contains method_name and config_id foreign key

#### Scenario: Find framework configs by method
- **WHEN** querying for middleware implementing 'process_exception'
- **THEN** JOIN on `python_framework_methods WHERE method_name = 'process_exception'` returns matching configs

---

### Requirement: No JSON Blob Columns

The system SHALL NOT store JSON arrays or objects in TEXT columns.

#### Scenario: Implemented methods not stored as JSON
- **WHEN** inspecting `python_protocols` table
- **THEN** `implemented_methods` column does NOT exist
- **AND** method data is in `python_protocol_methods` junction table

#### Scenario: TypedDict fields not stored as JSON
- **WHEN** inspecting `python_type_definitions` table
- **THEN** `fields` column does NOT exist
- **AND** field data is in `python_typeddict_fields` junction table

#### Scenario: Bounded arrays use expanded columns
- **WHEN** an array has known maximum cardinality (e.g., type_params max 5)
- **THEN** individual columns exist: type_param_1, type_param_2, ..., type_param_5
- **AND** no JSON blob column exists

#### Scenario: Schema validation rejects JSON columns
- **WHEN** `test_no_json_blob_columns()` runs
- **THEN** no Python table has columns with JSON in description
- **AND** no Python table has columns with '[]' or '{}' defaults

---

### Requirement: Junction Table Database Methods

The system SHALL provide `add_python_*` methods for each junction table.

#### Scenario: Protocol methods insert method exists
- **WHEN** storage needs to insert a protocol method
- **THEN** `db_manager.add_python_protocol_method(file, protocol_id, method_name, method_order)` exists

#### Scenario: TypedDict fields insert method exists
- **WHEN** storage needs to insert a TypedDict field
- **THEN** `db_manager.add_python_typeddict_field(file, typeddict_id, field_name, field_type, required, field_order)` exists

#### Scenario: Junction table methods return inserted row ID
- **WHEN** `add_python_protocol_method()` is called
- **THEN** method returns the auto-generated row ID
- **AND** ID can be used for subsequent related inserts

---

### Requirement: Parent Table Methods Return Row IDs

The system SHALL ensure parent table `add_*` methods return the inserted row ID for FK reference.

#### Scenario: Parent methods use direct cursor execute
- **WHEN** `add_python_protocol()` is called
- **THEN** method uses `cursor.execute()` directly (NOT batch append pattern)
- **AND** method returns `cursor.lastrowid`

#### Scenario: Batch pattern NOT used for junction parents
- **WHEN** a parent table has a junction table child
- **THEN** the parent's `add_*` method does NOT use `self.generic_batches.append()`
- **BECAUSE** batch pattern does not return row IDs needed for FK population

#### Scenario: Storage handler captures parent ID before junction insert
- **WHEN** storage handler processes a record with junction data
- **THEN** handler calls parent `add_*` method FIRST
- **AND** handler captures the returned row ID
- **AND** handler passes row ID as FK to junction `add_*` method

**Implementation Reference:** See `appendix-implementation.md` Section 5.2 for complete code pattern.
