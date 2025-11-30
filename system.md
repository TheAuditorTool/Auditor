# System/Orchestration Layer Pre-Implementation Plan

**Document Version:** 1.0
**Layer:** Phase 0 - System Stability (The "5th Invisible Layer")
**Status:** PRE-IMPLEMENTATION
**Priority:** CRITICAL - Must be fixed before Layers 1-4

---

## Executive Summary

The System/Orchestration layer is the **5th "invisible" layer** that sits above the 4 logical layers (Extraction, Storage, Graph, Taint). You cannot fix the logic (Layers 1-4) if the Orchestrator (Layer 0) blows up the RAM before you even finish indexing.

**Current Impact:** 6GB OOM crashes on large repositories kill the process before analysis completes.

---

## Part 1: The Sum of System Bugs

### 1.1 The "Crash" Cascade

When running on a large codebase, this is what happens:

1. **RAM Explosion:** The Orchestrator loads all ASTs and Import Tables into RAM at startup
2. **OOM Kill:** On large repos (50k+ files), Python dictionaries consume 10GB+ RAM
3. **Process Death:** Container/process killed before analysis even starts
4. **Zero Results:** No findings because the pipeline never completed

### 1.2 Root Causes Identified

| Component | File | Bug | Impact |
|-----------|------|-----|--------|
| **RAM Cache** | `orchestrator.py` | Loads `js_ts_cache` for entire batch | 6GB+ memory spike |
| **Import Cache** | `db_cache.py` | Loads ALL imports into Python dict at startup | OOM on 500k+ rows |
| **Graph Preload** | `flow_resolver.py` | Preloads ENTIRE graph into memory | 10GB+ for 5M edges |
| **Delete-on-Write** | `store.py` | `DELETE FROM nodes` wipes previous batches | Data loss, full rebuilds |
| **All-or-Nothing** | `javascript.py` | Discards entire file on single syntax error | 100% data loss per file |
| **Transaction Safety** | `store.py` | No atomic delete+insert | Partial graph corruption |

---

## Part 2: Verification Phase Report (Pre-Implementation)

### 2.1 Hypotheses & Verification Required

**Hypothesis 1:** `orchestrator.py` loads the entire JS/TS AST cache into memory before processing.

- **Verification Method:** Read `orchestrator.py`, search for `js_ts_cache` or similar batch loading logic
- **Expected Finding:** Dictionary or list holding all parsed ASTs simultaneously

**Hypothesis 2:** `db_cache.py` eagerly loads all imports into `self.imports_by_file` dict.

- **Verification Method:** Read `db_cache.py`, locate `_load_cache()` or equivalent
- **Expected Finding:** `cursor.execute("SELECT ... FROM refs")` followed by dict population

**Hypothesis 3:** `flow_resolver.py` preloads the entire edge table into an adjacency list.

- **Verification Method:** Read `flow_resolver.py`, find `_preload_graph()` method
- **Expected Finding:** `cursor.fetchall()` loading all edges into Python dict

**Hypothesis 4:** `store.py` uses blanket DELETE before INSERT.

- **Verification Method:** Read `store.py`, find `_save_graph_bulk()` method
- **Expected Finding:** `DELETE FROM nodes WHERE graph_type = ?` without file scoping

**Hypothesis 5:** `javascript.py` uses `continue` on `success: false`, dropping entire file.

- **Verification Method:** Read `javascript.py`, find extraction loop
- **Expected Finding:** `if tree.get("success") is False: continue`

---

## Part 3: Deep Root Cause Analysis

### 3.1 Surface Symptom

The application crashes with OOM (Out of Memory) or hangs indefinitely when processing large repositories (50k+ files).

### 3.2 Problem Chain Analysis

1. **Orchestrator Startup:**
   - `orchestrator.py` begins batch processing
   - For JS/TS files, it caches parsed ASTs in memory
   - Memory grows linearly with batch size

2. **Import Table Loading:**
   - `db_cache.py` calls `_load_cache()`
   - Executes `SELECT * FROM refs WHERE kind IN (...)`
   - Stores 500k+ rows in Python dict (significant memory overhead)

3. **Graph Construction:**
   - `flow_resolver.py` calls `_preload_graph()`
   - Loads 5M+ edges into `self.adjacency_list` dict
   - Each edge requires ~200 bytes in Python dict overhead

4. **Memory Exhaustion:**
   - Combined memory exceeds container/system limits
   - OOM killer terminates process
   - Analysis never completes

### 3.3 Actual Root Cause

**Design Flaw:** The system was architected as a "Batch Processor" that loads everything into RAM, rather than a "Streaming Processor" that operates on-demand.

### 3.4 Why This Happened (Historical Context)

