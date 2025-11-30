# graph_atomic.md - Graph Layer Pre-Implementation Plan

**Document Version:** 2.0-VERIFIED
**Status:** PRE-IMPLEMENTATION (Audited)
**Last Updated:** 2025-12-01
**Prepared By:** AI Lead Coder (Opus)
**Audit Status:** Prime Directive Applied - Claims Verified Against Codebase

---

## Architecture Clarification

> **CRITICAL CORRECTION:** Previous versions of this document incorrectly claimed `resolved_imports` was a "missing database table." This is FALSE.

### How Import Resolution Actually Works

`resolved_imports` is a **runtime dictionary** in the extraction pipeline, NOT a database table:

| Layer | What Happens | File | Line |
|-------|--------------|------|------|
| **Python Extractor** | Produces `resolved_imports: {}` dict | `python_impl.py` | 52 |
| **JS Extractor** | Produces `resolved_imports: {}` dict | `javascript.py` | 25 |
| **TS Extractor** | Outputs `resolved_imports` in result | `main.ts` | 775 |
| **Storage Handler** | Reads dict via `_current_extracted.get("resolved_imports", {})` | `core_storage.py` | 63 |
| **Database** | Resolved value stored in existing `refs` table | `core_storage.py` | 66 |

**The infrastructure EXISTS and WORKS.** The resolution happens at storage time via `add_ref(file_path, kind, resolved, line)`.

### What IS Broken

The issue is that `builder.py` does its OWN resolution (`resolve_import_path` at line 253) instead of querying the pre-resolved values from the `refs` table. This is a **usage** bug, not a **missing infrastructure** bug.

---

## Pre-Implementation Verification Results

### FALSE Claims (Removed from Plan)

| Original Claim | Verdict | Evidence |
|----------------|---------|----------|
| SCHEMA-1: Missing `resolved_imports` TABLE | FALSE | Not a table - runtime dict stored in `refs` |
| SCHEMA-2: Missing `flush_order` entry | FALSE | Not needed - resolved at storage time |
| SCHEMA-3: Missing database mixin method | FALSE | Not needed - uses existing `add_ref()` |
| SCHEMA-4: Missing storage handler | FALSE | EXISTS at `core_storage.py:63` |
| SCHEMA-5: Node.js database crashes | FALSE | No evidence found |
| SCHEMA-6: Infrastructure data dropped | FALSE | Properly handled via `refs` table |
| 2.13/G2: DFG Parsing Fragility | ALREADY FIXED | `dfg_builder.py:710-761` has "GRAPH FIX G1" |
| G6: Split-Brain Resolution | PARTIALLY FIXED | `interceptors.py:366-431` has "GRAPH FIX G2" |

### CONFIRMED Bugs (Remain in Plan)

| Issue | Severity | Evidence |
|-------|----------|----------|
| 2.1/G1: Infinite Cycle Detection | Critical | `analyzer.py:33-40` - no `_reverse` filtering |
| 2.7: Ghost Node IDs | Medium | `node_express.py:272` - lacks file prefix |
| 2.8: SQLite 999 Limit | High | `python_orm.py:361-368` - no chunking |
| 2.10/G3: Cache Mutability | Medium | `db_cache.py:52-84` - mutable dicts in tuple |
| 2.9/G7: Django M x V Explosion | Medium | `interceptors.py:323-364` - nested loops |
| Transaction Nesting | High | `store.py:58` - explicit `BEGIN TRANSACTION` |
| Controller Resolution (`in` operator) | Medium | `interceptors.py:413`, `node_express.py:233` |
| builder.py Re-Resolution | Medium | `builder.py:253` - ignores `refs` table |

---

## Confirmed Issues Detail

### Issue 1: Infinite Cycle Detection (CRITICAL)

**Files:** `builder.py`, `analyzer.py`
**Status:** CONFIRMED

**Problem:**
- `builder.py:43-86` creates bidirectional edges via `create_bidirectional_graph_edges()`
- For every import `A -> B`, it creates reverse edge `B -> A` (type: `import_reverse`)
- `analyzer.py:33-40` `detect_cycles` does NOT filter `_reverse` edges
- Result: Every import is reported as a 2-node cycle

**Evidence:**
```python
# analyzer.py:33-40
def detect_cycles(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
    adj = defaultdict(list)
    for edge in graph.get("edges", []):
        adj[edge["source"]].append(edge["target"])  # NO filtering
```

**Fix:**
```python
for edge in graph.get("edges", []):
    if not edge["type"].endswith("_reverse"):  # ADD THIS
        adj[edge["source"]].append(edge["target"])
```

---

### Issue 2: Transaction Nesting Crash (HIGH)

**File:** `store.py`
**Status:** CONFIRMED

**Problem:**
- `store.py:54-58` opens connection then explicitly calls `BEGIN TRANSACTION`
- Python's sqlite3 manages transactions automatically
- Nesting causes `sqlite3.OperationalError`

