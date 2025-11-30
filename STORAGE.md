# STORAGE LAYER PRE-IMPLEMENTATION PLAN

**Document Version:** 1.0
**Status:** Pre-Implementation
**Last Updated:** 2025-11-30

---

## Executive Summary

This document consolidates all identified Storage Layer issues from the comprehensive code review. The Storage Layer is the critical bridge between Extraction (TypeScript/Python) and all downstream consumers (Graph Builder, FCE, Taint Analysis, Context Queries). Current failures cause cascading data loss, orphaned records, and broken referential integrity.

**The Core Problem:** The Storage Layer is silently corrupting, truncating, and discarding data before it ever reaches downstream consumers. Even perfect extraction produces incomplete results when storage fails its contract.

**Downstream Consumers Affected:**
- Graph Builder (call graphs, data flow graphs)
- FCE (Function Call Explorer)
- Taint Analysis (forward/backward flow resolution)
- Context Queries (`aud context query`)
- Rules Engine (security pattern matching)

---

## Part 1: Critical Bugs (Must Fix First)

### 1.1 The "Negative ID" Bug (CFG Detachment)

**Severity:** CRITICAL (Referential Integrity Violation)
**Files:** `node_storage.py`, `core_database.py`, `core_storage.py`
**Impact:** CFG statements orphaned - function bodies have no linkage to their containing blocks

**The Problem:**
- `add_cfg_block` uses a batching strategy returning temporary negative IDs (-1, -2, etc.)
- `add_cfg_statement` receives these negative IDs and stores them
- When `flush_batch()` executes, SQLite generates real IDs (e.g., 100, 101)
- Statements remain pointing to non-existent block `-1`

**Evidence from `node_storage.py`:**
```python
for block in cfg_blocks:
    # 1. Returns TEMP NEGATIVE ID (e.g., -1)
    temp_id = self.db_manager.add_cfg_block(...)

    # 2. Maps logical ID to NEGATIVE ID
    block_id_map[(function_id, block_id)] = temp_id

for stmt in cfg_block_statements:
    # 3. Retrieves NEGATIVE ID
    real_block_id = block_id_map.get((function_id, block_id), -1)

    # 4. Queues statement with block_id = -1
    self.db_manager.add_cfg_statement(real_block_id, ...)
```

**Evidence from `core_database.py`:**
```python
def add_cfg_block(self, ...):
    temp_id = -(len(batch) + 1)  # Returns -1, -2, etc.
    batch.append((..., temp_id))
    return temp_id
```

**The Fix:**
You MUST flush the `cfg_blocks` batch immediately to get real SQLite Row IDs before processing statements:

```python
# Fix in node_storage.py -> _store_cfg_flat

# 1. Collect Blocks (do NOT call db_manager.add_cfg_block yet)
block_batch = []
for block in cfg_blocks:
    block_batch.append(block)

# 2. Insert Blocks immediately and get mapping
cursor = self.db_manager.conn.cursor()
for block in block_batch:
    cursor.execute("INSERT INTO cfg_blocks ...")
    real_id = cursor.lastrowid
    block_id_map[(block['function_id'], block['block_id'])] = real_id

# 3. NOW process statements with real_id
for stmt in cfg_block_statements:
    real_block_id = block_id_map.get(...)
    self.db_manager.add_cfg_statement(real_block_id, ...)
```

---

### 1.2 The "Wipe-Out" Bug (Delete-on-Write)

**Severity:** CRITICAL (Total Data Loss)
**File:** `store.py` (Lines 37-38)
**Impact:** Saving Batch 2 deletes Batch 1

**The Problem:**
```python
def _save_graph_bulk(self, graph: dict[str, Any], graph_type: str, ...):
    with sqlite3.connect(self.db_path) as conn:
        # DANGER ZONE
        conn.execute("DELETE FROM nodes WHERE graph_type = ?", (graph_type,))
        conn.execute("DELETE FROM edges WHERE graph_type = ?", (graph_type,))
```

**Consequence:**
- Every time you save the graph, you delete the ENTIRE graph for that type
- Scenario: 10,000 files, change 1 file - system deletes other 9,999 files' nodes
- Result: Cannot support incremental builds

