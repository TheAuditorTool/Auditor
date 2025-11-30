# TAINT Layer Pre-Implementation Plan

**Document Type:** Pre-Implementation Technical Plan (teamsop.md v4.20 Compliant)
**Layer:** Taint Analysis Engine
**Status:** PLANNING - Awaiting Implementation
**Last Updated:** 2025-11-30

---

## Executive Summary

The Taint Analysis layer is experiencing **Systemic Disconnection** - a cascading data failure where:
1. **Extraction** misses ~40% of code (strict filters, AST null)
2. **Storage** corrupts ~20% of what remains (truncation, schema rejection)
3. **Graph** hallucinates connections to fill gaps (fuzzy matching)
4. **Taint Analysis** explodes because the graph is a hairball (99.6% max depth hits)

**Root Cause:** "Split-Brain" Path Cascade - Absolute vs Relative path mismatch flowing from Extractors into Database, severing edges in Graph, and blinding the Resolver.

---

## Relationship to TAINT_HANDOFF.md

**Context:** `TAINT_HANDOFF.md` documents the operational symptoms observed during PlantFlow analysis:
- 99.6% of flows hitting `max_depth=20`
- 100% `vulnerability_type = "unknown"`
- 67.6% `sink_line` populated
- 0% sanitizer matches

**These are downstream effects of the architectural issues documented in this plan.**

| HANDOFF Symptom | Root Cause (This Document) |
|-----------------|---------------------------|
| 99.6% max_depth | GRP-004: Bidirectional edges + TNT-002: Disconnected graph = infinite bouncing |
| 0% vuln classification | TNT-004: Hardcoded "unknown" + path mismatches preventing sink matching |
| 67.6% sink_line | STO-001: Truncation + EXT-005: JSX not captured in extractor |
| 0 sanitizer matches | TNT-006: Path strings don't match between registry and resolver |

**Guidance for Current Work:**
1. **Do NOT pivot** to taint-layer-only fixes - they will paper over, not solve, the problem
2. **Quick wins are valid** - The UNION query fix (Task 4.4) and vuln classification (Task 4.3) can be committed for partial improvement
3. **Full resolution requires upstream fixes** - Phases 1-3 must complete before Phase 4 symptoms truly resolve
4. **Be aware, don't derail** - Current tickets should acknowledge taint issues exist without abandoning their scope

---

## Part 1: The Sum of All Bugs (Kill List)

### 1.1 Extraction Layer (The Root Cause)

| Bug ID | Severity | Location | Description |
|--------|----------|----------|-------------|
| EXT-001 | CRITICAL | `main.ts` | **"Headless" Bug:** `ast: null` disables all Python fallbacks, causing complex nodes to vanish |
| EXT-002 | CRITICAL | `security_extractors.ts` | **"Security Blinder":** Ignores SQL queries if they are variables; ignores API routes if variable isn't named `router` or `app` |
| EXT-003 | HIGH | `schema.ts` | **"Strictness" Trap:** Zod schemas reject entire files if single field missing (e.g., `extraction_pass`) |
| EXT-004 | HIGH | `data_flow.ts` | **Blind Aliasing:** `const run = exec; run(...)` ignored - matches string names, not symbol definitions |
| EXT-005 | MEDIUM | `main.ts` | **Vue Virtual Paths:** Virtual paths (`/virtual_vue/...`) not mapped back to original `.vue` files |

### 1.2 Storage Layer (The Data Corruptor)

| Bug ID | Severity | Location | Description |
|--------|----------|----------|-------------|
| STO-001 | CRITICAL | `node_database.py:67` | **"Truncation" Sabotage:** React Hook bodies cut at 500 chars. Sinks after char 500 deleted |
| STO-002 | HIGH | `core_schema.py:268` | **Fragile FKs:** Links tables using `(file, line, col)`. Float columns break JOINs |
| STO-003 | HIGH | `core_storage.py:158` | **"Crash" Policy:** Worker throws `TypeError` on malformed symbol, drops entire batch |
| STO-004 | CRITICAL | `node_storage.py` | **CFG Negative ID Bug:** `cfg_blocks` uses temp negative IDs; statements stored with -1, causing orphan records |

### 1.3 Graph Layer (The Hallucinator)

