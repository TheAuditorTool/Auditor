## 1. Foundation - Base Classes and Types

- [x] 1.1 Create `theauditor/linters/base.py`
  - `Finding` dataclass with typed fields (see design.md Decision 2)
  - `BaseLinter` ABC with `run()` method signature
  - `_normalize_path()` helper extracted from linters.py:454-473
  - `_run_command()` async helper for subprocess execution

## 2. Individual Linter Classes

- [x] 2.1 Create `theauditor/linters/ruff.py` - `RuffLinter(BaseLinter)`
  - Extract from linters.py:224-325
  - **Remove batching** - pass all files in single invocation
  - Get binary via `self.toolbox.get_venv_binary("ruff")`
  - Get config via `self.toolbox.get_python_linter_config()`
  - Parse JSON output to Finding objects

- [x] 2.2 Create `theauditor/linters/eslint.py` - `EslintLinter(BaseLinter)`
  - Extract from linters.py:128-222
  - **Keep dynamic batching** based on command length (8191 char Windows limit)
  - Get binary via `self.toolbox.get_eslint()`
  - Get config via `self.toolbox.get_eslint_config()`
  - Parse JSON array output

- [x] 2.3 Create `theauditor/linters/mypy.py` - `MypyLinter(BaseLinter)`
  - Extract from linters.py:327-452
  - **Remove batching** - needs full project context for cross-file types
  - Get binary via `self.toolbox.get_venv_binary("mypy")`
  - Get config via `self.toolbox.get_python_linter_config()`
  - Parse JSONL output (one JSON per line)
  - Map severity levels: note -> info, error -> error, warning -> warning

- [x] 2.4 Create `theauditor/linters/clippy.py` - `ClippyLinter(BaseLinter)`
  - Extract from linters.py:498-592
  - Run `cargo clippy` on crate, filter output to requested files
  - Parse Cargo JSON messages (reason == "compiler-message")
  - Handle message format differences

- [x] 2.5 Create `theauditor/linters/golangci.py` - `GolangciLinter(BaseLinter)` **NEW**
  - **New linter** - Go support was missing from linters.py
  - Get binary via `self.toolbox.get_golangci_lint()` (system PATH fallback)
  - Run `golangci-lint run --out-format json` on Go files
  - Parse JSON output: extract file, line, column, rule (from Linter field), message
  - Map severity: error -> error, warning -> warning
  - **No batching** - golangci-lint handles file discovery internally

- [x] 2.6 Create `theauditor/linters/shellcheck.py` - `ShellcheckLinter(BaseLinter)` **NEW**
  - **New linter** - Bash support was missing from linters.py
  - Get binary via `self.toolbox.get_shellcheck()` (system PATH fallback)
  - Run `shellcheck --format=json` on .sh/.bash files
  - Parse JSON output: extract file, line, column, code (SC####), message
  - Map severity: error -> error, warning -> warning, info -> info, style -> info
  - **No batching** - shellcheck handles multiple files efficiently

## 2.5 Toolbox Additions

- [x] 2.7 Add `get_golangci_lint()` to `theauditor/utils/toolbox.py`
  - Check `.auditor_venv/.theauditor_tools/bin/golangci-lint` first
  - Fall back to system PATH via `shutil.which("golangci-lint")`
  - Return None if not found (optional tool)

- [x] 2.8 Add `get_shellcheck()` to `theauditor/utils/toolbox.py`
  - Check `.auditor_venv/.theauditor_tools/bin/shellcheck` first
  - Fall back to system PATH via `shutil.which("shellcheck")`
  - Return None if not found (optional tool)

## 3. Async Orchestrator Refactor

- [x] 3.1 Update `theauditor/linters/linters.py` - `LinterOrchestrator`
  - Import `Toolbox` from `theauditor/utils/toolbox.py`
  - Replace `self.toolbox = self.root / ".auditor_venv" / ".theauditor_tools"` with `self.toolbox = Toolbox(self.root)`
  - Remove `IS_WINDOWS` constant (line 16)
  - Remove `_get_venv_binary()` method (lines 115-126) - use Toolbox
  - Add `async _run_async()` using `asyncio.gather()` with `return_exceptions=True`
  - Keep sync `run_all_linters()` wrapper using `asyncio.run()`
  - Convert Finding objects to dicts for backward compatibility

- [x] 3.2 Update `theauditor/linters/__init__.py`
  - Export `LinterOrchestrator`, `Finding`, `BaseLinter`
  - Export individual linters: `RuffLinter`, `EslintLinter`, `MypyLinter`, `ClippyLinter`, `GolangciLinter`, `ShellcheckLinter`

- [x] 3.3 Update orchestrator to handle Go and Bash files
  - Add `go_files = self._get_source_files([".go"])`
  - Add `sh_files = self._get_source_files([".sh", ".bash"])`
  - Include `GolangciLinter` and `ShellcheckLinter` in async gather

## 4. Cleanup

- [x] 4.1 Delete `theauditor/sandbox_executor.py`
  - Verified zero imports in codebase
  - Superseded by `theauditor/utils/toolbox.py`

- [x] 4.2 Remove redundant code from `linters.py`
  - Delete extracted methods after linter classes are working
  - Target: reduce from 592 lines to ~150 lines (orchestrator only)

## 5. Testing

- [x] 5.1 Test `BaseLinter._normalize_path()` with Windows and Unix paths
- [x] 5.2 Test individual linter output parsing with sample JSON fixtures
- [x] 5.3 Test async orchestrator runs linters in parallel (timing comparison)
- [x] 5.4 Test backward compatibility of `run_all_linters()` return format

## 6. Integration Verification

- [x] 6.1 Run `aud full --offline` on TheAuditor itself
- [x] 6.2 Verify `lint.json` output format unchanged (diff against baseline)
- [x] 6.3 Verify database findings table populated correctly
- [x] 6.4 Time comparison: sequential vs parallel on sample project

## 7. Audit Remediation

- [x] 7.1 Fix Clippy file filtering (audit finding)
  - Task 2.4 spec said "filter output to requested files" but was not implemented
  - Added `requested_files` set for O(1) lookup in `clippy.py:64-65`
  - Added filtering logic in `clippy.py:85-96`
  - Updated logging to show filtered vs total count
  - Now matches spec: `aud lint src/main.rs` returns only findings for that file

## Code References

| Source | Destination | Lines |
|--------|-------------|-------|
| linters.py:224-325 | ruff.py | Ruff execution + parsing |
| linters.py:128-222 | eslint.py | ESLint execution + parsing |
| linters.py:327-452 | mypy.py | Mypy execution + parsing |
| linters.py:498-592 | clippy.py | Clippy execution + parsing |
| linters.py:454-473 | base.py | `_normalize_path()` |
| linters.py:115-126 | DELETE | Replaced by Toolbox |
| linters.py:16 | DELETE | IS_WINDOWS constant |
| NEW | golangci.py | Go linting via golangci-lint |
| NEW | shellcheck.py | Bash linting via shellcheck |
| toolbox.py | ADD methods | `get_golangci_lint()`, `get_shellcheck()` |
