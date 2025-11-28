# Intelligent Summaries Specification

## ADDED Requirements

### Requirement: Summary Generation Command

The system SHALL provide an `aud summary generate` command that creates AI-optimized summary files from raw analysis output.

#### Scenario: Generate all summaries

- **WHEN** user runs `aud summary generate` after `aud full` completes
- **THEN** the system creates `.pf/summary/` directory
- **AND** generates all 5 summary files:
  - `SAST_Summary.json`
  - `SCA_Summary.json`
  - `Intelligence_Summary.json`
  - `Quick_Start.json`
  - `Query_Guide.json`
- **AND** each file validates against its JSON schema
- **AND** command completes in under 5 seconds for typical codebases

#### Scenario: Missing raw files

- **WHEN** user runs `aud summary generate` without prior `aud full`
- **THEN** the system raises `FileNotFoundError`
- **AND** error message identifies which raw file is missing
- **AND** error message suggests running `aud full` first

#### Scenario: Pipeline integration

- **WHEN** user runs `aud full`
- **THEN** summary generation runs automatically in Stage 4
- **AND** summaries are generated after FCE completes
- **AND** summaries are generated before report generation
- **AND** summary generation failure does NOT block report generation

### Requirement: SAST Summary

The system SHALL generate `SAST_Summary.json` containing aggregated security findings with FCE correlation.

#### Scenario: SAST findings aggregation

- **WHEN** `patterns.json`, `taint.json`, and `github_workflows.json` exist
- **THEN** `SAST_Summary.json` contains:
  - `findings_map` grouped by issue type (e.g., `SQL_INJECTION`, `HARDCODED_SECRET`)
  - Each issue type includes `count`, `affected_files`, `fce_hotspot_overlap`
  - `sample_locations` limited to 3 per issue type
- **AND** `fce_summary.total_correlated` shows count of findings in FCE hotspots

#### Scenario: FCE hotspot correlation

- **WHEN** a finding's file appears in FCE `ARCHITECTURAL_RISK_ESCALATION` meta-finding
- **THEN** that issue type's `fce_hotspot_overlap` is `true`
- **AND** finding contributes to `fce_summary.architectural_risk_count`

### Requirement: SCA Summary

The system SHALL generate `SCA_Summary.json` containing aggregated dependency information.

#### Scenario: Package breakdown

- **WHEN** `deps.json` and `vulnerabilities.json` exist
- **THEN** `SCA_Summary.json` contains:
  - `packages.total` - total package count
  - `packages.direct` - packages in manifest (not transitive)
  - `packages.transitive` - packages installed as dependencies of dependencies
  - `packages.outdated_direct` - direct packages with newer versions
  - `packages.outdated_transitive` - transitive packages with newer versions

#### Scenario: Vulnerability counts

- **WHEN** `vulnerabilities.json` contains vulnerability findings
- **THEN** `packages.vulnerable` object contains counts by severity:
  - `critical`, `high`, `medium`, `low`
- **AND** counts are integers (not strings)

#### Scenario: Framework detection

- **WHEN** `frameworks.json` exists
- **THEN** `frameworks` array contains detected frameworks
- **AND** each framework has `name`, `version`, `category`

### Requirement: Intelligence Summary

The system SHALL generate `Intelligence_Summary.json` containing code health metrics.

#### Scenario: Graph metrics

- **WHEN** `graph_analysis.json` exists
- **THEN** `graph_metrics` contains:
  - `hotspot_count` - files with high connectivity score
  - `cycle_count` - number of circular dependencies
  - `largest_cycle_size` - nodes in largest cycle
  - `top_hotspots` - array of top 5 hotspot files with `in_degree`, `out_degree`, `score`

#### Scenario: CFG metrics

- **WHEN** `cfg_analysis.json` exists
- **THEN** `cfg_metrics` contains:
  - `total_functions_analyzed` - functions with CFG
  - `complex_functions` - functions with cyclomatic complexity > 20
  - `max_complexity` - highest complexity score
  - `avg_complexity` - mean complexity across all functions
  - `top_complex_functions` - array of top 5 with `file`, `function`, `complexity`

#### Scenario: Churn metrics

- **WHEN** `churn_analysis.json` exists
- **THEN** `churn_metrics` contains:
  - `files_analyzed` - files with git history
  - `high_churn_files` - files in 90th percentile of commit frequency
  - `percentile_90_threshold` - commit count threshold for 90th percentile
  - `top_churned_files` - array of top 5 with `file`, `commits_90d`, `unique_authors`

### Requirement: Quick Start Intersection Map

