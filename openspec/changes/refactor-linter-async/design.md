## Context

TheAuditor's linter orchestration (`theauditor/linters/linters.py`) runs ESLint, Ruff, Mypy, and Clippy sequentially. This is a bottleneck - on a project with 500 Python files and 200 JS files, Mypy alone can take 30+ seconds, blocking all other work.

The code also suffers from:
- **God class anti-pattern**: 600 lines with parsing for all 4 tools mixed together
- **Incorrect batching**: Mypy batched in 100-file chunks breaks cross-file type inference
- **Path spaghetti**: `if IS_WINDOWS` scattered throughout multiple files
- **Untyped returns**: `list[dict[str, Any]]` loses type information

Stakeholders: AI agents consuming `lint.json`, developers running `aud full`

## Goals / Non-Goals

**Goals:**
- Run all linters in parallel using `asyncio`
- Isolate tool-specific logic in dedicated classes
- Single source of truth for path resolution (`Toolbox` class)
- Type-safe results with `@dataclass Finding`
- Correct batching strategy per tool

**Non-Goals:**
- Docker containerization (explicit requirement: native execution only)
- Language server protocol integration
- Incremental linting (file watch mode)
- Custom rule development

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
class BaseLinter(ABC):
    @abstractmethod
    async def run(self, files: list[str]) -> list[Finding]: ...

class RuffLinter(BaseLinter): ...
class EslintLinter(BaseLinter): ...
class MypyLinter(BaseLinter): ...
class ClippyLinter(BaseLinter): ...
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

**Rationale:** The current uniform `BATCH_SIZE = 100` is wrong for every tool except ESLint. Ruff batching adds Python overhead that slows it down. Mypy batching causes type errors when cross-file imports can't be resolved.

### Decision 4: Toolbox class for path resolution

**Choice:** Single `Toolbox` class encapsulating all runtime paths

```python
class Toolbox:
    def __init__(self, root: Path):
        self.root = root
        self.venv = root / ".auditor_venv"
        self.tools_dir = self.venv / ".theauditor_tools"
        # Platform logic inside, not scattered

    def get_binary(self, name: str) -> Path | None: ...
    def get_config(self, name: str) -> Path: ...
```

**Rationale:**
- Current code has 15+ places checking `IS_WINDOWS` for path construction
- Single point of truth reduces bugs when paths change
- Easier testing - mock one class instead of patching everywhere
- Clean separation: `venv_install.py` creates, `Toolbox` queries

### Decision 5: Typed Finding dataclass

**Choice:** Replace `dict[str, Any]` with strict dataclass

```python
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
```

**Rationale:**
- Catches schema violations at creation time, not database write time
- IDE autocomplete for downstream consumers
- `asdict()` provides dict when needed for DB/JSON
- `Literal` type prevents typos in severity values

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| asyncio complexity for maintainers | Wrap in sync `run_all_linters()` public interface |
| Windows subprocess behavior differences | Test matrix includes Windows in CI |
| Breaking Mypy by removing batching | Actually fixes it - Mypy works better with full context |
| Large file lists exceeding Node limits | Dynamic batching based on `MAX_CMD_LENGTH` constant |

## Migration Plan

1. Create `theauditor/toolbox.py` with path resolution (non-breaking, additive)
2. Create `theauditor/linters/base.py` with `BaseLinter` and `Finding` (non-breaking, additive)
3. Create individual linter classes in `theauditor/linters/` directory (non-breaking, additive)
4. Update `LinterOrchestrator` to use new classes (internal refactor, same public API)
5. Delete `sandbox_executor.py` (replaced by `Toolbox`)
6. Simplify `venv_install.py` path handling (use `Toolbox` internally)

Rollback: `git revert` - no schema changes, no external API changes

## Open Questions

None - design is complete. Ready for implementation approval.
