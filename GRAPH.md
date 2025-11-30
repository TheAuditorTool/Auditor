# GRAPH Layer Pre-Implementation Plan

**Document Version:** 1.0
**Status:** PRE-IMPLEMENTATION PLAN
**Last Updated:** 2025-11-30
**Compliance:** SOP v4.20 Template C-4.20

---

## Executive Summary

The Graph Layer is the **foundation** upon which Taint Analysis operates. You cannot do Taint Analysis without a Graph Engine. Taint Analysis is simply **Graph Traversal** (DFS/BFS) over a specific set of edges.

**Current State:** The Graph Layer is acting as a "Hallucinator" - trying to compensate for data lost in the TypeScript extraction layer by guessing relationships rather than knowing them.

**Critical Finding:** 99.6% of flows hit max_depth because the graph is a "hairball of hallucinations" caused by fuzzy matching and bidirectional edge explosion.

---

## Scope Boundary

**IN SCOPE (This Ticket):**
- Graph Layer infrastructure: `store.py`, `builder.py`, `dfg_builder.py`, `db_cache.py`, `types.py`
- Graph strategies: `interceptors.py`, `node_express.py`, `node_orm.py`
- Path normalization, ID standardization, edge creation patterns

**OUT OF SCOPE (Tracked Separately):**
- Taint engine logic: `flow_resolver.py`, `ifds_analyzer.py`, `sanitizer_util.py`, `discovery.py`
- Vulnerability classification, sanitizer matching, sink_line lookup fixes

**Related Document:** Taint-specific issues are tracked in `TAINT_HANDOFF.md`

**Relationship:** Graph fixes are a **prerequisite** for taint fixes. A broken graph produces broken taint results. This ticket fixes the foundation; taint fixes become meaningful only after graph integrity is restored.

---

## Part 1: Verification Phase Report (Pre-Implementation)

### Hypotheses & Verification Status

| # | Hypothesis | Verification | Evidence |
|---|------------|--------------|----------|
| H1 | Graph Layer is ready for Taint Analysis | REJECTED | Graph is disconnected due to path mismatches |
| H2 | Bidirectional edges enable backward traversal | PARTIAL | Edges exist but cause infinite loops (99.6% max_depth hits) |
| H3 | store.py handles incremental updates | REJECTED | Uses DELETE FROM - wipes entire graph on save |
| H4 | dfg_builder.py parses arguments correctly | REJECTED | Uses naive `split(" ")[0]` causing data loss |
| H5 | Node IDs are consistent across builders | REJECTED | builder.py vs dfg_builder.py use different ID formats |
| H6 | db_cache.py is memory-efficient | REJECTED | Loads EVERYTHING into RAM at startup |

### Critical Discrepancies Found

1. **Path Schizophrenia**: Python Layer uses relative paths, Node.js Layer uses absolute paths
2. **ID Format Divergence**: Call graph uses `{module_path}::{function_name}`, DFG uses `{file}::{scope}::{variable}`
3. **Edge Direction Mismatch**: IFDS expects `_reverse` edges but Call Graph builder doesn't create them
4. **Virtual Path Ghost Files**: Vue.js `/virtual_vue/` paths have no mapping back to real files

---

## Part 2: Deep Root Cause Analysis

### Surface Symptom
- Empty graphs, 0 edges, unconnected nodes
- 99.6% of taint flows hit max_depth (20)
- 100% "Unknown" vulnerability classification
- 0% Sanitized flows

### Problem Chain Analysis

```
1. main.ts extracts data with ABSOLUTE paths (/Users/dev/app/src/index.ts)
       |
       v
2. node_storage.py faithfully records absolute paths to DB
       |
       v
3. builder.py walks filesystem using RELATIVE paths (src/index.ts)
       |
       v
4. Query: "Give me node for src/index.ts"
   DB Response: "I only have /Users/dev/app/src/index.ts"
       |
       v
5. MISMATCH -> Zero Edges Created
       |
       v
6. flow_resolver.py runs on disconnected graph
       |
       v
7. Hits dead end immediately, busy-waits until max_depth
       |
       v
8. Never reaches Sink -> No vulnerability classified
```