| Bug ID | Severity | Location | Description |
|--------|----------|----------|-------------|
| GRP-001 | HIGH | `dfg_builder.py` | **"Re-Parser":** Uses `split(" ")[0]` for arguments. `await getID()` becomes `await`, losing function link |
| GRP-002 | HIGH | `interceptors.py:87-95` | **"Fuzzy" Controller:** `LIKE %methodName%` connects `Admin.update` to `User.update` - false attack paths |
| GRP-003 | CRITICAL | `store.py:37-38` | **"Nuke" Bug:** `DELETE FROM nodes WHERE graph_type = ?` wipes entire graph on save |
| GRP-004 | MEDIUM | `types.py` | **Bidirectional Noise:** Creates `_reverse` edges doubling graph size, causing infinite loops |
| GRP-005 | HIGH | `builder.py:122-127` | **Path Normalization Fallback:** Falls back to absolute path if relativization fails, breaking lookups |
| GRP-006 | HIGH | `db_cache.py:42` | **RAM Explosion:** Loads entire `refs` table into Python dict at startup - OOM on large repos |

### 1.4 Taint Layer (The Victim)

| Bug ID | Severity | Location | Description |
|--------|----------|----------|-------------|
| TNT-001 | CRITICAL | `ifds_analyzer.py` | **Backward Analysis Fail:** Queries `source = ?` with `type LIKE '%_reverse'` - returns 0 if reverse edges missing |
| TNT-002 | CRITICAL | `flow_resolver.py` | **Infinite Loops:** "Everything connects to everything" causes 99.6% max_depth (20) hits |
| TNT-003 | HIGH | `flow_resolver.py` | **Preload OOM:** `_preload_graph` loads entire graph into memory - 10GB+ for 5M edges |
| TNT-004 | HIGH | `flow_resolver.py:597` | **Hardcoded "unknown":** Vulnerability classification hardcoded to "unknown" |
| TNT-005 | MEDIUM | `access_path.py` | **Global Fallback:** Malformed node IDs default to `function="global"`, breaking edges |
| TNT-006 | MEDIUM | `type_resolver.py` | **Path String Mismatch:** Controller file paths stored differently than queried, missing entry points |

---

## Part 2: The "Split-Brain" Cascade (Root Cause Analysis)

### 2.1 Data Flow Diagram

```
[Node.js Extractor]              [Python Storage]               [Graph Builder]
main.ts                          node_storage.py                builder.py
     |                                 |                              |
     v                                 v                              v
ABSOLUTE PATHS          -->       STORES AS-IS        <--      QUERIES RELATIVE
/Users/dev/app/src/index.ts       /Users/dev/...               src/index.ts
     |                                 |                              |
     v                                 v                              v
Virtual Vue paths                 Stores /virtual_vue/...      Looks for .vue
/virtual_vue/1234.ts             in symbols table              NO MATCH
     |                                 |                              |
     +---> MISMATCH <-----------------+-----------> ZERO EDGES CREATED
```

### 2.2 The Failure Chain

1. **Source (Node.js):** `main.ts` extracts high-fidelity data but stamps it with:
   - **Absolute Paths:** `/Users/dev/app/src/index.ts`
   - **Virtual Paths:** `/virtual_vue/...`

2. **Storage (Python):** `node_storage.py` faithfully records these paths into `symbols` and `imports`.

3. **Graph (Python):** `builder.py` walks the file system using **Relative Paths** (`src/index.ts`). It tries to link nodes:
   - Query: "Give me the node for `src/index.ts`."
   - DB Response: "I only have `/Users/dev/app/src/index.ts`."
   - Result: **Mismatch. Zero Edges created.**

4. **Resolver (Python):** `flow_resolver.py` runs on a disconnected graph:
   - Finds entry point
   - Tries to step forward
   - Hits "dead end" (missing edge) immediately
   - Fallback: Blindly iterates until `max_depth=20` - busy-waiting

5. **Report:** Resolver never reached a Sink (broken edges), never triggered vulnerability classifier:
   - Result: **99,116 flows, 100% "Unknown" vulnerability, 0% Sanitized**

---

## Part 3: The Master Remediation Plan

**Implementation Order:** Extractor --> Storage --> Graph --> Taint (Fix dependencies first)

### Phase 1: Stop the Poison (Extraction Layer)

