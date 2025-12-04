## Verification Phase (Pre-Implementation)

**Status**: COMPLETE
**Verified By**: AI Lead Coder (Opus)
**Date**: 2025-12-05

---

### Hypothesis 1: bash_impl.py has self.variables and self.commands structures
**Verification**: CONFIRMED

**Evidence** (`theauditor/ast_extractors/bash_impl.py:65-68`):
```python
self.functions: list[dict] = []
self.variables: list[dict] = []
self.sources: list[dict] = []
self.commands: list[dict] = []
```

**Variable dict structure** (`bash_impl.py:215-223`):
```python
var = {
    "line": self._get_line(node),
    "name": name,
    "scope": scope,
    "readonly": readonly,
    "value_expr": value_expr,
    "containing_function": self.current_function,
}
```

**Command dict structure** (`bash_impl.py:337-345`):
```python
cmd = {
    "line": self._get_line(node),
    "command_name": command_name,
    "pipeline_position": pipeline_position,
    "containing_function": self.current_function,
    "args": normalized_args,
    "wrapped_command": wrapped_command,
}
```

---

### Hypothesis 2: assignments table schema matches spec
**Verification**: INCORRECT - Schema has additional column

**Spec claimed** (`schema.py:193`):
```sql
assignments (file, line, col, target_var, source_expr, in_function)
```

**Actual schema** (`theauditor/indexer/schemas/core_schema.py:92-113`):
```python
ASSIGNMENTS = TableSchema(
    name="assignments",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("col", "INTEGER", nullable=False, default="0"),
        Column("target_var", "TEXT", nullable=False),
        Column("source_expr", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
        Column("property_path", "TEXT", nullable=True),  # MISSING FROM ORIGINAL SPEC
    ],
    primary_key=["file", "line", "col", "target_var"],
    ...
)
```

**Impact**: Implementation must include `property_path` (can be NULL for Bash).

---

### Hypothesis 3: function_call_args table schema matches spec
**Verification**: INCORRECT - Schema has additional columns

**Spec claimed** (`schema.py:195`):
```sql
function_call_args (file, line, caller_function, callee_function, argument_index, argument_expr)
```

**Actual schema** (`theauditor/indexer/schemas/core_schema.py:138-162`):
```python
FUNCTION_CALL_ARGS = TableSchema(
    name="function_call_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("caller_function", "TEXT", nullable=False),
        Column("callee_function", "TEXT", nullable=False, check="callee_function != ''"),
        Column("argument_index", "INTEGER", nullable=True),
        Column("argument_expr", "TEXT", nullable=True),
        Column("param_name", "TEXT", nullable=True),        # MISSING FROM ORIGINAL SPEC
        Column("callee_file_path", "TEXT"),                 # MISSING FROM ORIGINAL SPEC
    ],
    ...
)
```

**Impact**: Implementation can leave `param_name` and `callee_file_path` NULL for Bash commands.

---

### Hypothesis 4: func_params table schema matches spec
**Verification**: INCORRECT - Schema structure different

**Spec claimed**:
```sql
func_params (file, function_name, param_name, param_index, line)
```

**Actual schema** (`theauditor/indexer/schemas/node_schema.py:847-862`):
```python
FUNC_PARAMS = TableSchema(
    name="func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),  # NOT "line"!
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("param_type", "TEXT"),                        # NOT IN ORIGINAL SPEC
    ],
    ...
)
```

**Impact**: Implementation must:
- Use `function_line` (line where function is defined), NOT first usage line
- Include `param_type` (can be NULL for Bash - no types)
- Column order matters for insertion

---

### Hypothesis 5: injection_analyze.py exists and has no register_taint_patterns
**Verification**: CONFIRMED

**Evidence**: File exists at `theauditor/rules/bash/injection_analyze.py` (229 lines)
- Contains `BashInjectionPatterns` dataclass
- Contains `BashInjectionAnalyzer` class
- Contains `analyze()` function
- NO `register_taint_patterns()` function present

**Reference pattern** (`theauditor/rules/go/injection_analyze.py:306-323`):
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

---

### Hypothesis 6: Database has 0 Bash rows in language-agnostic tables
**Verification**: ASSUMED CORRECT (per proposal.md evidence)

**From proposal.md**:
- `assignments` table: 0 Bash rows
- `function_call_args` table: 0 Bash rows
- TaintRegistry: 0 Bash patterns
- BashPipeStrategy produces `pipe_flow` edges but they don't connect to taint sources/sinks

**To verify at implementation time**:
```sql
SELECT COUNT(*) FROM assignments WHERE file LIKE '%.sh';
SELECT COUNT(*) FROM function_call_args WHERE file LIKE '%.sh';
SELECT COUNT(*) FROM func_params WHERE file LIKE '%.sh';
```

---

### Hypothesis 7: Storage layer auto-handles extractor return keys
**Verification**: ASSUMED CORRECT (per existing patterns)

**Evidence from design.md**:
> The indexer pipeline uses a generic pattern:
> 1. Extractor returns dict with table names as keys
> 2. Storage handler iterates over keys and inserts into corresponding tables
> 3. No explicit storage layer modification needed

**To verify**: Check `theauditor/indexer/extractors/bash.py` does `result.update(extracted)`

---

## Discrepancies Found

| Item | Spec Said | Reality | Impact |
|------|-----------|---------|--------|
| assignments schema location | `schema.py:193` | `schemas/core_schema.py:92-113` | Wrong reference |
| assignments columns | 6 columns | 7 columns (+property_path) | Must include in insert |
| function_call_args location | `schema.py:195` | `schemas/core_schema.py:138-162` | Wrong reference |
| function_call_args columns | 6 columns | 8 columns (+param_name, +callee_file_path) | Can be NULL |
| func_params schema | `line` column | `function_line` column | Code will fail |
| func_params schema | no `param_type` | has `param_type` | Must include NULL |

---

## Resolution

All discrepancies have been corrected in the spec files:
- `spec.md` - Updated with correct schema references and columns
- `tasks.md` - Updated implementation code to match actual schemas
- `design.md` - Embedded full Go reference implementation