- **Design Decision:** Eager loading was chosen for simplicity and to minimize database round-trips
- **Missing Safeguard:** No memory profiling or limits were implemented
- **Scale Assumption:** Original design assumed smaller codebases (~10k files)

---

## Part 4: Implementation Plan

### Phase 0.1: Kill the RAM Cache (CRITICAL)

**Objective:** Stop loading `js_ts_cache` for the entire batch.

**File:** `theauditor/orchestrator.py` (or equivalent)

**Current Pattern (Problematic):**
```python
# WRONG - Loads all ASTs into memory
self.js_ts_cache = {}
for file in batch:
    ast = parse_file(file)
    self.js_ts_cache[file] = ast  # Memory grows indefinitely

# Later processing uses cached ASTs
for file, ast in self.js_ts_cache.items():
    process(ast)
```

**Target Pattern (Fixed):**
```python
# CORRECT - Parse, process, discard immediately
for file in batch:
    ast = parse_file(file)
    process(ast)
    # AST is garbage collected after this iteration
    del ast  # Explicit cleanup (optional but clear)
```

**Implementation Steps:**
1. Locate the `js_ts_cache` dictionary initialization
2. Remove the caching logic - process each file inline
3. Ensure AST is discarded after extraction completes
4. Add explicit `del` or scope limiting to enable GC

---

### Phase 0.2: Lazy-Load Imports (HIGH)

**Objective:** Replace eager loading with on-demand SQL queries.

**File:** `theauditor/graph/db_cache.py`

**Current Pattern (Problematic):**
```python
class DBCache:
    def __init__(self, db_path):
        self.imports_by_file = {}
        self._load_cache()  # DANGER: Loads EVERYTHING

    def _load_cache(self):
        cursor.execute("SELECT * FROM refs WHERE kind IN (...)")
        for row in cursor.fetchall():  # Could be 500k+ rows
            self.imports_by_file[row['file']] = ...
```

**Target Pattern (Fixed):**
```python
from functools import lru_cache

class DBCache:
    def __init__(self, db_path):
        self.db_path = db_path
        # NO eager loading

    @lru_cache(maxsize=1000)  # Keep 1000 most recent files in memory
    def get_imports(self, file_path: str) -> list:
        """Query imports on-demand for a specific file."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM refs WHERE file = ? AND kind IN (...)",
                (file_path,)
            )
            return cursor.fetchall()
```

**Implementation Steps:**
1. Delete `_load_cache()` method entirely
2. Delete `self.imports_by_file = {}` initialization
3. Add `@lru_cache` decorated method for on-demand queries
4. Update all callers to use `get_imports(file)` instead of dict access

---

### Phase 0.3: Lazy-Load Graph (HIGH)

**Objective:** Stop preloading entire graph into memory.

**File:** `theauditor/taint/flow_resolver.py`

**Current Pattern (Problematic):**
```python
def _preload_graph(self):
    cursor.execute("SELECT source, target, type FROM edges ...")
    for source, target, edge_type in cursor.fetchall():  # 5M+ rows
        self.adjacency_list[source].append(target)
```

**Target Pattern (Fixed):**
```python
@lru_cache(maxsize=10000)
def _get_successors(self, node_id: str) -> list[str]:
    """Query successors on-demand for a specific node."""
    cursor = self.graph_conn.execute(
        "SELECT target FROM edges WHERE source = ? AND graph_type = ?",
        (node_id, self.graph_type)
    )
    return [row[0] for row in cursor.fetchall()]

@lru_cache(maxsize=10000)
def _get_predecessors(self, node_id: str) -> list[str]:
    """Query predecessors on-demand for backward traversal."""
    cursor = self.graph_conn.execute(
        "SELECT source FROM edges WHERE target = ? AND graph_type = ?",
        (node_id, self.graph_type)
    )
    return [row[0] for row in cursor.fetchall()]
```

**Implementation Steps:**
1. Delete `_preload_graph()` method entirely
2. Delete `self.adjacency_list` initialization
3. Add `@lru_cache` decorated methods for on-demand neighbor queries
4. Ensure proper database indexing on `source` and `target` columns

---

### Phase 0.4: Incremental Graph Saves (MEDIUM)

**Objective:** Stop wiping the entire graph on every save.

**File:** `theauditor/graph/store.py`

**Current Pattern (Problematic):**
```python
def _save_graph_bulk(self, graph: dict, graph_type: str, ...):
    with sqlite3.connect(self.db_path) as conn:
        # DANGER: Deletes ALL nodes of this type
        conn.execute("DELETE FROM nodes WHERE graph_type = ?", (graph_type,))
        conn.execute("DELETE FROM edges WHERE graph_type = ?", (graph_type,))
        # Then inserts only the new batch...
```

