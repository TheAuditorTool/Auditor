## ADDED Requirements

### Requirement: Bash Assignment Extraction for DFG
The Bash extractor SHALL populate the language-agnostic `assignments` table for all variable assignments in Bash scripts.

**Schema reference** (`theauditor/indexer/schemas/core_schema.py:92-113`):
```sql
assignments (
    file TEXT,           -- File path (NOT NULL)
    line INTEGER,        -- 1-indexed line number (NOT NULL)
    col INTEGER,         -- 0-indexed column (NOT NULL, default 0)
    target_var TEXT,     -- Variable being assigned (NOT NULL)
    source_expr TEXT,    -- Right-hand side expression (NOT NULL)
    in_function TEXT,    -- Containing function or "global" (NOT NULL)
    property_path TEXT   -- Property path for nested assignments (NULL for Bash)
)
-- PRIMARY KEY: (file, line, col, target_var)
```

#### Scenario: Simple assignment
- **WHEN** a Bash file contains `VAR=value`
- **THEN** the `assignments` table SHALL contain a row:
  - `file`: the file path
  - `line`: the line number (1-indexed)
  - `col`: 0
  - `target_var`: "VAR"
  - `source_expr`: "value"
  - `in_function`: containing function name or "global"

#### Scenario: Command substitution assignment
- **WHEN** a Bash file contains `VAR=$(command arg)`
- **THEN** the `assignments` table SHALL contain a row:
  - `target_var`: "VAR"
  - `source_expr`: "$(command arg)"

#### Scenario: Arithmetic expansion assignment
- **WHEN** a Bash file contains `VAR=$((x + 1))`
- **THEN** the `assignments` table SHALL contain a row:
  - `target_var`: "VAR"
  - `source_expr`: "$((x + 1))"

#### Scenario: Read command as assignment
- **WHEN** a Bash file contains `read USER_INPUT`
- **THEN** the `assignments` table SHALL contain a row:
  - `target_var`: "USER_INPUT"
  - `source_expr`: "stdin" or empty string

#### Scenario: Local declaration
- **WHEN** a Bash file contains `local VAR=value` inside function `myfunc`
- **THEN** the `assignments` table SHALL contain a row:
  - `target_var`: "VAR"
  - `in_function`: "myfunc"

#### Scenario: Export with assignment
- **WHEN** a Bash file contains `export VAR=value`
- **THEN** the `assignments` table SHALL contain a row:
  - `target_var`: "VAR"
  - `source_expr`: "value"

---

### Requirement: Bash Command Extraction as Function Calls
The Bash extractor SHALL populate the language-agnostic `function_call_args` table for all command invocations in Bash scripts.

**Schema reference** (`theauditor/indexer/schemas/core_schema.py:138-162`):
```sql
function_call_args (
    file TEXT,            -- File path (NOT NULL)
    line INTEGER,         -- 1-indexed line number (NOT NULL)
    caller_function TEXT, -- Function containing the call, or "global" (NOT NULL)
    callee_function TEXT, -- Command being invoked (NOT NULL, CHECK != '')
    argument_index INTEGER, -- 0-indexed argument position (nullable)
    argument_expr TEXT,   -- Argument value/expression (nullable)
    param_name TEXT,      -- Named parameter if known (NULL for Bash positional args)
    callee_file_path TEXT -- Path to callee definition (NULL for Bash external commands)
)
-- No composite primary key (allows multiple args per call)
```

#### Scenario: Simple command with arguments
- **WHEN** a Bash file contains `grep pattern file.txt`
- **THEN** the `function_call_args` table SHALL contain rows:
  - Row 1: `callee_function`="grep", `argument_index`=0, `argument_expr`="pattern"
  - Row 2: `callee_function`="grep", `argument_index`=1, `argument_expr`="file.txt"

