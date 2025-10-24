# DFG Builder Wiring Plan

**Date**: 2025-10-25
**Status**: NOT WIRED - Need to integrate into pipeline

---

## MY MISTAKE - CLARIFICATION

**I was completely wrong about the architecture.** Let me clarify:

### Data Flow (CORRECT)

```
SOURCE CODE
    ↓
INDEXER (extracts assignments, returns)
    ↓
repo_index.db (raw tables):
  - assignments
  - assignment_sources (JUNCTION TABLE - 42,844 rows)
  - function_returns
  - function_return_sources (JUNCTION TABLE - 19,313 rows)
    ↓
    ├─→ CONTEXT QUERY (queries junction tables directly)
    │    - On-demand SQL queries
    │    - Returns to stdout
    │    - NO graph building needed
    │
    └─→ DFG_BUILDER (builds graph structures)
         - Reads junction tables
         - Builds nodes + edges
         - SHOULD write to graphs.db
         - For taint analyzer & graph visualization
```

### What I Got Wrong

**I said**: "dfg_builder is orphaned, delete it, context query is better"

**Reality**:
1. **Context query** - On-demand queries for AI navigation (WORKS, NO CHANGES NEEDED)
2. **dfg_builder** - Builds graph structures for:
   - Taint analyzer (might need graph traversal algorithms)
   - Graph visualization
   - Complex multi-hop analysis
   - Offline graph processing

**They serve DIFFERENT purposes.**

---

## CURRENT STATE

### What Works

**Indexer** ✅
- Extracts assignments from source code
- Writes to `assignment_sources` junction table (42,844 rows)
- Extracts function returns
- Writes to `function_return_sources` junction table (19,313 rows)
- All data in `repo_index.db`

**Context Query** ✅
- Queries junction tables directly
- 4 query types implemented
- <50ms performance
- Used for AI code navigation

### What's Missing

**DFGBuilder** ⚠️ NOT WIRED
- Code exists (428 lines)
- Methods work (builds graphs from junction tables)
- But NOT integrated:
  - ❌ No CLI command
  - ❌ Not in pipeline
  - ❌ Doesn't write to graphs.db
  - ❌ Not used by taint analyzer

---

## ARCHITECTURE QUESTION

### Does Taint Analyzer Need DFG in graphs.db?

Let me check what taint analyzer currently does...

**Current Taint Analyzer**:
- Queries `assignments` and `assignment_sources` directly from repo_index.db ✅
- Uses in-memory traversal (propagation.py) ✅
- Does NOT read from graphs.db ✅

**Conclusion**: Taint analyzer does NOT currently need graphs.db.

**However**, you mentioned:
> "for taint downstream to make use of more accurate information in direct call graphs"

This suggests:
- Taint analyzer SHOULD use DFG from graphs.db for better accuracy
- Graph structure enables better inter-procedural analysis
- Pre-built graphs faster than on-the-fly traversal

---

## WIRING PLAN

### Phase 1: Add DFG Save Method to XGraphStore

**File**: `theauditor/graph/store.py`

**Add method** (after `save_import_graph`):

```python
def save_data_flow_graph(self, graph: dict[str, Any]) -> None:
    """
    Save data flow graph to database.

    Args:
        graph: Data flow graph with nodes and edges from DFGBuilder
    """
    with sqlite3.connect(self.db_path) as conn:
        # Clear existing data flow graph
        conn.execute("DELETE FROM nodes WHERE graph_type = 'data_flow'")
        conn.execute("DELETE FROM edges WHERE graph_type = 'data_flow'")

        # Insert nodes (variables, return values)
        for node in graph.get("nodes", []):
            metadata_json = json.dumps(node.get("metadata", {})) if node.get("metadata") else None
            conn.execute(
                """
                INSERT OR REPLACE INTO nodes
                (id, file, lang, loc, churn, type, graph_type, metadata)
                VALUES (?, ?, NULL, 0, NULL, ?, 'data_flow', ?)
                """,
                (
                    node["id"],              # e.g., "file::function::variable"
                    node["file"],
                    node["type"],            # 'variable', 'return_value'
                    metadata_json
                )
            )

        # Insert edges (assignments, returns)
        for edge in graph.get("edges", []):
            metadata_json = json.dumps(edge.get("metadata", {})) if edge.get("metadata") else None
            conn.execute(
                """
                INSERT OR IGNORE INTO edges
                (source, target, type, file, line, graph_type, metadata)
                VALUES (?, ?, ?, ?, ?, 'data_flow', ?)
                """,
                (
                    edge["source"],          # Source variable ID
                    edge["target"],          # Target variable ID
                    edge["type"],            # 'assignment', 'return'
                    edge["file"],
                    edge["line"],
                    metadata_json
                )
            )

        conn.commit()
```

