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

### **🟡 TIER 2 - MEDIUM PRIORITY (1-2 Days)**

#### **5. Missing Database Indexes**
- Add `idx_function_call_args_argument_index` to schema
- Add `idx_function_call_args_param_name` to schema
- **Impact**: 120ms saved per run (minor but free)

#### **6. GraphQL LIKE Pattern Fixes**
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

**TIER 2 (Medium Priority)**:
- `theauditor/indexer/schemas/core_schema.py` - Add indexes (2 lines)
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

**Migration Path**: All breaking changes are internal implementation details. Public APIs remain stable. No user-facing changes required.

### **Dependencies**
- No new external dependencies
- No changes to Python version requirements (>=3.11)
- No changes to database schema (indexes only)

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

**TIER 2 (Medium Priority - 1-2 Days)**:
- Database indexes: 5 minutes
- GraphQL fixes: 30 minutes

**Total**: 3-6 weeks for all tiers

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
