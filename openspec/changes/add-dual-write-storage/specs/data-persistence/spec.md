## ADDED Requirements
### Requirement: Analysis Outputs Persist to Database
All analysis commands MUST store their factual outputs in the project database so downstream tools can operate without relying on `.pf/raw/*.json` files.

#### Scenario: Graph Analysis Dual Write
- **GIVEN** a user runs `aud graph analyze`
- **WHEN** the command completes
- **THEN** the resulting cycles, hotspots, and summary payloads are saved via `XGraphStore.save_analysis_result` in `.pf/graphs.db`
- **AND** FCE loads graph insights from the database even if `graph_analysis.json` is missing

#### Scenario: CFG Analysis Dual Write
- **GIVEN** `aud cfg analyze --complexity-threshold 15`
- **WHEN** the command emits complexity findings
- **THEN** rows are inserted into `cfg_analysis_results` (and `cfg_dead_blocks` when requested)
- **AND** FCE and `aud summary` query those tables before falling back to `.pf/raw/cfg_analysis.json`

#### Scenario: Churn and Coverage Metrics Persisted
- **GIVEN** `aud metadata churn` or `aud metadata coverage` runs successfully
- **WHEN** metrics are produced
- **THEN** per-file results are upserted into `code_churn_metrics` / `coverage_metrics`
- **AND** FCE retrieves churn/coverage data from those tables during correlation

#### Scenario: Dependency Version Checks in DB
- **GIVEN** `aud deps --check-latest` completes
- **WHEN** latest version information is computed
- **THEN** entries are stored in `dependency_version_checks`
- **AND** the `update_lag` rule reads from the table before consulting `deps_latest.json`

#### Scenario: Taint Paths Stored
- **GIVEN** `aud taint-analyze` succeeds
- **WHEN** taint paths are assembled
- **THEN** each path is recorded in `taint_paths` with severity, source, sink, and path metadata
- **AND** summary/insight commands query `taint_paths` for detailed flows

#### Scenario: FCE Correlations Persisted
- **GIVEN** `aud fce` runs to completion
- **WHEN** correlated findings and failures are produced
- **THEN** they are inserted into `fce_correlations` and `fce_failures`
- **AND** the JSON outputs remain as courier copies but consumers can query the database directly

### Requirement: Semantic Context Results in Database
The semantic context engine MUST dual-write its classifications into the database.

#### Scenario: Semantic Context Run
- **GIVEN** `aud context --file semantic_rules/migration.yaml`
- **WHEN** the classification completes
- **THEN** a row is added to `semantic_context_runs` and the classified findings are stored in `semantic_context_classifications`
- **AND** subsequent tooling can query the run without reopening `semantic_context_*.json`

### Requirement: Consumers Prefer Database Facts
Commands that previously consumed `.pf/raw/*.json` MUST read from the database when the dual-write tables exist.

#### Scenario: FCE Database Read Path
- **GIVEN** a repository with up-to-date dual-write tables
- **WHEN** `aud fce` begins correlation
- **THEN** it loads graph, CFG, churn, coverage, taint, and prior correlation facts from the database
- **AND** only falls back to JSON files when tables are missing or empty

#### Scenario: Summary Command Database Read Path
- **GIVEN** `aud summary` runs on a repository with dual-write tables populated
- **WHEN** it assembles the audit summary
- **THEN** it queries the database for dependency updates, coverage, churn, taint, graph, and CFG insights before reading JSON
- **AND** it still supports legacy JSON-only runs for backward compatibility
