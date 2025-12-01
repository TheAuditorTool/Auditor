## Context

TheAuditor's linter orchestration (`theauditor/linters/linters.py`, 592 lines) runs ESLint, Ruff, Mypy, and Clippy sequentially. This is a bottleneck - on a project with 500 Python files and 200 JS files, Mypy alone can take 30+ seconds, blocking all other work.

**Stakeholders:** AI agents consuming `lint.json`, developers running `aud full`

**Existing Infrastructure:**
- `theauditor/utils/toolbox.py` - Toolbox class already exists (153 lines), provides all path resolution
- `theauditor/sandbox_executor.py` - Dead code, zero imports, superseded by Toolbox

## Goals / Non-Goals

**Goals:**
- Run all linters in parallel using `asyncio`
- Isolate tool-specific logic in dedicated classes (strategy pattern)
- Use existing `Toolbox` class for path resolution
- Type-safe results with `@dataclass Finding`
- Correct batching strategy per tool (ESLint only)

**Non-Goals:**
- Docker containerization (explicit requirement: native execution only)
- Language server protocol integration
- Incremental linting (file watch mode)
- Custom rule development
- Creating new Toolbox class (already exists)

## Decisions

### Decision 1: asyncio over multiprocessing

**Choice:** Use `asyncio.create_subprocess_exec()` and `asyncio.gather()`

**Rationale:** Linters are I/O bound (waiting for subprocess output), not CPU bound. asyncio provides:
- Native subprocess support without GIL issues
- Simple parallel execution with `gather()`
- No serialization overhead like multiprocessing
- Cleaner error handling with `return_exceptions=True`

**Alternatives considered:**
- `multiprocessing.Pool` - Overkill for I/O bound tasks, pickling issues with Path objects
- `concurrent.futures.ThreadPoolExecutor` - Works but asyncio is more idiomatic for subprocess control
- `trio`/`anyio` - Additional dependency for no real benefit here

### Decision 2: Strategy pattern for tool implementations

**Choice:** Abstract `BaseLinter` class with concrete implementations per tool

```python
# theauditor/linters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Literal
from theauditor.utils.toolbox import Toolbox

@dataclass
class Finding:
    tool: str
    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: Literal["error", "warning", "info"]
    category: str
    additional_info: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)

class BaseLinter(ABC):
    def __init__(self, toolbox: Toolbox, root: Path):
        self.toolbox = toolbox
        self.root = root

    @abstractmethod
    async def run(self, files: list[str]) -> list[Finding]:
        """Run linter on files and return findings."""
        ...

    def _normalize_path(self, path: str) -> str:
        """Normalize path to forward slashes, relative to root."""
        # Extracted from linters.py:454-473
        path = path.replace("\\", "/")
        try:
            abs_path = Path(path)
            if abs_path.is_absolute():
                rel_path = abs_path.relative_to(self.root)
                return str(rel_path).replace("\\", "/")
        except ValueError:
            pass
        return path
```

**Rationale:**
- Each tool has unique output format, batching needs, and configuration
- Adding new tools requires only new class, no modification to orchestrator
- Testing can mock individual linters
- Clear ownership of parsing logic

### Decision 3: Tool-specific batching strategies

**Choice:** Different batching per tool type

| Tool | Strategy | Reason |
|------|----------|--------|
| Ruff | No batching | Rust binary, internally parallelized, handles thousands of files |
| Mypy | No batching | Needs full project context for type inference across files |
| ESLint | Dynamic batching | Node.js, Windows command line limit (8191 chars) |
| Clippy | Crate-level | Cargo requirement - must run on whole crate, filter output |
| golangci-lint | No batching | Go binary, internally parallelized, handles file discovery |
| shellcheck | No batching | Haskell binary, efficient multi-file handling |

**Current code locations to modify:**
- Remove batching from `_run_ruff` (linters.py:235-238)
- Remove batching from `_run_mypy` (linters.py:338-341)
- Keep batching in `_run_eslint` (linters.py:145-148) but make dynamic

**Rationale:** The current uniform `BATCH_SIZE = 100` is wrong for every tool except ESLint:
- Ruff batching adds Python overhead that slows it down
- Mypy batching causes type errors when cross-file imports can't be resolved

### Decision 4: Use existing Toolbox class

**Choice:** Inject existing `Toolbox` from `theauditor/utils/toolbox.py` into `LinterOrchestrator`

