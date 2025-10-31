# CFG/Graph/Taint Integration Enhancement

**Change ID**: `verify-cfg-graph-taint-integration`
**Status**: Ready for Implementation (Back Burner)
**Last Updated**: 2025-10-16

---

## 📁 File Guide

### ⭐ Implementation Files (Start Here)
- **START.md** - **READ THIS FIRST** - Entry point for implementation
- **IMPLEMENTATION_GUIDE.md** - Complete step-by-step guide with code examples
  - Pre-flight checklist
  - 5 phases with 20+ steps
  - Verification tests for each step
  - Troubleshooting section
  - Final checklist

### 📋 Planning Files (Reference)
- **proposal.md** - Investigation findings and rationale (context)
- **tasks.md** - Task breakdown and sequencing
- **verification.md** - Testing strategy and acceptance criteria
- **specs/taint-analysis/spec.md** - OpenSpec requirement deltas

---

## 🎯 Quick Summary

**Problem**: CFG data extracted and cached but NOT used by taint analysis → 10-100x performance loss

**Solution**: Add optional cache parameter to 4 CFG functions + thread through consumers

**Impact**:
- CFG queries: 10-100x faster
- Full pipeline: 2-20x faster
- Cache hit rate: >90%

**Effort**: 8-12 days (5 phases)

**Status**: Investigation complete, ready to implement

---

## 🚀 Quick Start

```bash
# 1. Open START.md
cat START.md

# 2. Follow IMPLEMENTATION_GUIDE.md
cat IMPLEMENTATION_GUIDE.md

# 3. Begin Phase 2, Step 2.1
# (Guide has complete code examples)
```

---

## 📊 Progress Tracking

- [x] Phase 1: Investigation (COMPLETE)
- [ ] Phase 2: CFG Cache Integration (P0) - 3-5 days
- [ ] Phase 3: Hot Path Tables (P1) - 2-3 days
- [ ] Phase 4: Testing & Validation - 2-3 days
- [ ] Phase 5: Documentation - 1 day

---

## ✅ Validation Status

```bash
# OpenSpec validation
cd /c/Users/santa/Desktop/TheAuditor
openspec validate verify-cfg-graph-taint-integration --strict
# ✅ Change 'verify-cfg-graph-taint-integration' is valid
```

---

## 🔍 Key Findings

### Finding 1: CFG Cache Integration Gap (P0)
- **Problem**: memory_cache.py loads CFG tables with 8 indexes BUT taint/database.py query functions don't accept cache parameter
- **Impact**: ~100-200MB CFG data loaded but unused, queries hit disk
- **Solution**: Add optional cache parameter to 4 functions

### Finding 2: CFG Extraction Verified Complete ✅
- **Python**: ast_extractors/python_impl.py::extract_python_cfg()
- **JS/TS**: ast_extractors/typescript_impl.py::extract_typescript_cfg()
- **Full chain traced and verified**

### Finding 3: Hot Path Tables Missing (P1)
- **Tables**: frameworks, object_literals, framework_safe_sinks
- **Impact**: Hot path disk queries instead of cache lookups
- **Solution**: Add to memory_cache.py loading

### Clarifications
- ✅ graphs.db separation intentional (serves many purposes)
- ✅ Memory management dynamic via utils/memory.py (60% of RAM)
- ✅ All changes backward compatible (optional parameters)
- ✅ memory_cache.py is THE ONLY cache (no alternatives)

---

## 📈 Expected Results

| Metric | Target | Verification |
|--------|--------|-------------|
| CFG query speedup | 10-100x | Benchmark |
| Pipeline speedup (small) | 2-5x | End-to-end test |
| Pipeline speedup (medium) | 5-10x | End-to-end test |
| Pipeline speedup (large) | 10-20x | End-to-end test |
| Cache hit rate | >90% | Integration test |
| Regression rate | 0% | Full test suite |
| Breaking changes | 0 | Backward compat guaranteed |

---

## 🛠️ Files Modified

1. `theauditor/taint/database.py` - 4 CFG query functions
2. `theauditor/taint/cfg_integration.py` - PathAnalyzer
3. `theauditor/taint/interprocedural_cfg.py` - InterProceduralCFGAnalyzer
4. `theauditor/taint/propagation.py` - Cache threading
5. `theauditor/taint/memory_cache.py` - Hot path tables
6. `theauditor/taint/core.py` - Consumer updates

**Total**: 6 files, ~500 lines of changes

---

## 🎓 Learning Resources

**Before implementing, understand**:
- How memory_cache.py works (read file)
- How CFG extraction chain works (see proposal.md Finding 2)
- Database-first architecture (see CLAUDE.md)
- Schema contract system (indexer/schema.py)

**During implementation, reference**:
- IMPLEMENTATION_GUIDE.md for exact steps
- verification.md for test strategies
- proposal.md for context when stuck

---

## 🔗 Related Changes

- Depends on: None (standalone)
- Blocks: None
- Related to: Memory cache system, CFG extraction, Taint analysis

---

## 📞 Contact

**Questions?** Ask Architect (Boss) - see teamsop.md for team structure

**Bugs?** Document in openspec/changes/verify-cfg-graph-taint-integration/BUGS.md (create if needed)

---

**Status**: Ironclad. Pick up anytime. Follow START.md → IMPLEMENTATION_GUIDE.md.
