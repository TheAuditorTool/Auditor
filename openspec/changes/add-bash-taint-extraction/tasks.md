## 0. Verification (Pre-Implementation)

**Status**: COMPLETE - See `verification.md` for full details.

- [x] 0.1 Read `theauditor/indexer/extractors/bash.py` - thin wrapper that delegates to bash_impl.py
- [x] 0.2 Read `theauditor/ast_extractors/bash_impl.py` - the ACTUAL extraction logic (823 lines)
- [x] 0.3 Read `theauditor/graph/strategies/bash_pipes.py` - understand existing pipe flow edges
- [x] 0.4 Read `theauditor/rules/bash/injection_analyze.py` - confirmed no `register_taint_patterns()` exists
- [x] 0.5 Query database to confirm 0 Bash rows in language-agnostic tables

**Key findings from verification:**
- Schema locations corrected (were pointing to wrong file/lines)
- `func_params` uses `function_line` NOT `line` column
- All schemas have additional nullable columns that must be included

## 1. Assignment Mapping (bash_variables -> assignments)

**Context**: `bash_impl.py` ALREADY extracts variables to `bash_variables`. We need to MAP this to `assignments` format.

- [ ] 1.1 Add `_map_variables_to_assignments()` method in `theauditor/ast_extractors/bash_impl.py`
- [ ] 1.2 Map existing `bash_variables` dict keys to `assignments` schema:
  - `name` -> `target_var`
  - `value_expr` -> `source_expr`
  - `line` -> `line`
  - `containing_function` -> `in_function`
- [ ] 1.3 Handle `read` command: detect in bash_commands, create assignment with source="stdin"
- [ ] 1.4 Add `assignments` key to `extract()` return dict
- [ ] 1.5 Add logging: `logger.debug(f"Bash: mapped {count} assignments from {file}")`

**Implementation Details:**
```python
# In bash_impl.py BashExtractor class
def _map_variables_to_assignments(self) -> list[dict]:
    """Map bash_variables to language-agnostic assignments format.

    Schema: theauditor/indexer/schemas/core_schema.py:92-113
    Columns: file, line, col, target_var, source_expr, in_function, property_path
    """
    assignments = []
    for var in self.variables:
        assignments.append({
            "file": self.file_path,
            "line": var["line"],
            "col": 0,
            "target_var": var["name"],
            "source_expr": var.get("value_expr") or "",
            "in_function": var.get("containing_function") or "global",
            "property_path": None,  # Bash has no property access syntax
        })
    return assignments

# In extract() method, add to return dict:
def extract(self) -> dict[str, Any]:
    self._walk(self.tree.root_node)
    return {
        # ... existing bash_* keys ...
        "assignments": self._map_variables_to_assignments(),
    }
```

## 2. Command Mapping (bash_commands -> function_call_args)

**Context**: `bash_impl.py` ALREADY extracts commands to `bash_commands` with `args` list. We need to MAP this to `function_call_args` format.

- [ ] 2.1 Add `_map_commands_to_function_call_args()` method in `theauditor/ast_extractors/bash_impl.py`
- [ ] 2.2 Map existing `bash_commands` dict keys to `function_call_args` schema:
  - `command_name` -> `callee_function`
  - `args[i].value` -> `argument_expr`
  - `args` index -> `argument_index`
  - `containing_function` -> `caller_function`
- [ ] 2.3 Add `function_call_args` key to `extract()` return dict
- [ ] 2.4 Add logging: `logger.debug(f"Bash: mapped {count} function_call_args from {file}")`

**Implementation Details:**
```python
# In bash_impl.py BashExtractor class
def _map_commands_to_function_call_args(self) -> list[dict]:
    """Map bash_commands to language-agnostic function_call_args format.

    Schema: theauditor/indexer/schemas/core_schema.py:138-162
    Columns: file, line, caller_function, callee_function, argument_index,
             argument_expr, param_name, callee_file_path
    """
    call_args = []
    for cmd in self.commands:
        cmd_name = cmd.get("command_name", "")
        if not cmd_name:  # Skip empty command names (schema CHECK constraint)
            continue
        caller = cmd.get("containing_function") or "global"
        line = cmd.get("line", 0)

        for idx, arg in enumerate(cmd.get("args", [])):
            call_args.append({
                "file": self.file_path,
                "line": line,
                "caller_function": caller,
                "callee_function": cmd_name,
                "argument_index": idx,
                "argument_expr": arg.get("value", ""),
                "param_name": None,       # Bash commands don't have named params
                "callee_file_path": None, # External commands - no file path
            })
    return call_args

# In extract() method, add to return dict:
def extract(self) -> dict[str, Any]:
    self._walk(self.tree.root_node)
    return {
        # ... existing bash_* keys ...
        "function_call_args": self._map_commands_to_function_call_args(),
    }
```

## 3. Positional Parameter Extraction (NEW - func_params)

**Context**: `bash_impl.py` extracts functions but does NOT track which positional params (`$1`, `$2`, etc.) are used. We need to ADD this capability.

- [ ] 3.1 Add `_extract_positional_params()` method in `theauditor/ast_extractors/bash_impl.py`
- [ ] 3.2 Scan function bodies for `$1`, `$2`, `$@`, `$*` usage via tree-sitter `simple_expansion` nodes
- [ ] 3.3 Map to `func_params` schema (node_schema.py:847-862):
  - `function_line`: Line where function is defined (0 for script-level)
  - `function_name`: containing function name or "global"
  - `param_index`: 0, 1, 2, etc. (or -1 for variadic)
  - `param_name`: "$1", "$2", "$@", etc.
  - `param_type`: NULL (Bash is untyped)
