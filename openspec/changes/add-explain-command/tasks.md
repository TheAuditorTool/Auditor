## 0. Verification

- [x] Verified `theauditor/context/query.py` exists with `CodeQueryEngine` class (1,488 lines)
- [x] Verified `theauditor/commands/query.py` exists with click command pattern
- [x] Verified database tables exist: `symbols`, `function_call_args`, `react_components`, `react_hooks`, `refs`, `api_endpoints`
- [x] Verified `edges` table in `graphs.db` for import relationships
- [x] Verified CLI registration pattern in `theauditor/cli.py`
- [x] Verified NO existing `explain.py` in commands/ (will create new)

## 1. Core Infrastructure

- [ ] 1.1 Create `theauditor/utils/code_snippets.py` with `CodeSnippetManager` class
  - File: `theauditor/utils/code_snippets.py` (NEW, ~150 lines)
  - Class: `CodeSnippetManager`
  - Methods:
    - `__init__(self, root_dir: Path, cache_size: int = 20)`
    - `get_snippet(self, file_path: str, line: int, context_mode: str = 'auto') -> str`
    - `_get_file_lines(self, file_path: Path) -> list[str]`
    - `_expand_block(self, lines: list[str], start_idx: int) -> int`
    - `_format_snippet(self, lines: list[str], start_idx: int, end_idx: int) -> str`
  - Safety: 1MB file limit, binary detection, UTF-8 with fallback
  - Cache: OrderedDict LRU, max 20 files
  - Block expansion: indentation-based, max 15 lines

- [ ] 1.2 Create `theauditor/context/explain_formatter.py` with output formatters
  - File: `theauditor/context/explain_formatter.py` (NEW, ~200 lines)
  - Class: `ExplainFormatter`
  - Methods:
    - `format_file_explain(self, data: dict, snippet_manager: CodeSnippetManager) -> str`
    - `format_symbol_explain(self, data: dict, snippet_manager: CodeSnippetManager) -> str`
    - `format_component_explain(self, data: dict, snippet_manager: CodeSnippetManager) -> str`
    - `_format_section(self, title: str, items: list, limit: int = 20) -> str`
    - `_truncate_line(self, line: str, max_len: int = 120) -> str`
  - Output: Plain text (no emojis for Windows CP1252)
  - Sections: SYMBOLS, HOOKS, DEPENDENCIES, DEPENDENTS, OUTGOING CALLS, INCOMING CALLS

## 2. Query Engine Extensions

- [ ] 2.1 Add `get_file_context_bundle()` method to `CodeQueryEngine`
  - File: `theauditor/context/query.py` (MODIFY)
  - Location: Add after `close()` method (~line 1488)
  - Method signature: `def get_file_context_bundle(self, file_path: str, limit: int = 20) -> dict`
  - Returns dict with keys: symbols, hooks, dependencies, dependents, outgoing_calls, incoming_calls
  - Each value is a list (capped at limit)

- [ ] 2.2 Add `get_symbol_context_bundle()` method to `CodeQueryEngine`
  - File: `theauditor/context/query.py` (MODIFY)
  - Location: Add after `get_file_context_bundle()`
  - Method signature: `def get_symbol_context_bundle(self, symbol_name: str, limit: int = 20) -> dict`
  - Returns dict with keys: definition, callers, callees, related_symbols
  - Uses existing `find_symbol()`, `get_callers()`, `get_callees()` methods

- [ ] 2.3 Add `_get_react_hooks()` private method to `CodeQueryEngine`
  - File: `theauditor/context/query.py` (MODIFY)
  - Location: Add in private methods section (~line 193)
  - Method signature: `def _get_react_hooks(self, file_path: str) -> list[dict]`
  - Query: `SELECT hook_name, line FROM react_hooks WHERE file = ?`
  - Returns list of {hook_name, line} dicts

- [ ] 2.4 Add `_get_outgoing_calls()` private method to `CodeQueryEngine`
  - File: `theauditor/context/query.py` (MODIFY)
  - Location: Add after `_get_react_hooks()`
  - Method signature: `def _get_outgoing_calls(self, file_path: str, limit: int = 20) -> list[dict]`
  - Query: `SELECT callee_function, line, argument_expr FROM function_call_args WHERE file = ? LIMIT ?`
  - Returns list of {callee_function, line, arguments} dicts

