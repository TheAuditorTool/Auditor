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

### Requirement: bash_functions Table Schema
The indexer SHALL store Bash function definitions in a normalized table.

#### Scenario: bash_functions table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_functions` table SHALL exist
- **AND** columns SHALL include: file (TEXT), line (INTEGER), end_line (INTEGER), name (TEXT), style (TEXT: 'function'|'posix'|'function_no_parens'), body_start_line (INTEGER), body_end_line (INTEGER)
- **AND** primary key SHALL be (file, name, line)
- **AND** indexes SHALL exist for file lookup and name search

### Requirement: bash_variables Table Schema
The indexer SHALL store Bash variable assignments in a normalized table.

#### Scenario: bash_variables table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_variables` table SHALL exist
- **AND** columns SHALL include: file (TEXT), line (INTEGER), name (TEXT), scope (TEXT: 'global'|'local'|'export'), readonly (BOOLEAN), value_expr (TEXT), containing_function (TEXT nullable)
- **AND** primary key SHALL be (file, name, line)
- **AND** indexes SHALL exist for file lookup, name search, and scope filtering

### Requirement: bash_sources Table Schema
The indexer SHALL store Bash source/dot statements in a normalized table.

#### Scenario: bash_sources table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_sources` table SHALL exist
- **AND** columns SHALL include: file (TEXT), line (INTEGER), sourced_path (TEXT), syntax (TEXT: 'source'|'dot'), has_variable_expansion (BOOLEAN), containing_function (TEXT nullable)
- **AND** primary key SHALL be (file, line)
- **AND** indexes SHALL exist for file lookup and sourced_path search

### Requirement: bash_commands Table Schema
The indexer SHALL store Bash command invocations in a normalized table.

#### Scenario: bash_commands table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_commands` table SHALL exist
- **AND** columns SHALL include: file (TEXT), line (INTEGER), command_name (TEXT), pipeline_position (INTEGER nullable), containing_function (TEXT nullable)
- **AND** primary key SHALL be (file, line, pipeline_position)
- **AND** indexes SHALL exist for file lookup and command_name search

### Requirement: bash_command_args Junction Table Schema
The indexer SHALL store Bash command arguments in a junction table.

#### Scenario: bash_command_args table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_command_args` table SHALL exist
- **AND** columns SHALL include: file (TEXT), command_line (INTEGER), arg_index (INTEGER), arg_value (TEXT), is_quoted (BOOLEAN), quote_type (TEXT: 'none'|'single'|'double'), has_expansion (BOOLEAN), expansion_vars (TEXT nullable)
- **AND** primary key SHALL be (file, command_line, arg_index)
- **AND** indexes SHALL exist for command lookup and expansion detection

### Requirement: bash_pipes Table Schema
The indexer SHALL store Bash pipeline connections in a normalized table.

#### Scenario: bash_pipes table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_pipes` table SHALL exist
- **AND** columns SHALL include: file (TEXT), line (INTEGER), pipeline_id (INTEGER), position (INTEGER), command_text (TEXT), containing_function (TEXT nullable)
- **AND** primary key SHALL be (file, line, pipeline_id, position)
- **AND** indexes SHALL exist for file lookup and pipeline tracing

### Requirement: bash_subshells Table Schema
The indexer SHALL store Bash command substitutions in a normalized table.

#### Scenario: bash_subshells table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_subshells` table SHALL exist
- **AND** columns SHALL include: file (TEXT), line (INTEGER), syntax (TEXT: 'dollar_paren'|'backtick'), command_text (TEXT), capture_target (TEXT nullable), containing_function (TEXT nullable)
- **AND** primary key SHALL be (file, line)
- **AND** indexes SHALL exist for file lookup and capture_target search

### Requirement: bash_redirections Table Schema
The indexer SHALL store Bash I/O redirections in a normalized table.

#### Scenario: bash_redirections table columns
- **WHEN** the database schema is initialized
- **THEN** the `bash_redirections` table SHALL exist
- **AND** columns SHALL include: file (TEXT), line (INTEGER), direction (TEXT: 'input'|'output'|'append'|'heredoc'|'herestring'|'stderr'), target (TEXT), fd_number (INTEGER nullable), containing_function (TEXT nullable)
- **AND** primary key SHALL be (file, line, direction)
- **AND** indexes SHALL exist for file lookup and direction filtering

### Requirement: Bash Data Flow Tracking
The indexer SHALL track data flow through pipes, subshells, and variable expansion.

#### Scenario: Pipe chain extraction
- **WHEN** a Bash file contains a pipeline (`cmd1 | cmd2 | cmd3`)
- **THEN** the indexer SHALL extract each command in the pipeline
- **AND** the order and connections between commands SHALL be stored in bash_pipes

