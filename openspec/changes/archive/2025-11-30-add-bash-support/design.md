## Context

Shell scripts are the glue of modern infrastructure. CI/CD pipelines, Docker entrypoints, deployment automation, cron jobs - all Bash. Security vulnerabilities in shell scripts are common and severe: command injection can lead to RCE, unquoted variables cause unexpected behavior, hardcoded credentials leak.

Unlike Python/JS/Rust, Bash has no type system, no imports (just source), and everything is string manipulation. This makes it both simpler to parse and trickier to analyze for data flow.

## Goals / Non-Goals

**Goals:**
- Extract functions, variables, commands, control flow from .sh files
- Track data flow through pipes, subshells, and variable expansion
- Detect common security anti-patterns (injection, unsafe eval, hardcoded creds)
- Support common shebang variants (bash, sh, zsh for basic compatibility)
- Run on TheAuditor's own scripts as dogfooding

**Non-Goals:**
- Full POSIX sh compatibility matrix (focus on Bash)
- Zsh-specific features (oh-my-zsh plugins, etc.)
- Fish shell
- PowerShell (completely different language)
- Makefile parsing (different syntax despite similar use cases)
- Dynamic analysis / actually executing scripts

## Decisions

### Decision 1: Schema design - 8 normalized tables

| Table | Purpose |
|-------|---------|
| `bash_functions` | Function definitions with body location |
| `bash_variables` | Variable assignments, exports, readonly |
| `bash_sources` | Source/dot statements with resolved paths |
| `bash_commands` | External command invocations |
| `bash_command_args` | Arguments to commands (junction table) |
| `bash_pipes` | Pipe chains showing data flow |
| `bash_subshells` | Command substitution captures |
| `bash_redirections` | File redirections for I/O tracking |

**Rationale:** Smaller schema than Python/Rust because Bash is simpler. No classes, no types, no imports beyond source. Commands and pipes are the core abstractions.

### Decision 2: File detection - shebang + extension

**Detection rules:**
1. `.sh` extension → Bash
2. `.bash` extension → Bash
3. `#!/bin/bash` shebang → Bash
4. `#!/usr/bin/env bash` shebang → Bash
5. `#!/bin/sh` shebang → Bash (close enough for our purposes)
6. No extension + shebang → Bash

**Rationale:** Many shell scripts have no extension (especially in `/usr/local/bin`). Must read first line to detect shebang.

### Decision 3: Function extraction - both syntax forms

```bash
# Form 1: function keyword
function my_func() {
    echo "hello"
}

# Form 2: POSIX style
my_func() {
    echo "hello"
}

# Form 3: function keyword without parens (bash-specific)
function my_func {
    echo "hello"
}
```

All three stored identically in `bash_functions`.

### Decision 4: Variable tracking scope

```bash
# Global assignment
MY_VAR="value"

# Export (environment)
export MY_VAR="value"

# Local (function-scoped)
local my_var="value"

# Readonly
readonly MY_VAR="value"

# Declaration without value
declare -a MY_ARRAY
```

Store:
- `name` - variable name
- `scope` - global/local/export
- `readonly` - boolean
- `value_expr` - RHS expression (for credential detection)
- `containing_function` - NULL for global, function name for local

### Decision 5: Command invocation tracking

```bash
# Simple command
ls -la /tmp

# With variable expansion
rm "$file"

# With command substitution
result=$(curl "$url")

# Pipeline
cat file.txt | grep pattern | wc -l
```

Track:
- Command name (first word)
- Arguments (including which contain variable expansions)
- Whether arguments are quoted
- Position in pipeline (if any)

### Decision 6: Security rule categories

| Category | Pattern | Severity |
|----------|---------|----------|
| **Command injection** | `eval "$var"`, `` `$var` ``, `$($var)` | Critical |
| **Unquoted expansion** | `rm $file` (should be `"$file"`) | High |
| **Curl-pipe-bash** | `curl ... \| bash`, `wget -O- \| sh` | Critical |
| **Hardcoded credentials** | `PASSWORD=`, `API_KEY=`, `SECRET=` in assignment | High |
| **Missing safety flags** | No `set -e`, `set -u`, or `set -o pipefail` | Medium |
| **Unsafe temp files** | `/tmp/predictable_name` without mktemp | Medium |
| **Sudo abuse** | `sudo $cmd` with variable command | High |
| **Path injection** | Relative command without explicit PATH | Low |

### Decision 7: Data flow through pipes

```bash
user_input=$(read_input)
filtered=$(echo "$user_input" | sanitize)
result=$(echo "$filtered" | process)
```

Model as:
- `bash_pipes` tracks each `|` connection
- `bash_subshells` tracks `$(...)` captures
- Variable assignments link subshell output to variable

This enables taint tracking: if `user_input` is tainted, trace through pipes to see if it reaches dangerous sinks.

### Decision 8: Quoting analysis

```bash
# Safe - double quoted, expansion happens but word splitting doesn't
rm "$file"

# Unsafe - unquoted, word splitting + globbing can occur
rm $file

# Safe - single quoted, no expansion
echo '$file'

# Complex - mixed quoting
cmd "prefix${var}suffix"
```

Track quote context for each variable expansion to detect word-splitting vulnerabilities.

### Decision 9: tree-sitter-bash Node Type Mapping

The following tree-sitter node types map to extraction entities:

| Entity | tree-sitter Node Type | Key Children |
|--------|----------------------|--------------|
| Function | `function_definition` | `name` (word), `body` (compound_statement) |
| Variable assignment | `variable_assignment` | `name` (variable_name), `value` (various) |
| Export/local/declare | `declaration_command` | first child is keyword, rest are assignments |
| Command | `command` | `name` (word), `argument` (word/expansion) |
| Pipeline | `pipeline` | multiple `command` children |
| Command substitution | `command_substitution` | `$()` or backtick style, contains commands |
| Variable expansion | `simple_expansion` or `expansion` | `$var` or `${var}` |
| Redirection | `file_redirect` | operator (`>`, `<`), destination |
| Here document | `heredoc_redirect` | `<<EOF` style |
| If statement | `if_statement` | `condition`, `consequence`, `alternative` |
| For loop | `for_statement` | `variable`, `value`, `body` |
| While loop | `while_statement` | `condition`, `body` |
| Case statement | `case_statement` | `value`, `case_item` children |

