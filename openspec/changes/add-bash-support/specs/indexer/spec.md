## ADDED Requirements

### Requirement: Bash Language Extraction
The indexer SHALL extract Bash/Shell language constructs from .sh files using tree-sitter parsing.

#### Scenario: Function extraction
- **WHEN** a Bash file contains a function definition
- **THEN** the indexer SHALL extract function name, body location, and style (function keyword vs POSIX)
- **AND** the indexer SHALL store data in bash_functions table

#### Scenario: Variable extraction
- **WHEN** a Bash file contains variable assignments
- **THEN** the indexer SHALL extract variable name, value expression, and scope (global/local/export)
- **AND** readonly and declare flags SHALL be tracked

#### Scenario: Source statement extraction
- **WHEN** a Bash file contains source or dot statements
- **THEN** the indexer SHALL extract the sourced file path
- **AND** both `source file.sh` and `. file.sh` syntax SHALL be supported

#### Scenario: Command invocation extraction
- **WHEN** a Bash file contains command invocations
- **THEN** the indexer SHALL extract command name, arguments, and containing function
- **AND** quote context for each argument SHALL be tracked

#### Scenario: Shebang detection
- **WHEN** a file has no .sh extension but starts with bash shebang
- **THEN** the indexer SHALL detect it as a Bash file
- **AND** shebangs `#!/bin/bash`, `#!/usr/bin/env bash`, and `#!/bin/sh` SHALL be recognized

### Requirement: Bash Schema Tables
The indexer SHALL store Bash extraction data in dedicated normalized tables.

#### Scenario: Core entity tables exist
- **WHEN** the database is initialized
- **THEN** tables bash_functions, bash_variables, bash_sources, bash_commands SHALL exist

#### Scenario: Data flow tables exist
- **WHEN** the database is initialized
- **THEN** tables bash_command_args, bash_pipes, bash_subshells, bash_redirections SHALL exist

### Requirement: Bash Data Flow Tracking
The indexer SHALL track data flow through pipes, subshells, and variable expansion.

#### Scenario: Pipe chain extraction
- **WHEN** a Bash file contains a pipeline (`cmd1 | cmd2 | cmd3`)
- **THEN** the indexer SHALL extract each command in the pipeline
- **AND** the order and connections between commands SHALL be stored

#### Scenario: Subshell capture extraction
- **WHEN** a Bash file contains command substitution (`$(cmd)` or backticks)
- **THEN** the indexer SHALL extract the substitution and its capture target
- **AND** variable assignments capturing subshell output SHALL be linked

#### Scenario: Redirection extraction
- **WHEN** a Bash file contains redirections
- **THEN** the indexer SHALL extract input, output, and error redirections
- **AND** here documents and here strings SHALL be captured

### Requirement: Bash Quote Context Analysis
The indexer SHALL track quoting context for security analysis.

#### Scenario: Unquoted variable detection
- **WHEN** a variable expansion occurs without double quotes
- **THEN** the indexer SHALL flag the expansion as unquoted
- **AND** the surrounding context (command argument, test expression) SHALL be recorded

#### Scenario: Quote nesting tracking
- **WHEN** a command contains nested quoting
- **THEN** the indexer SHALL correctly parse quote boundaries
- **AND** variables inside single quotes SHALL be marked as unexpanded

### Requirement: Bash Security Pattern Detection
The indexer SHALL detect security-relevant patterns in Bash code.

#### Scenario: Command injection detection
- **WHEN** code contains `eval "$var"` or variable-as-command patterns
- **THEN** the indexer SHALL flag it as a potential command injection

#### Scenario: Unquoted variable in command detection
- **WHEN** code passes unquoted variable to a command argument
- **THEN** the indexer SHALL flag it as a word-splitting vulnerability

#### Scenario: Curl-pipe-bash detection
- **WHEN** code pipes curl/wget output directly to bash/sh
- **THEN** the indexer SHALL flag it as a critical security risk

#### Scenario: Hardcoded credential detection
- **WHEN** code assigns values to variables named PASSWORD, SECRET, API_KEY, TOKEN, or similar
- **THEN** the indexer SHALL flag it as a potential hardcoded credential

#### Scenario: Missing safety flags detection
- **WHEN** a script lacks `set -e`, `set -u`, or `set -o pipefail`
- **THEN** the indexer SHALL note the missing safety flags

#### Scenario: Unsafe temp file detection
- **WHEN** code creates files in /tmp with predictable names
- **THEN** the indexer SHALL flag it as an unsafe temp file pattern
- **AND** suggest mktemp as alternative

#### Scenario: Sudo abuse detection
- **WHEN** code runs sudo with variable command or arguments
- **THEN** the indexer SHALL flag it as potential privilege escalation risk
