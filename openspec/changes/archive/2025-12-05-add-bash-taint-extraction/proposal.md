## Why

Bash extractor currently populates only language-specific tables (`bash_commands`, `bash_variables`, `bash_pipes`) but NOT the language-agnostic tables (`assignments`, `function_call_args`, `function_returns`, `func_params`) that the DFGBuilder and taint engine require. Additionally, **no source/sink patterns are registered** for Bash.

This means:
1. **Zero data flow edges** for Bash scripts
2. **Zero taint detection** for shell injection vulnerabilities

Shell injection is one of the most critical vulnerability classes (CWE-78), and many CI/CD pipelines, deployment scripts, and automation tools are written in Bash.

**Evidence from Prime Directive investigation:**
- `assignments` table: 0 Bash rows
- `function_call_args` table: 0 Bash rows
- TaintRegistry: 0 Bash patterns
- BashPipeStrategy produces `pipe_flow` edges but they don't connect to taint sources/sinks

## What Changes

**NOTE**: `theauditor/ast_extractors/bash_impl.py` (823 lines) ALREADY extracts `bash_variables`, `bash_commands`, `bash_pipes`, etc. The issue is that these bash-specific extractions are NOT mapped to the language-agnostic tables (`assignments`, `function_call_args`, `func_params`) that DFGBuilder requires.

1. **AST Extractor Enhancement** - `theauditor/ast_extractors/bash_impl.py`
   - Modify `extract()` to ALSO return language-agnostic table data
   - Map `bash_variables` -> `assignments` format
   - Map `bash_commands` -> `function_call_args` format
   - Extract positional parameters (`$1`, `$2`, `$@`) -> `func_params` format

2. **Thin Wrapper Update** - `theauditor/indexer/extractors/bash.py`
   - Update to pass through the new language-agnostic keys from bash_impl.py
   - No major changes needed (already delegates to bash_impl.py)

3. **Source/Sink Patterns** - Add `register_taint_patterns()` to `rules/bash/injection_analyze.py`
   - Follow pattern from `rules/go/injection_analyze.py:306-323`
   - Register Bash sources (positional params, read, stdin)
   - Register Bash sinks (eval, exec, rm, curl)

**NOT changing:**
- Graph strategies (BashPipeStrategy already exists)
- Database schema (using existing language-agnostic tables)

## Impact

- **Affected specs**: NEW `bash-extraction` capability
- **Affected code**:
  - `theauditor/ast_extractors/bash_impl.py` (~80 lines added - mapping methods)
  - `theauditor/indexer/extractors/bash.py` (~10 lines modified - pass through new keys)
  - `theauditor/rules/bash/injection_analyze.py` (~50 lines added - register_taint_patterns function)
- **Risk**: Low - leveraging existing extraction, just adding mapping layer
- **Dependencies**: tree-sitter-bash already installed and working

## Success Criteria

After implementation:
```sql
-- Should show Bash assignments
SELECT COUNT(*) FROM assignments WHERE file LIKE '%.sh';
-- Expected: >0

-- Should show Bash function calls (command invocations)
SELECT COUNT(*) FROM function_call_args WHERE file LIKE '%.sh';
-- Expected: >0

-- Taint analysis should find Bash flows
SELECT COUNT(*) FROM taint_flows WHERE source_file LIKE '%.sh';
-- Expected: >0 for scripts with injection vulnerabilities
```

## Bash-Specific Challenges

1. **Variable Assignment Variants**
   - Simple: `VAR=value`
   - Command substitution: `VAR=$(command)`
   - Arithmetic: `VAR=$((x + 1))`
   - Read command: `read VAR`

2. **Data Flow Through Pipes**
   - `cmd1 | cmd2` - stdout of cmd1 flows to stdin of cmd2
   - BashPipeStrategy handles this but needs to connect to taint

3. **Positional Parameters**
   - `$1`, `$2` ... `$9`, `$@`, `$*` are function parameters
   - Need to map these to `func_params` table

4. **Command Invocation as Function Calls**
   - `grep pattern file` is semantically a function call with args
   - Need to model this in `function_call_args` table

## Source Patterns (User Input)

| Pattern | Category | Description |
|---------|----------|-------------|
| `$1` - `$9` | positional_param | Script/function arguments |
| `$@` | positional_param | All arguments as separate words |
| `$*` | positional_param | All arguments as single word |
| `read` | stdin | User input from stdin |
| `$INPUT` | env | Common input variable |
| `$QUERY_STRING` | cgi | CGI query string |
| `$REQUEST_URI` | cgi | CGI request URI |

## Sink Patterns (Dangerous Operations)

| Pattern | Category | Description |
|---------|----------|-------------|
| `eval` | command_injection | Evaluate string as command |
| `exec` | command_injection | Execute and replace shell |
| `sh -c` | command_injection | Shell command string |
| `bash -c` | command_injection | Bash command string |
| `source` | command_injection | Source file as script |
| `.` | command_injection | Source shorthand |
| `rm` | file_delete | File deletion |
| `curl \| sh` | remote_exec | Remote script execution |
| `wget \| sh` | remote_exec | Remote script execution |
