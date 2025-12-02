## Why

The current linter orchestration in `theauditor/linters/linters.py` (592 lines) is sequential and uses incorrect batching. ESLint blocks Ruff blocks Mypy - if Mypy hangs for 30 seconds, everything waits. The uniform `BATCH_SIZE = 100` (line 20) is wrong for Ruff (internally parallelized) and Mypy (needs full project context for cross-file type inference).

**Current Problems (with line references):**
- Sequential execution via `subprocess.run()` - no parallelism
- Uniform batching at lines 145-148 (ESLint), 235-238 (Ruff), 338-341 (Mypy)
- Returns `list[dict[str, Any]]` instead of typed dataclass (line 54)
- Doesn't use existing `Toolbox` class from `theauditor/utils/toolbox.py`

## What Changes

- **Async execution**: Replace sequential `subprocess.run()` with `asyncio.create_subprocess_exec()` and `asyncio.gather()` - all linters run in parallel, total time = slowest linter not sum of all
- **Strategy pattern**: Create `BaseLinter` ABC with tool-specific subclasses (`RuffLinter`, `EslintLinter`, `MypyLinter`, `ClippyLinter`) - extract parsing logic from current methods
- **Typed results**: Replace loose `dict[str, Any]` with `@dataclass Finding` for type safety
- **Use existing Toolbox**: Inject `Toolbox` from `theauditor/utils/toolbox.py` instead of inline path construction
- **Smart batching**: Only batch ESLint (Windows command line limits), remove batching from Ruff and Mypy

## Impact

- Affected specs: `pipeline` (linting stage)
- Affected code:
  - `theauditor/linters/linters.py` - Refactor to use strategy pattern + async
  - `theauditor/linters/base.py` - New file: `BaseLinter` ABC + `Finding` dataclass
  - `theauditor/linters/ruff.py` - New file: Extract from `linters.py:224-325`
  - `theauditor/linters/eslint.py` - New file: Extract from `linters.py:128-222`
  - `theauditor/linters/mypy.py` - New file: Extract from `linters.py:327-452`
  - `theauditor/linters/clippy.py` - New file: Extract from `linters.py:498-592`
  - `theauditor/linters/golangci.py` - **New file**: Go linting via golangci-lint (was missing)
  - `theauditor/linters/shellcheck.py` - **New file**: Bash linting via shellcheck (was missing)
  - `theauditor/utils/toolbox.py` - Add `get_golangci_lint()` and `get_shellcheck()` methods
- Files to DELETE:
  - `theauditor/sandbox_executor.py` - Superseded by `theauditor/utils/toolbox.py` (no imports found)
- Breaking changes: None (same public interface `LinterOrchestrator.run_all_linters()`)
- Performance: Expected 40-60% faster on multi-core systems (parallel execution)
- Risk: Low - existing tests cover output format, internal restructuring only
- **Expanded scope**: Added Go and Bash linters to complete language coverage (extractors existed but linters were missing)

## Verified Current State

### linters.py Structure (592 lines)

| Lines | Method | Purpose | Extract To |
|-------|--------|---------|------------|
| 27-53 | `__init__` | Setup, validates toolbox path | Keep in orchestrator |
| 54-89 | `run_all_linters` | Sequential orchestration | Refactor to async |
| 91-113 | `_get_source_files` | Query DB for files by extension | Keep in orchestrator |
| 115-126 | `_get_venv_binary` | Find Python binary | Replace with `Toolbox.get_venv_binary()` |
| 128-155 | `_run_eslint` | Batch loop for ESLint | Extract to `EslintLinter` |
| 157-222 | `_run_eslint_batch` | Single ESLint batch | Extract to `EslintLinter` |
| 224-245 | `_run_ruff` | Batch loop for Ruff | Extract to `RuffLinter` (remove batching) |
| 247-325 | `_run_ruff_batch` | Single Ruff batch | Extract to `RuffLinter` |
| 327-348 | `_run_mypy` | Batch loop for Mypy | Extract to `MypyLinter` (remove batching) |
| 350-452 | `_run_mypy_batch` | Single Mypy batch | Extract to `MypyLinter` |
| 454-473 | `_normalize_path` | Path normalization | Move to `BaseLinter` |
| 475-496 | `_write_json_output` | Write lint.json | Keep in orchestrator |
| 498-592 | `_run_clippy` | Clippy execution | Extract to `ClippyLinter` |

### IS_WINDOWS Usage in linters.py (4 locations)

| Line | Usage | Resolution |
|------|-------|------------|
| 16 | `IS_WINDOWS = platform.system() == "Windows"` | Remove - use Toolbox |
| 117-118 | `_get_venv_binary` path construction | Replace with `Toolbox.get_venv_binary()` |
| 137 | ESLint `.cmd` extension | Replace with `Toolbox.get_eslint()` |

### Existing Toolbox Class (theauditor/utils/toolbox.py)

The `Toolbox` class already exists and provides:
- `get_venv_binary(name)` - Python linter binaries (ruff, mypy)
- `get_eslint()` - ESLint binary path
- `get_eslint_config()` - eslint.config.cjs path
- `get_python_linter_config()` - pyproject.toml path
- `get_node_runtime()` - Node.js executable
- `get_npm_command()` - npm command array

**Action**: Inject Toolbox into LinterOrchestrator instead of constructing paths inline.

### sandbox_executor.py Status

File exists at `theauditor/sandbox_executor.py` (109 lines) but has **zero imports** in the codebase (verified via grep). It's dead code superseded by `theauditor/utils/toolbox.py`. Safe to delete.

### Batching Behavior (BATCH_SIZE = 100)

| Tool | Current | Correct | Why |
|------|---------|---------|-----|
| ESLint | Batched (line 145) | Keep batched | Windows 8191 char command limit |
| Ruff | Batched (line 235) | Remove batching | Rust binary, internally parallelized |
| Mypy | Batched (line 338) | Remove batching | Needs full project for cross-file types |
| Clippy | No batching | Keep as-is | Runs on whole crate |
