## ADDED Requirements

### Requirement: Persist Coverage Metrics in SQLite
Coverage analysis MUST store per-file coverage percentages and uncovered line facts in normalized tables so downstream consumers query the database instead of JSON blobs.

#### Scenario: Coverage summary rows written during metadata analyze
- **GIVEN** a repository with a valid coverage report
- **WHEN** `aud metadata analyze` (or the coverage subcommand) completes
- **THEN** `test_coverage_summary` contains one row per file with normalized coverage percentage, counts, and analysis timestamp
- **AND** the data is accessible via `sqlite3` queries without reading `.pf/raw/coverage_analysis.json`

#### Scenario: Uncovered lines tracked for per-line lookups
- **GIVEN** coverage data includes uncovered lines
- **WHEN** coverage collection finishes
- **THEN** `test_coverage_gaps` records each uncovered line keyed by file
- **AND** repeat runs replace prior rows so lookups remain current

### Requirement: Compute Coverage-Aware Risk Scores
Risk scoring MUST combine normalized severity with coverage facts to produce deterministic risk values for every finding.

#### Scenario: Risk command persists severity-weighted scores
- **GIVEN** `findings_consolidated` contains findings and coverage tables are populated
- **WHEN** `aud prioritize` runs
- **THEN** each finding receives a risk record keyed by `findings_consolidated.id` with severity weight, coverage ratio, and calculated `risk_score`
- **AND** the risk table updates in place so re-runs refresh existing rows

#### Scenario: Missing coverage defaults to zero coverage
- **GIVEN** a finding with no matching coverage summary
- **WHEN** `aud prioritize` computes its risk
- **THEN** the coverage ratio stored with the risk record is `0.0`
- **AND** the risk score equals the severity weight (highest possible risk for that severity)

### Requirement: Publish Prioritized Outputs
The prioritization stage MUST expose sorted results via both SQLite and JSON for downstream automation.

#### Scenario: Prioritized JSON emitted for AI consumption
- **GIVEN** `aud prioritize` completes successfully
- **WHEN** the command exits
- **THEN** `.pf/raw/prioritized_findings.json` exists and lists findings sorted by descending `risk_score`, including coverage context

#### Scenario: FCE surfaces risk metadata and ordering
- **GIVEN** risk scores exist in the database
- **WHEN** `aud fce` composes `results["all_findings"]`
- **THEN** each finding entry contains `risk_score` and coverage metadata
- **AND** the list is ordered by risk score (severity used only as a tie-breaker)

### Requirement: Generate AI-Sized Prioritized Summaries
Summaries MUST give copilots an immediate prioritized view without exceeding the target context size.

#### Scenario: Combined summary constrained to ≤100 KB
- **GIVEN** the full pipeline completes
- **WHEN** `aud summary` runs
- **THEN** `.pf/readthis/summary_prioritized_*.json` (maximum two files) contain the combined prioritized overview, each file ≤100 KB
- **AND** the documents list top findings ordered by risk score with references back to the database artifacts

#### Scenario: Per-track capsules highlight top risks
- **GIVEN** risk scores span multiple analyzers (lint, taint, graph, etc.)
- **WHEN** `aud summary` completes
- **THEN** separate summary capsules (e.g., `summary_lint.json`, `summary_taint.json`) are written under `.pf/readthis/`
- **AND** each capsule includes the top N risk-ranked findings for that track with pointers to full records
