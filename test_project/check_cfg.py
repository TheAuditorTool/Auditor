"""Check CFG data in database."""

import sqlite3
import sys
sys.path.insert(0, 'C:/Users/santa/Desktop/TheAuditor')

from theauditor.graph.cfg_builder import CFGBuilder

# Open database
builder = CFGBuilder('test_cfg.db')

# Get all functions
functions = builder.get_all_functions()
print(f"Found {len(functions)} functions with CFG data:")
for func in functions:
    print(f"  - {func['function_name']} in {func['file']} ({func['block_count']} blocks)")

# Get complex functions
print("\nComplex functions (complexity >= 5):")
complex_funcs = builder.analyze_complexity(threshold=5)
for func in complex_funcs:
    print(f"  - {func['function']}: complexity={func['complexity']}, blocks={func['block_count']}, has_loops={func['has_loops']}")

# Check a specific function if we have any
if functions:
    func = functions[0]
    print(f"\nDetailed CFG for {func['function_name']}:")
    cfg = builder.get_function_cfg(func['file'], func['function_name'])
    print(f"  Blocks: {len(cfg['blocks'])}")
    for block in cfg['blocks']:
        print(f"    - {block['type']} (lines {block['start_line']}-{block['end_line']})")
    print(f"  Edges: {len(cfg['edges'])}")
    for edge in cfg['edges']:
        print(f"    - {edge['source']} -> {edge['target']} ({edge['type']})")
    print(f"  Metrics: {cfg['metrics']}")

builder.close()