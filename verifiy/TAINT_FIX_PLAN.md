# Taint Analysis Fix Plan - Bidirectional DFG

## Problem Summary
TheAuditor has two taint analysis engines that serve different purposes:
1. **flow_resolver.py** - Forward traversal for complete codebase truth (WORKS)
2. **ifds_analyzer.py** - Backward traversal for security analysis (BROKEN)

The DFG only has forward edges, making backward traversal impossible.

## Root Cause
- Data Flow Graph has 78,780 FORWARD edges only
- IFDS needs BACKWARD edges to trace from sinks to sources
- `_get_predecessors()` returns empty because no edges point TO sinks

## The Fix: Bidirectional Edge Creation

### Option 1: Add Reverse Edges (Recommended)
Modify `theauditor/graph/dfg_builder.py` to create reverse edges:

```python
def _add_bidirectional_edge(self, source: str, target: str, edge_type: str):
    """Add both forward and backward edges for bidirectional traversal."""
    cursor = self.graph_conn.cursor()

    # Forward edge (existing)
    cursor.execute("""
        INSERT INTO edges (graph_type, source, target, type, metadata)
        VALUES ('data_flow', ?, ?, ?, ?)
    """, (source, target, edge_type, None))

    # Backward edge (NEW)
    cursor.execute("""
        INSERT INTO edges (graph_type, source, target, type, metadata)
        VALUES ('data_flow', ?, ?, ?, ?)
    """, (target, source, f"{edge_type}_reverse", None))
```

Then update IFDS to filter reverse edges:
```python
def _get_predecessors(self, node_id: str) -> List[str]:
    cursor = self.graph_conn.cursor()
    cursor.execute("""
        SELECT DISTINCT source FROM edges
        WHERE graph_type = 'data_flow'
          AND target = ?
          AND type LIKE '%_reverse'
    """, (node_id,))
    return [row[0] for row in cursor.fetchall()]
```

### Option 2: Separate Forward/Backward Tables
Create dedicated tables:
- `edges_forward` - for flow_resolver.py
- `edges_backward` - for ifds_analyzer.py

### Option 3: Restore Old CFG Analyzer
Bring back `analysis.py.backup` which used Control Flow Graph and worked.

## Implementation Steps

1. **Modify DFG Builder** (dfg_builder.py)
   - Update all edge creation to be bidirectional
   - Add ~78,000 reverse edges to match forward edges

2. **Update IFDS Analyzer** (ifds_analyzer.py)
   - Modify `_get_predecessors()` to use reverse edges
   - Remove the "no predecessors found" early exit

3. **Test with Plant Project**
   - Run `aud full` to rebuild with bidirectional edges
   - Verify IFDS can now trace backward from sinks
   - Should find 175 sources × 275 sinks = potential paths

## Expected Outcome

After fix:
- Forward flow_resolver.py continues working (ignores reverse edges)
- Backward ifds_analyzer.py can finally traverse (uses reverse edges)
- Both engines populate their respective tables:
  - `resolved_flow_audit` - complete codebase flows
  - `taint_flows` - security vulnerabilities only

## Why This Architecture Makes Sense

1. **Complete Truth** (forward) - Maps everything for AI queries
2. **Targeted Security** (backward) - Efficient vulnerability detection
3. **Complementary** - Forward builds the map, backward analyzes threats

The Oracle research paper confirms backward analysis is more scalable for security (O(CallD³ + 2ED²) vs O(ED³)).