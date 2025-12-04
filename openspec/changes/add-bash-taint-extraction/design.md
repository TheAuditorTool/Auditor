## Context

**Current State**: `theauditor/ast_extractors/bash_impl.py` (823 lines) ALREADY extracts comprehensive Bash data:
- `bash_functions`, `bash_variables`, `bash_sources`, `bash_commands`
- `bash_pipes`, `bash_subshells`, `bash_redirections`, `bash_control_flows`

**The Problem**: This extracted data is NOT mapped to language-agnostic tables (`assignments`, `function_call_args`, `func_params`) that DFGBuilder and taint analysis require. Additionally, no source/sink patterns are registered in TaintRegistry for Bash.

**Architecture**:
```
theauditor/indexer/extractors/bash.py      # Thin wrapper (85 lines)
    └── imports from theauditor/ast_extractors/bash_impl.py  # Actual extraction (823 lines)
```

**Stakeholders:**
- Taint analysis pipeline (needs DFG edges and patterns)
- DFGBuilder (reads from language-agnostic tables)
- BashPipeStrategy (already produces pipe_flow edges)
- Security teams (shell injection is CWE-78, critical severity)

**Constraints:**
- Must use tree-sitter-bash (already installed)
- Must ADD to existing `bash_impl.py`, NOT create new files
- Must use centralized logging: `from theauditor.utils.logging import logger`
- ZERO FALLBACK policy applies
- Shell semantics are complex - must handle correctly

## Goals / Non-Goals

**Goals:**
- Populate `assignments`, `assignment_sources` tables for Bash
- Populate `function_call_args` table for Bash (command invocations)
- Populate `func_params` table for Bash (positional parameters)
- Register Bash source patterns (positional params, read, CGI vars)
- Register Bash sink patterns (eval, exec, rm, curl|sh)
- Enable taint analysis for Bash scripts

**Non-Goals:**
- Modifying BashPipeStrategy (already works)
- Full shell semantic analysis (too complex)
- Handling all bash features (arrays, associative arrays, etc.)
- Supporting zsh/fish/other shells (Bash only)

## Decisions

### Decision 1: Model commands as function calls
**What:** Treat `grep pattern file` as a function call to `grep` with arguments `pattern` and `file`.

**Why:** This maps shell commands to the existing `function_call_args` schema, enabling taint flow through command arguments.

**Alternatives considered:**
- Create separate `bash_commands` table - Rejected: Duplicates existing pattern, doesn't integrate with DFGBuilder

### Decision 2: Positional params as pseudo-parameters
**What:** Store `$1`, `$2`, etc. literally in `func_params` table with indices 0, 1, etc.

**Why:** Bash doesn't have named parameters like other languages. The positional syntax IS the parameter name.

**Schema** (`theauditor/indexer/schemas/node_schema.py:847-862`):
```sql
func_params (file, function_line, function_name, param_index, param_name, param_type)
```

**Example:**
```bash
# Line 5:
function process() {
    echo $1 $2
}
```
Results in:
- func_params: (file, 5, "process", 0, "$1", NULL)
- func_params: (file, 5, "process", 1, "$2", NULL)

### Decision 3: Treat `read` as assignment from stdin
**What:** When parsing `read VAR`, create assignment row with source indicating stdin.

**Why:** `read` is the primary way user input enters a script. Must be tracked for taint.

### Decision 4: Handle command substitution as both assignment and call
**What:** For `VAR=$(command)`:
1. Create assignment row: target=VAR, source=$(command)
2. Create function_call_args row for the inner command

**Why:** Data flows both through the command execution AND through the assignment.

### Decision 5: Pattern registration with injection_analyze.py
**What:** Add `register_taint_patterns(taint_registry)` function to existing `rules/bash/injection_analyze.py`.

**Why:** Follow existing pattern from `rules/go/injection_analyze.py:306-323`. The orchestrator calls `collect_rule_patterns()` which imports each rule module and calls `register_taint_patterns()` if it exists.

**Reference implementation** (full code from `theauditor/rules/go/injection_analyze.py:306-324`):
```python
def register_taint_patterns(taint_registry):
    """Register Go injection-specific taint patterns."""
    patterns = GoInjectionPatterns()

    for pattern in patterns.USER_INPUTS:
        taint_registry.register_source(pattern, "user_input", "go")

    for pattern in patterns.SQL_METHODS:
        taint_registry.register_sink(pattern, "sql", "go")

    for pattern in patterns.COMMAND_METHODS:
        taint_registry.register_sink(pattern, "command", "go")

    for pattern in patterns.TEMPLATE_METHODS:
        taint_registry.register_sink(pattern, "template", "go")

    for pattern in patterns.PATH_METHODS:
        taint_registry.register_sink(pattern, "path", "go")
```

