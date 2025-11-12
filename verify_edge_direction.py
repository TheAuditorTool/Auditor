#!/usr/bin/env python3
"""
Verify that the Data Flow Graph only has forward edges, not backward edges.
This proves why IFDS backward traversal fails.
"""

import sqlite3
import sys
from pathlib import Path

def verify_edge_directionality(graphs_db_path):
    """Check if edges are unidirectional (forward only) or bidirectional."""

    conn = sqlite3.connect(graphs_db_path)
    cursor = conn.cursor()

    print("=" * 80)
    print("EDGE DIRECTIONALITY ANALYSIS")
    print("=" * 80)

    # 1. Total edges
    cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_type = 'data_flow'")
    total_edges = cursor.fetchone()[0]
    print(f"\nTotal edges in data_flow graph: {total_edges:,}")

    # 2. Check for reverse edges
    cursor.execute("SELECT COUNT(*) FROM edges WHERE type LIKE '%_reverse'")
    reverse_edges = cursor.fetchone()[0]
    print(f"Reverse edges (with _reverse suffix): {reverse_edges:,}")

    if reverse_edges == 0:
        print("\n[WARNING] GRAPH IS UNIDIRECTIONAL (Forward Only)")
    else:
        print(f"\n[OK] GRAPH IS BIDIRECTIONAL ({reverse_edges:,} reverse edges)")

    # 3. Check specific patterns - Sources (should have outgoing edges)
    print("\n" + "=" * 40)
    print("SOURCE PATTERNS (User Input):")
    print("=" * 40)

    source_patterns = ['req.body', 'req.params', 'req.query', 'process.env']
    for pattern in source_patterns:
        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE source LIKE ?",
            (f'%{pattern}%',)
        )
        from_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE target LIKE ?",
            (f'%{pattern}%',)
        )
        to_count = cursor.fetchone()[0]

        print(f"{pattern:20} FROM: {from_count:5} edges | TO: {to_count:5} edges")
        if from_count > 0 and to_count == 0:
            print(f"  --> [X] FORWARD ONLY (can't trace back TO {pattern})")

    # 4. Check specific patterns - Sinks (should have incoming edges)
    print("\n" + "=" * 40)
    print("SINK PATTERNS (Database/Response):")
    print("=" * 40)

    sink_patterns = ['create', 'update', 'delete', 'query', 'res.send', 'res.json']
    for pattern in sink_patterns:
        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE source LIKE ?",
            (f'%{pattern}%',)
        )
        from_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE target LIKE ?",
            (f'%{pattern}%',)
        )
        to_count = cursor.fetchone()[0]

        print(f"{pattern:20} FROM: {from_count:5} edges | TO: {to_count:5} edges")
        if to_count == 0:
            print(f"  --> [X] NO INCOMING EDGES (can't trace back FROM {pattern})")

    # 5. Sample actual edges to show directionality
    print("\n" + "=" * 40)
    print("SAMPLE EDGES (First 5):")
    print("=" * 40)

    cursor.execute("""
        SELECT source, target, type
        FROM edges
        WHERE graph_type = 'data_flow'
        LIMIT 5
    """)

    for source, target, edge_type in cursor.fetchall():
        print(f"{edge_type:20} {source[:40]:40} -> {target[:40]}")

    # 6. The smoking gun - can we traverse backward?
    print("\n" + "=" * 40)
    print("BACKWARD TRAVERSAL TEST:")
    print("=" * 40)

    # Find a node that SHOULD be a sink (has 'create' in it)
    cursor.execute("""
        SELECT DISTINCT target
        FROM edges
        WHERE target LIKE '%create%'
        LIMIT 1
    """)
    sample_sink = cursor.fetchone()

    if sample_sink:
        sink_node = sample_sink[0]
        print(f"\nTesting backward traversal from: {sink_node}")

        # Try to find predecessors (this is what IFDS does)
        cursor.execute("""
            SELECT source
            FROM edges
            WHERE target = ?
        """, (sink_node,))

        predecessors = cursor.fetchall()
        if predecessors:
            print(f"  [OK] Found {len(predecessors)} predecessors")
            for pred in predecessors[:3]:
                print(f"    <- {pred[0]}")
        else:
            print(f"  [X] NO PREDECESSORS FOUND (backward traversal impossible)")
    else:
        # No sink nodes exist as targets, try a different approach
        cursor.execute("""
            SELECT DISTINCT source
            FROM edges
            WHERE source LIKE '%create%'
            LIMIT 1
        """)
        sample_source = cursor.fetchone()
        if sample_source:
            source_node = sample_source[0]
            print(f"\nFound node with 'create': {source_node}")
            print("  But it's a SOURCE, not a TARGET (can't trace backward TO it)")

    print("\n" + "=" * 80)
    print("CONCLUSION:")
    print("=" * 80)

    if reverse_edges == 0:
        print("""
[X] The Data Flow Graph is UNIDIRECTIONAL (forward only).
   - Sources (req.body) have outgoing edges but no incoming edges
   - Sinks (database ops) appear as sources, not targets
   - Backward traversal is IMPOSSIBLE without reverse edges

   SOLUTION: Add reverse edges for every forward edge in dfg_builder.py
        """)
    else:
        print("""
[OK] The Data Flow Graph has bidirectional edges.
   Backward traversal should work!
        """)

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default to Plant project
        db_path = "C:/Users/santa/Desktop/Plant/.pf/graphs.db"

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        sys.exit(1)

    verify_edge_directionality(db_path)