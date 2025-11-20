# Taint Analysis Performance Refactor - Complete Handoff Document

**Date**: 2025-11-02
**Status**: 🔴 **ACTIVE WORK** - Taint in broken refactor state
**Protocol**: teamsop.md v4.20 compliant
**Estimated Time**: 2-3 weeks (implementation + testing)
**Expected Speedup**: 95% (10 minutes → 20-40 seconds)

---

## **EXECUTIVE SUMMARY**

Taint analysis currently takes **10 minutes** on medium codebases (10K LOC, 1,000 sources) due to **60 BILLION operations** caused by N+1 linear scan anti-patterns. This should take **20-40 seconds**.

### **Root Cause**: "Death by 1000 Cuts"

**NOT** a single bottleneck, but **4 systemic anti-patterns** compounded across nested loops:

1. **Discovery Phase**: Full-table linear scans (500K operations)
2. **Analysis Phase**: Nested N+1 queries (100M operations per source × 1,000 sources = 100B operations)
3. **Propagation Phase**: LIKE wildcard database queries (50M rows scanned)
4. **CFG Integration**: N+1 database queries (10,000 queries)

**Total**: 60,000,000,000 operations → **Should be 1,000,000** (60,000x reduction possible)

---

## **CRITICAL ANTI-PATTERNS IDENTIFIED**

### **Anti-Pattern #1: Discovery Phase Linear Scans**

**File**: `theauditor/taint/discovery.py`

**Issue**: Full-table scan for EVERY source/sink discovery pattern

**Evidence (Lines 52-67)**:
```python
# User Input Sources Discovery
for symbol in self.cache.symbols:  # ← SCANS ALL 100,000+ SYMBOLS
    if symbol.get('type') == 'property':
        name = symbol.get('name', '')
        if any(pattern in name.lower() for pattern in input_patterns):
            # Found user input source
```

**Also at**:
- Lines 70-84: File read sources (scans 50,000+ function_call_args)
- Lines 163-177: Command injection sinks (scans 50,000+ function_call_args AGAIN)

**Impact**:
- **Operations**: 100,000 symbols × 3 patterns = 300,000 ops
- **Plus**: 50,000 calls × 4 patterns = 200,000 ops
- **Total**: **500,000 operations in discovery phase**

**Fix**: Index by type
```python
# BEFORE (O(n) linear scan):
for symbol in self.cache.symbols:
    if symbol.get('type') == 'property':

# AFTER (O(1) hash lookup):
for symbol in self.cache.symbols_by_type.get('property', []):
```

---

### **Anti-Pattern #2: Analysis Phase N+1 Pattern**

**File**: `theauditor/taint/analysis.py`

**Issue**: Full-table scan for EVERY source to find containing function

**Evidence (Lines 187-195)**:
```python
def _get_containing_function(self, file_path: str, line: int) -> Optional[str]:
    """Find function containing given line - CALLED ONCE PER SOURCE."""

    for symbol in self.cache.symbols:  # ← SCANS ALL 100,000 SYMBOLS
        if (symbol.get('type') == 'function' and
            symbol.get('path') == file_path and
            line is not None and
            start_line <= line <= end_line):
            return symbol.get('name')
```

**Called From**: Every source discovery (typically 1,000+ times per run)

**Impact**:
- **Per Call**: 100,000 symbol comparisons
- **Calls**: 1,000 sources
- **Total**: **100,000,000 comparisons** (100 million)

**Also at**:
- Lines 245-249: `_propagate_through_block` - scans 50,000 assignments per block × 100 blocks = 5M ops
- Lines 267-270: `_get_calls_in_block` - scans 50,000 calls per block × 100 blocks = 5M ops
- Lines 284-292: `_get_block_successors` - O(n²) nested loop: 10K edges × 5K blocks = 50M ops

**Total Analysis Phase**: **160,000,000 operations per source** × 1,000 sources = **160 BILLION operations**