**Verified via:** `tree-sitter parse test.sh` with tree-sitter-bash grammar.

**Function style detection:**
```python
def get_function_style(node):
    # Check if 'function' keyword present
    for child in node.children:
        if child.type == 'function' or (child.type == 'word' and child.text == b'function'):
            # Check for parens
            has_parens = any(c.type == '(' for c in node.children)
            return 'function' if has_parens else 'function_no_parens'
    return 'posix'  # name() style
```

### Decision 10: Shebang Detection Architecture

**Problem:** Current `ExtractorRegistry.get_extractor()` (extractors/__init__.py:120-129) uses extension only. Extensionless Bash scripts need shebang detection.

**Solution:** Add shebang detection in file discovery phase before extractor routing.

**Implementation location:** `theauditor/indexer/core.py` or `file_iterator.py`

```python
# In file iteration, before extractor lookup:
BASH_SHEBANGS = [
    b'#!/bin/bash',
    b'#!/usr/bin/env bash',
    b'#!/bin/sh',
    b'#!/usr/bin/env sh',
]

def detect_bash_shebang(file_path: Path) -> bool:
    """Check if extensionless file has bash shebang."""
    if file_path.suffix:  # Has extension, skip
        return False
    try:
        with open(file_path, 'rb') as f:
            first_line = f.readline(128)
        return any(first_line.startswith(shebang) for shebang in BASH_SHEBANGS)
    except (IOError, OSError):
        return False

# In file enumeration:
if detect_bash_shebang(file_path):
    file_info['detected_language'] = 'bash'
    file_info['extension'] = '.sh'  # Virtual extension for routing
```

**Extractor modification:** BashExtractor checks `file_info.get('detected_language')` in addition to extension.

### Decision 11: Storage Wiring Pattern

**Pattern from existing code:** See `theauditor/indexer/storage/python_storage.py:14-44`

```python
# theauditor/indexer/storage/bash_storage.py
from .base import BaseStorage


class BashStorage(BaseStorage):
    """Bash-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        # Map extraction data keys to handler methods
        self.handlers = {
            "bash_functions": self._store_bash_functions,
            "bash_variables": self._store_bash_variables,
            "bash_sources": self._store_bash_sources,
            "bash_commands": self._store_bash_commands,
            "bash_pipes": self._store_bash_pipes,
            "bash_subshells": self._store_bash_subshells,
            "bash_redirections": self._store_bash_redirections,
        }

    # =========================================================================
    # HANDLER 1: bash_functions
    # =========================================================================
    def _store_bash_functions(self, file_path: str, bash_functions: list, jsx_pass: bool) -> None:
        """Store Bash function definitions."""
        for func in bash_functions:
            self.db_manager.add_bash_function(
                file_path,
                func.get("line", 0),
                func.get("end_line", 0),
                func.get("name", ""),
                func.get("style", "posix"),
                func.get("body_start_line"),
                func.get("body_end_line"),
            )
            self.counts["bash_functions"] = self.counts.get("bash_functions", 0) + 1

    # =========================================================================
    # HANDLER 2: bash_variables
    # =========================================================================
    def _store_bash_variables(self, file_path: str, bash_variables: list, jsx_pass: bool) -> None:
        """Store Bash variable assignments."""
        for var in bash_variables:
            self.db_manager.add_bash_variable(
                file_path,
                var.get("line", 0),
                var.get("name", ""),
                var.get("scope", "global"),
                var.get("readonly", False),
                var.get("value_expr"),
                var.get("containing_function"),
            )
            self.counts["bash_variables"] = self.counts.get("bash_variables", 0) + 1

    # =========================================================================
    # HANDLER 3: bash_sources
    # =========================================================================
    def _store_bash_sources(self, file_path: str, bash_sources: list, jsx_pass: bool) -> None:
        """Store Bash source/dot statements."""
        for src in bash_sources:
            self.db_manager.add_bash_source(
                file_path,
                src.get("line", 0),
                src.get("sourced_path", ""),
                src.get("syntax", "source"),
                src.get("has_variable_expansion", False),
                src.get("containing_function"),
            )
            self.counts["bash_sources"] = self.counts.get("bash_sources", 0) + 1

    # =========================================================================
    # HANDLER 4: bash_commands (with junction table for args)
    # =========================================================================
    def _store_bash_commands(self, file_path: str, bash_commands: list, jsx_pass: bool) -> None:
        """Store Bash command invocations and their arguments."""
        for cmd in bash_commands:
            line = cmd.get("line", 0)
            self.db_manager.add_bash_command(
                file_path,
                line,
                cmd.get("command_name", ""),
                cmd.get("pipeline_position"),
                cmd.get("containing_function"),
            )
            self.counts["bash_commands"] = self.counts.get("bash_commands", 0) + 1

            # Store arguments in junction table
            for idx, arg in enumerate(cmd.get("args", [])):
                self.db_manager.add_bash_command_arg(
                    file_path,
                    line,  # command_line FK
                    idx,
                    arg.get("value", ""),
                    arg.get("is_quoted", False),
                    arg.get("quote_type", "none"),
                    arg.get("has_expansion", False),
                    arg.get("expansion_vars"),
                )
                self.counts["bash_command_args"] = self.counts.get("bash_command_args", 0) + 1

    # =========================================================================
    # HANDLER 5: bash_pipes
    # =========================================================================
    def _store_bash_pipes(self, file_path: str, bash_pipes: list, jsx_pass: bool) -> None:
        """Store Bash pipeline connections."""
        for pipe in bash_pipes:
            self.db_manager.add_bash_pipe(
                file_path,
                pipe.get("line", 0),
                pipe.get("pipeline_id", 0),
                pipe.get("position", 0),
                pipe.get("command_text", ""),
                pipe.get("containing_function"),
            )
            self.counts["bash_pipes"] = self.counts.get("bash_pipes", 0) + 1

    # =========================================================================
    # HANDLER 6: bash_subshells
    # =========================================================================
    def _store_bash_subshells(self, file_path: str, bash_subshells: list, jsx_pass: bool) -> None:
        """Store Bash command substitutions."""
        for sub in bash_subshells:
            self.db_manager.add_bash_subshell(
                file_path,
                sub.get("line", 0),
                sub.get("syntax", "dollar_paren"),
                sub.get("command_text", ""),
                sub.get("capture_target"),
                sub.get("containing_function"),
            )
            self.counts["bash_subshells"] = self.counts.get("bash_subshells", 0) + 1

    # =========================================================================
    # HANDLER 7: bash_redirections
    # =========================================================================
    def _store_bash_redirections(self, file_path: str, bash_redirections: list, jsx_pass: bool) -> None:
        """Store Bash I/O redirections."""
        for redir in bash_redirections:
            self.db_manager.add_bash_redirection(
                file_path,
                redir.get("line", 0),
                redir.get("direction", "output"),
                redir.get("target", ""),
                redir.get("fd_number"),
                redir.get("containing_function"),
            )
            self.counts["bash_redirections"] = self.counts.get("bash_redirections", 0) + 1
```

