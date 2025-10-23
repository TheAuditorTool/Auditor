# Tasks: Code Context Query Suite

## 0. Verification (SOP v4.20 Alignment)

- [x] 0.1 Read current `theauditor/commands/context.py` implementation
  - Confirmed: Single command, not group (line 17)
  - Confirmed: Semantic analyzer only, no query interface
- [x] 0.2 Query plant project database to verify data richness
  - Confirmed: 42,104 symbols (33,356 main + 8,748 JSX)
  - Confirmed: 17,394 function calls with arguments
  - Confirmed: 7,332 graph edges, 4,802 nodes
- [x] 0.3 Review existing query patterns in `theauditor/graph/store.py`
  - Confirmed: `query_dependencies()` at line 263
  - Confirmed: `query_calls()` at line 305
  - Pattern: Direct SQL queries with sqlite3.Row factory
- [x] 0.4 Review Click group pattern in `theauditor/commands/graph.py`
  - Confirmed: `@click.group()` pattern at line 9
  - Confirmed: Multiple subcommands (build, analyze, query, viz)
  - Can reuse exact pattern for context command
- [x] 0.5 Reject old proposal approach (static JSON summaries)
  - Discrepancy: Old design wanted pre-generated context packs
  - Reality: AIs should query on-demand for speed and precision
  - Fix: Query-first architecture, no chunking/summarization

## 1. CLI Refactoring

### 1.1 Convert context command to group
- [ ] Modify `theauditor/commands/context.py`:
  - Change `@click.command(name="context")` to `@click.group(invoke_without_command=True)`
  - Add `@click.pass_context` decorator
  - Update docstring to list subcommands
  - Add `if ctx.invoked_subcommand is None: click.echo(ctx.get_help())`

**Acceptance Criteria:**
- Running `aud context` shows help with subcommands listed
- No functionality breaks yet (existing code still in place)

**Files Modified:**
- `theauditor/commands/context.py` (lines 17-24)

### 1.2 Move existing implementation to semantic subcommand
- [ ] Create `@context.command("semantic")` decorator
- [ ] Move entire current implementation (lines 25-227) under semantic function
- [ ] Preserve all existing options: `--file`, `--output`, `--verbose`
- [ ] Test backward compatibility: `aud context semantic --file test.yaml`

**Acceptance Criteria:**
- `aud context semantic --file foo.yaml` works exactly as before
- All existing tests pass
- Help text shows semantic as subcommand

**Files Modified:**
- `theauditor/commands/context.py` (lines 25-314)

## 2. Query Engine Implementation

### 2.1 Create query engine module
- [ ] Create new file: `theauditor/context/__init__.py`
- [ ] Create new file: `theauditor/context/query.py`
- [ ] Define dataclasses:
  - `SymbolInfo` (name, type, file, line, end_line, signature, is_exported, framework_type)
  - `CallSite` (caller_file, caller_line, caller_function, callee_function, arguments)
  - `Dependency` (source_file, target_file, import_type, line, symbols)

**Acceptance Criteria:**
- Module imports successfully
- Dataclasses have proper type hints
- No circular import errors

**Files Created:**
- `theauditor/context/__init__.py` (export CodeQueryEngine)
- `theauditor/context/query.py` (~400 lines)

### 2.2 Implement CodeQueryEngine class
- [ ] Implement `__init__(root: Path)`:
  - Connect to `.pf/repo_index.db` (required)
  - Connect to `.pf/graphs.db` (optional, None if missing)
  - Set `row_factory = sqlite3.Row` for both
  - Raise `FileNotFoundError` if repo_index.db missing
- [ ] Add connection validation
- [ ] Add error messages with remediation steps

**Acceptance Criteria:**
- Engine initializes with valid `.pf/` directory
- Raises helpful error if database missing
- Both databases accessible via `self.repo_db` and `self.graph_db`

**Files Modified:**
- `theauditor/context/query.py` (lines 1-100)