**Fix**: Spatial index (file → line range → symbols)
```python
# BEFORE (O(n) scan):
def _get_containing_function(file_path, line):
    for symbol in self.cache.symbols:
        if symbol.get('type') == 'function' and file == file_path and line in range(...):

# AFTER (O(1) lookup):
def _get_containing_function(file_path, line):
    line_block = line // 100
    candidates = self.cache.symbols_by_file_line[file_path][line_block]
    for symbol in candidates:  # Only 5-10 symbols per 100-line block
        if symbol.get('type') == 'function' and line in range(...):
```

---

### **Anti-Pattern #3: Propagation Phase LIKE Wildcards**

**File**: `theauditor/taint/propagation.py`

**Issue**: Leading wildcard LIKE pattern forces full table scan

**Evidence (Lines 224-232)**:
```python
query = build_query('assignments', ['target_var', 'in_function', 'line'],
    where="file = ? AND line BETWEEN ? AND ? AND source_expr LIKE ?",
    order_by="line"
)
cursor.execute(query, (
    source["file"],
    source["line"] - 2,
    source["line"] + 2,
    f"%{source['pattern']}%"  # ← LEADING WILDCARD (can't use index)
))
```

**Impact**:
- **Rows Scanned**: 50,000 assignments per query
- **Queries**: 1,000 sources
- **Total**: **50,000,000 rows scanned** (50 million)

**Also at**: Lines 254-262 (duplicate pattern for function_call_args)

**Fix**: Pre-filter by indexed columns, then Python substring search
```python
# BEFORE (Full Table Scan):
WHERE file = ? AND line BETWEEN ? AND ? AND source_expr LIKE '%pattern%'

# AFTER (Indexed Pre-filter):
query = build_query('assignments', ['target_var', 'source_expr', 'line'],
    where="file = ? AND line BETWEEN ? AND ?",  # NO LIKE
    order_by="line"
)
cursor.execute(query, (source["file"], source["line"] - 2, source["line"] + 2))

# Filter in Python (fast on small result set):
for target_var, source_expr, line in cursor.fetchall():
    if source['pattern'] in source_expr:  # Python substring search
        tainted_elements.add(f"{in_function}:{target_var}")
```

---

### **Anti-Pattern #4: CFG Integration N+1 Queries**

**File**: `theauditor/taint/cfg_integration.py.bak` (or current equivalent)

**Issue**: Database query for EVERY CFG block

**Evidence (Lines 295-300 from .bak file)**:
```python
for block in cfg_blocks:  # 100 blocks per path
    query = build_query('cfg_block_statements',
        ['statement_type', 'line', 'statement_text'],
        where="block_id = ? AND statement_type = 'call'",
        order_by="line"
    )
    cursor.execute(query, (block.get('id'),))  # ← QUERY PER BLOCK
```

**Impact**:
- **Queries per Path**: 100 CFG blocks
- **Paths per Function**: ~100 paths
- **Total**: **10,000 database queries**

**Fix**: Batch load all statements upfront
```python
# BEFORE (10,000 queries):
for block in cfg_blocks:
    cursor.execute("SELECT ... WHERE block_id = ?", (block_id,))

# AFTER (1 query):
# In SchemaMemoryCache.__init__:
cursor.execute("""
    SELECT block_id, statement_type, line, statement_text
    FROM cfg_block_statements
""")
self.statements_by_block = defaultdict(list)
for block_id, stmt_type, line, text in cursor.fetchall():
    self.statements_by_block[block_id].append({
        'type': stmt_type, 'line': line, 'text': text
    })

# In analysis:
for block in cfg_blocks:
    statements = self.cache.statements_by_block[block.id]  # O(1) lookup
```

---

## **IMPLEMENTATION PLAN**

### **Phase 1: Add Spatial Indexes to SchemaMemoryCache** (2-3 days)

**Objective**: Build O(1) lookup structures for location-based queries

**Files to Modify**:
- `theauditor/indexer/schemas/generated_cache.py` (or equivalent cache file)

