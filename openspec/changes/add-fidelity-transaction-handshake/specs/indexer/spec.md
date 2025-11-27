# indexer Specification - Delta

## ADDED Requirements

### Requirement: Fidelity Reconciliation Check

The system SHALL compare extraction manifest to storage receipt and CRASH if data was extracted but not stored.

The fidelity control system SHALL be invoked by the orchestrator after each file's extraction and storage cycle completes.

#### Scenario: Reconciliation passes when counts match
- **WHEN** `reconcile_fidelity(manifest, receipt)` is called
- **AND** all table counts match between manifest and receipt
- **THEN** reconciliation returns status 'OK'
- **AND** no exception is raised

#### Scenario: Reconciliation crashes on zero-store data loss
- **WHEN** manifest shows `count: 156`
- **AND** receipt shows `count: 0`
- **THEN** `DataFidelityError` is raised
- **AND** error message includes table name and counts

#### Scenario: Reconciliation warns on partial data loss
- **WHEN** manifest shows `count: 156`
- **AND** receipt shows `count: 150`
- **THEN** reconciliation returns status 'WARNING'
- **AND** warning message includes delta (6 rows lost)

#### Scenario: Reconciliation integrated into orchestrator
- **WHEN** file indexing completes
- **THEN** orchestrator calls `reconcile_fidelity()` with manifest and receipt
- **AND** pipeline halts if `DataFidelityError` is raised

---

### Requirement: Transactional Fidelity Token

The fidelity control system SHALL use rich transaction tokens containing identity, topology, and volume metadata instead of simple counts.

The token structure SHALL contain: `tx_id` (UUID string), `columns` (sorted list of column names), `count` (integer), `bytes` (approximate data volume).

#### Scenario: Manifest token generated during extraction
- **WHEN** an extractor completes extraction for a file
- **THEN** `result['_extraction_manifest'][table_name]` contains a dict with keys: `tx_id`, `columns`, `count`, `bytes`
- **AND** `tx_id` is a unique UUID string for this batch
- **AND** `columns` is a sorted list of column names from the first row

#### Scenario: Receipt token generated during storage
- **WHEN** `DataStorer.store()` processes extracted data
- **THEN** the returned receipt contains rich tokens for list-of-dict data types
- **AND** the receipt echoes back the `tx_id` from the corresponding manifest
- **AND** the receipt contains the `columns` actually written to storage
- **AND** the receipt contains a `bytes` field with approximate data volume

#### Scenario: Legacy integer format backward compatible
- **WHEN** a manifest contains simple `{table_name: count}` integer format
- **THEN** `reconcile_fidelity()` auto-upgrades to dict format internally
- **AND** reconciliation proceeds without error

---

### Requirement: Transaction Identity Verification

The fidelity control system SHALL verify that Storage processed the same batch that Extractor sent by comparing transaction IDs.

#### Scenario: Transaction ID match passes
- **WHEN** manifest `tx_id` matches receipt `tx_id` for a table
- **THEN** identity verification passes
- **AND** no error is raised for this check

#### Scenario: Transaction ID mismatch crashes
- **WHEN** manifest `tx_id` is `"abc123"` but receipt `tx_id` is `"xyz789"`
- **THEN** `DataFidelityError` is raised
- **AND** error message includes both transaction IDs
- **AND** error message mentions "pipeline cross-talk or stale buffer"

#### Scenario: Missing transaction ID skips check
- **WHEN** either manifest or receipt `tx_id` is None
- **THEN** identity verification is skipped for that table
- **AND** reconciliation continues with other checks

---

### Requirement: Schema Topology Verification

The fidelity control system SHALL verify that Storage preserved all columns that Extractor found.

#### Scenario: All columns preserved passes
- **WHEN** manifest `columns` is `['id', 'name', 'type']`
- **AND** receipt `columns` is `['id', 'name', 'type']` or a superset
- **THEN** topology verification passes
- **AND** no error is raised for this check

#### Scenario: Column dropped crashes
- **WHEN** manifest `columns` is `['id', 'name', 'type']`
- **AND** receipt `columns` is `['id', 'name']` (missing 'type')
- **THEN** `DataFidelityError` is raised
- **AND** error message identifies dropped columns: `{'type'}`
- **AND** error message indicates "SCHEMA VIOLATION"

#### Scenario: Extra columns in receipt allowed
- **WHEN** manifest `columns` is `['name', 'type']`
- **AND** receipt `columns` is `['id', 'name', 'type', 'created_at']`
- **THEN** topology verification passes
- **AND** no error is raised (Storage may add auto-generated columns)

---

### Requirement: Data Volume Warning

The fidelity control system SHALL warn when data volume collapses significantly despite matching row counts.

#### Scenario: Volume collapse triggers warning
- **WHEN** manifest shows `count: 100, bytes: 50000`
- **AND** receipt shows `count: 100, bytes: 500`
- **AND** the collapse ratio exceeds 90%
- **THEN** a WARNING is logged (not an error)
- **AND** reconciliation continues
- **AND** warning message mentions "Data volume collapsed"

#### Scenario: Small data sets skip volume check
- **WHEN** manifest `bytes` is less than 1000
- **THEN** volume verification is skipped
- **AND** no warning is raised for this check

---

### Requirement: FidelityToken Utility Class

The system SHALL provide a `FidelityToken` utility class for standardized token creation.

#### Scenario: Create manifest from row data
- **WHEN** `FidelityToken.create_manifest(rows)` is called with a list of dicts
- **THEN** return value contains `tx_id`, `columns`, `count`, `bytes`
- **AND** `tx_id` is a new UUID string
- **AND** `columns` is derived from the first row's keys

#### Scenario: Create manifest from empty list
- **WHEN** `FidelityToken.create_manifest([])` is called
- **THEN** return value has `count: 0, columns: [], tx_id: None, bytes: 0`

#### Scenario: Create receipt echoing transaction
- **WHEN** `FidelityToken.create_receipt(count, columns, tx_id, data_bytes)` is called
- **THEN** return value contains the provided values including `bytes`
- **AND** `columns` is sorted for consistent comparison

#### Scenario: Attach manifest helper
- **WHEN** `FidelityToken.attach_manifest(extracted_data)` is called
- **THEN** `extracted_data["_extraction_manifest"]` is populated
- **AND** private keys (starting with `_`) are skipped
- **AND** non-list values are skipped

---

### Requirement: DataFidelityError Exception

The system SHALL provide a `DataFidelityError` exception class for fidelity check failures.

#### Scenario: Exception raised with descriptive message
- **WHEN** `DataFidelityError` is raised
- **THEN** exception message includes all tables with integrity violations
- **AND** exception message includes extracted and stored counts

#### Scenario: Exception is catchable for reporting
- **WHEN** `DataFidelityError` is raised in orchestrator
- **THEN** exception can be caught for logging before re-raising
- **AND** full reconciliation report is available via `details` attribute
