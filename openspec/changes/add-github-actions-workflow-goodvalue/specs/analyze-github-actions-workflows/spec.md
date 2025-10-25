
## ADDED Requirements
### Requirement: Workflow Graph Persisted
The indexer MUST detect `.github/workflows/**/*.yml` files and store normalized workflow/job/step metadata in the SQLite manifest.

#### Scenario: Workflow Stored With Dependencies
- **GIVEN** a repository containing `.github/workflows/ci.yml` with two jobs (`setup`, `build`) where `build` needs `setup`
- **WHEN** `aud index` finishes successfully
- **THEN** `.pf/repo_index.db` contains rows in `github_workflows` for `ci.yml`, `github_jobs` for both jobs, and `github_job_dependencies` linking `build` to `setup`
- **AND** each workflow step is inserted into `github_steps` with ordered `sequence_order` values and JSON columns populated for permissions/env/with data
- **AND** step references (e.g., `${{ secrets.GITHUB_TOKEN }}`) are captured in `github_step_references` for downstream analysis

### Requirement: Workflow Export Command
The CLI MUST expose `aud workflows analyze` that emits database-backed JSON capsules and integrates with the full pipeline.

#### Scenario: Pipeline Runs Workflow Analysis
- **GIVEN** `.pf/repo_index.db` already contains GitHub workflow tables
- **WHEN** the user runs `aud workflows analyze` (or `aud full`)
- **THEN** the command writes `.pf/raw/github_workflows.json` summarizing workflows/jobs/steps with provenance metadata referencing the corresponding table rows
- **AND** courier chunking produces `.pf/readthis/github_workflows_*.json` within configured size limits
- **AND** the full pipeline log records a Stage 2 phase named "Analyze GitHub workflows"

### Requirement: Workflow Security Rules
The rules engine MUST surface high-impact GitHub Actions risks using the new tables without resorting to regex heuristics.

#### Scenario: Untrusted Checkout Detection
- **GIVEN** a workflow triggered by `pull_request_target` where a job performs `actions/checkout` of `github.event.pull_request.head.sha` before any validation job
- **WHEN** `aud rules` executes after workflow data exists
- **THEN** a finding with `tool="github-actions-rules"` is written to `findings_consolidated` referencing the risky job/step
- **AND** the finding message cites the workflow file, job id, step id, and the dependency chain that allows untrusted code to run with target-level secrets

### Requirement: Workflow Data Flow Modeling
Workflow outputs and references MUST be modeled so taint analysis and queries can trace data movement across jobs and steps.

#### Scenario: Step Output Tracked Into Run Script
- **GIVEN** job `scan` defines `outputs.result` sourced from PR data and downstream job `deploy` runs a shell script referencing `${{ needs.scan.outputs.result }}`
- **WHEN** taint-aware components query the database
- **THEN** `github_step_outputs` records the `result` output, `github_step_references` records the `${{ needs.scan.outputs.result }}` usage, and rules/taint helpers can treat the reference as a source-to-sink edge without additional parsing

### Requirement: FCE Correlates Workflow Findings
The Factual Correlation Engine MUST ingest workflow findings and include them in correlation clusters.

#### Scenario: Workflow Finding Appears In FCE Output
- **GIVEN** `aud workflows analyze` and `aud rules` have produced workflow risk findings
- **WHEN** `aud fce` runs
- **THEN** `fce.json` contains correlation entries (e.g., `github_workflow_secret_leak`) that merge workflow findings with related taint or dependency evidence
- **AND** the correlation references the originating workflow file/job/step identifiers so agents can trace remediation targets
