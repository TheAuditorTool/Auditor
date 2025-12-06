## ADDED Requirements

### Requirement: Stdout-Only JSON Output

All CLI commands that produce structured analysis data SHALL output JSON to stdout via `--json` flag. The system SHALL NOT write JSON files to `.pf/raw/` or any default file location.

#### Scenario: JSON output to stdout
- **WHEN** user runs any analysis command with `--json` flag
- **THEN** JSON output is written to stdout
- **AND** no files are created in `.pf/` directory

#### Scenario: Piping JSON to file
- **WHEN** user runs `aud taint --json > my_report.json`
- **THEN** JSON is written to user-specified file via shell redirection
- **AND** user controls the destination, not the tool

#### Scenario: Default output without --json
- **WHEN** user runs analysis command without `--json` flag
- **THEN** human-readable formatted output is written to stdout
- **AND** no JSON files are created anywhere

### Requirement: No Default File Outputs

CLI commands SHALL NOT have `--output` flags with default values pointing to `.pf/raw/`. Commands that previously wrote to `.pf/raw/` by default SHALL only output to stdout.

#### Scenario: Removed --output defaults
- **WHEN** user runs `aud taint` without arguments
- **THEN** output goes to stdout only
- **AND** no `.pf/raw/taint_analysis.json` file is created

#### Scenario: No --write flag
- **WHEN** user runs `aud fce`
- **THEN** output goes to stdout
- **AND** `--write` flag does not exist
- **AND** no `.pf/raw/fce.json` file is created

### Requirement: Commands With JSON Support

The following commands SHALL support `--json` flag for machine-readable output:

- `aud docker-analyze --json`
- `aud graph analyze --json`
- `aud detect-frameworks --json`
- `aud deps --json`
- `aud cfg analyze --json`
- `aud terraform provision --json`
- `aud terraform analyze --json`
- `aud workflows analyze --json`
- `aud metadata churn --json`
- `aud metadata coverage --json`
- `aud taint --json`
- `aud fce` (JSON is default format)
- `aud tools list --json`
- `aud impact --json`
- `aud graphql query --json`
- `aud session activity --json-output`

#### Scenario: Consistent --json behavior
- **WHEN** user runs any of the above commands with `--json`
- **THEN** valid JSON is output to stdout
- **AND** output is parseable by `jq` or similar tools

## REMOVED Requirements

### Requirement: Raw JSON File Outputs

**Reason**: Database is source of truth. JSON files are redundant, stale immediately, and unused by AI tooling.

**Migration**: Use `command --json > file.json` for file output.

The following file outputs are removed:
- `.pf/raw/vulnerabilities.json`
- `.pf/raw/docker_findings.json`
- `.pf/raw/graph_analysis.json`
- `.pf/raw/graph_summary.json`
- `.pf/raw/frameworks.json`
- `.pf/raw/deps.json`
- `.pf/raw/deps_latest.json`
- `.pf/raw/fce.json`
- `.pf/raw/cfg_analysis.json`
- `.pf/raw/terraform_graph.json`
- `.pf/raw/terraform_findings.json`
- `.pf/raw/github_workflows.json`
- `.pf/raw/taint_analysis.json`
- `.pf/raw/tools.json`
- `.pf/raw/churn_analysis.json`
- `.pf/raw/coverage_analysis.json`
- `.pf/raw/semantic_context_*.json`
- `.pf/raw/lint.json`
- `.pf/raw/patterns.json`
- `.pf/raw/deadcode.json`
- `.pf/raw/refactor_report.json`

#### Scenario: No raw directory created
- **WHEN** user runs `aud full`
- **THEN** no `.pf/raw/` directory is created
- **AND** all analysis results are in database only

### Requirement: --output Flag Defaults

**Reason**: Implicit file writing encourages stale artifacts and fallback patterns.

**Migration**: Use shell redirection: `command --json > path/to/file.json`

The following `--output` flag defaults are removed:
- `aud taint --output` (was `.pf/raw/taint_analysis.json`)
- `aud cfg analyze --output` (was `.pf/raw/cfg_analysis.json`)
- `aud metadata churn --output` (was `.pf/raw/churn_analysis.json`)
- `aud metadata coverage --output` (was `.pf/raw/coverage_analysis.json`)
- `aud terraform provision --output` (was `.pf/raw/terraform_graph.json`)
- `aud terraform analyze --output` (was `.pf/raw/terraform_findings.json`)
- `aud workflows analyze --output` (was `.pf/raw/github_workflows.json`)
- `aud graph analyze --out` (was `.pf/raw/graph_analysis.json`)
- `aud graph viz --out-dir` (was `.pf/raw/`)

#### Scenario: No implicit file creation
- **WHEN** user runs `aud taint` without `--json` flag
- **THEN** human-readable output goes to stdout
- **AND** no file is created anywhere

### Requirement: FCE --write Flag

**Reason**: Redundant. FCE outputs JSON to stdout by default.

**Migration**: Use `aud fce > report.json` for file output.

#### Scenario: --write flag removed
- **WHEN** user runs `aud fce --write`
- **THEN** error: unrecognized option '--write'
