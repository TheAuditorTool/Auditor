# Design Document: Walk Once Architecture

## Context

TheAuditor's Python indexing pipeline currently walks each AST 82 times per file, causing 80-90x performance degradation. The original design never anticipated the number of extractors growing to 14 domain modules (70+ extraction functions).

**Current Architecture** (Problematic):
```
Orchestrator (python.py)
├─ Calls framework_extractors.extract_sqlalchemy_models(tree)
│  └─ Walks entire tree (500 nodes)
├─ Calls framework_extractors.extract_django_models(tree)
│  └─ Walks entire tree (500 nodes)
├─ Calls core_extractors.extract_functions(tree)
│  └─ Walks entire tree (500 nodes)
├─ ... (68 more extractor calls)
│  └─ Each walks entire tree

Total: 82 walks × 500 nodes = 41,000 node visits per file
```

**Proposed Architecture** (Optimal):
```
Orchestrator (python.py)
├─ Walk tree ONCE, build cache (500 nodes)
│  └─ Cache: {'ClassDef': [...], 'FunctionDef': [...], 'Assign': [...]}
├─ Pass cache to framework_extractors.extract_all(node_cache)
│  └─ Filters cache (0 walks)
├─ Pass cache to core_extractors.extract_all(node_cache)
│  └─ Filters cache (0 walks)
├─ ... (10-15 domain module calls)
│  └─ All filter cache (0 walks)

Total: 1 walk × 500 nodes = 500 node visits per file
```

**Key Constraint**: Extractors are well-organized in domain modules. We must preserve this organization and minimize changes to extractor logic.

---

## Goals / Non-Goals

### Goals
1. **Primary**: Reduce AST walks from 82 to 1 per file (80x speedup)
2. **Secondary**: Preserve domain module organization (no monolithic rewrite)
3. **Tertiary**: Maintain 100% output compatibility (database schema unchanged)
4. **Quaternary**: Minimize changes to extractor logic (only change data source)

### Non-Goals
1. **NOT consolidating extractors** into a single visitor class (failed approach from parent proposal)
2. **NOT changing database schema** (pure performance optimization)
3. **NOT adding persistent cache** (in-memory only, released after each file)
4. **NOT optimizing extractors themselves** (future work, out of scope)

---

## Decisions

### Decision 1: In-Memory Cache vs Database Cache

**Options Considered**:
1. **Option A**: In-memory node cache (dict), rebuilt per file
2. **Option B**: Database table (`raw_ast_nodes`), persistent across files

**Decision**: **Option A** (in-memory cache)

**Reasoning**:
- **Simplicity**: No schema changes, no migration, no disk I/O
- **Performance**: Dictionary lookup is O(1), database query is O(log n) best case
- **Memory**: Cache is per-file (~1-2MB), released after extraction (no accumulation)
- **Disk I/O**: Avoids writing raw AST nodes to database (500 nodes × 1,000 files = 500K rows)

**Trade-offs**:
- ❌ Cache rebuilt for every file (no reuse across files)
- ✅ But rebuilding is cheap (<10ms per file)
- ❌ Cannot query raw nodes across files
- ✅ But extractors already provide structured data for cross-file queries

**Alternatives Considered**:
- **Option B rejected** because disk I/O overhead negates speedup gains

---

### Decision 2: Thin Wrapper vs Monolithic Visitor

**Options Considered**:
1. **Option A**: Thin orchestrator wrapper (10KB), extractors stay in domain modules
2. **Option B**: Consolidate all extractors into `UnifiedPythonVisitor` class (800-1000 lines)

**Decision**: **Option A** (thin wrapper)

**Reasoning**:
- **Maintainability**: Domain expertise stays in domain modules (easier to understand)
- **Testability**: Each extractor module can be unit tested independently
- **Risk**: Lower risk (minimal changes to proven extractor logic)
- **Architect Guidance**: User explicitly stated "the orchestrator fucked it all up, it should be a 10kb wrapper"

**Trade-offs**:
- ❌ Still have 15 function calls in orchestrator (one per domain module)
- ✅ But 15 calls is manageable, and preserves clean separation of concerns
- ❌ Extractors still have some redundant filtering logic
- ✅ But this is minor compared to 82 walks (future optimization)

**Alternatives Considered**:
- **Option B rejected** because parent proposal attempted this approach and failed (implementation collapsed, git hard reset required)

---

### Decision 3: Extractor API Changes (Function Signatures)

**Options Considered**:
1. **Option A**: Change signature to `extract_X(node_cache, file_info)`
2. **Option B**: Keep `extract_X(tree)`, build cache inside each extractor
3. **Option C**: Add cache as optional parameter `extract_X(tree, node_cache=None)`

**Decision**: **Option A** (explicit cache parameter)