#### Scenario: Command with variable argument
- **WHEN** a Bash file contains `rm -rf $DIR`
- **THEN** the `function_call_args` table SHALL contain rows:
  - `callee_function`="rm"
  - One row with `argument_expr`="-rf"
  - One row with `argument_expr`="$DIR"

#### Scenario: Built-in command
- **WHEN** a Bash file contains `echo $MESSAGE`
- **THEN** the `function_call_args` table SHALL contain a row:
  - `callee_function`="echo"
  - `argument_expr`="$MESSAGE"

#### Scenario: Command in function
- **WHEN** a Bash file contains `function foo() { curl $URL; }`
- **THEN** the `function_call_args` row SHALL have:
  - `caller_function`="foo"
  - `callee_function`="curl"
  - `argument_expr`="$URL"

---

### Requirement: Bash Positional Parameter Extraction
The Bash extractor SHALL populate the `func_params` table for positional parameters in Bash functions.

**Schema reference** (`theauditor/indexer/schemas/node_schema.py:847-862`):
```sql
func_params (
    file TEXT,            -- File path (NOT NULL)
    function_line INTEGER,-- Line where function is defined (NOT NULL)
    function_name TEXT,   -- Function name or "global" (NOT NULL)
    param_index INTEGER,  -- 0, 1, 2, ... or -1 for variadic (NOT NULL)
    param_name TEXT,      -- "$1", "$2", "$@", etc. (NOT NULL)
    param_type TEXT       -- Type annotation (NULL for Bash - no types)
)
-- Indexed on: (file, function_line, function_name), (param_name)
```

**Note for Bash**: Since Bash functions don't have formal parameter declarations, we track:
- `function_line`: Line where the function is defined (or 0 for script-level/global)
- `param_name`: The positional parameter syntax (`$1`, `$2`, `$@`, `$*`)
- `param_type`: Always NULL for Bash (untyped language)

#### Scenario: Function using positional params
- **WHEN** a Bash file contains `function process() { echo $1 $2; }` at line 5
- **THEN** the `func_params` table SHALL contain rows:
  - `function_line`=5, `function_name`="process", `param_name`="$1", `param_index`=0, `param_type`=NULL
  - `function_line`=5, `function_name`="process", `param_name`="$2", `param_index`=1, `param_type`=NULL

#### Scenario: Script-level positional params
- **WHEN** a Bash file uses `$1` at the script level (not in a function)
- **THEN** the `func_params` table SHALL contain a row:
  - `function_line`=0 (indicating script-level)
  - `function_name`="global"
  - `param_name`="$1"
  - `param_index`=0
  - `param_type`=NULL

#### Scenario: All arguments parameter
- **WHEN** a Bash file contains `function foo() { for arg in "$@"; do echo $arg; done; }` at line 10
- **THEN** the `func_params` table SHALL contain a row:
  - `function_line`=10
  - `function_name`="foo"
  - `param_name`="$@"
  - `param_index`=-1 (indicating variadic)
  - `param_type`=NULL

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
The Bash extractor SHALL use the centralized logging system (loguru wrapper).

**Logging module reference** (`theauditor/utils/logging.py`):
```python
# This wraps loguru and provides Pino-compatible output
from theauditor.utils.logging import logger

# Usage:
logger.debug(f"Bash: mapped {count} assignments from {file}")
logger.info("Starting bash extraction")
logger.error(f"Failed to parse: {error}")
```

#### Scenario: Logging import
- **WHEN** examining `theauditor/ast_extractors/bash_impl.py` source code
- **THEN** it SHALL contain `from theauditor.utils.logging import logger`
- **NOTE**: This imports the loguru-based logger from the centralized module

#### Scenario: Debug logging for extraction counts
- **WHEN** Bash extraction completes for a file
- **THEN** logger.debug SHALL be called with extraction statistics
- **AND** the message SHALL include file path and counts per table type

#### Scenario: No print statements
- **WHEN** examining bash_impl.py and injection_analyze.py source code
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