**Wiring into DataStorer** (`theauditor/indexer/storage/__init__.py:6-30`):
```python
from .bash_storage import BashStorage

class DataStorer:
    """Routes extracted data to appropriate storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        self.python = PythonStorage(db_manager, counts)
        self.node = NodeStorage(db_manager, counts)
        self.bash = BashStorage(db_manager, counts)  # ADD THIS

        # Merge all handlers
        self.handlers = {
            **self.python.handlers,
            **self.node.handlers,
            **self.bash.handlers,  # ADD THIS
        }
```

**Wiring location:** `theauditor/indexer/orchestrator.py` - add BashStorage to storage handlers list.

### Decision 12: Database Manager Method Pattern

**Pattern from:** `theauditor/indexer/database/base_database.py`

Database manager uses generic batch insertion. Add methods following existing pattern:

```python
# theauditor/indexer/database/bash_database.py
"""Bash-specific database mixin for batch insertion methods."""


class BashDatabaseMixin:
    """Mixin providing add_bash_* methods for DatabaseManager."""

    # =========================================================================
    # METHOD 1: add_bash_function
    # =========================================================================
    def add_bash_function(
        self,
        file: str,
        line: int,
        end_line: int,
        name: str,
        style: str,
        body_start_line: int | None,
        body_end_line: int | None,
    ) -> None:
        """Add a Bash function definition."""
        self._batch_insert("bash_functions", {
            "file": file,
            "line": line,
            "end_line": end_line,
            "name": name,
            "style": style,
            "body_start_line": body_start_line,
            "body_end_line": body_end_line,
        })

    # =========================================================================
    # METHOD 2: add_bash_variable
    # =========================================================================
    def add_bash_variable(
        self,
        file: str,
        line: int,
        name: str,
        scope: str,
        readonly: bool,
        value_expr: str | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash variable assignment."""
        self._batch_insert("bash_variables", {
            "file": file,
            "line": line,
            "name": name,
            "scope": scope,
            "readonly": 1 if readonly else 0,
            "value_expr": value_expr,
            "containing_function": containing_function,
        })

    # =========================================================================
    # METHOD 3: add_bash_source
    # =========================================================================
    def add_bash_source(
        self,
        file: str,
        line: int,
        sourced_path: str,
        syntax: str,
        has_variable_expansion: bool,
        containing_function: str | None,
    ) -> None:
        """Add a Bash source/dot statement."""
        self._batch_insert("bash_sources", {
            "file": file,
            "line": line,
            "sourced_path": sourced_path,
            "syntax": syntax,
            "has_variable_expansion": 1 if has_variable_expansion else 0,
            "containing_function": containing_function,
        })

    # =========================================================================
    # METHOD 4: add_bash_command
    # =========================================================================
    def add_bash_command(
        self,
        file: str,
        line: int,
        command_name: str,
        pipeline_position: int | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash command invocation."""
        self._batch_insert("bash_commands", {
            "file": file,
            "line": line,
            "command_name": command_name,
            "pipeline_position": pipeline_position,
            "containing_function": containing_function,
        })

    # =========================================================================
    # METHOD 5: add_bash_command_arg
    # =========================================================================
    def add_bash_command_arg(
        self,
        file: str,
        command_line: int,
        arg_index: int,
        arg_value: str,
        is_quoted: bool,
        quote_type: str,
        has_expansion: bool,
        expansion_vars: str | None,
    ) -> None:
        """Add a Bash command argument."""
        self._batch_insert("bash_command_args", {
            "file": file,
            "command_line": command_line,
            "arg_index": arg_index,
            "arg_value": arg_value,
            "is_quoted": 1 if is_quoted else 0,
            "quote_type": quote_type,
            "has_expansion": 1 if has_expansion else 0,
            "expansion_vars": expansion_vars,
        })

    # =========================================================================
    # METHOD 6: add_bash_pipe
    # =========================================================================
    def add_bash_pipe(
        self,
        file: str,
        line: int,
        pipeline_id: int,
        position: int,
        command_text: str,
        containing_function: str | None,
    ) -> None:
        """Add a Bash pipeline component."""
        self._batch_insert("bash_pipes", {
            "file": file,
            "line": line,
            "pipeline_id": pipeline_id,
            "position": position,
            "command_text": command_text,
            "containing_function": containing_function,
        })

    # =========================================================================
    # METHOD 7: add_bash_subshell
    # =========================================================================
    def add_bash_subshell(
        self,
        file: str,
        line: int,
        syntax: str,
        command_text: str,
        capture_target: str | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash command substitution."""
        self._batch_insert("bash_subshells", {
            "file": file,
            "line": line,
            "syntax": syntax,
            "command_text": command_text,
            "capture_target": capture_target,
            "containing_function": containing_function,
        })

    # =========================================================================
    # METHOD 8: add_bash_redirection
    # =========================================================================
    def add_bash_redirection(
        self,
        file: str,
        line: int,
        direction: str,
        target: str,
        fd_number: int | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash I/O redirection."""
        self._batch_insert("bash_redirections", {
            "file": file,
            "line": line,
            "direction": direction,
            "target": target,
            "fd_number": fd_number,
            "containing_function": containing_function,
        })
```

