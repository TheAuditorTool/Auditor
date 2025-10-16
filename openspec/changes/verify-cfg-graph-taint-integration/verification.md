# Verification Plan: CFG/Graph Integration Enhancement

**Change ID**: `verify-cfg-graph-taint-integration`
**Status**: Proposed

## Verification Strategy

This document defines how we'll validate that CFG/graph integration works correctly and achieves expected performance improvements.

---

## 1. Unit Tests

### 1.1 CFG Cache Query Functions

**File**: `tests/test_taint_database_cfg_cache.py` (NEW)

#### Test: `test_get_block_for_line_with_cache()`
```python
def test_get_block_for_line_with_cache():
    """Verify get_block_for_line() uses cache when available."""
    # Setup
    cursor = setup_test_db()
    cache = create_test_cache_with_cfg_blocks()

    # Execute
    block = get_block_for_line(cursor, "test.py", 42, "test_func", cache=cache)

    # Verify
    assert block is not None
    assert block["line"] == 42
    assert cache.cache_hit  # Verify cache was used, not database
```

#### Test: `test_get_block_for_line_cache_miss_fallback()`
```python
def test_get_block_for_line_cache_miss_fallback():
    """Verify fallback to database when cache misses."""
    # Setup
    cursor = setup_test_db_with_cfg()
    cache = MemoryCache()  # Empty cache

    # Execute
    block = get_block_for_line(cursor, "test.py", 42, "test_func", cache=cache)

    # Verify
    assert block is not None  # Still works via database fallback
    assert cache.cache_miss  # Confirm cache was attempted but missed
```

#### Test: `test_get_block_for_line_no_cache_parameter()`
```python
def test_get_block_for_line_no_cache_parameter():
    """Verify backward compatibility when cache=None."""
    cursor = setup_test_db_with_cfg()

    # Execute (no cache parameter)
    block = get_block_for_line(cursor, "test.py", 42, "test_func")

    # Verify
    assert block is not None  # Works without cache (backward compat)
```

**Repeat similar tests for**:
- `get_paths_between_blocks()`
- `get_block_statements()`
- `get_cfg_for_function()`

**Total**: 12 unit tests (3 tests × 4 functions)

---

### 1.2 Memory Cache Loading

**File**: `tests/test_memory_cache_cfg.py` (ENHANCED)

#### Test: `test_preload_cfg_blocks()`
```python
def test_preload_cfg_blocks():
    """Verify CFG blocks load correctly into cache."""
    # Setup
    cursor = setup_test_db_with_cfg_blocks()
    cache = MemoryCache()

    # Execute
    success = cache.preload(cursor)

    # Verify
    assert success
    assert len(cache.cfg_blocks) > 0
    assert len(cache.cfg_blocks_by_function) > 0
    assert "test.py" in cache.cfg_blocks_by_file
```

#### Test: `test_preload_cfg_edges()`
```python
def test_preload_cfg_edges():
    """Verify CFG edges load correctly into cache."""
    # Similar pattern to test_preload_cfg_blocks
    assert len(cache.cfg_edges) > 0
    assert len(cache.cfg_edges_by_source) > 0
```

#### Test: `test_preload_frameworks_table()`
```python
def test_preload_frameworks_table():
    """Verify frameworks table loads into cache (Phase 3)."""
    cursor = setup_test_db_with_frameworks()
    cache = MemoryCache()

    success = cache.preload(cursor)

    assert success
    assert len(cache.frameworks) > 0
    assert "Express" in cache.frameworks_by_name
```

**Total**: 5 unit tests (cfg_blocks, cfg_edges, cfg_statements, frameworks, object_literals)

---

### 1.3 PathAnalyzer Cache Integration

**File**: `tests/test_cfg_integration_cache.py` (NEW)

#### Test: `test_path_analyzer_uses_cache()`
```python
def test_path_analyzer_uses_cache():
    """Verify PathAnalyzer uses cache when provided."""
    cursor = setup_test_db()
    cache = create_test_cache_with_cfg()

    # Execute
    analyzer = PathAnalyzer(cursor, "test.py", "test_func", cache=cache)

    # Verify
    assert analyzer.cache is not None
    assert len(analyzer.blocks) > 0
    assert cache.cfg_function_access_count == 1  # Verify cache was queried
```

