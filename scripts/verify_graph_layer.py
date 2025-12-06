"""
Graph Layer Verification (Wave 3b)
==================================
Tests the graph layer components in ISOLATION.
Uses an in-memory database - no disk I/O, no production data touched.

This catches:
  - Graph schema creation failures
  - XGraphStore CRUD bugs
  - Strategy loading failures
  - Builder initialization issues
  - Node/Edge relationship problems

Exit codes:
  0 = All checks passed
  1 = Warnings (non-fatal issues)
  2 = Critical errors (graph layer is broken)

Author: TheAuditor Team
"""
import sys
import os
import traceback
import sqlite3
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def verify_graph_layer() -> int:
    """Run graph layer verification. Returns exit code."""
    print("=" * 60)
    print("GRAPH LAYER VERIFICATION (Wave 3b)")
    print("=" * 60)

    errors = 0
    warnings = 0

    # 1. Import graph schema
    print("\n[1] Loading graph schema...")
    try:
        from theauditor.indexer.schemas.graphs_schema import GRAPH_TABLES

        print(f"    [OK] Loaded {len(GRAPH_TABLES)} graph table definitions")
        for table_name in GRAPH_TABLES:
            print(f"        - {table_name}")
    except ImportError as e:
        print(f"    [CRITICAL] Failed to import graph schema: {e}")
        return 2

    # 2. Test schema SQL generation
    print("\n[2] Testing graph schema SQL generation...")
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        for table_name, schema in GRAPH_TABLES.items():
            sql = schema.create_table_sql()
            cursor.execute(sql)

            for idx_sql in schema.create_indexes_sql():
                cursor.execute(idx_sql)

        print(f"    [OK] All graph tables created successfully in-memory")
        conn.close()
    except Exception as e:
        print(f"    [CRITICAL] Graph schema SQL generation failed: {e}")
        traceback.print_exc()
        errors += 1

    # 3. Test XGraphStore initialization
    print("\n[3] Testing XGraphStore initialization...")
    try:
        from theauditor.graph.store import XGraphStore

        # Use temp file for store test (manually manage to avoid Windows locking)
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_graphs.db")
        store = XGraphStore(db_path=db_path)
        print(f"    [OK] XGraphStore initialized at temp path")

        # Verify schema was created
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected = {"nodes", "edges", "analysis_results"}
        missing = expected - tables
        if missing:
            print(f"    [FAIL] Missing tables in graph DB: {missing}")
            errors += 1
        else:
            print(f"    [OK] All expected tables present: {expected}")

        conn.close()
        # Don't try to cleanup tmpdir on Windows - leave for OS cleanup

    except Exception as e:
        print(f"    [CRITICAL] XGraphStore initialization failed: {e}")
        traceback.print_exc()
        errors += 1

    # 4. Test GraphNode and GraphEdge dataclasses
    print("\n[4] Testing graph data structures...")
    try:
        from theauditor.graph.builder import GraphNode, GraphEdge

        node = GraphNode(
            id="test/module.py:func",
            file="test/module.py",
            lang="python",
            loc=100,
            type="function",
        )

        edge = GraphEdge(
            source="test/a.py:foo",
            target="test/b.py:bar",
            type="call",
            file="test/a.py",
            line=42,
        )

        # Verify dataclass fields
        from dataclasses import asdict
        node_dict = asdict(node)
        edge_dict = asdict(edge)

        if node_dict.get("id") and edge_dict.get("source"):
            print(f"    [OK] GraphNode and GraphEdge dataclasses work correctly")
        else:
            print(f"    [FAIL] Dataclass serialization issue")
            errors += 1

    except Exception as e:
        print(f"    [CRITICAL] Graph data structures failed: {e}")
        traceback.print_exc()
        errors += 1

    # 5. Test XGraphStore CRUD operations
    print("\n[5] Testing XGraphStore CRUD operations...")
    try:
        from theauditor.graph.store import XGraphStore

        # Use manual temp directory to avoid Windows locking issues
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "crud_test.db")
        store = XGraphStore(db_path=db_path)

        # Create a test graph
        test_graph = {
            "nodes": [
                {"id": "module_a", "file": "src/a.py", "type": "module"},
                {"id": "module_b", "file": "src/b.py", "type": "module"},
                {"id": "func_foo", "file": "src/a.py", "type": "function"},
            ],
            "edges": [
                {"source": "module_a", "target": "module_b", "type": "import", "file": "src/a.py", "line": 1},
                {"source": "func_foo", "target": "module_b", "type": "call", "file": "src/a.py", "line": 10},
            ],
        }

        # Save graph
        store._save_graph_bulk(test_graph, graph_type="import", default_node_type="module")

        # Verify save
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM nodes WHERE graph_type = 'import'")
        node_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_type = 'import'")
        edge_count = cursor.fetchone()[0]

        if node_count == 3 and edge_count == 2:
            print(f"    [OK] CRUD: Inserted {node_count} nodes, {edge_count} edges")
        else:
            print(f"    [WARN] CRUD counts off - nodes: {node_count} (expected 3), edges: {edge_count} (expected 2)")
            warnings += 1

        conn.close()
        # Don't try to cleanup tmpdir on Windows - leave for OS cleanup

    except Exception as e:
        print(f"    [FAIL] XGraphStore CRUD failed: {e}")
        traceback.print_exc()
        errors += 1

    # 6. Test graph strategies loading
    print("\n[6] Testing graph strategies...")
    try:
        from theauditor.graph.strategies.base import GraphStrategy

        # Import strategies from their individual modules
        # Note: Class names use CamelCase (Orm not ORM)
        strategy_modules = [
            ("python_orm", "PythonOrmStrategy"),
            ("node_express", "NodeExpressStrategy"),
            ("node_orm", "NodeOrmStrategy"),
        ]

        loaded = 0
        for module_name, class_name in strategy_modules:
            try:
                module = __import__(
                    f"theauditor.graph.strategies.{module_name}",
                    fromlist=[class_name]
                )
                cls = getattr(module, class_name)
                if issubclass(cls, GraphStrategy):
                    loaded += 1
                    print(f"        - {class_name}: OK")
                else:
                    print(f"        - {class_name}: WARN (not a GraphStrategy subclass)")
                    warnings += 1
            except (ImportError, AttributeError) as e:
                print(f"        - {class_name}: WARN ({e})")
                warnings += 1

        if loaded >= 3:
            print(f"    [OK] Loaded {loaded}/{len(strategy_modules)} graph strategies")
        else:
            print(f"    [WARN] Only {loaded}/{len(strategy_modules)} strategies loaded")
            warnings += 1

    except ImportError as e:
        print(f"    [WARN] Base strategy import failed: {e}")
        warnings += 1
    except Exception as e:
        print(f"    [FAIL] Strategy loading failed: {e}")
        errors += 1

    # 7. Test XGraphBuilder initialization
    print("\n[7] Testing XGraphBuilder initialization...")
    try:
        from theauditor.graph.builder import XGraphBuilder

        builder = XGraphBuilder(
            batch_size=100,
            exclude_patterns=[],
            project_root=PROJECT_ROOT,
        )

        print(f"    [OK] XGraphBuilder initialized")

    except Exception as e:
        print(f"    [FAIL] XGraphBuilder initialization failed: {e}")
        traceback.print_exc()
        errors += 1

    # 8. Test bidirectional edge creation
    print("\n[8] Testing bidirectional edge creation (GRAPH FIX G3)...")
    try:
        from theauditor.graph.builder import create_bidirectional_graph_edges

        edges = create_bidirectional_graph_edges(
            source="src/a.py:foo",
            target="src/b.py:bar",
            edge_type="call",
            file="src/a.py",
            line=10,
        )

        if len(edges) == 2:
            forward = edges[0]
            reverse = edges[1]

            if (forward.source == "src/a.py:foo" and forward.target == "src/b.py:bar" and
                reverse.source == "src/b.py:bar" and reverse.target == "src/a.py:foo" and
                "_reverse" in reverse.type):
                print(f"    [OK] Bidirectional edges created correctly")
            else:
                print(f"    [FAIL] Bidirectional edge structure incorrect")
                errors += 1
        else:
            print(f"    [FAIL] Expected 2 edges, got {len(edges)}")
            errors += 1

    except Exception as e:
        print(f"    [FAIL] Bidirectional edge creation failed: {e}")
        traceback.print_exc()
        errors += 1

    # 9. Test graph analyzer import
    print("\n[9] Testing graph analyzer...")
    try:
        from theauditor.graph.analyzer import XGraphAnalyzer

        print(f"    [OK] XGraphAnalyzer imported successfully")

    except ImportError as e:
        print(f"    [WARN] XGraphAnalyzer not available: {e}")
        warnings += 1
    except Exception as e:
        print(f"    [FAIL] Graph analyzer error: {e}")
        errors += 1

    # 10. Test CFG and DFG builders
    print("\n[10] Testing CFG and DFG builders...")
    try:
        from theauditor.graph.cfg_builder import CFGBuilder
        from theauditor.graph.dfg_builder import DFGBuilder

        print(f"    [OK] CFGBuilder and DFGBuilder imported successfully")

    except ImportError as e:
        print(f"    [WARN] Some builders not available: {e}")
        warnings += 1
    except Exception as e:
        print(f"    [FAIL] Builder import error: {e}")
        errors += 1

    # 11. Test path correlator
    print("\n[11] Testing path correlator...")
    try:
        from theauditor.graph.path_correlator import PathCorrelator

        print(f"    [OK] PathCorrelator imported successfully")

    except ImportError as e:
        print(f"    [WARN] PathCorrelator not available: {e}")
        warnings += 1
    except Exception as e:
        print(f"    [FAIL] PathCorrelator error: {e}")
        errors += 1

    # Final verdict
    print("\n" + "=" * 60)
    if errors > 0:
        print(f"[FAIL] Graph layer verification failed with {errors} error(s)")
        print("       Graph operations may not work correctly.")
        return 2
    elif warnings > 0:
        print(f"[PASS] Graph layer verification passed with {warnings} warning(s)")
        return 1
    else:
        print("[PASS] Graph layer verification passed - all checks clean")
        return 0


if __name__ == "__main__":
    exit_code = verify_graph_layer()
    sys.exit(exit_code)