#### Scenario: Subshell capture extraction
- **WHEN** a Bash file contains command substitution (`$(cmd)` or backticks)
- **THEN** the indexer SHALL extract the substitution and its capture target
- **AND** variable assignments capturing subshell output SHALL be linked via capture_target column

#### Scenario: Redirection extraction
- **WHEN** a Bash file contains redirections
- **THEN** the indexer SHALL extract input, output, and error redirections to bash_redirections
- **AND** here documents and here strings SHALL be captured with direction='heredoc' or 'herestring'

### Requirement: Bash Quote Context Analysis
The indexer SHALL track quoting context for security analysis.

#### Scenario: Unquoted variable detection
- **WHEN** a variable expansion occurs without double quotes
- **THEN** the indexer SHALL set is_quoted=FALSE and quote_type='none' in bash_command_args
- **AND** has_expansion=TRUE and expansion_vars SHALL list the variable names

#### Scenario: Quote nesting tracking
- **WHEN** a command contains nested quoting
- **THEN** the indexer SHALL correctly parse quote boundaries
- **AND** variables inside single quotes SHALL have has_expansion=FALSE

### Requirement: Bash Security Pattern Detection
The indexer SHALL detect security-relevant patterns in Bash code.

Security patterns are detected during extraction and stored as findings. Pattern detection uses the bash_* tables for analysis.

#### Scenario: Command injection detection
- **WHEN** code contains `eval "$var"` or variable-as-command patterns
- **THEN** the indexer SHALL flag it as a potential command injection
- **AND** detection SHALL query bash_commands WHERE command_name='eval' AND has variable args

#### Scenario: Unquoted variable in command detection
- **WHEN** code passes unquoted variable to a command argument
- **THEN** the indexer SHALL flag it as a word-splitting vulnerability
- **AND** detection SHALL query bash_command_args WHERE is_quoted=FALSE AND has_expansion=TRUE

#### Scenario: Curl-pipe-bash detection
- **WHEN** code pipes curl/wget output directly to bash/sh
- **THEN** the indexer SHALL flag it as a critical security risk
- **AND** detection SHALL query bash_pipes for curl/wget followed by bash/sh in same pipeline

#### Scenario: Hardcoded credential detection
- **WHEN** code assigns values to variables named PASSWORD, SECRET, API_KEY, TOKEN, or similar
- **THEN** the indexer SHALL flag it as a potential hardcoded credential
- **AND** detection SHALL query bash_variables WHERE name LIKE '%PASSWORD%' OR name LIKE '%SECRET%' etc.

#### Scenario: Missing safety flags detection
- **WHEN** a script lacks `set -e`, `set -u`, or `set -o pipefail`
- **THEN** the indexer SHALL note the missing safety flags
- **AND** detection SHALL query bash_commands for 'set' commands with safety options

#### Scenario: Unsafe temp file detection
- **WHEN** code creates files in /tmp with predictable names
- **THEN** the indexer SHALL flag it as an unsafe temp file pattern
- **AND** detection SHALL query bash_redirections WHERE target LIKE '/tmp/%' without mktemp

#### Scenario: Sudo abuse detection
- **WHEN** code runs sudo with variable command or arguments
- **THEN** the indexer SHALL flag it as potential privilege escalation risk
- **AND** detection SHALL query bash_commands WHERE command_name='sudo' with variable expansion in args

### Requirement: Database flush_order Integration
The base database manager SHALL include Bash tables in batch flush operations.

> **Cross-reference**: See `design.md` Decision 17 for ordering rationale.

#### Scenario: flush_order list inclusion
- **WHEN** the database manager's `flush_batch()` method executes
- **THEN** all 8 bash_* tables SHALL be included in the flush_order list
- **AND** location SHALL be `theauditor/indexer/database/base_database.py:193-332`

#### Scenario: Bash table ordering
- **WHEN** Bash tables are flushed
- **THEN** the order SHALL respect dependencies:
  1. `bash_functions` - no dependencies
  2. `bash_variables` - no dependencies
  3. `bash_sources` - no dependencies
  4. `bash_commands` - no dependencies
  5. `bash_command_args` - depends on bash_commands (file + command_line FK)
  6. `bash_pipes` - no dependencies
  7. `bash_subshells` - no dependencies
  8. `bash_redirections` - no dependencies
- **AND** all bash_* tables SHALL appear after `python_control_statements`
- **AND** all bash_* tables SHALL appear before `sql_query_tables`

### Requirement: Schema Table Count Assertion
The schema module SHALL maintain correct table count assertion.

#### Scenario: Table count update
- **WHEN** Bash tables are added to the schema
- **THEN** the assertion in `theauditor/indexer/schema.py:27` SHALL be updated
- **AND** the count SHALL change from 170 to 178 (adding 8 new tables)
- **AND** if the assertion fails, schema initialization SHALL fail loudly
