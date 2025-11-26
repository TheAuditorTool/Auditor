## ADDED Requirements

### Requirement: Node.js Extraction Manifest Generation

The JavaScript extractor SHALL generate an `_extraction_manifest` dictionary containing counts of all extracted data items before returning results.

The manifest SHALL include:
- A count for each data type key that has non-empty list values
- A `_total` field with the sum of all counts
- A `_timestamp` field with ISO format UTC timestamp
- A `_file` field with the source file path

#### Scenario: Manifest generated for JavaScript file
- **WHEN** `javascript.py` extracts data from a `.js` or `.ts` file
- **THEN** the result dictionary contains `_extraction_manifest` key
- **AND** manifest contains counts matching the extracted data lists

#### Scenario: Empty extraction produces minimal manifest
- **WHEN** extraction finds no data (empty file or binary)
- **THEN** manifest contains `_total: 0` and timestamp metadata

### Requirement: Node.js Storage Handlers Use Batched Methods

All Node.js storage handlers SHALL call `db_manager.add_*()` methods instead of direct `cursor.execute()` calls.

The following 9 handlers SHALL be migrated to use batched methods:
- `_store_sequelize_models` -> `add_sequelize_model()`
- `_store_sequelize_associations` -> `add_sequelize_association()`
- `_store_bullmq_queues` -> `add_bullmq_queue()`
- `_store_bullmq_workers` -> `add_bullmq_worker()`
- `_store_angular_components` -> `add_angular_component()`
- `_store_angular_services` -> `add_angular_service()`
- `_store_angular_modules` -> `add_angular_module()`
- `_store_angular_guards` -> `add_angular_guard()`
- `_store_di_injections` -> `add_di_injection()`

#### Scenario: Sequelize model stored via batched method
- **WHEN** `_store_sequelize_models` handler processes a model
- **THEN** it calls `db_manager.add_sequelize_model()` with correct parameters
- **AND** no direct `cursor.execute()` calls are made

#### Scenario: Angular component stored via batched method
- **WHEN** `_store_angular_components` handler processes a component
- **THEN** it calls `db_manager.add_angular_component()` with correct parameters
- **AND** no direct `cursor.execute()` calls are made

### Requirement: Node.js Database Methods Use Generic Batches

The `NodeDatabaseMixin` SHALL provide 9 additional `add_*()` methods for tables currently using direct SQL.

Each method SHALL:
1. Accept parameters matching the table schema columns
2. Append a tuple to `self.generic_batches[table_name]`
3. NOT execute SQL directly (batching handles that)

#### Scenario: add_sequelize_model uses generic_batches
- **WHEN** `add_sequelize_model()` is called with file, line, model_name, table_name, extends_model
- **THEN** a tuple is appended to `self.generic_batches['sequelize_models']`
- **AND** no direct SQL execution occurs

#### Scenario: add_angular_module uses generic_batches
- **WHEN** `add_angular_module()` is called with file, line, module_name, declarations, imports, providers, exports
- **THEN** a tuple is appended to `self.generic_batches['angular_modules']`
- **AND** no direct SQL execution occurs

## MODIFIED Requirements

### Requirement: Data Fidelity Reconciliation

The indexer orchestrator SHALL call `reconcile_fidelity()` for ALL files (Python AND Node.js) when `_extraction_manifest` is present in extracted data.

The fidelity check SHALL raise `DataFidelityError` when:
- Extracted count > 0 AND stored count = 0 (100% data loss)

**Change:** This requirement now applies to BOTH Python AND Node.js extraction pipelines (previously Python-only).

#### Scenario: Fidelity check runs for TypeScript file
- **WHEN** a `.ts` file is processed with manifest
- **THEN** `reconcile_fidelity()` compares manifest vs receipt
- **AND** DataFidelityError is raised if extracted count != stored count