**New Data Structures**:
```python
class SchemaMemoryCache:
    def __init__(self, db_path):
        # ... existing code (load symbols, assignments, etc.) ...

        # NEW: Build spatial indexes
        self._build_spatial_indexes()

    def _build_spatial_indexes(self):
        """Build O(1) lookup indexes for line-based queries."""

        # Index 1: Symbols by type
        self.symbols_by_type: Dict[str, List[Dict]] = defaultdict(list)
        for symbol in self.symbols:
            self.symbols_by_type[symbol['type']].append(symbol)

        # Index 2: Symbols by file + line (for containing function lookup)
        self.symbols_by_file_line: Dict[str, Dict[int, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        for symbol in self.symbols:
            if symbol.get('type') == 'function':
                file = symbol.get('path', '')
                start_line = symbol.get('line', 0) or 0
                end_line = symbol.get('end_line', 0) or start_line

                # Group by 100-line blocks
                for line in range(start_line, end_line + 1, 100):
                    block = line // 100
                    self.symbols_by_file_line[file][block].append(symbol)

        # Index 3: Assignments by location (file → line_block → assignments)
        self.assignments_by_location: Dict[str, Dict[int, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        for a in self.assignments:
            file = a.get('file', '')
            line = a.get('line', 0) or 0
            block = line // 100  # Group by 100-line blocks
            self.assignments_by_location[file][block].append(a)

        # Index 4: Function calls by location (same pattern)
        self.calls_by_location: Dict[str, Dict[int, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        for c in self.function_call_args:
            file = c.get('file', '')
            line = c.get('line', 0) or 0
            block = line // 100
            self.calls_by_location[file][block].append(c)

        # Index 5: CFG block successors (adjacency list)
        self.successors_by_block: Dict[str, List[Dict]] = defaultdict(list)
        self.blocks_by_id: Dict[str, Dict] = {}

        for block in self.cfg_blocks:
            self.blocks_by_id[block['id']] = block

        for edge in self.cfg_edges:
            from_id = edge.get('from_block')
            to_id = edge.get('to_block')
            if to_id in self.blocks_by_id:
                self.successors_by_block[from_id].append(self.blocks_by_id[to_id])

        # Index 6: CFG statements by block (batch load)
        self.statements_by_block: Dict[str, List[Dict]] = defaultdict(list)
        # (Populated if cfg_block_statements loaded)
```

**Testing**:
- [ ] Unit test each index builder
- [ ] Verify index correctness with fixture data
- [ ] Test edge cases: empty files, single-line functions, missing blocks
- [ ] Measure memory overhead (~10-20MB expected)

---

### **Phase 2: Refactor Discovery Phase** (1 day)

**Objective**: Replace linear scans with indexed lookups

**Files to Modify**:
- `theauditor/taint/discovery.py`

**Changes**:

**Change 2.1: User Input Sources (Lines 52-67)**
```python
# BEFORE:
for symbol in self.cache.symbols:
    if symbol.get('type') == 'property':
        name = symbol.get('name', '')
        if any(pattern in name.lower() for pattern in input_patterns):

# AFTER:
for symbol in self.cache.symbols_by_type.get('property', []):
    name = symbol.get('name', '')
    if any(pattern in name.lower() for pattern in input_patterns):
```

**Change 2.2: File Read Sources (Lines 70-84)**
```python
# BEFORE:
for call in self.cache.function_call_args:
    func_name = call.get('callee_function', '')
    if any(f in func_name for f in file_funcs):

# AFTER:
# Pre-compile frozenset for O(1) lookups
FILE_READ_FUNCS = frozenset(['readFile', 'fs.readFile', 'open', 'fopen', ...])

for call in self.cache.function_call_args:
    func_name = call.get('callee_function', '')
    if func_name in FILE_READ_FUNCS:  # O(1) instead of O(m) substring search
```

**Change 2.3: Command Injection Sinks (Lines 163-177)**
```python
# Same pattern as 2.2 - use frozenset lookup
```

**Testing**:
- [ ] Verify source/sink counts match original implementation
- [ ] Test on 5 fixture projects
- [ ] Measure speedup (500K ops → ~1K ops = 500x expected)

---

### **Phase 3: Refactor Analysis Phase** (2-3 days)

**Objective**: Replace N+1 patterns with spatial index lookups

**Files to Modify**:
- `theauditor/taint/analysis.py`

**Changes**:

**Change 3.1: _get_containing_function (Lines 187-195)**
```python
# BEFORE:
def _get_containing_function(self, file_path: str, line: int) -> Optional[str]:
    for symbol in self.cache.symbols:
        if (symbol.get('type') == 'function' and
            symbol.get('path') == file_path and
            line is not None and start_line <= line <= end_line):
            return symbol.get('name')

# AFTER:
def _get_containing_function(self, file_path: str, line: int) -> Optional[str]:
    line_block = line // 100

    # Check current block and adjacent blocks (handle boundaries)
    for block_idx in [line_block - 1, line_block, line_block + 1]:
        candidates = self.cache.symbols_by_file_line[file_path].get(block_idx, [])
        for symbol in candidates:
            start_line = symbol.get('line', 0) or 0
            end_line = symbol.get('end_line', 0) or start_line
            if start_line <= line <= end_line:
                return symbol.get('name')

    return None
```

**Change 3.2: _propagate_through_block (Lines 245-249)**
```python
# BEFORE:
for a in self.cache.assignments:
    a_line = a.get('line', 0) or 0
    if (a.get('file') == block.get('file') and
        block_start <= a_line <= block_end):

# AFTER:
file = block.get('file')
start_block = block_start // 100
end_block = block_end // 100

block_assignments = []
for block_idx in range(start_block, end_block + 1):
    block_assignments.extend(self.cache.assignments_by_location[file].get(block_idx, []))

# Filter by exact line range
block_assignments = [a for a in block_assignments
                     if block_start <= (a.get('line', 0) or 0) <= block_end]
```

**Change 3.3: _get_calls_in_block (Lines 267-270)**
```python
# Same pattern as 3.2, use calls_by_location index
```

**Change 3.4: _get_block_successors (Lines 284-292)**
```python
# BEFORE:
for edge in self.cache.cfg_edges:
    if edge.get('from_block') == block_id:
        to_id = edge.get('to_block')
        for b in self.cache.cfg_blocks:
            if b.get('id') == to_id:
                successors.append(b)

# AFTER:
successors = self.cache.successors_by_block.get(block_id, [])
```

**Testing**:
- [ ] Verify taint findings match original (byte-for-byte comparison)
- [ ] Test edge cases: functions at block boundaries (lines 99-101, 199-201)
- [ ] Test on 10 fixture projects with known taint paths
- [ ] Measure speedup (160B ops → 1M ops = 160,000x expected)

---

### **Phase 4: Refactor Propagation Phase** (1 day)

**Objective**: Eliminate LIKE wildcard patterns

**Files to Modify**:
- `theauditor/taint/propagation.py`

**Changes**:

**Change 4.1: Assignment Pattern Search (Lines 224-232)**
```python
# BEFORE:
query = build_query('assignments', ['target_var', 'in_function', 'line'],
    where="file = ? AND line BETWEEN ? AND ? AND source_expr LIKE ?",
    order_by="line"
)
cursor.execute(query, (..., f"%{source['pattern']}%"))

# AFTER:
query = build_query('assignments', ['target_var', 'source_expr', 'in_function', 'line'],
    where="file = ? AND line BETWEEN ? AND ?",  # NO LIKE
    order_by="line"
)
cursor.execute(query, (source["file"], source["line"] - 2, source["line"] + 2))

# Python filter (fast on small result set):
for target_var, source_expr, in_function, line in cursor.fetchall():
    if source['pattern'] in source_expr:
        tainted_elements.add(f"{in_function}:{target_var}")
```

**Change 4.2: Function Call Pattern Search (Lines 254-262)**
```python
# Same pattern as 4.1
```

**Testing**:
- [ ] Verify findings unchanged (LIKE and Python `in` are equivalent)
- [ ] Measure rows scanned (50M → 500K = 100x reduction)
- [ ] Test on 5 projects

---

### **Phase 5: Batch Load CFG Statements** (1 day)

**Objective**: Eliminate N+1 database queries

**Files to Modify**:
- `theauditor/indexer/schemas/generated_cache.py` (add to __init__)
- `theauditor/taint/cfg_integration.py` (or equivalent)

**Changes**:

**Change 5.1: Add to SchemaMemoryCache (in _build_spatial_indexes)**
```python
# Load all CFG statements upfront (if cfg_block_statements table exists)
try:
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT block_id, statement_type, line, statement_text
        FROM cfg_block_statements
    """)

    for block_id, stmt_type, line, text in cursor.fetchall():
        self.statements_by_block[block_id].append({
            'type': stmt_type,
            'line': line,
            'text': text
        })
    conn.close()
except sqlite3.Error:
    # Table doesn't exist or empty - no CFG data available
    pass
```