### 2.3 Implement symbol query methods
- [ ] Implement `find_symbol(name, type_filter=None)`:
  - Query both `symbols` and `symbols_jsx` tables
  - Support optional type filter (function, class, etc.)
  - Return list of `SymbolInfo` objects
  - Use exact match on name (no LIKE)

**Acceptance Criteria:**
- Finds symbols in both main and JSX tables
- Returns empty list for non-existent symbols (no errors)
- Type filter works correctly

**SQL Queries:**
```sql
SELECT name, type, file, line, end_line, signature, is_exported, framework_type
FROM symbols WHERE name = ?
```

**Files Modified:**
- `theauditor/context/query.py` (method: `find_symbol`)

### 2.4 Implement caller/callee analysis
- [ ] Implement `get_callers(symbol_name, depth=1)`:
  - Query `function_call_args` and `function_call_args_jsx`
  - For depth=1: Direct callers only
  - For depth>1: BFS traversal through call graph
  - Track visited set to prevent infinite loops
  - Max depth: 5 (raise ValueError if > 5)
  - Return list of `CallSite` objects

- [ ] Implement `get_callees(symbol_name)`:
  - Query WHERE `caller_function LIKE %symbol_name%`
  - Return list of `CallSite` objects

**Acceptance Criteria:**
- Direct callers query works (depth=1)
- Transitive query returns more results at depth=3 than depth=1
- Circular calls don't cause infinite loops
- Performance: <50ms for depth=3 on plant project

**SQL Queries:**
```sql
SELECT DISTINCT file, line, caller_function, callee_function, argument_expr
FROM function_call_args
WHERE callee_function = ?
ORDER BY file, line
```

**Files Modified:**
- `theauditor/context/query.py` (methods: `get_callers`, `get_callees`)

### 2.5 Implement file dependency queries
- [ ] Implement `get_file_dependencies(file_path, direction='both')`:
  - Check if `self.graph_db` exists (return error dict if None)
  - Query `edges` table WHERE `graph_type='import'`
  - Support direction: 'incoming', 'outgoing', 'both'
  - Use LIKE for partial path matching
  - Return dict with 'incoming' and/or 'outgoing' lists

**Acceptance Criteria:**
- Returns error if graph database missing
- Finds incoming dependencies (who imports this file)
- Finds outgoing dependencies (what this file imports)
- LIKE matching works for partial paths

**SQL Queries:**
```sql
-- Incoming (who imports this file)
SELECT source, target, type, line
FROM edges
WHERE target LIKE ? AND graph_type = 'import'

-- Outgoing (what this file imports)
SELECT source, target, type, line
FROM edges
WHERE source LIKE ? AND graph_type = 'import'
```

**Files Modified:**
- `theauditor/context/query.py` (method: `get_file_dependencies`)

### 2.6 Implement framework-specific queries
- [ ] Implement `get_api_handlers(route_pattern)`:
  - Query `api_endpoints` table
  - Use LIKE for route pattern matching
  - Return list of dicts with route, method, file, line, handler, auth

- [ ] Implement `get_component_tree(component_name)`:
  - Query `react_components` for definition
  - Query `react_hooks` for hooks used in file
  - Query `function_call_args_jsx` for child components
  - Return dict with component info, hooks, children

**Acceptance Criteria:**
- API query finds endpoints by route pattern
- Component query returns full hierarchy
- Returns helpful error for non-existent component

**SQL Queries:**
```sql
-- API endpoints
SELECT route, method, file, line, handler_function, requires_auth, framework
FROM api_endpoints
WHERE route LIKE ?

-- Component definition
SELECT name, file, line, is_default_export, has_props, has_state
FROM react_components
WHERE name = ?

-- Hooks used
SELECT hook_name, line
FROM react_hooks
WHERE file = ?

-- Child components
SELECT DISTINCT callee_function, line
FROM function_call_args_jsx
WHERE file = ? AND callee_function IN (SELECT name FROM react_components)
```

**Files Modified:**
- `theauditor/context/query.py` (methods: `get_api_handlers`, `get_component_tree`)

