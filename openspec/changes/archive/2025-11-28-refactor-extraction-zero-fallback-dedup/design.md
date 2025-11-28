# Design: ZERO FALLBACK Extraction Pipeline

## Context

TheAuditor's extraction pipeline follows a 3-layer architecture (per `project.md`):

```
INDEXER (file_path provider) -> EXTRACTOR (file_info dict) -> IMPLEMENTATION (AST tree only)
        |                              |                              |
        v                              v                              v
  core_storage.py              extractors/*.py              ast_extractors/*_impl.py
```

### Current Problem

Each layer independently "protects" against upstream bugs:
- Storage deduplicates "in case" extractors produce duplicates
- Database deduplicates "in case" storage sends duplicates
- Validators exist but aren't called "in case" we need them later

This creates **silent data loss** - the worst failure mode for a SAST tool.

### Stakeholders
- **AI Auditors**: Consume `repo_index.db` for analysis - need complete, accurate data
- **Taint Engine**: Builds flow graphs from assignments/calls - missing data = false negatives
- **FCE (Factual Correlation Engine)**: Cross-references findings - orphaned data = missed correlations

## Goals / Non-Goals

### Goals
1. **Hard fail on extraction bugs**: Duplicates crash immediately with actionable error messages
2. **Type safety at boundaries**: Invalid types caught before database insert
3. **Referential integrity**: Foreign keys enforced to prevent orphaned records
4. **Zero dead code**: Remove unused validators

### Non-Goals
- Performance optimization (assertions add negligible overhead)
- Schema changes (no migrations in this refactor)
- New extraction capabilities (bug fixes only)
- Backward compatibility with corrupt databases (rebuild required)

## Decisions

### Decision 1: Replace Deduplication with Hard Fail

**What**: Remove `seen = set()` + `if key in seen: continue` pattern from `core_storage.py`

**Why**:
- Deduplication masks extractor bugs that should be fixed at source
- Silent data loss is worse than a crash for auditing tools
- CLAUDE.md ZERO FALLBACK POLICY mandates single code path

**Pattern** (apply to all `_store_*` methods):
```python
# BEFORE (fallback):
seen = set()
deduplicated = []
for item in items:
    key = (file_path, item['line'], item['name'])
    if key not in seen:
        seen.add(key)
        deduplicated.append(item)
    # else: silently dropped

# AFTER (hard fail):
seen = set()
for item in items:
    key = (file_path, item['line'], item['name'])
    if key in seen:
        raise ValueError(
            f"EXTRACTOR BUG: Duplicate detected.\n"
            f"  File: {file_path}\n"
            f"  Identity: {key}\n"
            f"  Fix extractor to visit nodes only once."
        )
    seen.add(key)
```

**Locations**:
| Method | File | Lines | Identity Key |
|--------|------|-------|--------------|
| `_store_assignments` | `core_storage.py` | 351-364 | `(file, line, target_var)` |
| `_store_returns` | `core_storage.py` | 456-469 | `(file, line, function_name)` |
| `_store_env_var_usage` | `core_storage.py` | 615-628 | `(file, line, var_name, access_type)` |
| `add_file` | `core_database.py` | 15-24 | `(path,)` |
| `add_nginx_config` | `infrastructure_database.py` | 119-122 | `(file, block_type, block_context)` |

### Decision 2: Explicit Type Assertions (Not Decorators)

**What**: Add `isinstance` checks directly in `_store_*` methods

**Why**:
- `generated_validators.py` exists but is never called (dead code)
- Decorators are harder to debug - stack traces point to decorator, not logic
- Explicit checks are faster (no decorator overhead)
- Explicit checks are readable - validation visible inline

