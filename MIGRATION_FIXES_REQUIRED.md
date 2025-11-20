# IMMEDIATE FIXES REQUIRED BEFORE MIGRATION

## CRITICAL BLOCKERS - Fix These First!

### 1. File: `theauditor/ast_extractors/python/advanced_extractors.py`

**Function:** `extract_ellipsis_usage`
**Problem:** Variable named `context` on lines 335, 340, 343, 346
**Fix:** Rename `context` to `ellipsis_context`

```python
# Line 335 - BEFORE:
context = "some_value"

# Line 335 - AFTER:
ellipsis_context = "some_value"
```

### 2. File: `theauditor/ast_extractors/python/core_extractors.py`

**Function:** `extract_generators`
**Problem:** Variable named `context` on line 1075
**Fix:** Rename `context` to `gen_context`

```python
# Line 1075 - BEFORE:
context = "generator_context"

# Line 1075 - AFTER:
gen_context = "generator_context"
```

---

## After Fixing These:

1. **Re-run verifier:**
   ```bash
   python verify_filecontext_migration.py ./theauditor/ast_extractors/python/
   ```
   Should show: `[PASS] VERDICT: Safe to proceed with migration`

2. **Then proceed with migration** (see full plan in filecontext_migration_risk_assessment.md)

---

## Quick Reference - Dispatcher Updates Needed

After migration, you'll need to update these files:

1. **`theauditor/indexer/extractors/python.py`** (148 calls to update)
2. **`theauditor/ast_extractors/__init__.py`** (11 calls to update)

Pattern change:
```python
# OLD: extract_python_functions(tree, self)
# NEW: extract_python_functions(context)
```

---

**Total fixes needed before migration: 2 variable renames**
**Estimated time: 5 minutes**