## 3. Output Formatters

### 3.1 Create formatters module
- [ ] Create file: `theauditor/context/formatters.py`
- [ ] Implement `format_output(results, format='text')`:
  - Route to `_format_text()`, `_format_json()`, or `_format_tree()`
  - Handle all result types (symbol, callers, dependencies, API, component)

**Acceptance Criteria:**
- Formatters module imports successfully
- Main entry point dispatches correctly

**Files Created:**
- `theauditor/context/formatters.py` (~250 lines)

### 3.2 Implement text formatter
- [ ] Implement `_format_text(results)`:
  - Format symbol info (name, type, file:line, exported, signature)
  - Format caller list (numbered, file:line, function name)
  - Format dependencies (incoming/outgoing with arrows)
  - Format API endpoints (method, route, handler, auth icon)
  - Format component tree (name, hooks, children)
  - Fallback to JSON for unknown types

**Acceptance Criteria:**
- Output is human-readable
- File paths include line numbers
- Lists are numbered or bulleted
- No emojis (unless Windows encoding safe)

**Example Output:**
```
Symbol: authenticateUser
  Type: function
  File: src/auth/service.ts:42-58
  Exported: Yes

Callers (5):
  1. src/middleware/auth.ts:23  authMiddleware()
  2. src/api/users.ts:105       UserController.login()
```

**Files Modified:**
- `theauditor/context/formatters.py` (function: `_format_text`)

### 3.3 Implement JSON formatter
- [ ] Implement `_format_json(results)`:
  - Convert dataclasses to dicts (use `asdict()` from dataclasses)
  - Handle nested structures recursively
  - Use `json.dumps(indent=2, default=str)` for serialization
  - Include provenance metadata

**Acceptance Criteria:**
- Valid JSON output
- Dataclasses converted correctly
- AI-consumable structure

**Files Modified:**
- `theauditor/context/formatters.py` (functions: `_format_json`, `_to_dict`)

### 3.4 Implement tree formatter (placeholder)
- [ ] Implement `_format_tree(results)`:
  - For now: Fallback to `_format_text()`
  - TODO comment for future visual tree implementation
  - (Full tree visualization is Phase 2)

**Acceptance Criteria:**
- Returns valid output (via text formatter)
- TODO comment indicates future enhancement

**Files Modified:**
- `theauditor/context/formatters.py` (function: `_format_tree`)

## 4. CLI Query Command

### 4.1 Implement query subcommand skeleton
- [ ] Add `@context.command("query")` in `theauditor/commands/context.py`
- [ ] Add all CLI options:
  - `--symbol`, `--file`, `--api`, `--component` (query targets)
  - `--show-callers`, `--show-callees` (symbol actions)
  - `--show-dependencies`, `--show-dependents` (file actions)
  - `--show-tree`, `--show-hooks` (component actions)
  - `--depth` (default=1, type=int, help="Traversal depth 1-5")
  - `--format` (default='text', choices=['text', 'json', 'tree'])
  - `--save` (optional path to save output)
- [ ] Add docstring with examples

**Acceptance Criteria:**
- Command shows in `aud context --help`
- `aud context query --help` shows all options
- No implementation yet (just skeleton)

**Files Modified:**
- `theauditor/commands/context.py` (new function: `query`)

### 4.2 Wire query engine to CLI
- [ ] Validate inputs (at least one query target required)
- [ ] Check `.pf/` directory exists
- [ ] Initialize `CodeQueryEngine(Path.cwd())`
- [ ] Route query based on target:
  - `--symbol` → `find_symbol()` + `get_callers()` or `get_callees()`
  - `--file` → `get_file_dependencies()`
  - `--api` → `get_api_handlers()`
  - `--component` → `get_component_tree()`
- [ ] Handle missing database errors gracefully

**Acceptance Criteria:**
- Query routing works for all targets
- Helpful error if no .pf/ directory
- Helpful error if database missing

**Files Modified:**
- `theauditor/commands/context.py` (function: `query`)