**Target Pattern (Fixed):**
```python
def _save_graph_bulk(self, graph: dict, graph_type: str, file_path: str = None):
    with sqlite3.connect(self.db_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            if file_path:
                # Incremental: Only delete nodes for THIS file
                cursor.execute(
                    "DELETE FROM nodes WHERE graph_type = ? AND file = ?",
                    (graph_type, file_path)
                )
                cursor.execute(
                    "DELETE FROM edges WHERE graph_type = ? AND source_file = ?",
                    (graph_type, file_path)
                )
            else:
                # Full rebuild (explicit flag required)
                cursor.execute("DELETE FROM nodes WHERE graph_type = ?", (graph_type,))
                cursor.execute("DELETE FROM edges WHERE graph_type = ?", (graph_type,))

            # Insert new data
            cursor.executemany("INSERT INTO nodes ...", nodes_data)
            cursor.executemany("INSERT INTO edges ...", edges_data)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

**Implementation Steps:**
1. Add `file_path` parameter to `_save_graph_bulk()`
2. Scope DELETE to specific file when provided
3. Wrap in explicit transaction with rollback on error
4. Update callers to pass file path for incremental updates

---

### Phase 0.5: Transaction Safety (MEDIUM)

**Objective:** Ensure atomic delete+insert operations.

**File:** `theauditor/graph/store.py`

**Current Pattern (Problematic):**
```python
with sqlite3.connect(self.db_path) as conn:
    conn.execute("DELETE FROM nodes ...")  # Success
    conn.executemany("INSERT INTO nodes ...", data)  # FAILS: disk full
    # Result: Empty database, all data lost
```

**Target Pattern (Fixed):**
```python
with sqlite3.connect(self.db_path) as conn:
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("DELETE FROM nodes ...")
        cursor.executemany("INSERT INTO nodes ...", data)
        conn.commit()  # Only commits if ALL succeed
    except Exception as e:
        conn.rollback()  # Restore previous state
        raise StorageError(f"Graph save failed: {e}")
```

**Implementation Steps:**
1. Wrap all multi-statement operations in explicit transactions
2. Add `BEGIN TRANSACTION` before destructive operations
3. Add `conn.commit()` only after all operations succeed
4. Add `conn.rollback()` in exception handler

---

### Phase 0.6: Partial Success Mode (MEDIUM)

**Objective:** Stop discarding entire files on single syntax errors.

**File:** `theauditor/indexer/extractors/javascript.py`

**Current Pattern (Problematic):**
```python
for file_info in batch:
    tree = parse_file(file_info)
    if isinstance(tree, dict) and tree.get("success") is False:
        print(f"Parse error: {file_info}", file=sys.stderr)
        continue  # DANGER: 100% data loss for this file
```

**Target Pattern (Fixed):**
```python
for file_info in batch:
    tree = parse_file(file_info)

    if isinstance(tree, dict) and tree.get("success") is False:
        logger.warning(f"Partial parse for {file_info}: {tree.get('error')}")

        # Check if partial data exists
        extracted = tree.get("extracted_data", {})
        if extracted:
            # Use whatever was successfully extracted
            process_partial(file_info, extracted, partial=True)
        else:
            # Fall back to regex extraction for basic imports/exports
            fallback_data = regex_extract_basics(file_info)
            if fallback_data:
                process_partial(file_info, fallback_data, partial=True)

        continue  # Don't process as if fully successful

    # Full success path
    process_full(file_info, tree)
```

**Implementation Steps:**
1. Check for `extracted_data` even when `success` is False
2. Implement `regex_extract_basics()` fallback for imports/exports
3. Add `partial` flag to tracking for debugging
4. Log warning instead of dropping file

---

## Part 5: Edge Case & Failure Mode Analysis

### 5.1 Edge Cases Considered

| Scenario | Handling |
|----------|----------|
| **Empty batch** | Skip processing, return early |
| **Single file failure** | Log and continue with other files |
| **Database locked** | Retry with exponential backoff |
| **Disk full during write** | Transaction rollback, clear error message |
| **Memory pressure** | LRU cache eviction handles automatically |

### 5.2 Performance & Scale Analysis

| Metric | Before | After (Expected) |
|--------|--------|------------------|
| Peak RAM (50k files) | 6GB+ (OOM) | <2GB |
| Peak RAM (500k refs) | 4GB+ | <500MB |
| Graph load time | 30s+ (eager) | <1s (lazy) |
| Incremental update | Full rebuild | Single file |

### 5.3 Failure Modes

| Mode | Detection | Recovery |
|------|-----------|----------|
| OOM | Process exit code | Should not occur after fixes |
| Transaction failure | Exception caught | Automatic rollback |
| Cache miss | LRU eviction | Re-query from DB |
| Corrupt partial data | Validation checks | Log and skip record |

---

## Part 6: Implementation Order & Dependencies

**Strict Order Required:** Fix upstream before downstream.

```
Phase 0.1 (RAM Cache)
    |
    v
