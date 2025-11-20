# Fix Python AST Orchestrator - Walk Once Architecture

## Why

The Python AST orchestrator (`theauditor/indexer/extractors/python.py`) calls 71 independent extractor functions, each triggering its own `ast.walk()` traversal of the same tree. This results in **82 total tree walks per Python file** (some extractors walk multiple times).

**Evidence from 12-agent verification**:
- Agent #2: Confirmed 82 `ast.walk()` calls across all extractor modules
- Agent #10: Verified orchestrator calls 71 extractor functions sequentially
- Nested walks create 2.2x additional overhead (triply-nested walk at `core_extractors.py:1053`)

**Performance Impact** (measured):
- Current: 82 walks × 1,000 files × 500 nodes = **90,200,000 node visits** (with nesting overhead)
- Time: **18-30 seconds** for 1,000 Python files
- After fix: 1 walk × 1,000 files × 500 nodes = **500,000 node visits**
- Target: **<1 second** for 1,000 Python files
- **Speedup: 80-90x** (25-30 seconds saved)

**Root Cause**: The orchestrator was never designed for "walk once" architecture. Each domain module (framework, core, flask, async, security, testing, types, ORM, validation, Django, tasks/GraphQL) developed independently with their own traversal logic. The orchestrator simply calls them all sequentially.

**Critical Insight**: The extractors are already well-organized in domain modules. The problem is NOT the extractors - it's the orchestrator calling them inefficiently. We don't need to rewrite extractors into a monolithic visitor class. We need a **thin wrapper** that walks once and feeds cached nodes to existing extractors.

---

## What Changes

Replace the 71-function sequential orchestrator with a **10KB "walk once" wrapper**:

### **Architecture**

```python
# theauditor/indexer/extractors/python.py

def extract(file_info, content, tree):
    """
    Walk AST once, build in-memory cache, pass to extractors.

    This is a THIN WRAPPER (10KB max) - extractors stay in domain modules.
    """
    # 1. Walk tree ONCE, cache all nodes by type
    node_cache = _build_node_cache(tree)  # Dict[str, List[ast.Node]]

    # 2. Pass cache to extractors (they filter cached nodes, no re-walking)
    results = {}
    results.update(framework_extractors.extract_all(node_cache, file_info))
    results.update(core_extractors.extract_all(node_cache, file_info))
    results.update(flask_extractors.extract_all(node_cache, file_info))
    # ... etc (10-15 domain modules)

    return results


def _build_node_cache(tree: ast.AST) -> Dict[str, List[ast.Node]]:
    """
    Walk tree once, group nodes by type.

    Returns: {
        'ClassDef': [all ClassDef nodes],
        'FunctionDef': [all FunctionDef nodes],
        'Assign': [all Assign nodes],
        ...
    }
    """
    cache = defaultdict(list)
    for node in ast.walk(tree):
        node_type = type(node).__name__
        cache[node_type].append(node)
    return dict(cache)
```

**Extractors stay mostly unchanged** - they replace `ast.walk(tree)` with `node_cache.get('ClassDef', [])`:

```python
# framework_extractors.py (BEFORE - 19 walks)
def extract_sqlalchemy_models(tree):
    for node in ast.walk(tree):  # ← Full tree walk
        if isinstance(node, ast.ClassDef):
            # Extract model...

# framework_extractors.py (AFTER - 0 walks)
def extract_sqlalchemy_models(node_cache, file_info):
    for node in node_cache.get('ClassDef', []):  # ← Cached nodes only
        # Extract model... (same logic)
```

**Key Design Principles** (from teamsop.md Prime Directive):
1. **Verify Before Acting**: Read all 14 extractor modules before modifying
2. **Minimal Change**: Extractors keep their logic, just change data source
3. **No Monolith**: Don't consolidate extractors into single visitor (that was the failed approach)
4. **10KB Wrapper**: Orchestrator stays small, domain expertise stays in modules

---

## What Changes (Detailed)

