## 1. Foundation - Base Classes and Types

- [ ] 1.1 Create `theauditor/linters/base.py`
  - `Finding` dataclass with typed fields (see design.md Decision 2)
  - `BaseLinter` ABC with `run()` method signature
  - `_normalize_path()` helper extracted from linters.py:454-473
  - `_run_command()` async helper for subprocess execution

## 2. Individual Linter Classes

- [ ] 2.1 Create `theauditor/linters/ruff.py` - `RuffLinter(BaseLinter)`
  - Extract from linters.py:224-325
  - **Remove batching** - pass all files in single invocation
  - Get binary via `self.toolbox.get_venv_binary("ruff")`
  - Get config via `self.toolbox.get_python_linter_config()`
  - Parse JSON output to Finding objects

- [ ] 2.2 Create `theauditor/linters/eslint.py` - `EslintLinter(BaseLinter)`
  - Extract from linters.py:128-222
  - **Keep dynamic batching** based on command length (8191 char Windows limit)
  - Get binary via `self.toolbox.get_eslint()`
  - Get config via `self.toolbox.get_eslint_config()`
  - Parse JSON array output

- [ ] 2.3 Create `theauditor/linters/mypy.py` - `MypyLinter(BaseLinter)`
  - Extract from linters.py:327-452
  - **Remove batching** - needs full project context for cross-file types
  - Get binary via `self.toolbox.get_venv_binary("mypy")`
  - Get config via `self.toolbox.get_python_linter_config()`
  - Parse JSONL output (one JSON per line)
  - Map severity levels: note -> info, error -> error, warning -> warning

- [ ] 2.4 Create `theauditor/linters/clippy.py` - `ClippyLinter(BaseLinter)`
  - Extract from linters.py:498-592
  - Run `cargo clippy` on crate, filter output to requested files
  - Parse Cargo JSON messages (reason == "compiler-message")
  - Handle message format differences

## 3. Async Orchestrator Refactor

- [ ] 3.1 Update `theauditor/linters/linters.py` - `LinterOrchestrator`
  - Import `Toolbox` from `theauditor/utils/toolbox.py`
  - Replace `self.toolbox = self.root / ".auditor_venv" / ".theauditor_tools"` with `self.toolbox = Toolbox(self.root)`
  - Remove `IS_WINDOWS` constant (line 16)
  - Remove `_get_venv_binary()` method (lines 115-126) - use Toolbox
  - Add `async _run_async()` using `asyncio.gather()` with `return_exceptions=True`
  - Keep sync `run_all_linters()` wrapper using `asyncio.run()`
  - Convert Finding objects to dicts for backward compatibility

- [ ] 3.2 Update `theauditor/linters/__init__.py`
  - Export `LinterOrchestrator`, `Finding`, `BaseLinter`
  - Export individual linters: `RuffLinter`, `EslintLinter`, `MypyLinter`, `ClippyLinter`

## 4. Cleanup

- [ ] 4.1 Delete `theauditor/sandbox_executor.py`
  - Verified zero imports in codebase
  - Superseded by `theauditor/utils/toolbox.py`

- [ ] 4.2 Remove redundant code from `linters.py`
  - Delete extracted methods after linter classes are working
  - Target: reduce from 592 lines to ~150 lines (orchestrator only)

## 5. Testing

- [ ] 5.1 Test `BaseLinter._normalize_path()` with Windows and Unix paths
- [ ] 5.2 Test individual linter output parsing with sample JSON fixtures
- [ ] 5.3 Test async orchestrator runs linters in parallel (timing comparison)
- [ ] 5.4 Test backward compatibility of `run_all_linters()` return format

## 6. Integration Verification

- [ ] 6.1 Run `aud full --offline` on TheAuditor itself
- [ ] 6.2 Verify `lint.json` output format unchanged (diff against baseline)
- [ ] 6.3 Verify database findings table populated correctly
- [ ] 6.4 Time comparison: sequential vs parallel on sample project

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
