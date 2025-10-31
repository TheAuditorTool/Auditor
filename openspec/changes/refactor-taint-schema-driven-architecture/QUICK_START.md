# QUICK START: Taint Schema-Driven Refactor

**For**: Future AI implementing this refactor
**Read This First**: You are here
**Time to Read**: 5 minutes
**Status**: Ready for implementation after architect approval

---

## 🚀 START HERE

### What You're Implementing

**1-Sentence Summary**: Convert taint analysis from manual 8-layer architecture to schema-driven 5-layer architecture that auto-generates loaders/queries from schema, reducing code 77% and enabling sub-10 minute performance.

**Why**: Fix 60% problem (8-layer change hell blocks velocity) → enables solving 40% problem (multihop cross-path analysis).

**Architect Mandate**: AST extractors (`javascript_impl.py`, `python_impl.py`) are **SACRED - DO NOT TOUCH** or architect will kill you.

---

## 📋 Document Reading Order (MANDATORY)

Read in THIS order. Do NOT skip ahead.

### 1. ✅ THIS FILE (you are here)
- 5-minute orientation
- Verification checklist before starting

### 2. 📄 `proposal.md` (10-15 min read)
- **WHY** this refactor (60/40 problem split)
- **WHAT** changes (8 layers → 5 layers)
- **SUCCESS** metrics (sub-10 min, AST untouched)
- **RISKS** and rollback plan

### 3. 🔍 `verification.md` (15-20 min read)
- **PROOF** all claims verified against source code
- Current state inventory (8,691 lines, 14 files)
- Hypothesis → Evidence → Result format (teamsop.md)
- **READ THIS** to avoid re-investigating

### 4. 🏗️ `design.md` (20-30 min read)
- **HOW** to implement schema code generation
- Concrete algorithms with code examples
- Before/After comparisons
- Decision rationales with alternatives considered

### 5. ✅ `tasks.md` (30-40 min read)
- **STEP-BY-STEP** implementation (200+ granular tasks)
- 6 phases with validation gates
- Profiling commands at every phase
- Exactly what to code, in what order

### 6. 📐 `specs/taint-analysis/spec.md` (10 min read)
- Detailed spec for taint analysis module
- Expected behavior after refactor

---

## ⚠️ CRITICAL PRE-FLIGHT CHECKS

**STOP. Before writing ANY code, verify these:**

### ✅ Checklist 1: Environment Setup

```bash
# 1. Confirm you're in the right directory
cd C:/Users/santa/Desktop/TheAuditor
pwd  # Should show TheAuditor

# 2. Confirm branch
git branch  # Should be on 'pythonparity' or new feature branch

# 3. Confirm Python environment
.venv/Scripts/python.exe --version  # Should be Python 3.11+

# 4. Confirm database exists
ls .pf/repo_index.db  # Should exist (91MB)

# 5. Confirm current taint works
.venv/Scripts/python.exe -c "from theauditor.taint.core import trace_taint; print('OK')"
# Should print "OK"
```

### ✅ Checklist 2: Understanding Boundaries

**SACRED** (READ-ONLY - verify you will NOT touch these):
- [ ] `theauditor/ast_extractors/javascript_impl.py` - ❌ DO NOT MODIFY
- [ ] `theauditor/ast_extractors/python_impl.py` - ❌ DO NOT MODIFY
- [ ] `theauditor/indexer/extractors/*.py` - ❌ DO NOT MODIFY
- [ ] `theauditor/indexer/database/*.py` - ❌ DO NOT MODIFY
- [ ] `theauditor/indexer/schema.py` - ✅ CAN MODIFY (add codegen only)

**EXPENDABLE** (delete if better architecture exists):
- [ ] `theauditor/taint/*.py` (8,691 lines) - ✅ FAIR GAME
- [ ] Can delete 9 files, modify 3, create 2 (see proposal.md)

**CAPABILITIES** (preserve functionality, implementation can change):
- [ ] Parameter resolution (6,511 resolved calls)
- [ ] CFG analysis (27,369 blocks)
- [ ] Framework detection (validation, ORM, GraphQL)
- [ ] Cross-file taint tracking