**The Fix:**
Switch to Upsert (Update or Insert) strategy:

```python
# Remove the DELETE statements
# Use ON CONFLICT clause
conn.executemany("""
    INSERT INTO nodes (...) VALUES (...)
    ON CONFLICT(id) DO UPDATE SET
    metadata = json_patch(nodes.metadata, excluded.metadata)
""", nodes_data)
```

**Alternative for Incremental Builds:**
```python
# Only delete for specific file scope
def _save_graph_bulk(self, graph, graph_type, file_path=None):
    if file_path:
        conn.execute("DELETE FROM nodes WHERE file = ? AND graph_type = ?",
                     (file_path, graph_type))
```

---

### 1.3 Transaction Safety (Data Corruption Risk)

**Severity:** HIGH
**File:** `store.py` (Line 36)
**Impact:** Partial writes leave graph empty

**The Problem:**
`with sqlite3.connect(...)` handles the connection, but `executemany` is not wrapped in atomic transaction block.

**Failure Scenario:**
1. `DELETE FROM nodes` (Success)
2. `INSERT INTO nodes` (Fails due to disk space or encoding error)
3. Result: Graph is EMPTY - analysis is gone

**The Fix:**
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

---

## Part 2: High Severity Issues

### 2.1 The "Hook Truncation" Sabotage

**Severity:** HIGH
**File:** `node_database.py` (Line 67)
**Impact:** Data loss - code after character 500 is silently discarded

**The Problem:**
```python
if callback_body and len(callback_body) > 500:
    callback_body = callback_body[:497] + "..."
```

**Why This Violates Data Integrity:**
- Modern React apps put substantial logic inside `useEffect`, `useCallback`, etc.
- Any code after character 500 is permanently lost from the database
- Downstream consumers (Graph Builder, FCE, Taint) receive incomplete data
- Queries for symbols/calls in truncated regions return nothing

**The Fix:**
```python
# DELETE the truncation logic entirely
# Storage is cheap; incomplete data breaks all downstream analysis
# callback_body = callback_body  # Store full content
```

---

### 2.2 The "Implicit Column" / Fragile Foreign Keys

**Severity:** HIGH
**Files:** `core_database.py` (Line 95), `core_schema.py` (Line 268)
**Impact:** JOINs fail, data flow graph breaks

**The Problem:**
`add_assignment` uses composite Foreign Key relying on `(file, line, col)`:
```python
self.generic_batches["assignment_sources"].append(
    (file_path, line, col, target_var, source_var)
)
```

**The Risk:**
- TypeScript extractor emits slightly different column numbers for assignment vs variable nodes
- AST parsers often report fractionally different positions
- FK constraint fails or JOIN misses - link between Variable A and Variable B is severed

**The Fix:**
Use Artificial IDs:
```python
# When storing ASSIGNMENT, return real SQLite ROWID
assignment_id = cursor.lastrowid

# Use that ID in ASSIGNMENT_SOURCES
self.generic_batches["assignment_sources"].append(
    (assignment_id, source_var)  # Don't rely on line/col
)
```

Schema Update for `core_schema.py`:
```python
# Add to ASSIGNMENTS table
Column("id", "INTEGER PRIMARY KEY")

# Update ASSIGNMENT_SOURCES
Column("assignment_id", "INTEGER", nullable=False)
# Add FK to assignment_id, NOT file/line/col
```

---

### 2.3 Strict Type Validation Crashes Storage

**Severity:** HIGH
**File:** `core_storage.py` (Line 158)
**Impact:** One bad symbol crashes entire batch

**The Problem:**
```python
raise TypeError(f"EXTRACTOR BUG: Symbol.col must be int >= 0...")
```

**Consequence:**
- If 1 symbol in 10,000 lines is malformed (e.g., `col = -1` from parser bug)
- ENTIRE file is rejected by orchestrator try/catch
- Lose 99.9% good data because of 0.1% bad data

**The Fix:**
```python
# Log and continue, don't crash
if col < 0:
    logger.warning(f"Invalid column {col} for symbol {name}, sanitizing to 0")
    col = 0
    continue  # Or sanitize: col = max(0, col)
```

---

