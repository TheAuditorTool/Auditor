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