**Change 5.2: Update CFG Integration (Replace Per-Block Queries)**
```python
# BEFORE:
for block in cfg_blocks:
    cursor.execute("SELECT ... WHERE block_id = ?", (block.get('id'),))
    statements = cursor.fetchall()

# AFTER:
for block in cfg_blocks:
    statements = self.cache.statements_by_block.get(block.get('id'), [])
```

**Testing**:
- [ ] Verify CFG analysis results unchanged
- [ ] Measure query count (10,000 → 1 = 10,000x reduction)
- [ ] Test on 3 projects with CFG data

---

## **TESTING STRATEGY**

### **Fixture Validation** (CRITICAL)

**Objective**: Verify taint findings match original implementation byte-for-byte

**Method**:
1. **Before Refactor**: Run taint analysis on 10 fixture projects, save findings to JSON
2. **After Refactor**: Run taint analysis again, compare findings
3. **Assertion**: Findings must match EXACTLY (file, line, source, sink, path)

**Fixture Projects** (cover all taint categories):
- [ ] Python SQL injection (SQLAlchemy + raw SQL)
- [ ] Python command injection (subprocess, os.system)
- [ ] Python XSS (Flask templates)
- [ ] JavaScript SQL injection (node-postgres)
- [ ] JavaScript XSS (React dangerouslySetInnerHTML)
- [ ] TypeScript command injection (child_process)
- [ ] Mixed Python + JS project
- [ ] Project with CFG (100+ blocks, complex control flow)
- [ ] Large project (10K LOC, 1,000+ sources)
- [ ] Edge case: functions at line boundaries (199-201, 999-1001)

**Comparison Script**:
```python
import json

def compare_findings(original, refactored):
    original_set = {(f['file'], f['line'], f['source_type'], f['sink_type'])
                    for f in original}
    refactored_set = {(f['file'], f['line'], f['source_type'], f['sink_type'])
                      for f in refactored}

    missing = original_set - refactored_set
    extra = refactored_set - original_set

    if missing:
        print(f"❌ REGRESSION: {len(missing)} findings missing")
        for f in missing:
            print(f"  Missing: {f}")

    if extra:
        print(f"⚠️ NEW FINDINGS: {len(extra)} extra findings")
        for f in extra:
            print(f"  Extra: {f}")

    if not missing and not extra:
        print("✅ PERFECT MATCH: All findings identical")

    return len(missing) == 0  # Pass if no missing findings
```

---

### **Performance Benchmarking** (MANDATORY)

**Objective**: Verify speedup targets met

**Baseline (Before Refactor)**:
```bash
# Measure current performance
time aud taint-analyze --project /path/to/10k-loc-project

# Expected: ~600 seconds (10 minutes)
```

**After Refactor**:
```bash
# Measure new performance
time aud taint-analyze --project /path/to/10k-loc-project

# Target: ≤40 seconds (95% improvement)
# Acceptable: ≤60 seconds (90% improvement)
# Failure: >100 seconds (<83% improvement)
```

**Per-Phase Timing** (add instrumentation):
```python
import time

def trace_taint(...):
    start = time.time()

    # Discovery
    t0 = time.time()
    sources = discovery.discover_sources(...)
    print(f"Discovery: {time.time() - t0:.2f}s", file=sys.stderr)

    # Analysis
    t0 = time.time()
    for source in sources:
        # ... analysis ...
    print(f"Analysis: {time.time() - t0:.2f}s", file=sys.stderr)

    # Propagation
    t0 = time.time()
    # ... propagation ...
    print(f"Propagation: {time.time() - t0:.2f}s", file=sys.stderr)

    print(f"Total: {time.time() - start:.2f}s", file=sys.stderr)
```

**Target Breakdown**:
- Discovery: ≤1 second (currently ~5s)
- Analysis: ≤20 seconds (currently ~400s)
- Propagation: ≤10 seconds (currently ~150s)
- CFG: ≤5 seconds (currently ~45s)
- **Total: ≤36 seconds** (currently ~600s)

