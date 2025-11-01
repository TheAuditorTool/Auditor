# Performance Revolution Now - OpenSpec Change Proposal

**Status**: 🔴 **PROPOSAL STAGE** - Awaiting Architect approval

**Created**: 2025-11-02

**Type**: EMERGENCY (P0) - Systemic performance optimization

---

## Quick Start Guide

**If you're reading this 1 week/month/year from now**, here's how to execute this proposal:

### Step 1: Read These Files IN ORDER

1. **START HERE**: `INVESTIGATION_REPORT.md` (30 min read)
   - Verbatim findings from 8-agent deep dive investigation
   - Explains WHY this proposal exists
   - Shows root cause analysis and evidence

2. **NEXT**: `proposal.md` (15 min read)
   - High-level overview of the change
   - Impact assessment, risks, timeline
   - Breaking changes and migration path

3. **THEN**: `design.md` (30 min read)
   - Technical design decisions
   - Architectural patterns and trade-offs
   - Why each approach was chosen

4. **THEN**: `tasks.md` (15 min read)
   - Step-by-step implementation checklist
   - Broken down by tier (Tier 0 = Emergency, Tier 1 = High, Tier 2 = Medium)
   - Each task has verification steps

5. **CRITICAL**: `verification.md` (1-2 hours to EXECUTE)
   - **MANDATORY** pre-implementation verification protocol
   - Verify every hypothesis from investigation report
   - Document discrepancies before coding
   - **NO CODE MAY BE WRITTEN UNTIL THIS IS COMPLETE**

6. **FINALLY**: `specs/performance-optimization/spec.md` (20 min read)
   - Formal requirements and scenarios
   - Success criteria and acceptance tests

**Total Reading Time**: ~2 hours
**Total Verification Time**: ~2 hours (executing verification.md)
**Total Before Coding**: ~4 hours (DO NOT SKIP)

---

## Execution Checklist (For Future You/AI)

- [ ] 1. Read all documents above in order
- [ ] 2. Run `openspec validate performance-revolution-now --strict` (verify proposal valid)
- [ ] 3. Get Architect approval on proposal.md
- [ ] 4. Execute verification.md (fill out all sections)
- [ ] 5. Get Architect approval on verification findings
- [ ] 6. Start Tier 0 implementation (tasks.md section 1-2)
- [ ] 7. Complete Tier 0 testing and validation
- [ ] 8. Start Tier 1 implementation (tasks.md section 3-4)
- [ ] 9. Complete Tier 1 testing and validation
- [ ] 10. Start Tier 2 implementation (tasks.md section 5-6)
- [ ] 11. Complete final documentation (tasks.md section 7)
- [ ] 12. Archive change: `openspec archive performance-revolution-now --yes`

---

## What This Proposal Achieves

**Performance Improvements**:
- ✅ Indexing: 90s → 12-18s (75-80% faster, 5-7.5x speedup)
- ✅ Taint Analysis: 10 min → 20-40s (95% faster, 20-40x speedup)
- ✅ Overall: 16 min → 2-3 min (83-86% faster, 5-8x speedup)

**How**:
1. Single-Pass AST Visitor (eliminates 80 redundant tree walks)
2. Spatial Indexes for Taint (eliminates 60 billion operations)
3. LIKE Wildcard Elimination (eliminates full table scans)
4. CFG Batch Loading (eliminates 10,000 queries)
5. Vue In-Memory Compilation (eliminates disk I/O)
6. Node Module Resolution (fixes cross-file taint)

---

## Critical Warnings

### ⚠️ WARNING 1: Do NOT Skip Verification Phase

`verification.md` is **NOT OPTIONAL**. It is a mandatory gate before coding.

**Why**: The investigation report was created on 2025-11-02. Code may have changed since then. You MUST verify:
- All file paths still valid
- All line numbers still accurate
- All anti-patterns still present (or already fixed)
- Performance measurements still representative

**If you skip this**: You WILL waste days implementing fixes for problems that don't exist.

---

### ⚠️ WARNING 2: Check Concurrent Changes

Before starting, run:
```bash
openspec list
```

Check for conflicts with in-progress changes:
- `add-framework-extraction-parity` (KNOWN CONFLICT - refactors same files)
- Any other changes touching `theauditor/taint/` or `theauditor/ast_extractors/`

**If conflicts exist**: Coordinate with Architect BEFORE starting.

---

### ⚠️ WARNING 3: This is a 3-6 Week Project

**Do NOT** attempt to rush this. Timeline:
- Tier 0 (Emergency): 1-2 weeks
- Tier 1 (High Priority): 2-4 weeks
- Tier 2 (Medium Priority): 1-2 days