### 2.4 Schema Nullability Mismatches

**Severity:** MEDIUM-HIGH
**Files:** `core_schema.py` vs `core_storage.py`
**Impact:** Random batch insertion failures

**The Problem:**
Schema defines strict constraints:
```python
Column("target_var", "TEXT", nullable=False)
Column("source_expr", "TEXT", nullable=False)
```

But extractors may produce None for complex patterns:
```python
# core_storage.py
assignment["target_var"]  # Might be None for ({a} = b) destructuring
```

**The Fix:**
Add defensive defaults:
```python
target_var = assignment.get("target_var") or "unknown_var"
source_expr = assignment.get("source_expr") or "unknown_expr"
```

---

### 2.5 Express Strategy "Silent Drops"

**Severity:** HIGH
**File:** `node_express.py`
**Impact:** API endpoints missing from graph

**The Problem:**
```python
if not symbol_result:
    stats["failed_resolutions"] += 1
    continue  # <--- SILENT DROP
```

If symbol extractor fails to index an export pattern, the edge is silently discarded. This breaks the path from `GET /api/user` -> `UserController.getUser`.

**The Fix:**
Create Ghost Nodes instead of dropping:
```python
if not symbol_result:
    stats["failed_resolutions"] += 1
    # Create placeholder node
    ghost_node = DFGNode(
        id=f"unresolved::{handler_expr}",
        type="unresolved_controller",
        # ...
    )
    nodes.append(ghost_node)
    # Create edge to ghost
    edges.append(create_edge(source, ghost_node.id))
```

---

## Part 3: Memory & Performance Issues

### 3.1 The RAM Explosion (db_cache.py)

**Severity:** MEDIUM (OOM on large repos)
**File:** `db_cache.py` (Line 42)
**Impact:** 10GB+ RAM consumption, container OOM kills

**The Problem:**
```python
cursor.execute("... FROM refs WHERE kind IN (...)")
self.imports_by_file = ...  # Loads EVERYTHING into Python Dict
```

On repos with 1M+ lines, `refs` table easily hits 500k+ rows. Loading entire table into Dict at startup causes OOM.

**The Fix:**
SQLite is already a cache (pages in RAM). Don't double-cache in Python:
```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def get_imports_for_file(self, file_path: str) -> list:
    cursor.execute("SELECT ... FROM refs WHERE file = ?", (file_path,))
    return cursor.fetchall()
```

---

### 3.2 Graph Preloading Memory Bomb (Consumer Pattern)

**Severity:** MEDIUM
**File:** `flow_resolver.py` (Consumer-side, but storage-relevant)
**Impact:** OOM before analysis starts

**Note:** This is a consumer-side issue, but included here because storage layer design should accommodate lazy-loading patterns.

**The Problem:**
```python
def _preload_graph(self):
    cursor.execute("SELECT source, target, type FROM edges ...")
    for source, target, edge_type in cursor.fetchall():
        self.adjacency_list[source].append(target)
```

5M edges = 10GB+ RAM in Python dictionaries.

**The Fix (Consumer-side):**
Use LRU cache + on-demand SQL:
```python
@lru_cache(maxsize=50000)
def _get_successors(self, node_id: str) -> list:
    cursor.execute(
        "SELECT target FROM edges WHERE source = ?",
        (node_id,)
    )
    return [row[0] for row in cursor.fetchall()]
```

**Storage Layer Consideration:** Ensure `edges` table has index on `source` column for efficient point lookups.

---

### 3.3 Bidirectional Edge Bloat

**Severity:** LOW-MEDIUM
**File:** `types.py`
**Impact:** 2x storage size, potential traversal loops for consumers

**The Problem:**
```python
def create_bidirectional_edges(...):
    # ... creates forward edge ...
    reverse = DFGEdge(..., type=f"{edge_type}_reverse", ...)
    edges.append(reverse)
```

**Issues:**
1. Storing 2x the edges - database bloat, slower queries
2. Consumers traversing without filtering may hit infinite loops

**The Fix:**
Store directionality in metadata, not as separate rows:
```python
def create_edge(..., bidirectional=True):
    edge = DFGEdge(..., metadata={"bidirectional": bidirectional})
    return [edge]  # Single edge, metadata flag
```