**Goal:** Ensure `repo_index.db` contains normalized, relative paths matching the file system.

#### Task 1.1: Fix Path Normalization in `main.ts`
- **File:** `theauditor/ast_extractors/javascript/src/main.ts`
- **Action:** Force all output paths relative to `projectRoot`. Unwrap Vue virtual paths.
- **Implementation:**
```typescript
// Add helper
function toRelative(absPath: string, root: string): string {
  if (absPath.includes('/virtual_vue/')) {
    return path.relative(root, originalFilePath);
  }
  return path.relative(root, absPath).split(path.sep).join('/');
}

// Apply to results
fileName: toRelative(fileInfo.absolute, resolvedProjectRoot),
imports: imports.map(i => ({
  ...i,
  module: path.isAbsolute(i.module) ? toRelative(i.module, root) : i.module
})),
```

#### Task 1.2: Enable AST Fallback
- **File:** `main.ts`
- **Action:** Set `ast: sourceFile` (or stripped version) so Python can handle edge cases
- **Current:** `ast: null` disables all Python fallbacks

#### Task 1.3: Loosen Zod Schemas
- **File:** `schema.ts`
- **Action:** Make every field `.optional()` or `.nullable()`. Stop rejecting data.

#### Task 1.4: Fix SQL Extraction for Variables
- **File:** `security_extractors.ts`
- **Action:** Capture `call.arguments[0]` even if variable. Flag as `{"dynamic_sql": true}`

#### Task 1.5: Fix Sink Aliasing
- **File:** `data_flow.ts`
- **Action:** Use `checker.getAliasedSymbol(symbol)` to resolve `run` back to `exec`

#### Task 1.6: Relax Router Pattern Matching
- **File:** `security_extractors.ts:87-90`
- **Current:**
```typescript
const ROUTER_PATTERNS = ["router", "app", "express", "server", "route"];
const isRouter = ROUTER_PATTERNS.some((p) => receiver.includes(p));
```
- **Action:** Remove name check. If method is HTTP verb and first arg looks like route (`/`), assume endpoint.

**Verification:**
```bash
cd theauditor/ast_extractors/javascript && npm run build
aud full --index
# Check paths
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT src FROM refs LIMIT 5')
for row in c.fetchall():
    print(row)
# Should see: ('src/index.ts',) NOT ('/Users/...',)
"
```

---

### Phase 2: Stop the Bleeding (Storage Layer)

**Goal:** Ensure whatever is extracted actually gets saved correctly.

#### Task 2.1: Fix CFG Negative ID Bug (CRITICAL)
- **File:** `node_storage.py` -> `_store_cfg_flat`
- **Problem:** CFG blocks get temp negative IDs; statements stored with -1, orphaned
- **Fix:** Flush `cfg_blocks` to DB immediately to get real `lastrowid` before processing statements

```python
# Current (BROKEN):
temp_id = self.db_manager.add_cfg_block(...)  # Returns -1
block_id_map[(func_id, 0)] = temp_id  # Map: 0 -> -1
self.db_manager.add_cfg_statement(real_id, ...)  # Saves with block_id = -1

# Fixed:
cursor = self.db_manager.conn.cursor()
for block in block_batch:
    cursor.execute("INSERT INTO cfg_blocks ...")
    real_id = cursor.lastrowid
    block_id_map[(block['function_id'], block['block_id'])] = real_id
# NOW process statements with real_id
```

#### Task 2.2: Remove Truncation Sabotage
- **File:** `node_database.py:67`
- **Action:** Delete `[:497] + "..."` logic. Store full code.
```python
# DELETE THIS:
if callback_body and len(callback_body) > 500:
    callback_body = callback_body[:497] + "..."
```

#### Task 2.3: Add Artificial IDs for Assignments
- **File:** `core_schema.py`
- **Action:** Add `id INTEGER PRIMARY KEY` to `ASSIGNMENTS`. Update `ASSIGNMENT_SOURCES` to point to `assignment_id`, NOT `file/line/col`

#### Task 2.4: Safe Storage - No Crash on Bad Records
- **File:** `core_storage.py`
- **Action:** Wrap inserts in try/except. Log and `continue` on single record failure. Do not crash worker.
```python
# Add defensive checks:
target_var = assignment.get("target_var") or "unknown_var"
source_expr = assignment.get("source_expr") or "unknown_expr"
```

