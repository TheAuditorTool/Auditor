# Tasks: CFG/Graph Integration Verification and Enhancement

**Change ID**: `verify-cfg-graph-taint-integration`
**Status**: Proposed - Awaiting Architect Approval

## Phase 1: Investigation & Documentation (COMPLETED)

- [x] **Task 1.1**: Read all indexer files completely (4 files)
  - [x] indexer/__init__.py
  - [x] indexer/database.py
  - [x] indexer/schema.py
  - [x] indexer/extractors/__init__.py

- [x] **Task 1.2**: Read all graph files completely (3 files)
  - [x] graph/builder.py
  - [x] graph/cfg_builder.py
  - [x] graph/store.py

- [x] **Task 1.3**: Read all taint files completely (11 files)
  - [x] taint/__init__.py
  - [x] taint/core.py
  - [x] taint/config.py
  - [x] taint/sources.py
  - [x] taint/propagation.py
  - [x] taint/database.py
  - [x] taint/memory_cache.py
  - [x] taint/interprocedural.py
  - [x] taint/interprocedural_cfg.py
  - [x] taint/cfg_integration.py
  - [x] taint/registry.py

- [x] **Task 1.4**: Trace data flows and integration points
  - [x] CFG extraction → storage → consumption
  - [x] Graph extraction → storage → consumption
  - [x] Memory cache loading and usage patterns
  - [x] Cross-module function call chains

- [x] **Task 1.5**: Document findings in proposal.md
  - [x] Critical Finding 1: CFG cache integration gap
  - [x] Critical Finding 2: Graph data duplication
  - [x] Critical Finding 3: CFG builder coverage unknown
  - [x] Critical Finding 4: Missing hot path tables in cache

## Phase 2: CFG Cache Integration (P0)

**Dependency**: Architect approval of proposal

### Task 2.1: Add cache parameter to CFG query functions

**File**: `taint/database.py`

**Changes**:
1. Modify `get_block_for_line()` signature (line 841):
   ```python
   # BEFORE
   def get_block_for_line(cursor: sqlite3.Cursor, file_path: str, line: int,
                          function_name: Optional[str] = None) -> Optional[Dict[str, Any]]:

   # AFTER
   def get_block_for_line(cursor: sqlite3.Cursor, file_path: str, line: int,
                          function_name: Optional[str] = None,
                          cache: Optional[Any] = None) -> Optional[Dict[str, Any]]:
   ```

2. Add cache lookup implementation:
   ```python
   if cache and hasattr(cache, 'cfg_blocks_by_function'):
       # O(1) lookup
       blocks = cache.cfg_blocks_by_function.get((file_path, function_name), [])
       for block in blocks:
           if block["start_line"] <= line <= block["end_line"]:
               return block
       return None

   # FALLBACK: Original database query
   ```

3. Repeat for other 3 CFG functions:
   - `get_paths_between_blocks()` (line 892)
   - `get_block_statements()` (line 952)
   - `get_cfg_for_function()` (line 984)

**Verification**:
- Unit test: Cache hit returns correct block
- Unit test: Cache miss falls back to database
- Unit test: None cache parameter works (backward compat)

---

### Task 2.2: Thread cache through cfg_integration.py

**File**: `taint/cfg_integration.py`

**Changes**:

1. Modify `PathAnalyzer.__init__()` (line 78):
   ```python
   # BEFORE
   def __init__(self, cursor: sqlite3.Cursor, file_path: str, function_name: str) -> None:
       self.cfg = get_cfg_for_function(cursor, file_path, function_name)

   # AFTER
   def __init__(self, cursor: sqlite3.Cursor, file_path: str, function_name: str,
                cache: Optional[Any] = None) -> None:
       self.cache = cache
       self.cfg = get_cfg_for_function(cursor, file_path, function_name, cache=cache)
   ```

2. Update all `get_block_for_line()` calls (line 127):
   ```python
   # BEFORE
   source_block = get_block_for_line(self.cursor, self.file_path, source_line, self.function_name)

   # AFTER
   source_block = get_block_for_line(self.cursor, self.file_path, source_line,
                                      self.function_name, cache=self.cache)
   ```

3. Update `trace_flow_sensitive()` signature (line 641):
   ```python
   # Add cache parameter
   def trace_flow_sensitive(cursor, source, sink, source_function, max_paths=100, cache=None):
       # Pass cache to PathAnalyzer
       analyzer = PathAnalyzer(cursor, source["file"], source_function["name"], cache=cache)
   ```

