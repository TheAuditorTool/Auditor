## MODIFIED Requirements

### Requirement: Final Status Reporting

The pipeline SHALL report final status after all analysis phases complete, indicating security findings severity.

Final status SHALL be determined by querying the `findings_consolidated` table in the database, NOT by reading JSON files.

#### Scenario: Status reflects findings severity from database
- **WHEN** the pipeline completes all analysis phases
- **THEN** final status SHALL query `findings_consolidated` for severity counts
- **AND** status SHALL NOT read any `.pf/raw/*.json` files
- **AND** status SHALL indicate severity level based on database query results

#### Scenario: Clean status when no security issues in database
- **WHEN** the pipeline completes and `findings_consolidated` has no critical/high security findings
- **THEN** final status SHALL indicate "[CLEAN]"

#### Scenario: Critical status when critical issues in database
- **WHEN** the pipeline completes and `findings_consolidated` has critical severity findings
- **THEN** final status SHALL indicate "[CRITICAL]"
- **AND** exit code SHALL be CRITICAL_SEVERITY

### Requirement: Findings Return Structure

The pipeline SHALL return findings counts in a dict consumed by full.py and journal.py.

Findings counts SHALL be populated from database queries, NOT from JSON file reads.

#### Scenario: Findings dict populated from database
- **WHEN** the pipeline completes
- **THEN** return dict SHALL include findings.critical, findings.high, findings.medium, findings.low
- **AND** counts SHALL be derived from `SELECT severity, COUNT(*) FROM findings_consolidated GROUP BY severity`
- **AND** findings.total_vulnerabilities SHALL count tool='vulnerabilities' rows

## ADDED Requirements

> **NOTE (2025-11-28)**: The first two requirements below (No Readthis, No Report Command) are
> **ALREADY SATISFIED** by previous tickets. They remain documented as acceptance criteria but
> require no implementation work.

### Requirement: No Readthis Directory Generation - ALREADY SATISFIED

The pipeline SHALL NOT create or populate the `.pf/readthis/` directory.

The `.pf/readthis/` directory was designed for AI-optimized chunked output but is obsolete since:
1. AI tools can query the database directly via `aud context query`
2. Chunking logic is fragile and unmaintained
3. The `report` command is DEPRECATED

#### Scenario: Pipeline does not create readthis directory
- **WHEN** `aud full` completes
- **THEN** the pipeline SHALL NOT create `.pf/readthis/` directory
- **AND** the pipeline SHALL NOT write any `*_chunk*.json` files

#### Scenario: Context command does not create readthis chunks
- **WHEN** `aud context` commands run
- **THEN** output SHALL be written to `.pf/raw/` only (if JSON needed)
- **AND** NO files SHALL be written to `.pf/readthis/`

### Requirement: No Report Command - ALREADY SATISFIED

The pipeline SHALL NOT include a `report` command.

The `report` command is DEPRECATED and SHALL be removed entirely.

#### Scenario: Report command not registered
- **WHEN** `aud --help` is displayed
- **THEN** the `report` command SHALL NOT be listed

#### Scenario: Report command invocation fails
- **WHEN** a user runs `aud report`
- **THEN** the command SHALL fail with "No such command 'report'"

### Requirement: Engine JSON Write Removal

Analysis engines that INSERT findings to database SHALL NOT also write JSON files.

Engines affected: vulnerability_scanner, deps, cfg, terraform, docker_analyze, workflows, detect_frameworks.

#### Scenario: Vulnerability scanner writes to database only
- **WHEN** `aud deps --vuln-scan` completes
- **THEN** vulnerabilities SHALL be inserted into `findings_consolidated`
- **AND** NO `.pf/raw/vulnerabilities.json` file SHALL be created

#### Scenario: Workflow analyzer writes to database only
- **WHEN** `aud workflows analyze` completes
- **THEN** workflow findings SHALL be inserted into database tables
- **AND** NO `.pf/raw/github_workflows.json` file SHALL be created

#### Scenario: CFG analyzer writes to database only
- **WHEN** `aud cfg analyze` completes
- **THEN** CFG data SHALL be inserted into `cfg_blocks` and `cfg_edges`
- **AND** NO `.pf/raw/cfg_analysis.json` file SHALL be created

### Requirement: Database-First Pipeline Architecture

The pipeline SHALL follow a database-first architecture where:
1. Extractors INSERT data to normalized tables
2. Analyzers query database for input, INSERT findings to database
3. Reporters query database for output generation
4. NO intermediate JSON files between pipeline stages

#### Scenario: No JSON intermediates between stages
- **WHEN** taint analyzer runs after indexing
- **THEN** taint analyzer SHALL query `repo_index.db` tables for input
- **AND** taint analyzer SHALL INSERT to `taint_flows` for output
- **AND** NO JSON files SHALL be read or written between these stages

#### Scenario: Summary reads from database
- **WHEN** `aud summary` generates executive summary
- **THEN** summary SHALL query `findings_consolidated` for findings
- **AND** summary SHALL query `deps_version_cache` for dependencies
- **AND** summary SHALL NOT read any `.pf/raw/*.json` files