#### Task 2.5: Implement Partial Success Mode
- **Files:** `main.ts` (TS), `javascript.py` (Python)
- **Action:** Return `partial: true` with whatever data found even on syntax error. Don't discard entire file.

**Verification:**
```bash
aud full --index
# Check CFG integrity
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM cfg_block_statements WHERE block_id < 0')
orphaned = c.fetchone()[0]
print(f'Orphaned statements with negative ID: {orphaned}')
# Should be: 0
"
```

---

### Phase 3: Connect the Tissue (Graph Layer)

**Goal:** Ensure edges are actually created and traversable in both directions.

#### Task 3.1: Fix "Delete-on-Write" Logic (Nuke Bug)
- **File:** `store.py:37-38`
- **Current:**
```python
conn.execute("DELETE FROM nodes WHERE graph_type = ?", (graph_type,))
conn.execute("DELETE FROM edges WHERE graph_type = ?", (graph_type,))
```
- **Action:** Switch to `INSERT OR REPLACE` or scope delete to specific file:
```python
conn.execute("DELETE FROM nodes WHERE file = ? AND graph_type = ?", (file_path, graph_type))
```

#### Task 3.2: Stop Re-parsing Arguments
- **File:** `dfg_builder.py`
- **Action:** Delete `_parse_argument_variable`. Use `arg_type` column from extraction.
- **Problem:** `split(" ")[0]` turns `await getID()` into just `await`

#### Task 3.3: Standardize Edges in `builder.py`
- **File:** `builder.py`
- **Action:** Use `types.create_bidirectional_edges` instead of manual `GraphEdge` creation
- **Why:** IFDS backward analysis queries `_reverse` edges. If missing, returns 0 results.

#### Task 3.4: Fix Fuzzy Controller Resolution
- **File:** `interceptors.py:87-95`
- **Current:** `WHERE name LIKE ?` matches multiple controllers
- **Action:** Require exact match on `ImportSpecifier`. Create `GhostNode` type=`unresolved_controller` if missing.

#### Task 3.5: Add Ghost Nodes for Express
- **File:** `node_express.py`
- **Current:** `continue` on missing symbols breaks API-to-Controller graph
- **Action:** Create `GhostNode` (type=`unresolved_controller`) instead of dropping edge

#### Task 3.6: Fix Memory Bomb in db_cache
- **File:** `db_cache.py:42`
- **Action:** Replace eager loading with `@lru_cache` on `get_imports` method
```python
# Current (OOM):
self.imports_by_file = {}  # Loads ALL imports at startup

# Fixed:
@functools.lru_cache(maxsize=10000)
def get_imports(self, file_path):
    cursor.execute("SELECT ... WHERE file = ?", (file_path,))
    return cursor.fetchall()
```

**Verification:**
```bash
aud graph build
# Check reverse edges exist
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/graphs.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM edges WHERE type LIKE \"%_reverse\"')
print(f'Reverse edges: {c.fetchone()[0]}')
# Should be > 0
"
```

---

### Phase 4: Restore Intelligence (Taint Analysis Layer)

**Goal:** Performance and accuracy in vulnerability detection.

#### Task 4.1: Kill Bidirectional Noise
- **File:** `types.py`
- **Action:** Stop creating `_reverse` edges by default, OR update Taint Engine to explicitly ignore edges where `type` ends in `_reverse`
- **Why:** This causes infinite loops and max_depth timeouts

#### Task 4.2: Fix IFDS Backward Analysis Query
- **File:** `ifds_analyzer.py`
- **Current:**
```python
SELECT target, type, metadata FROM edges
WHERE source = ? AND type LIKE '%_reverse'
```
- **Action:** If using forward-only edges, flip query:
```sql
SELECT source, type, metadata FROM edges
WHERE target = ?  -- Find who points TO me
```