- [ ] 3.4 For script-level params, use function_name="global" and function_line=0
- [ ] 3.5 Add `func_params` key to `extract()` return dict
- [ ] 3.6 Add logging: `logger.debug(f"Bash: extracted {count} func_params from {file}")`

**Implementation Details:**
```python
# In bash_impl.py BashExtractor class
def _extract_positional_params(self) -> list[dict]:
    """Extract positional parameter usage from function bodies.

    Schema: theauditor/indexer/schemas/node_schema.py:847-862
    Columns: file, function_line, function_name, param_index, param_name, param_type
    """
    params = []
    seen = set()  # (function_name, param_name) to dedupe

    # Build function line lookup from self.functions
    func_lines = {f["name"]: f["line"] for f in self.functions}

    # Scan all simple_expansion nodes for $1, $2, $@, $*
    def walk_for_params(node, current_func):
        if node.type == "simple_expansion":
            var_name = self._node_text(node)  # e.g., "$1"
            if var_name.startswith("$") and (
                var_name[1:].isdigit() or var_name in ("$@", "$*")
            ):
                func_name = current_func or "global"
                key = (func_name, var_name)
                if key not in seen:
                    seen.add(key)
                    # Determine index
                    if var_name in ("$@", "$*"):
                        idx = -1  # variadic
                    else:
                        idx = int(var_name[1:]) - 1  # $1 -> 0, $2 -> 1

                    # Get function definition line (0 for script-level)
                    func_line = func_lines.get(func_name, 0)

                    params.append({
                        "file": self.file_path,
                        "function_line": func_line,
                        "function_name": func_name,
                        "param_index": idx,
                        "param_name": var_name,
                        "param_type": None,  # Bash is untyped
                    })
        for child in node.children:
            walk_for_params(child, current_func)

    walk_for_params(self.tree.root_node, None)
    return params
```

## 4. Source/Sink Pattern Registration

**Context**: Add `register_taint_patterns()` function to `theauditor/rules/bash/injection_analyze.py` following the Go pattern from `rules/go/injection_analyze.py:306-323`.

- [ ] 4.1 Add `register_taint_patterns(taint_registry)` function to `rules/bash/injection_analyze.py`
- [ ] 4.2 Define `BASH_SOURCES` frozenset with:
  - Positional params: `$1` through `$9`, `$@`, `$*`
  - Input commands: `read`
  - CGI variables: `$QUERY_STRING`, `$REQUEST_URI`, `$HTTP_USER_AGENT`
  - Common input vars: `$INPUT`, `$DATA`, `$PAYLOAD`
- [ ] 4.3 Define `BASH_COMMAND_SINKS` frozenset with:
  - Code execution: `eval`, `exec`, `sh`, `bash`, `source`, `.`
  - Dangerous ops: `rm`, `curl`, `wget`, `xargs`
  - Database clients: `mysql`, `psql`, `sqlite3`
- [ ] 4.4 Register sources with category `"user_input"` and language `"bash"`
- [ ] 4.5 Register sinks with category `"command"` and language `"bash"`

**Implementation Details:**
```python
# Add at end of rules/bash/injection_analyze.py

BASH_SOURCES = frozenset([
    "$1", "$2", "$3", "$4", "$5", "$6", "$7", "$8", "$9",
    "$@", "$*",
    "read",
    "$QUERY_STRING", "$REQUEST_URI",
    "$HTTP_USER_AGENT", "$HTTP_COOKIE",
    "$INPUT", "$DATA", "$PAYLOAD",
])

BASH_COMMAND_SINKS = frozenset([
    "eval", "exec", "sh", "bash", "source", ".",
    "rm", "curl", "wget", "xargs",
    "mysql", "psql", "sqlite3",
])


def register_taint_patterns(taint_registry):
    """Register Bash injection-specific taint patterns.

    Called by orchestrator.collect_rule_patterns() during taint analysis setup.
    Pattern: rules/go/injection_analyze.py:306-323
    """
    for pattern in BASH_SOURCES:
        taint_registry.register_source(pattern, "user_input", "bash")

    for pattern in BASH_COMMAND_SINKS:
        taint_registry.register_sink(pattern, "command", "bash")
```

## 5. Wrapper Integration (bash.py)

**Context**: `theauditor/indexer/extractors/bash.py` is a thin wrapper. It needs to pass through the new keys.

- [ ] 5.1 Verify `result.update(extracted)` in bash.py passes through new keys
- [ ] 5.2 No changes needed if bash_impl.py returns the new keys - bash.py already does `result.update(extracted)`

## 6. End-to-End Verification

- [ ] 6.1 Run `aud full --offline` on TheAuditor (has .sh files in scripts/)
- [ ] 6.2 Query database to verify Bash rows in `assignments`:
  ```sql
  SELECT COUNT(*) FROM assignments WHERE file LIKE '%.sh';
  ```
- [ ] 6.3 Query database to verify Bash rows in `function_call_args`:
  ```sql
  SELECT COUNT(*) FROM function_call_args WHERE file LIKE '%.sh';
  ```
- [ ] 6.4 Run `aud taint` and verify Bash flows appear in results
- [ ] 6.5 Verify TaintRegistry contains Bash patterns:
  ```python
  registry.get_sources_for_language("bash")
  registry.get_sinks_for_language("bash")
  ```

## 7. Logging Verification

**Logging import**: `from theauditor.utils.logging import logger` (wraps loguru)

- [ ] 7.1 Verify bash_impl.py uses `from theauditor.utils.logging import logger`
- [ ] 7.2 Add debug logs for mapping counts:
  ```python
  logger.debug(f"Bash: mapped {len(assignments)} assignments, {len(call_args)} call_args, {len(params)} params")
  ```
- [ ] 7.3 Verify NO bare `print()` statements in modified files