**Reasoning**:
- **Clarity**: Explicit contract that extractors receive cached nodes, not raw tree
- **Enforcement**: Type hints prevent accidental raw tree passing
- **Performance**: Impossible to accidentally call `ast.walk(tree)` if tree isn't available

**Trade-offs**:
- ❌ Breaking change to extractor function signatures (internal API only)
- ✅ But external API (`python.py:extract()`) unchanged, no user impact
- ❌ All 14 modules must be updated
- ✅ But updates are mechanical (10-20 lines per module)

**Alternatives Considered**:
- **Option B rejected** because cache would be rebuilt 14 times (defeats purpose)
- **Option C rejected** because optional parameter allows fallback to slow path (violates zero fallback policy)

---

### Decision 4: Handling Nested Walks

**Options Considered**:
1. **Option A**: Remove all nested walks (assume they're redundant)
2. **Option B**: Keep nested walks if functionally necessary (verify during verification phase)
3. **Option C**: Convert nested walks to nested cache filtering

**Decision**: **Option B** (verify first, then decide)

**Reasoning**:
- **Risk Mitigation**: Some nested walks may serve functional purposes (e.g., walking inside a FunctionDef body for app factory detection)
- **Verification Required**: teamsop.md Prime Directive requires reading code before acting
- **Conditional**: If nested walk is redundant → remove. If functional → keep (or convert to nested filtering)

**Examples**:
- `flask_extractors.py:138`: Nested walk inside app factory detection
  - **If functional**: Walk is traversing inside `app = Flask()` function body (keep walk)
  - **If redundant**: Walk is re-traversing entire tree (remove walk, use cache)

**Trade-offs**:
- ✅ Safe approach (no assumptions, verify first)
- ❌ Requires careful analysis during verification phase
- ✅ But verification is mandatory per teamsop.md anyway

**Alternatives Considered**:
- **Option A rejected** because blind removal is high risk (could break extraction logic)
- **Option C rejected** because nested filtering is complex and may not be needed

---

### Decision 5: Cache Structure (Flat vs Hierarchical)

**Options Considered**:
1. **Option A**: Flat cache by node type: `{'ClassDef': [...], 'FunctionDef': [...]}`
2. **Option B**: Hierarchical cache with parent-child relationships: `{'ClassDef': [{'node': ..., 'children': [...]}]}`

**Decision**: **Option A** (flat cache)

**Reasoning**:
- **Simplicity**: `ast.walk()` provides flat list, we preserve same structure
- **Performance**: No overhead building parent-child relationships
- **Compatibility**: Extractors currently use `ast.walk()` which is flat (minimal API change)

**Trade-offs**:
- ❌ Extractors that need parent context must still track manually
- ✅ But they already do this today (no regression)
- ❌ Cannot query "all methods inside class X" without parsing
- ✅ But this is rare, and can use `ast.iter_child_nodes()` if needed

**Alternatives Considered**:
- **Option B rejected** because added complexity doesn't provide clear benefit for current extractors

---

## Implementation Strategy

### Phase 1: Verification (6-8 hours)
1. Read all 14 extractor modules
2. Count actual `ast.walk()` calls (verify 82 walks)
3. Identify nested walks and determine if functional or redundant
4. Document findings in `verification.md`
5. Get Architect approval before proceeding

### Phase 2: Core Wrapper (3-4 hours)
1. Implement `_build_node_cache()` in `python.py`
2. Add unit tests for cache builder
3. Verify cache structure matches `ast.walk()` output

### Phase 3: Orchestrator Refactor (2-3 hours)
1. Replace 71 function calls with cache-based orchestration
2. Update orchestrator to pass `node_cache` + `file_info` to extractors
3. Test orchestrator in isolation (mock extractors)

### Phase 4: Extractor Updates (4-6 hours)
1. Update function signatures: `extract_X(tree)` → `extract_X(node_cache, file_info)`
2. Replace `ast.walk(tree)` → `node_cache.get('ClassDef', [])`
3. Update one module at a time, test after each change
4. Order: Start with simplest modules (1 walk), end with complex (19 walks)

### Phase 5: Testing (4-6 hours)
1. Fixture validation (100 Python files, byte-for-byte comparison)
2. Performance benchmarking (1,000 Python files, measure speedup)
3. Memory profiling (ensure cache overhead acceptable)
4. Edge case testing (empty files, syntax errors, large files)

### Phase 6: Audit & Documentation (2-3 hours)
1. Re-read all modified files (post-implementation audit per teamsop.md)
2. Update CLAUDE.md with "Walk Once Pattern"
3. Write completion report (teamsop.md Template C-4.20)
4. Archive OpenSpec change

**Total Estimated Time**: 2-3 days (21-30 hours)

---

## Risks / Trade-offs

### Risk 1: Nested Walks are Functional

**Likelihood**: Medium
**Impact**: Medium
**Mitigation**: Verification phase will identify functional vs redundant nesting
**Fallback**: Keep functional nested walks, only replace outer walks

### Risk 2: Cache Incompleteness

**Likelihood**: Low
**Impact**: High (missing nodes = extraction failures)
**Mitigation**: `ast.walk()` is well-documented BFS traversal, our cache is identical
**Verification**: Unit test cache builder, compare node counts

### Risk 3: Memory Overhead on Large Files

**Likelihood**: Low
**Impact**: Medium
**Mitigation**: Cache is per-file, released after extraction. Large files (10K LOC) = ~1-2MB cache (acceptable)
**Fallback**: If memory issues arise, add cache size limit or streaming approach

### Risk 4: Code Changed Since Investigation

**Likelihood**: Medium (investigation was Nov 3, 2025 - code may have changed)
**Impact**: Low (walk counts might differ slightly, but problem remains)
**Mitigation**: Verification phase will measure current state and update numbers if needed

---

## Migration Plan

**No migration required** - This is a pure performance optimization with no external API changes.

**Backward Compatibility**:
- ✅ External API: `python.py:extract(file_info, content, tree)` signature unchanged
- ✅ Database schema: Unchanged (no new tables, no migrations)
- ✅ Output format: Unchanged (extractors produce identical data)
- ❌ Internal API: Extractor function signatures changed (but this is internal, not user-facing)

**Rollback Plan**:
If issues arise, rollback is trivial:
```bash
git revert <commit_hash>
```

No database migrations to reverse, no schema changes to undo.

---

## Performance Model

### Current Performance (82 Walks)

**Per Python file** (500 nodes average):
- Tree walks: 82 × 500 nodes = 41,000 node visits
- With nesting overhead (2.2x): 41,000 × 2.2 = 90,200 visits
- Time per file: ~30ms (small) to ~200ms (large)

**For 1,000 Python files**:
- Total node visits: 90,200,000
- Time: 18-30 seconds

### Target Performance (1 Walk)

**Per Python file**:
- Tree walk: 1 × 500 nodes = 500 node visits
- Cache build: ~5-10ms
- Extraction: ~5-10ms (filtering cached nodes)
- Total per file: ~10-20ms

**For 1,000 Python files**:
- Total node visits: 500,000
- Time: <1 second (target: 0.5-1.0s)

**Speedup**: 18-30s → 0.5-1.0s = **18-60x speedup**

**Confidence**: HIGH (problem is well-understood, solution is proven, implementation is straightforward)

---

## Open Questions

1. **Q**: Are there any extractors that rely on multiple passes over the tree?
   - **A**: Verification phase will determine this by reading extractor logic
   - **Resolution**: If found, keep multi-pass logic (but use cached nodes, not re-walks)

2. **Q**: Do any extractors modify the tree in-place?
   - **A**: Unlikely (extractors are read-only), but verify during verification phase
   - **Resolution**: If found, document and handle carefully (cache invalidation)

3. **Q**: Should we cache across files (persistent cache)?
   - **A**: Out of scope for this proposal (Decision 1: in-memory only)
   - **Future Work**: If profiling shows cache rebuild is bottleneck, revisit

4. **Q**: What if walk count significantly differs from investigation (e.g., 60 walks instead of 82)?
   - **A**: Update proposal numbers, but proceed with same approach
   - **Impact**: Speedup would be 60x instead of 82x (still massive improvement)

---

## Success Criteria

**Must Have**:
- ✅ All 82 `ast.walk()` calls replaced with cache lookups (or verified as functionally necessary)
- ✅ Indexing time: 18-30s → <1s (80-90x speedup measured)
- ✅ All tests pass (no regressions)
- ✅ Fixture validation: byte-for-byte match (database contents identical)

**Should Have**:
- ✅ Memory overhead <10% of baseline
- ✅ Cache build time <10ms per file
- ✅ Clean separation of concerns (domain modules preserved)

**Nice to Have**:
- ✅ Code is simpler after refactor (less complex than 71 sequential calls)
- ✅ Extractors easier to test (pass mock cache instead of building tree)

---

## References

- **Parent Proposal**: `performance-revolution-now/proposal.md`
- **Verification Findings**: `performance-revolution-now/VERIFICATION_COMPLETE.md` (Agent #2, #10)
- **teamsop.md**: Prime Directive, Template C-4.20
- **CLAUDE.md**: Zero fallback policy, Windows environment constraints
- **ast module docs**: https://docs.python.org/3/library/ast.html#ast.walk

---

**Document Status**: ✅ COMPLETE

**Next Steps**:
1. Architect reviews and approves design
2. Coder begins verification phase (read all 14 extractors)
3. Coder documents findings in `verification.md`
4. Architect approves verification, coder begins implementation