**Wiring into DatabaseManager** (`theauditor/indexer/database/__init__.py:17-27`):
```python
from .bash_database import BashDatabaseMixin

class DatabaseManager(
    BaseDatabaseMixin,
    PythonDatabaseMixin,
    NodeDatabaseMixin,
    BashDatabaseMixin,  # ADD THIS
    # ... other mixins
):
    """Unified database manager combining all language mixins."""
    pass
```

**Batch insertion pattern:** `_batch_insert()` accumulates rows and flushes at batch_size threshold.

### Decision 13: Schema Python Definition Pattern

**Pattern from:** `theauditor/indexer/schemas/python_schema.py`

```python
# theauditor/indexer/schemas/bash_schema.py
from .utils import Column, TableSchema

# =============================================================================
# TABLE 1: bash_functions - Function definitions
# =============================================================================
BASH_FUNCTIONS = TableSchema(
    name="bash_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("style", "TEXT", nullable=False, default="'posix'"),  # 'function'|'posix'|'function_no_parens'
        Column("body_start_line", "INTEGER", nullable=True),
        Column("body_end_line", "INTEGER", nullable=True),
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_bash_functions_file", ["file"]),
        ("idx_bash_functions_name", ["name"]),
    ],
)

# =============================================================================
# TABLE 2: bash_variables - Variable assignments
# =============================================================================
BASH_VARIABLES = TableSchema(
    name="bash_variables",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("scope", "TEXT", nullable=False, default="'global'"),  # 'global'|'local'|'export'
        Column("readonly", "INTEGER", nullable=False, default="0"),  # 0=false, 1=true
        Column("value_expr", "TEXT", nullable=True),  # RHS expression, NULL if declaration only
        Column("containing_function", "TEXT", nullable=True),  # NULL for global scope
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_bash_variables_file", ["file"]),
        ("idx_bash_variables_name", ["name"]),
        ("idx_bash_variables_scope", ["scope"]),
    ],
)

# =============================================================================
# TABLE 3: bash_sources - Source/dot statements
# =============================================================================
BASH_SOURCES = TableSchema(
    name="bash_sources",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("sourced_path", "TEXT", nullable=False),  # Path being sourced
        Column("syntax", "TEXT", nullable=False, default="'source'"),  # 'source'|'dot'
        Column("has_variable_expansion", "INTEGER", nullable=False, default="0"),  # Path contains $VAR
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_bash_sources_file", ["file"]),
        ("idx_bash_sources_sourced_path", ["sourced_path"]),
    ],
)

# =============================================================================
# TABLE 4: bash_commands - Command invocations
# =============================================================================
BASH_COMMANDS = TableSchema(
    name="bash_commands",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("command_name", "TEXT", nullable=False),  # First word of command
        Column("pipeline_position", "INTEGER", nullable=True),  # NULL if not in pipeline, 0-indexed
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "pipeline_position"],
    indexes=[
        ("idx_bash_commands_file", ["file"]),
        ("idx_bash_commands_name", ["command_name"]),
    ],
)

# =============================================================================
# TABLE 5: bash_command_args - Command arguments (junction table)
# =============================================================================
BASH_COMMAND_ARGS = TableSchema(
    name="bash_command_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("command_line", "INTEGER", nullable=False),  # FK to bash_commands.line
        Column("arg_index", "INTEGER", nullable=False),  # 0-indexed position
        Column("arg_value", "TEXT", nullable=False),  # Argument text
        Column("is_quoted", "INTEGER", nullable=False, default="0"),  # 0=unquoted, 1=quoted
        Column("quote_type", "TEXT", nullable=False, default="'none'"),  # 'none'|'single'|'double'
        Column("has_expansion", "INTEGER", nullable=False, default="0"),  # Contains $VAR
        Column("expansion_vars", "TEXT", nullable=True),  # Comma-separated var names if has_expansion
    ],
    primary_key=["file", "command_line", "arg_index"],
    indexes=[
        ("idx_bash_command_args_file_line", ["file", "command_line"]),
        ("idx_bash_command_args_expansion", ["has_expansion"]),
    ],
)

# =============================================================================
# TABLE 6: bash_pipes - Pipeline connections
# =============================================================================
BASH_PIPES = TableSchema(
    name="bash_pipes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("pipeline_id", "INTEGER", nullable=False),  # Groups commands in same pipeline
        Column("position", "INTEGER", nullable=False),  # 0-indexed position in pipeline
        Column("command_text", "TEXT", nullable=False),  # Full command text at this position
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "pipeline_id", "position"],
    indexes=[
        ("idx_bash_pipes_file", ["file"]),
        ("idx_bash_pipes_pipeline", ["file", "pipeline_id"]),
    ],
)

# =============================================================================
# TABLE 7: bash_subshells - Command substitutions
# =============================================================================
BASH_SUBSHELLS = TableSchema(
    name="bash_subshells",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("syntax", "TEXT", nullable=False, default="'dollar_paren'"),  # 'dollar_paren'|'backtick'
        Column("command_text", "TEXT", nullable=False),  # Content inside $() or ``
        Column("capture_target", "TEXT", nullable=True),  # Variable capturing output, if any
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_bash_subshells_file", ["file"]),
        ("idx_bash_subshells_capture", ["capture_target"]),
    ],
)

# =============================================================================
# TABLE 8: bash_redirections - I/O redirections
# =============================================================================
BASH_REDIRECTIONS = TableSchema(
    name="bash_redirections",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("direction", "TEXT", nullable=False),  # 'input'|'output'|'append'|'heredoc'|'herestring'|'stderr'
        Column("target", "TEXT", nullable=False),  # File path or heredoc delimiter
        Column("fd_number", "INTEGER", nullable=True),  # File descriptor number (e.g., 2 for stderr)
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "direction"],
    indexes=[
        ("idx_bash_redirections_file", ["file"]),
        ("idx_bash_redirections_direction", ["direction"]),
    ],
)

# =============================================================================
# EXPORT: All Bash tables
# =============================================================================
BASH_TABLES = {
    "bash_functions": BASH_FUNCTIONS,
    "bash_variables": BASH_VARIABLES,
    "bash_sources": BASH_SOURCES,
    "bash_commands": BASH_COMMANDS,
    "bash_command_args": BASH_COMMAND_ARGS,
    "bash_pipes": BASH_PIPES,
    "bash_subshells": BASH_SUBSHELLS,
    "bash_redirections": BASH_REDIRECTIONS,
}
```