#### Task 4.3: Fix Vulnerability Classification
- **File:** `flow_resolver.py:597`
- **Action:** Replace hardcoded "unknown" with dynamic classification:
```python
def _determine_vuln_type(self, sink_pattern: str, category: str | None) -> str:
    cat_map = {
        "xss": "Cross-Site Scripting (XSS)",
        "sql": "SQL Injection",
        "command": "Command Injection",
        "path": "Path Traversal",
    }
    if category and category in cat_map:
        return cat_map[category]

    lower_pat = sink_pattern.lower()
    if "res.send" in lower_pat or "innerhtml" in lower_pat:
        return "Cross-Site Scripting (XSS)"
    if "query" in lower_pat or "execute" in lower_pat:
        return "SQL Injection"
    if "exec" in lower_pat or "spawn" in lower_pat or "eval" in lower_pat:
        return "Command Injection"
    return "Data Exposure"
```

#### Task 4.4: Fix Sink Line Lookup (UNION Query)
- **File:** `flow_resolver.py`
- **Action:** Query both standard args and JSX args:
```sql
SELECT line FROM function_call_args WHERE ...
UNION ALL
SELECT line FROM function_call_args_jsx WHERE ...
```

#### Task 4.5: Implement Lazy Loading (No Preload OOM)
- **File:** `flow_resolver.py`
- **Action:** Use LRU Cache on `_get_successors`, query SQLite on demand
- **Why:** Preloading 5M edges consumes 10GB+ RAM

#### Task 4.6: Normalize Node IDs
- **Files:** `dfg_builder.py`, `interceptors.py`
- **Action:** Ensure both use identical ID format: `{file}::{function}::{var}`

#### Task 4.7: Prune the Graph Before Analysis
- **Action:** Now that graph is accurate (after Phase 3), "everything connects to everything" problem will disappear
- **Define Sinks:** Populate `sinks` table with React/Node patterns: `dangerouslySetInnerHTML`, `eval`, `child_process.exec`

**Verification:**
```bash
aud taint-analyze --mode forward
# Check vulnerability types
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT vulnerability_type, COUNT(*) FROM resolved_flow_audit GROUP BY vulnerability_type')
for row in c.fetchall():
    print(row)
# Should NOT show: ('unknown', 99116)
"
```

---

## Part 4: Implementation Checklist

### Step 1: Fix Node.js Pathing (CRITICAL - DO FIRST)
- [ ] Modify `main.ts` to output relative paths
- [ ] Rebuild extractor: `cd theauditor/ast_extractors/javascript && npm run build`
- [ ] Verify: `sqlite3 .pf/repo_index.db "SELECT src FROM refs LIMIT 1"` shows `src/index.ts` NOT `/Users/...`

### Step 2: Fix Storage Integrity
- [ ] Fix CFG Negative ID bug in `node_storage.py`
- [ ] Remove truncation in `node_database.py`
- [ ] Add defensive defaults in `core_storage.py`

### Step 3: Fix Graph Edges
- [ ] Fix `store.py` to use incremental updates
- [ ] Modify `builder.py` to use `create_bidirectional_edges`
- [ ] Verify: `sqlite3 .pf/graphs.db "SELECT count(*) FROM edges WHERE type LIKE '%_reverse'"` > 0

### Step 4: Fix Taint Classification
- [ ] Implement dynamic `vulnerability_type` in `flow_resolver.py`
- [ ] Add `UNION` query for sink lines
- [ ] Verify: `sqlite3 .pf/repo_index.db "SELECT vulnerability_type FROM resolved_flow_audit LIMIT 1"` NOT "unknown"

### Step 5: Scale & Optimize
- [ ] Refactor `db_cache.py` to use LRU caching
- [ ] Run on full repo, monitor RAM usage

---

## Part 5: Verification Commands

### Database Integrity Check Script