### Actual Root Causes

| Layer | Root Cause | Impact |
|-------|------------|--------|
| **Extraction** | Absolute paths from TypeScript compiler | Breaks all DB JOINs |
| **Storage** | `DELETE FROM nodes` wipes previous batches | No incremental builds |
| **Graph Logic** | Naive string parsing (`split(" ")[0]`) | Loses complex expressions |
| **Graph Logic** | Fuzzy `LIKE %methodName%` resolution | False positive edges |
| **Analysis** | Bidirectional edges without filtering | Infinite traversal loops |

---

## Part 3: The Sum of All Bugs (Graph Layer Kill List)

### CRITICAL SEVERITY

#### 3.1 The "Wipe-Out" Bug
**File:** `theauditor/graph/store.py`
**Location:** `_save_graph_bulk` method

```python
# DANGER ZONE - This deletes EVERYTHING
conn.execute("DELETE FROM nodes WHERE graph_type = ?", (graph_type,))
conn.execute("DELETE FROM edges WHERE graph_type = ?", (graph_type,))
```

**Consequence:** Saving Batch 2 deletes Batch 1. For 10,000 files, changing 1 file wipes 9,999 files' nodes.

**Fix Required:**
```python
# Switch to UPSERT strategy
conn.executemany("""
    INSERT INTO nodes (...) VALUES (...)
    ON CONFLICT(id) DO UPDATE SET
    metadata = json_patch(nodes.metadata, excluded.metadata)
""", nodes_data)
```

#### 3.2 The "Re-Parser" Trap
**File:** `theauditor/graph/dfg_builder.py`
**Location:** `_parse_argument_variable` method

```python
# DANGER - Naive string splitting
clean_expr = arg_expr.split(" ")[0]  # Loses everything after space
```

**Failure Scenarios:**
- `deleteUser(req.body.id + 1)` -> loses `+ 1`
- `deleteUser(await getID())` -> returns `"await"` instead of `getID`
- `deleteUser(new User())` -> returns `"new"` instead of `User`

**Fix Required:** Use `arg_type` column from extraction, not string parsing.

#### 3.3 The "Name Collision" Trap
**File:** `theauditor/graph/strategies/interceptors.py`
**Location:** `_resolve_controller_info` method

```python
# DANGER - Fuzzy matching creates false edges
SELECT name, path FROM symbols
WHERE type = 'function' AND name LIKE ?  -- e.g. "%.updateUser"
```

**Consequence:** If you have `AdminController.updateUser` AND `UserController.updateUser`, query matches BOTH. Creates false attack paths connecting Public API to Admin Controller.

**Fix Required:** Resolve using exact import path, not global symbol search.

#### 3.4 Transaction Safety Gap
**File:** `theauditor/graph/store.py`

**Bug:** `executemany` not wrapped in explicit transaction.

**Failure Scenario:**
1. `DELETE FROM nodes` (Success)
2. `INSERT INTO nodes` (Fails - disk space/encoding error)
3. Result: Graph is EMPTY

**Fix Required:**
```python
with sqlite3.connect(self.db_path) as conn:
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        # ... delete ...
        # ... insert ...
        conn.commit()
    except:
        conn.rollback()
        raise
```

### HIGH SEVERITY

#### 3.5 The "One-Way" Graph Trap
**File:** `theauditor/graph/builder.py`

**Bug:** DFG Builder creates `_reverse` edges. Call Graph Builder does NOT.

**Consequence:** IFDS analyzer queries `type LIKE '%_reverse'` for backward traversal. Call/Import graphs have no reverse edges. Taint stops at function boundaries.

**Fix Required:** Use `types.create_bidirectional_edges` in builder.py.

#### 3.6 The RAM Explosion
**File:** `theauditor/graph/db_cache.py`
**Location:** Line 42

```python
# DANGER - Loads ENTIRE DATABASE into Python dict
cursor.execute("... FROM refs WHERE kind IN (...)")
self.imports_by_file = ...  # ALL imports in repo
```