**Registration:** Add to `theauditor/indexer/schema.py:15-24`:
```python
from .schemas.bash_schema import BASH_TABLES

TABLES: dict[str, TableSchema] = {
    **CORE_TABLES,
    **BASH_TABLES,  # Add this line
    # ... rest
}
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Heredocs are complex to parse | tree-sitter handles them, extract as opaque strings |
| Array syntax is bash-specific | Support common patterns, document limitations |
| Sourced files may not exist | Store path as-is, note if resolution fails |
| Dynamic command construction | Flag as potential injection, can't fully analyze |
| Aliases not visible | Document limitation (aliases are runtime) |

## Migration Plan

1. **Phase 1** (Core): Functions, variables, commands, sources → queryable data
2. **Phase 2** (Data flow): Pipes, subshells, redirections → taint tracking possible
3. **Phase 3** (Security): Rules for injection, credentials, safety flags

Each phase is independently valuable. Phase 1 alone lets you query "what commands does this script run?"

### Decision 14: Graph Strategy for Bash Data Flow

> **Spec reference**: `specs/graph/spec.md` - BashPipeStrategy registration

**Problem:** Existing graph strategies (`python_orm.py`, `node_orm.py`) handle language-specific data flow. Bash needs a strategy for pipes and source statements.

**Solution:** Create `BashPipeStrategy` extending `GraphStrategy` base class.

**Pattern from:** `theauditor/graph/strategies/python_orm.py:316-380`

```python
# theauditor/graph/strategies/bash_pipes.py
import sqlite3
from typing import Any

from .base import GraphStrategy