### 4.3 Wire formatters to CLI
- [ ] Import `format_output` from formatters
- [ ] Call formatter with results and format parameter
- [ ] Print to stdout with `click.echo()`
- [ ] Implement `--save` option:
  - Create parent directories if needed
  - Write formatted output to file
  - Print confirmation with path

**Acceptance Criteria:**
- Text format prints to terminal
- JSON format is valid and readable
- `--save` creates file in correct location
- File paths auto-created

**Files Modified:**
- `theauditor/commands/context.py` (function: `query`)

## 5. Testing

### 5.1 Unit tests for query engine
- [ ] Create `tests/unit/context/test_query_engine.py`
- [ ] Test `find_symbol()`:
  - Exact match finds symbol
  - Type filter works
  - Non-existent symbol returns empty list
- [ ] Test `get_callers()`:
  - Depth=1 returns direct callers
  - Depth=3 returns more results (transitive)
  - Max depth enforced (ValueError if > 5)
- [ ] Test `get_callees()`:
  - Returns callees correctly
- [ ] Test `get_file_dependencies()`:
  - Incoming dependencies
  - Outgoing dependencies
  - Both directions
- [ ] Test error handling:
  - Missing database raises FileNotFoundError
  - Missing graph DB returns error dict

**Acceptance Criteria:**
- All tests pass
- Coverage >80% for query.py

**Files Created:**
- `tests/unit/context/test_query_engine.py`

### 5.2 Integration tests with plant database
- [ ] Create `tests/integration/context/test_context_query_plant.py`
- [ ] Test queries on real plant project database:
  - Query known symbol (verify exists)
  - Query callers (verify count > 0)
  - Query file dependencies
  - Query API endpoint
  - Query React component
- [ ] Measure performance:
  - Symbol lookup <5ms
  - Direct callers <10ms
  - Transitive (depth=3) <50ms

**Acceptance Criteria:**
- All integration tests pass with plant database
- Performance requirements met

**Files Created:**
- `tests/integration/context/test_context_query_plant.py`

### 5.3 CLI tests
- [ ] Create `tests/cli/test_context_commands.py`
- [ ] Test command group structure:
  - `aud context` shows help
  - Help lists 'semantic' and 'query' subcommands
- [ ] Test semantic subcommand:
  - `aud context semantic --file test.yaml` works
  - Existing tests still pass
- [ ] Test query subcommand:
  - `aud context query --symbol foo --show-callers` works
  - `--format json` returns valid JSON
  - `--save` creates file
  - Error handling (no database, invalid symbol)

**Acceptance Criteria:**
- All CLI tests pass
- Help text verified
- Error messages verified

**Files Created:**
- `tests/cli/test_context_commands.py`

### 5.4 Unit tests for formatters
- [ ] Create `tests/unit/context/test_formatters.py`
- [ ] Test `_format_text()`:
  - Symbol info formatted correctly
  - Callers list numbered
  - Dependencies show arrows
- [ ] Test `_format_json()`:
  - Valid JSON output
  - Dataclasses converted
- [ ] Test `_to_dict()` helper:
  - Recursive conversion
  - Handles lists, dicts, dataclasses

**Acceptance Criteria:**
- All formatter tests pass
- Output samples verified

**Files Created:**
- `tests/unit/context/test_formatters.py`

## 6. Documentation

### 6.1 Update CLAUDE.md
- [ ] Add "Code Context Query Suite" section
- [ ] Document query commands with examples:
  - Symbol queries (callers, callees)
  - File queries (dependencies, dependents)
  - API queries (endpoints)
  - Component queries (tree, hooks)
- [ ] Add query syntax reference
- [ ] Add performance expectations
- [ ] Add comparison to Claude Compass

**Acceptance Criteria:**
- CLAUDE.md has complete query documentation
- Examples are copy-pasteable
- Performance numbers documented

**Files Modified:**
- `CLAUDE.md` (new section: "Code Context Queries")

