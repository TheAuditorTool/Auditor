# Fix Extraction Data Quality - OpenSpec Proposal

## 🚨 CRITICAL: Pipeline is Currently Broken

**Status**: ~5,800+ database errors, extraction crashes on ORM relationships
**Root Cause**: JavaScript extractors return `{param_name: 'foo'}` but database expects `'foo'`
**Impact**: Taint analysis, FCE, and all code intelligence features compromised

## 📋 For AI Implementation Teams

This proposal is designed for **2-3 AIs working in parallel**. Pick your track and execute independently:

### Quick Start
1. **AI-1 (JavaScript/Node)**: Open `IMPLEMENTATION_GUIDE.md` → Follow Track 1
2. **AI-2 (Python)**: Open `IMPLEMENTATION_GUIDE.md` → Follow Track 2
3. **AI-3 (QA)** or **Both after tracks**: Follow Track 3 for validation

### Files in This Proposal

| File | Purpose | When to Read |
|------|---------|--------------|
| `README.md` | This file - overview and quick start | First |
| `proposal.md` | What and why we're fixing | Context |
| `verification.md` | TEAMSOP Phase 0 - proof of problems | Before starting |
| `design.md` | Technical decisions and rationale | Understanding choices |
| `tasks.md` | Task breakdown for parallel execution | Task assignment |
| **`IMPLEMENTATION_GUIDE.md`** | **EXACT code changes with BEFORE/AFTER** | **During implementation** |
| `specs/extraction/spec.md` | Specification changes | Reference |

## 🎯 The Problems (With Evidence)

### Problem 1: GraphQL Params as Objects
- **Location**: `framework_extractors.js:529-682`
- **Current**: `params: [{param_name: 'user', param_index: 0}]`
- **Should Be**: `params: ['user']`
- **Evidence**: 5,800+ warnings in debug output

### Problem 2: No JavaScript ORM Deduplication
- **Location**: `core_ast_extractors.js:959-1086`
- **Current**: Pushes all relationships, creates duplicates
- **Should Be**: Use Set like Python does
- **Evidence**: Database constraint violations

### Problem 3: Missing Bidirectional Relationships
- **Location**: `sequelize_extractors.js:69-100`
- **Current**: Only User→Post
- **Should Be**: User→Post AND Post→User
- **Evidence**: Incomplete taint flow analysis

### Problem 4: Defensive Type Conversions
- **Location**: `storage.py:427-437`
- **Current**: Converts dicts to strings, hiding bugs
- **Should Be**: Hard fail per ZERO FALLBACK POLICY
- **Evidence**: Violates core architecture principles

## 🔧 Implementation Strategy

### Parallel Execution Model
```
Start → [AI-1: JavaScript] → Track 3: Validation
      ↘ [AI-2: Python]     ↗
```

- **Zero Dependencies**: AI-1 and AI-2 work simultaneously
- **No Conflicts**: Different file sets, no overlap
- **Clear Ownership**: Each track owns specific files

### Track Assignments

**Track 1 (JavaScript) - AI-1**:
- `framework_extractors.js` - Fix GraphQL params
- `core_ast_extractors.js` - Add ORM deduplication
- `sequelize_extractors.js` - Add bidirectional relationships
- Check other JS extractors for similar issues

**Track 2 (Python) - AI-2**:
- `typescript_impl.py` - Fix parameter unwrapping
- `framework_extractors.py` - Verify dedup keys
- `storage.py` - Remove ALL defensive conversions

**Track 3 (Validation) - Both or AI-3**:
- Run test script from `IMPLEMENTATION_GUIDE.md`
- Verify all fixes working
- Full reindex without errors

## ✅ Success Criteria

Run this after implementation:
```bash
# 1. Reindex with debug
THEAUDITOR_DEBUG=1 .venv/Scripts/python.exe -m theauditor.cli index 2>&1 | grep "WARNING.*dict"
# EXPECT: No output

# 2. Check database quality
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute(\"SELECT COUNT(*) FROM function_call_args WHERE param_name LIKE '{%'\")
print(f'Dict params remaining: {c.fetchone()[0]}')  # Should be 0
"

# 3. Run full test suite from IMPLEMENTATION_GUIDE.md
```

## 📚 TEAMSOP Compliance

This proposal follows TEAMSOP v4.20:
- ✅ Phase 0: Verification complete (see `verification.md`)
- ✅ Root cause analysis with evidence
- ✅ BEFORE/AFTER code in `IMPLEMENTATION_GUIDE.md`
- ✅ Parallel execution design
- ✅ No assumptions - all verified with file:line evidence

## 🚀 Start Implementation

1. **READ**: `IMPLEMENTATION_GUIDE.md` for exact code changes
2. **PICK**: Your track (JavaScript or Python)
3. **EXECUTE**: Make the changes shown in BEFORE/AFTER
4. **TEST**: Use provided commands to verify
5. **VALIDATE**: Run Track 3 tests when done

## ⚠️ Critical Notes

- **DO NOT** add more defensive code - fail hard on errors
- **DO NOT** skip deduplication - it's required
- **DO NOT** forget bidirectional relationships
- **DO** follow the exact BEFORE/AFTER code in the guide
- **DO** test each fix before moving to the next

## Questions/Issues

If something is unclear:
1. Check `IMPLEMENTATION_GUIDE.md` - it has exact code
2. Check `verification.md` - it has the evidence
3. Check `design.md` - it has the rationale

Everything needed is in this proposal. Pick it up and run with it.