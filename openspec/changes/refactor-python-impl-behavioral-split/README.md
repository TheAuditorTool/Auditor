# Python Implementation Behavioral Split - Complete Package

**Change ID**: refactor-python-impl-behavioral-split
**Status**: READY FOR IMPLEMENTATION
**Created**: 2025-11-01
**Architect**: Santa (TheAuditor maintainer)
**Lead Coder**: Claude (Opus AI)

---

## Quick Start

**READ THESE FILES IN ORDER**:

1. **proposal.md** - Why we're doing this, what changes, impact assessment
2. **FUNCTION_INVENTORY.md** - Complete 43-function classification table (IRONCLAD)
3. **LINE_BY_LINE_SPLIT_MAP.md** - Exact line ranges for copy operations (IRONCLAD)
4. **IMPLEMENTATION_GUIDE.md** - Step-by-step execution commands (IRONCLAD)
5. **design.md** - Technical decisions, trade-offs, risks
6. **tasks.md** - 67-task checklist for implementation
7. **verification.md** - Pre-implementation verification (SOP v4.20 compliant)

---

## What Makes This "Ironclad"

### 1. Complete Function Inventory
- All 43 functions classified with line numbers
- Clear STRUCTURAL vs BEHAVIORAL rules
- Evidence cited for each classification
- Split ratio calculated: 49.5% / 50.5% (target: 50/50 ± 5%)

### 2. Line-by-Line Split Map
- Exact source line ranges (e.g., "Lines 44-282 → python_impl_structure.py")
- No guesswork - mechanical copy operations
- Gap analysis (blank lines accounted for)
- Verification commands included

### 3. Step-by-Step Implementation Guide
- Phase 1: Create python_impl_structure.py (6 steps)
- Phase 2: Refactor python_impl.py (5 steps)
- Phase 3: Integration Testing (4 steps)
- Phase 4: Final Verification (4 steps)
- Each step has exact commands (Read/Write/Edit tool calls)
- Rollback procedure included

### 4. Windows Path Compliance
- All file paths use backslashes: `C:\Users\santa\Desktop\TheAuditor\`
- No Unix forward slashes in actual implementation commands
- Read/Write/Edit tools used (NOT bash cp/cat/heredoc)

### 5. TypeScript Pattern Reference
- Explicitly matches proven TypeScript split architecture
- Side-by-side comparisons throughout
- Same docstring patterns
- Same dependency structure (behavioral → structural)

---

## File Manifest

### OpenSpec Standard Files
- `proposal.md` - OpenSpec proposal (Why, What, Impact)
- `design.md` - Technical design document
- `tasks.md` - 67-task implementation checklist
- `verification.md` - Pre-implementation verification results
- `specs/ast-extraction/spec.md` - Specification deltas

### Ironclad Implementation Files (NEW)
- **`FUNCTION_INVENTORY.md`** - Complete function classification
- **`LINE_BY_LINE_SPLIT_MAP.md`** - Exact line-by-line copy instructions
- **`IMPLEMENTATION_GUIDE.md`** - Step-by-step execution guide
- **`README.md`** - This file (navigation guide)

### Generated During Implementation
- `IMPLEMENTATION_RESULTS.md` - Will be created post-implementation

---

## Target Files

### CREATED (New File)
- `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl_structure.py`
  - **Size**: ~1150 lines (49.5%)
  - **Functions**: 36 structural + 3 constants
  - **Role**: Stateless structural extraction layer

### MODIFIED (Refactored)
- `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py`
  - **Size**: ~1174 lines (50.5%) - DOWN from 2324
  - **Functions**: 7 behavioral + re-exports from structural
  - **Role**: Stateful behavioral analysis layer

### UNAFFECTED (Active Production Code)
- `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python\` package
  - Import alias points here: `from . import python as python_impl`
  - This refactor does NOT touch the active python/ package

---

## Verification Checklist

Before starting implementation, verify:
- [x] Read teamsop.md SOP v4.20
- [x] Read entire python_impl.py (2324 lines)
- [x] Read TypeScript reference (typescript_impl.py + typescript_impl_structure.py)
- [x] Complete function inventory created
- [x] Line-by-line split map created
- [x] Implementation guide created
- [x] OpenSpec validation passed (`openspec validate --strict`)
- [x] Architect approval received

After implementation, verify:
- [ ] Syntax check (py_compile both files)
- [ ] Import chain test (structural, behavioral, re-export)
- [ ] Dependency direction (one-way: behavioral → structural)
- [ ] Split ratio (48-52% for each file)
- [ ] No duplicate functions
- [ ] Docstring patterns match TypeScript
- [ ] No circular imports
- [ ] Backward compatibility maintained
- [ ] Post-implementation audit (re-read both files)

---

## Implementation Time Estimate

**Experienced AI/Human**: 2-3 hours
- Phase 1 (Create structure): 60 minutes
- Phase 2 (Refactor behavioral): 45 minutes
- Phase 3 (Integration test): 20 minutes
- Phase 4 (Final verification): 15 minutes

**Fresh AI (no context)**: 4-6 hours
- Must read all documentation first: 60 minutes
- Implementation: 3-4 hours
- Testing & debugging: 1 hour

**Key Advantage**: With this ironclad package, even a fresh AI can execute mechanically without understanding the broader context.

---

## Rollback Plan

If anything goes wrong:
```bash
cd C:\Users\santa\Desktop\TheAuditor
git checkout theauditor/ast_extractors/python_impl.py
rm theauditor/ast_extractors/python_impl_structure.py
```

Zero impact on production (python/ package unaffected).

---

## Success Criteria (10 Requirements)

1. ✅ python_impl_structure.py created (~1150 lines, 48-52%)
2. ✅ python_impl.py refactored (~1174 lines, 48-52%)
3. ✅ Total lines: ~2324 (within ±50 lines)
4. ✅ No syntax errors (py_compile passes)
5. ✅ Import chain works (structural, behavioral, re-export)
6. ✅ One-way dependency (behavioral → structural, never reverse)
7. ✅ No duplicate function definitions
8. ✅ Docstrings match TypeScript pattern
9. ✅ No circular imports
10. ✅ Backward compatibility maintained

**ALL 10 must pass for completion.**

---

## Questions?

1. **Why split if python_impl.py is deprecated?**
   - Matches TypeScript architecture pattern
   - Easier to understand for future maintainers
   - Prepares for eventual Phase 2.2 removal
   - Demonstrates architectural consistency

2. **Why not modify python/ package instead?**
   - python/ package is active production code
   - Separate proposal needed for that (out of scope)
   - This refactor is low-risk (deprecated file only)

3. **What if I mess up?**
   - Rollback procedure is simple (git checkout)
   - Zero impact on production (python/ unaffected)
   - Complete documentation for re-attempt

4. **Can I start now or next week?**
   - **YES** - All documentation is complete and self-contained
   - No context needed beyond these files
   - Fresh AI can execute mechanically

---

## Contact

**Architect**: Santa (TheAuditor maintainer)
**Questions**: See CLAUDE.md for project guidelines
**Issues**: Create issue in GitHub repo (if available)

---

## Final Word

This package represents **95% ironclad** implementation documentation:
- Complete function inventory ✓
- Exact line-by-line split map ✓
- Step-by-step mechanical guide ✓
- Windows path compliance ✓
- TypeScript pattern matching ✓
- Verification procedures ✓
- Rollback plan ✓

**Missing 5%**: Actual execution (your job!)

**Estimated success rate**: 95%+ if following guide exactly

**Go time**: Whenever you're ready. This package is complete and self-sufficient.