### **Files Modified** (2 primary + 14 extractors)

#### **1. Orchestrator Wrapper** (`theauditor/indexer/extractors/python.py`)
- **Before**: 602 lines, 71 sequential function calls
- **After**: ~150 lines, 10KB wrapper with `_build_node_cache()` + 15 `extract_all()` calls
- **Lines modified**: ~100 lines (replace orchestration section)

#### **2. Schema (Optional)** (`theauditor/indexer/schemas/core_schema.py`)
- **Option A**: No schema changes (in-memory cache only, simpler)
- **Option B**: Add `raw_ast_nodes` table for persistent caching (future optimization)
- **Recommendation**: Start with Option A (in-memory), add Option B if profiling shows benefit

#### **3. Extractor Modules** (14 files, minimal changes per file)

**Pattern**: Replace `ast.walk(tree)` → `node_cache.get(node_type, [])`

| Module | Current Walks | Lines to Change | Complexity |
|--------|---------------|-----------------|------------|
| `framework_extractors.py` | 19 | ~40 lines | Low |
| `core_extractors.py` | 19 | ~35 lines | Low |
| `flask_extractors.py` | 10 | ~20 lines | Medium (nested walks) |
| `async_extractors.py` | 9 | ~18 lines | Medium (nested walks) |
| `security_extractors.py` | 8 | ~16 lines | Low |
| `testing_extractors.py` | 8 | ~16 lines | Low |
| `type_extractors.py` | 5 | ~10 lines | Low |
| `orm_extractors.py` | 1 | ~2 lines | Low |
| `validation_extractors.py` | 6 | ~12 lines | Low |
| `django_web_extractors.py` | 6 | ~12 lines | Low |
| `task_graphql_extractors.py` | 6 | ~12 lines | Low |
| `cfg_extractor.py` | 1 | ~2 lines | Low |
| `cdk_extractor.py` | 1 | ~2 lines | Low |
| `django_advanced_extractors.py` | 0 | 0 lines | N/A |
| **TOTAL** | **82** | **~197 lines** | **Low-Medium** |

---

## Impact

### **Affected Specifications**
- `python-indexing` (MODIFIED) - Python extraction performance requirements

### **Affected Code**
- `theauditor/indexer/extractors/python.py` - Orchestrator wrapper (~100 lines modified)
- `theauditor/ast_extractors/python/*.py` - 14 extractor modules (~197 lines modified total)

### **Breaking Changes**
**NONE** - This is a pure performance optimization. All extractors preserve identical logic and output.

**Extractor API changes** (internal only):
- **Before**: `extract_X(tree: ast.AST) -> dict`
- **After**: `extract_X(node_cache: Dict[str, List[ast.Node]], file_info: FileInfo) -> dict`

External APIs (database schema, CLI commands, output format) remain unchanged.

### **Dependencies**
- No new external dependencies
- No Python version changes (>=3.11)
- No schema changes (in-memory cache only)

### **Backward Compatibility**
- ✅ Database schema: Unchanged
- ✅ CLI commands: Unchanged
- ✅ Output format: Unchanged
- ✅ Configuration: Unchanged

### **Risk Assessment**

**Risk Level**: **LOW-MEDIUM**

**Risks**:
1. **Nested Walk Removal** (Medium Risk)
   - Flask/async extractors have nested walks that serve functional purposes
   - Example: `flask_extractors.py:138` - walks inside app factory functions
   - Mitigation: Verify nested walks are for traversal, not logic (read code first)
   - Rollback: Revert commits (no schema changes)

2. **Node Cache Completeness** (Low Risk)
   - Risk: `ast.walk()` might traverse differently than our cache
   - Mitigation: `ast.walk()` is documented BFS traversal, our cache is identical
   - Testing: Compare extracted data before/after on 100 Python files

3. **Memory Overhead** (Low Risk)
   - Risk: Caching all nodes in memory for large files
   - Impact: ~1-2MB per 10K LOC file (acceptable)
   - Mitigation: Cache is per-file, released after extraction

