# Performance Revolution Now

## Why

TheAuditor suffers from systemic "death by 1000 cuts" performance degradation caused by redundant traversal anti-patterns across all major subsystems. Independent performance investigation (INVESTIGATION_REPORT.md) confirmed:

- **90-second indexing** → Should be 9-15 seconds (80-90% slower than optimal)
- **10-minute taint analysis** → Should be 10-30 seconds (95-98% slower than optimal)
- **95-second pattern detection** → Should be 5-10 seconds (90% slower than optimal)

The root cause is **NOT** a single bug, but a **codewide architectural pattern** of redundant operations:
- 80 full AST tree walks per Python file (should be 1)
- 60 BILLION operations in taint analysis (should be 1 million)
- Missing database indexes + LIKE wildcard patterns

This was discovered following the `regex_perf.md` fix (7,900x LIKE wildcard speedup), which revealed the tip of a much larger iceberg.

**Impact**: TheAuditor is currently **5-40x slower** than it should be across all operations. This makes the tool unusable on large codebases (>100K LOC) and creates a poor user experience even on small projects.

**Urgency**: P0 - This is a critical architectural issue that affects every user, every run, and justifies dropping all other work to fix.

---

## What Changes

This proposal eliminates redundant traversal anti-patterns through surgical refactoring of 3 core subsystems:

### **TIER 0 - EMERGENCY (1-2 Weeks)**

#### **1. Taint Analysis Refactor** (95% speedup: 10 min → 30s)
- **BREAKING**: Refactor `theauditor/taint/` architecture from N+1 linear scans to indexed lookups
- Add spatial indexes to `SchemaMemoryCache` (symbols_by_type, assignments_by_location, calls_by_location)
- Replace LIKE wildcard patterns in `propagation.py` with indexed pre-filtering
- Batch load CFG statements (1 query instead of 10,000)
- **Impact**: 540 seconds saved per run (60,000x operation reduction)

#### **2. Python AST Single-Pass Visitor** (80% speedup: 30s → 5s per 1K files)
- **BREAKING**: Replace 80 independent `ast.walk()` calls with `UnifiedPythonVisitor` pattern
- Consolidate framework extractors (SQLAlchemy, Django, Flask, etc.) into single traversal
- Eliminate nested `ast.walk()` calls in Flask/async extractors
- Replace string operations (`.endswith()`) with frozenset lookups
- **Impact**: 25 seconds saved per 1,000 Python files (80x reduction in node visits)

### **⚠️ TIER 1 - HIGH PRIORITY (2-4 Weeks)**

#### **3. Vue In-Memory Compilation** (70% speedup: 9s → 3s per 100 Vue files)
- Refactor Vue SFC compilation in `batch_templates.js` to skip disk I/O
- Pass compiled code directly to TypeScript API (in-memory)
- **Impact**: 6 seconds saved per 100 Vue files

#### **4. Node Module Resolution** (Enables cross-file taint)
- Implement proper TypeScript module resolution in `javascript.py`
- Support `tsconfig.json` path mappings and `node_modules` resolution
- **Impact**: 40-60% more imports resolved (critical for taint accuracy)

### **⚡ TIER 1.5 - JSON BLOB NORMALIZATION (1-2 Weeks)**

**PARALLEL-SAFE**: Can be executed concurrently with TIER 1 (different files, no dependencies)

#### **5. FCE findings_consolidated.details_json Normalization** (75-700ms FCE overhead eliminated)
- **BREAKING**: Normalize findings_consolidated.details_json to junction tables
- Replace 8 json.loads() calls in FCE with JOIN queries
- Create normalized tables: finding_taint_paths, finding_metadata, finding_graph_hotspots, finding_cfg_complexity
- Add indexes for O(1) lookups by finding_id
- **Impact**: 75-700ms saved per FCE run (taint paths are 50-500ms bottleneck with 100-10K paths at 1KB+ each)
- **Critical**: Commit d8370a7 (Oct 23, 2025) explicitly exempted findings_consolidated.details_json as "Intentional findings metadata storage" - this reverses that decision based on measured FCE overhead

#### **6. symbols.parameters Normalization** (Eliminate duplicate JSON parsing)
- Normalize symbols.parameters column to symbol_parameters junction table
- Replace JSON parsing in taint/discovery.py:112 and extractors/javascript.py:1288
- **Impact**: Eliminates duplicate parsing, enables indexed parameter queries
- **Note**: Should already be normalized per commit d8370a7 pattern, but was missed

