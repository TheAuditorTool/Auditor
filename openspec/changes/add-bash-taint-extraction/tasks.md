## 0. Verification (Pre-Implementation)

- [ ] 0.1 Read `theauditor/indexer/extractors/bash.py` - confirm current state (no assignments/calls tables)
- [ ] 0.2 Read `theauditor/indexer/extractors/bash_impl.py` - understand existing AST processing
- [ ] 0.3 Read `theauditor/graph/strategies/bash_pipes.py` - understand existing pipe flow edges
- [ ] 0.4 Read `rules/bash/injection_analyze.py` - check if any patterns exist
- [ ] 0.5 Query database to confirm 0 Bash rows in language-agnostic tables

## 1. Assignment Extraction

- [ ] 1.1 Add tree-sitter queries for `variable_assignment` nodes
- [ ] 1.2 Handle simple assignments: `VAR=value`
- [ ] 1.3 Handle command substitution: `VAR=$(command)`
- [ ] 1.4 Handle arithmetic expansion: `VAR=$((expr))`
- [ ] 1.5 Handle `read` command as assignment: `read VAR`
- [ ] 1.6 Handle `local` declarations in functions: `local VAR=value`
- [ ] 1.7 Handle `export` with assignment: `export VAR=value`
- [ ] 1.8 Extract source variables from value for `assignment_sources` table
- [ ] 1.9 Add logging: `logger.debug(f"Bash: extracted {count} assignments from {file}")`
- [ ] 1.10 Write unit tests

**Implementation Details:**
```python
# In bash.py extract() method
def _extract_assignments(self, tree, file_path: str, in_function: str) -> list[dict]:
    """Extract variable assignments for language-agnostic tables."""
    assignments = []

    for node in tree.root_node.descendants:
        if node.type == "variable_assignment":
            # name=value
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")

            if name_node:
                target_var = name_node.text.decode("utf-8")
                source_expr = value_node.text.decode("utf-8") if value_node else ""

                assignments.append({
                    "file": file_path,
                    "line": node.start_point[0] + 1,
                    "col": node.start_point[1],
                    "target_var": target_var,
                    "source_expr": source_expr,
                    "in_function": in_function or "global",
                })

    return assignments
```

## 2. Command Invocation as Function Calls

- [ ] 2.1 Add tree-sitter queries for `command` and `simple_command` nodes
- [ ] 2.2 Extract command name as callee_function
- [ ] 2.3 Extract arguments with correct indices
- [ ] 2.4 Handle command with redirections
- [ ] 2.5 Handle built-in commands vs external commands
- [ ] 2.6 Add logging: `logger.debug(f"Bash: extracted {count} commands from {file}")`
- [ ] 2.7 Write unit tests

**Implementation Details:**
```python
def _extract_commands(self, tree, file_path: str, in_function: str) -> list[dict]:
    """Extract command invocations as function calls."""
    calls = []

    for node in tree.root_node.descendants:
        if node.type == "command":
            name_node = node.child_by_field_name("name")
            if name_node:
                cmd_name = name_node.text.decode("utf-8")

                # Extract arguments
                arg_idx = 0
                for child in node.children:
                    if child.type == "word" and child != name_node:
                        calls.append({
                            "file": file_path,
                            "line": node.start_point[0] + 1,
                            "caller_function": in_function or "global",
                            "callee_function": cmd_name,
                            "argument_index": arg_idx,
                            "argument_expr": child.text.decode("utf-8"),
                        })
                        arg_idx += 1

    return calls
```

## 3. Positional Parameter Extraction

- [ ] 3.1 Parse function definitions for positional parameter usage
- [ ] 3.2 Map `$1`, `$2`, etc. to `func_params` with indices 0, 1, etc.
- [ ] 3.3 Handle `$@` and `$*` as variadic parameters
- [ ] 3.4 Detect parameter usage within function body
- [ ] 3.5 Add logging: `logger.debug(f"Bash: extracted {count} params from {file}")`
- [ ] 3.6 Write unit tests

## 4. Source Pattern Registration

- [ ] 4.1 Add/update `rules/bash/injection_analyze.py`
- [ ] 4.2 Register positional parameter sources: `$1` through `$9`
- [ ] 4.3 Register `$@` and `$*` sources
- [ ] 4.4 Register `read` command as source
- [ ] 4.5 Register CGI variables: `$QUERY_STRING`, `$REQUEST_URI`
- [ ] 4.6 Register common input variables: `$INPUT`, `$DATA`
- [ ] 4.7 Add logging for pattern registration

## 5. Sink Pattern Registration

- [ ] 5.1 Register `eval` as command injection sink
- [ ] 5.2 Register `exec` as command injection sink
- [ ] 5.3 Register `sh -c` and `bash -c` as sinks
- [ ] 5.4 Register `source` and `.` as sinks
- [ ] 5.5 Register `rm` as file deletion sink (especially `rm -rf`)
- [ ] 5.6 Register `curl | sh` and `wget | sh` patterns
- [ ] 5.7 Register database clients: `mysql`, `psql` when with user input
- [ ] 5.8 Add logging for pattern registration

## 6. Integration

- [ ] 6.1 Wire new extraction methods into main `extract()` return dict
- [ ] 6.2 Ensure storage layer handles new data
- [ ] 6.3 Run `aud full --offline` on TheAuditor (has .sh files)
- [ ] 6.4 Query database to verify Bash rows appear in language-agnostic tables
- [ ] 6.5 Run taint analysis, verify flows detected

## 7. Pipe Flow Integration

- [ ] 7.1 Verify BashPipeStrategy edges connect to new assignment nodes
- [ ] 7.2 Test pipe flow: `cat file | grep pattern` should show data flow
- [ ] 7.3 Test subshell capture: `VAR=$(cmd)` should link command output to VAR

## 8. Documentation

- [ ] 8.1 Update extractor docstrings
- [ ] 8.2 Document shell-specific semantics handled
- [ ] 8.3 Add logging following: `from theauditor.utils.logging import logger`