**Consequence:** 500k+ rows for large repo. OOM crash on worker nodes.

**Fix Required:** Use `functools.lru_cache` on method that queries SQLite on-demand.

#### 3.7 The "ID Mismatch" Risk
**Divergent ID Formats:**

| Builder | ID Format | Example |
|---------|-----------|---------|
| `builder.py` (Call Graph) | `{module_path}::{function_name}` | `src/api::getUser` |
| `dfg_builder.py` (Data Flow) | `{file}::{scope}::{variable}` | `src/api::getUser::req` |

**Consequence:** Nodes from different graphs are "disjointed islands" - cannot traverse between them.

**Fix Required:** Standardize ID format across ALL builders.

#### 3.8 The Bidirectional Edge Explosion
**File:** `theauditor/graph/types.py`

```python
def create_bidirectional_edges(...):
    # Creates forward edge
    reverse = DFGEdge(..., type=f"{edge_type}_reverse", ...)  # DOUBLES graph size
    edges.append(reverse)
```

**Problems:**
1. **Graph Bloat:** 2x edges stored
2. **Engine Confusion:** BFS/DFS traverses `_reverse` edges back to source -> infinite loops

**Fix Required:** Store directionality flag in metadata OR explicitly filter `_reverse` in traversal.

### MEDIUM SEVERITY

#### 3.9 The "English Pluralization" Bug
**File:** `theauditor/graph/strategies/node_orm.py`
**Location:** `_infer_alias` method

```python
# DANGER - Guessing English plurals
if "Many" in assoc_type:
    if lower.endswith("y"): return lower[:-1] + "ies"  # category -> categories
```

**Failures:**
- `Person` -> `People` (Sequelize does this, script guesses `Persons`)
- `hasMany(Models.Comment, { as: 'feedback' })` -> script guesses `comments`, code uses `feedback`

**Fix Required:** Extract `as` alias from Sequelize options, stop guessing.

#### 3.10 The "Method Chaining" Blind Spot
**File:** `theauditor/graph/strategies/node_express.py`

```python
# DANGER - Only handles 2-part dot notation
parts = handler_expr.split(".")
if len(parts) == 2:  # e.g. UserController.index
```

**Failures:**
- `require('./controllers/user').index` - not handled
- `new UserController().index` - not handled
- `services.users.update` - 3 parts, not handled

**Fix Required:** Use `REFS` table to resolve variable definitions, not string splitting.

#### 3.11 Silent Symbol Resolution Drop
**File:** `theauditor/graph/strategies/node_express.py`

```python
if not symbol_result:
    stats["failed_resolutions"] += 1
    continue  # <--- SILENT DROP - No edge created
```

**Consequence:** API endpoints silently disappear from graph when controller can't be resolved.

**Fix Required:** Create "Ghost Node" (`type="unresolved_controller"`) instead of dropping.

---

## Part 4: Implementation Plan - Phased Approach

### Phase Order (CRITICAL)
Fix in dependency order: **Storage -> Graph Logic -> Analysis**

Do NOT fix Taint before fixing Graph. Do NOT fix Graph before fixing Storage.

### Phase 1: Stop the Bleeding (Storage Layer)

| Task | File | Action | Verification |
|------|------|--------|--------------|
| 1.1 | `store.py` | Remove `DELETE FROM nodes`. Switch to UPSERT. | `SELECT count(*) FROM nodes` increases after second build |
| 1.2 | `store.py` | Wrap operations in explicit transaction | Force disk-full error, verify rollback |
| 1.3 | `db_cache.py` | Replace eager loading with `lru_cache` | Monitor RAM during build |

### Phase 2: Connect the Tissue (Graph Logic)

