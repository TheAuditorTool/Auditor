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

    def _store_bash_functions(self, file_path: str, bash_functions: list, jsx_pass: bool):
        """Store Bash function definitions."""
        for func in bash_functions:
            self.db_manager.add_bash_function(
                file_path,
                func.get("line", 0),
                func.get("end_line", 0),
                func.get("name", ""),
                func.get("style", "posix"),
                func.get("body_start_line", 0),
                func.get("body_end_line", 0),
            )
            self.counts["bash_functions"] = self.counts.get("bash_functions", 0) + 1
```

**Wiring location:** `theauditor/indexer/orchestrator.py` - add BashStorage to storage handlers list.

### Decision 12: Database Manager Method Pattern

**Pattern from:** `theauditor/indexer/database/base_database.py`

Database manager uses generic batch insertion. Add methods following existing pattern:

```python
# In theauditor/indexer/database/repo_database.py (or equivalent)

def add_bash_function(self, file: str, line: int, end_line: int,
                      name: str, style: str, body_start: int, body_end: int):
    """Add a Bash function definition."""
    self._batch_insert("bash_functions", {
        "file": file,
        "line": line,
        "end_line": end_line,
        "name": name,
        "style": style,
        "body_start_line": body_start,
        "body_end_line": body_end,
    })

def add_bash_variable(self, file: str, line: int, name: str,
                      scope: str, readonly: bool, value_expr: str,
                      containing_function: str | None):
    """Add a Bash variable assignment."""
    self._batch_insert("bash_variables", {
        "file": file,
        "line": line,
        "name": name,
        "scope": scope,
        "readonly": readonly,
        "value_expr": value_expr,
        "containing_function": containing_function,
    })

# Similar methods for: add_bash_source, add_bash_command,
# add_bash_command_arg, add_bash_pipe, add_bash_subshell, add_bash_redirection
```

**Batch insertion pattern:** `_batch_insert()` accumulates rows and flushes at batch_size threshold.

### Decision 13: Schema Python Definition Pattern

**Pattern from:** `theauditor/indexer/schemas/python_schema.py`

```python
# theauditor/indexer/schemas/bash_schema.py
from .utils import Column, TableSchema

BASH_FUNCTIONS = TableSchema(
    name="bash_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("style", "TEXT", nullable=False, default="'posix'"),
        Column("body_start_line", "INTEGER"),
        Column("body_end_line", "INTEGER"),
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_bash_functions_file", ["file"]),
        ("idx_bash_functions_name", ["name"]),
    ],
)

# ... similar for other 7 tables ...

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

## Open Questions

1. Should we track shell options (`set -e`, `shopt -s`)?
   - Tentative: Yes, in a `bash_options` table - important for security analysis

2. Should we handle here-strings (`<<<`)?
   - Tentative: Yes, treat like redirections

3. Track arithmetic expressions (`$(( ))`, `$[ ]`)?
   - Tentative: Low priority, rarely security-relevant
