#!/usr/bin/env python3
"""
Performance Benchmarks for Object Literal Parsing (Phase 5.4)

Measures actual performance improvement from database-backed approach vs regex fallback.
Target: Validate 100-1000x speedup claim from docs/OBJECT_LITERAL_PARSING.md
"""

import sqlite3
import time
import tempfile
import re
from pathlib import Path
from typing import List, Tuple

# Import schema contract for database-first queries
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from theauditor.indexer.schema import build_query


def create_test_database(num_objects: int) -> str:
    """Create a test database with specified number of object literal entries."""
    db_path = tempfile.mktemp(suffix='.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create object_literals table
    cursor.execute("""
        CREATE TABLE object_literals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT NOT NULL,
            line INTEGER NOT NULL,
            variable_name TEXT,
            property_name TEXT NOT NULL,
            property_value TEXT NOT NULL,
            property_type TEXT,
            nested_level INTEGER DEFAULT 0,
            in_function TEXT
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX idx_object_literals_var ON object_literals(variable_name)")
    cursor.execute("CREATE INDEX idx_object_literals_value ON object_literals(property_value)")
    cursor.execute("CREATE INDEX idx_object_literals_type ON object_literals(property_type)")

    # Insert test data: Multiple objects with varying properties
    for obj_id in range(num_objects):
        obj_name = f"handlers{obj_id}"
        # Each object has 3 function references
        for prop_id in range(3):
            cursor.execute("""
                INSERT INTO object_literals
                (file, line, variable_name, property_name, property_value, property_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                f'test_file_{obj_id % 10}.js',
                10 + prop_id,
                obj_name,
                f'action{prop_id}',
                f'handler{prop_id}_{obj_id}',
                'function_ref'
            ))

    conn.commit()
    conn.close()
    return db_path


def benchmark_database_approach(db_path: str, variable_name: str, iterations: int = 100) -> Tuple[float, List[str]]:
    """Benchmark database-backed dispatch resolution."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    results = []
    start = time.perf_counter()

    for _ in range(iterations):
        query = build_query('object_literals',
            ['property_value'],
            where="variable_name = ? AND property_type IN ('function_ref', 'shorthand')"
        )
        cursor.execute(query, (variable_name,))
        results = [row[0] for row in cursor.fetchall()]

    elapsed = time.perf_counter() - start
    conn.close()

    return elapsed / iterations, results


def benchmark_regex_approach(variable_name: str, source_code: str, iterations: int = 100) -> Tuple[float, List[str]]:
    """Benchmark regex-based dispatch resolution (fallback method)."""
    # Simulate the old regex approach from interprocedural_cfg.py
    pattern = re.compile(rf'{re.escape(variable_name)}\s*=\s*\{{([^}}]+)\}}', re.DOTALL)

    results = []
    start = time.perf_counter()

    for _ in range(iterations):
        match = pattern.search(source_code)
        if match:
            props_str = match.group(1)
            # Split on commas, extract property values
            props = [p.strip() for p in props_str.split(',')]
            results = []
            for prop in props:
                if ':' in prop:
                    parts = prop.split(':', 1)
                    value = parts[1].strip()
                    # Extract identifier
                    id_match = re.match(r'^[a-zA-Z_]\w*', value)
                    if id_match:
                        results.append(id_match.group())

    elapsed = time.perf_counter() - start
    return elapsed / iterations, results


def generate_source_code(num_objects: int) -> str:
    """Generate JavaScript source code with object literals."""
    lines = []
    for obj_id in range(num_objects):
        lines.append(f"const handlers{obj_id} = {{")
        lines.append(f"    action0: handler0_{obj_id},")
        lines.append(f"    action1: handler1_{obj_id},")
        lines.append(f"    action2: handler2_{obj_id}")
        lines.append("};")
        lines.append("")
    return "\n".join(lines)


def run_micro_benchmark(num_objects: int, iterations: int = 100):
    """Run micro-benchmark for single dispatch resolution."""
    print(f"\n{'='*80}")
    print(f"Micro-Benchmark: {num_objects} object literals, {iterations} iterations")
    print(f"{'='*80}")

    # Setup
    db_path = create_test_database(num_objects)
    source_code = generate_source_code(num_objects)
    test_var = f"handlers{num_objects // 2}"  # Test middle object

    # Benchmark database approach
    db_time, db_results = benchmark_database_approach(db_path, test_var, iterations)

    # Benchmark regex approach
    regex_time, regex_results = benchmark_regex_approach(test_var, source_code, iterations)

    # Calculate speedup
    if regex_time > 0:
        speedup = regex_time / db_time
    else:
        speedup = float('inf')

    # Results
    print(f"\nDatabase Approach:")
    print(f"  Time per query: {db_time * 1000:.6f} ms")
    print(f"  Results found: {len(db_results)}")

    print(f"\nRegex Approach:")
    print(f"  Time per query: {regex_time * 1000:.6f} ms")
    print(f"  Results found: {len(regex_results)}")

    print(f"\nPerformance:")
    print(f"  Speedup: {speedup:.1f}x faster")
    print(f"  Target: 100-1000x")
    status = 'PASS' if speedup >= 100 else 'FAIL' if speedup < 10 else 'PARTIAL'
    print(f"  Status: {status}")

    # Cleanup
    Path(db_path).unlink()

    return {
        'num_objects': num_objects,
        'db_time_ms': db_time * 1000,
        'regex_time_ms': regex_time * 1000,
        'speedup': speedup,
        'db_results': len(db_results),
        'regex_results': len(regex_results)
    }


def run_scalability_test():
    """Test scalability with increasing dataset sizes."""
    print(f"\n{'='*80}")
    print(f"Scalability Test: Performance vs Dataset Size")
    print(f"{'='*80}")

    sizes = [10, 50, 100, 500, 1000]
    results = []

    for size in sizes:
        result = run_micro_benchmark(size, iterations=100)
        results.append(result)

    # Summary table
    print(f"\n{'='*80}")
    print(f"Scalability Summary")
    print(f"{'='*80}")
    print(f"{'Objects':<10} {'DB Time (ms)':<15} {'Regex Time (ms)':<18} {'Speedup':<12} {'Status':<10}")
    print(f"{'-'*80}")

    for r in results:
        status = 'PASS' if r['speedup'] >= 100 else 'FAIL' if r['speedup'] < 10 else 'PARTIAL'
        print(f"{r['num_objects']:<10} {r['db_time_ms']:<15.6f} {r['regex_time_ms']:<18.6f} {r['speedup']:<12.1f} {status:<10}")

    return results


def run_real_world_simulation():
    """Simulate real-world taint analysis workload."""
    print(f"\n{'='*80}")
    print(f"Real-World Simulation: Full Taint Analysis Scenario")
    print(f"{'='*80}")

    # Simulate realistic workload: 50 objects, 20 dispatch resolutions per analysis
    num_objects = 50
    num_resolutions = 20

    db_path = create_test_database(num_objects)
    source_code = generate_source_code(num_objects)

    # Database approach: 20 resolutions
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    start = time.perf_counter()

    for i in range(num_resolutions):
        var_name = f"handlers{i % num_objects}"
        query = build_query('object_literals',
            ['property_value'],
            where="variable_name = ? AND property_type IN ('function_ref', 'shorthand')"
        )
        cursor.execute(query, (var_name,))
        _ = cursor.fetchall()

    db_total_time = time.perf_counter() - start
    conn.close()

    # Regex approach: 20 resolutions
    start = time.perf_counter()

    for i in range(num_resolutions):
        var_name = f"handlers{i % num_objects}"
        pattern = re.compile(rf'{re.escape(var_name)}\s*=\s*\{{([^}}]+)\}}', re.DOTALL)
        match = pattern.search(source_code)
        if match:
            props_str = match.group(1)
            props = [p.strip() for p in props_str.split(',')]
            for prop in props:
                if ':' in prop:
                    parts = prop.split(':', 1)
                    value = parts[1].strip()
                    id_match = re.match(r'^[a-zA-Z_]\w*', value)

    regex_total_time = time.perf_counter() - start

    # Results
    speedup = regex_total_time / db_total_time if db_total_time > 0 else float('inf')

    print(f"\nWorkload: {num_objects} objects, {num_resolutions} dispatch resolutions")
    print(f"\nDatabase Approach:")
    print(f"  Total time: {db_total_time * 1000:.3f} ms")
    print(f"  Per resolution: {(db_total_time / num_resolutions) * 1000:.6f} ms")

    print(f"\nRegex Approach:")
    print(f"  Total time: {regex_total_time * 1000:.3f} ms")
    print(f"  Per resolution: {(regex_total_time / num_resolutions) * 1000:.6f} ms")

    print(f"\nPerformance:")
    print(f"  Speedup: {speedup:.1f}x faster")
    print(f"  Time saved: {(regex_total_time - db_total_time) * 1000:.3f} ms")

    # Cleanup
    Path(db_path).unlink()

    return {
        'db_total_ms': db_total_time * 1000,
        'regex_total_ms': regex_total_time * 1000,
        'speedup': speedup,
        'time_saved_ms': (regex_total_time - db_total_time) * 1000
    }


def main():
    """Run all benchmarks and generate performance report."""
    print("="*80)
    print("Object Literal Parsing - Performance Benchmark Suite")
    print("Phase 5.4: Validating 100-1000x speedup claim")
    print("="*80)

    # Run benchmarks
    scalability_results = run_scalability_test()
    real_world_result = run_real_world_simulation()

    # Final summary
    print(f"\n{'='*80}")
    print(f"FINAL SUMMARY")
    print(f"{'='*80}")

    avg_speedup = sum(r['speedup'] for r in scalability_results) / len(scalability_results)
    max_speedup = max(r['speedup'] for r in scalability_results)
    min_speedup = min(r['speedup'] for r in scalability_results)

    print(f"\nScalability Test:")
    print(f"  Average speedup: {avg_speedup:.1f}x")
    print(f"  Range: {min_speedup:.1f}x - {max_speedup:.1f}x")

    print(f"\nReal-World Simulation:")
    print(f"  Speedup: {real_world_result['speedup']:.1f}x")
    print(f"  Time saved per analysis: {real_world_result['time_saved_ms']:.3f} ms")

    print(f"\nTarget Validation:")
    print(f"  Target: 100-1000x speedup")
    print(f"  Achieved: {avg_speedup:.1f}x average")

    if avg_speedup >= 100:
        print(f"  Status: PASS - Target achieved!")
    elif avg_speedup >= 10:
        print(f"  Status: PARTIAL - Significant improvement, but below target")
    else:
        print(f"  Status: FAIL - Below expected performance")

    print(f"\nConclusion:")
    if avg_speedup >= 100:
        print(f"  Database-backed approach delivers {avg_speedup:.1f}x speedup.")
        print(f"  Indexed lookups provide consistent O(1) performance.")
        print(f"  Recommendation: Use database approach for all new code.")
    else:
        print(f"  Database approach is {avg_speedup:.1f}x faster than regex.")
        print(f"  Performance improvement validated, though target not fully met.")
        print(f"  Recommendation: Further optimization may be needed.")


if __name__ == '__main__':
    main()