Phase 0.2 (Import Cache) --> Phase 0.3 (Graph Cache)
    |                            |
    v                            v
Phase 0.4 (Incremental Saves) <--+
    |
    v
Phase 0.5 (Transaction Safety)
    |
    v
Phase 0.6 (Partial Success)
```

### Verification Commands

**After Phase 0.1-0.3 (Memory Fixes):**
```bash
# Monitor memory during large repo indexing
aud full --offline 2>&1 | tee /tmp/aud.log &
watch -n 1 'ps -o pid,rss,vsz,comm -p $(pgrep -f "aud full")'
# Expected: RSS stays under 2GB
```

**After Phase 0.4 (Incremental Saves):**
```bash
# Verify single-file update doesn't wipe graph
aud full --offline
sqlite3 .pf/graphs.db "SELECT count(*) FROM nodes"  # Note count
# Modify one file
aud full --offline --file src/single_file.ts
sqlite3 .pf/graphs.db "SELECT count(*) FROM nodes"  # Should be ~same
```

**After Phase 0.5 (Transactions):**
```bash
# Verify rollback on simulated failure
# (Requires test harness to inject disk-full error)
```

**After Phase 0.6 (Partial Success):**
```bash
# Create file with intentional syntax error
echo "function foo( { broken" > /tmp/test_partial.ts
aud full --offline --file /tmp/test_partial.ts 2>&1 | grep -i partial
# Should see "Partial parse" warning, not complete failure
```

---

## Part 7: Impact Assessment

### 7.1 Immediate Impact

- **6 files** directly modified across orchestrator, cache, and storage layers
- **Memory usage** reduced by 70-90% on large repositories
- **Incremental builds** enabled (single-file updates without full rebuild)

### 7.2 Downstream Impact

- **Layers 1-4** can now run to completion on large repos
- **Taint Analysis** receives complete graph data (not truncated by OOM)
- **CI/CD pipelines** can process enterprise-scale repositories

### 7.3 Reversion Plan

**Reversibility:** Fully Reversible

**Steps:**
```bash
git revert <commit_hash>  # Reverts all system layer changes
```

---

## Part 8: Confirmation Checklist

Before marking Phase 0 complete, verify:

- [ ] `orchestrator.py` no longer caches ASTs in batch dictionary
- [ ] `db_cache.py` uses `@lru_cache` instead of eager loading
- [ ] `flow_resolver.py` uses on-demand neighbor queries
- [ ] `store.py` supports incremental file-scoped saves
- [ ] `store.py` uses explicit transactions with rollback
- [ ] `javascript.py` implements partial success mode
- [ ] Memory stays under 2GB for 50k file repository
- [ ] Single-file update completes in <5 seconds

---

## Summary

**The 5th Layer Problem:** System/Orchestration crashes prevent Layers 1-4 from ever running.

**Root Cause:** Eager loading architecture designed for small repos, applied to enterprise scale.

**Solution:** Convert from "Batch Processor" to "Streaming Processor" with lazy loading and incremental updates.

**Implementation Order:** Phase 0.1 -> 0.2 -> 0.3 -> 0.4 -> 0.5 -> 0.6

**Expected Outcome:** 70-90% memory reduction, enabling analysis of enterprise-scale repositories.

---

## Related Documents (Out of Scope)

This document covers **Phase 0: System Stability** - ensuring the pipeline can run to completion without crashing.

### TAINT_HANDOFF.md (Separate Ticket)

Covers taint analysis **LOGIC** issues that assume Phase 0 is resolved:

| Issue | Nature | This Doc? |
|-------|--------|-----------|
| `vulnerability_type = "unknown"` | Taint classification logic | No |
| 99.6% hitting max_depth=20 | Taint traversal tuning | No |
| sink_line only 67.6% populated | Taint lookup queries | No |
| 0 sanitizer detections | Taint pattern matching | No |
| IFDS backward analysis not run | Taint mode configuration | No |

### Boundary Clarification

| Question | Document |
|----------|----------|
| "Can the process survive to produce ANY output?" | **system.md** (this doc) |
| "When it produces output, is that output CORRECT?" | **TAINT_HANDOFF.md** |

### Why `flow_resolver.py` Appears in Both

- **system.md**: References `_preload_graph()` memory issue (RAM explosion)
- **TAINT_HANDOFF.md**: References classification logic, sink lookups, max_depth

Same file, different concerns. System = memory. Taint = correctness.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-30 | AI Coder | Initial extraction from taint1/2/3.md + orch.md |
