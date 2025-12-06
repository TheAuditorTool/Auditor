# TheAuditor Linters Integration

## Overview

A **unified wrapper layer** for external static analysis tools with:
- **LinterOrchestrator** - Async parallel orchestration
- **BaseLinter** - Abstract strategy pattern base
- **6 supported linters** across 5 languages

---

## Supported Linters

| Linter | Language | File | Features |
|--------|----------|------|----------|
| **RuffLinter** | Python | `ruff.py` | Fast, internally parallelized |
| **MypyLinter** | Python | `mypy.py` | Type checking, needs full context |
| **EslintLinter** | JS/TS | `eslint.py` | Dynamic batching (Windows limit) |
| **ClippyLinter** | Rust | `clippy.py` | Crate-level, output filtering |
| **GolangciLinter** | Go | `golangci.py` | Internally parallelized |
| **ShellcheckLinter** | Bash | `shellcheck.py` | Shell script analysis |

---

## Unified Interface

All linters inherit from `BaseLinter`:

```python
class BaseLinter(ABC):
    @abstractmethod
    async def run(self, files: list[str]) -> LinterResult:
        """Run linter on files, return normalized results."""
        pass
```

### LinterResult
```python
@dataclass
class LinterResult:
    status: str          # SUCCESS | SKIPPED | FAILED
    findings: list[Finding]
    tool: str
    elapsed: float
```

### Finding
```python
@dataclass
class Finding:
    file: str
    line: int
    column: int
    severity: str        # error | warning | info
    message: str
    rule: str
    tool: str
```

---

## Orchestration

```python
class LinterOrchestrator:
    async def run_all_linters(self, workset_files: list[str]) -> dict:
        # Run all 6 linters in parallel
        results = await asyncio.gather(
            self.ruff.run(python_files),
            self.mypy.run(python_files),
            self.eslint.run(js_files),
            self.clippy.run(rust_files),
            self.golangci.run(go_files),
            self.shellcheck.run(bash_files),
            return_exceptions=True
        )
```

**Features:**
- Parallel execution via `asyncio.gather()`
- Individual failures don't affect others
- Workset filtering for targeted analysis

---

## Database Integration

Findings written to `findings_consolidated` table:

```python
def write_findings_batch(self, findings: list[dict]):
    # Batch insertion with tool-specific metadata
    # Supports: cfg_*, graph_*, mypy_*, tf_* fields
    # Atomic transactions with error handling
```

---

## Batching Strategies

| Linter | Strategy | Reason |
|--------|----------|--------|
| **Ruff** | No batching | Internally parallelized |
| **Mypy** | No batching | Needs full project context |
| **ESLint** | Dynamic batching | 8191 char Windows cmd limit |
| **Clippy** | Crate-level | Rust compilation unit |
| **GolangCI** | No batching | Internally parallelized |
| **ShellCheck** | No batching | Fast enough |

### ESLint Dynamic Batching
```python
def _batch_files(self, files: list[str]) -> list[list[str]]:
    # Split files into batches that fit Windows command line limit
    # MAX_CMD_LENGTH = 8191
    batches = []
    current_batch = []
    current_length = len(base_cmd)

    for file in files:
        if current_length + len(file) + 1 > MAX_CMD_LENGTH:
            batches.append(current_batch)
            current_batch = []
            current_length = len(base_cmd)
        current_batch.append(file)
        current_length += len(file) + 1
```

---

## Path Normalization

All linters use common normalization:
```python
def _normalize_path(self, path: str) -> str:
    """Convert absolute paths to relative for database storage."""
    return str(Path(path).relative_to(self.root))
```

---

## Output Integration

Results flow to:
1. **Console**: Rich-formatted summary
2. **Database**: `findings_consolidated` table
3. **JSON**: `.pf/raw/lint.json`

---

## Performance

| Linter | Typical Time (1K files) |
|--------|-------------------------|
| Ruff | 1-3 sec |
| Mypy | 5-15 sec |
| ESLint | 3-10 sec |
| Clippy | 5-20 sec |
| GolangCI | 3-10 sec |
| ShellCheck | 1-3 sec |
| **Total (parallel)** | **5-20 sec** |
