## 0. Verification
- [ ] 0.1 Read current `theauditor/linters/linters.py` and document actual batching behavior
- [ ] 0.2 Read current `theauditor/sandbox_executor.py` and map all path resolution points
- [ ] 0.3 Read current `theauditor/venv_install.py` and identify IS_WINDOWS checks
- [ ] 0.4 Verify existing test coverage for linter output format

## 1. Foundation - Toolbox and Types
- [ ] 1.1 Create `theauditor/toolbox.py` with `Toolbox` class
  - `__init__(self, root: Path)` - resolve venv and tools paths
  - `get_binary(name: str) -> Path | None` - find Python/Node binaries
  - `get_config(name: str) -> Path` - get config file path
  - `is_healthy -> bool` - verify toolbox exists
  - All IS_WINDOWS logic encapsulated here
- [ ] 1.2 Create `theauditor/linters/base.py` with:
  - `Finding` dataclass with typed fields
  - `BaseLinter` abstract class with `run()` and `_run_command()` methods
  - `_normalize_path()` helper for consistent path format

## 2. Individual Linter Classes
- [ ] 2.1 Create `theauditor/linters/ruff.py` - `RuffLinter(BaseLinter)`
  - No batching (Rust handles parallelism)
  - Parse JSON output to Finding objects
  - Handle config from Toolbox
- [ ] 2.2 Create `theauditor/linters/eslint.py` - `EslintLinter(BaseLinter)`
  - Dynamic batching based on command length limit
  - Parse JSON array output
  - Handle Windows .cmd extension
- [ ] 2.3 Create `theauditor/linters/mypy.py` - `MypyLinter(BaseLinter)`
  - No batching (needs full project context)
  - Parse JSONL output (one JSON per line)
  - Map severity levels correctly
- [ ] 2.4 Create `theauditor/linters/clippy.py` - `ClippyLinter(BaseLinter)`
  - Run on crate, filter output to requested files
  - Parse Cargo JSON messages
  - Handle message format differences

## 3. Async Orchestrator
- [ ] 3.1 Update `theauditor/linters/linters.py` - `LinterOrchestrator`
  - Use `Toolbox` for all path resolution
  - Add `async _run_async()` with `asyncio.gather()`
  - Keep sync `run_all_linters()` wrapper for backward compatibility
  - Handle exceptions per-linter without failing all
- [ ] 3.2 Add `theauditor/linters/__init__.py` exports
  - Export `LinterOrchestrator`, `Finding`, individual linters

## 4. Cleanup and Migration
- [ ] 4.1 Delete `theauditor/sandbox_executor.py` (replaced by Toolbox)
- [ ] 4.2 Update `theauditor/venv_install.py` to use Toolbox for path checks
- [ ] 4.3 Update any imports in other modules referencing sandbox_executor

## 5. Testing
- [ ] 5.1 Test `Toolbox` path resolution on both Windows and Unix-like paths
- [ ] 5.2 Test individual linter output parsing with sample JSON
- [ ] 5.3 Test async orchestrator runs linters in parallel
- [ ] 5.4 Test backward compatibility of `run_all_linters()` signature

## 6. Integration Verification
- [ ] 6.1 Run `aud full --offline` on TheAuditor itself
- [ ] 6.2 Verify `lint.json` output format unchanged
- [ ] 6.3 Verify database findings table populated correctly
- [ ] 6.4 Time comparison: before/after on sample project
