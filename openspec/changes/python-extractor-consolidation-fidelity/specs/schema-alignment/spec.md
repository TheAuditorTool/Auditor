# Schema Alignment Specification

## ADDED Requirements

### Requirement: Two-Discriminator Pattern

The system SHALL use two columns per consolidated table: a kind column (table discriminator) and a type column (extractor subtype).

#### Scenario: Loop table preserves extractor subtype
- **WHEN** `extract_for_loops` produces a record with `loop_type='enumerate'`
- **THEN** storage adds `loop_kind='for'` (discriminator)
- **AND** `loop_type='enumerate'` is preserved (not overwritten)

#### Scenario: Query by kind returns all variants
- **WHEN** querying `SELECT * FROM python_loops WHERE loop_kind='for'`
- **THEN** results include all for loops regardless of `loop_type` subtype

#### Scenario: Query by type returns specific pattern
- **WHEN** querying `SELECT * FROM python_loops WHERE loop_type='enumerate'`
- **THEN** results include only enumerate-style for loops

#### Scenario: Two-discriminator applies to all consolidated tables
- **WHEN** inspecting consolidated Python tables
- **THEN** each has both `*_kind` and `*_type` columns
- **AND** kind column is NOT NULL (discriminator)
- **AND** type column is nullable (subtype may not exist)

---

### Requirement: Expression Table Decomposition

The system SHALL split `python_expressions` into logical subtables and re-route misplaced extractors.

#### Scenario: Comprehensions stored in dedicated table
- **WHEN** `extract_comprehensions` produces data
- **THEN** records are stored in `python_comprehensions` table
- **AND** `comp_kind` discriminator is set based on comprehension type

#### Scenario: Control statements stored in dedicated table
- **WHEN** `extract_break_continue_pass`, `extract_assert_statements`, `extract_del_statements`, or `extract_with_statements` produces data
- **THEN** records are stored in `python_control_statements` table
- **AND** `statement_kind` discriminator identifies the statement type

#### Scenario: Copy protocol re-routed to protocols table
- **WHEN** `extract_copy_protocol` produces data
- **THEN** records are stored in `python_protocols` with `protocol_kind='copy'`
- **AND** NOT stored in `python_expressions`

#### Scenario: Recursion patterns re-routed to functions table
- **WHEN** `extract_recursion_patterns` produces data
- **THEN** records are stored in `python_functions_advanced` with `function_kind='recursive'`
- **AND** NOT stored in `python_expressions`

#### Scenario: Memoization patterns re-routed to functions table
- **WHEN** `extract_memoization_patterns` produces data
- **THEN** records are stored in `python_functions_advanced` with `function_kind='memoized'`
- **AND** NOT stored in `python_expressions`

#### Scenario: Loop complexity re-routed to loops table
- **WHEN** `extract_loop_complexity` produces data
- **THEN** records are stored in `python_loops` with `loop_kind='complexity_analysis'`
- **AND** NOT stored in `python_expressions`

#### Scenario: Reduced expressions table has acceptable sparsity
- **WHEN** analyzing `python_expressions` after decomposition
- **THEN** remaining extractors produce max 50% NULL columns per row
- **AND** column count is approximately 25 (reduced from 55)

---

### Requirement: Schema Columns Match Extractor Output

The system SHALL ensure every schema column corresponds to actual extractor output keys.

#### Scenario: No invented columns in python_loops
- **WHEN** inspecting `python_loops` schema
- **THEN** columns match extractor truth: loop_kind, loop_type, has_else, in_function, nesting_level, target_count, is_infinite, estimated_complexity, has_growing_operation
- **AND** no columns exist that extractors don't output (e.g., 'target', 'iterator', 'body_line_count' are REMOVED)

#### Scenario: No invented columns in python_branches
- **WHEN** inspecting `python_branches` schema
- **THEN** columns match extractor truth for if/match/try/except/finally/raise extractors
- **AND** 'condition' column is REMOVED (invented)

#### Scenario: No invented columns in python_io_operations
- **WHEN** inspecting `python_io_operations` schema
- **THEN** columns match extractor truth: io_kind, io_type, operation, target, is_static, in_function
- **AND** 'is_taint_source' and 'is_taint_sink' are REMOVED (invented)

#### Scenario: Column types match extractor output types
- **WHEN** extractor outputs boolean field (e.g., `has_else`)
- **THEN** schema column is INTEGER (SQLite boolean)
- **AND** storage converts Python bool to 0/1

---

### Requirement: Wire All Extractors with Data

The system SHALL wire all extractors that produce data to appropriate tables.

#### Scenario: Python exports wired to imports table
- **WHEN** `extract_python_exports` produces data
- **THEN** records are stored in `python_imports_advanced` with `import_kind='export'`

#### Scenario: Flask blueprints wired to framework config
- **WHEN** `extract_flask_blueprints` produces data
- **THEN** records are stored in `python_framework_config` with `framework='flask', config_kind='blueprint'`

#### Scenario: Celery tasks wired to framework config
- **WHEN** `extract_celery_tasks` produces data
- **THEN** records are stored in `python_framework_config` with `framework='celery', config_kind='task'`

#### Scenario: GraphQL resolvers wired to framework config
- **WHEN** `extract_graphene_resolvers`, `extract_ariadne_resolvers`, or `extract_strawberry_resolvers` produces data
- **THEN** records are stored in `python_framework_config` with appropriate `framework` and `config_kind='resolver'`

---

## MODIFIED Requirements

### Requirement: Schema Table Count

The system SHALL maintain exactly 136 tables total (129 original + 5 junction + 2 expression split).

#### Scenario: Schema assertion passes
- **WHEN** `theauditor.indexer.schema` module loads
- **THEN** `len(TABLES) == 136`

#### Scenario: Python table count accurate
- **WHEN** `theauditor.indexer.schemas.python_schema` module loads
- **THEN** `len(PYTHON_TABLES) == 30` (28 current + 2 new)

### Requirement: Storage Handler Count

The system SHALL provide storage handlers for all Python tables.

#### Scenario: Handler count matches table count
- **WHEN** PythonStorage is instantiated
- **THEN** `len(ps.handlers) == 32` (27 current + 5 new)
