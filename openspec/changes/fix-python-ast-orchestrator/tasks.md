# Fix Python AST Orchestrator - Implementation Tasks

**CRITICAL - teamsop.md v4.20 Prime Directive**: Do NOT start implementation until:
1. ✅ Architect approves `proposal.md`
2. ✅ Verification phase completed (see `verification.md`)
3. ✅ Architect approves verification findings

---

## 0. Verification Phase (MANDATORY - Complete Before Coding)

**Objective**: Verify all assumptions from parent investigation by reading actual code

**From teamsop.md v4.20**:
> "Before writing or modifying a single line of code, you MUST first perform a Verification Phase. The output of this phase is the first section of your final report. You must explicitly list your initial hypotheses and then present the evidence from the code that confirms or refutes them."

**Protocol**: Question Everything, Assume Nothing, Verify Everything.

### 0.1 Read All Extractor Modules

- [ ] 0.1.1 Read `theauditor/ast_extractors/python/framework_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 19 walks)
  - Document each walk's purpose
  - Identify any functional dependencies on traversal order
- [ ] 0.1.2 Read `theauditor/ast_extractors/python/core_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 19 walks)
  - **CRITICAL**: Verify triply-nested walk at line 1053 (generator detection)
  - Determine if nested walks serve functional purpose or are redundant
- [ ] 0.1.3 Read `theauditor/ast_extractors/python/flask_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 10 walks)
  - **CRITICAL**: Verify nested walk at line 138 (app factory detection)
  - Determine if nested walk is for app factory traversal or can be replaced
- [ ] 0.1.4 Read `theauditor/ast_extractors/python/async_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 9 walks)
  - Document nested walks at lines 50, 60, 64
  - Verify these are redundant traversals (not functional logic)
- [ ] 0.1.5 Read `theauditor/ast_extractors/python/security_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 8 walks)
  - Document walk purposes
- [ ] 0.1.6 Read `theauditor/ast_extractors/python/testing_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 8 walks)
  - Document walk purposes
- [ ] 0.1.7 Read `theauditor/ast_extractors/python/type_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 5 walks)
  - Document walk purposes
- [ ] 0.1.8 Read `theauditor/ast_extractors/python/orm_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 1 walk)
  - Document walk purpose
- [ ] 0.1.9 Read `theauditor/ast_extractors/python/validation_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 6 walks)
  - Document walk purposes
- [ ] 0.1.10 Read `theauditor/ast_extractors/python/django_web_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 6 walks)
  - Document walk purposes
- [ ] 0.1.11 Read `theauditor/ast_extractors/python/task_graphql_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 6 walks)
  - Document walk purposes
- [ ] 0.1.12 Read `theauditor/ast_extractors/python/cfg_extractor.py`
  - Count `ast.walk()` calls (hypothesis: 1 walk)
  - Document walk purpose
- [ ] 0.1.13 Read `theauditor/ast_extractors/python/cdk_extractor.py`
  - Count `ast.walk()` calls (hypothesis: 1 walk)
  - Document walk purpose
- [ ] 0.1.14 Read `theauditor/ast_extractors/python/django_advanced_extractors.py`
  - Count `ast.walk()` calls (hypothesis: 0 walks)
  - Confirm no walks

### 0.2 Read Orchestrator

- [ ] 0.2.1 Read `theauditor/indexer/extractors/python.py`
  - Verify lines 243-602 contain orchestration logic
  - Count extractor function calls (hypothesis: 71 calls)
  - Document current orchestration pattern
  - Identify dependencies between extractors (if any)

### 0.3 Verify Performance Claims

- [ ] 0.3.1 Benchmark current indexing performance
  - Run `aud index` on test project (1,000 Python files)
  - Measure time (hypothesis: 18-30 seconds)
  - Profile with cProfile to confirm AST walking is bottleneck
- [ ] 0.3.2 Measure memory baseline
  - Measure peak memory usage during indexing
  - Document baseline for comparison after optimization

### 0.4 Document Verification Findings

- [ ] 0.4.1 Update `verification.md` with all findings
  - List hypothesis vs actual for each extractor
  - Document any discrepancies from parent investigation
  - Identify any blockers or risks discovered
- [ ] 0.4.2 Get Architect approval on verification
  - Submit verification findings to Architect
  - Address any questions or concerns
  - Obtain approval to proceed with implementation

**Status**: ⚠️ **BLOCKING** - No implementation may proceed until this section is complete and approved

---

## 1. Implementation Phase

### 1.1 Build Node Cache Wrapper

**Objective**: Create 10KB wrapper that walks tree once and caches nodes by type

**Estimated Time**: 3-4 hours

- [ ] 1.1.1 Implement `_build_node_cache()` function
  ```python
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
- [ ] 1.1.2 Add unit tests for `_build_node_cache()`
  - Test with minimal AST tree (3-5 nodes)
  - Verify all node types captured
  - Verify node count matches `ast.walk()` count
  - Test with empty tree (edge case)
