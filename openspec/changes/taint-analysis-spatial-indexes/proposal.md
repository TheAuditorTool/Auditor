# Taint Analysis Spatial Index Refactor

**Status**: 🔴 PROPOSAL - Awaiting Architect approval

**Parent Proposal**: `performance-revolution-now` (TIER 0 Task 1)

**Assigned to**: AI #1 (Opus recommended - highest complexity)

**Timeline**: 5-6 days (3-4 days implementation + 1-2 days testing)

**Impact**: 🔴 **CRITICAL** - 95% of total performance gain (540 seconds saved per run)

---

## Why

Taint analysis currently suffers from **N+1 linear scan anti-patterns** causing 165 million to 20 billion operations (depending on recursion depth) when it should be ~1 million operations.

**Root Cause**: Every taint source/sink discovery and propagation step does full-table scans instead of indexed lookups.

**Measured Impact**:
- Taint analysis: 10 minutes → Should be 20-40 seconds (95-98% slower than optimal)
- 165M-20B operations → Should be 1M operations (100-1000x overhead)

This is the **single most impactful performance fix** in the entire codebase.

---

## What Changes

### **Add Spatial Indexes to SchemaMemoryCache**

Add 6 spatial index data structures to `generated_cache.py`:

1. **`symbols_by_type: Dict[str, List[Dict]]`** - O(1) lookup by symbol type
2. **`symbols_by_file_line: Dict[str, Dict[int, List[Dict]]]`** - O(1) spatial lookup (file → line_block → symbols)
3. **`assignments_by_location: Dict[str, Dict[int, List[Dict]]]`** - O(1) spatial lookup for assignments
4. **`calls_by_location: Dict[str, Dict[int, List[Dict]]]`** - O(1) spatial lookup for function calls
5. **`successors_by_block: Dict[str, List[Dict]]`** - O(1) adjacency list for CFG traversal
6. **`blocks_by_id: Dict[str, Dict]`** - O(1) block lookup by ID

**Line blocking strategy**: Group by 100-line blocks for efficient spatial queries.

### **Refactor Discovery Phase** (`theauditor/taint/discovery.py`)

Replace linear scans with indexed lookups:

**Lines 52-67** - User input source discovery:
- BEFORE: `for symbol in self.cache.symbols if type == 'property'` (500K ops)
- AFTER: `for symbol in self.cache.symbols_by_type.get('property', [])` (1K ops)
- **500x improvement**

**Lines 70-84** - File read source discovery:
- BEFORE: `if 'readFile' in func_name` (string operations)
- AFTER: Pre-compiled frozenset lookups `if func_name in FILE_READ_FUNCTIONS`
- **100x improvement**

**Lines 163-177** - Command injection sink discovery:
- BEFORE: Full-table scan for callee_function
- AFTER: Indexed lookup by callee_function
- **1000x improvement**

### **Refactor Analysis Phase** (`theauditor/taint/analysis.py`)

Replace N+1 queries with spatial index lookups:

**Lines 187-195** - `_get_containing_function`:
- BEFORE: `for symbol in self.cache.symbols if type == 'function' and line in range(...)` (100M ops)
- AFTER: `symbols_by_file_line[file][line_block]` lookup (1K ops)
- **100,000x improvement**

**Lines 245-249** - `_propagate_through_block`:
- BEFORE: `for a in self.cache.assignments if file == block.file and line in range(...)` (500M ops)
- AFTER: `assignments_by_location[file][line_block]` (500K ops)
- **1,000x improvement**

**Lines 267-270** - `_get_calls_in_block`:
- BEFORE: Full-table scan of function_call_args (500M ops)
- AFTER: `calls_by_location[file][line_block]` (500K ops)
- **1,000x improvement**

**Lines 284-292** - `_get_block_successors`:
- BEFORE: O(n²) nested loop `for edge in edges: for block in blocks if block.id == edge.to_block` (50M ops)
- AFTER: `return self.cache.successors_by_block[block_id]` (O(1))
- **50,000,000x improvement**

### **Refactor Propagation Phase** (`theauditor/taint/propagation.py`)

**Lines 224-232 & 254-262** - Replace LIKE wildcard patterns:
- BEFORE: `WHERE source_expr LIKE '%{pattern}%'` (50M rows scanned)
- AFTER: `WHERE file = ? AND line BETWEEN ? AND ?` + Python filter `if pattern in source_expr` (500K rows)
- **100x improvement**

### **Batch Load CFG Statements**

**N+1 Query Pattern**: Currently ~10,000 separate queries for CFG block statements.

- BEFORE: `cursor.execute("SELECT ... WHERE block_id = ?")` per block (10,000 queries)
- AFTER: Load all statements for function upfront, store in `statements_by_block: Dict[str, List[Dict]]` (1 query)
- **10,000x improvement**

---

## Impact

### **Affected Code**

**Modified Files** (200-650 lines total):
- `theauditor/indexer/schemas/generated_cache.py` - Add spatial index builders (300 lines added)
- `theauditor/taint/discovery.py` - Replace linear scans (200 lines modified)
- `theauditor/taint/analysis.py` - Replace N+1 patterns (150 lines modified)
- `theauditor/taint/propagation.py` - Fix LIKE patterns (100 lines modified)

**Read-Only** (for understanding):
- `theauditor/taint/schema_cache_adapter.py` - Memory cache interface