**Evidence:**
```python
# store.py:54-58
conn = sqlite3.connect(self.db_path)
cursor = conn.cursor()
try:
    cursor.execute("BEGIN TRANSACTION")  # CONFLICT
```

**Fix:**
Remove explicit `BEGIN TRANSACTION`. Use `conn.commit()` at end.

---

### Issue 3: SQLite 999 Variable Limit (HIGH)

**File:** `python_orm.py`
**Status:** CONFIRMED

**Problem:**
- `python_orm.py:361-368` creates `WHERE target_var IN (...)` with unbounded patterns
- SQLite limit: 999 variables per query
- Large codebases crash with `OperationalError: too many SQL variables`

**Evidence:**
```python
# python_orm.py:361-368
placeholders = ",".join("?" * len(model_patterns))  # Can exceed 999
cursor.execute(f"... WHERE target_var IN ({placeholders})", list(model_patterns))
```

**Fix:**
```python
chunk_size = 900
for i in range(0, len(patterns_list), chunk_size):
    chunk = patterns_list[i:i + chunk_size]
    placeholders = ",".join("?" * len(chunk))
    cursor.execute(f"... IN ({placeholders})", chunk)
```

---

### Issue 4: Ghost Node IDs (MEDIUM)

**File:** `node_express.py`
**Status:** CONFIRMED

**Problem:**
- `node_express.py:272` creates ghost nodes with ID `UNRESOLVED::{object_name}.{method_name}`
- No file path in ID
- `store.py` cannot clean them up (`DELETE ... WHERE file=?`)
- Ghost nodes persist forever

**Evidence:**
```python
# node_express.py:272
ghost_id = f"UNRESOLVED::{object_name}.{method_name}"  # Missing file
```

**Fix:**
```python
ghost_id = f"{route_file}::UNRESOLVED::{object_name}.{method_name}"
```

---

### Issue 5: Cache Mutability (MEDIUM)

**File:** `db_cache.py`
**Status:** CONFIRMED

**Problem:**
- `db_cache.py:52-84` uses `@lru_cache` returning `tuple[dict[str, Any], ...]`
- Tuple is immutable but dicts inside are mutable
- Consumer modifications persist in cache
- Non-deterministic bugs across runs

**Evidence:**
```python
# db_cache.py:52-84
@lru_cache(maxsize=IMPORTS_CACHE_SIZE)
def get_imports(self, file_path: str) -> tuple[dict[str, Any], ...]:
    results = tuple({...} for row in cursor.fetchall())
    return results  # Mutable dicts inside
```

**Fix:**
```python
from copy import deepcopy
return tuple(deepcopy(d) for d in results)
# OR use frozen dataclasses/namedtuples
```

---

### Issue 6: Django M x V Edge Explosion (MEDIUM)

**File:** `interceptors.py`
**Status:** CONFIRMED

**Problem:**
- `interceptors.py:323-364` connects every middleware to every view
- 20 middlewares x 500 views = 10,000 edges
- Creates unusable "hairball" visualization

**Evidence:**
```python
# interceptors.py:323-364
for mw in middlewares:
    ...
    for view in views:  # NESTED LOOP = M x V
        new_edges = create_bidirectional_edges(...)
```

**Fix:** Hub Node Pattern
```python
router_node_id = "Django::Router::Dispatch"
for mw in middlewares:
    create_edge(mw, router_node_id)  # M edges
for view in views:
    create_edge(router_node_id, view)  # V edges
# Total: M + V instead of M x V
```

---

### Issue 7: Controller Resolution Uses `in` Operator (MEDIUM)

**Files:** `interceptors.py`, `node_express.py`
**Status:** CONFIRMED

**Problem:**
- `interceptors.py:413` and `node_express.py:233` check `if import_package in sym["path"]`
- `import_package` is relative: `../controllers/User`
- DB path is normalized: `src/controllers/User.ts`
- `"../controllers/User" in "src/controllers/User.ts"` is **False**

**Evidence:**
```python
# interceptors.py:413
if import_package in sym["path"]:  # FAILS for relative paths
```

**Fix:**
```python
import_base = import_package.split("/")[-1].replace(".ts", "").lower()
sym_base = sym["path"].split("/")[-1].replace(".ts", "").lower()
if import_base == sym_base:
    # Match found
```

---

### Issue 8: builder.py Ignores Pre-Resolved Imports (MEDIUM)

**File:** `builder.py`
**Status:** CONFIRMED

**Problem:**
- `builder.py:253` `resolve_import_path` re-resolves imports using string manipulation
- Ignores the high-fidelity resolution already stored in `refs` table
- Fails on path aliases (`@/utils`), monorepos, tsconfig paths

**Evidence:**
```python
# builder.py:253
def resolve_import_path(self, import_str: str, source_file: Path, lang: str) -> str:
    # Guesses paths using string manipulation
    # IGNORES refs table with pre-resolved paths
```

