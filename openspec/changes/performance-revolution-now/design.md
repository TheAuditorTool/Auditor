# Performance Revolution - Technical Design

## Context

TheAuditor exhibits systemic performance degradation caused by "death by 1000 cuts" - redundant operations compounded across multiple subsystems. Independent investigation by 8 specialized agents confirmed 5-40x slower-than-optimal performance across indexing, taint analysis, and pattern detection.

**Key Discovery**: The `regex_perf.md` fix (7,900x LIKE wildcard speedup) exposed a deeper architectural pattern - **redundant traversal operations** that compound exponentially.

**Stakeholders**:
- **Users**: Blocked by 10-minute runs on medium codebases (unacceptable UX)
- **Architect**: Needs performance parity with commercial SAST tools
- **Lead Auditor (Gemini)**: Quality control on refactor correctness
- **Lead Coder (Opus)**: Implementation responsibility

---

## Goals / Non-Goals

### Goals
1. **5-40x Performance Improvement**: Achieve measured speedups across all subsystems
   - Indexing: 90s → 12-18s (5-7.5x)
   - Taint Analysis: 10 min → 20-40s (20-40x)
   - Pattern Detection: Already optimal (no action needed)

2. **Zero Regression**: Preserve exact extraction behavior
   - Database schema unchanged (indexes only)
   - Fixture outputs must match byte-for-byte
   - Public APIs preserved

3. **Maintainability**: Simplify architecture for future development
   - Single-pass visitor pattern is more maintainable than 80 extractors
   - Spatial indexes are standard CS pattern (easy to understand)

### Non-Goals
1. **New Features**: This is pure optimization (no new capabilities)
2. **Schema Changes**: No database migrations (additive indexes only)
3. **API Changes**: No breaking changes to public APIs
4. **Algorithmic Changes**: No changes to taint analysis algorithms (only execution efficiency)

---

## Architectural Decisions

### Decision 1: Single-Pass Visitor Pattern for Python AST

**Problem**: 80 independent `ast.walk()` calls per Python file (70-80x overhead)

**Decision**: Consolidate all extractors into `UnifiedPythonVisitor(ast.NodeVisitor)`

**Rationale**:
- ✅ **Standard Pattern**: `ast.NodeVisitor` is Python's recommended AST traversal pattern
- ✅ **80x Reduction**: Single traversal vs 80 traversals = 80x fewer node visits
- ✅ **Maintainability**: Centralized extraction logic easier to debug/modify
- ✅ **Extensibility**: Adding new framework support = add method to visitor (not new file)

**Alternatives Considered**:

1. **Keep Separate Extractors, Cache AST**
   - **Rejected**: Still 80 traversals (cache helps parsing, not traversal)
   - AST is already cached (parsing not the bottleneck)

