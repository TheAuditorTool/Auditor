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

---

### Requirement: Polyglot Manifest Generation Parity

The fidelity control system SHALL ensure Python and Node extractors generate manifests with equivalent integrity guarantees.

#### Scenario: Python extractor generates manifest at source
- **WHEN** Python extractor (`python_impl.py`) completes extraction
- **THEN** `result['_extraction_manifest']` is generated BY the extractor
- **AND** manifest reflects what Python INTENDED to extract
- **AND** fidelity catches any data loss between extractor and storage

#### Scenario: Node extractor generates manifest at source (Phase 5)
- **WHEN** Node extractor (TypeScript bundle) completes extraction
- **THEN** `result['_extraction_manifest']` is generated INSIDE Node
- **AND** manifest reflects what Node INTENDED to extract
- **AND** manifest is passed through by Python orchestrator (not rebuilt)
- **AND** fidelity catches any data loss between Node and storage

#### Scenario: Python orchestrator detects Node-generated manifest
- **WHEN** Node extraction output contains `_extraction_manifest`
- **AND** manifest values are dict format (not int)
- **AND** manifest values contain `tx_id` key
- **THEN** Python orchestrator passes through Node's manifest
- **AND** orchestrator does NOT rebuild manifest from Node output
- **AND** log indicates "Using Node-generated manifest"

#### Scenario: Interim compatibility for pre-Phase-5 Node output (DEPRECATED after Phase 5)
- **WHEN** Node extraction output does NOT contain `_extraction_manifest`
- **OR** manifest values are int format (legacy)
- **THEN** Python orchestrator builds manifest from Node output
- **AND** log indicates "Building manifest from Node output (legacy) - upgrade to Phase 5"
- **AND** this provides PARTIAL fidelity (cannot catch Node-internal loss)
- **NOTE**: This interim behavior SHALL be removed after Phase 5 completion. It exists only for backward compatibility during the rollout period.

---

### Requirement: Node Manifest Format Compatibility

Node-generated manifests SHALL match Python manifest format exactly for interoperability.

#### Scenario: Node manifest token structure
- **WHEN** Node generates a manifest token for a table
- **THEN** token contains `tx_id` (UUID string)
- **AND** token contains `columns` (sorted array of column names)
- **AND** token contains `count` (integer row count)
- **AND** token contains `bytes` (approximate data volume)

#### Scenario: Node manifest metadata
- **WHEN** Node generates `_extraction_manifest`
- **THEN** Python orchestrator adds `_total` (sum of all counts)
- **AND** Python orchestrator adds `_timestamp` (ISO format)
- **AND** Python orchestrator adds `_file` (source file path)

#### Scenario: Zod validation before manifest (recommended)
- **WHEN** Node extractor uses Zod schema validation
- **THEN** extraction output is validated BEFORE manifest generation
- **AND** invalid data throws error with stack trace inside Node
- **AND** Python never receives malformed data

---

### Requirement: Logging Integration

The fidelity control system SHALL integrate with the unified logging infrastructure.

#### Scenario: Python fidelity uses Loguru
- **WHEN** `reconcile_fidelity()` logs a warning or error
- **THEN** logging uses `from theauditor.utils.logging import logger`
- **AND** logs include `request_id` for correlation

#### Scenario: Node fidelity uses Pino
- **WHEN** Node manifest generation logs debug info
- **THEN** logging uses `import { logger } from './utils/logger'`
- **AND** logs go to stderr (not stdout)
- **AND** logs include `request_id` from environment

#### Scenario: Rich displays fidelity errors
- **WHEN** `DataFidelityError` is raised during pipeline execution
- **AND** Rich Live display is active
- **THEN** error renders correctly via `swap_to_rich_sink()` integration
- **AND** error message is visible above Live display

---

### Requirement: TypeScript Bundle Architecture Dependency

Phase 5 (Node-side manifest generation) SHALL require the TypeScript bundle architecture to be operational.

The system SHALL verify bundle existence before Phase 5 implementation begins.

#### Scenario: Bundle exists before Phase 5 work
- **WHEN** implementer begins Phase 5 implementation
- **THEN** `ast_extractors/javascript/dist/extractor.cjs` SHALL exist
- **AND** `ast_extractors/javascript/src/main.ts` SHALL be the entry point
- **AND** Zod validation SHALL exist in `src/schema.ts`
- **AND** Pino logging SHALL exist in `src/utils/logger.ts`

#### Scenario: TypeScript build process validates changes
- **WHEN** implementer modifies `src/fidelity.ts` or `src/main.ts`
- **THEN** `npm run typecheck` SHALL validate types before build
- **AND** `npm run build` SHALL produce updated `dist/extractor.cjs`
- **AND** `js_build_guard.py` SHALL detect source changes on next `aud full`