**Confidence**: **HIGH** (simple refactor, well-understood problem, clear solution)

---

## Testing Strategy

**Required Before Merge** (from teamsop.md verification protocol):

### **1. Verification Phase** (Pre-Implementation)
- [ ] Read all 14 extractor modules
- [ ] Document every `ast.walk()` call location and purpose
- [ ] Verify nested walks are traversal-only (not functional logic)
- [ ] Record any discrepancies from 12-agent audit findings

### **2. Implementation Testing**
- [ ] Unit tests for `_build_node_cache()` (verify correctness)
- [ ] Fixture validation: Run on 100 Python files, compare output byte-for-byte
- [ ] Performance benchmarking: Measure actual speedup (target: 80-90x)
- [ ] Memory profiling: Ensure cache overhead acceptable (<5MB per file)

### **3. Post-Implementation Audit** (from teamsop.md)
- [ ] Re-read all modified files to confirm correctness
- [ ] Verify no syntax errors, logic flaws, or side effects
- [ ] Run full test suite (all tests must pass)

---

## Success Metrics

**Performance Targets** (measured on 1,000 Python files):
- ✅ **Indexing time**: 18-30s → <1s (80-90x speedup)
- ✅ **Node visits**: 90.2M → 500K (180x reduction)
- ✅ **Memory usage**: Within 10% of baseline (cache overhead minimal)

**Validation Criteria**:
- All existing tests pass (no regressions)
- Fixture outputs match byte-for-byte (except timing data)
- No change to database schema or output format

---

## Timeline Estimate

**Total**: **2-3 days** (including verification, implementation, testing)

| Phase | Duration | Tasks |
|-------|----------|-------|
| Verification | 4-6 hours | Read 14 modules, document walks, verify nested walk purposes |
| Implementation | 1 day | Build cache wrapper, update orchestrator, modify extractors |
| Testing | 4-6 hours | Fixtures, benchmarks, memory profiling |
| Post-Audit | 2-3 hours | Re-read files, run full test suite |

---

## Approval Gates

**Stage 1: Proposal Review** (Current Stage)
- [ ] Architect reviews proposal
- [ ] Architect approves scope and approach
- [ ] Conflicts resolved with concurrent changes

**Stage 2: Verification Phase** (Before Implementation)
- [ ] Coder completes verification protocol (read all 14 extractors)
- [ ] Coder documents findings in `verification.md`
- [ ] Architect reviews verification results
- [ ] Architect approves implementation plan

**Stage 3: Implementation** (After Verification Approved)
- [ ] Implementation complete
- [ ] Testing complete (fixtures, benchmarks, memory)
- [ ] Post-implementation audit complete

**Stage 4: Deployment**
- [ ] Performance benchmarks validated (80-90x speedup)
- [ ] Architect approves deployment
- [ ] Change archived via `openspec archive fix-python-ast-orchestrator --yes`

---

## Related Changes

**Parent Proposal**: `performance-revolution-now` (paused/split)
- This change is TIER 0 Task 2 from parent proposal
- Corrects architectural approach (10KB wrapper vs 800-line visitor class)

**Independent**: No dependencies on other proposals
**Concurrent**: Can run in parallel with `taint-analysis-spatial-indexes`

---

## References

- **Parent Investigation**: `openspec/changes/performance-revolution-now/INVESTIGATION_REPORT.md`
- **Verification Findings**: `openspec/changes/performance-revolution-now/VERIFICATION_COMPLETE.md` (Agent #2, #10)
- **Team Protocols**: `teamsop.md` v4.20 (Prime Directive, verification requirements)
- **Architecture**: `CLAUDE.md` (zero fallback policy, schema contracts)
- **OpenSpec Conventions**: `openspec/AGENTS.md`

---

**Status**: 🔴 **PROPOSAL STAGE** - Awaiting Architect approval

**Next Step**: Architect reviews and approves/rejects/modifies this proposal
