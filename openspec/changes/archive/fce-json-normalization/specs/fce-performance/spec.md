## ADDED Requirements

### Requirement: FCE Sub-10ms Data Loading

The Findings Consolidation Engine SHALL load all finding metadata with less than 10ms total overhead by using indexed database queries instead of JSON parsing.

#### Scenario: Loading Taint Paths
- **GIVEN** FCE needs to load taint analysis paths
- **WHEN** querying finding_taint_paths table
- **THEN** the query SHALL complete in <1ms using indexed lookup
- **AND** no JSON deserialization SHALL occur

#### Scenario: Loading Graph Hotspots
- **GIVEN** FCE needs to load architectural hotspot data
- **WHEN** querying finding_graph_hotspots table
- **THEN** the query SHALL complete in <1ms using indexed lookup
- **AND** hotspot metrics SHALL be directly accessible as columns

#### Scenario: Loading CFG Complexity
- **GIVEN** FCE needs to load function complexity metrics
- **WHEN** querying finding_cfg_complexity table
- **THEN** the query SHALL complete in <1ms using indexed lookup
- **AND** complexity scores SHALL be directly filterable

#### Scenario: Loading Metadata
- **GIVEN** FCE needs to load finding metadata (churn, coverage, CWE)
- **WHEN** querying finding_metadata table
- **THEN** the query SHALL complete in <1ms using indexed lookup
- **AND** metadata SHALL be joinable with findings_consolidated

### Requirement: FCE Database Connection Pooling

The FCE SHALL use a single shared database connection or connection pool to eliminate the overhead of opening 8 separate connections.

#### Scenario: Connection Reuse
- **GIVEN** FCE needs to query multiple tables
- **WHEN** executing database operations
- **THEN** all queries SHALL reuse the same connection or pool
- **AND** connection overhead SHALL be <5ms total

## MODIFIED Requirements

### Requirement: FCE Performance Targets

The FCE SHALL complete all data loading and correlation operations with the following performance targets:
- Database query overhead: <10ms total (was 75-700ms with JSON)
- Taint path loading: <1ms per finding (was 50-500ms with JSON)
- Total FCE execution: <1000ms for codebases under 100K LOC
- Memory usage: <100MB for finding data (no JSON string duplication)

#### Scenario: Performance Validation
- **GIVEN** a codebase with 1000+ taint findings
- **WHEN** running FCE correlation
- **THEN** total JSON parsing time SHALL be 0ms
- **AND** database query time SHALL be <10ms total
- **AND** the performance improvement SHALL be measurable via cProfile

#### Scenario: Large Taint Path Handling
- **GIVEN** a taint path with 100+ intermediate steps
- **WHEN** FCE loads the path from finding_taint_paths
- **THEN** the indexed query SHALL complete in <1ms
- **AND** path ordering SHALL be preserved via path_index column

## REMOVED Requirements

### Requirement: JSON Deserialization Performance Tolerance
**Reason**: JSON parsing overhead of 75-700ms is unacceptable for a performance-critical path.
**Migration**: All JSON deserialization replaced with indexed JOIN queries completing in <1ms.