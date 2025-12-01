## ADDED Requirements

### Requirement: Rich Console Output for Commands
All CLI commands SHALL use the shared Rich Console instance from `theauditor.pipeline.ui` for output instead of `click.echo()`.

#### Scenario: Console singleton import
- **WHEN** a command file needs to output to console
- **THEN** it SHALL import `console` from `theauditor.pipeline.ui`
- **AND** it SHALL NOT create its own Console instance
- **AND** it SHALL NOT use `click.echo()` or `click.secho()`

#### Scenario: Semantic status tokens
- **WHEN** a command outputs a status message with prefix `[OK]`, `[PASS]`, or `[SUCCESS]`
- **THEN** the output SHALL use `[success]...[/success]` Rich markup token
- **AND** the token SHALL render in bold green per AUDITOR_THEME

#### Scenario: Warning token styling
- **WHEN** a command outputs a message with prefix `[WARN]` or `[WARNING]`
- **THEN** the output SHALL use `[warning]...[/warning]` Rich markup token
- **AND** the token SHALL render in bold yellow per AUDITOR_THEME

#### Scenario: Error token styling
- **WHEN** a command outputs a message with prefix `[ERROR]`, `[FAIL]`, or `[FAILED]`
- **THEN** the output SHALL use `[error]...[/error]` Rich markup token
- **AND** the token SHALL render in bold red per AUDITOR_THEME

#### Scenario: Severity level tokens
- **WHEN** a command outputs finding severity levels
- **THEN** `[CRITICAL]` SHALL use `[critical]` token (bold red)
- **AND** `[HIGH]` SHALL use `[high]` token (bold yellow)
- **AND** `[MEDIUM]` SHALL use `[medium]` token (bold blue)
- **AND** `[LOW]` SHALL use `[low]` token (cyan)

#### Scenario: Path highlighting
- **WHEN** a command outputs a file path
- **THEN** the path MAY use `[path]...[/path]` token for consistent styling
- **AND** the token SHALL render in bold cyan per AUDITOR_THEME

#### Scenario: Command highlighting
- **WHEN** a command outputs a CLI command reference
- **THEN** the command MAY use `[cmd]...[/cmd]` token for consistent styling
- **AND** the token SHALL render in bold magenta per AUDITOR_THEME

### Requirement: Separator Line Rendering
Commands SHALL use `console.rule()` for visual separator lines instead of printing repeated characters.

#### Scenario: Horizontal rule replacement
- **WHEN** a command needs to output a separator like `"=" * 60` or `"-" * 40`
- **THEN** it SHALL use `console.rule()` instead
- **AND** the rule SHALL span the terminal width appropriately

#### Scenario: Titled separator
- **WHEN** a command needs a separator with a title
- **THEN** it SHALL use `console.rule("[bold]Title[/bold]")`

### Requirement: Bracket Escaping in Output
Commands SHALL escape literal bracket characters in output strings to prevent Rich markup interpretation.

#### Scenario: Static string brackets escaped
- **WHEN** a string literal contains `[` that is not a Rich tag
- **THEN** it SHALL be escaped as `\[` in the source code
- **AND** Rich SHALL render it as a literal `[` character

#### Scenario: Variable output safety
- **WHEN** a command outputs a variable that may contain brackets
- **THEN** the `console.print()` call SHALL include `markup=False`
- **AND** Rich SHALL NOT interpret any bracket sequences as tags

#### Scenario: F-string variable safety
- **WHEN** a command uses f-string with runtime variable expressions
- **THEN** the `console.print()` call SHALL include `highlight=False`
- **AND** Rich SHALL NOT apply auto-highlighting to the output

### Requirement: Error Stream Routing
Commands SHALL route error output to stderr using Rich's stderr parameter.

#### Scenario: Error flag mapping
- **WHEN** code previously used `click.echo(msg, err=True)`
- **THEN** it SHALL use `console.print(msg, stderr=True)`

#### Scenario: File stderr mapping
- **WHEN** code previously used `click.echo(msg, file=sys.stderr)`
- **THEN** it SHALL use `console.print(msg, stderr=True)`

### Requirement: Newline Control
Commands SHALL control trailing newlines using Rich's end parameter.

#### Scenario: Suppress newline
- **WHEN** code previously used `click.echo(msg, nl=False)`
- **THEN** it SHALL use `console.print(msg, end="")`
