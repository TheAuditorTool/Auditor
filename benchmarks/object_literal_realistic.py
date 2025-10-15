#!/usr/bin/env python3
"""
REALISTIC Performance Benchmark for Object Literal Parsing

This benchmark compares:
- NEW: Database query (parse once during indexing, query many times)
- OLD: File I/O + regex parsing (read and parse file every time)

The 100-1000x speedup claim comes from avoiding repeated file I/O + parsing.
"""

import sqlite3
import time
import tempfile
import re
from pathlib import Path
from typing import List, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from theauditor.indexer.schema import build_query


def create_realistic_database(num_files: int, objects_per_file: int) -> Tuple[str, Path]:
    """Create test database and source files."""
    # Create temp directory for source files
    temp_dir = Path(tempfile.mkdtemp())

    # Create database
    db_path = tempfile.mktemp(suffix='.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create schema
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
    cursor.execute("CREATE INDEX idx_object_literals_var ON object_literals(variable_name)")

    # Create realistic source files and populate database
    for file_id in range(num_files):
        file_path = temp_dir / f"handlers_{file_id}.js"

        # Generate realistic JavaScript file content
        lines = [
            "// Auto-generated handler file",
            "import { Router } from 'express';",
            "import { validateAuth } from '../middleware';",
            "",
            "// Authentication handlers",
        ]

        # Add multiple object literals to this file
        for obj_id in range(objects_per_file):
            obj_name = f"handlers{file_id}_{obj_id}"
            lines.append(f"const {obj_name} = {{")

            # Each object has 5 properties
            for prop_id in range(5):
                prop_name = f"action{prop_id}"
                func_name = f"handle{prop_name.title()}{file_id}_{obj_id}"
                lines.append(f"    {prop_name}: {func_name},")

                # Insert into database
                cursor.execute("""
                    INSERT INTO object_literals
                    (file, line, variable_name, property_name, property_value, property_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(file_path),
                    len(lines),
                    obj_name,
                    prop_name,
                    func_name,
                    'function_ref'
                ))

            lines.append("};")
            lines.append("")

        # Add more boilerplate to make file realistic size
        lines.extend([
            "// Export handlers",
            "export default function setupHandlers(router) {",
            "    // Route setup logic here",
            "    return router;",
            "}",
        ])

        # Write file
        file_path.write_text("\n".join(lines))

    conn.commit()
    conn.close()

    return db_path, temp_dir


def benchmark_database_query(db_path: str, variable_names: List[str]) -> Tuple[float, int]:
    """Benchmark: Query database for callees (NEW approach)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    total_results = 0
    start = time.perf_counter()

    for var_name in variable_names:
        query = build_query('object_literals',
            ['property_value'],
            where="variable_name = ? AND property_type IN ('function_ref', 'shorthand')"
        )
        cursor.execute(query, (var_name,))
        results = cursor.fetchall()
        total_results += len(results)

    elapsed = time.perf_counter() - start
    conn.close()

    return elapsed, total_results


def benchmark_file_regex(source_dir: Path, variable_names: List[str]) -> Tuple[float, int]:
    """Benchmark: Read files and parse with regex (OLD approach)."""
    total_results = 0
    start = time.perf_counter()

    # For each variable, need to find which file contains it (requires scanning all files!)
    for var_name in variable_names:
        found = False

        # Scan all JavaScript files (realistic: don't know which file has the object)
        for js_file in source_dir.glob("*.js"):
            # FILE I/O - this is the killer overhead
            content = js_file.read_text()

            # Regex parsing
            pattern = re.compile(rf'\b{re.escape(var_name)}\s*=\s*\{{([^}}]+)\}}', re.DOTALL)
            match = pattern.search(content)

            if match:
                # Extract property values
                props_str = match.group(1)
                props = [p.strip() for p in props_str.split(',')]
                for prop in props:
                    if ':' in prop:
                        parts = prop.split(':', 1)
                        value = parts[1].strip()
                        id_match = re.match(r'^[a-zA-Z_]\w*', value)
                        if id_match:
                            total_results += 1
                found = True
                break  # Found it, stop scanning files

        if not found:
            # Variable not found - in real scenario, would need to scan ALL files
            pass

    elapsed = time.perf_counter() - start
    return elapsed, total_results


def run_realistic_benchmark(num_files: int, objects_per_file: int, num_queries: int):
    """Run realistic benchmark comparing database vs file I/O approaches."""
    print(f"\n{'='*80}")
    print(f"Realistic Benchmark: {num_files} files, {objects_per_file} objects/file, {num_queries} queries")
    print(f"{'='*80}")

    # Setup
    print("Setting up test data...")
    db_path, source_dir = create_realistic_database(num_files, objects_per_file)

    # Generate variable names to query (distributed across files)
    variable_names = []
    for i in range(num_queries):
        file_id = i % num_files
        obj_id = (i // num_files) % objects_per_file
        variable_names.append(f"handlers{file_id}_{obj_id}")

    print(f"Querying {len(variable_names)} variables across {num_files} files...")

    # Benchmark database approach
    print("\nRunning database approach...")
    db_time, db_results = benchmark_database_query(db_path, variable_names)

    # Benchmark file I/O + regex approach
    print("Running file I/O + regex approach...")
    file_time, file_results = benchmark_file_regex(source_dir, variable_names)

    # Calculate speedup
    speedup = file_time / db_time if db_time > 0 else float('inf')

    # Results
    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")

    print(f"\nDatabase Approach (NEW):")
    print(f"  Total time: {db_time * 1000:.3f} ms")
    print(f"  Per query: {(db_time / len(variable_names)) * 1000:.6f} ms")
    print(f"  Results found: {db_results}")

    print(f"\nFile I/O + Regex Approach (OLD):")
    print(f"  Total time: {file_time * 1000:.3f} ms")
    print(f"  Per query: {(file_time / len(variable_names)) * 1000:.6f} ms")
    print(f"  Results found: {file_results}")

    print(f"\nPerformance:")
    print(f"  Speedup: {speedup:.1f}x faster")
    print(f"  Time saved: {(file_time - db_time) * 1000:.3f} ms")

    print(f"\nBreakdown:")
    print(f"  File I/O overhead: ~{(file_time - db_time) / len(variable_names) * 1000:.3f} ms per query")
    print(f"  Database eliminates: Repeated file reads and regex parsing")

    # Cleanup
    Path(db_path).unlink()
    for f in source_dir.glob("*.js"):
        f.unlink()
    source_dir.rmdir()

    return speedup, db_time, file_time


def main():
    """Run realistic benchmarks."""
    print("="*80)
    print("Object Literal Parsing - REALISTIC Performance Benchmark")
    print("Comparing: Database query vs File I/O + regex parsing")
    print("="*80)

    # Test scenarios
    scenarios = [
        (5, 2, 10, "Small project"),      # 5 files, 2 objects each, 10 queries
        (10, 5, 50, "Medium project"),    # 10 files, 5 objects each, 50 queries
        (20, 5, 100, "Large project"),    # 20 files, 5 objects each, 100 queries
    ]

    results = []
    for num_files, objs_per_file, queries, label in scenarios:
        print(f"\n\nScenario: {label}")
        print(f"=" * 80)
        speedup, db_time, file_time = run_realistic_benchmark(num_files, objs_per_file, queries)
        results.append((label, speedup, db_time * 1000, file_time * 1000))

    # Final summary
    print(f"\n\n{'='*80}")
    print(f"FINAL SUMMARY")
    print(f"{'='*80}")

    print(f"\n{'Scenario':<20} {'Speedup':<15} {'DB Time (ms)':<18} {'File Time (ms)':<18}")
    print(f"{'-'*80}")
    for label, speedup, db_ms, file_ms in results:
        print(f"{label:<20} {speedup:<15.1f}x {db_ms:<18.3f} {file_ms:<18.3f}")

    avg_speedup = sum(r[1] for r in results) / len(results)

    print(f"\nAverage Speedup: {avg_speedup:.1f}x")
    print(f"\nTarget: 100-1000x speedup")

    if avg_speedup >= 100:
        print(f"Status: PASS - Target achieved!")
        print(f"\nConclusion:")
        print(f"  The database approach achieves {avg_speedup:.1f}x speedup by:")
        print(f"  1. Parsing once during indexing (not on every query)")
        print(f"  2. Eliminating repeated file I/O operations")
        print(f"  3. Using indexed SQL lookups instead of regex scanning")
    elif avg_speedup >= 10:
        print(f"Status: PARTIAL - Significant improvement")
        print(f"\nConclusion:")
        print(f"  The database approach provides {avg_speedup:.1f}x speedup.")
        print(f"  Major benefit: Eliminates file I/O overhead.")
        print(f"  Further optimization possible with more realistic file sizes.")
    else:
        print(f"Status: FAIL - Below target")
        print(f"\nConclusion:")
        print(f"  Need to investigate benchmark methodology or implementation.")


if __name__ == '__main__':
    main()