### 6.2 Update README.md
- [ ] Add `aud context query` to command reference
- [ ] Add quick start example:
  ```bash
  # Query who calls a function
  aud context query --symbol authenticateUser --show-callers

  # Query file dependencies
  aud context query --file src/auth.ts --show-dependencies

  # Query API endpoint
  aud context query --api "/users/:id" --format json
  ```
- [ ] Update "Core Philosophy" section with query-first approach

**Acceptance Criteria:**
- README has context query examples
- Quick start works for new users

**Files Modified:**
- `README.md` (sections: "Quick Reference Commands", "Core Philosophy")

### 6.3 Update command help text
- [ ] Update `aud context --help`:
  - List both subcommands (semantic, query)
  - Add description for each
- [ ] Update `aud context query --help`:
  - Complete option documentation
  - Add usage examples
  - Add output format descriptions

**Acceptance Criteria:**
- Help text is comprehensive
- Examples are helpful

**Files Modified:**
- `theauditor/commands/context.py` (docstrings)

## 7. Validation

### 7.1 Run openspec validation
- [ ] Run: `openspec validate add-code-context-suite --strict`
- [ ] Fix any spec violations
- [ ] Ensure all docs are up-to-date

**Acceptance Criteria:**
- Validation passes
- No spec violations

### 7.2 Manual testing
- [ ] Test on TheAuditor itself:
  - `aud index`
  - `aud graph build`
  - `aud context query --symbol CodeQueryEngine --show-callers`
- [ ] Test on plant project:
  - Query known symbols
  - Query API endpoints
  - Measure performance
- [ ] Test error scenarios:
  - Missing database
  - Invalid symbol
  - Missing graph DB

**Acceptance Criteria:**
- All manual tests pass
- Error messages are helpful
- Performance meets requirements

### 7.3 Run full test suite
- [ ] Run: `pytest tests/ -v`
- [ ] Run: `ruff check theauditor tests --fix`
- [ ] Run: `mypy theauditor --strict`
- [ ] Fix any failures

**Acceptance Criteria:**
- All tests pass
- No linting errors
- No type errors

## Implementation Checklist Summary

- [ ] **1. CLI Refactoring** (1.1-1.2)
  - Convert to command group
  - Move semantic to subcommand
- [ ] **2. Query Engine** (2.1-2.6)
  - Create module structure
  - Implement CodeQueryEngine
  - Add all query methods
- [ ] **3. Formatters** (3.1-3.4)
  - Create formatters module
  - Implement text/json/tree formats
- [ ] **4. CLI Query Command** (4.1-4.3)
  - Add query subcommand
  - Wire engine and formatters
- [ ] **5. Testing** (5.1-5.4)
  - Unit tests for engine
  - Integration tests with plant
  - CLI tests
  - Formatter tests
- [ ] **6. Documentation** (6.1-6.3)
  - Update CLAUDE.md
  - Update README.md
  - Update help text
- [ ] **7. Validation** (7.1-7.3)
  - OpenSpec validation
  - Manual testing
  - Full test suite

## Estimated Effort

- **Phase 1 (CLI Refactoring)**: 1-2 hours
- **Phase 2 (Query Engine)**: 4-6 hours
- **Phase 3 (Formatters)**: 2-3 hours
- **Phase 4 (CLI Command)**: 2-3 hours
- **Phase 5 (Testing)**: 4-6 hours
- **Phase 6 (Documentation)**: 2-3 hours
- **Phase 7 (Validation)**: 1-2 hours

**Total**: 16-25 hours (2-3 days of focused work)

## Dependencies

- No new database tables required
- No new dependencies in pyproject.toml
- Requires existing `aud index` and `aud graph build` outputs

## Success Criteria

1. `aud context query --symbol X --show-callers` returns exact results in <50ms
2. `aud context semantic --file Y` still works (backward compatible)
3. All output formats work (text, json, tree)
4. All tests pass (unit, integration, CLI)
5. Documentation complete and accurate
6. Performance meets requirements (10-100x faster than Compass)
