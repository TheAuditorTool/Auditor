## Why

The current linter orchestration is sequential and fragile. ESLint blocks Ruff blocks Mypy - if Mypy hangs for 30 seconds, everything waits. Batching Mypy in 100-file chunks actually breaks type inference (Mypy needs full project context). The `LinterOrchestrator` class is a 600-line god class containing parsing logic for 4 different tools. Path handling is scattered with `if IS_WINDOWS` checks everywhere.

## What Changes

- **Async execution**: Replace sequential `subprocess.run()` with `asyncio.create_subprocess_exec()` and `asyncio.gather()` - all linters run in parallel, total time = slowest linter not sum of all
- **Strategy pattern**: Create `BaseLinter` ABC with tool-specific subclasses (`RuffLinter`, `EslintLinter`, `MypyLinter`, `ClippyLinter`) - move parsing logic into each class
- **Typed results**: Replace loose `dict[str, Any]` with `@dataclass Finding` for type safety
- **Toolbox abstraction**: Create unified `Toolbox` class to centralize all path resolution (Python binaries, Node binaries, configs) - eliminate scattered `IS_WINDOWS` checks
- **Smart batching**: Only batch ESLint (Windows command line limits), let Ruff and Mypy run on full file list - Ruff is internally parallelized, Mypy needs full context for type inference
- **No Docker dependency**: Pure native execution with portable Node.js download (existing approach, cleaned up)

## Impact

- Affected specs: `pipeline` (linting stage)
- Affected code:
  - `theauditor/linters/linters.py` - Complete rewrite
  - `theauditor/sandbox_executor.py` - Replace with `toolbox.py`
  - `theauditor/venv_install.py` - Simplify path handling, remove redundant code
- Breaking changes: None (same public interface `LinterOrchestrator.run_all_linters()`)
- Performance: Expected 40-60% faster on multi-core systems (parallel execution)
- Risk: Low - existing tests cover output format, internal restructuring only
