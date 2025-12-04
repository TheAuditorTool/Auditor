## Why

Go extractor currently populates only language-specific tables (`go_functions`, `go_routes`, `go_variables`) but NOT the language-agnostic tables (`assignments`, `function_call_args`, `function_returns`, `func_params`) that the DFGBuilder and taint engine require. This means **zero data flow edges** are produced for Go code, making taint analysis impossible despite having source/sink patterns already defined in `rules/go/injection_analyze.py`.

**Evidence from Prime Directive investigation:**
- `assignments` table: 0 Go rows (vs 22,640 Python rows)
- `function_call_args` table: 0 Go rows (vs 77,752 Python rows)
- Graph strategies produce `go_route_handler` edges but no core `assignment`/`return` edges

## What Changes

1. **Extractor Enhancement** - `theauditor/indexer/extractors/go.py`
   - Add tree-sitter traversal for assignment statements (`:=`, `=`)
   - Extract function call arguments from `call_expression` nodes
   - Extract return statements and source variables
   - Extract function parameter definitions

2. **Go Impl Module** - `theauditor/indexer/extractors/go_impl.py`
   - Add AST node processing functions for language-agnostic table population
   - Handle Go-specific semantics (multiple returns, blank identifier `_`)

3. **Source/Sink Patterns** - Verify existing patterns in `rules/go/injection_analyze.py` work with new DFG edges

**NOT changing:**
- Graph strategies (already exist: GoHttpStrategy, GoOrmStrategy)
- Database schema (using existing language-agnostic tables)
- TaintRegistry (Go patterns already registered)

## Impact

- **Affected specs**: NEW `go-extraction` capability
- **Affected code**:
  - `theauditor/indexer/extractors/go.py` (~300 lines added)
  - `theauditor/indexer/extractors/go_impl.py` (~200 lines added)
- **Risk**: Medium - must handle Go-specific semantics correctly (multiple returns, blank identifier, short variable declaration vs regular assignment)
- **Dependencies**: tree-sitter-go already installed and working

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
