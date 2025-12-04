## Context

Bash extractor exists and works for language-specific tables (`bash_commands`, `bash_variables`, `bash_pipes`) but does not populate the language-agnostic tables required for DFG construction and taint analysis. Additionally, no source/sink patterns are registered for Bash.

**Stakeholders:**
- Taint analysis pipeline (needs DFG edges and patterns)
- DFGBuilder (reads from language-agnostic tables)
- BashPipeStrategy (already produces pipe_flow edges)
- Security teams (shell injection is CWE-78, critical severity)

**Constraints:**
- Must use tree-sitter-bash (already installed)
- Must follow existing extractor pattern (see python.py, rust.py)
- Must use centralized logging
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

**Example:**
```
function process() {
    echo $1 $2
}
```
Results in:
- func_params: (process, $1, 0)
- func_params: (process, $2, 1)

### Decision 3: Treat `read` as assignment from stdin
**What:** When parsing `read VAR`, create assignment row with source indicating stdin.

**Why:** `read` is the primary way user input enters a script. Must be tracked for taint.

### Decision 4: Handle command substitution as both assignment and call
**What:** For `VAR=$(command)`:
1. Create assignment row: target=VAR, source=$(command)
2. Create function_call_args row for the inner command

**Why:** Data flows both through the command execution AND through the assignment.

### Decision 5: Pattern registration with injection_analyze.py
**What:** Add `register_bash_patterns()` to existing `rules/bash/injection_analyze.py`.

**Why:** Follow existing pattern from Go. Keep all language injection patterns in consistent location.

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