### ✅ Checklist 3: Verification Artifacts

**Confirm you have read and understand**:
- [ ] verification.md Hypothesis 1: Manual loaders exist (CONFIRMED)
- [ ] verification.md Hypothesis 2: 8-layer change cascade (CONFIRMED)
- [ ] verification.md Hypothesis 3: Hardcoded patterns duplicate DB (CONFIRMED)
- [ ] verification.md Current state: 8,691 lines, 14 files, 70 tables
- [ ] verification.md Performance baseline: 15 min (TheAuditor), 10-12 min (75K LOC)

**If you can't confirm all above**: STOP. Read verification.md first.

---

## 🎯 Implementation Phases (High-Level)

You will implement in **6 phases over 6 weeks**. Each phase has:
- Detailed tasks in `tasks.md`
- Validation gate (MUST pass before next phase)
- Rollback point (if validation fails)

### Phase 0: Verification (Pre-Implementation)
**Status**: ✅ COMPLETE (verification.md exists)
**Gate**: Architect + Auditor approval

### Phase 1: Schema Auto-Generation (Week 1)
**Goal**: Add code generation WITHOUT touching taint
**Create**: `indexer/schemas/codegen.py`
**Gate**: Generated code compiles, type-checks, <100ms generation time

### Phase 2: Replace Memory Cache (Week 2)
**Goal**: Replace manual loaders with auto-generated
**Delete**: `taint/memory_cache.py`, `taint/python_memory_cache.py`
**Gate**: Taint results 100% identical, performance ≥baseline

### Phase 3: Integrate Validation Framework (Week 3)
**Goal**: Complete Layer 3 integration (unfinished work)
**Modify**: Extractor to populate `validation_framework_usage`
**Gate**: Table populated, validated inputs not flagged

### Phase 4: Unified CFG Analysis (Week 4)
**Goal**: Merge 3 CFG files → 1 file
**Create**: `taint/analysis.py` (~1,000 lines)
**Delete**: `interprocedural.py`, `interprocedural_cfg.py`, `cfg_integration.py`
**Gate**: All baseline paths detected, <10 min analysis

### Phase 5: Database-Driven Discovery (Week 5)
**Goal**: Replace hardcoded patterns with DB queries
**Delete**: `taint/sources.py`, `taint/database.py`
**Gate**: Same sources/sinks discovered, <10% false positives

### Phase 6: Final Optimization (Week 6)
**Goal**: Profile, optimize, benchmark, document
**Gate**: All projects <10 min, memory <500MB, docs complete

---

## 🚨 STOP CONDITIONS (Immediate Rollback)

**If ANY of these occur during implementation:**

1. ❌ **AST extractor modified** → STOP. Revert. Architect will be angry.
2. ❌ **Performance regression** → STOP. Profile bottleneck. Fix before continuing.
3. ❌ **Any baseline path not detected** → STOP. Debug. All paths must be found.
4. ❌ **Memory >500MB** → STOP. Optimize or implement lazy loading.
5. ❌ **Tests fail** → STOP. Fix tests before continuing to next phase.

---

## 📊 Success Metrics (Final Validation)

**After Phase 6, ALL of these must be true:**

Performance:
- [ ] TheAuditor analysis <10 minutes (currently 15 min)
- [ ] 75K LOC project <10 minutes (currently 10-12 min)
- [ ] Memory usage <500MB (currently 122MB)

Coverage:
- [ ] 100% of baseline taint paths detected
- [ ] Zero false negatives introduced
- [ ] False positive rate <10%

Code Quality:
- [ ] mypy --strict passes on all new code
- [ ] ruff check passes
- [ ] Test coverage ≥95%

Sacred Files:
- [ ] javascript_impl.py unchanged (verify with git diff)
- [ ] python_impl.py unchanged (verify with git diff)
- [ ] No modifications to AST extraction logic