#### **7. python_routes.dependencies Normalization** (Post-d8370a7 compliance)
- Normalize python_routes.dependencies (added AFTER schema normalization refactor)
- Create python_route_dependencies junction table with AUTOINCREMENT pattern
- **Impact**: Brings Python parity work into compliance with normalization policy

#### **8. Schema Contract Validation Enhancement** (Prevent future violations)
- Add JSON blob detection to schema.py contract validator
- Enforce junction table AUTOINCREMENT pattern
- Validate write path compliance (28 json.dumps() calls audited)
- Fix 3 junction tables missing AUTOINCREMENT (react_component_hooks, react_hook_dependencies, import_style_names)
- **Impact**: Prevents "3rd refactor" by catching violations at schema load time

### **🟡 TIER 2 - MEDIUM PRIORITY (1-2 Days)**

#### **9. Missing Database Indexes**
- Add `idx_function_call_args_argument_index` to schema
- Add `idx_function_call_args_param_name` to schema
- **Impact**: 120ms saved per run (minor but free)

#### **10. GraphQL LIKE Pattern Fixes**
- Fix `graphql/injection.py:103` - Replace `LIKE '%{arg}%'`
- Fix `graphql/input_validation.py:38` - Replace `LIKE '%String%'`
- **Impact**: <500ms (minor, low priority)

---

## Impact

### **Affected Specifications**
- `performance-optimization` (NEW) - Establishes performance contracts for all subsystems

### **Affected Code** (By Tier)

**TIER 0 (Emergency)**:
- `theauditor/taint/discovery.py` - Add spatial indexes (200 lines modified)
- `theauditor/taint/analysis.py` - Replace N+1 patterns (150 lines modified)
- `theauditor/taint/propagation.py` - Fix LIKE patterns (100 lines modified)
- `theauditor/indexer/schemas/generated_cache.py` - Add index builders (300 lines added)
- `theauditor/ast_extractors/python/unified_visitor.py` - NEW (800 lines)
- `theauditor/indexer/extractors/python.py` - Replace orchestration (100 lines modified)

**TIER 1 (High Priority)**:
- `theauditor/extractors/js/batch_templates.js` - Vue compilation (50 lines modified)
- `theauditor/indexer/extractors/javascript.py` - Module resolution (200 lines modified)

**TIER 1.5 (JSON Normalization - PARALLEL-SAFE with TIER 1)**:
- `theauditor/fce.py` - Replace 8 json.loads() with JOINs (lines 60, 78, 127, 168, 207, 265, modified 200 lines)
- `theauditor/indexer/schemas/core_schema.py` - Add 4 normalized tables (finding_taint_paths, finding_metadata, finding_graph_hotspots, finding_cfg_complexity) + symbol_parameters + python_route_dependencies (300 lines added)
- `theauditor/indexer/database/base_database.py` - Remove details_json writes, add junction table writes (50 lines modified)
- `theauditor/taint/discovery.py` - Replace symbols.parameters parsing (line 112, 5 lines modified)
- `theauditor/indexer/extractors/javascript.py` - Replace symbols.parameters parsing (line 1288, 5 lines modified)
- `theauditor/indexer/database/python_database.py` - Normalize python_routes.dependencies (30 lines modified)
- `theauditor/indexer/schema.py` - Add JSON blob validator (100 lines added)
- **Fix 3 junction tables**: react_component_hooks, react_hook_dependencies, import_style_names (add AUTOINCREMENT, 15 lines)

**TIER 2 (Medium Priority)**:
- `theauditor/indexer/schemas/core_schema.py` - Add 2 indexes (2 lines)
- `theauditor/rules/graphql/injection.py` - Fix query (10 lines)
- `theauditor/rules/graphql/input_validation.py` - Fix query (10 lines)

### **Breaking Changes**

**TIER 0**:
1. **Taint Analysis API** - Internal cache structure changes (external API preserved)
   - `SchemaMemoryCache` gains spatial indexes (backward compatible for consumers)
   - Taint findings format unchanged (no migration needed)

2. **Python Extractor Registration** - Framework extractors consolidated
   - Individual `extract_X()` functions → `UnifiedPythonVisitor` class
   - External extractor API (`extract(file_info, content, tree)`) preserved
   - Database schema unchanged (no migration needed)

**TIER 1.5**:
1. **FCE Data Access API** - findings_consolidated.details_json → normalized tables
   - FCE queries change from JSON parsing to JOINs
   - New tables: finding_taint_paths, finding_metadata, finding_graph_hotspots, finding_cfg_complexity
   - **MIGRATION REQUIRED**: Database regenerated fresh (standard for schema changes)
   - External FCE API unchanged (consumers still call `run_fce(root_path)`)

