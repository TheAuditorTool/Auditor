## MODIFIED Requirements

### Requirement: Console Output Rendering
The pipeline SHALL render console output through a single RichRenderer instance that implements the PipelineObserver protocol. **Additionally, all CLI commands SHALL use the shared console singleton from `theauditor.pipeline.ui` for consistency.**

#### Scenario: Single output authority
- **WHEN** the pipeline executes any phase
- **THEN** all console output SHALL be routed through RichRenderer
- **AND** no direct print() calls SHALL exist in pipeline execution code

#### Scenario: TTY detection for Rich mode
- **WHEN** the pipeline starts and stdout is a TTY
- **THEN** RichRenderer SHALL use Rich Live display with updating table
- **AND** refresh rate SHALL be 4 times per second

#### Scenario: Non-TTY fallback mode
- **WHEN** the pipeline starts and stdout is NOT a TTY (CI/CD)
- **THEN** RichRenderer SHALL fall back to simple sequential prints
- **AND** no Rich Live context SHALL be created

#### Scenario: Quiet mode suppression
- **WHEN** the pipeline runs with --quiet flag
- **THEN** RichRenderer SHALL suppress all non-error output
- **AND** errors SHALL still be displayed to stderr

#### Scenario: Command output through shared console
- **WHEN** any CLI command in `theauditor/commands/` outputs to console
- **THEN** it SHALL use the `console` singleton from `theauditor.pipeline.ui`
- **AND** it SHALL NOT use `click.echo()` or create separate Console instances

## ADDED Requirements

### Requirement: AUDITOR_THEME Token Definitions
The pipeline ui module SHALL define semantic style tokens in AUDITOR_THEME for consistent command output styling.

#### Scenario: Status tokens defined
- **WHEN** AUDITOR_THEME is loaded
- **THEN** it SHALL define `success` as bold green
- **AND** it SHALL define `warning` as bold yellow
- **AND** it SHALL define `error` as bold red
- **AND** it SHALL define `info` as bold cyan

#### Scenario: Severity tokens defined
- **WHEN** AUDITOR_THEME is loaded
- **THEN** it SHALL define `critical` as bold red
- **AND** it SHALL define `high` as bold yellow
- **AND** it SHALL define `medium` as bold blue
- **AND** it SHALL define `low` as cyan

#### Scenario: UI element tokens defined
- **WHEN** AUDITOR_THEME is loaded
- **THEN** it SHALL define `cmd` as bold magenta (for command references)
- **AND** it SHALL define `path` as bold cyan (for file paths)
- **AND** it SHALL define `dim` as dim white (for secondary information)

### Requirement: Console Singleton Export
The pipeline ui module SHALL export a pre-configured Console singleton for use by all commands.

#### Scenario: Console singleton configuration
- **WHEN** `console` is imported from `theauditor.pipeline.ui`
- **THEN** it SHALL be a Rich Console instance
- **AND** it SHALL use AUDITOR_THEME for styling
- **AND** it SHALL have `force_terminal` set based on `sys.stdout.isatty()`

#### Scenario: Console singleton is reusable
- **WHEN** multiple commands import `console` from `theauditor.pipeline.ui`
- **THEN** they SHALL all receive the same Console instance
- **AND** theme and configuration SHALL be consistent across all usages