```python
# save as check_taint_integrity.py
import sqlite3
import os

DB_PATH = ".pf/repo_index.db"
GRAPH_DB_PATH = ".pf/graphs.db"

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"CRITICAL: Repo DB not found at {DB_PATH}")
        return

    print("Checking Databases...")

    # 1. CHECK FILE PATH FORMATS (REPO DB)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n--- [REPO DB] File Path Format Check ---")
    try:
        cursor.execute("SELECT path FROM files LIMIT 5")
        files = [row[0] for row in cursor.fetchall()]
        if not files:
            print("Repo DB is EMPTY (0 files). Extraction failed.")
        else:
            print(f"Sample paths: {files}")
            if os.path.isabs(files[0]):
                print("WARNING: DB uses ABSOLUTE paths. Builder must match.")
            else:
                print("PASS: DB uses RELATIVE paths.")
    except Exception as e:
        print(f"Error reading files: {e}")

    # 2. CHECK CFG INTEGRITY
    print("\n--- [REPO DB] CFG Block Integrity ---")
    try:
        cursor.execute("SELECT COUNT(*) FROM cfg_block_statements WHERE block_id < 0")
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            print(f"FAIL: {orphaned} orphaned statements with negative block_id")
        else:
            print("PASS: No orphaned CFG statements")
    except Exception as e:
        print(f"Error: {e}")

    conn.close()

    # 3. CHECK GRAPH NODES (GRAPH DB)
    if not os.path.exists(GRAPH_DB_PATH):
        print(f"\nGraph DB not found at {GRAPH_DB_PATH}")
        return

    conn = sqlite3.connect(GRAPH_DB_PATH)
    cursor = conn.cursor()

    print("\n--- [GRAPH DB] Node & Edge Counts ---")
    try:
        cursor.execute("SELECT count(*) FROM nodes")
        node_count = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM edges")
        edge_count = cursor.fetchone()[0]

        print(f"Nodes: {node_count}")
        print(f"Edges: {edge_count}")

        if node_count > 0 and edge_count == 0:
            print("FAIL: Nodes exist but NO EDGES. Path mismatch likely.")
        elif node_count == 0:
            print("FAIL: Graph is completely empty.")

        # CHECK REVERSE EDGES
        cursor.execute("SELECT count(*) FROM edges WHERE type LIKE '%_reverse'")
        rev_count = cursor.fetchone()[0]
        print(f"Reverse Edges: {rev_count}")
        if edge_count > 0 and rev_count == 0:
            print("WARNING: No reverse edges. IFDS backward analysis will fail.")
        elif rev_count > 0:
            print("PASS: Reverse edges detected.")

    except Exception as e:
        print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    check_db()
```

---

## Part 6: Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OOM on large repos | HIGH | System crash | Implement LRU caching (Task 3.6, 4.5) |
| False negatives (missed vulns) | HIGH | Security blind spots | Fix path normalization (Phase 1) |
| False positives (noise) | MEDIUM | Developer fatigue | Fix fuzzy matching (Task 3.4) |
| Infinite loops in traversal | HIGH | CPU exhaustion | Kill bidirectional noise (Task 4.1) |
| Data corruption on save | MEDIUM | Data loss | Fix nuke bug (Task 3.1), transaction safety |

---

## Part 7: Success Criteria

After completing all phases:

1. **Path Consistency:** All paths in `repo_index.db` are relative and match filesystem structure
2. **CFG Integrity:** Zero orphaned `cfg_block_statements` with negative `block_id`
3. **Graph Connectivity:** Edge count > 0, reverse edges exist for bidirectional traversal
4. **Vulnerability Classification:** Zero "unknown" vulnerability types in `resolved_flow_audit`
5. **Memory Stability:** No OOM on repos with 50k+ files
6. **Max Depth:** < 5% of flows hitting `max_depth` (down from 99.6%)

---

## Appendix: File Reference Map

| Component | Files |
|-----------|-------|
| **Extraction (Node.js)** | `main.ts`, `schema.ts`, `security_extractors.ts`, `data_flow.ts`, `cfg_extractor.ts`, `module_framework.ts` |
| **Extraction (Python)** | `javascript.py`, `typescript_impl.py`, `javascript_resolvers.py` |
| **Storage** | `node_storage.py`, `core_storage.py`, `node_database.py`, `core_database.py`, `core_schema.py` |
| **Graph** | `builder.py`, `dfg_builder.py`, `store.py`, `types.py`, `db_cache.py` |
| **Strategy** | `node_express.py`, `node_orm.py`, `interceptors.py` |
| **Taint** | `flow_resolver.py`, `ifds_analyzer.py`, `access_path.py`, `discovery.py`, `type_resolver.py` |

---

**Document Status:** Ready for Phase 1 Implementation
**Confidence Level:** High
**Blocking Issues:** None - all information gathered from diagnostic analysis

---

*This document synthesizes findings from comprehensive due diligence analysis of the extraction, storage, graph, and taint layers. Fix order is dependency-driven: upstream fixes (extraction) enable downstream fixes (taint).*