**Consumer-side mitigation (if storage unchanged):**
```python
# Consumers should filter reverse edges when doing forward traversal
if edge_type.endswith("_reverse"):
    continue
```

---

## Part 4: Path & ID Mismatch Issues

### 4.1 The "Split-Brain" Path Crisis

**Severity:** CRITICAL
**Files:** `main.ts`, `builder.py`, `node_storage.py`
**Impact:** Zero edges created - disconnected graph

**The Problem:**
- Node.js (`main.ts`): Uses Absolute Paths (`/Users/dev/app/src/index.ts`)
- Python (`builder.py`): Uses Relative Paths (`src/index.ts`)

**The Failure Chain:**
1. `main.ts` parses file, resolves imports to absolute paths
2. `node_storage.py` saves absolute paths to DB
3. `builder.py` queries DB for relative path - NO MATCH
4. Result: Nodes exist, edges never created

**The Fix in `main.ts`:**
```typescript
function toRelative(absPath: string, root: string): string {
  return path.relative(root, absPath).split(path.sep).join(path.posix.sep);
}

// Apply to ALL output paths
results[fileInfo.original] = {
  fileName: toRelative(fileInfo.absolute, projectRoot),
  imports: imports.map(i => ({
    ...i,
    module: path.isAbsolute(i.module)
      ? toRelative(i.module, projectRoot)
      : i.module
  }))
};
```

---

### 4.2 Vue.js Virtual File Path Mismatch

**Severity:** HIGH
**File:** `main.ts`
**Impact:** Vue components detached from graph

**The Problem:**
```typescript
const virtualPath = `/virtual_vue/${scopeId}.${isTs ? "ts" : "js"}`;
```

- DB contains symbols linked to `/virtual_vue/12345678.ts`
- `builder.py` iterates files on disk, finds `Component.vue`
- All Vue script block logic is detached

**The Fix:**
Map virtual paths back to original:
```typescript
const isVirtual = fileInfo.absolute.includes('/virtual_vue/');
const outputFileName = isVirtual
  ? toRelative(fileInfo.original, projectRoot)  // Original .vue path
  : toRelative(fileInfo.absolute, projectRoot);
```

---

### 4.3 ID Format Mismatch Between Builders

**Severity:** MEDIUM
**Files:** `builder.py`, `dfg_builder.py`, `interceptors.py`
**Impact:** Cross-graph linking fails

**The Problem:**
- Call Graph (`builder.py`): `{module_path}::{function_name}`
- Data Flow (`dfg_builder.py`): `{file}::{scope}::{variable}`
- Interceptors: `{file}::{function}::input`

If path prefixes differ (`src/api.ts` vs `api.ts`), graphs become disjointed islands.

**Verification Query:**
```sql
SELECT id FROM nodes WHERE graph_type='call' AND file='same_file.py'
UNION ALL
SELECT id FROM nodes WHERE graph_type='data_flow' AND file='same_file.py'
-- Check if path prefixes match EXACTLY
```

**The Fix:**
Standardize ID generation across all builders:
```python
# In all builders, use same normalization
def make_node_id(file: str, scope: str, name: str) -> str:
    normalized_file = normalize_path(file)  # Common function
    return f"{normalized_file}::{scope}::{name}"
```

---

## Part 5: Implementation Order

**CRITICAL: Fix in Dependency Order - Extractor -> Storage -> Graph -> Consumers**

Storage must be fixed before downstream consumers (Graph Builder, FCE, Taint, Context Queries) can produce correct results.

### Phase 1: Stop the Bleeding (Storage Layer)
Priority 1 fixes that prevent data corruption:

| Priority | Bug | File | Action |
|----------|-----|------|--------|
| P0 | Negative ID Bug | `node_storage.py` | Flush cfg_blocks immediately to get real IDs |
| P0 | Delete-on-Write | `store.py` | Switch to INSERT OR REPLACE / ON CONFLICT |
| P1 | Hook Truncation | `node_database.py` | Remove 500-char truncation |
| P1 | Transaction Safety | `store.py` | Wrap in explicit BEGIN/COMMIT/ROLLBACK |
| P2 | Storage Crashes | `core_storage.py` | Log and continue, don't raise |
| P2 | Nullability | `core_storage.py` | Add `.get() or "unknown"` defaults |

