# 🚀 START HERE

**If you're picking up this change (in a week, month, or by a different AI):**

## Read This File First

You found the right place. This is the entry point.

---

## What This Change Does

**Problem**: CFG data is extracted and loaded into cache BUT taint analysis doesn't use it. Result: 10-100x performance loss.

**Solution**: Connect cache to CFG query functions. Add hot path tables to cache.

**Impact**: 10-100x faster CFG queries, 2-20x faster full pipeline.

---

## Files You Need (in order)

1. **START.md** (this file) - You are here ✅
2. **IMPLEMENTATION_GUIDE.md** - Step-by-step instructions with code examples
3. **proposal.md** - Context and findings (read if you need background)
4. **tasks.md** - Task breakdown (reference only)
5. **verification.md** - Testing strategy (reference only)
6. **specs/taint-analysis/spec.md** - Requirements (reference only)

---

## Quick Start (5 minutes)

1. **Open IMPLEMENTATION_GUIDE.md**
2. **Run Pre-Flight Checklist** (verify baseline works)
3. **Start Phase 2, Step 2.1** (first function modification)
4. **Follow mechanically** - Don't skip, don't improvise
5. **Verify after each step** - Use provided test commands

---

## Time Estimate

- **Phase 2** (CFG Cache Integration): 3-5 days → **START HERE**
- **Phase 3** (Hot Path Tables): 2-3 days
- **Phase 4** (Testing): 2-3 days
- **Phase 5** (Documentation): 1 day

**Total**: 8-12 days

---

## Current Status

- ✅ Investigation complete
- ✅ Proposal validated
- ✅ Implementation guide written
- ⏸️  **Implementation NOT started** (back burner)

---

## Success Criteria

**Phase 2 Complete When**:
- All 4 CFG query functions accept optional cache parameter
- Benchmark shows ≥10x speedup
- All existing tests still pass

**Full Change Complete When**:
- All phases done
- Performance targets met
- Zero regressions
- Documentation updated

---

## Emergency Contacts

**If stuck**:
1. Read "Troubleshooting" section in IMPLEMENTATION_GUIDE.md
2. Check git history for context: `git log --oneline --grep="cfg.*cache"`
3. Ask Architect (Boss) for clarification

---

## One-Liner Summary

*"Add optional cache parameter to 4 CFG functions + thread through consumers = 10-100x speedup"*

---

**Next Action**: Open IMPLEMENTATION_GUIDE.md and start Pre-Flight Checklist.
