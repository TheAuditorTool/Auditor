## ADDED Requirements
### Requirement: CLI Bootstrap Integrity
The CLI entry point MUST import without raising and expose `aud --help` output that renders end-to-end.

#### Scenario: Help Command Succeeds
- **GIVEN** a project with TheAuditor installed and its Python dependencies available
- **WHEN** a user (or automation) executes `aud --help`
- **THEN** the CLI imports without raising `ImportError` or other bootstrap failures
- **AND** the command exits with status code `0` after printing the help banner

### Requirement: Help Text Mirrors Live Commands
The detailed help listing MUST enumerate every registered command and only show options that actually exist on the corresponding Click definitions.

#### Scenario: Help Output Matches Click Metadata
- **GIVEN** the CLI has registered commands including `metadata`, `summary`, `detect-frameworks`, `tool-versions`, and `learn-feedback`
- **WHEN** `aud --help` is executed
- **THEN** the “Detailed Command Overview” section lists those commands with descriptions pulled from their command objects
- **AND** no line references deprecated flags such as `--workset` for `taint-analyze` or `--threshold` for `cfg analyze`

### Requirement: Truth Courier Messaging
Audit commands MUST emit factual findings without prescriptive guidance, marketing language, or remediation tips.

#### Scenario: Command Output Contains Facts Only
- **GIVEN** a repository that has run `aud full`
- **WHEN** a user runs `aud taint-analyze`, `aud refactor`, `aud docker-analyze`, or `aud deps`
- **THEN** each command prints findings, counts, or file paths without phrases like “TIP”, “Fix:”, “Recommendation”, or “RECOMMENDED ACTIONS”
- **AND** any remediation guidance remains confined to machine-readable artifacts (e.g., JSON fields) rather than CLI stdout