### **Breaking Changes**

**None** - This is an internal optimization. External API preserved:
- Taint findings format unchanged
- `SchemaMemoryCache` API backward compatible (spatial indexes are additional properties)
- All consumers continue to work unchanged

### **Performance Targets**

**Before**: 600 seconds (10 minutes)
**After**: 20-40 seconds
**Speedup**: 15-30x (95% improvement)

**Operation Reduction**:
- Discovery phase: 500K → 1K operations (500x)
- `_get_containing_function`: 100M → 1K operations (100,000x)
- `_propagate_through_block`: 500M → 500K operations (1,000x)
- `_get_calls_in_block`: 500M → 500K operations (1,000x)
- `_get_block_successors`: 50M → O(1) (50,000,000x)
- CFG statement loading: 10,000 queries → 1 query (10,000x)

**Total**: 165M-20B operations → 1M operations (100-1000x reduction)

### **Risk Assessment**

**Complexity**: 🔴 **VERY HIGH** - Most complex refactor in entire proposal

**Risks**:
1. **Correctness**: Spatial index bugs could introduce false negatives (missed vulnerabilities)
2. **Completeness**: Must test on all 113 taint rules
3. **Memory**: Spatial indexes add ~10-20MB overhead (acceptable)

**Mitigation**:
- Extensive fixture testing (byte-for-byte output comparison)
- Profile with memory profiler
- Measure operation count reduction with profiling

---

## Dependencies

**Prerequisites**:
- ✅ Schema-driven taint architecture (already completed in `refactor-taint-schema-driven-architecture`)
- ✅ `SchemaMemoryCache` exists in `generated_cache.py`

**Required Reading** (BEFORE coding):
1. `performance-revolution-now/INVESTIGATION_REPORT.md` sections 2.1-2.4 (taint analysis findings)
2. `performance-revolution-now/design.md` section 2.1 (spatial index design decisions)
3. This proposal's `tasks.md` sections 1.1-1.6 (detailed implementation steps)
4. `teamsop.md` v4.20 (Prime Directive verification protocols)

**Blocking**: None - Can start immediately after approval

**Blocked by this**: None - Other proposals can run in parallel

---

## Testing Strategy

### **Correctness Testing** (MANDATORY)

1. **All 113 taint rules must pass** (zero regressions)
2. **Fixture validation**: Run on 5 fixture projects (Python, JS, mixed)
   - Compare taint findings before/after (must match byte-for-byte except timing)
   - Test: `pytest tests/test_taint*.py -v`
3. **Edge cases**:
   - Empty files
   - Functions with no CFG blocks
   - Circular taint flows
   - Very large functions (10K+ LOC)

### **Performance Testing**

1. **Measure operation count reduction**:
   - Use cProfile to measure calls per function
   - Document before/after operation counts
   - Expected: 100-1000x reduction

2. **Benchmark taint analysis time**:
   - Test on 10K LOC project
   - Before: ~10 minutes
   - After: ~30 seconds
   - Document actual speedup

3. **Memory profiling**:
   - Measure memory usage before/after
   - Spatial indexes add ~10-20MB (acceptable)
   - Confirm no memory leaks

---

## Success Criteria

**MUST MEET ALL** before merging:

1. ✅ Taint analysis: 600s → ≤40s (15x+ speedup)
2. ✅ 165M-20B operations → ≤1M operations (100x+ reduction)
3. ✅ All 113 taint rules pass (zero regressions)
4. ✅ Fixtures byte-for-byte identical (except timing data)
5. ✅ Memory usage within 10% of baseline
6. ✅ No false negatives (no security findings lost)

---

## Approval Gates

**Stage 1**: Proposal Review (Current Stage)
- [ ] Architect reviews proposal
- [ ] Architect approves scope and timeline

**Stage 2**: Verification Phase (Before Implementation)
- [ ] Coder reads INVESTIGATION_REPORT.md sections 2.1-2.4
- [ ] Coder reads design.md section 2.1
- [ ] Coder completes verification protocol (see `verification.md`)
- [ ] Coder documents findings in `verification.md`
- [ ] Architect approves verification results

**Stage 3**: Implementation
- [ ] Spatial indexes implemented (tasks 1.1-1.3)
- [ ] Discovery phase refactored (task 1.2)
- [ ] Analysis phase refactored (task 1.3)
- [ ] Propagation phase refactored (task 1.4)
- [ ] CFG batch loading implemented (task 1.5)
- [ ] All tests passing (task 1.6)

**Stage 4**: Deployment
- [ ] Performance benchmarks validated
- [ ] Architect approves deployment
- [ ] Merged to main

---

## Related Changes

**Parent**: `performance-revolution-now` (PAUSED AND SPLIT)

**Siblings** (can run in parallel):
- `fix-python-ast-orchestrator` (AI #2, TIER 0 Task 2) - Zero file conflicts
- `vue-inmemory-module-resolution` (AI #3, TIER 1) - Zero file conflicts
- `fce-json-normalization` (AI #4, TIER 1.5) - Zero file conflicts
- `database-indexes-cleanup` (TIER 2) - Zero file conflicts

**Merge Strategy**: Can merge independently (zero file conflicts with other proposals)

---

**Next Step**: Architect reviews and approves/rejects/modifies this proposal
