# Taint Analysis Spatial Index Implementation Tasks

**CRITICAL**: Do NOT start implementation until:
1. ✅ Architect approves `proposal.md`
2. ✅ Verification phase completed (see `verification.md`)
3. ✅ Architect approves verification findings

---

## 0. Verification Phase (MANDATORY - Complete Before Coding)

**Objective**: Verify all assumptions from INVESTIGATION_REPORT.md by reading actual code

- [ ] 0.1 **Read Investigation Report** - Fully digest `performance-revolution-now/INVESTIGATION_REPORT.md` sections 2.1-2.4
- [ ] 0.2 **Read Design Document** - Understand architectural decisions in `design.md`
- [ ] 0.3 **Execute Verification Protocol** - Follow `verification.md` step-by-step
- [ ] 0.4 **Document Findings** - Record all discrepancies in `verification.md`
- [ ] 0.5 **Get Architect Approval** - Architect must approve verification before continuing

**Status**: ⚠️ **BLOCKING** - No implementation may proceed until this section is checked

---

## 1. Add Spatial Indexes to SchemaMemoryCache

**Objective**: Eliminate 165M-20B operations → 1 MILLION (100-1000x reduction)

**Estimated Time**: 3-4 days implementation + 1-2 days testing

### 1.1 Read and Understand Current Cache Structure
- [ ] 1.1.1 Read `theauditor/indexer/schemas/generated_cache.py`
  - Verify current cache structure
  - Confirm no existing spatial indexes
  - Understand how cache is built from database
- [ ] 1.1.2 Read `theauditor/taint/schema_cache_adapter.py`
  - Understand memory cache interface
  - Identify where spatial indexes will be accessed
- [ ] 1.1.3 Document current data flow
  - How does data flow from database → cache → taint analysis?
  - Where are the bottlenecks?

### 1.2 Design Spatial Index Data Structures
- [ ] 1.2.1 Design `symbols_by_type` index
  ```python
  symbols_by_type: Dict[str, List[Dict]]
  # Example: {'property': [...], 'function': [...], 'class': [...]}
  ```
- [ ] 1.2.2 Design `symbols_by_file_line` spatial index
  ```python
  symbols_by_file_line: Dict[str, Dict[int, List[Dict]]]
  # Example: {'src/main.py': {0: [...], 100: [...], 200: [...]}}
  # Key is file path, value is dict of line_block (rounded to 100) → symbols
  ```
- [ ] 1.2.3 Design `assignments_by_location` spatial index
  ```python
  assignments_by_location: Dict[str, Dict[int, List[Dict]]]
  # Same structure as symbols_by_file_line
  # Groups assignments by file + 100-line blocks
  ```
- [ ] 1.2.4 Design `calls_by_location` spatial index
  ```python
  calls_by_location: Dict[str, Dict[int, List[Dict]]]
  # Groups function_call_args by file + 100-line blocks
  ```
- [ ] 1.2.5 Design `successors_by_block` adjacency list
  ```python
  successors_by_block: Dict[str, List[Dict]]
  # Maps CFG block_id → list of successor blocks
  # Eliminates O(n²) nested loop in _get_block_successors
  ```
- [ ] 1.2.6 Design `blocks_by_id` lookup table
  ```python
  blocks_by_id: Dict[str, Dict]
  # Maps block_id → block dict (O(1) lookup)
  ```

### 1.3 Implement Index Builders in generated_cache.py
- [ ] 1.3.1 Add `_build_spatial_indexes()` method to `SchemaMemoryCache`
  ```python
  def _build_spatial_indexes(self):
      """Build all spatial indexes after loading base data."""
      self._build_symbols_by_type()
      self._build_symbols_by_file_line()
      self._build_assignments_by_location()
      self._build_calls_by_location()
      self._build_cfg_adjacency_lists()
  ```
- [ ] 1.3.2 Implement `_build_symbols_by_type()`
  - Iterate through self.symbols
  - Group by symbol['type']
  - Store in self.symbols_by_type