#### Test: `test_path_analyzer_without_cache()`
```python
def test_path_analyzer_without_cache():
    """Verify PathAnalyzer works without cache (backward compat)."""
    cursor = setup_test_db_with_cfg()

    # Execute (no cache)
    analyzer = PathAnalyzer(cursor, "test.py", "test_func")

    # Verify
    assert analyzer.cache is None  # No cache
    assert len(analyzer.blocks) > 0  # Still works via database
```

**Total**: 3 tests (PathAnalyzer, trace_flow_sensitive, interprocedural)

---

## 2. Integration Tests

### 2.1 End-to-End Taint Analysis with CFG Cache

**File**: `tests/integration/test_taint_with_cfg_cache.py` (NEW)

#### Test: `test_full_taint_analysis_with_cache()`
```python
def test_full_taint_analysis_with_cache():
    """Verify complete taint analysis pipeline uses cache."""
    # Setup
    db_path = create_test_project_db()
    cache = MemoryCache()
    cache.preload(sqlite3.connect(db_path).cursor())

    # Execute
    result = trace_taint(db_path, use_cfg=True, cache=cache)

    # Verify
    assert result["success"]
    assert len(result["taint_paths"]) > 0
    assert cache.cfg_hit_rate > 0.9  # >90% cache hit rate
```

#### Test: `test_interprocedural_cfg_with_cache()`
```python
def test_interprocedural_cfg_with_cache():
    """Verify inter-procedural CFG analysis uses cache."""
    # Setup test with function calls
    # Execute analysis
    # Verify cache hits on CFG queries
```

**Total**: 4 integration tests

---

## 3. Performance Benchmarks

### 3.1 CFG Query Performance

**File**: `benchmarks/bench_cfg_cache.py` (NEW)

#### Benchmark: CFG query time with/without cache
```python
def benchmark_get_block_for_line():
    """Measure speedup from cache for get_block_for_line()."""

    # Benchmark WITHOUT cache
    start = time.perf_counter()
    for _ in range(1000):
        get_block_for_line(cursor, file, line, func, cache=None)
    time_without_cache = time.perf_counter() - start

    # Benchmark WITH cache
    start = time.perf_counter()
    for _ in range(1000):
        get_block_for_line(cursor, file, line, func, cache=cache)
    time_with_cache = time.perf_counter() - start

    # Report
    speedup = time_without_cache / time_with_cache
    print(f"Speedup: {speedup:.1f}x")

    # Verify
    assert speedup >= 10.0  # Expect at least 10x speedup
```

**Metrics to collect**:
- Query time (with/without cache)
- Cache hit rate
- Memory usage
- Speedup ratio

**Target**: 10-100x speedup on CFG queries

---

### 3.2 Full Pipeline Performance

**File**: `benchmarks/bench_taint_pipeline.py` (ENHANCED)

#### Benchmark: Full taint analysis time
```python
def benchmark_taint_analysis_pipeline():
    """Measure end-to-end taint analysis performance."""

    # Test projects
    projects = [
        ("small", "<5K LOC"),
        ("medium", "~20K LOC"),
        ("large", ">100K LOC")
    ]

    for name, size in projects:
        db_path = get_test_project_db(name)

        # Baseline: WITHOUT cache
        start = time.perf_counter()
        result_no_cache = trace_taint(db_path, use_cfg=True, use_memory_cache=False)
        time_no_cache = time.perf_counter() - start

        # Enhanced: WITH cache
        start = time.perf_counter()
        result_with_cache = trace_taint(db_path, use_cfg=True, use_memory_cache=True)
        time_with_cache = time.perf_counter() - start

        # Verify correctness
        assert result_no_cache["total_vulnerabilities"] == result_with_cache["total_vulnerabilities"]

        # Report
        speedup = time_no_cache / time_with_cache
        print(f"{name} ({size}): {speedup:.2f}x speedup")
```

