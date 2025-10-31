# Node.js/TypeScript Parity Worklog - VERIFIED TRUTH (2025-10-30)

## ⚠️ CRITICAL: TRUST NO DOCUMENTATION - VERIFY EVERYTHING ⚠️

**This document was rewritten 2025-10-30 after verification audit revealed:**
- React extraction has **83.4% false positive rate** (captures backend controllers as "components")
- React hooks capture `users.map` and service methods (NOT actual React hooks)
- core_ast_extractors.js exceeded 2000-line growth threshold (now **2172 lines**)
- node_support.md claimed "Vue extractor pending" but code exists since January (git c7c7d98)

**PRIME DIRECTIVE: ALWAYS verify database state with direct sqlite queries before accepting ANY claim in ANY document.**

---

## Comprehensive Investigation Complete - Session 8 Summary

**Verified Against:** C:\Users\santa\Desktop\plant\.pf\repo_index.db (modified 2025-10-30 16:06)

**P0 BLOCKERS IDENTIFIED:**
1. **Monolith:** core_ast_extractors.js = 2172 lines (exceeded 2000 threshold by 172 lines)
2. **Data Quality:** React components = 83.4% false positives (694 backend controllers captured)
3. **Data Quality:** React hooks = captures users.map, userService.createUser (NOT React hooks)

**WORKING:**
- Core extraction: ✅ 34,608 symbols, 16,891 function calls, 185 API endpoints
- Framework detection: ✅ Express/React/Vite/Zod from package.json
- Validation: ✅ Zod detection (3 rows)
- Vue extraction: ✅ Code exists (git c7c7d98) but 0 data (no fixtures)

**ROOT CAUSES:**
- Monolith: File grew 544 lines since header comment written (1628 → 2172)
- React false positives: Python layer (javascript.py:442-493) lacks path filtering that JS layer has
- Hooks false positives: javascript.py:498 uses `startswith('use')` without validation

---

## Roadmap (Fix P0 First)

### **Phase 1: Data Quality (URGENT - 2.5 hours)**
1. Add path filtering to javascript.py:442-493 (exclude backend/)
2. Fix hooks validation (replace startswith with proper pattern)
3. Investigate duplicate components
4. Re-index plant + verify counts

### **Phase 2: Monolith Refactor (HIGH - 4.5 hours)**
1. Split core_ast_extractors.js into:
   - core\imports_exports.js (~500 lines)
   - core\functions_classes.js (~800 lines)
   - core\data_flow.js (~800 lines)
2. Update js_helper_templates.py concatenation
3. Verify no regressions

### **Phase 3: Vue Testing + Validation Expansion (MEDIUM - 6 hours)**
1. Create Vue fixture (tests\fixtures\javascript\vue_project\)
2. Test Vue extraction (verify vue_* tables populated)
3. Add Joi/Yup/class-validator/express-validator/AJV detection

---

## Database Evidence (Plant Project - Express + React)

```sql
-- Core (WORKING)
symbols: 34,608
function_call_args: 16,891
api_endpoints: 185

-- React (BUGGY)
react_components: 834 (only ~140 real, 694 backend controllers)
react_hooks: 1,494 (captures users.map, service methods)

-- Vue (CODE EXISTS, NO DATA)
vue_components: 0 (no Vue files in plant)

-- Validation (WORKING)
validation_framework_usage: 3 (Zod parseAsync detected)
```

**False Positive Evidence:**
```sql
SELECT name, file FROM react_components WHERE file LIKE '%backend%' LIMIT 3;
-- AccountController.list | backend\src\controllers\account.controller.ts
-- AreaController.create | backend\src\controllers\area.controller.ts
-- UserController.getUser | backend\src\controllers\user.controller.ts
```

---

## Architecture (Line Counts Verified)

```
theauditor\ast_extractors\javascript\
├── core_ast_extractors.js       2172 lines ⚠️ MONOLITH (14 extractors)
├── batch_templates.js           1017 lines
├── cfg_extractor.js              554 lines
├── framework_extractors.js       473 lines (HAS path filtering)
└── security_extractors.js        433 lines
Total: 4,649 lines

Integration:
└── theauditor\indexer\extractors\javascript.py  1297 lines (LACKS path filtering)
```

**The Problem:**
- JavaScript layer (framework_extractors.js:49-92) HAS backend/ filtering
- Python layer (javascript.py:442-493) does NOT have filtering
- Database has backend controllers → Python code is executing (fallback path)

---

## Git History (Recent Work)

```
c7c7d98 feat(js, indexer): Implement deterministic Vue.js SFC extraction (January 2025)
76b00b9 feat(taint): implement validation framework sanitizer detection
a33d015 feat(indexer): implement cross-file parameter name resolution
4a1d74c feat(indexer): achieve 98.8% call coverage
4f441a0 refactor(ast)!: extract JavaScript templates to separate .js files
```

**Observation:** Vue implemented months ago but never tested (no fixtures)

---

## Parity vs Python

| Feature | Node | Python | Winner |
|---------|------|--------|--------|
| Code volume | 4649 lines | 1584 lines | Node (+3x) |
| Monolith risk | 2172 lines (HIGH) | 1584 lines (MED) | Python |
| Data quality | 83.4% false pos | Clean | Python |
| Test coverage | No fixtures | 441 lines | Python |
| ORM extraction | Minimal | 14 models, 48 fields | Python |
| Validation | 3 rows (Zod) | 9 validators | Python |

**Verdict:** Node has more features but worse quality + monolith problem

---

## Verification Commands

```bash
# Check monolith status
wc -l theauditor\ast_extractors\javascript\core_ast_extractors.js
# Expected: 2172 lines (BREACHED 2000 threshold)

# Verify plant database
cd C:\Users\santa\Desktop\TheAuditor && .venv\Scripts\python.exe -c "
import sqlite3
db = 'C:\\Users\\santa\\Desktop\\plant\\.pf\\repo_index.db'
conn = sqlite3.connect(db)
c = conn.cursor()

print('Core extraction:', c.execute('SELECT COUNT(*) FROM symbols').fetchone()[0], 'symbols')
print('React (total):', c.execute('SELECT COUNT(*) FROM react_components').fetchone()[0])
print('React (frontend):', c.execute(\"SELECT COUNT(*) FROM react_components WHERE file LIKE '%frontend%'\").fetchone()[0])
print('React (backend - SHOULD BE 0):', c.execute(\"SELECT COUNT(*) FROM react_components WHERE file LIKE '%backend%'\").fetchone()[0])

conn.close()
"
```

---

## Next Session: Fix P0 Blockers

**HIGH PRIORITY (30 min each):**
1. Add path filtering to javascript.py:442-493
2. Fix hooks validation (use REACT_HOOK_NAMES set + custom pattern)
3. Re-index plant + verify

**AFTER DATA FIXES:**
4. Refactor monolith (4-6 hours)
5. Create Vue fixtures (2-3 hours)
6. Expand validation coverage (3-4 hours)

---

**Status:** Session 8 complete. Comprehensive audit done. P0 blockers documented. Roadmap ready.
**Last Updated:** 2025-10-30 18:00 UTC
**Branch:** pythonparity (clean, 2 commits ahead)
**Next Priority:** Fix React false positives BEFORE monolith refactor