### Phase 2: Path Normalization
Ensure data consistency between layers:

| Priority | Bug | File | Action |
|----------|-----|------|--------|
| P1 | Absolute Paths | `main.ts` | Force relative paths via `toRelative()` |
| P1 | Vue Virtual Paths | `main.ts` | Map back to original `.vue` file |
| P2 | ID Mismatch | All builders | Standardize ID format |

### Phase 3: Memory Optimization
Prevent OOM on large repos:

| Priority | Bug | File | Action |
|----------|-----|------|--------|
| P2 | RAM Explosion | `db_cache.py` | Use LRU cache, query on demand |
| P2 | Edge Bloat | `types.py` | Metadata flag vs duplicate edges |
| P3 | Graph Preload | `flow_resolver.py` | Consumer-side: lazy load adjacency |

*Note: P3 item is consumer-side but included for completeness. Storage should ensure proper indexing to support lazy-loading patterns.*

---

## Part 6: Verification Checklist

Run these after each fix phase:

### After Phase 1:
```bash
# Verify CFG statements have real block IDs (not -1)
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM cfg_block_statements WHERE block_id < 0"
# Expected: 0

# Verify edges exist after multiple saves
aud graph build
sqlite3 .pf/graphs.db "SELECT COUNT(*) FROM edges"
# Expected: > 0
```

### After Phase 2:
```bash
# Verify paths are relative
sqlite3 .pf/repo_index.db "SELECT path FROM files LIMIT 5"
# Expected: src/..., NOT /Users/...

# Verify no virtual_vue paths in final storage
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols WHERE path LIKE '%virtual_vue%'"
# Expected: 0
```

### After Phase 3:
```bash
# Monitor memory during full build
aud full --offline 2>&1 | head -100
# Watch for OOM warnings
```

---

## Appendix A: Schema Changes Required

```sql
-- ASSIGNMENTS table: Add artificial ID
ALTER TABLE assignments ADD COLUMN id INTEGER PRIMARY KEY;

-- ASSIGNMENT_SOURCES: Reference by ID, not line/col
CREATE TABLE assignment_sources_v2 (
    assignment_id INTEGER REFERENCES assignments(id),
    source_var TEXT NOT NULL
);

-- CFG_BLOCK_STATEMENTS: Add FK constraint
ALTER TABLE cfg_block_statements
ADD CONSTRAINT fk_block_id
FOREIGN KEY (block_id) REFERENCES cfg_blocks(id);
```

---

## Appendix B: Quick Reference - File Locations

| Component | File | Line(s) |
|-----------|------|---------|
| CFG Batching | `theauditor/storage/core_database.py` | add_cfg_block |
| CFG Storage | `theauditor/storage/node_storage.py` | _store_cfg_flat |
| Graph Wipe | `theauditor/graph/store.py` | 37-38 |
| Hook Truncation | `theauditor/storage/node_database.py` | 67 |
| Type Crashes | `theauditor/storage/core_storage.py` | 158 |
| DB Cache | `theauditor/graph/db_cache.py` | 42 |
| Path Resolution | `theauditor/ast_extractors/javascript/src/main.ts` | results assignment |
| ID Generation | `theauditor/graph/builder.py` | Node ID creation |
| ID Generation | `theauditor/graph/dfg_builder.py` | Node ID creation |

---

## Related Documents

| Document | Scope | Relationship |
|----------|-------|--------------|
| `TAINT_HANDOFF.md` | Taint Analysis Engine | Consumer-side issues (vulnerability classification, max_depth, sanitizer detection) |
| `CLAUDE.md` | Project conventions | Environment setup, forbidden patterns |
| `teamsop.md` | Workflow protocol | Report templates, verification standards |

**Boundary Note:** This document covers Storage Layer data integrity. Consumer-side logic issues (how data is interpreted/classified after retrieval) belong in their respective domain documents.

---

**Document Status:** Ready for Implementation
**Next Action:** Begin Phase 1 - Fix Negative ID Bug in `node_storage.py`