2. **symbols.parameters Schema** - JSON TEXT → symbol_parameters junction table
   - Taint discovery and JS extraction updated to use normalized table
   - **MIGRATION REQUIRED**: Database regenerated fresh
   - External symbol query API unchanged

3. **python_routes.dependencies Schema** - JSON TEXT → python_route_dependencies junction table
   - Python route extraction updated to use normalized table
   - **MIGRATION REQUIRED**: Database regenerated fresh
   - External route query API unchanged

**Migration Path**: All breaking changes require `aud full` to regenerate database (standard procedure). Public APIs remain stable. No user-facing changes required beyond reindexing.

### **Dependencies**
- No new external dependencies
- No changes to Python version requirements (>=3.11)
- **Schema Changes**: TIER 1.5 adds 6 normalized tables + 3 AUTOINCREMENT fixes (database regenerated fresh, standard procedure)

### **Backward Compatibility**
- ✅ Database schema: Preserved (indexes are additive)
- ✅ Rule API: Unchanged
- ✅ CLI commands: Unchanged
- ✅ Output format: Unchanged
- ✅ Configuration: Unchanged

### **Risk Assessment**

**Tier 0 Risks**:
1. **Taint Analysis Refactor** (Medium Risk)
   - Complexity: High (nested loops, complex logic)
   - Mitigation: Extensive fixture testing, compare results before/after
   - Rollback: Revert commits (no schema changes)

2. **Python AST Visitor** (High Risk)
   - Complexity: Very High (70+ extractors to consolidate)
   - Mitigation: Incremental migration (framework by framework), fixture validation
   - Rollback: Revert commits (database unchanged)

**Tier 1 Risks**:
- Vue compilation: Low (isolated change, easy to test)
- Module resolution: Medium (complex logic, but isolated)

**Tier 2 Risks**:
- Negligible (trivial changes, minimal risk)

### **Testing Strategy**

**Tier 0 Testing** (Required Before Merge):
1. **Fixture Validation**: Run all existing fixtures, compare output before/after
2. **Performance Benchmarking**: Measure actual speedups on representative codebases
3. **Regression Testing**: Full test suite must pass
4. **Integration Testing**: Full `aud full` pipeline on 3 codebases (small/medium/large)

**Tier 1 Testing**:
- Vue projects: Test SFC extraction output matches
- Module resolution: Test import graph completeness

**Tier 2 Testing**:
- Schema migration: Verify indexes created
- GraphQL rules: Verify findings unchanged

### **Success Metrics**

**Performance Targets** (Measured on 1,000 Python files + 10K JS/TS):
- ✅ **Indexing**: 90s → 12-18s (75-80% improvement)
- ✅ **Taint Analysis**: 10 min → 20-40s (95% improvement)
- ✅ **Pattern Detection**: Already optimal (95s is acceptable for 113 rules)

**Validation Criteria**:
- All existing tests pass (no regressions)
- Fixture outputs match byte-for-byte (except timing data)
- Memory usage unchanged (within 10%)
- Database schema unchanged (indexes only)

### **Timeline Estimate**

**TIER 0 (Emergency - 1-2 Weeks)**:
- Taint refactor: 3-4 days implementation + 1-2 days testing
- Python AST visitor: 4-6 days implementation + 2-3 days testing

**TIER 1 (High Priority - 2-4 Weeks)**:
- Vue compilation: 4-6 hours
- Module resolution: 1-2 weeks (complex, needs TypeScript integration)

**TIER 1.5 (JSON Normalization - 1-2 Weeks, PARALLEL with TIER 1)**:
- FCE normalization: 2-3 days implementation + 1 day testing
- symbols.parameters normalization: 1 day implementation + 1 day testing
- python_routes.dependencies normalization: 1 day implementation + 1 day testing
- Schema contract validator: 1-2 days implementation + 1 day testing
- Fix 3 junction tables: 2-3 hours

**TIER 2 (Medium Priority - 1-2 Days)**:
- Database indexes: 5 minutes
- GraphQL fixes: 30 minutes

**Total**: 4-7 weeks for all tiers (3-6 weeks if TIER 1 and TIER 1.5 executed in parallel by separate AIs)

### **Parallelization Strategy (Multi-AI Execution)**

This proposal is designed for safe parallel execution by multiple AIs. Below is the dependency matrix:

**PARALLEL-SAFE (No file conflicts, can run concurrently)**:
- ✅ **TIER 0 Task 1 (Taint) ‖ TIER 0 Task 2 (Python AST)** - Different file sets
  - Taint: `theauditor/taint/*.py` + `generated_cache.py`
  - Python AST: `theauditor/ast_extractors/python/*.py` + `indexer/extractors/python.py`

