## ADDED Requirements

### Requirement: GraphQL Build Runs in Stage 2 of `aud full`
The full pipeline MUST execute a GraphQL build step during Stage 2 so downstream analysis receives resolver graph data.

#### Scenario: Pipeline Stage Order Includes GraphQL
- **GIVEN** a repository with GraphQL artefacts
- **WHEN** `aud full --offline` runs
- **THEN** the Stage 2 log shows `aud graphql build` running after `aud graph build` and before Stage 3 tracks start
- **AND** `.pf/status/graphql_build.status` captures progress telemetry for supervising agents
- **AND** `.pf/raw/graphql_schema.json` and `.pf/raw/graphql_execution.json` exist at the end of Stage 2.

### Requirement: CLI Surfaces GraphQL Commands
The CLI MUST offer help text and subcommands that expose GraphQL build/dump workflows to humans and AI assistants.

#### Scenario: Help Output Documents GraphQL Usage
- **GIVEN** the updated CLI is installed
- **WHEN** running `aud graphql --help`
- **THEN** the command documents the `build`, `analyze`, and `dump` subcommands with notes about required prerequisites (`aud index`) and output locations
- **AND** `aud --help` and README/HOWTOUSE mention the GraphQL workflow alongside other core commands.

### Requirement: Courier Artefacts Remain Truthful
GraphQL outputs MUST follow the Truth Courier contract with provenance and chunking.

#### Scenario: Chunked Outputs Include Provenance
- **GIVEN** `aud graphql build` completes
- **WHEN** inspecting `.pf/readthis/graphql_schema_*.json` and `.pf/readthis/graphql_execution_*.json`
- **THEN** each chunk includes machine-readable provenance (table name + primary key) for every fact and respects courier size limits using the existing chunker.

### Requirement: FCE Ingests GraphQL Findings
GraphQL findings MUST be aggregated into the standard reporting flow without additional manual steps.

#### Scenario: GraphQL Findings in Report Summary
- **GIVEN** GraphQL rules emit findings into `findings_consolidated`
- **WHEN** `aud fce` runs as part of `aud full`
- **THEN** `.pf/raw/report_summary.json` includes a `graphql` section summarising auth/injection/N+1 issues with references back to the originating `graphql_*` tables
- **AND** the consolidated evidence packs written to `.pf/raw/fce_findings.json` list GraphQL findings alongside REST/security results.