**Current Toolbox API (theauditor/utils/toolbox.py:10-153):**
```python
class Toolbox:
    def __init__(self, project_root: Path): ...
    def get_venv_binary(self, name: str, required: bool = True) -> Path | None: ...
    def get_node_runtime(self, required: bool = True) -> Path | None: ...
    def get_eslint(self, required: bool = True) -> Path | None: ...
    def get_eslint_config(self) -> Path: ...
    def get_python_linter_config(self) -> Path: ...
```

**Usage in refactored orchestrator:**
```python
# theauditor/linters/linters.py (refactored)
from theauditor.utils.toolbox import Toolbox

class LinterOrchestrator:
    def __init__(self, root_path: str, db_path: str):
        self.root = Path(root_path).resolve()
        self.toolbox = Toolbox(self.root)  # Inject existing class
        self.db = DatabaseManager(db_path)
```

**Rationale:**
- Toolbox already encapsulates all IS_WINDOWS logic
- Single point of truth reduces bugs when paths change
- Easier testing - mock one class instead of patching everywhere
- Eliminates 4 IS_WINDOWS checks in linters.py (lines 16, 117-118, 137)

### Decision 5: Add Go and Bash linters (scope expansion)

**Choice:** Add `GolangciLinter` and `ShellcheckLinter` to complete language coverage

**Rationale:** Go and Bash extractors exist (`theauditor/indexer/extractors/go.py`, `bash.py`) but linters were missing. Adding them during refactor ensures all indexed languages have lint coverage.

**Implementation:**

```python
# theauditor/linters/golangci.py
class GolangciLinter(BaseLinter):
    async def run(self, files: list[str]) -> list[Finding]:
        # golangci-lint run --out-format json ./...
        # Parse: Issues[].Pos.Filename, Line, Column; FromLinter; Text
```

```python
# theauditor/linters/shellcheck.py
class ShellcheckLinter(BaseLinter):
    async def run(self, files: list[str]) -> list[Finding]:
        # shellcheck --format=json file1.sh file2.sh
        # Parse: [].file, line, column, code, message, level
```

**Toolbox additions:**
- `get_golangci_lint()` - Check sandbox, fallback to system PATH
- `get_shellcheck()` - Check sandbox, fallback to system PATH

Both tools are optional (not installed by `aud setup-ai`). If not found, linter is silently skipped.

### Decision 6: Typed Finding dataclass

**Choice:** Replace `dict[str, Any]` with strict dataclass (shown in Decision 2)

**Current return type (linters.py:54):**
```python
def run_all_linters(self, workset_files: list[str] | None = None) -> list[dict[str, Any]]:
```

**New return type:**
```python
def run_all_linters(self, workset_files: list[str] | None = None) -> list[dict[str, Any]]:
    # Internal: list[Finding]
    # External: converted via Finding.to_dict() for backward compatibility
```

**Rationale:**
- Catches schema violations at creation time, not database write time
- IDE autocomplete for downstream consumers
- `to_dict()` provides dict when needed for DB/JSON
- `Literal` type prevents typos in severity values

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| asyncio complexity for maintainers | Wrap in sync `run_all_linters()` public interface |
| Windows subprocess behavior differences | Toolbox already handles Windows paths |
| Breaking Mypy by removing batching | Actually fixes it - Mypy works better with full context |
| Large file lists exceeding Node limits | Dynamic batching based on actual path lengths |

## Migration Plan

1. **Create base.py** (non-breaking, additive)
   - `Finding` dataclass
   - `BaseLinter` ABC with `_normalize_path()`

2. **Create individual linter classes** (non-breaking, additive)
   - `ruff.py` - Extract from linters.py:224-325, remove batching
   - `eslint.py` - Extract from linters.py:128-222, keep dynamic batching
   - `mypy.py` - Extract from linters.py:327-452, remove batching
   - `clippy.py` - Extract from linters.py:498-592

3. **Update LinterOrchestrator** (internal refactor, same public API)
   - Import Toolbox from `theauditor/utils/toolbox.py`
   - Replace inline path construction with Toolbox methods
   - Add async `_run_async()` with `asyncio.gather()`
   - Keep sync `run_all_linters()` wrapper

4. **Update __init__.py exports** (non-breaking)
   - Export `LinterOrchestrator`, `Finding`, individual linters

5. **Delete dead code** (cleanup)
   - `theauditor/sandbox_executor.py` (zero imports, superseded by Toolbox)

**Rollback:** `git revert` - no schema changes, no external API changes

## Open Questions

None - design is complete. Ready for implementation approval.