- [ ] 1.1.3 Add type hints and docstrings
  - Document cache structure
  - Document performance characteristics (O(n) where n = nodes)

### 1.2 Update Orchestrator

**Objective**: Replace 71 function calls with cache-based orchestration

**Estimated Time**: 2-3 hours

- [ ] 1.2.1 Refactor `extract()` function in `python.py`
  - BEFORE: 71 sequential `extractor.extract_X(tree)` calls
  - AFTER: Build cache once, pass to `extractor.extract_all(node_cache, file_info)` calls
- [ ] 1.2.2 Update function signature
  - Keep external API unchanged: `extract(file_info, content, tree)`
  - Internal: Build cache from tree
- [ ] 1.2.3 Test orchestrator in isolation
  - Verify cache is built correctly
  - Verify extractors are called with cache

### 1.3 Update Extractor Modules (14 files)

**Objective**: Replace `ast.walk(tree)` with `node_cache.get(node_type, [])`

**Estimated Time**: 4-6 hours (30-45 min per module)

#### Pattern for All Modules

```python
# BEFORE
def extract_X(tree: ast.AST) -> dict:
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Extract logic...

# AFTER
def extract_X(node_cache: Dict[str, List[ast.Node]], file_info: FileInfo) -> dict:
    results = []
    for node in node_cache.get('ClassDef', []):
        # Extract logic... (UNCHANGED)
```

#### 1.3.1 Update `framework_extractors.py`
- [ ] Replace 19 `ast.walk()` calls with cache lookups
- [ ] Update function signatures to accept `node_cache` + `file_info`
- [ ] Test on SQLAlchemy/Django fixture projects
- [ ] Verify extracted models match original output

#### 1.3.2 Update `core_extractors.py`
- [ ] Replace 19 `ast.walk()` calls with cache lookups
- [ ] **CRITICAL**: Handle triply-nested walk at line 1053
  - Verify nested walk is redundant (verification phase should confirm)
  - Replace with cache lookup if safe
- [ ] Test on Python fixture projects
- [ ] Verify extracted functions/classes match original output

#### 1.3.3 Update `flask_extractors.py`
- [ ] Replace 10 `ast.walk()` calls with cache lookups
- [ ] **CRITICAL**: Handle nested walk at line 138 (app factories)
  - If nested walk is functional (walks inside factory body), keep it
  - If nested walk is redundant (re-walks entire tree), replace
- [ ] Test on Flask fixture projects
- [ ] Verify extracted routes/blueprints match original output

#### 1.3.4 Update `async_extractors.py`
- [ ] Replace 9 `ast.walk()` calls with cache lookups
- [ ] Handle nested walks at lines 50, 60, 64
  - Verification phase should confirm these are redundant
- [ ] Test on async Python fixture projects
- [ ] Verify extracted async functions match original output

#### 1.3.5 Update `security_extractors.py`
- [ ] Replace 8 `ast.walk()` calls with cache lookups
- [ ] Test on security fixture projects
- [ ] Verify extracted patterns match original output