| Task | File | Action | Verification |
|------|------|--------|--------------|
| 2.1 | `builder.py` | Use `create_bidirectional_edges` for imports/calls | `SELECT count(*) FROM edges WHERE type LIKE '%_reverse'` > 0 |
| 2.2 | `dfg_builder.py` | Remove `_parse_argument_variable`. Use `arg_type` column | No more `"await"` nodes in graph |
| 2.3 | `interceptors.py` | Require exact import match, disable `LIKE` fuzzy | No Admin->User false edges |
| 2.4 | `node_express.py` | Create Ghost Nodes for unresolved symbols | All routes have outbound edges |
| 2.5 | `types.py` | Add `is_reverse` flag instead of creating duplicate edges OR filter in traversal | Edge count ~50% of current |

### Phase 3: Standardize Identity

| Task | File | Action | Verification |
|------|------|--------|--------------|
| 3.1 | All builders | Standardize ID format: `{file}::{scope}::{symbol}` | Query: same file returns matching IDs across graph types |
| 3.2 | All builders | Force relative paths before ID generation | No IDs starting with `/` or `C:\` |
| 3.3 | Vue handling | Map `/virtual_vue/` back to original `.vue` path | Vue symbols linked to real files |

---

## Part 5: Edge Case & Failure Mode Analysis

### Edge Cases to Handle

| Scenario | Current Behavior | Required Behavior |
|----------|------------------|-------------------|
| Empty graph save | Deletes all existing nodes | No-op if nothing to save |
| Symbol resolution failure | Silent drop | Create Ghost Node |
| Complex expression argument | Returns first word | Mark as `complex_expr` node |
| OOM during cache load | Crash | Stream from DB with LRU |
| Path format mismatch | Broken edges | Normalize at extraction, verify at storage |
| Circular edges (A->B->A) | Infinite traversal | Cycle detection in traverser |

### Performance Considerations

| Component | Current Complexity | Target Complexity |
|-----------|-------------------|-------------------|
| Graph save | O(n) delete + O(n) insert | O(changed) upsert |
| Cache lookup | O(1) but O(n) RAM | O(1) with O(cache_size) RAM |
| Edge count | 2n (bidirectional) | n (with reverse flag) |
| Symbol resolution | O(m) fuzzy search | O(1) exact lookup |

---

## Part 6: Diagnostic Commands

### Graph Integrity Check Script
```python
import sqlite3
import os

DB_PATH = "./.pf/repo_index.db"
GRAPH_DB_PATH = "./.pf/graphs.db"

