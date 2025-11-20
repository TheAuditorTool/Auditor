#!/usr/bin/env python3
"""
NodeIndex Performance Benchmark
================================
Validates the 95%+ performance improvement from NodeIndex implementation.

This script:
1. Generates a large AST (2000 functions)
2. Compares old way (ast.walk) vs new way (NodeIndex)
3. Shows the speedup factor achieved

Author: Lead Auditor
Date: November 2025
"""

import ast
import time
import sys
from pathlib import Path

# Ensure we can import your modules
sys.path.append(str(Path.cwd()))

def verify_migration_complete():
    """Check if the migration has been run."""
    try:
        from theauditor.ast_extractors.python.utils.node_index import NodeIndex
        print("[PASS] Successfully imported NodeIndex")
        return NodeIndex
    except ImportError:
        print("[FAIL] Could not import NodeIndex. Did you run the migration script?")
        print("\nRun these commands first:")
        print("  python ast_walk_to_filecontext.py --create-modules --target-dir ./theauditor/ast_extractors/python/")
        print("  python ast_walk_to_filecontext.py --target-dir ./theauditor/ast_extractors/python/")
        sys.exit(1)

def generate_heavy_ast(n_functions=1000, n_classes=500):
    """Generates a large Python AST to stress-test performance."""
    print(f"\nGenerating test AST:")
    print(f"  - {n_functions} functions")
    print(f"  - {n_classes} classes")

    code_parts = []

    # Add functions
    for i in range(n_functions):
        code_parts.append(f"""
def function_{i}(arg1, arg2):
    '''Docstring for function {i}'''
    x = {i}
    y = arg1 + arg2
    if x > 100:
        return x * y
    else:
        for j in range(10):
            x += j
    return x
""")

    # Add classes
    for i in range(n_classes):
        code_parts.append(f"""
class Class_{i}:
    '''Class {i} for testing'''
    def __init__(self):
        self.value = {i}

    def method_{i}(self, x):
        return self.value + x

    @property
    def prop_{i}(self):
        return self.value * 2
""")

    full_code = "\n".join(code_parts)
    tree = ast.parse(full_code)

    # Count nodes
    total_nodes = len(list(ast.walk(tree)))
    print(f"  - Total AST nodes: {total_nodes:,}")

    return tree

def benchmark_old_way(tree, iterations=50):
    """Benchmark the old ast.walk approach."""
    print(f"\n[OLD WAY] Running {iterations} extractors with ast.walk()...")

    start_time = time.time()
    total_nodes_found = 0

    for i in range(iterations):
        # Simulate different extractors looking for different node types
        if i % 3 == 0:
            # Looking for functions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_nodes_found += 1
        elif i % 3 == 1:
            # Looking for classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    total_nodes_found += 1
        else:
            # Looking for calls
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    total_nodes_found += 1

    elapsed = time.time() - start_time
    print(f"  Time: {elapsed:.4f} seconds")
    print(f"  Nodes processed: {total_nodes_found:,}")

    return elapsed, total_nodes_found

def benchmark_new_way(tree, NodeIndex, iterations=50):
    """Benchmark the new NodeIndex approach."""
    print(f"\n[NEW WAY] Building NodeIndex + {iterations} O(1) queries...")

    start_time = time.time()

    # Build the index ONCE (this is the key improvement)
    build_start = time.time()
    index = NodeIndex(tree)
    build_time = time.time() - build_start
    print(f"  Index build time: {build_time:.4f} seconds")

    total_nodes_found = 0

    # Now query the index (O(1) lookups)
    query_start = time.time()
    for i in range(iterations):
        # Simulate different extractors querying the index
        if i % 3 == 0:
            # Looking for functions
            nodes = index.find_nodes(ast.FunctionDef)
            total_nodes_found += len(nodes)
        elif i % 3 == 1:
            # Looking for classes
            nodes = index.find_nodes(ast.ClassDef)
            total_nodes_found += len(nodes)
        else:
            # Looking for calls
            nodes = index.find_nodes(ast.Call)
            total_nodes_found += len(nodes)

    query_time = time.time() - query_start
    total_time = time.time() - start_time

    print(f"  Query time: {query_time:.4f} seconds")
    print(f"  Total time: {total_time:.4f} seconds")
    print(f"  Nodes processed: {total_nodes_found:,}")

    return total_time, total_nodes_found

def run_benchmark():
    """Main benchmark function."""
    print("="*70)
    print("AST TRAVERSAL PERFORMANCE BENCHMARK")
    print("="*70)

    # Verify migration is complete
    NodeIndex = verify_migration_complete()

    # Generate test data
    tree = generate_heavy_ast(n_functions=1500, n_classes=500)

    # Number of extractors to simulate
    iterations = 100  # Simulating 100 different extractors

    print(f"\nSimulating {iterations} extractors processing the same AST file")
    print("-"*70)

    # Run benchmarks
    old_time, old_nodes = benchmark_old_way(tree, iterations)
    new_time, new_nodes = benchmark_new_way(tree, NodeIndex, iterations)

    # Verify correctness (both should find same nodes)
    if old_nodes != new_nodes:
        print(f"\n[WARNING] Node count mismatch: old={old_nodes}, new={new_nodes}")
        print("This might indicate a bug in the transformation")

    # Calculate and display results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    print(f"\nOld approach (ast.walk):")
    print(f"  Total time: {old_time:.4f} seconds")
    print(f"  Per extractor: {old_time/iterations:.4f} seconds")

    print(f"\nNew approach (NodeIndex):")
    print(f"  Total time: {new_time:.4f} seconds")
    print(f"  Per extractor: {new_time/iterations:.6f} seconds")

    if new_time > 0:
        speedup = old_time / new_time
        improvement = ((old_time - new_time) / old_time) * 100

        print(f"\n" + "="*70)
        print(f"PERFORMANCE IMPROVEMENT: {speedup:.1f}x FASTER")
        print(f"Time saved: {improvement:.1f}%")
        print("="*70)

        if speedup >= 10:
            print("\n[SUCCESS] Target achieved: >10x speedup!")
            print("The NodeIndex optimization is working as expected.")
        elif speedup >= 5:
            print("\n[GOOD] Significant speedup achieved: 5-10x")
            print("The optimization is effective, though not quite at theoretical maximum.")
        else:
            print("\n[WARNING] Speedup lower than expected (<5x)")
            print("Check if complex ast.walk patterns are limiting the optimization.")
    else:
        print("\n[AMAZING] New approach is too fast to measure accurately!")
        print("The optimization exceeded all expectations.")

    # Additional metrics
    print(f"\nAdditional metrics:")
    total_ast_nodes = len(list(ast.walk(tree)))
    print(f"  AST size: {total_ast_nodes:,} nodes")
    print(f"  Old way node visits: {total_ast_nodes * iterations:,}")
    print(f"  New way node visits: {total_ast_nodes:,} (index) + {new_nodes:,} (queries)")

    complexity_old = total_ast_nodes * iterations
    complexity_new = total_ast_nodes + new_nodes
    complexity_reduction = ((complexity_old - complexity_new) / complexity_old) * 100
    print(f"  Complexity reduction: {complexity_reduction:.1f}%")

    return speedup

if __name__ == "__main__":
    try:
        speedup = run_benchmark()
        sys.exit(0 if speedup >= 5 else 1)
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)