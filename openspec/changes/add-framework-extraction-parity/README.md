# Framework Extraction Parity - IRONCLAD PROPOSAL

**Created**: 2025-11-01
**Status**: Ready for Implementation
**Validation**: ✅ `openspec validate add-framework-extraction-parity --strict` PASSED

---

## TL;DR

TheAuditor extracts data from Sequelize, BullMQ, and Angular but throws it away. Python has tables for Marshmallow, WTForms, Celery, and Pytest but the extraction functions don't exist.

**This proposal provides 100% copy-paste ready code to fix both issues.**

---

## What's Included

### 1. **IMPLEMENTATION_COOKBOOK.md** ⭐ **START HERE** ⭐
- 1,400+ lines of copy-paste ready code
- Complete worked example (Sequelize - reference implementation)
- Templates for all other frameworks
- Code markers instead of line numbers (resilient to changes)
- Zero ambiguity - no design decisions needed
- **Any AI or human can execute in 6-8 hours**

### 2. **proposal.md**
- Executive summary (why/what/impact)
- Verification evidence (every claim backed by source code)
- Success criteria
- Relationship to other changes

### 3. **verification.md**
- TeamSOP v4.20 compliant investigation
- Hypothesis testing (verified against actual code)
- Root cause analysis
- Evidence trail (file:line references)
- Zero assumptions made

### 4. **tasks.md**
- 107 detailed tasks
- 4-phase breakdown
- Estimated effort (9 days → 6-8 hours with cookbook)
- Checklist format

### 5. **design.md**
- 7 major design decisions with rationale
- 5 risk analyses with mitigation
- 4-phase migration plan
- Open questions resolved
- Success metrics

### 6. **specs/framework-extraction/spec.md**
- 17 requirements
- 40+ scenarios (WHEN/THEN format)
- Database schema requirements
- Integration requirements
- Testing requirements

---

## How to Use This Proposal

### For Review (30 minutes)
1. Read `proposal.md` - high-level overview
2. Skim `verification.md` - see the evidence
3. Check `design.md` - understand decisions
4. Approve or request changes

### For Implementation (6-8 hours)
1. **Read `IMPLEMENTATION_COOKBOOK.md` Section 1** (Sequelize reference) - 15 min
2. **Copy-paste Sequelize code** from cookbook - 45 min
3. **Copy-paste BullMQ code** (follow pattern) - 30 min
4. **Copy-paste Angular code** (5 tables) - 1 hour
5. **Update schema assertion** - 2 min
6. **Implement 10 Python functions** (copy from cookbook) - 2 hours
7. **Add Python storage** (copy from cookbook) - 30 min
8. **Create test fixtures** - 1.5 hours
9. **Run verification script** - 5 min
10. **Fix any issues** - 30 min

**Total**: 6-8 hours of focused copy-paste work

---

## Key Features

### ✅ Zero Ambiguity
- Every function has complete skeleton
- Every table has exact schema code
- Every integration point has code marker (not line numbers)
- Every storage operation has SQL template

### ✅ Evidence-Based
- Every claim verified through source code
- Database inspected to confirm gaps
- Tool execution confirms silent failures
- No assumptions made

### ✅ Future-Proof
- Code markers resist drift (unique strings, not line numbers)
- Templates for all frameworks (copy pattern)
- Comprehensive test fixtures
- Verification scripts included

### ✅ Complete
- Covers both Node.js (9 tables) and Python (10 functions)
- Addresses root cause (disconnected extractors/schema)
- Includes migration plan
- Documents all design decisions

---

## What Problem Does This Solve?

### Before (Current State)
```bash
$ aud index
[Indexer] Indexed 765 files, 50019 symbols...
# Sequelize models extracted but DISCARDED (no database tables)
# BullMQ queues extracted but DISCARDED (no database tables)
# Angular components extracted but DISCARDED (no database tables)
# Marshmallow schemas NOT extracted (function doesn't exist)
# Celery tasks NOT extracted (function doesn't exist)

$ python -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM sequelize_models')"
sqlite3.OperationalError: no such table: sequelize_models
```

### After (With This Implementation)
```bash
$ aud index
[Indexer] Indexed 765 files, 50019 symbols...
[Indexer] Sequelize models: 15, associations: 23
[Indexer] BullMQ queues: 3, workers: 3
[Indexer] Angular components: 42, services: 15, DI injections: 78
[Indexer] Marshmallow schemas: 8, fields: 45
[Indexer] Celery tasks: 12, task calls: 56
[Indexer] Pytest fixtures: 23, parametrize: 15

$ python -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM sequelize_models'); print(cursor.fetchone()[0])"
15
```