**Verification**:
- Integration test: PathAnalyzer with cache completes faster than without
- Benchmark: Measure speedup on real CFG data

---

### Task 2.3: Thread cache through interprocedural_cfg.py

**File**: `taint/interprocedural_cfg.py`

**Changes**:

1. InterProceduralCFGAnalyzer already has cache in __init__ (line 82) ✅
2. Update PathAnalyzer creation (line 138):
   ```python
   # BEFORE
   analyzer = PathAnalyzer(self.cursor, callee_file, callee_func)

   # AFTER
   analyzer = PathAnalyzer(self.cursor, callee_file, callee_func, cache=self.cache)
   ```

**Verification**:
- Integration test: Interprocedural CFG analysis uses cache
- Debug log: Verify cache hits during analysis

---

### Task 2.4: Thread cache through propagation.py

**File**: `taint/propagation.py`

**Changes**:

1. Update `trace_from_source()` CFG integration (line 134):
   ```python
   # Import uses cache already, pass through
   from .cfg_integration import trace_flow_sensitive

   flow_paths = trace_flow_sensitive(
       cursor=cursor,
       source=source,
       sink=sink,
       source_function=source_function,
       max_paths=100,
       cache=cache  # ✅ Already has cache parameter
   )
   ```

2. Update `verify_unsanitized_cfg_paths()` calls:
   ```python
   # Add cache parameter to all calls
   cfg_paths_for_sink = verify_unsanitized_cfg_paths(
       cursor=cursor,
       source=source,
       sink=sink,
       source_function=source_function,
       max_paths=100,
       cache=cache  # ADD THIS
   )
   ```

**Verification**:
- End-to-end test: Full taint analysis with cache enabled
- Performance test: Measure pipeline speedup

---

## Phase 3: Hot Path Table Caching (P1)

**Dependency**: Phase 2 complete

### Task 3.1: Add frameworks table to memory cache

**File**: `taint/memory_cache.py`

**Changes**:

1. Add storage (after line 62):
   ```python
   # Phase 3: Add frameworks and object_literals
   self.frameworks = []
   self.object_literals = []
   ```

2. Add indexes (after line 114):
   ```python
   # Frameworks indexes
   self.frameworks_by_name = defaultdict(list)  # name -> [frameworks]

   # Object literals indexes
   self.object_literals_by_variable = defaultdict(list)  # variable_name -> [literals]
   self.object_literals_by_file = defaultdict(list)  # file -> [literals]
   ```

3. Add loading (after line 510):
   ```python
   # Load frameworks table
   query = build_query('frameworks', ['name', 'version', 'language', 'path', 'is_primary'])
   cursor.execute(query)

   for name, version, language, path, is_primary in cursor.fetchall():
       fw = {
           "name": name,
           "version": version,
           "language": language,
           "path": path,
           "is_primary": is_primary
       }
       self.frameworks.append(fw)
       self.frameworks_by_name[name].append(fw)
       self.current_memory += sys.getsizeof(fw) + 50

   print(f"[MEMORY] Loaded {len(self.frameworks)} frameworks", file=sys.stderr)
   ```

**Verification**:
- Unit test: Frameworks load correctly
- Unit test: Index lookups work

---

### Task 3.2: Add cached framework lookup method

**File**: `taint/memory_cache.py`

**Add method** (after line 955):
```python
def get_frameworks_cached(self) -> List[Dict[str, Any]]:
    """Get all frameworks from cache."""
    return self.frameworks.copy()

def get_framework_by_name_cached(self, name: str) -> List[Dict[str, Any]]:
    """Get frameworks by name from cache."""
    return self.frameworks_by_name.get(name, []).copy()
```

---

### Task 3.3: Update taint/core.py to use framework cache

**File**: `taint/core.py`

**Change** (line 145-174):
```python
# BEFORE
cursor.execute(query)
for name, version, language, path in cursor.fetchall():
    frameworks.append({...})

# AFTER
if cache and hasattr(cache, 'get_frameworks_cached'):
    frameworks = cache.get_frameworks_cached()
else:
    # FALLBACK: Original database query
    cursor.execute(query)
    for name, version, language, path in cursor.fetchall():
        frameworks.append({...})
```

**Verification**:
- Integration test: trace_taint() with cache uses cached frameworks
- Benchmark: Measure speedup

---

### Task 3.4: Add object_literals and framework_safe_sinks to cache

**Similar pattern to Task 3.1-3.3**:

1. Add storage fields
2. Add indexes
3. Add loading logic
4. Add cached methods
5. Update consumers (interprocedural_cfg.py, database.py)

**Verification**:
- Unit tests for each table
- Integration tests for consumers
- Memory usage validation

---

## Phase 4: Testing & Validation

**Dependency**: Phases 2-3 complete

### Task 4.1: Performance benchmarks

**Metrics to measure**:
- CFG query time (with/without cache)
- Full taint analysis time (with/without cache improvements)
- Memory usage (validate within limits)
- Cache hit rate (target: >90% for CFG queries)

**Test projects**:
- Small: <5K LOC
- Medium: ~20K LOC
- Large: >100K LOC

**Deliverable**: Performance report with before/after comparisons

---

### Task 4.2: Integration tests

**Test scenarios**:
1. Taint analysis with CFG cache enabled
2. Interprocedural analysis with CFG cache
3. Framework detection using cached frameworks
4. Dynamic dispatch with cached object_literals
5. Mixed: cache miss → fallback → correct result

**Deliverable**: Test suite with >90% coverage of changes

---

### Task 4.3: Regression testing

**Run existing test suite**:
- All existing taint analysis tests
- All existing CFG tests
- All existing graph tests

**Validation**: Zero regressions, all tests pass

---

## Phase 5: Documentation Updates

### Task 5.1: Update CLAUDE.md

**Sections to update**:
- Memory cache architecture (add new tables)
- CFG integration flow
- CFG extraction chain documentation
- Performance expectations
- Clarify graphs.db separation (already intentional)

---

### Task 5.2: Update code comments

**Files**:
- Add docstrings explaining cache parameters
- Update function comments with cache behavior
- Add inline comments for cache lookup patterns

---

### Task 5.3: Update changelog

**No breaking changes** - all changes backward compatible:
- Document new cache parameters (optional)
- Note performance improvements
- Update version notes

---

## Dependencies & Sequencing

```
Phase 1 (Investigation) → COMPLETE ✅
    ↓
Architect Review → COMPLETE ✅
    ↓
Phase 2 (CFG Cache) → P0
    ├→ Task 2.1 (database.py - add cache parameters)
    ├→ Task 2.2 (cfg_integration.py - thread cache)
    ├→ Task 2.3 (interprocedural_cfg.py - propagate cache)
    └→ Task 2.4 (propagation.py - use cache)
    ↓
Phase 3 (Hot Path Cache) → P1
    ├→ Task 3.1-3.2 (frameworks table)
    └→ Task 3.3-3.4 (object_literals, framework_safe_sinks)
    ↓
Phase 4 (Testing) → Required before merge
    ├→ Task 4.1 (performance benchmarks)
    ├→ Task 4.2 (integration tests)
    └→ Task 4.3 (regression tests)
    ↓
Phase 5 (Documentation) → Final step
    ├→ Task 5.1 (CLAUDE.md updates)
    ├→ Task 5.2 (code comments)
    └→ Task 5.3 (changelog)
```

---

## Success Criteria

- [ ] All CFG query functions use cache when available (backward compatible)
- [ ] Performance improvement: 10-100x faster CFG queries
- [ ] Cache hit rate: >90% for CFG operations
- [ ] Hot path tables (frameworks, object_literals) cached
- [ ] CFG extraction verified complete for Python + JS/TS ✅
- [ ] graphs.db separation documented (intentional design) ✅
- [ ] Zero regressions in existing tests
- [ ] Performance benchmarks validate improvements
- [ ] Documentation updated and complete
- [ ] Zero breaking changes - all backward compatible

---

## Risk Mitigation

**Risk 1**: Breaking existing callers of CFG functions
- **Mitigation**: Optional cache parameter (default None), backward compatible

**Risk 2**: Memory cache exceeds limits with new tables
- **Mitigation**: Load new tables only if memory available, monitor usage

**Risk 3**: Cache invalidation bugs
- **Mitigation**: Comprehensive tests, fallback to database on cache miss

**Risk 4**: Performance gains not realized
- **Mitigation**: Benchmark early, validate assumptions, adjust approach

---

**Estimated Effort**:
- Phase 1: COMPLETE ✅
- Phase 2: 3-5 days (P0 - CFG cache integration)
- Phase 3: 2-3 days (P1 - hot path tables)
- Phase 4: 2-3 days (testing and benchmarks)
- Phase 5: 1 day (documentation)

**Total**: 8-12 days (streamlined with verification complete)

---

**Next Action**: Await Architect approval to begin Phase 2 implementation.
