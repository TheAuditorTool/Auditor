# Python Extraction Specification - Delta Changes

## VERIFICATION FINDINGS (2025-11-25)

**Auditor:** Opus Lead Coder

### Critical Finding: Zombie Database Methods

The `python_database.py` file contains ~100 `add_python_*` methods writing to tables that no longer exist. These must be deleted and replaced with 20 new methods for consolidated tables.

### Additional Requirements Identified:

1. **Database Mixin Methods:** 20 new `add_python_*` methods required
2. **Flush Order Update:** 20 new tables must be added to `base_database.py` flush_order
3. **Zombie Cleanup:** ~100 old methods must be deleted

---

## ADDED Requirements

### Requirement: Consolidated Python Tables

The system SHALL provide 20 consolidated tables to store Python extraction patterns, grouped by domain with discriminator columns.

#### Scenario: Control flow patterns stored in consolidated tables
- **WHEN** Python files containing for loops, while loops, and async for loops are indexed
- **THEN** all loop patterns are stored in `python_loops` table with `loop_type` discriminator

#### Scenario: Security patterns stored in consolidated table
- **WHEN** Python files containing SQL injection, command injection, or path traversal patterns are indexed
- **THEN** all security patterns are stored in `python_security_findings` table with `finding_type` discriminator

#### Scenario: Test patterns stored in consolidated table
- **WHEN** Python files containing pytest fixtures, unittest cases, or mock patterns are indexed
- **THEN** fixture patterns are stored in `python_test_fixtures` table with `fixture_type` discriminator
- **AND** test case patterns are stored in `python_test_cases` table with `test_type` discriminator

### Requirement: Database Mixin Methods (NEW - from verification)

The system SHALL provide `add_python_*` methods in `python_database.py` for each consolidated table.

#### Scenario: Mixin method exists for each table
- **WHEN** a storage handler needs to insert a `python_loops` record
- **THEN** `db_manager.add_python_loop(...)` method exists
- **AND** the method appends a tuple to `generic_batches['python_loops']`

#### Scenario: Method parameter order matches schema
- **WHEN** `add_python_loop(file, line, loop_type, ...)` is called
- **THEN** the tuple order matches the `python_loops` table column order exactly

#### Scenario: Mixin method count is correct
- **WHEN** inspecting `PythonDatabaseMixin` methods
- **THEN** exactly 28 `add_python_*` methods exist (8 kept + 20 new)

### Requirement: Flush Order Registration (NEW - from verification)

The system SHALL register all 20 new consolidated tables in `base_database.py` flush_order.

#### Scenario: Tables flushed during batch commit
- **WHEN** `flush_batch()` is called
- **THEN** all 20 new consolidated tables are flushed
- **AND** data is persisted to disk

### Requirement: Extractor Output Mapping

The system SHALL map all extractor outputs to consolidated tables via `python_impl.py`.

#### Scenario: Extractor outputs include discriminator type
- **WHEN** an extractor produces output (e.g., `extract_for_loops`)
- **THEN** the output is enriched with a `loop_type` field before storage
- **AND** the output is appended to the consolidated `python_loops` result key

#### Scenario: All 150 extractor outputs mapped
- **WHEN** `aud full` completes on a Python project
- **THEN** all extractor outputs are stored in one of the 28 Python tables (8 kept + 20 new consolidated)

### Requirement: Storage Handlers for Consolidated Tables

The system SHALL provide storage handlers for each consolidated table in `python_storage.py`.

#### Scenario: Handler stores discriminated data
- **WHEN** `python_loops` data is passed to storage
- **THEN** the handler calls `db_manager.add_python_loop(...)` for each record
- **AND** rows contain file, line, loop_type, and domain-specific columns

#### Scenario: Handler count matches table count
- **WHEN** PythonStorage is instantiated
- **THEN** `len(ps.handlers) == 27` (7 original + 20 new)

## MODIFIED Requirements

### Requirement: Schema Table Count

The system SHALL maintain exactly 129 tables (109 original + 20 new consolidated).

#### Scenario: Schema assertion passes
- **WHEN** `theauditor.indexer.schema` module loads
- **THEN** `len(TABLES) == 129`

#### Scenario: Python table count accurate
- **WHEN** `theauditor.indexer.schemas.python_schema` module loads
- **THEN** `len(PYTHON_TABLES) == 28`

## CLEANUP Requirements (NEW - from verification)

### Requirement: Remove Zombie Database Methods

The system SHALL NOT contain `add_python_*` methods for tables that no longer exist.

#### Scenario: No orphan methods
- **WHEN** inspecting `PythonDatabaseMixin` methods
- **THEN** no method writes to a table not in `PYTHON_TABLES`
- **AND** methods like `add_python_flask_app`, `add_python_for_loop` do NOT exist