Velocity:
- [ ] Add table to schema → 0 taint code changes needed
- [ ] Taint logic changes → 0 reindex needed (iteration <1 min)

---

## 🔧 Profiling Commands (Run At Every Gate)

```bash
# Profile schema generation (Phase 1 gate)
python -m cProfile -o schema_gen.prof -c "
from theauditor.indexer.schema import SchemaCodeGenerator
SchemaCodeGenerator.generate_all()
"
# Verify: <100ms

# Profile cache loading (Phase 2 gate)
python -m cProfile -o cache_load.prof -c "
from theauditor.taint import SchemaMemoryCache
cache = SchemaMemoryCache('.pf/repo_index.db')
"
# Verify: ≤current time, ≤500MB

# Profile full analysis (Phase 4, 6 gates)
time aud taint-analyze --max-depth 5 --use-cfg
# Verify: <10 minutes

# Memory profiling
python -m memory_profiler theauditor/taint/core.py
# Verify: <500MB peak
```

---

## 🆘 If You Get Stuck

### Common Issues & Solutions

**Issue**: "I don't understand the schema codegen algorithm"
- **Solution**: Read `design.md` Section 2 (Schema Auto-Generation Algorithm)
- Look for concrete code examples with Before/After comparisons

**Issue**: "I'm not sure if this code should be deleted"
- **Solution**: Check `proposal.md` Section "What's Sacred vs Expendable"
- If it's in `taint/*.py` and not registry.py, it's expendable

**Issue**: "Performance test failing"
- **Solution**: Run profiling commands, identify bottleneck
- Check `design.md` for optimization strategies
- DO NOT proceed to next phase until fixed

**Issue**: "Test coverage decreasing"
- **Solution**: Add tests for new code paths
- Check `verification.md` for baseline test count
- Target: ≥95% coverage

**Issue**: "Unsure about a design decision"
- **Solution**: Check `design.md` "Alternatives Considered" tables
- Each decision has rationale + rejected alternatives

---

## 📞 Communication Protocol (Teamsop.md)

**After EVERY phase**:

1. Create completion report using Template C-4.20
2. Include:
   - Verification findings
   - Root cause analysis
   - Implementation details
   - Performance metrics
   - Post-implementation audit
3. Submit to Architect + Lead Auditor
4. Await approval before next phase

**Template location**: `teamsop.md` Section "Part 3: Communication Template v4.20"

---

## ✅ Final Pre-Flight

**Before you start Phase 1, confirm:**

- [ ] I have read ALL 6 documents in order
- [ ] I understand what's sacred (AST extractors) vs expendable (taint/*.py)
- [ ] I have verified current state matches verification.md
- [ ] I understand 60/40 problem split (velocity → enables multihop)
- [ ] I know success criteria (sub-10 min, AST untouched, 100% coverage)
- [ ] I have profiling commands ready for each gate
- [ ] I will follow teamsop.md Prime Directive (verify before acting)
- [ ] I will create completion reports using Template C-4.20

**If ANY checkbox unchecked**: Go back and read the relevant document.

**If ALL checkboxes checked**: ✅ Ready to begin Phase 1

---

## 🚀 Next Action

**Read in order**:
1. ✅ This file (you are here)
2. ➡️ **NEXT**: `proposal.md` (understand WHY and WHAT)
3. Then: `verification.md` (see the PROOF)
4. Then: `design.md` (learn HOW to implement)
5. Then: `tasks.md` (get exact steps)
6. Finally: Begin Phase 1 implementation

**Time to full understanding**: ~2 hours of reading
**Time to implementation**: 6 weeks (1 phase per week)

---

**Good luck. You have everything you need. Read carefully. Verify religiously. Code confidently.**

**Remember**: AST extractors are sacred. Architect is watching. Performance matters. Coverage is non-negotiable.

**Any questions? Check the relevant document first. 99% of answers are already written.**

---

**Created**: 2025-11-01
**Status**: Ready for implementation
**Confidence**: Ironclad (all docs synced, all claims verified)