- [ ] 1.3.3 Implement `_build_symbols_by_file_line()`
  - Iterate through self.symbols
  - Group by file and line_block (line // 100 * 100)
  - Store in self.symbols_by_file_line
- [ ] 1.3.4 Implement `_build_assignments_by_location()`
  - Iterate through self.assignments
  - Group by file and line_block
  - Store in self.assignments_by_location
- [ ] 1.3.5 Implement `_build_calls_by_location()`
  - Iterate through self.function_call_args
  - Group by file and line_block
  - Store in self.calls_by_location
- [ ] 1.3.6 Implement `_build_cfg_adjacency_lists()`
  - Iterate through self.cfg_edges
  - Build successors_by_block: block_id → [successor_blocks]
  - Build blocks_by_id: block_id → block
- [ ] 1.3.7 Call `_build_spatial_indexes()` from `__init__`
  - After loading base data from database
  - Before returning to caller

### 1.4 Add Unit Tests for Index Builders
- [ ] 1.4.1 Test `symbols_by_type` with fixture data
  - Create minimal fixture with 3 symbol types
  - Verify grouping correctness
  - Verify O(1) lookup time
- [ ] 1.4.2 Test `symbols_by_file_line` spatial lookup
  - Create fixture with symbols at lines 50, 150, 250
  - Verify correct line_block grouping (0, 100, 200)
  - Test edge case: line 100 should map to block 100, not 0
- [ ] 1.4.3 Test spatial lookup correctness
  - Query for symbols in line range 140-160
  - Should return symbols from blocks 100 and 200
  - Verify no false negatives
- [ ] 1.4.4 Test edge cases
  - Empty files (no symbols)
  - Missing blocks (None handling)
  - Very large line numbers (>10,000)

---

## 2. Refactor Discovery Phase (discovery.py)

**Objective**: Replace linear scans with indexed lookups (500-1000x improvement)

**Estimated Time**: 1 day

### 2.1 Read and Verify Current Linear Scan Pattern
- [ ] 2.1.1 Read `theauditor/taint/discovery.py:52-84`
  - Verify current linear scan pattern
  - Identify all source/sink discovery loops
  - Document current operation count (estimated 500K operations)
- [ ] 2.1.2 Measure baseline performance
  - Profile discovery phase with cProfile
  - Count iterations per loop
  - Document hotspots

### 2.2 Replace User Input Source Discovery (lines 52-67)
- [ ] 2.2.1 Locate code:
  ```python
  # BEFORE (lines 52-67):
  for symbol in self.cache.symbols:
      if symbol.get('type') == 'property':
          # Extract user input source
  ```
- [ ] 2.2.2 Replace with indexed lookup:
  ```python
  # AFTER:
  for symbol in self.cache.symbols_by_type.get('property', []):
      # Extract user input source
  ```
- [ ] 2.2.3 Verify output unchanged
  - Run on fixture project
  - Compare sources before/after (must match exactly)

### 2.3 Replace File Read Source Discovery (lines 70-84)
- [ ] 2.3.1 Locate code:
  ```python
  # BEFORE (lines 70-84):
  if 'readFile' in func_name or 'readFileSync' in func_name:
      # Extract file read source
  ```
- [ ] 2.3.2 Create frozenset of file read functions:
  ```python
  FILE_READ_FUNCTIONS = frozenset([
      'readFile', 'readFileSync', 'readdir', 'readdirSync',
      'open', 'read', 'readline', ...
  ])
  ```
- [ ] 2.3.3 Replace with frozenset lookup:
  ```python
  # AFTER:
  if func_name in FILE_READ_FUNCTIONS:
      # Extract file read source
  ```
- [ ] 2.3.4 Verify speedup
  - Measure string operations vs frozenset lookups
  - Expected: 10-100x faster

### 2.4 Replace Command Injection Sink Discovery (lines 163-177)
- [ ] 2.4.1 Locate code:
  ```python
  # BEFORE (lines 163-177):
  for call in self.cache.function_call_args:
      if call.get('callee_function') in COMMAND_INJECTION_SINKS:
          # Extract sink
  ```
- [ ] 2.4.2 Analyze if indexed lookup needed
  - If already using `in` operator with frozenset, no change needed
  - If doing string comparisons, add frozenset
- [ ] 2.4.3 Verify correctness
  - Test on fixture with known command injection sinks

### 2.5 Measure Speedup with Profiling
- [ ] 2.5.1 Profile discovery phase before/after
  - Use cProfile to measure function calls
  - Count operations: Before ~500K, After ~1K
  - Document 500x improvement
- [ ] 2.5.2 Verify no regressions
  - Run all taint tests: `pytest tests/test_taint*.py -v`
  - All tests must pass

---

## 3. Refactor Analysis Phase (analysis.py)

**Objective**: Replace N+1 patterns with spatial indexes (100,000-50,000,000x improvement)

**Estimated Time**: 2 days

### 3.1 Replace `_get_containing_function` (lines 187-195)
- [ ] 3.1.1 Read current implementation:
  ```python
  # BEFORE (lines 187-195):
  def _get_containing_function(self, file, line):
      for symbol in self.cache.symbols:
          if symbol.get('type') == 'function':
              if symbol.get('file') == file:
                  if symbol.get('start_line') <= line <= symbol.get('end_line'):
                      return symbol
      return None
  ```
  - Confirm called once per source (~1,000 times)
  - Calculate operation count: 1,000 calls × 100K symbols = 100M comparisons
- [ ] 3.1.2 Replace with spatial index:
  ```python
  # AFTER:
  def _get_containing_function(self, file, line):
      line_block = (line // 100) * 100
      # Check current block and adjacent blocks (line might span blocks)
      for block_offset in [0, -100, 100]:
          block = line_block + block_offset
          if block < 0:
              continue
          symbols = self.cache.symbols_by_file_line.get(file, {}).get(block, [])
          for symbol in symbols:
              if symbol.get('type') == 'function':
                  if symbol.get('start_line') <= line <= symbol.get('end_line'):
                      return symbol
      return None
  ```
- [ ] 3.1.3 Verify correctness
  - Test edge case: function spanning line 95-105 (crosses block boundary)
  - Test with fixture projects
  - Compare results before/after (must match exactly)
- [ ] 3.1.4 Measure speedup
  - Before: 100M comparisons
  - After: ~1K lookups
  - Document 100,000x improvement

### 3.2 Replace `_propagate_through_block` (lines 245-249)
- [ ] 3.2.1 Read current implementation:
  ```python
  # BEFORE (lines 245-249):
  def _propagate_through_block(self, block):
      tainted = set()
      for assignment in self.cache.assignments:
          if assignment.get('file') == block.file:
              if block.start_line <= assignment.get('line') <= block.end_line:
                  # Propagate taint
      return tainted
  ```
  - Confirm called ~500 times (once per block)
  - Calculate: 500 calls × 1M assignments = 500M comparisons
- [ ] 3.2.2 Replace with spatial index:
  ```python
  # AFTER:
  def _propagate_through_block(self, block):
      tainted = set()
      start_block = (block.start_line // 100) * 100
      end_block = (block.end_line // 100) * 100
      for block_num in range(start_block, end_block + 100, 100):
          assignments = self.cache.assignments_by_location.get(block.file, {}).get(block_num, [])
          for assignment in assignments:
              if block.start_line <= assignment.get('line') <= block.end_line:
                  # Propagate taint
      return tainted
  ```
- [ ] 3.2.3 Verify correctness with fixtures
- [ ] 3.2.4 Measure speedup: 500M → 500K (1,000x improvement)

### 3.3 Replace `_get_calls_in_block` (lines 267-270)
- [ ] 3.3.1 Read current implementation:
  ```python
  # BEFORE (lines 267-270):
  def _get_calls_in_block(self, block):
      calls = []
      for call in self.cache.function_call_args:
          if call.get('file') == block.file:
              if block.start_line <= call.get('line') <= block.end_line:
                  calls.append(call)
      return calls
  ```
  - Calculate: 500 calls × 1M function_call_args = 500M comparisons
- [ ] 3.3.2 Replace with spatial index:
  ```python
  # AFTER:
  def _get_calls_in_block(self, block):
      calls = []
      start_block = (block.start_line // 100) * 100
      end_block = (block.end_line // 100) * 100
      for block_num in range(start_block, end_block + 100, 100):
          block_calls = self.cache.calls_by_location.get(block.file, {}).get(block_num, [])
          for call in block_calls:
              if block.start_line <= call.get('line') <= block.end_line:
                  calls.append(call)
      return calls
  ```
- [ ] 3.3.3 Verify correctness with fixtures
- [ ] 3.3.4 Measure speedup: 500M → 500K (1,000x improvement)

### 3.4 Replace `_get_block_successors` (lines 284-292)
- [ ] 3.4.1 Read current O(n²) implementation:
  ```python
  # BEFORE (lines 284-292):
  def _get_block_successors(self, block_id):
      successors = []
      for edge in self.cache.cfg_edges:
          if edge.get('from_block') == block_id:
              for block in self.cache.cfg_blocks:
                  if block.get('id') == edge.get('to_block'):
                      successors.append(block)
      return successors
  ```
  - Calculate: 100 paths × 500 blocks × 1000 edges = 50M comparisons
- [ ] 3.4.2 Replace with adjacency list:
  ```python
  # AFTER:
  def _get_block_successors(self, block_id):
      successor_ids = self.cache.successors_by_block.get(block_id, [])
      successors = []
      for succ_id in successor_ids:
          block = self.cache.blocks_by_id.get(succ_id)
          if block:
              successors.append(block)
      return successors
  ```
- [ ] 3.4.3 Verify correctness
  - Test on fixture with known CFG structure
  - Verify all paths found
- [ ] 3.4.4 Measure speedup: 50M → O(1) lookups (50,000,000x improvement)

---

## 4. Refactor Propagation Phase (propagation.py)

**Objective**: Replace LIKE wildcard patterns (100x improvement)

**Estimated Time**: 4 hours

### 4.1 Fix Source Expression LIKE Pattern (lines 224-232)
- [ ] 4.1.1 Read current query:
  ```python
  # BEFORE (lines 224-232):
  cursor.execute("""
      SELECT * FROM taint_sources
      WHERE file = ? AND line BETWEEN ? AND ?
        AND source_expr LIKE '%{pattern}%'
  """, (file, start_line, end_line))
  ```
  - Confirm called ~1,000 times (once per source)
  - LIKE wildcard scans 50M rows total
- [ ] 4.1.2 Replace with indexed pre-filter + Python search:
  ```python
  # AFTER:
  cursor.execute("""
      SELECT * FROM taint_sources
      WHERE file = ? AND line BETWEEN ? AND ?
  """, (file, start_line, end_line))
  rows = cursor.fetchall()
  # Filter in Python
  filtered = [row for row in rows if pattern in row['source_expr']]
  ```
- [ ] 4.1.3 Verify correctness
  - Test on fixture with known taint patterns
  - Ensure no false negatives
- [ ] 4.1.4 Measure speedup: 50M rows scanned → 500K rows (100x improvement)

### 4.2 Fix Function Call Args LIKE Pattern (lines 254-262)
- [ ] 4.2.1 Read current query:
  ```python
  # BEFORE (lines 254-262):
  cursor.execute("""
      SELECT * FROM function_call_args
      WHERE callee_function LIKE '%{pattern}%'
  """, ())
  ```
- [ ] 4.2.2 Apply same fix as 4.1.2
  - Remove LIKE wildcard
  - Filter in Python with `in` operator
- [ ] 4.2.3 Verify correctness with fixtures

---

## 5. Batch Load CFG Statements

**Objective**: Eliminate 10,000 separate queries → 1 query (10,000x improvement)

**Estimated Time**: 3 hours

### 5.1 Read Current N+1 Query Pattern
- [ ] 5.1.1 Read `theauditor/taint/cfg_integration.py.bak:295-300`
  - Verify N+1 query pattern (query per CFG block)
  - Confirm called ~100 times per path (~10,000 total queries)
  - Document current implementation

### 5.2 Add Batch Load to SchemaMemoryCache.__init__
- [ ] 5.2.1 Add `statements_by_block` property:
  ```python
  self.statements_by_block: Dict[str, List[Dict]] = {}
  ```
- [ ] 5.2.2 Load all cfg_block_statements for function upfront:
  ```python
  def _load_cfg_statements(self, function_id):
      cursor.execute("""
          SELECT block_id, statement_line, statement_expr
          FROM cfg_block_statements
          WHERE function_id = ?
      """, (function_id,))
      for row in cursor.fetchall():
          block_id = row['block_id']
          if block_id not in self.statements_by_block:
              self.statements_by_block[block_id] = []
          self.statements_by_block[block_id].append(row)
  ```
- [ ] 5.2.3 Call from `__init__` or lazy-load on first access

### 5.3 Replace Per-Block Queries with Cache Lookup
- [ ] 5.3.1 Locate code making per-block queries
- [ ] 5.3.2 Replace:
  ```python
  # BEFORE (10,000 queries):
  cursor.execute("SELECT ... WHERE block_id = ?", (block_id,))
  statements = cursor.fetchall()

  # AFTER (1 query):
  statements = self.cache.statements_by_block.get(block_id, [])
  ```
- [ ] 5.3.3 Verify correctness with fixtures
- [ ] 5.3.4 Measure speedup: 10,000 queries → 1 query (10,000x improvement)

---

## 6. Testing & Validation

**Objective**: Ensure zero regressions and validate performance targets

**Estimated Time**: 1-2 days

### 6.1 Run Existing Taint Analysis Tests
- [ ] 6.1.1 Run full test suite:
  ```bash
  pytest tests/test_taint*.py -v
  ```
- [ ] 6.1.2 All tests must pass (zero regressions)
- [ ] 6.1.3 If any test fails:
  - Debug root cause
  - Fix implementation
  - Re-run tests
  - **DO NOT** proceed until all tests pass

### 6.2 Run Fixture-Based Validation
- [ ] 6.2.1 Test on 5 fixture projects:
  - `tests/fixtures/python/taint_simple` - Basic taint flow
  - `tests/fixtures/python/taint_complex` - Nested functions
  - `tests/fixtures/javascript/taint_xss` - XSS vulnerabilities
  - `tests/fixtures/mixed/taint_sql_injection` - SQL injection
  - Large project (~10K LOC)
- [ ] 6.2.2 Compare taint findings before/after:
  - Run taint analysis on old implementation → save results
  - Run taint analysis on new implementation → save results
  - Diff results (must match exactly except timing data)
- [ ] 6.2.3 Verify finding IDs unchanged
- [ ] 6.2.4 Verify paths unchanged
- [ ] 6.2.5 Document any discrepancies (should be none)

### 6.3 Performance Benchmarking
- [ ] 6.3.1 Measure taint analysis time on 10K LOC project:
  ```bash
  time aud taint-analyze
  ```
- [ ] 6.3.2 Document results:
  - Before: ~600 seconds (10 minutes) expected
  - After: ~20-40 seconds target
  - Actual speedup: ___ seconds (___x faster)
- [ ] 6.3.3 If speedup < 15x:
  - Profile with cProfile to find remaining bottlenecks
  - Identify missed optimization opportunities
  - Implement additional fixes
- [ ] 6.3.4 Document final performance metrics in `verification.md`

### 6.4 Operation Count Verification
- [ ] 6.4.1 Profile with cProfile:
  ```bash
  python -m cProfile -o taint.prof aud taint-analyze
  python -c "import pstats; p = pstats.Stats('taint.prof'); p.sort_stats('cumulative').print_stats(20)"
  ```
- [ ] 6.4.2 Count operations per function:
  - `_get_containing_function`: Before 100M, After ~1K (document actual)
  - `_propagate_through_block`: Before 500M, After ~500K (document actual)
  - `_get_calls_in_block`: Before 500M, After ~500K (document actual)
  - `_get_block_successors`: Before 50M, After O(1) (document actual)
- [ ] 6.4.3 Verify 100-1000x total reduction
- [ ] 6.4.4 Document in `verification.md`

### 6.5 Memory Profiling
- [ ] 6.5.1 Profile memory usage:
  ```python
  from memory_profiler import profile
  # Add @profile decorator to SchemaMemoryCache.__init__
  # Run: python -m memory_profiler aud taint-analyze
  ```
- [ ] 6.5.2 Measure memory increase from spatial indexes:
  - Expected: ~10-20MB overhead
  - Acceptable: <50MB overhead
  - If > 50MB: Optimize index structure
- [ ] 6.5.3 Confirm no memory leaks:
  - Run taint analysis 10 times in loop
  - Memory should stabilize after first run
  - No continuous growth
- [ ] 6.5.4 Document memory metrics in `verification.md`

### 6.6 Edge Case Testing
- [ ] 6.6.1 Test empty files:
  - No symbols, no assignments, no calls
  - Should not crash
- [ ] 6.6.2 Test functions with no CFG blocks:
  - Empty functions, single-expression functions
  - Should handle gracefully
- [ ] 6.6.3 Test circular taint flows:
  - Function A calls B calls A
  - Should detect cycles and terminate
- [ ] 6.6.4 Test very large functions:
  - 10,000+ LOC function
  - Should complete in reasonable time (<5 seconds)
- [ ] 6.6.5 Test deeply nested structures:
  - 100+ levels of nesting
  - Should not stack overflow

---

## Task Status Legend

- [ ] **Pending** - Not started
- [▶] **In Progress** - Currently working
- [x] **Completed** - Done and verified
- [⚠] **Blocked** - Waiting on dependency
- [❌] **Failed** - Attempted but failed (requires resolution)

---

## Completion Checklist (Final Verification)

Before marking this change as complete:

- [ ] All tasks 1.1-1.4 completed (spatial indexes implemented)
- [ ] All tasks 2.1-2.5 completed (discovery phase refactored)
- [ ] All tasks 3.1-3.4 completed (analysis phase refactored)
- [ ] All tasks 4.1-4.2 completed (propagation phase refactored)
- [ ] All tasks 5.1-5.3 completed (CFG batch loading implemented)
- [ ] All tasks 6.1-6.6 completed (testing & validation passed)
- [ ] Performance target met: 600s → ≤40s (15x+ speedup)
- [ ] Operation reduction verified: 165M-20B → ≤1M (100x+ reduction)
- [ ] All 113 taint rules passing (zero regressions)
- [ ] Fixtures byte-for-byte identical (except timing)
- [ ] Memory usage within 10% of baseline
- [ ] No false negatives (no security findings lost)
- [ ] Architect final approval
- [ ] Merged to main

---

**Current Status**: 🔴 **VERIFICATION PHASE** - Complete verification.md before starting implementation

**Estimated Total Time**: 5-6 days (3-4 days implementation + 1-2 days testing)