2. **Selective Extraction (Only Extract What's Needed)**
   - **Rejected**: We need all data (can't skip extractors)
   - Complexity of determining "what's needed" outweighs benefit

3. **Parallel AST Traversal (ThreadPool)**
   - **Rejected**: GIL prevents true parallelism in Python
   - Overhead of thread creation > benefit of parallelism

**Implementation Strategy**:
- Visitor pattern with `visit_ClassDef`, `visit_FunctionDef`, etc.
- Each visit method checks ALL framework patterns (SQLAlchemy, Django, Flask, etc.)
- Frozenset lookups replace `.endswith()` string operations (O(1) vs O(n))
- Backward compatible: Orchestrator gets same result structure

**Migration Path**:
1. Implement `UnifiedPythonVisitor` alongside existing extractors
2. Migrate framework-by-framework (SQLAlchemy → Django → Flask → ...)
3. Test each migration with fixtures
4. Remove old extractor files only after full validation

---

### Decision 2: Spatial Indexes for Taint Analysis

**Problem**: 60 BILLION operations (100M comparisons per source × 1,000 sources)

**Decision**: Add spatial indexes to `SchemaMemoryCache` for O(1) lookups

**Rationale**:
- ✅ **Standard CS Pattern**: Spatial indexing is well-established for line-based queries
- ✅ **60,000x Reduction**: O(n) linear scans → O(1) hash lookups
- ✅ **Low Memory Cost**: ~10-20MB additional memory (acceptable)
- ✅ **Zero Algorithm Changes**: Same taint logic, just faster lookups

**Spatial Index Design**:

```python
class SchemaMemoryCache:
    def __init__(self, db_path):
        # ... existing code ...

        # NEW: Spatial indexes
        self.symbols_by_type: Dict[str, List[Dict]] = defaultdict(list)
        self.symbols_by_file_line: Dict[str, Dict[int, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        self.assignments_by_location: Dict[str, Dict[int, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        self.calls_by_location: Dict[str, Dict[int, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        self.successors_by_block: Dict[str, List[Dict]] = defaultdict(list)
        self.blocks_by_id: Dict[str, Dict] = {}

        self._build_spatial_indexes()

    def _build_spatial_indexes(self):
        """Build O(1) lookup indexes for line-based queries."""
        # Index symbols by type
        for symbol in self.symbols:
            self.symbols_by_type[symbol['type']].append(symbol)

        # Index assignments by location (file → line_block → assignments)
        for a in self.assignments:
            file = a.get('file', '')
            line = a.get('line', 0) or 0
            block = line // 100  # Group by 100-line blocks
            self.assignments_by_location[file][block].append(a)

        # ... similar for calls, symbols, CFG blocks ...
```

**Line Block Grouping** (100-line blocks):
- **Why 100**: Balance between index size and lookup efficiency
- Larger blocks (500): Fewer buckets but more false positives
- Smaller blocks (10): More buckets but higher memory overhead
- 100-line blocks: Sweet spot for typical function sizes

**Alternatives Considered**:

1. **Database Indexes (SQLite)**
   - **Rejected**: Requires schema changes and migration
   - SQLite indexes on ranges (BETWEEN) less efficient than hash lookups

2. **Pre-filter with SQL, Then Linear Scan**
   - **Rejected**: Still requires N queries to database
   - Database I/O slower than in-memory hash lookup

3. **R-Tree or KD-Tree Spatial Indexes**
   - **Rejected**: Overkill for 1D line number lookups
   - Simple hash map sufficient for our use case

**Implementation Strategy**:
- Build indexes in `SchemaMemoryCache.__init__` (one-time cost at startup)
- Replace all `for x in self.cache.symbols if ...` patterns with index lookups
- Backward compatible: Cache structure change is internal (consumers unchanged)

---

### Decision 3: LIKE Wildcard Elimination in Propagation

**Problem**: `WHERE source_expr LIKE '%pattern%'` forces full table scan (50M rows scanned)

**Decision**: Pre-filter by indexed columns (file, line), then Python substring search

**Rationale**:
- ✅ **Indexed Pre-filter**: `WHERE file = ? AND line BETWEEN ?` uses indexes
- ✅ **Python Substring Search**: `if pattern in expr` is fast on small result sets
- ✅ **100x Reduction**: 50,000 rows → 5 rows (typical line range) = 10,000x fewer rows scanned
- ✅ **Exact Same Results**: Substring search in Python = same logic as LIKE

**Pattern**:
```python
# BEFORE (Full Table Scan):
cursor.execute("""
    SELECT target_var, source_expr
    FROM assignments
    WHERE file = ? AND line BETWEEN ? AND ?
      AND source_expr LIKE ?
""", (file, start_line, end_line, f"%{pattern}%"))

# AFTER (Indexed Pre-filter):
cursor.execute("""
    SELECT target_var, source_expr
    FROM assignments
    WHERE file = ? AND line BETWEEN ? AND ?
""", (file, start_line, end_line))

# Python filter (fast on small result set):
for target_var, source_expr in cursor.fetchall():
    if pattern in source_expr:
        # Found match
```

**Alternatives Considered**:

1. **Full-Text Search (FTS5)**
   - **Rejected**: Requires schema changes (virtual table)
   - FTS overhead > benefit for small line ranges

2. **Regex Pre-compilation**
   - **Rejected**: Not a regex problem (substring search, not pattern match)
   - LIKE '%pattern%' = substring search, not regex

**Implementation Strategy**:
- Replace all LIKE wildcard patterns in `propagation.py` (2 locations)
- Replace all LIKE wildcard patterns in `graphql/injection.py` (1 location)
- Test with fixtures (verify findings unchanged)

---

### Decision 4: CFG Batch Loading

**Problem**: 10,000 database queries (1 query per CFG block × 100 blocks × 100 paths)

**Decision**: Batch load all CFG statements for function upfront (1 query instead of 10,000)

**Rationale**:
- ✅ **10,000x Reduction**: 10,000 queries → 1 query
- ✅ **Database Efficiency**: SQLite batch query faster than N small queries
- ✅ **Memory Acceptable**: ~1MB for typical function (100 blocks × 10KB/block)

**Pattern**:
```python
# BEFORE (N+1 Anti-Pattern):
for block in cfg_blocks:
    cursor.execute("SELECT ... WHERE block_id = ?", (block.id,))
    statements = cursor.fetchall()
    # Process statements

# AFTER (Batch Load):
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

# In analysis code:
for block in cfg_blocks:
    statements = self.cache.statements_by_block[block.id]  # O(1) lookup
```

**Alternatives Considered**:

1. **Lazy Loading with LRU Cache**
   - **Rejected**: Still requires N queries (just cached)
   - Cache hit rate low (each block visited once per path)

2. **JOIN Query (Fetch All Blocks + Statements)**
   - **Rejected**: Same as batch load, more complex SQL

**Implementation Strategy**:
- Add `statements_by_block` to `SchemaMemoryCache`
- Load in `__init__` (one-time cost)
- Replace all per-block queries with hash lookups

---

### Decision 5: Vue In-Memory Compilation

**Problem**: Disk I/O overhead (write temp file → read → delete) = 10-30ms per .vue file

**Decision**: Skip disk I/O, pass compiled code directly to TypeScript API

**Rationale**:
- ✅ **2-5x Speedup**: Eliminate I/O latency (10-30ms → 2-5ms)
- ✅ **TypeScript Supports It**: `ts.createSourceFile(path, content)` accepts string
- ✅ **Simple Change**: 5 lines of code
- ✅ **Zero Risk**: In-memory compilation is more robust (no temp file cleanup failures)

**Pattern**:
```javascript
// BEFORE (Disk I/O):
const tempPath = `/tmp/theauditor_vue_${scopeId}.js`;
fs.writeFileSync(tempPath, compiled.content);
const sourceFile = ts.createSourceFile(tempPath, fs.readFileSync(tempPath), ...);
fs.unlinkSync(tempPath);

// AFTER (In-Memory):
const virtualPath = `/virtual/${scopeId}.js`;  // Virtual path (not on disk)
const sourceFile = ts.createSourceFile(virtualPath, compiled.content, ...);
```

**Alternatives Considered**:

1. **Use OS RAM Disk**
   - **Rejected**: Platform-specific (not cross-platform)
   - Still has I/O syscall overhead

2. **Cache Compiled Vue Scripts**
   - **Deferred**: Good idea, but orthogonal to in-memory compilation
   - Can add later if profiling shows repeated compilation of same file

**Implementation Strategy**:
- Modify `batch_templates.js:prepareVueSfcFile()`
- Test on Vue 2 and Vue 3 fixture projects
- Verify extraction output matches

---

### Decision 6: Node Module Resolution

**Problem**: 40-60% of imports unresolved (breaks cross-file taint analysis)

**Decision**: Implement TypeScript module resolution algorithm

**Rationale**:
- ✅ **Critical for Taint**: Cross-file taint requires import graph
- ✅ **Standard Algorithm**: TypeScript module resolution is well-specified
- ✅ **Complexity Justified**: 40-60% improvement in import resolution

**Resolution Algorithm**:
1. **Relative imports**: `./utils/validation` → resolve relative to current file
2. **Path mappings**: `@/utils` → resolve via tsconfig.json paths
3. **Node modules**: `lodash` → resolve via node_modules + package.json exports

**Implementation Strategy**:
- Parse tsconfig.json for path mappings
- Implement Node.js module resolution algorithm
- Cache resolved modules (avoid re-resolving same import)

**Alternatives Considered**:

1. **Call TypeScript Compiler API via Node Subprocess**
   - **Accepted for Path Mappings**: TypeScript API handles complex tsconfig.json
   - **Rejected for Node Modules**: Too slow (subprocess overhead)

2. **Use require.resolve()**
   - **Rejected**: Not accurate for TypeScript (ignores tsconfig.json)

---

## Risks & Trade-offs

### Risk 1: Taint Analysis Correctness

**Risk**: Spatial index implementation introduces bugs (incorrect results)

**Likelihood**: Medium (complex logic with nested loops)

**Impact**: Critical (incorrect taint findings = security miss)

**Mitigation**:
1. ✅ **Fixture Validation**: Run 10 fixture projects, compare findings byte-for-byte
2. ✅ **Unit Tests**: Test spatial index builders independently
3. ✅ **Code Review**: Architect + Lead Auditor review before merge
4. ✅ **Phased Rollout**: Test internally before public release

**Rollback**: Revert commits (no schema changes, easy rollback)

---

### Risk 2: Python AST Visitor Extraction Parity

**Risk**: Unified visitor misses edge cases that individual extractors caught

**Likelihood**: Medium (70+ extractors to consolidate = high complexity)

**Impact**: High (missing framework detection = incomplete analysis)

**Mitigation**:
1. ✅ **Incremental Migration**: Migrate one framework at a time (SQLAlchemy → Django → Flask → ...)
2. ✅ **Fixture Testing**: Test each framework migration with dedicated fixture projects
3. ✅ **SQL Diff Validation**: Compare database contents before/after (catch any missing extractions)
4. ✅ **Backward Compat Window**: Keep old extractors for 1 release (fallback if issues found)

**Rollback**: Revert to old extractors (orchestrator switch)

---

### Risk 3: Performance Regression in Edge Cases

**Risk**: Spatial indexes degrade performance on pathological inputs (10,000-line functions)

**Likelihood**: Low (rare edge case)

**Impact**: Medium (slower on specific projects)

**Mitigation**:
1. ✅ **Adaptive Indexing**: Use different block sizes for large functions (auto-detect)
2. ✅ **Performance Tests**: Add benchmark tests to CI (fail if >20% regression)
3. ✅ **Profiling**: Monitor production usage, adjust indexes if needed

---

### Trade-off 1: Memory vs Speed

**Trade-off**: Spatial indexes add 10-20MB memory for 60,000x speedup

**Decision**: Accept memory cost (modern systems have GB of RAM)

**Rationale**: 10-20MB is negligible compared to typical Python process (500MB-4GB)

---

### Trade-off 2: Code Complexity vs Performance

**Trade-off**: Unified visitor is more complex than separate extractors

**Decision**: Accept complexity (long-term maintainability benefit)

**Rationale**: 800-line visitor is easier to maintain than 8,000+ lines across 9 files

---

## Migration Plan

### Phase 1: Tier 0 - Emergency (Week 1-2)

1. **Taint Analysis Refactor**
   - Day 1-2: Implement spatial indexes
   - Day 3-4: Refactor discovery/analysis/propagation
   - Day 5: Testing and validation
   - Day 6-7: Fix any issues found in testing

2. **Python AST Visitor**
   - Day 1-2: Design and scaffold UnifiedPythonVisitor
   - Day 3-6: Migrate framework extractors (2-3 frameworks per day)
   - Day 7-10: Testing and fixture validation
   - Day 11-12: Fix any extraction parity issues

**Gate**: All Tier 0 tests pass before proceeding to Tier 1

---

### Phase 2: Tier 1 - High Priority (Week 3-6)

1. **Vue In-Memory Compilation** (Week 3, Day 1)
   - 4-6 hours implementation + testing

2. **Node Module Resolution** (Week 3-6)
   - Week 3 Day 2-5: Implement relative imports + path mappings
   - Week 4: Implement node_modules resolution
   - Week 5: Testing and edge cases
   - Week 6: Integration testing with taint analysis

**Gate**: Import resolution rate >60% before considering Tier 1 complete

---

### Phase 3: Tier 2 - Medium Priority (Week 7)

1. **Database Indexes** (Day 1, 5 minutes)
2. **GraphQL LIKE Fixes** (Day 1, 30 minutes)
3. **Documentation Updates** (Day 2-3)
4. **Performance Regression Tests** (Day 4-5)

**Gate**: All tests pass, performance targets met, documentation complete

---

### Rollback Strategy

**Tier 0 Rollback**:
- Taint: Revert commits in `theauditor/taint/` (no schema changes)
- Python AST: Switch orchestrator back to old extractors (keep both for 1 release)

**Tier 1 Rollback**:
- Vue: Revert to disk I/O (1 line change)
- Module resolution: Revert to simplistic resolver

**Tier 2 Rollback**:
- Indexes: No rollback needed (additive only)
- GraphQL: Revert queries (2 line change)

**Emergency Rollback** (All Tiers):
- Git: `git revert <commit-range>`
- Database: No migration needed (indexes auto-recreate on next run)
- Zero downtime (pure code change)

---

## Open Questions

### Q1: Should We Add Performance Regression Tests to CI?

**Answer**: ✅ **YES** - Add benchmark tests that fail if performance degrades >20%

**Rationale**: Prevents future performance regressions

**Action**: Add to Tier 2 tasks

---

### Q2: Should We Keep Old Extractors for Backward Compat?

**Answer**: ✅ **YES (Temporarily)** - Keep for 1 release as safety net

**Rationale**: Easy rollback if unified visitor has issues

**Action**: Delete old extractors in v1.4 (after 1.3 stable)

---

### Q3: Should We Optimize JavaScript Extractors Similarly?

**Answer**: ⏸️ **NOT NOW** - JavaScript is already unified (TypeScript API)

**Rationale**: No redundant traversals in JS extraction (single code path via TypeScript Compiler API)

**Action**: Defer to future (only if profiling shows bottleneck)

---

## Success Criteria

### Performance Targets (Measured on 1,000 Python + 10K JS/TS files)

- ✅ **Indexing**: 90s → 12-18s (75-80% improvement)
- ✅ **Taint Analysis**: 10 min → 20-40s (95% improvement)
- ✅ **Pattern Detection**: Already optimal (no regression)

### Quality Targets

- ✅ All existing tests pass (no regressions)
- ✅ Fixture outputs match byte-for-byte (except timing metadata)
- ✅ Memory usage within 10% of baseline
- ✅ Import resolution rate >60% (Tier 1)

### Maintainability Targets

- ✅ Code coverage >80% for new code
- ✅ Documentation updated (CLAUDE.md, README)
- ✅ Performance regression tests in CI

---

## Decision Log

| Date | Decision | Rationale | Owner |
|------|----------|-----------|-------|
| 2025-11-02 | Single-Pass Visitor Pattern | 80x reduction in AST traversals | Opus |
| 2025-11-02 | Spatial Indexes for Taint | 60,000x reduction in operations | Opus |
| 2025-11-02 | LIKE Wildcard Elimination | 100x reduction in rows scanned | Opus |
| 2025-11-02 | CFG Batch Loading | 10,000x reduction in queries | Opus |
| 2025-11-02 | Vue In-Memory Compilation | 2-5x speedup, zero risk | Opus |
| 2025-11-02 | Node Module Resolution | Critical for taint accuracy | Opus |

---

**Last Updated**: 2025-11-02
**Status**: 🔴 **PROPOSAL STAGE** - Awaiting Architect approval
