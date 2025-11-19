# Bidirectional Edges Implementation Plan

## 1. THE EVIDENCE (From Actual Database Queries)

### Current State - UNIDIRECTIONAL Forward Edges Only
```sql
-- Plant project database queries show:
SELECT COUNT(*) FROM edges WHERE source LIKE '%req.body%';  -- 418 edges FROM req.body
SELECT COUNT(*) FROM edges WHERE target LIKE '%req.body%';  -- 0 edges TO req.body

SELECT COUNT(*) FROM edges WHERE target LIKE '%create%';    -- 0 edges TO any sink
SELECT COUNT(*) FROM edges WHERE target LIKE '%update%';    -- 0 edges TO any sink
```

### The Broken Backward Traversal
```python
# ifds_analyzer.py line 254 - THIS RETURNS EMPTY
def _get_predecessors(self, current_ap: AccessPath) -> List[AccessPath]:
    cursor.execute("""
        SELECT DISTINCT source FROM edges
        WHERE target = ?  -- NO EDGES HAVE SINKS AS TARGETS!
    """, (current_ap.node_id,))
    # Returns [] because graph is forward-only
```

## 2. THE SOLUTION - Newton's Third Law for Data Flow

**For every forward edge, create an equal and opposite reverse edge.**

### Core Implementation in dfg_builder.py

```python
def _add_edge_bidirectional(self, source_id: str, target_id: str,
                           edge_type: str, metadata: Dict):
    """Helper to add both forward and reverse edges."""
    edges = []

    # 1. Forward edge (existing logic)
    forward_edge = DFGEdge(
        source=source_id,
        target=target_id,
        type=edge_type,
        file=metadata.get('file'),
        line=metadata.get('line'),
        expression=metadata.get('expression', ''),
        function=metadata.get('function', 'global'),
        metadata=metadata
    )
    edges.append(forward_edge)

    # 2. Reverse edge (NEW)
    reverse_edge = DFGEdge(
        source=target_id,  # Swapped
        target=source_id,  # Swapped
        type=f"{edge_type}_reverse",
        file=metadata.get('file'),
        line=metadata.get('line'),
        expression=f"REV: {metadata.get('expression', '')[:190]}",
        function=metadata.get('function', 'global'),
        metadata={**metadata, 'is_reverse': True}
    )
    edges.append(reverse_edge)

    return edges
```

## 3. APPLY TO ALL EDGE CREATION METHODS

### A. build_assignment_flow_graph (line ~89)
```python
# BEFORE (line 134-145)
edge = DFGEdge(
    source=source_id,
    target=target_id,
    type="assignment",
    file=file,
    line=line,
    expression=source_expr[:200] if source_expr else "",
    function=in_function if in_function else "global",
    metadata={}
)
edges.append(edge)

# AFTER
edges.extend(self._add_edge_bidirectional(
    source_id, target_id, "assignment",
    {'file': file, 'line': line, 'expression': source_expr, 'function': in_function}
))
```

### B. build_return_flow_graph (line ~189)
```python
# BEFORE (line 234-243)
edge = DFGEdge(
    source=var_id,
    target=return_id,
    type="return",
    file=file,
    line=line,
    expression=return_expr[:200] if return_expr else "",
    function=function_name,
    metadata={}
)
edges.append(edge)

# AFTER
edges.extend(self._add_edge_bidirectional(
    var_id, return_id, "return",
    {'file': file, 'line': line, 'expression': return_expr, 'function': function_name}
))
```

### C. build_parameter_binding_edges (line ~299) - MOST CRITICAL
```python
# BEFORE (line 449-463) - This is where req.body connections are made!
edge = DFGEdge(
    source=source_id,
    target=target_id,
    type="parameter_binding",
    file=caller_file,
    line=line,
    expression=f"{callee_function}({argument_expr})",
    function=caller_function,
    metadata={
        "callee": callee_function,
        "param_name": param_name,
        "arg_expr": argument_expr
    }
)
edges.append(edge)

# AFTER
edges.extend(self._add_edge_bidirectional(
    source_id, target_id, "parameter_binding",
    {
        'file': caller_file,
        'line': line,
        'expression': f"{callee_function}({argument_expr})",
        'function': caller_function,
        'callee': callee_function,
        'param_name': param_name,
        'arg_expr': argument_expr
    }
))
```