**Fix:**
Query `refs` table first:
```python
def get_resolved_imports(self, file_path: str) -> dict[str, str]:
    """Get import -> resolved_path mapping from refs table."""
    cursor.execute("""
        SELECT value FROM refs
        WHERE src = ? AND kind IN ('import', 'require')
    """, (file_path,))
    # value column contains pre-resolved paths from core_storage.py:63
```

---

## Already Fixed Issues (Skip)

### DFG Parsing Fragility (2.13/G2) - ALREADY FIXED

**File:** `dfg_builder.py:710-761`
**Status:** Fixed with "GRAPH FIX G1"

The `_parse_argument_variable` function now properly handles keyword prefixes:
```python
# dfg_builder.py:731-740
keyword_prefixes = ("await ", "new ", "typeof ", "void ", "delete ", "yield ", "yield* ")
for prefix in keyword_prefixes:
    if expr.startswith(prefix):
        remainder = expr[len(prefix):].strip()
        if remainder:
            result = self._parse_argument_variable(remainder)  # RECURSIVE
```

### Split-Brain Resolution (G6) - PARTIALLY FIXED

**File:** `interceptors.py:366-431`
**Status:** Fixed with "GRAPH FIX G2"

The `_resolve_controller_info` method now uses import-based resolution instead of fuzzy LIKE matching.

---

## Implementation Plan (Revised)

### Phase 1: Stop the Crashes

| # | Issue | File | Change |
|---|-------|------|--------|
| 1 | Transaction Nesting | `store.py` | Remove explicit `BEGIN TRANSACTION` |
| 2 | Infinite Cycle | `analyzer.py` | Filter `_reverse` edges in `detect_cycles` |
| 3 | SQLite 999 Limit | `python_orm.py` | Chunk queries to 900 items |
| 4 | Ghost Node IDs | `node_express.py` | Add file prefix to ghost IDs |

### Phase 2: Data Quality

| # | Issue | File | Change |
|---|-------|------|--------|
| 5 | Cache Mutability | `db_cache.py` | deepcopy on return OR frozen dataclasses |
| 6 | Use Pre-Resolved Imports | `builder.py` | Query `refs` table instead of re-resolving |
| 7 | Controller Resolution | `interceptors.py`, `node_express.py` | Normalize paths before comparison |

### Phase 3: Optimization

| # | Issue | File | Change |
|---|-------|------|--------|
| 8 | Django Hub Pattern | `interceptors.py` | Replace M x V with M + V edges |
| 9 | Path Normalization | `builder.py`, `store.py` | Consistent forward slashes |

### Phase 4: Skip (Already Done)

- ~~DFG Parsing~~ - GRAPH FIX G1 applied
- ~~Split-Brain Resolution~~ - GRAPH FIX G2 applied

---

## Files to Modify (Verified)

| File | Changes |
|------|---------|
| `theauditor/graph/store.py` | Remove `BEGIN TRANSACTION` |
| `theauditor/graph/analyzer.py` | Filter `_reverse` edges |
| `theauditor/graph/strategies/python_orm.py` | Chunk SQL queries |
| `theauditor/graph/strategies/node_express.py` | Add file prefix to ghost nodes |
| `theauditor/graph/db_cache.py` | deepcopy cached results |
| `theauditor/graph/builder.py` | Query `refs` table for resolved imports |
| `theauditor/graph/strategies/interceptors.py` | Django hub pattern, path normalization |

---

## Verification Checklist

### Pre-Implementation (All VERIFIED)

- [x] `resolved_imports` handled via runtime dict -> `refs` table (NOT a separate table)
- [x] Storage handler EXISTS at `core_storage.py:63`
- [x] Graph database path is `.pf/graphs.db`
- [x] Repo index database path is `.pf/repo_index.db`
- [x] DFG parsing already fixed (GRAPH FIX G1)
- [x] Split-brain resolution partially fixed (GRAPH FIX G2)

### Post-Implementation

- [ ] `detect_cycles` returns 0 false positives for simple imports
- [ ] `aud full` completes without transaction errors
- [ ] Large codebases don't crash on ORM strategy
- [ ] Ghost nodes cleaned up on re-index
- [ ] Multiple runs produce identical graphs
- [ ] Import resolution uses pre-resolved paths from `refs` table
- [ ] Django middleware visualization is readable

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing queries | Medium | High | Run `aud full` before/after on test repo |
| Performance regression | Low | Medium | Profile after Phase 2 |
| Database needs rebuild | High | Low | Delete `.pf/*.db` and reindex |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-01 | Initial merge of 3 investigations |
| 2.0 | 2025-12-01 | **Prime Directive audit applied.** Removed 7 false claims about missing infrastructure. Confirmed 8 actual bugs. Marked 2 issues as already fixed. |

---

**Status:** Ready for implementation
**Confidence Level:** HIGH (verified against codebase)
**Next Step:** Architect approval to proceed with Phase 1
