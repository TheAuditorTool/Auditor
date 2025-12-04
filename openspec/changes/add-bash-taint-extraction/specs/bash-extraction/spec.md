## ADDED Requirements

### Requirement: Bash Assignment Extraction for DFG
The Bash extractor SHALL populate the language-agnostic `assignments` and `assignment_sources` tables for all variable assignments in Bash scripts.

#### Scenario: Simple assignment
- **WHEN** a Bash file contains `VAR=value`
- **THEN** the `assignments` table SHALL contain a row with target_var="VAR", source_expr="value"
- **AND** the row SHALL include file path, line number, and containing function

#### Scenario: Command substitution assignment
- **WHEN** a Bash file contains `VAR=$(command arg)`
- **THEN** the `assignments` table SHALL contain a row with target_var="VAR", source_expr="$(command arg)"
- **AND** `assignment_sources` SHALL link VAR to the command substitution

#### Scenario: Arithmetic expansion assignment
- **WHEN** a Bash file contains `VAR=$((x + 1))`
- **THEN** the `assignments` table SHALL contain a row with target_var="VAR"
- **AND** `assignment_sources` SHALL link VAR to source variable "x"

#### Scenario: Read command as assignment
- **WHEN** a Bash file contains `read USER_INPUT`
- **THEN** the `assignments` table SHALL contain a row with target_var="USER_INPUT"
- **AND** the source_expr SHALL indicate stdin source

#### Scenario: Local declaration
- **WHEN** a Bash file contains `local VAR=value` inside a function
- **THEN** the `assignments` table SHALL contain a row with in_function set to the function name

#### Scenario: Export with assignment
- **WHEN** a Bash file contains `export VAR=value`
- **THEN** the `assignments` table SHALL contain a row with target_var="VAR"

---

### Requirement: Bash Command Extraction as Function Calls
The Bash extractor SHALL populate the language-agnostic `function_call_args` table for all command invocations in Bash scripts.

#### Scenario: Simple command with arguments
- **WHEN** a Bash file contains `grep pattern file.txt`
- **THEN** the `function_call_args` table SHALL contain rows with callee_function="grep"
- **AND** argument_index 0 SHALL have argument_expr="pattern"
- **AND** argument_index 1 SHALL have argument_expr="file.txt"

#### Scenario: Command with variable argument
- **WHEN** a Bash file contains `rm -rf $DIR`
- **THEN** the `function_call_args` table SHALL contain a row with callee_function="rm"
- **AND** one argument row SHALL have argument_expr="$DIR"

#### Scenario: Built-in command
- **WHEN** a Bash file contains `echo $MESSAGE`
- **THEN** the `function_call_args` table SHALL contain a row with callee_function="echo"
- **AND** argument_expr SHALL be "$MESSAGE"

#### Scenario: Command in function
- **WHEN** a Bash file contains a command inside `function foo() { curl $URL; }`
- **THEN** the `function_call_args` row SHALL have caller_function="foo"

---

### Requirement: Bash Positional Parameter Extraction
The Bash extractor SHALL populate the `func_params` table for positional parameters in Bash functions.

#### Scenario: Function using positional params
- **WHEN** a Bash file contains `function process() { echo $1 $2; }`
- **THEN** the `func_params` table SHALL contain rows for function_name="process"
- **AND** param_name="$1" with param_index=0
- **AND** param_name="$2" with param_index=1

#### Scenario: Script-level positional params
- **WHEN** a Bash file uses `$1` at the script level (not in a function)
- **THEN** the `func_params` table SHALL contain a row with function_name="main" or "global"
- **AND** param_name="$1" with param_index=0

#### Scenario: All arguments parameter
- **WHEN** a Bash file contains `function foo() { for arg in "$@"; do echo $arg; done; }`
- **THEN** the `func_params` table SHALL contain a row with param_name="$@"
- **AND** it SHALL be marked as variadic

---

### Requirement: Bash Taint Source Pattern Registration
The system SHALL register Bash-specific source patterns in TaintRegistry.

#### Scenario: Positional parameter sources
- **WHEN** TaintRegistry is initialized with Bash patterns
- **THEN** it SHALL contain source patterns for `$1` through `$9`
- **AND** it SHALL contain source patterns for `$@` and `$*`

#### Scenario: Read command as source
- **WHEN** TaintRegistry is initialized with Bash patterns
- **THEN** it SHALL contain source patterns for the `read` command
- **AND** variables assigned by `read` SHALL be considered tainted

#### Scenario: CGI variable sources
- **WHEN** TaintRegistry is initialized with Bash patterns
- **THEN** it SHALL contain source patterns for `$QUERY_STRING`
- **AND** it SHALL contain source patterns for `$REQUEST_URI`
- **AND** it SHALL contain source patterns for `$HTTP_*` variables

---

### Requirement: Bash Taint Sink Pattern Registration
The system SHALL register Bash-specific sink patterns in TaintRegistry.

#### Scenario: Command injection sinks
- **WHEN** TaintRegistry is initialized with Bash patterns
- **THEN** it SHALL contain sink patterns for `eval`
- **AND** it SHALL contain sink patterns for `exec`
- **AND** it SHALL contain sink patterns for `sh -c`
- **AND** it SHALL contain sink patterns for `bash -c`

#### Scenario: Source command sinks
- **WHEN** TaintRegistry is initialized with Bash patterns
- **THEN** it SHALL contain sink patterns for `source`
- **AND** it SHALL contain sink patterns for `.` (source shorthand)

#### Scenario: Dangerous command sinks
- **WHEN** TaintRegistry is initialized with Bash patterns
- **THEN** it SHALL contain sink patterns for `rm` (especially `rm -rf`)
- **AND** it SHALL contain sink patterns for `curl | sh` pattern
- **AND** it SHALL contain sink patterns for `wget | sh` pattern

#### Scenario: Database client sinks
- **WHEN** TaintRegistry is initialized with Bash patterns
- **THEN** it SHALL contain sink patterns for `mysql` with user input
- **AND** it SHALL contain sink patterns for `psql` with user input
- **AND** it SHALL contain sink patterns for `sqlite3` with user input

---

### Requirement: Bash Logging Integration
The Bash extractor SHALL use the centralized logging system.

#### Scenario: Logging import
- **WHEN** examining bash.py and bash_impl.py source code
- **THEN** they SHALL contain `from theauditor.utils.logging import logger`

#### Scenario: Debug logging for extraction counts
- **WHEN** Bash extraction completes for a file
- **THEN** logger.debug SHALL be called with extraction statistics
- **AND** the message SHALL include file path and counts per table

#### Scenario: No print statements
- **WHEN** examining bash.py, bash_impl.py, and injection_analyze.py source code
- **THEN** there SHALL be no bare `print()` calls
- **AND** all output SHALL use the logger

---

### Requirement: ZERO FALLBACK Compliance for Bash Extraction
The Bash extractor SHALL NOT use fallback logic when extracting data.

#### Scenario: Malformed AST node
- **WHEN** a tree-sitter node is missing expected children
- **THEN** the extractor SHALL log a debug message with the file and line
- **AND** SHALL skip that node
- **AND** SHALL NOT substitute default values

#### Scenario: No try-except fallbacks
- **WHEN** examining bash.py extraction logic
- **THEN** there SHALL be no try-except blocks that swallow errors and return defaults