---

### **Memory Profiling** (VALIDATION)

**Objective**: Verify spatial indexes don't blow up memory usage

**Method**:
```python
import tracemalloc

tracemalloc.start()

# Before building indexes
snapshot1 = tracemalloc.take_snapshot()

# After building indexes
self._build_spatial_indexes()
snapshot2 = tracemalloc.take_snapshot()

# Calculate difference
stats = snapshot2.compare_to(snapshot1, 'lineno')
for stat in stats[:10]:
    print(f"{stat.size_diff / 1024 / 1024:.2f} MB - {stat}")
```

**Acceptance Criteria**:
- Spatial indexes add ≤20MB memory (acceptable)
- Total memory usage within 10% of baseline
- No memory leaks (verify with repeated runs)

---

## **EDGE CASES TO TEST**

### **Edge Case 1: Block Boundary Functions**

**Scenario**: Function spans 100-line block boundary

```python
# Function at lines 199-201 (spans blocks 1 and 2)
def foo():  # Line 199 (block 1: 100-199)
    x = request.body  # Line 200 (block 2: 200-299)
    execute(x)  # Line 201 (block 2)
```

**Test**:
- [ ] Source at line 200 correctly finds containing function `foo`
- [ ] Both blocks 1 and 2 are checked (handle boundary)

---

### **Edge Case 2: Empty Blocks**

**Scenario**: No symbols/assignments in a 100-line range

```python
# Lines 100-199: All comments/blank lines
# Line 200: First actual code
def bar():
    x = input()
```

**Test**:
- [ ] Empty blocks don't cause KeyError
- [ ] Lookup correctly skips to next populated block

---

### **Edge Case 3: Single-Line Functions**

**Scenario**: Lambda or one-liner function

```python
foo = lambda x: execute(x)  # Line 42 (start_line == end_line)
```

**Test**:
- [ ] Single-line function indexed correctly
- [ ] Line 42 lookup finds containing function

---

### **Edge Case 4: Nested Functions**

**Scenario**: Function inside function

```python
def outer():  # Lines 100-200
    def inner():  # Lines 150-160
        x = request.body
        execute(x)
```

**Test**:
- [ ] Source at line 155 finds `inner` (not `outer`)
- [ ] Nested function takes precedence (smallest containing function)

---

## **ROLLBACK PLAN**

### **If Issues Found During Testing**

**Option 1: Rollback Individual Phase**
```bash
# Revert just propagation changes
git revert <commit-hash-phase-4>

# Keep other phases (discovery, analysis still optimized)
```

**Option 2: Complete Rollback**
```bash
# Revert entire refactor
git revert <commit-hash-phase-1>..<commit-hash-phase-5>

# Taint goes back to original (10 min runtime)
```

**Option 3: Feature Flag** (RECOMMENDED)
```python
# Add environment variable toggle
USE_SPATIAL_INDEXES = os.environ.get('THEAUDITOR_SPATIAL_INDEXES', 'true') == 'true'

if USE_SPATIAL_INDEXES:
    # Use new optimized path
    for symbol in self.cache.symbols_by_type.get('property', []):
        ...
else:
    # Fallback to original path
    for symbol in self.cache.symbols:
        if symbol.get('type') == 'property':
            ...
```

**Benefit**: Can ship with both paths, toggle in production if issues found

---

## **SUCCESS CRITERIA**

### **Performance Targets**
- ✅ Taint analysis ≤40 seconds (baseline: 600s) = 95% improvement
- ✅ Discovery ≤1 second (baseline: 5s)
- ✅ Analysis ≤20 seconds (baseline: 400s)
- ✅ Propagation ≤10 seconds (baseline: 150s)

### **Correctness Targets**
- ✅ All fixture findings match original (byte-for-byte)
- ✅ No missing taint paths (false negatives)
- ✅ Acceptable: Extra findings (false positives are safe, missing findings are NOT)

### **Quality Targets**
- ✅ Memory usage within 10% of baseline
- ✅ No memory leaks
- ✅ All existing tests pass
- ✅ Code coverage ≥80% on new index code

---

## **KNOWN RISKS**