- ✅ **TIER 1 (Vue/Module) ‖ TIER 1.5 (JSON Normalization)** - Zero overlap
  - TIER 1: `extractors/js/*.js` + `indexer/extractors/javascript.py` (module resolution only)
  - TIER 1.5: `fce.py` + `indexer/schemas/core_schema.py` + `indexer/database/*.py` + `taint/discovery.py:112` + `indexer/schema.py`
  - **CONFLICT**: Both touch `indexer/extractors/javascript.py` BUT different sections (module resolution vs parameters parsing)
  - **SAFE**: Coordinate line ranges (TIER 1 = lines 748-768, TIER 1.5 = line 1288)

- ✅ **TIER 2 (All tasks)** - Trivial changes, can be done last by any AI

**SEQUENTIAL DEPENDENCIES** (Must run in order):
- ⚠️ **TIER 0 BEFORE TIER 1/1.5** - Spatial indexes required for performance testing baseline
- ⚠️ **ALL TIERS BEFORE TIER 2** - Indexes are last step (trivial, 5 minutes)

**Recommended Multi-AI Assignment**:
- **AI #1 (Opus)**: TIER 0 Task 1 (Taint refactor) - Complex, needs deep analysis
- **AI #2 (Sonnet)**: TIER 0 Task 2 (Python AST visitor) - Large refactor, fast coding
- **AI #3 (Sonnet)**: TIER 1 (Vue + Module resolution) - Medium complexity
- **AI #4 (Sonnet)**: TIER 1.5 (JSON normalization) - Schema work, database refactor
- **Any AI**: TIER 2 (Cleanup) - Trivial, 1-2 days

**Merge Strategy**:
1. Complete TIER 0 Tasks 1+2, merge independently (no conflicts)
2. Complete TIER 1 + TIER 1.5, coordinate `javascript.py` merge (1 file conflict)
3. Complete TIER 2 last (trivial)

---

## Verification Requirements (Pre-Implementation)

**This proposal follows teamsop.md v4.20 protocols. See `verification.md` for detailed verification phase requirements.**

Before any implementation begins, the assigned coder MUST:
1. ✅ Read `INVESTIGATION_REPORT.md` - Understand root cause analysis
2. ✅ Read `design.md` - Review architectural decisions
3. ✅ Read `verification.md` - Execute verification protocol
4. ✅ Complete verification phase (document findings in `verification.md`)
5. ✅ Get Architect approval on verification before coding

**No code may be written until verification phase is completed and approved.**

---

## Related Changes

**Predecessor**:
- `regex_perf.md` fix (7,900x LIKE wildcard speedup) - Exposed the systemic pattern

**Concurrent Changes** (Potential Conflicts):
- `refactor-taint-schema-driven-architecture` (COMPLETED) - Refactored taint to schema-driven
  - **Impact**: This proposal builds on schema-driven architecture (no conflict)
- `add-framework-extraction-parity` (10/74 tasks)
  - **Impact**: BLOCKS this proposal (framework extractors are being refactored)
  - **Resolution**: Merge or pause parity work, apply this refactor, then resume parity

**Recommendation**: Review `openspec list` and coordinate with Architect before starting implementation.

---

## References

- Investigation Report: `INVESTIGATION_REPORT.md` (verbatim findings from 8 agent deep dive)
- Performance Analysis: `regex_perf.md` (root discovery document)
- Team Protocols: `teamsop.md` v4.20 (verification requirements)
- Architecture: `CLAUDE.md` (zero fallback policy, schema contracts)
- OpenSpec Conventions: `openspec/AGENTS.md`

---

## Approval Gates

**Stage 1: Proposal Review** (Current Stage)
- [ ] Architect reviews proposal
- [ ] Architect approves scope and timeline
- [ ] Conflicts resolved with concurrent changes

**Stage 2: Verification Phase** (Before Implementation)
- [ ] Coder completes verification protocol
- [ ] Coder documents findings in `verification.md`
- [ ] Architect reviews verification results
- [ ] Architect approves implementation plan

**Stage 3: Implementation** (After Verification Approved)
- [ ] Tier 0 implementation begins
- [ ] Tier 0 testing completes
- [ ] Tier 1 implementation begins
- [ ] All tests pass

**Stage 4: Deployment**
- [ ] Performance benchmarks validated
- [ ] Architect approves deployment
- [ ] Change archived via `openspec archive performance-revolution-now --yes`

---

**Status**: 🔴 **PROPOSAL STAGE** - Awaiting Architect approval

**Next Step**: Architect reviews and approves/rejects/modifies this proposal
