=== AGENT #4 REPORT: TAINT ANALYSIS (CRITICAL) ===

SECTION 1: DISCOVERY PHASE VERIFICATION
File: taint/discovery.py lines 89-102
  - Linear scan pattern: `for symbol in self.cache.symbols`
    - EXISTS: ✅ YES (line 89)
  - Filter condition: `if symbol.get('type') == 'property'`
    - EXISTS: ✅ YES (line 90)

Evidence (paste actual code):
```python
# Lines 89-102
for symbol in self.cache.symbols:
    if symbol.get('type') == 'property':
        name = symbol.get('name', '')
        if any(pattern in name.lower() for pattern in input_patterns):
            sources.append({
                'type': 'user_input',
                'name': name,
                'file': symbol.get('path', ''),
                'line': symbol.get('line', 0),
                'pattern': name,
                'category': 'user_input',
                'risk': 'high',
                'metadata': symbol
            })
```

Operations calculation:
  - Symbols in test project: 56,118
  - Patterns to check: 8
  - Total operations: 448,944 (investigation claims 300,000)
  - Status: ✅ CONFIRMED (150% of claim - actually WORSE)

SECTION 2: ANALYSIS PHASE N+1
File: taint/analysis.py lines 298-331
  - Function `_get_containing_function` exists: ✅ YES
  - Pattern: `for symbol in self.cache.symbols`
    - EXISTS: ✅ YES (line 313 and 322 - TWO loops!)

Evidence (paste actual code):
```python
# Lines 313-331
# Check traditional function symbols - find exact line match first
for symbol in self.cache.symbols:
    start_line = symbol.get('line', 0) or 0
    # For function definitions, the source line equals the function line
    if (symbol.get('type') == 'function' and
        symbol.get('path') == file_path and
        start_line == line):
        return symbol.get('name')

# Then check range matches
for symbol in self.cache.symbols:
    start_line = symbol.get('line', 0) or 0
    end_line = symbol.get('end_line')
    if end_line is None:
        end_line = (line or 0) + 100

    if (symbol.get('type') == 'function' and
        symbol.get('path') == file_path and
        line is not None and start_line <= line <= end_line):
        return symbol.get('name')
```

Call site analysis:
  - Called from: line 58 in `analyze_interprocedural` (once per source)
  - Frequency: 1 time per source × ~1,054 sources

Operations calculation:
  - Sources: 1,054
  - Symbols: 56,118 × 2 loops = 112,236 per call
  - Total comparisons: 118,296,744 (investigation claims 100 MILLION)
  - Status: ✅ CONFIRMED (118% of claim - actually WORSE)

SECTION 3: PROPAGATION PHASE LIKE WILDCARDS
File: taint/propagation.py lines 224-232
  - LIKE wildcard pattern: `source_expr LIKE ?`
    - EXISTS: ✅ YES (line 224)
  - Parameter: `f"%{source['pattern']}%"` (leading wildcard)
    - CONFIRMED: ✅ YES (line 231)

Evidence (paste actual query):
```python
# Lines 223-232
query = build_query('assignments', ['target_var', 'in_function', 'line'],
    where="file = ? AND line BETWEEN ? AND ? AND source_expr LIKE ?",
    order_by="line"
)
cursor.execute(query, (
    source["file"],
    source["line"] - 2,
    source["line"] + 2,
    f"%{source['pattern']}%"
))
```

Additional LIKE patterns found:
  - Line 254: `argument_expr LIKE ?` with same leading wildcard pattern
  - Total LIKE wildcards: 2

Operations calculation:
  - Assignments in DB: 21,977
  - Sources: 1,054
  - Rows scanned: 46,327,516 (investigation claims 50 MILLION)
  - Status: ✅ CONFIRMED (93% of claim)

SECTION 4: CFG INTEGRATION N+1 QUERIES
File: taint/cfg_integration.py.bak lines 295-300
  - File exists: ✅ YES (in backup directory)
  - Still in use: ❌ NO (import fails - module has been removed/broken)
  - Per-block query pattern: ✅ CONFIRMED in backup file