#### 1.3.6 Update `testing_extractors.py`
- [ ] Replace 8 `ast.walk()` calls with cache lookups
- [ ] Test on pytest fixture projects
- [ ] Verify extracted fixtures/tests match original output

#### 1.3.7 Update `type_extractors.py`
- [ ] Replace 5 `ast.walk()` calls with cache lookups
- [ ] Test on typed Python fixture projects
- [ ] Verify extracted type annotations match original output

#### 1.3.8 Update `orm_extractors.py`
- [ ] Replace 1 `ast.walk()` call with cache lookup
- [ ] Test on ORM fixture projects

#### 1.3.9 Update `validation_extractors.py`
- [ ] Replace 6 `ast.walk()` calls with cache lookups
- [ ] Test on Pydantic fixture projects

#### 1.3.10 Update `django_web_extractors.py`
- [ ] Replace 6 `ast.walk()` calls with cache lookups
- [ ] Test on Django fixture projects

#### 1.3.11 Update `task_graphql_extractors.py`
- [ ] Replace 6 `ast.walk()` calls with cache lookups
- [ ] Test on Celery/GraphQL fixture projects

#### 1.3.12 Update `cfg_extractor.py`
- [ ] Replace 1 `ast.walk()` call with cache lookup
- [ ] Test CFG extraction still works

#### 1.3.13 Update `cdk_extractor.py`
- [ ] Replace 1 `ast.walk()` call with cache lookup
- [ ] Test on CDK fixture projects

#### 1.3.14 Verify `django_advanced_extractors.py`
- [ ] Confirm no changes needed (0 walks)

---

## 2. Testing & Validation

### 2.1 Fixture Validation

**Objective**: Ensure extracted data matches original output byte-for-byte

**Estimated Time**: 2-3 hours

- [ ] 2.1.1 Run on 100 Python fixture projects
  - Cover all framework types (Flask, Django, FastAPI, SQLAlchemy, Pydantic, etc.)
  - Extract data with NEW orchestrator
  - Compare database contents with baseline (original orchestrator)
- [ ] 2.1.2 Byte-for-byte comparison
  - Use SQL diff tool to verify no regressions
  - Ignore timing/metadata fields
  - All symbols, functions, classes, routes, models must match exactly
- [ ] 2.1.3 Document any discrepancies
  - If discrepancies found, investigate root cause
  - Fix extractor logic if needed
  - Re-run validation until 100% match

### 2.2 Performance Benchmarking

**Objective**: Measure actual speedup (target: 80-90x)

**Estimated Time**: 1-2 hours

- [ ] 2.2.1 Benchmark on 1,000 Python files
  - Before: Measure with original orchestrator (baseline: 18-30s)
  - After: Measure with new cache-based orchestrator
  - Calculate speedup ratio
- [ ] 2.2.2 Profile with cProfile
  - Verify `ast.walk()` is no longer bottleneck
  - Confirm cache building is fast (<100ms per file)
  - Identify any new bottlenecks (if any)
- [ ] 2.2.3 Document results in verification.md
  - Actual speedup vs target (80-90x)
  - Performance breakdown (cache build vs extraction)

### 2.3 Memory Profiling

**Objective**: Ensure cache overhead is acceptable (<5MB per file)

**Estimated Time**: 1 hour

- [ ] 2.3.1 Measure peak memory usage
  - Before: Baseline memory (from verification phase)
  - After: Memory with node cache
  - Calculate overhead
- [ ] 2.3.2 Test on large files (10K LOC)
  - Verify cache overhead is acceptable
  - Expected: ~1-2MB per 10K LOC file
- [ ] 2.3.3 Verify cache is released
  - Cache should be garbage collected after each file
  - No memory leaks

### 2.4 Edge Case Testing

**Objective**: Ensure correctness on edge cases

**Estimated Time**: 1 hour

- [ ] 2.4.1 Empty Python files
  - Verify no crashes
  - Verify empty cache handled correctly
- [ ] 2.4.2 Syntax error files
  - Verify graceful handling (should skip extraction)
