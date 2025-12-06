# Data Fidelity Control Specification

## ADDED Requirements

### Requirement: Extraction Manifest Generation

The system SHALL generate an extraction manifest containing the count of records produced by each extractor group.

#### Scenario: Manifest generated during Python extraction
- **WHEN** `python_impl.py` completes extraction for a file
- **THEN** `result['_extraction_manifest']` contains a dict mapping table names to record counts
- **AND** the manifest includes `_total`, `_timestamp`, `_file`, and `_extractor_version` metadata

#### Scenario: Manifest counts match result dict lengths
- **WHEN** extraction produces 156 records for `python_loops`
- **THEN** `result['_extraction_manifest']['python_loops'] == 156`

#### Scenario: Manifest includes all 30 Python tables
- **WHEN** extraction manifest is generated
- **THEN** all 30 Python table keys are present in the manifest
- **AND** tables with no data have count 0

---

### Requirement: Storage Receipt Generation

The system SHALL generate a storage receipt containing the count of records actually stored in each table.

#### Scenario: Receipt generated during Python storage
- **WHEN** `python_storage.py` completes storage for a file
- **THEN** the `store()` method returns a dict mapping table names to rows inserted

#### Scenario: Receipt counts match database insertions
- **WHEN** storage handler inserts 156 rows into `python_loops`
- **THEN** `receipt['python_loops'] == 156`

#### Scenario: Receipt includes error and warning counts
- **WHEN** storage completes
- **THEN** receipt includes `_errors` and `_warnings` counts

---

### Requirement: Fidelity Reconciliation Check

The system SHALL compare extraction manifest to storage receipt and CRASH if data was extracted but not stored.

#### Scenario: Reconciliation passes when counts match
- **WHEN** `reconcile_fidelity(manifest, receipt)` is called
- **AND** all table counts match between manifest and receipt
- **THEN** reconciliation returns status 'OK'
- **AND** no exception is raised

#### Scenario: Reconciliation crashes on zero-store data loss
- **WHEN** manifest shows `python_loops: 156`
- **AND** receipt shows `python_loops: 0`
- **THEN** `DataFidelityError` is raised
- **AND** error message includes table name and counts

#### Scenario: Reconciliation warns on partial data loss
- **WHEN** manifest shows `python_loops: 156`
- **AND** receipt shows `python_loops: 150`
- **THEN** reconciliation returns status 'WARNING'
- **AND** warning message includes delta (6 rows lost)

#### Scenario: Reconciliation integrated into orchestrator
- **WHEN** Python file indexing completes
- **THEN** orchestrator calls `reconcile_fidelity()` with manifest and receipt
- **AND** pipeline halts if `DataFidelityError` is raised

---

### Requirement: DataFidelityError Exception

The system SHALL provide a `DataFidelityError` exception class for fidelity check failures.

#### Scenario: Exception raised with descriptive message
- **WHEN** `DataFidelityError` is raised
- **THEN** exception message includes all tables with zero-store issues
- **AND** exception message includes extracted and stored counts

#### Scenario: Exception is catchable for reporting
- **WHEN** `DataFidelityError` is raised in orchestrator
- **THEN** exception can be caught for logging before re-raising
- **AND** full reconciliation report is available

---

### Requirement: Schema Contract CI Test

The system SHALL include CI tests that verify schema columns match extractor outputs.

#### Scenario: Test detects missing schema columns
- **WHEN** an extractor outputs a key not in the schema
- **THEN** `test_extractor_keys_match_schema_columns()` fails
- **AND** test message identifies the extractor and missing column

#### Scenario: Test detects unmapped extractors
- **WHEN** an extractor has no table mapping
- **THEN** `test_all_extractor_outputs_have_tables()` fails
- **AND** test message identifies the unmapped extractor

#### Scenario: Test detects JSON blob columns
- **WHEN** a schema column description mentions JSON
- **OR** a schema column has JSON-like default ('[]', '{}')
- **THEN** `test_no_json_blob_columns()` fails
- **AND** test message identifies the JSON blob column
