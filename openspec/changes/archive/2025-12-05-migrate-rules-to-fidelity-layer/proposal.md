# Proposal: Migrate Rules to Fidelity Layer (Phase 2)

## Dependencies

**BLOCKING**: Phase 1 (`add-rules-data-fidelity`) MUST be complete before Wave 1.

Phase 1 creates:
- `theauditor/rules/query.py` - Q class
- `theauditor/rules/fidelity.py` - RuleResult, RuleDB, RuleManifest
- Updated `orchestrator.py` with RuleResult handling
- Updated `base.py` with RuleResult export

**Foundation section in tasks.md (Phase 0) is Phase 1 completion verification, NOT new implementation work.** If Phase 1 is incomplete, complete it first before starting Wave 1.

---

## MANDATORY HANDOFF DOCUMENTS

**Every terminal MUST read these BEFORE touching any rule file:**

| Document | Location | Purpose |
|----------|----------|---------|
| **RULES_HANDOFF.md** | `theauditor/rules/RULES_HANDOFF.md` | Understand fidelity system philosophy, common gotchas |
| **TEMPLATE_FIDELITY_RULE.py** | `theauditor/rules/TEMPLATE_FIDELITY_RULE.py` | THE canonical template - copy structure exactly |

**If you skip these, you WILL write rules incorrectly. No exceptions.**

---

## Why

Phase 1 designed the Q class and fidelity infrastructure. Phase 2 **executes the migration** of all 95 rule files to use the new system. This is a "never look at /rules/ again" comprehensive fix.

**This is NOT just a mechanical migration.** Rules are the billion-dollar valuation of TheAuditor. If rules miss vulnerabilities, have false positives, or don't detect modern attack patterns - the entire tool is worthless.

**Current state:**
- 95 rule files with raw SQL everywhere
- `build_query()` used inconsistently
- Raw `cursor.execute()` with hardcoded SQL
- CTEs hardcoded (e.g., `sql_injection_analyze.py:164-180`)
- No fidelity tracking - silent failures invisible
- CLAUDE.md violations scattered throughout
- **Unknown rule quality** - detection logic never comprehensively reviewed
- **Unknown false positive rates** - no systematic evaluation
- **Unknown coverage gaps** - missing attack patterns not documented

**Goals:**
1. Implement Q class + fidelity infrastructure (Phase 1 completion)
2. Migrate ALL 95 rule files to use RuleDB + Q class
3. Fix ALL CLAUDE.md violations found during migration
4. Add fidelity manifests to enable silent failure detection
5. Achieve zero raw SQL in rules (except Q.raw() escape hatch with logging)
6. **REVIEW detection logic quality for each rule**
7. **IDENTIFY false positive patterns and mitigate them**
8. **DOCUMENT missing attack patterns (TODO comments if not fixing inline)**
9. **VERIFY CWE mappings are correct and complete**
10. **ENSURE structure matches TEMPLATE_FIDELITY_RULE.py exactly**

## What Changes

### Foundation (Single Terminal - Must Complete First)
- Implement `theauditor/rules/query.py` - Q class
- Implement `theauditor/rules/fidelity.py` - RuleResult, RuleDB, RuleManifest
- Update `theauditor/rules/orchestrator.py` - RuleResult handling
- Update `theauditor/rules/base.py` - Re-export RuleResult

### Migration (10 Parallel Terminals × 2 Waves)
- Wave 1: 50 files (5 per terminal)
- Wave 2: 45 files (4-5 per terminal)
- Each terminal:
  1. Read all assigned files FULLY
  2. Identify issues (CLAUDE.md violations, bad patterns, bugs)
  3. Convert raw SQL to Q class
  4. Add RuleDB usage with manifest tracking
  5. Return RuleResult instead of bare list
  6. Run validation

## Impact

- **Affected code**: 95 rule files + 4 infrastructure files
- **Risk**: HIGH - touching security detection logic
- **Mitigation**: Parallel work with explicit file assignments prevents conflicts

## Success Criteria

### Mechanical Migration (Must Pass)
1. Zero raw `cursor.execute()` calls with hardcoded SQL (only Q class or Q.raw())
2. All rules return `RuleResult` with manifest
3. `aud full --offline` runs clean with no crashes
4. All 95 files pass import validation
5. CLAUDE.md violations eliminated
6. All rules match TEMPLATE_FIDELITY_RULE.py structure

### Quality Review (Must Document)
7. Each rule has documented detection logic evaluation (in TODO or inline comments)
8. False positive patterns identified per rule (at minimum: logging, testing, comments)
9. Missing attack patterns documented as TODO comments where applicable
10. CWE mappings verified against actual detection logic
11. Severity ratings reviewed for appropriateness

### Quality Gate Per Rule
Before any rule is marked complete, terminal MUST confirm:
- [ ] Detection logic reviewed - does it catch real vulnerabilities?
- [ ] False positives considered - will it flag safe code?
- [ ] Coverage gaps documented - what patterns should it catch but doesn't?
- [ ] CWE-ID verified - matches what rule actually detects
- [ ] Structure verified - matches TEMPLATE_FIDELITY_RULE.py
