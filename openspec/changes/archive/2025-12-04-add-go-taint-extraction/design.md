## Context

Go extractor exists and works for language-specific tables (`go_functions`, `go_routes`, etc.) but does not populate the language-agnostic tables (`assignments`, `function_call_args`, `function_returns`, `func_params`) required for DFG construction and taint analysis.

**Stakeholders:**
- Taint analysis pipeline (needs DFG edges)
- DFGBuilder (reads from language-agnostic tables)
- Graph strategies (GoHttpStrategy, GoOrmStrategy already exist)

**Constraints:**
- Must use tree-sitter-go (already installed)
- Must follow existing extractor pattern (see python.py, rust.py)
- Must use centralized logging (`from theauditor.utils.logging import logger`)
- ZERO FALLBACK policy applies

## Goals / Non-Goals

**Goals:**
- Populate `assignments`, `assignment_sources` tables for Go
- Populate `function_call_args` table for Go
- Populate `function_returns`, `function_return_sources` tables for Go
- Populate `func_params` table for Go
- Enable taint analysis for Go code

**Non-Goals:**
- Modifying graph strategies (already exist and will consume new data)
- Adding new source/sink patterns (already exist in `rules/go/injection_analyze.py`)
- Modifying database schema (using existing tables)
- Supporting Go generics type parameters (separate future work)

## Decisions

### Decision 1: Add extraction methods to existing go.py
**What:** Add `_extract_assignments()`, `_extract_function_calls()`, `_extract_returns()`, `_extract_params()` methods to `GoExtractor` class.

**Why:** Follows established pattern from python.py and rust.py. Keeps all Go extraction logic in one place.

**Alternatives considered:**
- Create separate `go_dfg_extractor.py` - Rejected: Creates fragmentation, harder to maintain
- Modify go_impl.py only - Rejected: go_impl.py handles tree-sitter queries, go.py handles orchestration

### Decision 2: Handle multiple returns with comma-separated return_expr
**What:** For `return a, b, err`, store return_expr as "a, b, err" (single row) with multiple rows in `function_return_sources`.

**Why:** Matches Python pattern where tuple returns are stored as single expression. DFGBuilder already handles this.

**Alternatives considered:**
- One row per return value - Rejected: Breaks DFGBuilder assumptions, doesn't match schema intent

### Decision 3: Skip blank identifier entirely
**What:** When parsing `_, err := foo()`, do NOT create any row for `_`.

**Why:** Blank identifier is explicitly "discard this value" - no data flows through it. Creating rows would pollute the graph with dead-end nodes.

### Decision 4: Use existing storage layer pattern
**What:** Return extraction data as dict keys that match existing storage layer HANDLER names (not table names).

**Why:** Storage layer in `theauditor/indexer/storage/core_storage.py` routes by handler name. Following the Rust extractor pattern ensures data flows correctly.

**Required dict keys (from core_storage.py:38-41):**
```python
{
    # Language-agnostic keys (handled by CoreStorage)
    "assignments": [
        {
            "file": file_path,
            "line": int,
            "col": int,  # default 0
            "target_var": str,
            "source_expr": str,
            "in_function": str,
            "property_path": str | None,
            "source_vars": [str, ...],  # EMBEDDED, not separate table
        },
        ...
    ],
    "function_calls": [  # NOT function_call_args - handler name!
        {
            "file": file_path,
            "line": int,
            "caller_function": str,
            "callee_function": str,
            "argument_index": int,
            "argument_expr": str,
            "param_name": str | None,
            "callee_file_path": str | None,
        },
        ...
    ],
    "returns": [  # NOT function_returns - handler name!
        {
            "file": file_path,
            "line": int,
            "col": int,  # default 0
            "function_name": str,
            "return_expr": str,
            "return_vars": [str, ...],  # EMBEDDED, not separate table
        },
        ...
    ],
    # Plus existing Go-specific keys (handled by GoStorage)
}
```

**CRITICAL:** The `source_vars` and `return_vars` arrays are EMBEDDED in the assignment/return dicts. The storage layer extracts them and writes to `assignment_sources`/`function_return_sources` tables automatically via `db_manager.add_assignment()` and `db_manager.add_function_return()`.

### Decision 5: Go-specific func_params sufficient for DFG
**What:** Continue using `go_func_params` table (already populated by `go_impl.extract_go_func_params()`). Do NOT duplicate to language-agnostic `func_params` table.

**Why:** The `func_params` table in core schema is primarily for JS/TS. Go has richer parameter semantics (receivers, variadic) that are captured in `go_func_params`. The DFGBuilder can query both tables as needed.

## Risks / Trade-offs

### Risk 1: Go semantic complexity (multiple returns)
**Risk:** Go allows `a, b := func()` which is different from Python tuple unpacking.

**Mitigation:** Parse the left side as identifier_list, create one assignment row per identifier. Tested against tree-sitter-go AST structure.

### Risk 2: Method receiver confusion
**Risk:** `func (s *Server) Handle(req Request)` - is `s` a parameter?

**Mitigation:** Receivers are NOT parameters in Go semantics. Store receivers in language-specific `go_methods` table only. `func_params` only contains actual parameters (`req` in this case).

### Risk 3: Named returns with naked return
**Risk:** `func foo() (result int) { result = 42; return }` - the naked `return` returns `result` implicitly.

**Mitigation:** Parse the function signature to get named return variables. When encountering naked `return`, create `function_return_sources` rows for all named returns.

## Migration Plan

**Steps:**
1. Add extraction methods to go.py
2. Run `aud full --offline` on TheAuditor (Go test fixtures exist)
3. Verify database has Go rows in language-agnostic tables
4. Run on real Go project to validate
5. Run taint analysis, verify flows detected

**Rollback:**
- Remove new methods from go.py
- Data in database will be overwritten on next `aud full`

## Open Questions

1. **Q:** Should we extract from `go.mod` to resolve import paths?
   **A:** Out of scope for this change. Import resolution is separate concern.

2. **Q:** Should we handle Go generics `[T any]`?
   **A:** Out of scope. Type parameters don't affect data flow for taint analysis.

## Tree-Sitter Node Reference

Key tree-sitter-go node types used:

```
short_var_declaration  # x := expr
  left: identifier_list
  right: expression_list

assignment_statement   # x = expr
  left: expression_list
  right: expression_list

call_expression
  function: identifier | selector_expression
  arguments: argument_list

return_statement
  expression_list (optional)

function_declaration
  name: identifier
  parameters: parameter_list
    parameter_declaration
      name: identifier (or identifier_list)
      type: type_identifier

method_declaration
  receiver: parameter_list
  name: identifier
  parameters: parameter_list
```