- [ ] 2.5 Add `_get_incoming_calls()` private method to `CodeQueryEngine`
  - File: `theauditor/context/query.py` (MODIFY)
  - Location: Add after `_get_outgoing_calls()`
  - Method signature: `def _get_incoming_calls(self, file_path: str, limit: int = 20) -> list[dict]`
  - Query: Calls to symbols defined in this file
  - Returns list of {caller_file, caller_line, caller_function, callee_function} dicts

## 3. CLI Command

- [ ] 3.1 Create `theauditor/commands/explain.py` with click command
  - File: `theauditor/commands/explain.py` (NEW, ~200 lines)
  - Command: `@click.command()`
  - Arguments:
    - `target` (required): File path, symbol name, or component name
  - Options:
    - `--depth` (int, default=1): Call graph depth (1-5)
    - `--format` (choice: text/json, default=text): Output format
    - `--section` (choice: symbols/deps/callers/callees/hooks/all, default=all): Filter sections
    - `--no-code` (flag): Disable code snippets (for faster output)
    - `--limit` (int, default=20): Max items per section
  - Functions:
    - `detect_target_type(target: str) -> str`
    - `explain_file(engine, target, snippet_manager, formatter, options) -> str`
    - `explain_symbol(engine, target, snippet_manager, formatter, options) -> str`
    - `explain_component(engine, target, snippet_manager, formatter, options) -> str`

- [ ] 3.2 Register explain command in CLI
  - File: `theauditor/cli.py` (MODIFY)
  - Add import: `from theauditor.commands import explain`
  - Add registration: `cli.add_command(explain.explain)`
  - Location: Group with other context commands (~line 50)

## 4. Query Command Enhancement

- [ ] 4.1 Add `--show-code` flag to query command
  - File: `theauditor/commands/query.py` (MODIFY)
  - Add option: `@click.option("--show-code", is_flag=True, help="Include source code snippets for results")`
  - Modify `format_caller()` function to include code line when flag set
  - Modify `format_callee()` function to include code line when flag set
  - Use `CodeSnippetManager` for line retrieval

## 5. Agent Updates

- [ ] 5.1 Update planning agent to use explain
  - File: `agents/planning.md` (MODIFY)
  - Add step: "Run `aud explain <target>` to get comprehensive context about the file/symbol"
  - Add before current step 1
  - Explain when to use explain vs query

- [ ] 5.2 Update refactor agent to use explain
  - File: `agents/refactor.md` (MODIFY)
  - Add step: "Run `aud explain <target>` to understand the file before modifying"
  - Add before current step 1
  - Explain when to use explain vs query

## 6. Testing

- [ ] 6.1 Create unit tests for CodeSnippetManager
  - File: `tests/test_code_snippets.py` (NEW)
  - Tests:
    - `test_get_snippet_simple_line()`
    - `test_get_snippet_block_expansion()`
    - `test_cache_eviction()`
    - `test_binary_file_handling()`
    - `test_missing_file_handling()`
    - `test_large_file_skip()`

- [ ] 6.2 Create unit tests for ExplainFormatter
  - File: `tests/test_explain_formatter.py` (NEW)
  - Tests:
    - `test_format_file_explain()`
    - `test_format_symbol_explain()`
    - `test_section_limiting()`
    - `test_line_truncation()`

- [ ] 6.3 Create integration tests for explain command
  - File: `tests/test_explain_command.py` (NEW)
  - Tests:
    - `test_explain_file_target()`
    - `test_explain_symbol_target()`
    - `test_explain_component_target()`
    - `test_explain_json_format()`
    - `test_explain_section_filter()`

## 7. Documentation

- [ ] 7.1 Update CLAUDE.md with explain command
  - File: `CLAUDE.md` (MODIFY)
  - Add to "Common CLI Commands" section
  - Add trigger words: "explain", "understand", "what does", "how does"
  - Document typical workflow

## 8. Validation

- [ ] 8.1 Run `aud explain` on test file and verify output format
- [ ] 8.2 Run `aud explain` on symbol and verify output format
- [ ] 8.3 Run `aud explain --format json` and verify JSON structure
- [ ] 8.4 Verify no emoji output (Windows CP1252 compatibility)
- [ ] 8.5 Verify <100ms response time for typical file (50 symbols)
- [ ] 8.6 Run `pytest tests/test_explain*.py -v` - all pass