**Expected Results**:
- Small project: 2-5x overall speedup
- Medium project: 5-10x overall speedup
- Large project: 10-20x overall speedup

---

### 3.3 Memory Usage Validation

#### Benchmark: Cache memory consumption
```python
def benchmark_memory_usage():
    """Verify cache stays within memory limits."""
    import psutil

    process = psutil.Process()
    baseline = process.memory_info().rss / 1024 / 1024  # MB

    # Load cache
    cache = MemoryCache(max_memory_mb=4000)
    cache.preload(cursor)

    after_load = process.memory_info().rss / 1024 / 1024
    cache_memory = after_load - baseline

    # Report
    print(f"Cache memory usage: {cache_memory:.1f}MB")
    print(f"Cache reports: {cache.get_memory_usage_mb():.1f}MB")

    # Verify
    assert cache_memory < 4000  # Within limit
    assert abs(cache_memory - cache.get_memory_usage_mb()) < 500  # Reasonable estimate
```

---

## 4. Regression Tests

### 4.1 Existing Test Suite

**Command**: `pytest tests/ -v`

**Expectation**: ALL existing tests pass

**Critical test files**:
- `tests/test_taint_analyzer.py`
- `tests/test_cfg_integration.py`
- `tests/test_interprocedural.py`
- `tests/test_memory_cache.py`

**Verification**:
```bash
# Run all tests
pytest tests/ -v --cov=theauditor --cov-report=html

# Verify coverage
# - >90% coverage on modified files
# - Zero failing tests
# - Zero new warnings
```

---

### 4.2 Backward Compatibility Tests

#### Test: Functions work without cache parameter
```python
def test_backward_compatibility_no_cache():
    """Verify all modified functions work without cache parameter."""

    # All these should work (no cache parameter)
    block = get_block_for_line(cursor, file, line, func)
    paths = get_paths_between_blocks(cursor, file, src, tgt)
    stmts = get_block_statements(cursor, block_id)
    cfg = get_cfg_for_function(cursor, file, func)
    analyzer = PathAnalyzer(cursor, file, func)

    # All should return valid results
    assert all(x is not None for x in [block, paths, stmts, cfg, analyzer])
```

---

## 5. Validation Checklist

### Phase 2: CFG Cache Integration

- [ ] All 4 CFG query functions accept cache parameter
- [ ] Cache parameter is optional (default None)
- [ ] Cache lookup happens before database query
- [ ] Database fallback works on cache miss
- [ ] PathAnalyzer passes cache through
- [ ] InterProceduralCFGAnalyzer passes cache through
- [ ] Unit tests pass for all 4 functions
- [ ] Integration tests show cache usage
- [ ] Benchmark shows 10-100x speedup on CFG queries
- [ ] Zero regressions in existing tests

---

### Phase 3: Hot Path Tables

- [ ] Frameworks table loads into cache
- [ ] Object_literals table loads into cache
- [ ] Framework_safe_sinks table loads into cache
- [ ] Cache methods added for new tables
- [ ] Consumers updated to use cache
- [ ] Unit tests for new cache methods
- [ ] Integration tests show cache usage
- [ ] Memory usage stays within limits
- [ ] Zero regressions

---

---

## 6. Acceptance Criteria

### Functionality

✅ **All CFG query functions use cache when available**
- Verified by: Unit tests + integration tests

✅ **Cache fallback to database on miss**
- Verified by: test_get_block_for_line_cache_miss_fallback()

✅ **Backward compatibility maintained**
- Verified by: test_backward_compatibility_no_cache()

✅ **Hot path tables cached**
- Verified by: Cache loading tests + consumer tests

---

### Performance

✅ **CFG query speedup: 10-100x**
- Verified by: benchmark_get_block_for_line()
- Measurement: Query time with/without cache

✅ **Pipeline speedup: 2-20x (varies by project size)**
- Verified by: benchmark_taint_analysis_pipeline()
- Measurement: End-to-end analysis time

✅ **Cache hit rate: >90%**
- Verified by: Integration tests + benchmarks
- Measurement: cache.cfg_hit_rate attribute