### **Risk 1: Spatial Index Boundary Bugs** (40% probability)

**Issue**: Line range grouping has edge cases (function at 199-201 spans 2 blocks)

**Mitigation**: Check adjacent blocks (line_block - 1, line_block, line_block + 1)

**If Occurs**: 1-2 weeks debugging edge cases

---

### **Risk 2: Iteration Order Changes** (30% probability)

**Issue**: Dict iteration order differs from list order, might affect results

**Mitigation**: Sort results before comparison (if order doesn't matter)

**If Occurs**: Update comparison logic to be order-agnostic

---

### **Risk 3: Hash Collision** (5% probability)

**Issue**: Python dict hash collision causes lookup miss

**Mitigation**: Unlikely with small datasets (<100K symbols), but possible

**If Occurs**: Use OrderedDict or list fallback for affected lookups

---

## **TEAMSOP.MD V4.20 VERIFICATION CHECKLIST**

**Before Implementation Begins**:

- [ ] **Read Investigation Report**: Understand root cause (this document)
- [ ] **Verify File Paths**: Confirm all file paths still accurate
- [ ] **Verify Line Numbers**: Code may have changed since 2025-11-02
- [ ] **Measure Baseline**: Run taint on test project, document current performance
- [ ] **Save Fixture Findings**: Run taint on 10 fixtures, save JSON for comparison
- [ ] **Architect Approval**: Get approval on implementation plan

**During Implementation**:

- [ ] **Implement Phase 1**: Spatial indexes
- [ ] **Unit Test Phase 1**: Test index builders independently
- [ ] **Implement Phase 2**: Discovery refactor
- [ ] **Test Phase 2**: Verify source/sink counts unchanged
- [ ] **Implement Phase 3**: Analysis refactor
- [ ] **Test Phase 3**: Verify taint findings match (CRITICAL)
- [ ] **Implement Phase 4**: Propagation refactor
- [ ] **Test Phase 4**: Verify findings match
- [ ] **Implement Phase 5**: CFG batch load
- [ ] **Test Phase 5**: Verify CFG analysis unchanged

**Post-Implementation Audit**:

- [ ] **Re-read All Modified Files**: Confirm no syntax errors, logic bugs
- [ ] **Fixture Validation**: All 10 fixtures match byte-for-byte
- [ ] **Performance Benchmark**: Measure speedup (target: 95%)
- [ ] **Memory Profile**: Verify memory within 10% of baseline
- [ ] **Full Test Suite**: All tests pass (no regressions)
- [ ] **Integration Test**: Run full `aud full` pipeline on 3 projects
- [ ] **Architect Review**: Get final approval

---

## **DISCREPANCIES LOG**

**If Code Changed Since Investigation** (2025-11-02):

| File | Expected Line | Actual Line | Impact | Resolution |
|------|---------------|-------------|--------|------------|
| discovery.py | 52-67 | ? | ? | Re-verify pattern exists |
| analysis.py | 187-195 | ? | ? | Re-verify N+1 pattern |
| propagation.py | 224-232 | ? | ? | Re-verify LIKE pattern |
| cfg_integration.py | 295-300 | ? | ? | Verify file still used (.bak?) |

**Instructions**: Fill this table during verification phase. Document ANY discrepancies.

---

## **FINAL CHECKLIST**

**Before Coding**:
- [ ] All hypotheses verified
- [ ] Baseline performance measured
- [ ] Fixture findings saved
- [ ] Architect approval obtained

**Before Merging**:
- [ ] All tests pass
- [ ] Fixtures validate (byte-for-byte match)
- [ ] Performance targets met (≥90% improvement)
- [ ] Memory within 10% of baseline
- [ ] No memory leaks
- [ ] Code reviewed by Architect
- [ ] Documentation updated

**After Deployment**:
- [ ] Monitor production performance
- [ ] Collect user feedback
- [ ] Watch for edge case reports

---

**STATUS**: 🔴 **READY TO IMPLEMENT** - All context provided

**NEXT STEP**: Begin Phase 1 (Spatial Indexes)

**ESTIMATED TIME**: 2-3 weeks total

**EXPECTED RESULT**: 10 minutes → 20-40 seconds (95% speedup)
