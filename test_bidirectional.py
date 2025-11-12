#!/usr/bin/env python3
"""
Test script to verify bidirectional edges were created correctly.
"""

import sqlite3
import sys
from pathlib import Path

def test_bidirectional_edges(graphs_db_path):
    """Check if bidirectional edges were created."""

    conn = sqlite3.connect(graphs_db_path)
    cursor = conn.cursor()

    print("=" * 80)
    print("BIDIRECTIONAL EDGE VERIFICATION")
    print("=" * 80)

    # 1. Count total edges
    cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_type = 'data_flow'")
    total_edges = cursor.fetchone()[0]
    print(f"\nTotal data_flow edges: {total_edges:,}")

    # 2. Count reverse edges
    cursor.execute("SELECT COUNT(*) FROM edges WHERE type LIKE '%_reverse'")
    reverse_edges = cursor.fetchone()[0]
    print(f"Reverse edges: {reverse_edges:,}")

    # 3. Count forward edges (non-reverse)
    cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_type = 'data_flow' AND type NOT LIKE '%_reverse'")
    forward_edges = cursor.fetchone()[0]
    print(f"Forward edges: {forward_edges:,}")

    # 4. Check ratio
    if forward_edges > 0:
        ratio = reverse_edges / forward_edges
        print(f"\nRatio (reverse/forward): {ratio:.2f}")
        if ratio > 0.95 and ratio < 1.05:
            print("[OK] Graph appears to be bidirectional (1:1 ratio)")
        else:
            print(f"[WARNING] Unexpected ratio - should be close to 1.0")

    # 5. Test backward traversal capability
    print("\n" + "=" * 40)
    print("BACKWARD TRAVERSAL TEST:")
    print("=" * 40)

    # Find a sink node (something with 'create' in it)
    cursor.execute("""
        SELECT DISTINCT source
        FROM edges
        WHERE source LIKE '%create%'
          AND type LIKE '%_reverse'
        LIMIT 1
    """)

    sample_sink = cursor.fetchone()
    if sample_sink:
        sink_node = sample_sink[0]
        print(f"\nTesting backward traversal from: {sink_node[:80]}")

        # Find predecessors using reverse edges
        cursor.execute("""
            SELECT target
            FROM edges
            WHERE source = ?
              AND type LIKE '%_reverse'
            LIMIT 5
        """, (sink_node,))

        predecessors = cursor.fetchall()
        if predecessors:
            print(f"  [OK] Found {len(predecessors)} predecessors via reverse edges:")
            for pred in predecessors:
                print(f"    <- {pred[0][:70]}")
        else:
            print(f"  [X] No predecessors found even with reverse edges")
    else:
        print("  [INFO] No sink nodes with reverse edges found yet")

    # 6. Check specific patterns
    print("\n" + "=" * 40)
    print("KEY PATTERNS:")
    print("=" * 40)

    patterns = ['req.body', 'req.params', 'create', 'update']
    for pattern in patterns:
        # Check forward edges FROM pattern
        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE source LIKE ? AND type NOT LIKE '%_reverse'",
            (f'%{pattern}%',)
        )
        from_forward = cursor.fetchone()[0]

        # Check reverse edges TO pattern (source->target swapped)
        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE target LIKE ? AND type LIKE '%_reverse'",
            (f'%{pattern}%',)
        )
        to_reverse = cursor.fetchone()[0]

        print(f"{pattern:15} Forward FROM: {from_forward:5} | Reverse TO: {to_reverse:5}")

    print("\n" + "=" * 80)

    if reverse_edges > 0 and reverse_edges >= forward_edges * 0.95:
        print("SUCCESS: Bidirectional edges implemented correctly!")
        print(f"  - {forward_edges:,} forward edges")
        print(f"  - {reverse_edges:,} reverse edges")
        print("  - Backward traversal now possible")
        return True
    else:
        print("FAILURE: Bidirectional edges not fully implemented")
        print(f"  - Expected ~{forward_edges:,} reverse edges")
        print(f"  - Found only {reverse_edges:,} reverse edges")
        return False

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "C:/Users/santa/Desktop/Plant/.pf/graphs.db"

    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        print("Waiting for rebuild to complete...")
        sys.exit(1)

    success = test_bidirectional_edges(db_path)
    sys.exit(0 if success else 1)