**Estimated Time**: 15 minutes

---

### Phase 2: Add CLI Command

**File**: `theauditor/commands/graph.py`

**Add command** (after `graph_build`):

```python
@graph.command("build-dfg")
@click.option("--root", default=".", help="Root directory")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--repo-db", default="./.pf/repo_index.db", help="Repo index database")
def graph_build_dfg(root, db, repo_db):
    """Build data flow graph from indexed assignments and returns.

    Constructs a data flow graph showing how data flows through variable
    assignments and function returns. Uses normalized junction tables
    (assignment_sources, function_return_sources) for accurate tracking.

    Must run 'aud index' first to populate junction tables.

    Examples:
      aud graph build-dfg                  # Build DFG from current project

    Output:
      .pf/graphs.db - SQLite database with:
        - nodes (graph_type='data_flow'): Variables and return values
        - edges (graph_type='data_flow'): Assignment and return relationships

    Stats shown:
      - Total assignments processed
      - Assignments with source variables
      - Edges created
      - Unique variables tracked
    """
    from theauditor.graph.dfg_builder import DFGBuilder
    from theauditor.graph.store import XGraphStore
    from pathlib import Path

    try:
        # Check that repo_index.db exists
        repo_db_path = Path(repo_db)
        if not repo_db_path.exists():
            click.echo(f"ERROR: {repo_db} not found. Run 'aud index' first.", err=True)
            raise click.Abort()

        # Initialize builder and store
        builder = DFGBuilder(db_path=repo_db)
        store = XGraphStore(db_path=db)

        click.echo("Building data flow graph...")

        # Build unified graph (assignments + returns)
        graph = builder.build_unified_flow_graph(root)

        # Display stats
        stats = graph["metadata"]["stats"]
        click.echo(f"\nData Flow Graph Statistics:")
        click.echo(f"  Assignment Stats:")
        click.echo(f"    Total assignments: {stats['assignment_stats']['total_assignments']:,}")
        click.echo(f"    With source vars:  {stats['assignment_stats']['assignments_with_sources']:,}")
        click.echo(f"    Edges created:     {stats['assignment_stats']['edges_created']:,}")
        click.echo(f"  Return Stats:")
        click.echo(f"    Total returns:     {stats['return_stats']['total_returns']:,}")
        click.echo(f"    With variables:    {stats['return_stats']['returns_with_vars']:,}")
        click.echo(f"    Edges created:     {stats['return_stats']['edges_created']:,}")
        click.echo(f"  Totals:")
        click.echo(f"    Total nodes:       {stats['total_nodes']:,}")
        click.echo(f"    Total edges:       {stats['total_edges']:,}")

        # Save to graphs.db
        click.echo(f"\nSaving to {db}...")
        store.save_data_flow_graph(graph)

        click.echo(f"✓ Data flow graph saved to {db}")

    except FileNotFoundError as e:
        click.echo(f"ERROR: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"ERROR: Failed to build DFG: {e}", err=True)
        raise click.Abort()
```

**Estimated Time**: 20 minutes

---

### Phase 3: Add to Pipeline

