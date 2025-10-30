# Spec Delta: Indexer Schema Architecture

**Capability**: indexer-schema
**Change**: refactor-schema-language-split
**Type**: Internal Architecture Refactor

## MODIFIED Requirements

### Requirement: Schema Module Organization

The database schema definitions SHALL be organized into language-specific modules while maintaining 100% backward compatibility.

**Previous Implementation**: Single monolithic `schema.py` file (2146 lines) containing all 70 table definitions.

**New Implementation**: Modular schema organization:
- `schema.py` - Stub entry point that merges all sub-modules
- `schemas/utils.py` - Column, ForeignKey, TableSchema classes
- `schemas/core_schema.py` - 26 core tables used by all languages
- `schemas/python_schema.py` - 5 Python-specific tables
- `schemas/node_schema.py` - 22 Node/JS-specific tables
- `schemas/infrastructure_schema.py` - 12 infrastructure tables
- `schemas/planning_schema.py` - 5 planning tables

**Rationale**: Improves maintainability, discoverability, and separation of concerns for 70+ table schema definitions.

#### Scenario: Import backward compatibility maintained

- **GIVEN** a consumer module imports from `theauditor.indexer.schema`
- **WHEN** the consumer imports `TABLES`, `build_query`, `Column`, or other symbols
- **THEN** all imports SHALL work identically to pre-refactor behavior
- **AND** all 70 tables SHALL be accessible via the `TABLES` registry
- **AND** zero code changes SHALL be required in consumer modules

#### Scenario: Language-specific schema isolation

- **GIVEN** a developer needs to add a Python-specific table
- **WHEN** the developer opens `theauditor/indexer/schemas/python_schema.py`
- **THEN** the file SHALL contain ONLY Python-specific tables (5 tables)
- **AND** the developer SHALL NOT see unrelated Node/React/Vue/Infrastructure tables
- **AND** the new table SHALL automatically merge into the global `TABLES` registry via stub

#### Scenario: Core schema shared across languages

- **GIVEN** a table is used by both Python AND Node extractors
- **WHEN** the table is categorized during refactor
- **THEN** the table SHALL be placed in `schemas/core_schema.py`
- **AND** both Python and Node extractors SHALL access the table identically
- **EXAMPLE**: `sql_queries` table used by SQLAlchemy (Python) and Sequelize (Node)

#### Scenario: Schema contract validation passes

- **GIVEN** the schema refactor is complete
- **WHEN** the schema contract tests run (`pytest tests/test_schema_contract.py`)
- **THEN** all table schemas SHALL validate successfully
- **AND** all 70 tables SHALL be present in the `TABLES` registry
- **AND** no schema mismatches SHALL be detected

#### Scenario: Database operations unchanged

- **GIVEN** database.py uses the schema module
- **WHEN** database operations execute (create_schema, flush_batch, add_* methods)
- **THEN** all operations SHALL work identically to pre-refactor behavior
- **AND** no database.py code changes SHALL be required (Phase 1)
- **AND** all batch inserts SHALL use the correct table schemas

### Requirement: Query Builder Functionality Preserved

The query builder utilities (build_query, build_join_query, validate_all_tables) SHALL remain functionally identical after schema modularization.

#### Scenario: Build query with schema-driven column validation

- **GIVEN** a rule needs to query the `symbols` table
- **WHEN** the rule calls `build_query('symbols', ['path', 'name', 'type'])`
- **THEN** the query builder SHALL validate columns exist in schema
- **AND** the query builder SHALL return `"SELECT path, name, type FROM symbols"`
- **AND** the behavior SHALL be identical to pre-refactor implementation

#### Scenario: Schema validation detects mismatches

- **GIVEN** the database is created from schema definitions
- **WHEN** `validate_all_tables(cursor)` is called
- **THEN** the validator SHALL check all 70 tables against actual database
- **AND** the validator SHALL report any column type mismatches
- **AND** the validation logic SHALL be unchanged from pre-refactor

## Notes

**Breaking Changes**: NONE - This is a pure architectural refactor with 100% backward compatibility.

**Testing**: All existing schema contract tests (`test_schema_contract.py`, `test_database_integration.py`) MUST pass without modification.

**Consumer Impact**: Zero - All 50 consumer files (rules, taint, commands, extractors) continue to import from `theauditor.indexer.schema` with no code changes.

**Future Work**: Phase 2 will apply same modular pattern to `database.py` (1407 lines) to split `add_*` methods by language (separate proposal).