### D. build_cross_boundary_edges (line ~500)
```python
# Apply same pattern to API boundaries
edges.extend(self._add_edge_bidirectional(
    source_id, target_id, "cross_boundary",
    metadata_dict
))
```

### E. build_express_middleware_edges (line ~724)
```python
# Apply to Express middleware chains
edges.extend(self._add_edge_bidirectional(
    req_body_id, handler_param_id, "middleware_chain",
    metadata_dict
))
```

## 4. UPDATE IFDS TO USE REVERSE EDGES

### Modify _get_predecessors in ifds_analyzer.py
```python
def _get_predecessors(self, current_ap: AccessPath) -> List[AccessPath]:
    """Get predecessors using REVERSE edges."""
    cursor = self.graph_conn.cursor()

    # Use reverse edges for backward traversal
    cursor.execute("""
        SELECT DISTINCT source
        FROM edges
        WHERE target = ?
          AND type LIKE '%_reverse'
        ORDER BY source
    """, (current_ap.node_id,))

    results = cursor.fetchall()
    predecessors = []

    for (source_id,) in results:
        pred_ap = AccessPath.parse(source_id)
        if pred_ap:
            predecessors.append(pred_ap)

    if self.debug and predecessors:
        print(f"[IFDS] Found {len(predecessors)} predecessors for {current_ap.node_id}")

    return predecessors
```

## 5. EXPECTED RESULTS

### Before Fix
```
edges table: 78,780 rows (forward only)
Taint paths found: 0
IFDS runtime: 4.7s (gives up immediately)
```

### After Fix
```
edges table: ~157,560 rows (78,780 forward + 78,780 reverse)
Taint paths found: Many (175 sources × 275 sinks potential)
IFDS runtime: Longer but actually working
```

## 6. TESTING PLAN

### Step 1: Apply Changes
```bash
# Edit dfg_builder.py with bidirectional edge creation
# Edit ifds_analyzer.py to use reverse edges
```

### Step 2: Rebuild Plant Project
```bash
cd C:/Users/santa/Desktop/Plant
aud full --offline
```

### Step 3: Verify Bidirectional Edges
```python
# Check that reverse edges exist
import sqlite3
conn = sqlite3.connect('.pf/graphs.db')
cursor = conn.cursor()

# Should return ~78,780
cursor.execute("SELECT COUNT(*) FROM edges WHERE type LIKE '%_reverse'")
print(f"Reverse edges: {cursor.fetchone()[0]}")

# Should return >0 for sinks
cursor.execute("SELECT COUNT(*) FROM edges WHERE target LIKE '%create%' AND type LIKE '%_reverse'")
print(f"Edges TO create sinks: {cursor.fetchone()[0]}")
```

### Step 4: Run Taint Analysis
```bash
aud taint
# Should now find taint paths!
```

## 7. WHY THIS IS THE CORRECT SOLUTION

1. **Empirically Proven**: Database queries show 0 backward edges exist
2. **Architecturally Sound**: Supports both forward (flow_resolver) and backward (ifds_analyzer) engines
3. **Oracle Paper Compliant**: Enables demand-driven backward analysis as described
4. **Minimal Changes**: Just add reverse edges, no complex refactoring
5. **Both Engines Work**: Forward uses normal edges, backward uses _reverse edges

## The Other AI's "Node Snapping" - Why It's Wrong

The other AI suggested the problem is "discovery finds sinks that don't match graph nodes". This is **incorrect** because:
- The nodes DO exist (we verified 56,222 nodes in the graph)
- The sink nodes ARE in the graph
- The problem is NO EDGES point TO these nodes for backward traversal

Even with perfect "node snapping", you can't traverse backward on a forward-only graph.

## CONCLUSION

We were right 7 hours ago. The solution is bidirectional edges. This plan shows exactly where and how to implement them based on the actual source code.