## MODIFIED Requirements

### Requirement: JSON Blob Prevention

The database schema SHALL enforce a ZERO JSON policy where all relational data MUST be stored in normalized tables with proper indexes, foreign keys, and type constraints, with explicitly documented exceptions for legitimate JSON storage.

#### Scenario: Schema Load Time Validation
- **GIVEN** the database schema is being loaded
- **WHEN** a table contains a TEXT column ending in '_json', 'dependencies', or 'parameters'
- **AND** the column is not in the LEGITIMATE_EXCEPTIONS list
- **THEN** the schema validator SHALL raise an assertion error preventing schema load

#### Scenario: Finding Data Storage
- **GIVEN** a tool generates finding data with structured metadata
- **WHEN** the finding is written to findings_consolidated
- **THEN** the structured data SHALL be written to normalized junction tables (finding_taint_paths, finding_graph_hotspots, finding_cfg_complexity, finding_metadata)
- **AND** no JSON serialization SHALL occur for relational data

#### Scenario: Symbol Parameter Storage
- **GIVEN** a symbol has function parameters
- **WHEN** the symbol is stored in the database
- **THEN** each parameter SHALL be written as a row in symbol_parameters table
- **AND** the parameters SHALL be retrievable via indexed JOIN queries

## ADDED Requirements

### Requirement: Finding Taint Path Normalization

The system SHALL store taint analysis paths in a normalized finding_taint_paths table with indexed lookups to eliminate JSON parsing overhead.

#### Scenario: Taint Path Storage
- **GIVEN** a taint analysis generates paths from source to sink
- **WHEN** the taint finding is persisted
- **THEN** each path SHALL be stored as a row in finding_taint_paths with path_index preserving order
- **AND** the path SHALL be retrievable in <1ms via indexed query on finding_id

#### Scenario: Taint Path Performance
- **GIVEN** FCE needs to load taint paths for correlation
- **WHEN** querying finding_taint_paths by finding_id
- **THEN** the query SHALL complete in O(log n) time using the composite index
- **AND** no JSON parsing SHALL be required

### Requirement: Finding Graph Hotspot Normalization

The system SHALL store graph analysis hotspots in a normalized finding_graph_hotspots table for efficient correlation.

#### Scenario: Hotspot Storage
- **GIVEN** graph analysis identifies architectural hotspots
- **WHEN** the hotspot finding is persisted
- **THEN** the hotspot data SHALL be stored in finding_graph_hotspots table
- **AND** metrics like in_degree, out_degree, centrality SHALL be queryable columns

### Requirement: Finding CFG Complexity Normalization

The system SHALL store control flow graph complexity metrics in a normalized finding_cfg_complexity table.

#### Scenario: Complexity Storage
- **GIVEN** CFG analysis identifies complex functions
- **WHEN** the complexity finding is persisted
- **THEN** the complexity data SHALL be stored in finding_cfg_complexity table
- **AND** complexity score, loop presence, and block count SHALL be indexed columns

### Requirement: Finding Metadata Normalization

The system SHALL store finding metadata (churn, coverage, CWE/CVE) in a normalized finding_metadata table.

#### Scenario: Metadata Storage
- **GIVEN** analysis tools generate metadata about findings
- **WHEN** the metadata is persisted
- **THEN** churn metrics, coverage percentages, and vulnerability IDs SHALL be stored in finding_metadata
- **AND** metadata SHALL be joinable with findings_consolidated on finding_id

### Requirement: Symbol Parameter Normalization

The system SHALL store function/method parameters in a normalized symbol_parameters table instead of JSON.

#### Scenario: Parameter Extraction
- **GIVEN** a function has parameters with names, types, and defaults
- **WHEN** the symbol is indexed
- **THEN** each parameter SHALL be stored as a row in symbol_parameters
- **AND** param_index SHALL preserve parameter order

#### Scenario: Parameter Query Performance
- **GIVEN** taint analysis needs to check function parameters
- **WHEN** querying symbol_parameters by symbol_id
- **THEN** the query SHALL use indexed lookup instead of JSON parsing
- **AND** parameter types and defaults SHALL be directly filterable

## REMOVED Requirements

### Requirement: JSON Blob Storage for Findings
**Reason**: Performance measurements show 75-700ms overhead from JSON parsing, with taint paths alone causing 50-500ms delays.
**Migration**: All existing findings_consolidated.details_json data will be migrated to normalized junction tables during the next `aud full` reindex.

### Requirement: JSON Array Storage for Symbol Parameters
**Reason**: Causes duplicate parsing in multiple consumers and violates ZERO FALLBACK policy.
**Migration**: All existing symbols.parameters JSON arrays will be migrated to symbol_parameters table during the next `aud full` reindex.