**Pattern**:
```python
def _store_symbols(self, file_path: str, symbols: list, jsx_pass: bool):
    for idx, symbol in enumerate(symbols):
        # Type assertions at storage boundary
        if not isinstance(symbol, dict):
            raise TypeError(
                f"EXTRACTOR BUG: Symbol must be dict, got {type(symbol).__name__}.\n"
                f"  File: {file_path}, Index: {idx}"
            )
        if not isinstance(symbol.get('name'), str) or not symbol['name']:
            raise TypeError(
                f"EXTRACTOR BUG: Symbol.name must be non-empty str.\n"
                f"  File: {file_path}, Got: {repr(symbol.get('name'))}"
            )
        # ... more checks ...
        # Then existing storage logic
```

**Required Checks Per Entity**:
| Entity | Required Fields | Type |
|--------|-----------------|------|
| symbol | name, type, line, col | str, str, int >= 1, int >= 0 |
| assignment | line, target_var, source_expr, in_function | int, str, str, str |
| function_call | line, caller_function, callee_function | int, str, str |
| function_return | line, function_name, return_expr | int, str, str |

**Alternative Considered**: Use `generated_validators.py` decorators
**Rejected Because**: Dead code for 6+ months, decorator overhead, harder debugging

### Decision 3: Foreign Key Enforcement with Ordered Flush

**What**: Enable `PRAGMA foreign_keys = ON` and enforce parent-before-child flush order

**Why**:
- SQLite FKs are OFF by default for legacy compatibility
- Without FKs, orphaned records (assignments without files, calls without symbols) silently persist
- Orphaned data causes `KeyError` in downstream analysis

**Flush Order** (must be enforced in `base_database.py:flush_batch`):
```python
FLUSH_ORDER = [
    # Parents first (no FK dependencies)
    'files',
    'config_files',

    # Children of files
    'refs',
    'symbols',
    'class_properties',

    # Children of symbols
    'assignments',
    'function_call_args',
    'function_returns',

    # Junction tables (children of above)
    'assignment_sources',
    'function_return_sources',

    # ... remaining tables in dependency order
]
```

**Note**: Current `flush_order` list in `base_database.py:266-440` already exists but may not be strictly enforced. Verification required.

### Decision 4: Reuse Existing visited_nodes Pattern for Extractor Fixes (POLYGLOT)

**What**: When Phase 1 crashes expose duplicate visits, fix extractors using language-appropriate patterns

**Why**:
- `typescript_impl.py:535-545` already has `visited_nodes = set()` pattern
- `module_framework.js:149-163` has equivalent `visitedNodes` Set
- Proven pattern, consistent with existing codebase
- **CRITICAL**: Different languages have different AST conventions - must use correct pattern per language

**POLYGLOT PATTERN REFERENCE**:

| Language | Line Access | Column Access | Type Access |
|----------|-------------|---------------|-------------|
| TypeScript/JS | `node.get("line")` | `node.get("column", 0)` | `node.get("kind")` |
| Python | `node.lineno` | `node.col_offset` | `type(node).__name__` |
| Rust/HCL | `node.start_point[0]` | `node.start_point[1]` | `node.type` |

---

**TypeScript/JavaScript Reference** (`typescript_impl.py:535-545`):
```python
# Track visited nodes by (line, column, kind) to avoid processing same node multiple times
visited_nodes = set()

def traverse(node, depth=0):
    node_id = (node.get("line"), node.get("column", 0), node.get("kind"))
    if node_id in visited_nodes:
        return  # Already processed
    visited_nodes.add(node_id)
    # ... process node ...
```

**JavaScript Equivalent** (`module_framework.js:149-163`):
```javascript
const visitedNodes = new Set();

function processNode(node) {
    const nodeId = `${node.loc?.start?.line}:${node.loc?.start?.column}:${node.type}`;
    if (visitedNodes.has(nodeId)) {
        return;  // Already processed
    }
    visitedNodes.add(nodeId);
    // ... process node ...
}
```

---