✅ **Memory usage: Within configured limits**
- Verified by: benchmark_memory_usage()
- Measurement: psutil memory tracking

---

### Quality

✅ **Zero regressions**
- Verified by: Full test suite (`pytest tests/ -v`)
- Standard: 100% of existing tests pass

✅ **Code coverage: >90% on modified files**
- Verified by: `pytest --cov=theauditor --cov-report=html`
- Measurement: Coverage report

✅ **No performance degradation without cache**
- Verified by: Benchmark with cache=None
- Standard: Performance matches baseline

---

## 7. Test Data Requirements

### Test Databases

1. **Minimal DB** (unit tests):
   - 1 file, 1 function, 5 CFG blocks
   - 1 if/else condition
   - Complete CFG tables populated

2. **Small Project DB** (integration tests):
   - 10 files, <1K LOC
   - Mix of Python and JavaScript
   - Complete CFG coverage
   - Known vulnerabilities for validation

3. **Medium Project DB** (benchmarks):
   - 100 files, ~20K LOC
   - Real-world project structure
   - Representative CFG complexity

4. **Large Project DB** (stress tests):
   - 500+ files, >100K LOC
   - Monorepo structure
   - High CFG complexity

### Test Fixtures

Create fixtures in `tests/fixtures/cfg_test/`:

1. `python_conditions.py` - If/else/elif patterns
2. `python_loops.py` - For/while loop patterns
3. `javascript_conditions.js` - If/else/switch patterns
4. `javascript_loops.js` - For/while loop patterns
5. `typescript_conditions.ts` - TypeScript-specific patterns

---

## 8. Debugging & Diagnostics

### Debug Environment Variables

```bash
# Enable CFG cache debugging
export THEAUDITOR_CFG_DEBUG=1

# Enable taint debugging
export THEAUDITOR_TAINT_DEBUG=1

# Enable memory cache debugging
export THEAUDITOR_MEMORY_DEBUG=1
```

### Debug Output Format

```
[CFG] Cache hit: get_block_for_line(test.py:42) -> block_id=5
[CFG] Cache miss: get_block_for_line(other.py:10) -> fallback to database
[MEMORY] Cache hit rate: 95.2% (1000/1050 queries)
```

### Diagnostic Queries

```sql
-- Verify CFG data exists
SELECT COUNT(*) FROM cfg_blocks;
SELECT COUNT(*) FROM cfg_edges;
SELECT COUNT(*) FROM cfg_block_statements;

-- Check CFG coverage per file
SELECT file, COUNT(*) as block_count
FROM cfg_blocks
GROUP BY file;

-- Identify files without CFG data
SELECT DISTINCT path FROM symbols
WHERE path NOT IN (SELECT DISTINCT file FROM cfg_blocks);
```

---

## 9. Success Metrics Summary

| Metric | Target | Verification Method |
|--------|--------|---------------------|
| CFG query speedup | 10-100x | Benchmark |
| Pipeline speedup (small) | 2-5x | Benchmark |
| Pipeline speedup (medium) | 5-10x | Benchmark |
| Pipeline speedup (large) | 10-20x | Benchmark |
| Cache hit rate | >90% | Integration tests |
| Memory usage | Dynamically managed (utils/memory.py) | Memory benchmark |
| Test coverage | >90% | pytest --cov |
| Regression rate | 0% | Full test suite |
| CFG extraction (Python) | ✅ Verified complete | Code review |
| CFG extraction (JS/TS) | ✅ Verified complete | Code review |
| Backward compatibility | ✅ Zero breaking changes | Test suite |

---

## 10. Sign-Off Criteria

Before merging to main:

- [ ] All unit tests pass (100%)
- [ ] All integration tests pass (100%)
- [ ] All regression tests pass (100%)
- [ ] Benchmarks meet targets (see table above)
- [ ] Code review approved
- [ ] Documentation updated
- [ ] Changelog entry added
- [ ] Performance report reviewed by Architect

---

**Status**: Awaiting implementation to begin verification process.