The system SHALL generate `Quick_Start.json` containing files with multiple converging signals.

#### Scenario: Intersection threshold

- **WHEN** generating Quick_Start.json
- **THEN** file is included ONLY if it has signals from 2+ distinct domains
- **AND** domains are: SAST, taint, complexity, churn
- **AND** multiple findings from same domain count as 1 signal

#### Scenario: FCE context population

- **WHEN** a file appears in Quick_Start intersections
- **THEN** `fce_context` contains factual context:
  - `churn_velocity` - "HIGH", "MODERATE", "LOW", or "STAGNANT"
  - `architectural_role` - from graph analysis (e.g., "CORE_COMPONENT")
  - `recent_commit_count` - commits in last 90 days
  - `unique_contributors` - distinct authors
  - `in_cycle` - boolean, true if file is in circular dependency
  - `is_hotspot` - boolean, true if file is graph hotspot

#### Scenario: Locator map precision

- **WHEN** a file has intersecting signals
- **THEN** `locator_map` contains exact locations:
  - `line` - line number in file
  - `signal_source` - domain ("sast_patterns", "taint_paths", etc.)
  - `signal_id` - specific identifier (rule ID, function name)
  - `value_raw` - original value (optional, e.g., complexity score)

#### Scenario: No severity filtering

- **WHEN** generating Quick_Start.json
- **THEN** ALL intersections are included regardless of severity
- **AND** no "critical only" or "high severity" filtering is applied
- **AND** AI consumer decides priority using provided context

### Requirement: Query Guide Reference

The system SHALL generate `Query_Guide.json` as a static reference for database queries.

#### Scenario: Schema map accuracy

- **WHEN** generating Query_Guide.json
- **THEN** `schema_map.tables` reflects actual `repo_index.db` schema
- **AND** column names are read from live database using `PRAGMA table_info()`
- **AND** includes key tables: `symbols`, `refs`, `findings_consolidated`, `taint_paths`

#### Scenario: Tool reference templates

- **WHEN** Query_Guide.json is generated
- **THEN** `tool_reference` contains CLI command templates:
  - `aud explain <target>` - comprehensive context retrieval
  - `aud query --symbol <name>` - symbol lookup
  - `aud context -f <file> -l <line>` - line-level context (if available)

#### Scenario: Investigation workflows

- **WHEN** Query_Guide.json is generated
- **THEN** `investigation_workflows` contains step-by-step patterns:
  - `security_verification` - SAST finding -> context -> FCE check
  - `architectural_risk` - complexity -> imports -> churn
  - `taint_investigation` - taint path -> source -> sink
  - `dependency_vulnerability` - vuln -> imports -> impact
  - `code_churn` - high churn -> authors -> commits

### Requirement: Truth Courier Principle

The system SHALL generate summaries that present facts without interpretation.

#### Scenario: No recommendations

- **WHEN** any summary file is generated
- **THEN** output contains NO recommendation text
- **AND** output contains NO "should", "must", "fix" language
- **AND** output contains NO severity prioritization
- **AND** AI consumer makes all prioritization decisions

#### Scenario: Factual language

- **WHEN** describing findings
- **THEN** use factual language:
  - CORRECT: "5 SQL_INJECTION patterns found in 2 files"
  - INCORRECT: "Critical SQL injection vulnerability needs immediate fix"
- **AND** all counts are exact integers, not qualitative descriptions

#### Scenario: FCE correlation without interpretation

- **WHEN** `fce_hotspot_overlap` or `is_hotspot` is true
- **THEN** this indicates factual correlation with architectural hotspot
- **AND** does NOT imply "this is more important"
- **AND** AI consumer interprets significance based on context

### Requirement: ZERO FALLBACK Policy

The system SHALL fail loudly when required data is missing.

#### Scenario: Missing required file

- **WHEN** generator requires `patterns.json` but file is missing
- **THEN** generator raises `FileNotFoundError`
- **AND** error includes path to missing file
- **AND** generator does NOT return empty data
- **AND** generator does NOT fall back to alternative source

#### Scenario: Partial generation allowed

- **WHEN** one generator fails but others can succeed
- **THEN** orchestrator logs the failure
- **AND** continues with remaining generators
- **AND** returns partial results indicating which summaries failed
- **AND** failed summary file is NOT created (not empty file)

#### Scenario: Database unavailable

- **WHEN** `repo_index.db` is missing for Query_Guide generation
- **THEN** generator raises `FileNotFoundError`
- **AND** does NOT generate Query_Guide with placeholder schema
- **AND** error message identifies database path