**Python AST Reference** (NEW - apply to `ast_extractors/python/*.py`):
```python
import ast

# Track visited nodes - Python AST uses different attributes
visited_nodes = set()

for node in ast.walk(tree):
    # Python AST convention: lineno, col_offset, type name
    node_id = (getattr(node, 'lineno', 0), getattr(node, 'col_offset', 0), type(node).__name__)
    if node_id in visited_nodes:
        continue  # Already processed
    visited_nodes.add(node_id)
    # ... process node ...
```

---

**Rust/HCL (tree-sitter) Reference** (apply to `rust_impl.py`, `hcl_impl.py`):
```python
# Tree-sitter nodes use start_point tuple and type property
visited_nodes = set()

def traverse(node):
    # Tree-sitter convention: (row, column) tuple and type string
    node_id = (node.start_point[0], node.start_point[1], node.type)
    if node_id in visited_nodes:
        return
    visited_nodes.add(node_id)
    # ... process node ...
    for child in node.children:
        traverse(child)
```

## Risks / Trade-offs

### Risk 1: Phase 1 Crashes Immediately and Extensively
- **Likelihood**: HIGH
- **Impact**: Cannot run `aud full` until extractors fixed
- **Mitigation**: Fix each extractor bug as it's discovered (per Architect directive)
- **Acceptance**: This is the intended behavior - we're exposing hidden bugs

### Risk 2: FK Violations on First Run
- **Likelihood**: MEDIUM
- **Impact**: Database commit fails
- **Mitigation**:
  1. Verify flush order before enabling FKs
  2. Phase 3 runs only after Phase 1+2 pass
- **Rollback**: Remove FK pragma (single line)

### Risk 3: Performance Degradation
- **Likelihood**: LOW
- **Impact**: Slower indexing
- **Mitigation**: Assertions are O(1) per item - negligible
- **Measurement**: Benchmark `aud full` before/after

## Migration Plan

### Execution Order
1. **One branch, sequential commits** (per Architect directive)
2. Fix extractor bugs **immediately** as crashes occur (option A)
3. Do NOT proceed to next phase until current phase passes all tests

### Phase 1 Execution
1. Edit `core_storage.py` to replace dedup with hard fail (3 locations)
2. Edit `core_database.py` to remove `add_file` dedup
3. Run `pytest tests/` - expect failures
4. For each failure:
   - Identify which extractor produces duplicates
   - Apply `visited_nodes` pattern to that extractor
   - Re-run tests
5. Phase 1 complete when all tests pass

### Phase 2 Execution
1. Add type assertions to all `_store_*` methods
2. Delete `generated_validators.py`
3. Run `pytest tests/` - expect failures if extractors return wrong types
4. Fix extractors as needed
5. Phase 2 complete when all tests pass

### Phase 3 Execution
1. Verify flush order in `base_database.py`
2. Add `PRAGMA foreign_keys = ON`
3. Enhance error messages for IntegrityError
4. Run `pytest tests/`
5. Run `aud full` on test fixtures
6. Phase 3 complete when full pipeline passes

### Rollback Procedure
```bash
# Full rollback (all phases)
git checkout HEAD -- theauditor/indexer/storage/core_storage.py
git checkout HEAD -- theauditor/indexer/database/core_database.py
git checkout HEAD -- theauditor/indexer/database/base_database.py
git checkout HEAD -- theauditor/indexer/schemas/generated_validators.py

# Phase-specific rollback
# Phase 1: Revert storage + database dedup changes
# Phase 2: Revert assertion additions, restore validators
# Phase 3: Remove FK pragma line only
```

## Open Questions

1. **Q**: Should we add metrics for "crashes prevented by hard fail"?
   **A**: Out of scope - this is enforcement, not observability

2. **Q**: What about existing corrupt `repo_index.db` files?
   **A**: Rebuild with `aud full` after upgrade - no migration path for corrupt data

3. **Q**: Should type assertions use `typing.TypedDict` for compile-time checks?
   **A**: Future enhancement - runtime `isinstance` sufficient for this refactor