- [ ] 2.4.3 Very large files (>10K LOC)
  - Verify performance still acceptable
  - Verify memory usage within bounds
- [ ] 2.4.4 Deeply nested structures
  - Verify all nodes captured in cache
  - Verify nested classes/functions extracted correctly

---

## 3. Post-Implementation Audit (teamsop.md v4.20 Requirement)

**From teamsop.md**:
> "After implementation, the Coder MUST re-read the entirety of all modified files to confirm correctness and ensure no syntax errors, logical flaws, or unintended side effects were introduced."

### 3.1 Re-read All Modified Files

- [ ] 3.1.1 Re-read `theauditor/indexer/extractors/python.py`
  - Verify syntax correctness
  - Verify logic is sound (cache built once, passed to extractors)
  - Verify no unintended side effects
- [ ] 3.1.2 Re-read all 14 extractor modules
  - Verify syntax correctness for each
  - Verify function signatures updated correctly
  - Verify logic unchanged (only data source changed)
- [ ] 3.1.3 Document audit results in final report
  - Status: ✅ SUCCESS or ❌ ISSUES FOUND
  - List any issues found and how they were resolved

### 3.2 Run Full Test Suite

- [ ] 3.2.1 Run pytest on entire codebase
  ```bash
  pytest tests/ -v --tb=short
  ```
  - All tests must pass
  - No new failures introduced
- [ ] 3.2.2 Run integration tests
  - Full `aud index` pipeline on test projects
  - Verify all extractors work end-to-end
  - Verify database populated correctly

---

## 4. Documentation & Deployment

### 4.1 Update Documentation

- [ ] 4.1.1 Update CLAUDE.md
  - Add "Walk Once Pattern" section
  - Document node cache architecture
  - Add anti-pattern: "Multiple independent ast.walk() calls"
- [ ] 4.1.2 Update extractor module docstrings
  - Document that extractors accept node_cache
  - Document expected cache structure
- [ ] 4.1.3 Add inline comments in orchestrator
  - Explain cache build process
  - Explain why this is faster (1 walk vs 82 walks)

### 4.2 Create Final Report (teamsop.md Template C-4.20)

- [ ] 4.2.1 Write completion report following template
  - Phase: Fix Python AST Orchestrator
  - Objective: Reduce 82 walks to 1 walk
  - Status: COMPLETE
- [ ] 4.2.2 Include all required sections:
  1. Verification Phase Report (from verification.md)
  2. Deep Root Cause Analysis
  3. Implementation Details & Rationale
  4. Edge Case & Failure Mode Analysis
  5. Post-Implementation Integrity Audit
  6. Impact, Reversion, & Testing
  7. Confirmation of Understanding

### 4.3 Archive OpenSpec Change

- [ ] 4.3.1 Run `openspec validate fix-python-ast-orchestrator --strict`
  - Fix any validation errors
- [ ] 4.3.2 Get Architect final approval
- [ ] 4.3.3 Archive change
  ```bash
  openspec archive fix-python-ast-orchestrator --yes
  ```
- [ ] 4.3.4 Update parent proposal
  - Mark `performance-revolution-now` TIER 0 Task 2 as "Completed via fix-python-ast-orchestrator"

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

- [ ] Verification phase complete (Section 0)
- [ ] Architect approved verification findings
- [ ] Implementation complete (Section 1)
- [ ] All tests passing (Section 2)
- [ ] Performance targets met:
  - Indexing: 18-30s → <1s (80-90x speedup)
  - Node visits: 90.2M → 500K (180x reduction)
  - Memory: Within 10% of baseline
- [ ] Fixtures validated (byte-for-byte match)
- [ ] Post-implementation audit complete (Section 3)
- [ ] Documentation updated (Section 4)
- [ ] Final report submitted (teamsop.md Template C-4.20)
- [ ] Architect final approval
- [ ] Change archived

---

**Current Status**: 🔴 **VERIFICATION PHASE** - Complete Section 0 before starting implementation

**Estimated Total Time**: 2-3 days (6-8 hours verification + 8-10 hours implementation + 4-6 hours testing)
