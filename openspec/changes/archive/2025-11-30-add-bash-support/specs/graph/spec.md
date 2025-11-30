## ADDED Requirements

### Requirement: Bash Graph Strategy
The graph builder SHALL include a Bash-specific strategy for data flow graph construction.

> **Cross-reference**: See `design.md` Decision 14 for architecture rationale.

#### Scenario: BashPipeStrategy registration
- **WHEN** the DFGBuilder is initialized
- **THEN** BashPipeStrategy SHALL be included in the strategies list
- **AND** it SHALL be imported from `theauditor/graph/strategies/bash_pipes.py`
- **AND** wiring location SHALL be `theauditor/graph/dfg_builder.py:27-32`

#### Scenario: Pipe data flow edge creation
- **WHEN** BashPipeStrategy.build() is called
- **THEN** it SHALL query `bash_pipes` table for pipeline connections
- **AND** it SHALL create DFGEdge instances linking stdout of command N to stdin of command N+1
- **AND** edges SHALL have edge_type='pipe_flow'

#### Scenario: Source statement cross-file edges
- **WHEN** BashPipeStrategy.build() encounters bash_sources records
- **THEN** it SHALL create cross-file edges linking the source statement to the sourced file
- **AND** edges SHALL have edge_type='source_include'
- **AND** sourced file symbols SHALL be treated as available in the sourcing file's scope

#### Scenario: Subshell capture edges
- **WHEN** BashPipeStrategy.build() encounters bash_subshells with capture_target
- **THEN** it SHALL create edges linking the subshell output to the capture variable
- **AND** edges SHALL have edge_type='subshell_capture'

### Requirement: Bash Taint Sources
The taint analysis SHALL recognize Bash-specific taint sources.

> **Cross-reference**: See `design.md` Decision 16 for source/sink definitions.

#### Scenario: User input sources
- **WHEN** taint analysis runs on Bash code
- **THEN** the following SHALL be recognized as taint sources:
  - Positional parameters: `$1`, `$2`, ..., `$@`, `$*`
  - Environment variables: `$USER`, `$HOME`, `$PATH`, etc.
  - Read command output: variables assigned via `read` builtin
  - Command substitution from external commands

#### Scenario: Network input sources
- **WHEN** a variable captures output from `curl`, `wget`, `nc`, or similar
- **THEN** the captured variable SHALL be marked as tainted
- **AND** taint SHALL propagate through pipes and assignments

### Requirement: Bash Taint Sinks
The taint analysis SHALL recognize Bash-specific dangerous sinks.

#### Scenario: Command injection sinks
- **WHEN** tainted data reaches these sinks
- **THEN** a critical finding SHALL be generated:
  - `eval` command with tainted argument
  - Unquoted variable expansion in command position
  - Backtick substitution with tainted content
  - `source` or `.` with tainted path

#### Scenario: File operation sinks
- **WHEN** tainted data reaches file operations
- **THEN** a high-severity finding SHALL be generated:
  - `rm`, `mv`, `cp` with tainted path argument
  - Redirection target with tainted path
  - `chmod`, `chown` with tainted target

### Requirement: Bash Rules Wiring
The rules orchestrator SHALL discover and execute Bash-specific rules.

> **Cross-reference**: See `design.md` Decision 15 for rules architecture.

#### Scenario: Rules directory structure
- **WHEN** the rules orchestrator initializes
- **THEN** it SHALL discover rules in `theauditor/rules/bash/`
- **AND** the pattern SHALL match existing `rules/python/` and `rules/node/`

#### Scenario: Rule function signature
- **WHEN** a Bash rule module is loaded
- **THEN** it SHALL export an `analyze(cursor, config)` function
- **AND** the function SHALL return a list of finding dictionaries
- **AND** findings SHALL conform to the standard finding schema

#### Scenario: Rule execution
- **WHEN** `aud rules` or `aud full` runs
- **THEN** Bash rules SHALL execute if bash_* tables contain data
- **AND** findings SHALL be written to `findings_consolidated` table

### Requirement: Database flush_order Integration
The base database manager SHALL include Bash tables in the flush order.

> **Cross-reference**: See `design.md` Decision 17 for flush ordering.

#### Scenario: flush_order list update
- **WHEN** flush_batch() executes
- **THEN** bash_* tables SHALL be flushed in correct order
- **AND** tables SHALL appear after core tables but before findings
- **AND** location SHALL be `theauditor/indexer/database/base_database.py:193-332`

#### Scenario: Bash table flush order
- **WHEN** Bash tables are flushed
- **THEN** the order SHALL be:
  1. `bash_functions` (no dependencies)
  2. `bash_variables` (no dependencies)
  3. `bash_sources` (no dependencies)
  4. `bash_commands` (no dependencies)
  5. `bash_command_args` (depends on bash_commands via file+command_line)
  6. `bash_pipes` (no dependencies)
  7. `bash_subshells` (no dependencies)
  8. `bash_redirections` (no dependencies)