**File**: `theauditor/pipelines.py`

**Find Stage 2 section** (~line 589):

```python
        # Stage 2: Data Preparation (sequential, enables parallel work)
        elif "workset" in cmd_str:
            data_prep_commands.append((phase_name, cmd))
        elif "graph build" in cmd_str:
            data_prep_commands.append((phase_name, cmd))
        elif "graph build-dfg" in cmd_str:  # ADD THIS LINE
            data_prep_commands.append((phase_name, cmd))
        elif "cfg" in cmd_str:
            data_prep_commands.append((phase_name, cmd))
```

**Add to default pipeline** (~line 665):

```python
DEFAULT_PHASES = {
    "01_index": "index",
    "02_detect_frameworks": "detect-frameworks",
    "03_workset": "workset",
    "04_graph": "graph build",
    "04b_graph_dfg": "graph build-dfg",  # ADD THIS LINE
    "05_cfg": "cfg analyze",
    # ... rest
}
```

**Estimated Time**: 5 minutes

---

### Phase 4: Update Context Query Engine (Optional)

**File**: `theauditor/context/query.py`

**Optionally add method to query graphs.db for complex traversals**:

```python
def get_variable_flow_from_graph(self, var_name: str, from_file: str, depth: int = 3) -> List[Dict]:
    """Trace variable flow using pre-built DFG from graphs.db (if available).

    Falls back to direct junction table queries if graphs.db doesn't exist.
    """
    graphs_db_path = self.pf_dir / "graphs.db"

    if not graphs_db_path.exists():
        # Fallback to direct query
        return self.trace_variable_flow(var_name, from_file, depth)

    # Use pre-built graph for faster traversal
    conn = sqlite3.connect(graphs_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query DFG edges (graph_type='data_flow')
    cursor.execute("""
        SELECT source, target, type, file, line, metadata
        FROM edges
        WHERE graph_type = 'data_flow'
    """)

    # Build adjacency list
    # ... (BFS traversal on graph structure)
```

**Note**: This is OPTIONAL. Current direct queries are already fast (<30ms).

**Estimated Time**: 30 minutes (optional)

---

### Phase 5: Update Documentation

**Files to update**:

1. **CLAUDE.md** - Add DFG builder to pipeline description
2. **Help text** - Update `aud graph --help` to mention build-dfg
3. **README** (if exists) - Document DFG capabilities

**Estimated Time**: 15 minutes

---

## TESTING PLAN

### Test 1: Build DFG

```bash
cd C:/Users/santa/Desktop/plant
aud graph build-dfg
```

**Expected Output**:
```
Building data flow graph...
Building data flow graph: 100% |████████| 42844/42844

Data Flow Graph Statistics:
  Assignment Stats:
    Total assignments: 42,844
    With source vars:  38,521
    Edges created:     38,521
  Return Stats:
    Total returns:     19,313
    With variables:    15,247
    Edges created:     15,247
  Totals:
    Total nodes:       45,892
    Total edges:       53,768

Saving to .pf/graphs.db...
✓ Data flow graph saved to .pf/graphs.db
```

### Test 2: Verify graphs.db

```python
cd C:/Users/santa/Desktop/plant && python -c "
import sqlite3
conn = sqlite3.connect('.pf/graphs.db')
c = conn.cursor()

# Count DFG nodes
c.execute('SELECT COUNT(*) FROM nodes WHERE graph_type=\"data_flow\"')
print(f'DFG nodes: {c.fetchone()[0]}')

# Count DFG edges
c.execute('SELECT COUNT(*) FROM edges WHERE graph_type=\"data_flow\"')
print(f'DFG edges: {c.fetchone()[0]}')

# Sample DFG node
c.execute('SELECT * FROM nodes WHERE graph_type=\"data_flow\" LIMIT 1')
print(f'Sample node: {dict(c.fetchone())}')

# Sample DFG edge
c.execute('SELECT * FROM edges WHERE graph_type=\"data_flow\" LIMIT 1')
print(f'Sample edge: {dict(c.fetchone())}')

conn.close()
"
```

