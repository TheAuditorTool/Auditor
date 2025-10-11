# HANDOFF: Rust Language Support Implementation for v1.1

**Date**: 2025-10-11
**Branch Context**: Work completed on `feat/rust-support-discovery` (based on `main`)
**Target**: Need to port to `upstream/v1.1` branch (clean implementation)
**Status**: Complete implementation on wrong branch, ready to port

---

## Executive Summary

We successfully implemented comprehensive Rust language support for TheAuditor, including:
- LSP-based semantic analysis via rust-analyzer
- Cargo.toml dependency parsing
- Sandboxed toolchain management
- Persistent LSP sessions (5x performance)
- 626 symbols extracted from 30-file test project (hegel-cli)

**Problem**: Implemented on `main` branch, but production is on `upstream/v1.1` which has 84 commits of major refactoring (+73K/-18K lines).

**Solution**: Option 3 - Fresh implementation on v1.1 using completed work as reference.

---

## What Was Built (Reference Implementation)

### Architecture Overview

```
theauditor/
├── lsp/                              # NEW: LSP protocol layer
│   ├── __init__.py
│   └── rust_analyzer_client.py       # 323 lines: Protocol + symbol parsing
│
├── toolboxes/                        # NEW: Language toolchain management
│   ├── __init__.py                   # LanguageToolbox interface
│   ├── base.py                       # 104 lines: Common utilities
│   └── rust.py                       # 227 lines: RustToolbox implementation
│
├── indexer/
│   ├── __init__.py                   # MODIFIED: Added cleanup hooks
│   ├── extractors/
│   │   ├── __init__.py               # MODIFIED: Added cleanup() interface
│   │   └── rust.py                   # NEW: 192 lines: RustExtractor
│   └── database.py                   # (v1.1 has major changes here)
│
├── deps.py                           # MODIFIED: Added _parse_cargo_toml()
└── venv_install.py                   # MODIFIED: Added Rust detection/setup

tests/
└── test_rust_extraction.py           # NEW: 139 lines: Validation script

CLAUDE.md                             # MODIFIED: Added Rust documentation
```

---

## Key Implementation Details (Preserve These)

### 1. LSP Client (`theauditor/lsp/rust_analyzer_client.py`)

**Purpose**: JSON-RPC LSP client for rust-analyzer communication

**Key Features**:
- Process management (start, initialize, shutdown)
- LSP protocol methods: `did_open()`, `did_close()`, `document_symbol()`
- Content-Length header handling for LSP messages
- Response ID matching (skips notifications)
- Symbol parsing: LSP DocumentSymbol → TheAuditor format

**Critical Constants**:
```python
LSP_ANALYSIS_DELAY_SEC = 0.2
LSP_REQUEST_TIMEOUT_SEC = 5
LSP_SHUTDOWN_TIMEOUT_SEC = 2
LSP_READ_TIMEOUT_SEC = 10
```