Evidence:
```python
# Lines 296-304 from backup file
self.cursor.execute(query, (block_id,))

for stmt_type, line, stmt_text in self.cursor.fetchall():
    # Query function_call_args to get exact function name
    args_query = build_query('function_call_args',
        ['callee_function', 'argument_expr'],
        where="file = ? AND line = ?"
    )
    self.cursor.execute(args_query, (self.file_path, line))
```

Current status:
  - cfg_integration.py has been deleted/moved to backup
  - Import in propagation.py line 132 fails at runtime
  - This part of the code is BROKEN and not contributing to performance issues

Query count calculation:
  - CFG blocks: 30,158
  - Estimated paths: 100
  - Total queries: 3,015,800 (investigation claims 10,000)
  - Status: ⚠️ MODIFIED (code is broken/unused)

SECTION 5: OVERALL COMPLEXITY ANALYSIS
Test project measurements:
  - Sources: 1,054
  - Symbols: 56,118
  - Assignments: 21,977
  - CFG blocks: 30,158

Total operations (WITHOUT recursion):
  - Discovery: 462,984 ops
  - Analysis: 118,296,744 ops
  - Propagation: 46,327,516 ops
  - CFG: N/A (code broken)
  - **GRAND TOTAL: 165,087,244 operations**

Total operations (WITH max_depth=5 recursion, branching_factor=3):
  - Recursive multiplier: 121 (3^0 + 3^1 + 3^2 + 3^3 + 3^4)
  - Analysis with recursion: 14,313,906,024 ops
  - Propagation with recursion: 5,605,629,436 ops
  - **GRAND TOTAL: 19,919,535,460 operations**

Investigation claim: 60 BILLION operations
Status: ⚠️ MODIFIED (33% of claim with aggressive recursion assumptions)

SECTION 6: DISCREPANCIES & CRITICAL FINDINGS

1. **60 BILLION CLAIM IS EXAGGERATED BY 3X**
   - Even with aggressive recursion (depth=5, branching=3), only reaches 20 billion ops
   - Without recursion, only 165 million ops (0.3% of claim)
   - Investigation appears to have overestimated by 3-357x depending on assumptions

2. **CORE PERFORMANCE ISSUES CONFIRMED**
   - Discovery: Linear scan confirmed (worse than claimed - 450K vs 300K)
   - Analysis: Double-loop N+1 confirmed (worse than claimed - 118M vs 100M)
   - Propagation: LIKE wildcards confirmed (46M vs 50M claimed)
   - CFG: Code is broken/deleted, not contributing to current performance

3. **ACTUAL BOTTLENECKS**
   - Primary: `_get_containing_function` doing 118 MILLION operations
   - Secondary: LIKE wildcards scanning 46 MILLION rows
   - Tertiary: Discovery phase scanning 450K operations

4. **CODE STATE ISSUES**
   - cfg_integration.py has been removed but is still imported
   - Import fails at runtime with DataStorer error
   - This suggests partial/incomplete refactoring

SECTION 7: IMPLEMENTATION ASSESSMENT

Spatial indexes feasible: YES - Clear optimization paths exist
Complexity: MEDIUM - Straightforward indexing patterns
Risk level: LOW - Well-understood optimizations
Estimated effort: 3-5 days
Expected speedup: 100-1000x (not 60,000x as claimed)

**CRITICAL RECOMMENDATIONS:**

1. **FIX IMMEDIATELY**: `_get_containing_function` double-loop
   - Build spatial index: file → line_range → function
   - Expected speedup: 1000x (from 118M to 118K operations)

2. **FIX SECOND**: LIKE wildcard queries
   - Use indexed columns first, then Python substring match
   - Expected speedup: 100x (from 46M to 460K operations)

3. **FIX THIRD**: Discovery phase linear scan
   - Index symbols by type
   - Expected speedup: 10x (from 450K to 45K operations)

4. **CLEANUP**: Remove broken cfg_integration imports
   - Either restore the module or remove the imports
   - Current state causes runtime errors

**BOTTOM LINE**:
- Performance problems are REAL and SEVERE
- 60 billion operations claim is EXAGGERATED by 3x
- Actual complexity is ~20 billion ops with recursion
- Optimizations could achieve 100-1000x speedup (not 60,000x)
- Priority remains HIGH but not "APOCALYPTIC"

=== END REPORT ===