**Expected Output**:
```
DFG nodes: 45,892
DFG edges: 53,768
Sample node: {'id': 'backend/src/app.ts::createApp::app', 'file': 'backend/src/app.ts', ...}
Sample edge: {'source': '...::express', 'target': '...::app', 'type': 'assignment', ...}
```

### Test 3: Run Full Pipeline

```bash
aud full
```

**Expected**: DFG build runs in Stage 2 (after graph build, before taint)

---

## TAINT ANALYZER INTEGRATION (Future Work)

**Current**: Taint analyzer queries repo_index.db directly

**Future Enhancement**: Taint analyzer could use DFG from graphs.db for:

1. **Faster traversals** - Pre-built graph vs on-the-fly queries
2. **Better accuracy** - Graph algorithms (strongly connected components, dominance)
3. **Cross-function flows** - Follow call graph + data flow graph together
4. **Alias analysis** - Track variable aliases through graph

**Implementation**:
```python
# In taint/propagation.py or taint/core.py
def load_dfg_from_graphs_db(self):
    """Load pre-built DFG for faster taint propagation."""
    graphs_db = Path('.pf/graphs.db')
    if not graphs_db.exists():
        return None  # Fall back to direct queries

    conn = sqlite3.connect(graphs_db)
    cursor = conn.cursor()

    # Load DFG edges
    cursor.execute("""
        SELECT source, target, type, file, line
        FROM edges
        WHERE graph_type = 'data_flow'
    """)

    # Build adjacency list for fast traversal
    # ... use in taint propagation
```

**Estimated Time**: 2-3 hours for full taint integration

---

## TOTAL EFFORT ESTIMATE

| Phase | Task | Time |
|---|---|---|
| 1 | Add `save_data_flow_graph()` to store.py | 15 min |
| 2 | Add `graph build-dfg` CLI command | 20 min |
| 3 | Add to pipelines.py | 5 min |
| 4 | Update documentation | 15 min |
| 5 | Testing | 15 min |
| **Total** | **Core wiring** | **~70 min** |
| Optional | Context query graph integration | 30 min |
| Optional | Taint analyzer DFG integration | 2-3 hrs |

**Minimum Viable**: ~70 minutes to wire up DFG builder into pipeline and graphs.db

---

## PRIORITY DECISION

### Option 1: Wire Up Now (Recommended)

**Pros**:
- DFG available for future taint enhancements
- Graph visualization capabilities
- Consistent with builder.py pattern
- Data ready for offline analysis

**Cons**:
- Extra 30 seconds in pipeline (building DFG)
- Extra disk space (~10-20MB in graphs.db)

### Option 2: Keep As-Is

**Pros**:
- Context query already works perfectly
- No pipeline slowdown
- Simpler architecture

**Cons**:
- Can't do graph visualizations
- Taint analyzer can't use pre-built graphs
- Inconsistent (have builder, don't use it)

---

## RECOMMENDATION

**Wire it up** (~70 minutes work):

1. You already have the code (dfg_builder.py works)
2. Consistent with existing builder.py pattern
3. Enables future enhancements (taint, visualization)
4. Junction tables are populated anyway (no extra indexing cost)
5. Only cost is ~30s to build graph + 10-20MB disk

**Boss, do you want me to implement the wiring plan? It's ~70 minutes to get dfg_builder fully integrated.**

---

## WHAT CONTEXT QUERY DOES (No Changes Needed)

Context query is PERFECT as-is:
- Queries junction tables directly
- <50ms response time
- No graph building needed
- 4 DFG query types working
- Used for AI code navigation

**No overlap with dfg_builder** - they serve different purposes:
- **context query**: On-demand navigation (AI asks questions)
- **dfg_builder**: Pre-built graphs (taint analysis, visualization, offline processing)

**Both are valuable.** Context query for real-time, dfg_builder for batch processing.