**Total**: 3-6 weeks of focused work

**Each tier MUST be tested and validated before proceeding to next tier.**

---

## Key Design Decisions (TL;DR)

1. **Single-Pass Visitor**: Use `ast.NodeVisitor` instead of 80 separate `ast.walk()` calls
   - **Why**: Standard Python pattern, 80x reduction in traversals, easier to maintain

2. **Spatial Indexes**: Add O(1) lookups to `SchemaMemoryCache`
   - **Why**: Eliminates N+1 linear scans (60,000x speedup), standard CS pattern

3. **LIKE Wildcard Elimination**: Pre-filter with indexes, then Python substring search
   - **Why**: 100x fewer rows scanned, same results

4. **CFG Batch Loading**: Load all statements upfront (1 query instead of 10,000)
   - **Why**: Database I/O is slow, batch queries are fast

5. **Vue In-Memory**: Skip disk I/O for .vue compilation
   - **Why**: Disk I/O is 10-30ms overhead, in-memory is 2-5ms

6. **Module Resolution**: Implement TypeScript algorithm for import resolution
   - **Why**: Critical for cross-file taint accuracy (40-60% more imports resolved)

---

## File Structure

```
performance-revolution-now/
├── README.md                          ← You are here
├── proposal.md                        ← High-level overview
├── tasks.md                           ← Implementation checklist
├── design.md                          ← Technical design
├── verification.md                    ← PRE-IMPLEMENTATION VERIFICATION (MANDATORY)
├── INVESTIGATION_REPORT.md            ← Root cause analysis (verbatim from investigation)
└── specs/
    └── performance-optimization/
        └── spec.md                    ← Formal requirements
```

---

## Success Criteria

**Performance Targets** (After All Tiers Complete):
- ✅ Indexing: ≤18 seconds (baseline: 90s)
- ✅ Taint: ≤40 seconds (baseline: 600s)
- ✅ Memory: Within 10% of baseline

**Quality Targets**:
- ✅ All tests pass (no regressions)
- ✅ Fixtures match byte-for-byte (except timing)
- ✅ Database schema unchanged (indexes only)

---

## FAQ

### Q: Can I skip Tier 0 and just do Tier 2?

**A**: ❌ **NO**. Tiers are ordered by impact:
- Tier 0: 95% of performance improvement (540 seconds saved)
- Tier 1: Additional 10 seconds saved
- Tier 2: Negligible (120ms saved)

Tier 0 is the **entire point** of this proposal. Tier 2 is cleanup.

---

### Q: Can I parallelize Tier 0 work (taint + AST)?

**A**: ⚠️ **WITH CAUTION**. The two refactors are independent (different files), so theoretically yes. BUT:
- Both are complex and high-risk
- Both require extensive testing
- Recommend: Do taint first (bigger impact), then AST second

---

### Q: What if I find the investigation report is wrong?

**A**: Execute verification.md, document discrepancies, and:
1. **Minor discrepancies** (line numbers off by 5): Update tasks.md, proceed
2. **Moderate discrepancies** (some anti-patterns already fixed): Re-assess impact, update proposal
3. **Major discrepancies** (root cause wrong): ABORT, re-run investigation, get Architect approval

---

### Q: Can I use a different AI model (Claude Sonnet vs Opus vs Gemini)?

**A**: ✅ **YES**. This proposal is designed for handoff. The verification.md protocol ensures any AI can verify the work.

**Recommendation**:
- Verification Phase: Use Opus (deep analysis, careful verification)
- Implementation: Use Sonnet (fast coding, less overthinking)
- Code Review: Use Gemini (quality control, catch errors)

---

## Contacts

**Architect (Human)**: Final authority on approval, scope, and priorities

**Lead Auditor (Gemini)**: Quality control, reviews verification findings and code changes

**Lead Coder (Opus)**: Implementation responsibility (you, if you're reading this)

---

## Version History

- **2025-11-02**: Initial proposal created (Opus AI)
- **[FUTURE]**: Verification phase completed
- **[FUTURE]**: Tier 0 implementation completed
- **[FUTURE]**: Tier 1 implementation completed
- **[FUTURE]**: Tier 2 implementation completed
- **[FUTURE]**: Change archived

---

## Related Documents

- **Root Discovery**: `regex_perf.md` (7,900x LIKE wildcard fix that started this)
- **Architecture**: `CLAUDE.md` (zero fallback policy, schema contracts)
- **Team Protocols**: `teamsop.md` v4.20 (verification requirements)
- **OpenSpec Guide**: `openspec/AGENTS.md` (proposal conventions)

---

**Last Updated**: 2025-11-02

**Next Action**: Architect reviews and approves/modifies proposal