**DRY Helpers** (don't skip these):
```python
_build_request(method, params)      # Builds LSP request dict
_build_notification(method, params) # Builds LSP notification dict
_send_message(message_dict)         # Sends with Content-Length header
```

**Symbol Mapping**:
```python
kind_map = {
    2: 'module',    # Module declarations
    5: 'impl',      # Class → impl blocks in Rust
    6: 'method',
    8: 'field',
    10: 'enum',
    11: 'trait',    # Interface → trait
    12: 'function',
    13: 'variable',
    14: 'const',
    23: 'struct',
    26: 'type'
}
```

**Important**: `parse_lsp_symbols()` recursively processes nested symbols (struct fields, impl methods).

---

### 2. RustExtractor (`theauditor/indexer/extractors/rust.py`)

**Purpose**: Extract symbols and imports from Rust files

**Critical Design Decision - Persistent LSP**:
```python
class RustExtractor(BaseExtractor):
    def __init__(self):
        self._lsp_client = None           # Reused across ALL files
        self._temp_workspace = None       # Single temp workspace
        self._file_counter = 0            # Unique filenames

    def _get_or_create_lsp_client(self):
        # Only creates ONCE, reuses for all files
        # 5x performance improvement (1s → 200ms per file)
```

**Why Persistent LSP Matters**:
- Without: Each file spawns new rust-analyzer process (~1s startup)
- With: One process handles all files (~200ms per file)
- hegel-cli (30 files): 30s → 6s

**Critical Bug Fix - Unique File URIs**:
```python
# WRONG (causes timeouts after ~7 files):
temp_file = workspace / 'src' / 'lib.rs'  # Reuses same URI

# CORRECT:
temp_file = workspace / 'src' / f'file_{self._file_counter}.rs'  # Unique per file
```

**Why**: LSP gets confused by rapid open/close of same URI. Unique filenames avoid this entirely.

**Imports Extraction**:
```python
use_pattern = re.compile(r'^\s*(?:pub\s+)?use\s+([^;]+);', re.MULTILINE)
```
Matches: `use std::fs::File;`, `pub use commands::start;`, `use serde::{Serialize, Deserialize};`

**Cleanup Hook**:
```python
def cleanup(self):
    # Called by IndexerOrchestrator after all files
    if self._lsp_client:
        self._lsp_client.shutdown()
    if self._temp_workspace:
        shutil.rmtree(self._temp_workspace)
```

---

### 3. RustToolbox (`theauditor/toolboxes/rust.py`)

**Purpose**: Manage rust-analyzer binary installation

**Key Methods**:

**1. Detection**:
```python
def detect_project(self, project_dir: Path) -> bool:
    return (project_dir / 'Cargo.toml').exists()
```

**2. Installation**:
- Downloads from GitHub: `https://github.com/rust-lang/rust-analyzer/releases/latest`
- Platform detection: darwin (arm64/x86_64), linux (x86_64), windows
- Installs to: `~/.auditor_venv/.theauditor_tools/rust/rust-analyzer`
- Verifies with `--version` check

**3. Platform Mapping**:
```python
'darwin' + 'arm64' → 'aarch64-apple-darwin'
'darwin' + 'x86_64' → 'x86_64-apple-darwin'
'linux' → 'x86_64-unknown-linux-gnu'
'windows' → 'x86_64-pc-windows-msvc'
```

**DRY Helpers**:
```python
_verify_binary(path) → (success: bool, version: str)
_build_result(status, path, version, cached, message) → dict
```

---

### 4. Toolbox Base Utilities (`theauditor/toolboxes/base.py`)

**Reusable helpers** (not Rust-specific):

```python
download_file(url, dest, timeout=30)           # URL → file with User-Agent
decompress_gz(src, dest)                       # .gz extraction
decompress_zip(src, dest_dir, binary_name)     # .zip extraction
get_sandbox_dir() → Path                       # ~/.auditor_venv/.theauditor_tools/
detect_platform() → dict                       # {'os', 'machine', 'is_windows'}
```

---

### 5. Cargo.toml Parser (`theauditor/deps.py`)

**Added Functions**:

```python
def _parse_cargo_deps(deps_dict: Dict, kind: str) -> List[Dict]:
    """Parse [dependencies] or [dev-dependencies] section."""
    # Handles both: dep = "1.0" and dep = { version = "1.0", features = [...] }

def _parse_cargo_toml(path: Path) -> List[Dict]:
    """Parse Cargo.toml using tomllib (Python 3.11+) or tomli fallback."""
    # Returns list of dicts: {name, version, manager, features, kind, source}
```

**Integration**:
```python
# In parse_dependencies():
cargo_toml = sanitize_path("Cargo.toml", root_path)
if cargo_toml.exists():
    deps.extend(_parse_cargo_toml(cargo_toml))
```

---

### 6. Setup Integration (`theauditor/venv_install.py`)

**Added to `setup_project_venv()`**:

```python
# After JS/TS setup, before return:
from theauditor.toolboxes.rust import RustToolbox

rust_toolbox = RustToolbox()
if rust_toolbox.detect_project(target_dir):
    print(f"  Rust project detected (Cargo.toml found)")
    result = rust_toolbox.install()

    if result['status'] in ['success', 'cached']:
        print(f"    ✓ rust-analyzer installed: {result['path']}")
        print(f"    ✓ Version: {result['version']}")
```

---

### 7. Cleanup Interface (`theauditor/indexer/extractors/__init__.py`)

**Added to BaseExtractor**:

```python
def cleanup(self) -> None:
    """Clean up extractor resources after all files processed.

    Override this if extractor maintains persistent resources
    (LSP sessions, database connections, temp directories).

    Default: no-op.
    """
    pass
```

**Called from IndexerOrchestrator** (`theauditor/indexer/__init__.py`):

```python
def index(self):
    # ... process all files ...

    # NEW: Cleanup extractor resources
    self._cleanup_extractors()

    self.db_manager.commit()

def _cleanup_extractors(self):
    """Call cleanup() on all extractors."""
    for extractor in self.extractor_registry.extractors.values():
        try:
            extractor.cleanup()
        except Exception as e:
            logger.debug(f"Extractor cleanup failed: {e}")
```

---

## Test Validation Script

**Location**: `tests/test_rust_extraction.py` (139 lines)

**What It Does**:
1. Detects Rust project (Cargo.toml)
2. Removes old database
3. Runs `aud index` on hegel-cli (~6K LOC, 30 files)
4. Queries database for Rust symbols
5. Reports statistics and sample output

**Expected Results** (hegel-cli):
```
Rust files indexed: 30
Rust symbols extracted: 626

Symbols by type:
  function: 349 (56%)
  field: 127 (20%)
  module: 51 (8%)
  method: 31 (5%)
  struct: 30 (5%)
  const: 4
  enum: 4
  unknown: 30

Use statements: 237
```

**Performance**: ~6 seconds (with persistent LSP)

---

## Critical Learnings & Decisions

### 1. Why LSP Instead of Tree-sitter?

**Decision**: Sandboxed rust-analyzer LSP

**Reasoning**:
- Tree-sitter: Fast (50ms) but syntactic only (no types, no semantic info)
- rust-analyzer: Slower (200ms) but provides types, visibility, symbol resolution
- Parity with JS/TS approach (also uses LSP via TypeScript compiler)
- Enables future taint analysis, pattern detection

**Tradeoff Accepted**: 200ms per file vs 50ms, gain semantic accuracy

---

### 2. Persistent LSP Session

**Initial Implementation**: Fresh LSP per file (toy validation)
- Simple, works for proof-of-concept
- 30 files × 1s = 30 seconds

**Production Implementation**: Single persistent LSP
- Added state to extractor (`_lsp_client`, `_temp_workspace`)
- Added cleanup hook to BaseExtractor interface
- 30 files × 200ms = 6 seconds (5x improvement)

**Key Insight**: Infrastructure investment (cleanup interface) pays off immediately.

---

### 3. Unique File URIs to Avoid Timeouts

**Bug**: After 6-7 files, rust-analyzer stopped responding (timeout errors)

**Root Cause**: Reusing same file URI (`lib.rs`) repeatedly. LSP protocol expects:
- `didOpen` on new URI
- OR `didChange` on existing URI
- NOT rapid `didClose` → `didOpen` on same URI

**Fix**: Use unique filenames per file (`file_1.rs`, `file_2.rs`, etc.)
- Avoids LSP file management entirely
- No need for `didClose` calls
- Simple, robust

---

### 4. Module Symbol Type Mapping

**Issue**: 51 module declarations (`mod commands;`) showed as "unknown"

**Cause**: LSP SymbolKind=2 (Module) not in `kind_map`

**Fix**: Added `2: 'module'` to kind mapping

**Impact**: Cosmetic but important for clarity in analysis output

---

## v1.1 Porting Strategy (Option 3: Fresh Implementation)

### Phase 1: Copy New Directories (No Conflicts)

These are completely new, drop them in:

```bash
# 1. Copy LSP layer
cp -r theauditor/lsp/ <v1.1-branch>/theauditor/

# 2. Copy toolboxes
cp -r theauditor/toolboxes/ <v1.1-branch>/theauditor/

# 3. Copy Rust extractor
cp theauditor/indexer/extractors/rust.py <v1.1-branch>/theauditor/indexer/extractors/

# 4. Copy test script
cp tests/test_rust_extraction.py <v1.1-branch>/tests/
```

---

### Phase 2: Integrate with v1.1 Architecture (Manual)

**Critical**: v1.1 has major refactors. Don't blindly copy, adapt to v1.1's patterns.

#### 2.1. Update `theauditor/indexer/extractors/__init__.py`

**Add cleanup interface to BaseExtractor**:
- Check v1.1's BaseExtractor signature (may have changed!)
- Add `cleanup()` method (default no-op)
- Ensure RustExtractor is auto-discovered by registry

**v1.1 Differences to Check**:
- Does BaseExtractor.__init__ signature match?
- Are there new abstract methods required?
- Registry discovery pattern changed?

---

#### 2.2. Update `theauditor/indexer/__init__.py` (or equivalent)

**Add cleanup hook to orchestrator**:

v1.1 likely has `IndexOrchestrator` or similar. Find where indexing loop finishes:

```python
# After all files processed, before final commit:
self._cleanup_extractors()

def _cleanup_extractors(self):
    # Call cleanup() on all registered extractors
```

**v1.1 Differences to Check**:
- Orchestrator class name/location (may have moved)
- Extractor registry access pattern
- Error handling conventions in v1.1

---

#### 2.3. Update `theauditor/deps.py`

**Add Cargo.toml parsing**:

1. Copy `_parse_cargo_deps()` helper function
2. Copy `_parse_cargo_toml()` function
3. Integrate into `parse_dependencies()`:

```python
# Check for Cargo.toml (around where package.json is checked)
cargo_toml = sanitize_path("Cargo.toml", root_path)
if cargo_toml.exists():
    deps.extend(_parse_cargo_toml(cargo_toml))
```

**v1.1 Differences to Check**:
- Has `parse_dependencies()` signature changed?
- New dependency dict schema? (check existing parsers)
- Error handling pattern (may have changed)

---

#### 2.4. Update `theauditor/venv_install.py`

**Add Rust toolchain setup**:

In `setup_project_venv()`, after JS/TS setup:

```python
# Detect and install Rust toolchain
from theauditor.toolboxes.rust import RustToolbox

rust_toolbox = RustToolbox()
if rust_toolbox.detect_project(target_dir):
    print("  Rust project detected")
    result = rust_toolbox.install()
    # Handle result...
```

**v1.1 Differences to Check**:
- Function signature changes
- Setup flow restructured?
- Print vs logger conventions
- Error handling pattern

---

#### 2.5. Update `CLAUDE.md`

Copy Rust documentation section (lines ~400-450 in our version):
- Supported languages section
- Rust-specific handling
- Performance expectations
- Setup requirements

**v1.1 Differences**: CLAUDE.md may have restructured. Adapt to v1.1 format.

---

### Phase 3: Testing & Validation

**Test 1: Setup**
```bash
cd ~/Code/hegel-cli
aud setup-claude --target .
# Should download rust-analyzer (~30MB)
# Should report version
```

**Test 2: Indexing**
```bash
aud index
# Should process 30 .rs files
# Should report ~626 symbols
# Should complete in ~6 seconds
```

**Test 3: Database Validation**
```bash
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols WHERE path LIKE '%.rs';"
# Should return ~626

sqlite3 .pf/repo_index.db "SELECT DISTINCT type FROM symbols WHERE path LIKE '%.rs';"
# Should show: function, field, module, method, struct, enum, const, type
```

**Test 4: Full Pipeline**
```bash
aud full
# Should complete without errors
# Check .pf/readthis/ for Rust analysis output
```

**Test 5: Validation Script**
```bash
python tests/test_rust_extraction.py
# Should pass with statistics matching above
```

---

## v1.1 Architecture Investigation Checklist

**Before starting implementation, investigate**:

### Indexer Changes
- [ ] Where is IndexerOrchestrator? (may be renamed/moved)
- [ ] BaseExtractor interface changes?
- [ ] Extractor registry pattern changes?
- [ ] Database schema changes? (check `symbols` table)
- [ ] Batch processing pattern changes?

### Database Changes
- [ ] `symbols` table schema? (name, type, line, col still exist?)
- [ ] `refs` table schema? (for imports)
- [ ] New tables added?
- [ ] DatabaseManager API changes?

### Setup Flow Changes
- [ ] `venv_install.py` restructured?
- [ ] Setup command flow different?
- [ ] Error handling conventions?
- [ ] Logging patterns changed?

### Dependencies Changes
- [ ] `deps.py` signature changes?
- [ ] New dependency dict schema?
- [ ] Parser integration pattern changes?

---

## Quick Reference: File Sizes

```
theauditor/lsp/rust_analyzer_client.py       323 lines
theauditor/indexer/extractors/rust.py        192 lines
theauditor/toolboxes/rust.py                 227 lines
theauditor/toolboxes/base.py                 104 lines
tests/test_rust_extraction.py                139 lines
------------------------------------------------
Total new code:                              985 lines
```

**Plus modifications** to 5 existing files (~100 lines added)

**Total implementation**: ~1,100 lines of production code

---

## Commit Message Template (for v1.1)

```
feat(rust): add Rust language support with LSP-based semantic analysis

Implements comprehensive Rust support including:
- rust-analyzer LSP client for semantic symbol extraction
- RustToolbox for sandboxed rust-analyzer management
- Cargo.toml dependency parsing
- Persistent LSP sessions (5x performance improvement)

Architecture:
- theauditor/lsp/rust_analyzer_client.py (323 lines)
- theauditor/toolboxes/rust.py (227 lines)
- theauditor/toolboxes/base.py (104 lines, reusable utilities)
- theauditor/indexer/extractors/rust.py (192 lines)

Integration points:
- BaseExtractor: Added cleanup() interface for resource management
- IndexerOrchestrator: Calls cleanup() after file processing
- deps.py: Added _parse_cargo_toml() for dependency extraction
- venv_install.py: Auto-detects Rust projects, installs rust-analyzer

Performance:
- Persistent LSP: ~200ms per file (vs 1s with fresh process)
- hegel-cli validation: 626 symbols from 30 files in ~6 seconds

Testing:
- tests/test_rust_extraction.py validates extraction on hegel-cli
- Expected: 349 functions, 127 fields, 51 modules, 30 structs

Ported from feat/rust-support-discovery branch (17 commits)
Based on fresh implementation adapted to v1.1 architecture.
```

---

## Known Gotchas

### 1. tomllib Import (Python 3.11+)
```python
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python < 3.11
    except ImportError:
        logger.warning("Cannot parse Cargo.toml - tomllib not available")
```

### 2. Rust-analyzer Binary Permissions (Unix)
```python
if not is_windows:
    os.chmod(binary_path, 0o755)  # Must be executable
```

### 3. LSP Content-Length Encoding
```python
content_length = len(message_json.encode('utf-8'))  # MUST be UTF-8 bytes, not string length!
```

### 4. Temp Workspace Cleanup
```python
# Use try/finally to ensure cleanup even on error
try:
    # ... LSP operations ...
finally:
    if temp_workspace.exists():
        shutil.rmtree(temp_workspace)
```

### 5. Type Hints Compatibility
```python
# Python 3.9+: tuple[bool, str]
# Python 3.8: Tuple[bool, str] from typing

# Use lowercase if v1.1 requires Python 3.9+, check pyproject.toml
```

---

## Success Criteria

### Minimum Viable (Phase 1)
- [ ] rust-analyzer downloads and installs
- [ ] Cargo.toml parsed correctly
- [ ] .rs files indexed without errors
- [ ] Symbols appear in database

### Full Success (Phase 2)
- [ ] 626 symbols extracted from hegel-cli
- [ ] Symbol types correctly mapped (function, struct, module, etc.)
- [ ] Import statements extracted
- [ ] Performance: <10 seconds for 30 files
- [ ] No LSP timeouts
- [ ] Cleanup happens correctly

### Production Ready (Phase 3)
- [ ] All tests passing
- [ ] Documentation in CLAUDE.md
- [ ] Error handling robust
- [ ] Logging appropriate
- [ ] Memory efficient (no leaks)

---

## Context Transfer Checklist

**Next session should have**:
- [ ] This HANDOFF.md
- [ ] Access to `feat/rust-support-discovery` branch (reference)
- [ ] Fresh checkout of `upstream/v1.1` branch
- [ ] hegel-cli project for testing (~6K LOC, 30 files)
- [ ] Understanding: This is Option 3 (fresh implementation, not cherry-pick)

**First actions**:
1. Checkout `upstream/v1.1` to new branch `feat/rust-support-v1.1`
2. Review v1.1 architecture (checklist above)
3. Copy new directories (Phase 1)
4. Adapt integrations to v1.1 patterns (Phase 2)
5. Test iteratively (Phase 3)

---

## Estimated Effort

**Phase 1** (Copy new code): 30 minutes
**Phase 2** (Integration): 2-3 hours (depends on v1.1 differences)
**Phase 3** (Testing/debugging): 1-2 hours

**Total**: 4-5 hours for clean, tested implementation on v1.1

---

## Reference Branch

**Branch**: `feat/rust-support-discovery` (based on `main`)
**Remote**: `origin` (https://github.com/selberhad/Auditor.git)
**Commits**: 17 commits (from baeb869 to 1f5988b)
**Status**: Complete, tested, all quality refactorings done

**Key commits to reference**:
- `35f3b61`: Rust extractor with LSP
- `f7c8d23`: LSP client wrapper
- `d1f3ccb`: RustToolbox integration
- `c2c3cfe`: Performance refactorings
- `d791fc1`: DRY eliminations
- `1f5988b`: Module type fix

---

**END OF HANDOFF**

Next session: Implement on v1.1 following this plan.