**TaintRegistry API** (method signatures):
```python
# From theauditor/taint/registry.py
taint_registry.register_source(pattern: str, category: str, language: str) -> None
taint_registry.register_sink(pattern: str, category: str, language: str) -> None
```

### Decision 6: Storage layer integration via extractor return dict
**What:** The extractor returns `assignments`, `function_call_args`, and `func_params` keys in its result dict. The storage layer automatically handles these.

**Why:** The indexer pipeline uses a generic pattern:
1. Extractor returns dict with table names as keys
2. Storage handler iterates over keys and inserts into corresponding tables
3. No explicit storage layer modification needed

**How it works:**
```python
# bash_impl.py extract() returns:
{
    "bash_variables": [...],  # Bash-specific (existing)
    "bash_commands": [...],   # Bash-specific (existing)
    "assignments": [...],     # Language-agnostic (NEW)
    "function_call_args": [...],  # Language-agnostic (NEW)
    "func_params": [...],     # Language-agnostic (NEW)
}

# bash.py does: result.update(extracted)
# Storage layer automatically processes all keys
```

## Risks / Trade-offs

### Risk 1: Word splitting complexity
**Risk:** `$VAR` behaves differently than `"$VAR"` due to word splitting.

**Mitigation:** For taint purposes, treat both as equivalent - the taint flows regardless of quoting. Document this simplification.

### Risk 2: Pipe semantics
**Risk:** `cmd1 | cmd2` - data flows through stdout/stdin, not explicit variables.

**Mitigation:** BashPipeStrategy already handles pipe edges. Ensure new assignment nodes connect to pipe flow nodes.

### Risk 3: Subshell isolation
**Risk:** `(VAR=value)` creates variable in subshell, not visible to parent.

**Mitigation:** For taint purposes, track all assignments. Subshell isolation affects scope but not security impact.

### Risk 4: Here documents
**Risk:** `cat <<EOF\n$DATA\nEOF` - data flows through heredoc.

**Mitigation:** Parse heredoc content as potential source, but this is complex. Mark as future enhancement if too complex.

## Migration Plan

**Steps:**
1. Add extraction methods to bash.py
2. Add source/sink patterns to injection_analyze.py
3. Run `aud full --offline` on TheAuditor (has shell scripts)
4. Verify database has Bash rows in language-agnostic tables
5. Run taint analysis, verify flows detected
6. Test on real-world bash-heavy project

**Rollback:**
- Remove new methods from bash.py
- Remove patterns from injection_analyze.py
- Data in database will be overwritten on next `aud full`

## Open Questions

1. **Q:** Should we track environment variable exports as sinks?
   **A:** Yes, `export VAR=$TAINTED` can affect child processes. Add to sink patterns.

2. **Q:** How to handle array assignments `ARR=(a b c)`?
   **A:** Out of scope for initial implementation. Track as enhancement.

3. **Q:** Should `test` / `[` / `[[` be tracked?
   **A:** No - these are conditionals, not data sinks. Skip.

## Tree-Sitter Node Reference

Key tree-sitter-bash node types used:

```
variable_assignment
  name: variable_name
  value: (word | string | command_substitution | ...)

command
  name: command_name
  argument: word*

simple_command
  name: (word | ...)
  (word)* # arguments

function_definition
  name: word
  body: compound_statement

command_substitution
  $(command)

read_command (special case)
  variable_name+

for_statement
  variable: variable_name
  body: do_group

pipeline
  command (command)*
```

## Pattern Examples

**Source patterns:**
```python
BASH_SOURCES = [
    "$1", "$2", "$3", "$4", "$5", "$6", "$7", "$8", "$9",
    "$@", "$*",
    "read",
    "$QUERY_STRING", "$REQUEST_URI",
    "$HTTP_USER_AGENT", "$HTTP_COOKIE",
    "$INPUT", "$DATA", "$PAYLOAD",
]
```

**Sink patterns:**
```python
BASH_SINKS = [
    "eval",
    "exec",
    "sh -c", "bash -c",
    "source", ".",
    "rm", "rm -rf",
    "mysql -e", "psql -c", "sqlite3",
    "curl | sh", "wget | sh",
    "xargs",
]
```