def check_graph_integrity():
    # 1. Check File Path Formats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM files LIMIT 5")
    files = [row[0] for row in cursor.fetchall()]
    print(f"Sample paths: {files}")
    if files and os.path.isabs(files[0]):
        print("WARNING: DB uses ABSOLUTE paths - will cause edge failures")
    conn.close()

    # 2. Check Graph Stats
    conn = sqlite3.connect(GRAPH_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM nodes")
    node_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM edges")
    edge_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM edges WHERE type LIKE '%_reverse'")
    rev_count = cursor.fetchone()[0]

    print(f"Nodes: {node_count}")
    print(f"Edges: {edge_count}")
    print(f"Reverse Edges: {rev_count}")

    if node_count > 0 and edge_count == 0:
        print("CRITICAL: Nodes exist but NO EDGES - path mismatch likely")
    if edge_count > 0 and rev_count == 0:
        print("WARNING: No reverse edges - IFDS backward analysis will fail")
    conn.close()

if __name__ == "__main__":
    check_graph_integrity()
```

### SQL Verification Queries
```sql
-- Check path format consistency
SELECT src FROM refs LIMIT 5;
-- Should NOT start with '/' or 'C:\'

-- Check ID format consistency
SELECT id FROM nodes WHERE graph_type='call' AND file='src/api.ts'
UNION ALL
SELECT id FROM nodes WHERE graph_type='data_flow' AND file='src/api.ts';
-- IDs should use same format

-- Check reverse edge coverage
SELECT graph_type,
       count(*) as total,
       sum(case when type like '%_reverse' then 1 else 0 end) as reverse
FROM edges
GROUP BY graph_type;
-- reverse should be ~50% of total for each type
```

---

## Part 7: Success Criteria

### Verification Checkpoints

| Checkpoint | Query/Command | Expected Result |
|------------|---------------|-----------------|
| CP1: Incremental builds work | Build twice, count nodes | Second build count >= first |
| CP2: Reverse edges exist | `SELECT count(*) WHERE type LIKE '%_reverse'` | > 0 for ALL graph types |
| CP3: No absolute paths | `SELECT path FROM files WHERE path LIKE '/%'` | 0 rows |
| CP4: No orphan nodes | `SELECT count(*) FROM nodes WHERE id NOT IN (SELECT source FROM edges UNION SELECT target FROM edges)` | Low count (entry points only) |
| CP5: RAM stable | Monitor during full repo build | < 4GB for 50k file repo |

### Definition of Done

1. Graph can be built incrementally (changing 1 file doesn't wipe 9,999)
2. All graph types have bidirectional edges for IFDS traversal
3. All paths are normalized (relative, forward slashes)
4. No fuzzy matching for symbol resolution
5. Ghost nodes created for unresolved symbols (no silent drops)
6. RAM usage bounded by LRU cache size
7. All diagnostic queries pass verification checkpoints

---

## Part 8: Files Requiring Modification

| File Path | Priority | Changes Required |
|-----------|----------|------------------|
| `theauditor/graph/store.py` | CRITICAL | UPSERT logic, transaction safety |
| `theauditor/graph/dfg_builder.py` | CRITICAL | Remove string parsing, use arg_type |
| `theauditor/graph/builder.py` | HIGH | Use create_bidirectional_edges |
| `theauditor/graph/db_cache.py` | HIGH | LRU cache instead of eager load |
| `theauditor/graph/types.py` | HIGH | Reverse edge flag vs duplicate |
| `theauditor/graph/strategies/interceptors.py` | MEDIUM | Exact import resolution |
| `theauditor/graph/strategies/node_express.py` | MEDIUM | Ghost nodes, method chaining |
| `theauditor/graph/strategies/node_orm.py` | MEDIUM | Extract alias, stop guessing |

---

## Appendix A: Architecture Decision

### Why Graph Layer Must Be Fixed FIRST

You physically **cannot** do accurate Taint Analysis without a functioning Graph Engine. Taint Analysis is fundamentally **graph traversal** - asking "is there a path from node A to node B?"

**The Dependency Chain:**
```
Extraction -> Storage -> Graph -> Taint
    |            |          |        |
    v            v          v        v
  (data)      (persist)  (connect) (traverse)
```

If the Graph Layer is broken (disconnected nodes, missing edges, path mismatches), Taint Analysis will:
- Hit dead ends immediately (no edges to traverse)
- Report false negatives (missing vulnerability paths)
- Spin uselessly until max_depth (no real progress)

**Current Evidence:** 99.6% of flows hitting max_depth=20 is proof the graph is broken, not that the codebase has 99,116 twenty-hop vulnerability chains.

**Sequencing Rule:** Fix Graph first. Validate with diagnostic queries. THEN address taint-specific issues in `TAINT_HANDOFF.md`.

---

## Appendix B: Quick Reference Card

```
GRAPH LAYER REFACTOR - QUICK REFERENCE

DO:
  - Use UPSERT in store.py
  - Use create_bidirectional_edges() for ALL edge creation
  - Use arg_type column from extraction
  - Create Ghost Nodes for unresolved symbols
  - Use lru_cache for db_cache.py
  - Normalize paths to relative format

DON'T:
  - DELETE FROM nodes (wipes graph)
  - split(" ")[0] for argument parsing (loses data)
  - LIKE '%name%' for symbol resolution (false matches)
  - Load entire DB into RAM (OOM)
  - Silent continue on resolution failure (loses edges)
  - Create duplicate edges for reverse (bloat)

VERIFY:
  - aud full --index
  - sqlite3 .pf/graphs.db "SELECT count(*) FROM edges WHERE type LIKE '%_reverse'"
  - python check_graph_integrity.py
```

---

**Document Status:** Ready for Architect Review
**Next Action:** Await approval to proceed with Phase 1 implementation