### Impact on Downstream Consumers
```bash
# BEFORE
$ aud blueprint
ORM Patterns: None detected

# AFTER
$ aud blueprint
ORM Patterns:
  - Sequelize: 15 models with 23 relationships
  - User.hasMany(Post), Order.belongsTo(User), etc.

# BEFORE
$ aud taint-analyze
# Misses taint flows through job queues

# AFTER
$ aud taint-analyze
Taint Flow:
  Source: req.body.email (user input)
  Propagation: emailQueue.add('sendEmail', { to: email })
  Sink: nodemailer.sendMail() in worker
  Severity: MEDIUM
```

---

## Verification Evidence

**Investigation Date**: 2025-11-01
**Method**: Source code audit + database inspection + tool execution

### Node.js Gaps (VERIFIED)
- ✅ Extractors EXIST: `sequelize_extractors.js` (99 lines), `bullmq_extractors.js` (82 lines), `angular_extractors.js` (213 lines)
- ✅ Integration EXISTS: Called from `batch_templates.js:416-418`
- ✅ Data RETURNED: `batch_templates.js:484-490`
- ❌ Tables MISSING: `node_schema.py` has NO Sequelize/BullMQ/Angular tables
- ❌ Indexer MISSING: `javascript.py` doesn't handle these data types
- ❌ **RESULT**: Data extracted then DISCARDED

### Python Gaps (VERIFIED)
- ✅ Tables EXIST: `python_schema.py` defines all 10 tables
- ✅ Calls EXIST: `python.py:243-285` calls all 10 functions
- ❌ Functions MISSING: `python_impl.py` has NO implementation
- ❌ **RESULT**: Functions called but fail SILENTLY

**Source**: See `verification.md` for complete evidence trail with file:line references

---

## Success Criteria

### Quantitative
- [x] 9 new Node.js tables defined
- [x] 10 new Python extraction functions templated
- [x] 100% copy-paste ready code provided
- [ ] Database size increase < 15%
- [ ] Indexing time increase < 10%
- [ ] 0 regressions in existing tests

### Qualitative
- [ ] `aud blueprint` shows framework patterns on production projects
- [ ] `aud taint-analyze` tracks taint through ORM/job queues/DI
- [ ] `aud planning` supports framework migrations
- [ ] Any AI can execute without design decisions

---

## Files in This Proposal

```
openspec/changes/add-framework-extraction-parity/
├── README.md (this file)
├── proposal.md (why/what/impact)
├── verification.md (evidence + investigation)
├── tasks.md (107-task checklist)
├── design.md (technical decisions)
├── IMPLEMENTATION_COOKBOOK.md ⭐ (copy-paste ready code)
└── specs/
    └── framework-extraction/
        └── spec.md (requirements + scenarios)
```

**Total**: 7 files, ~10,000 lines of documentation and code

---

## Quick Start

### For Architect (Review)
```bash
# 1. Read high-level overview
cat openspec/changes/add-framework-extraction-parity/proposal.md

# 2. Check evidence
cat openspec/changes/add-framework-extraction-parity/verification.md

# 3. Validate proposal
openspec validate add-framework-extraction-parity --strict

# 4. Approve or request changes
```

### For Implementer (Coding)
```bash
# 1. Read the cookbook
cat openspec/changes/add-framework-extraction-parity/IMPLEMENTATION_COOKBOOK.md

# 2. Start with Section 1 (Sequelize reference)
# Copy-paste schema code → node_schema.py
# Copy-paste integration code → javascript.py
# Copy-paste storage code → indexer/__init__.py

# 3. Follow pattern for other frameworks
# BullMQ (Section 2), Angular (Section 3)

# 4. Implement Python functions (Section 5)
# 10 complete function skeletons provided

# 5. Run verification script (Section 9)
bash verification.sh

# 6. Done!
```

---

## Questions?

**Q**: Is this really 100% copy-paste ready?
**A**: Yes. Every function has complete skeleton. Every table has exact schema. Every integration point has code marker.

**Q**: What if line numbers drift?
**A**: We use code markers (unique strings) instead of line numbers. Example: "Find `'cdk_constructs': []` and add after it"

**Q**: Do I need to make design decisions?
**A**: No. All decisions documented in `design.md`. Code is ready to paste.

**Q**: How long will implementation take?
**A**: 6-8 hours of focused copy-paste work (was 9 days before cookbook).

**Q**: What if I get stuck?
**A**: Section 8 has common pitfalls & solutions. Section 9 has verification script.

---

## Next Steps

1. **Review**: Read proposal.md + verification.md (30 min)
2. **Approve**: Confirm approach is sound
3. **Implement**: Follow IMPLEMENTATION_COOKBOOK.md (6-8 hours)
4. **Test**: Run verification script
5. **Deploy**: Create PR, merge to main

---

**Status**: ✅ Ready for implementation
**Confidence**: HIGH (all findings verified)
**Execution**: Copy-paste from cookbook
**Time**: 6-8 hours (any AI or human)
