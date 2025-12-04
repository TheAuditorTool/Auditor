## Why

Go extractor currently populates only language-specific tables (`go_functions`, `go_routes`, `go_variables`) but NOT the language-agnostic tables (`assignments`, `function_call_args`, `function_returns`) that the DFGBuilder and taint engine require. This means **zero data flow edges** are produced for Go code, making taint analysis impossible despite having source/sink patterns already defined in `rules/go/injection_analyze.py`.

Note: Go already populates `go_func_params` (via `go_impl.extract_go_func_params()`), which is sufficient for Go-specific param analysis. The language-agnostic `func_params` table is primarily for JS/TS.

**Evidence from Prime Directive investigation:**
- `assignments` table: 0 Go rows (vs 22,640 Python rows)
- `function_call_args` table: 0 Go rows (vs 77,752 Python rows)
- Graph strategies produce `go_route_handler` edges but no core `assignment`/`return` edges

## What Changes

1. **Extractor Enhancement** - `theauditor/indexer/extractors/go.py`
   - Add tree-sitter traversal for assignment statements (`:=`, `=`)
   - Extract function call arguments from `call_expression` nodes
   - Extract return statements and source variables
   - Return data using storage handler keys: `"assignments"`, `"function_calls"`, `"returns"`
     (Note: handler names differ from table names - see `core_storage.py:38-41`)

2. **Go Impl Module** - `theauditor/ast_extractors/go_impl.py`
   - Add AST node processing functions for language-agnostic table population
   - Handle Go-specific semantics (multiple returns, blank identifier `_`)
   - Embed `source_vars`/`return_vars` arrays in dicts (storage layer extracts to junction tables)

3. **Source/Sink Patterns** - Verify existing patterns in `rules/go/injection_analyze.py` work with new DFG edges

**NOT changing:**
- Graph strategies (already exist: GoHttpStrategy, GoOrmStrategy)
- Database schema (using existing language-agnostic tables)
- TaintRegistry (Go patterns already registered)

## Impact

- **Affected specs**: NEW `go-extraction` capability
- **Affected code**:
  - `theauditor/indexer/extractors/go.py` (~300 lines added)
  - `theauditor/ast_extractors/go_impl.py` (~200 lines added)
- **Risk**: Medium - must handle Go-specific semantics correctly (multiple returns, blank identifier, short variable declaration vs regular assignment)
- **Dependencies**: tree-sitter-go already installed and working

## Key Architecture Reference

Storage layer routing (from `core_storage.py:38-41`):
```python
self.handlers = {
    "assignments": self._store_assignments,      # -> assignments table
    "function_calls": self._store_function_calls,  # -> function_call_args table
    "returns": self._store_returns,              # -> function_returns table
    ...
}
```

The extractor return dict MUST use handler names (left column), NOT table names (right column).
Source variables are embedded in dicts as `source_vars`/`return_vars` arrays, NOT as separate keys.

## Success Criteria

After implementation:
```sql
-- Should show Go assignments
SELECT COUNT(*) FROM assignments WHERE file LIKE '%.go';
-- Expected: >0 (proportional to Go codebase size)

-- Should show Go function calls
SELECT COUNT(*) FROM function_call_args WHERE file LIKE '%.go';
-- Expected: >0

-- Taint analysis should find Go flows
SELECT COUNT(*) FROM taint_flows WHERE source_file LIKE '%.go';
-- Expected: >0 for codebases with injection vulnerabilities
```