class BashPipeStrategy(GraphStrategy):
    """Bash-specific DFG strategy for pipe chains and source statements."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build pipe flow edges and source include edges.

        Creates three edge types:
        1. pipe_flow: stdout of command N -> stdin of command N+1
        2. source_include: source statement -> sourced file
        3. subshell_capture: subshell output -> capture variable
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        nodes = {}
        edges = []
        stats = {
            "pipe_edges": 0,
            "source_edges": 0,
            "capture_edges": 0,
        }

        # =====================================================================
        # 1. Build pipe flow edges
        # =====================================================================
        cursor.execute("""
            SELECT file, line, pipeline_id, position, command_text, containing_function
            FROM bash_pipes
            ORDER BY file, pipeline_id, position
        """)

        current_pipeline = None
        prev_node_id = None

        for row in cursor.fetchall():
            file, line, pipeline_id, position, command_text, containing_function = row
            node_id = f"bash:pipe:{file}:{line}:{position}"

            # Reset on new pipeline
            if (file, pipeline_id) != current_pipeline:
                current_pipeline = (file, pipeline_id)
                prev_node_id = None

            # Create node for this pipeline position
            nodes[node_id] = {
                "id": node_id,
                "type": "bash_pipe_command",
                "file": file,
                "line": line,
                "label": command_text[:50] if len(command_text) > 50 else command_text,
                "containing_function": containing_function,
            }

            # Create edge from previous command to this one
            if prev_node_id:
                edges.append({
                    "source": prev_node_id,
                    "target": node_id,
                    "edge_type": "pipe_flow",
                    "label": "|",
                })
                stats["pipe_edges"] += 1

            prev_node_id = node_id

        # =====================================================================
        # 2. Build source include edges
        # =====================================================================
        cursor.execute("""
            SELECT file, line, sourced_path, syntax, has_variable_expansion
            FROM bash_sources
        """)

        for row in cursor.fetchall():
            file, line, sourced_path, syntax, has_variable_expansion = row

            source_node_id = f"bash:source:{file}:{line}"
            target_node_id = f"bash:file:{sourced_path}"

            # Create source statement node
            nodes[source_node_id] = {
                "id": source_node_id,
                "type": "bash_source_statement",
                "file": file,
                "line": line,
                "label": f"{syntax} {sourced_path}",
            }

            # Create target file node (if not already present)
            if target_node_id not in nodes:
                nodes[target_node_id] = {
                    "id": target_node_id,
                    "type": "bash_sourced_file",
                    "file": sourced_path,
                    "line": 0,
                    "label": sourced_path,
                }

            # Create edge linking source to target
            edges.append({
                "source": source_node_id,
                "target": target_node_id,
                "edge_type": "source_include",
                "label": "sources",
                "has_variable_expansion": bool(has_variable_expansion),
            })
            stats["source_edges"] += 1

        # =====================================================================
        # 3. Build subshell capture edges
        # =====================================================================
        cursor.execute("""
            SELECT file, line, syntax, command_text, capture_target
            FROM bash_subshells
            WHERE capture_target IS NOT NULL
        """)

        for row in cursor.fetchall():
            file, line, syntax, command_text, capture_target = row

            subshell_node_id = f"bash:subshell:{file}:{line}"
            variable_node_id = f"bash:var:{file}:{capture_target}"

            # Create subshell node
            nodes[subshell_node_id] = {
                "id": subshell_node_id,
                "type": "bash_subshell",
                "file": file,
                "line": line,
                "label": f"$({command_text[:30]}...)" if len(command_text) > 30 else f"$({command_text})",
                "syntax": syntax,
            }

            # Create variable node (if not already present)
            if variable_node_id not in nodes:
                nodes[variable_node_id] = {
                    "id": variable_node_id,
                    "type": "bash_variable",
                    "file": file,
                    "line": line,
                    "label": f"${capture_target}",
                }

            # Create edge linking subshell output to variable
            edges.append({
                "source": subshell_node_id,
                "target": variable_node_id,
                "edge_type": "subshell_capture",
                "label": "captures to",
            })
            stats["capture_edges"] += 1

        conn.close()

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": stats,
        }
```

**Wiring location:** `theauditor/graph/dfg_builder.py:11-32`

```python
from .strategies.bash_pipes import BashPipeStrategy

# In __init__:
self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    InterceptorStrategy(),
    BashPipeStrategy(),  # ADD THIS
]
```

### Decision 15: Rules Directory Structure

> **Spec reference**: `specs/graph/spec.md` - Bash Rules Wiring

**Problem:** Security rules need a home. Existing pattern is `rules/python/` and `rules/node/`.

**Solution:** Create `rules/bash/` with analyze functions.

**Pattern from:** `theauditor/rules/python/__init__.py`

```python
# theauditor/rules/bash/__init__.py
"""Bash-specific security rules."""

from .injection_analyze import analyze as find_injection_issues
from .quoting_analyze import analyze as find_quoting_issues
from .dangerous_patterns_analyze import analyze as find_dangerous_patterns

__all__ = [
    "find_injection_issues",
    "find_quoting_issues",
    "find_dangerous_patterns",
]
```

**Rule function signature:**

```python
# theauditor/rules/bash/injection_analyze.py
def analyze(cursor: sqlite3.Cursor, config: dict) -> list[dict]:
    """Find command injection vulnerabilities in Bash code."""
    findings = []

    # Query for eval with variable args
    cursor.execute("""
        SELECT c.file, c.line, c.command_name, a.arg_value, a.has_expansion
        FROM bash_commands c
        JOIN bash_command_args a ON c.file = a.file AND c.line = a.command_line
        WHERE c.command_name = 'eval'
          AND a.has_expansion = 1
    """)

    for row in cursor.fetchall():
        findings.append({
            "file": row[0],
            "line": row[1],
            "rule": "bash-command-injection",
            "severity": "critical",
            "message": f"eval with variable expansion: {row[3]}",
            "category": "injection",
        })

    return findings
```

### Decision 16: Taint Sources and Sinks

> **Spec reference**: `specs/graph/spec.md` - Bash Taint Sources/Sinks

**Bash-specific taint sources:**

| Source | Detection Method |
|--------|-----------------|
| `$1`, `$2`, ..., `$@`, `$*` | Variable name matches positional pattern |
| `read VAR` | Command is `read`, VAR is tainted |
| `$(curl ...)` | Subshell captures network command output |
| `$QUERY_STRING` | CGI environment variable patterns |

**Bash-specific taint sinks:**

| Sink | Severity | Detection Query |
|------|----------|-----------------|
| `eval $VAR` | Critical | bash_commands.command_name='eval' + unquoted expansion |
| `$VAR` as command | Critical | bash_commands.command_name starts with $ |
| `rm $VAR` | High | Dangerous command with unquoted path arg |
| `source $VAR` | Critical | Source with variable path |

### Decision 17: flush_order Integration

> **Spec reference**: `specs/graph/spec.md` - Database flush_order

**Problem:** `base_database.py:193-332` has an explicit flush order for all tables. Bash tables must be added.

**Solution:** Add bash_* tables after Python tables, before findings.

**Location:** `theauditor/indexer/database/base_database.py:250` (approximate)

```python
flush_order = [
    # ... existing entries ...
    ("python_control_statements", "INSERT"),
    # ADD BASH TABLES HERE:
    ("bash_functions", "INSERT"),
    ("bash_variables", "INSERT"),
    ("bash_sources", "INSERT"),
    ("bash_commands", "INSERT"),
    ("bash_command_args", "INSERT"),
    ("bash_pipes", "INSERT"),
    ("bash_subshells", "INSERT"),
    ("bash_redirections", "INSERT"),
    # ... continue with sql_query_tables, etc. ...
]
```

**Rationale:** Bash tables have no cross-dependencies with Python/Node tables. Insert order within Bash is: base tables first, then junction table (`bash_command_args` depends on `bash_commands` via file+line).

### Decision 18: Tree-sitter Extraction Walker Pattern

> **Spec reference**: `specs/indexer/spec.md` - Function/Variable/Source/Command extraction scenarios

**Problem:** bash_impl.py needs to walk tree-sitter AST and extract data into dict format for storage handlers. No example pattern existed.

**Solution:** Create recursive walker with scope tracking, following python_impl.py pattern.

**Pattern from:** `theauditor/ast_extractors/python_impl.py`

```python
# theauditor/ast_extractors/bash_impl.py
"""Bash AST extraction using tree-sitter-bash."""

from tree_sitter_language_pack import get_language, get_parser


class BashExtractor:
    """Extract Bash constructs from parsed AST."""

    def __init__(self):
        self.parser = get_parser("bash")
        self.language = get_language("bash")

    def extract(self, source_code: bytes, file_path: str) -> dict:
        """Extract all Bash constructs from source code.

        Returns dict with keys matching storage handler expectations:
        - bash_functions: list[dict]
        - bash_variables: list[dict]
        - bash_sources: list[dict]
        - bash_commands: list[dict]  (each with 'args' sub-list)
        - bash_pipes: list[dict]
        - bash_subshells: list[dict]
        - bash_redirections: list[dict]
        """
        tree = self.parser.parse(source_code)
        root = tree.root_node

        # Result containers
        result = {
            "bash_functions": [],
            "bash_variables": [],
            "bash_sources": [],
            "bash_commands": [],
            "bash_pipes": [],
            "bash_subshells": [],
            "bash_redirections": [],
        }

        # State tracking
        self._scope_stack = []  # Stack of function names for containing_function
        self._pipeline_counter = 0  # Unique ID for each pipeline

        # Walk the tree
        self._walk(root, source_code, result)

        return result

    def _walk(self, node, source: bytes, result: dict) -> None:
        """Recursively walk AST nodes and extract constructs."""

        # =================================================================
        # FUNCTION DEFINITIONS
        # =================================================================
        if node.type == "function_definition":
            func_data = self._extract_function(node, source)
            result["bash_functions"].append(func_data)

            # Enter function scope
            self._scope_stack.append(func_data["name"])

            # Walk children (body will be processed with this function in scope)
            for child in node.children:
                self._walk(child, source, result)

            # Exit function scope
            self._scope_stack.pop()
            return  # Don't double-process children

        # =================================================================
        # VARIABLE ASSIGNMENTS
        # =================================================================
        if node.type == "variable_assignment":
            var_data = self._extract_variable(node, source)
            result["bash_variables"].append(var_data)

        # =================================================================
        # DECLARATION COMMANDS (export, local, readonly, declare)
        # =================================================================
        if node.type == "declaration_command":
            var_list = self._extract_declaration(node, source)
            result["bash_variables"].extend(var_list)

        # =================================================================
        # COMMANDS (including source/dot)
        # =================================================================
        if node.type == "command":
            cmd_data = self._extract_command(node, source)

            # Check if it's a source statement
            if cmd_data["command_name"] in ("source", "."):
                src_data = self._convert_to_source(cmd_data, node, source)
                result["bash_sources"].append(src_data)
            else:
                result["bash_commands"].append(cmd_data)

        # =================================================================
        # PIPELINES
        # =================================================================
        if node.type == "pipeline":
            pipe_list = self._extract_pipeline(node, source)
            result["bash_pipes"].extend(pipe_list)
            self._pipeline_counter += 1
            # Don't recurse into pipeline children - already processed
            return

        # =================================================================
        # COMMAND SUBSTITUTIONS
        # =================================================================
        if node.type == "command_substitution":
            sub_data = self._extract_subshell(node, source)
            result["bash_subshells"].append(sub_data)

        # =================================================================
        # REDIRECTIONS
        # =================================================================
        if node.type in ("file_redirect", "heredoc_redirect", "herestring_redirect"):
            redir_data = self._extract_redirection(node, source)
            result["bash_redirections"].append(redir_data)

        # Recurse into children
        for child in node.children:
            self._walk(child, source, result)

    # =====================================================================
    # EXTRACTION HELPERS
    # =====================================================================

    def _extract_function(self, node, source: bytes) -> dict:
        """Extract function definition data."""
        name = ""
        style = "posix"
        body_start = None
        body_end = None

        for child in node.children:
            if child.type == "word":
                # Check if it's 'function' keyword or function name
                text = source[child.start_byte:child.end_byte].decode("utf-8")
                if text == "function":
                    style = "function"
                else:
                    name = text
            elif child.type == "function":  # 'function' keyword token
                style = "function"
            elif child.type == "compound_statement":
                body_start = child.start_point[0] + 1  # 1-indexed
                body_end = child.end_point[0] + 1

        # Check for parens to distinguish function styles
        has_parens = any(c.type == "(" for c in node.children)
        if style == "function" and not has_parens:
            style = "function_no_parens"

        return {
            "line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "name": name,
            "style": style,
            "body_start_line": body_start,
            "body_end_line": body_end,
        }

    def _extract_variable(self, node, source: bytes) -> dict:
        """Extract variable assignment data."""
        name = ""
        value_expr = None

        for child in node.children:
            if child.type == "variable_name":
                name = source[child.start_byte:child.end_byte].decode("utf-8")
            elif child.type not in ("=", "variable_name"):
                # Everything after = is the value expression
                value_expr = source[child.start_byte:child.end_byte].decode("utf-8")

        return {
            "line": node.start_point[0] + 1,
            "name": name,
            "scope": "global",
            "readonly": False,
            "value_expr": value_expr,
            "containing_function": self._scope_stack[-1] if self._scope_stack else None,
        }

    def _extract_declaration(self, node, source: bytes) -> list[dict]:
        """Extract export/local/readonly/declare statements."""
        results = []
        keyword = ""
        scope = "global"
        readonly = False

        for child in node.children:
            if child.type == "word":
                text = source[child.start_byte:child.end_byte].decode("utf-8")
                if text == "export":
                    scope = "export"
                    keyword = text
                elif text == "local":
                    scope = "local"
                    keyword = text
                elif text == "readonly":
                    readonly = True
                    keyword = text
                elif text == "declare":
                    keyword = text
            elif child.type == "variable_assignment":
                var_data = self._extract_variable(child, source)
                var_data["scope"] = scope
                var_data["readonly"] = readonly
                results.append(var_data)

        return results

    def _extract_command(self, node, source: bytes) -> dict:
        """Extract command invocation data."""
        command_name = ""
        args = []
        arg_index = 0

        for child in node.children:
            if child.type == "command_name" or (child.type == "word" and not command_name):
                # First word is command name
                if child.type == "command_name":
                    # Get the actual word inside command_name
                    for sub in child.children:
                        if sub.type == "word":
                            command_name = source[sub.start_byte:sub.end_byte].decode("utf-8")
                            break
                else:
                    command_name = source[child.start_byte:child.end_byte].decode("utf-8")
            elif child.type in ("word", "string", "raw_string", "expansion", "simple_expansion",
                                "concatenation", "command_substitution"):
                # This is an argument
                arg_data = self._extract_argument(child, source, arg_index)
                args.append(arg_data)
                arg_index += 1

        return {
            "line": node.start_point[0] + 1,
            "command_name": command_name,
            "pipeline_position": None,  # Set by pipeline extractor if applicable
            "containing_function": self._scope_stack[-1] if self._scope_stack else None,
            "args": args,
        }

    def _extract_argument(self, node, source: bytes, index: int) -> dict:
        """Extract command argument data with quoting analysis."""
        value = source[node.start_byte:node.end_byte].decode("utf-8")
        is_quoted = node.type in ("string", "raw_string")
        quote_type = "none"
        has_expansion = False
        expansion_vars = []

        if node.type == "string":
            quote_type = "double"
        elif node.type == "raw_string":
            quote_type = "single"

        # Check for expansions
        self._find_expansions(node, source, expansion_vars)
        has_expansion = len(expansion_vars) > 0

        return {
            "value": value,
            "is_quoted": is_quoted,
            "quote_type": quote_type,
            "has_expansion": has_expansion,
            "expansion_vars": ",".join(expansion_vars) if expansion_vars else None,
        }

    def _find_expansions(self, node, source: bytes, expansion_vars: list) -> None:
        """Recursively find variable expansions in a node."""
        if node.type == "simple_expansion":
            # $VAR style
            var_name = source[node.start_byte + 1:node.end_byte].decode("utf-8")
            expansion_vars.append(var_name)
        elif node.type == "expansion":
            # ${VAR} style - find variable_name child
            for child in node.children:
                if child.type == "variable_name":
                    var_name = source[child.start_byte:child.end_byte].decode("utf-8")
                    expansion_vars.append(var_name)
                    break

        for child in node.children:
            self._find_expansions(child, source, expansion_vars)

    def _extract_pipeline(self, node, source: bytes) -> list[dict]:
        """Extract pipeline components."""
        results = []
        position = 0

        for child in node.children:
            if child.type == "command":
                cmd_text = source[child.start_byte:child.end_byte].decode("utf-8")
                results.append({
                    "line": child.start_point[0] + 1,
                    "pipeline_id": self._pipeline_counter,
                    "position": position,
                    "command_text": cmd_text,
                    "containing_function": self._scope_stack[-1] if self._scope_stack else None,
                })
                position += 1

        return results

    def _extract_subshell(self, node, source: bytes) -> dict:
        """Extract command substitution data."""
        # Determine syntax from node text
        text = source[node.start_byte:node.end_byte].decode("utf-8")
        syntax = "backtick" if text.startswith("`") else "dollar_paren"

        # Get inner command text (strip $() or ``)
        if syntax == "dollar_paren":
            command_text = text[2:-1]  # Strip $( and )
        else:
            command_text = text[1:-1]  # Strip ` and `

        # Check if this is captured to a variable (parent is variable_assignment)
        capture_target = None
        parent = node.parent
        if parent and parent.type == "variable_assignment":
            for child in parent.children:
                if child.type == "variable_name":
                    capture_target = source[child.start_byte:child.end_byte].decode("utf-8")
                    break

        return {
            "line": node.start_point[0] + 1,
            "syntax": syntax,
            "command_text": command_text,
            "capture_target": capture_target,
            "containing_function": self._scope_stack[-1] if self._scope_stack else None,
        }

    def _extract_redirection(self, node, source: bytes) -> dict:
        """Extract I/O redirection data."""
        direction = "output"
        target = ""
        fd_number = None

        for child in node.children:
            if child.type == "file_descriptor":
                fd_number = int(source[child.start_byte:child.end_byte].decode("utf-8"))
            elif child.type in (">", ">>"):
                direction = "append" if child.type == ">>" else "output"
            elif child.type == "<":
                direction = "input"
            elif child.type == "word":
                target = source[child.start_byte:child.end_byte].decode("utf-8")

        # Handle heredoc/herestring
        if node.type == "heredoc_redirect":
            direction = "heredoc"
            # Find delimiter
            for child in node.children:
                if child.type == "heredoc_start":
                    target = source[child.start_byte:child.end_byte].decode("utf-8")
        elif node.type == "herestring_redirect":
            direction = "herestring"

        # Handle stderr (fd 2)
        if fd_number == 2:
            direction = "stderr"

        return {
            "line": node.start_point[0] + 1,
            "direction": direction,
            "target": target,
            "fd_number": fd_number,
            "containing_function": self._scope_stack[-1] if self._scope_stack else None,
        }

    def _convert_to_source(self, cmd_data: dict, node, source: bytes) -> dict:
        """Convert a source/dot command to bash_sources format."""
        sourced_path = ""
        has_variable_expansion = False

        # Get the first argument as the sourced path
        if cmd_data["args"]:
            sourced_path = cmd_data["args"][0]["value"]
            has_variable_expansion = cmd_data["args"][0]["has_expansion"]

        return {
            "line": cmd_data["line"],
            "sourced_path": sourced_path,
            "syntax": "dot" if cmd_data["command_name"] == "." else "source",
            "has_variable_expansion": has_variable_expansion,
            "containing_function": cmd_data["containing_function"],
        }
```

**Key patterns:**
1. **Scope stack**: Track containing function via `_scope_stack` list
2. **Pipeline counter**: Unique ID per pipeline for grouping
3. **Recursive walk**: `_walk()` handles all node types with early returns for container nodes
4. **Quoting analysis**: Check node.type for string/raw_string to determine quote context
5. **Expansion detection**: Recursively find simple_expansion and expansion nodes

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Heredocs are complex to parse | tree-sitter handles them, extract as opaque strings |
| Array syntax is bash-specific | Support common patterns, document limitations |
| Sourced files may not exist | Store path as-is, note if resolution fails |
| Dynamic command construction | Flag as potential injection, can't fully analyze |
| Aliases not visible | Document limitation (aliases are runtime) |
| Graph strategy may be heavyweight | Start minimal, expand based on actual taint needs |

## Migration Plan

1. **Phase 1** (Core): Functions, variables, commands, sources -> queryable data
   - Delivers: `bash_*` tables populated, basic queries work
   - Spec: `specs/indexer/spec.md`

2. **Phase 2** (Data flow): Pipes, subshells, redirections + graph strategy
   - Delivers: `BashPipeStrategy` creates DFG edges, taint tracking possible
   - Spec: `specs/indexer/spec.md` + `specs/graph/spec.md`

3. **Phase 3** (Security): Rules for injection, credentials, safety flags
   - Delivers: `rules/bash/` directory, findings in `findings_consolidated`
   - Spec: `specs/graph/spec.md`

Each phase is independently valuable. Phase 1 alone lets you query "what commands does this script run?"

## Open Questions

1. Should we track shell options (`set -e`, `shopt -s`)?
   - Tentative: Yes, in a `bash_options` table - important for security analysis

2. Should we handle here-strings (`<<<`)?
   - Tentative: Yes, treat like redirections

3. Track arithmetic expressions (`$(( ))`, `$[ ]`)?
   - Tentative: Low priority, rarely security-relevant

4. Should BashPipeStrategy query bash_subshells for capture edges?
   - Tentative: Yes, subshell capture is a form of data flow
