# FileContext Migration Risk Assessment Report

**Document Type:** Risk Assessment / Pre-Migration Analysis
**Date:** 2025-11-20
**Status:** CRITICAL BLOCKERS FOUND - DO NOT PROCEED
**Affected Version:** TheAuditor 1.3.0-RC1
**Analysis Tool:** verify_filecontext_migration.py

---

## Executive Summary

**VERDICT: DO NOT RUN MIGRATION** - Critical blockers detected that will cause immediate runtime failures.

### Key Findings:
- **159 extractor functions** across 27 files analyzed
- **2 context variable collisions** (CRITICAL BLOCKER)
- **48 complex ast.walk patterns** (WARNING - may not transform correctly)
- **159 caller locations** need manual updates (REQUIRED)
- **0 parser_self dependencies** (GOOD - no blocker here)

---

## 1. CRITICAL BLOCKERS (Must Fix Before Migration)

### 1.1 Context Variable Collisions

These extractors already use a local variable named `context`, which will collide with the new FileContext parameter:

#### File: `theauditor\ast_extractors\python\advanced_extractors.py`
- **Function:** `extract_ellipsis_usage`
- **Lines with `context =`:** 335, 340, 343, 346
- **Risk:** Variable name collision will cause immediate NameError or attribute errors
- **Fix Required:** Rename existing `context` variables to something else (e.g., `node_context`, `ellipsis_context`)

#### File: `theauditor\ast_extractors\python\core_extractors.py`
- **Function:** `extract_generators`
- **Lines with `context =`:** 1075
- **Risk:** Variable shadowing will break functionality
- **Fix Required:** Rename local `context` variable

### 1.2 Resolution Steps for Blockers

```bash
# Step 1: Fix advanced_extractors.py
# Open the file and rename 'context' variables on lines 335, 340, 343, 346
# Suggested rename: context -> ellipsis_context

# Step 2: Fix core_extractors.py
# Open the file and rename 'context' variable on line 1075
# Suggested rename: context -> gen_context

# Step 3: Verify fixes
python verify_filecontext_migration.py ./theauditor/ast_extractors/python/
# Should now show no context collision blockers
```

---

## 2. Complex AST Walk Patterns (Warnings)

### 2.1 Pattern Distribution

The script found **48 complex patterns** that may not transform correctly:

| Pattern Type | Count | Risk Level |
|-------------|-------|------------|
| Nested ast.walk loops | 14 | HIGH - Performance killer |
| Non-isinstance first condition | 34 | MEDIUM - Won't get optimization |
| Logic before isinstance | 1 | LOW - Still works, no optimization |

### 2.2 High-Risk Nested Walks

These files contain nested `ast.walk()` loops which are O(N²) complexity:

1. **behavioral_extractors.py**
   - `extract_property_patterns` (line 403)
   - `extract_dynamic_attributes` (line 548)

2. **core_extractors.py**
   - `extract_generators` (lines 1024, 1036)

3. **data_flow_extractors.py**
   - `extract_parameter_return_flow` (line 376)
   - `extract_closure_captures` (line 553)
   - `extract_nonlocal_access` (line 641)

4. **flask_extractors.py**
   - `extract_flask_app_factories` (line 126)

5. **performance_extractors.py**
   - `extract_memoization_patterns` (line 384)

6. **protocol_extractors.py**
   - `extract_iterator_protocol` (line 133)

7. **state_mutation_extractors.py**
   - `extract_global_mutations` (line 408)
   - `extract_augmented_assignments` (line 731)

**Action Required:** These need manual review after migration to ensure correctness.

### 2.3 Non-isinstance Patterns

34 extractors start their loops with conditions other than `isinstance`. Examples:

- **django_web_extractors.py**: Multiple functions checking for specific Django patterns
- **flask_extractors.py**: 8 functions with complex Flask-specific checks
- **security_extractors.py**: 8 functions checking for security patterns
- **testing_extractors.py**: Test discovery patterns
- **validation_extractors.py**: 6 functions for various validation frameworks

**Impact:** These won't benefit from NodeIndex optimization but will still work via `context.walk_tree()` fallback.

---

## 3. Caller/Dispatcher Updates Required

### 3.1 Primary Dispatcher Locations

Two main files contain the dispatcher logic that calls extractors:

#### File: `theauditor\ast_extractors\__init__.py`
- **11 calls** using pattern `(tree, self)`
- Lines: 104, 122, 140, 158, 176, and 6 more
- **Critical:** This appears to be the mixin/router pattern

#### File: `theauditor\indexer\extractors\python.py`
- **148 calls** using pattern `(tree, ...)`
- Lines: 481, 514, 522, 529, 534, and 143 more
- **Critical:** This is the main Python extractor orchestrator

### 3.2 Manual Update Required

After running the migration script, you MUST immediately update these dispatcher files:

```python
# BEFORE (current pattern in python.py):
results['functions'] = extract_python_functions(tree, self)
results['classes'] = extract_python_classes(tree, self)

# AFTER (required pattern):
from theauditor.ast_extractors.utils.context import build_file_context

# Build context once at the top of extract method
context = build_file_context(tree.get("tree"), content, str(file_info['path']))

# Pass context to all extractors
results['functions'] = extract_python_functions(context)
results['classes'] = extract_python_classes(context)
```

---

## 4. Good News: No parser_self Dependencies

**Zero extractors use `parser_self`** - This is excellent news as it means:
- No need to preserve parser_self in signatures
- No need to add parser_self data to FileContext
- Clean migration path for function signatures

---

## 5. Recommended Migration Plan

### Phase 1: Fix Blockers (30 minutes)
1. Fix context variable collisions in 2 files
2. Run verifier again to confirm blockers cleared

### Phase 2: Prepare Dispatcher Updates (1 hour)
1. Create a backup of `python.py` and `__init__.py`
2. Write the FileContext initialization code
3. Prepare the updated dispatcher logic (don't apply yet)

### Phase 3: Test Migration (2 hours)
1. Create infrastructure: `python ast_walk_to_filecontext.py --create-modules`
2. Test on single file: `fundamental_extractors.py`
3. Manually test the transformed file with a test script
4. Verify database output unchanged

### Phase 4: Execute Migration (1 hour)
1. Run migration on all files
2. IMMEDIATELY apply dispatcher updates
3. Run test suite
4. Verify database row counts

### Phase 5: Manual Verification (2 hours)
1. Review nested ast.walk patterns
2. Test complex extractors individually
3. Performance benchmarks

---

## 6. Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Context variable collision | **100%** (found) | CRITICAL - Runtime failure | Fix before migration |
| Dispatcher not updated | HIGH | CRITICAL - Nothing works | Update immediately after |
| Nested walks not optimized | MEDIUM | MEDIUM - Still slow | Manual optimization later |
| Non-isinstance patterns missed | HIGH | LOW - Fallback works | Accept for now |
| Database schema mismatch | LOW | HIGH - Data loss | Verify row counts |

---

## 7. Pre-Migration Checklist

**MUST DO BEFORE RUNNING MIGRATION:**

- [ ] Fix context variable in `advanced_extractors.py` (lines 335, 340, 343, 346)
- [ ] Fix context variable in `core_extractors.py` (line 1075)
- [ ] Run verifier again - must show "[PASS] VERDICT"
- [ ] Backup entire `ast_extractors/python/` directory
- [ ] Backup `indexer/extractors/python.py`
- [ ] Prepare dispatcher update code
- [ ] Have database row count baseline

**MUST DO IMMEDIATELY AFTER MIGRATION:**

- [ ] Update `theauditor/indexer/extractors/python.py` dispatcher
- [ ] Update `theauditor/ast_extractors/__init__.py` if needed
- [ ] Run basic smoke test
- [ ] Run full test suite
- [ ] Compare database row counts

---

## 8. Commands for Migration

```bash
# After fixing blockers:

# 1. Verify blockers fixed
python verify_filecontext_migration.py ./theauditor/ast_extractors/python/

# 2. Create infrastructure
python ast_walk_to_filecontext.py --create-modules --target-dir ./theauditor/ast_extractors/python/

# 3. Dry run
python ast_walk_to_filecontext.py --dry-run --target-dir ./theauditor/ast_extractors/python/

# 4. Test single file
python ast_walk_to_filecontext.py --target-dir ./theauditor/ast_extractors/python/fundamental_extractors.py

# 5. Run migration (after all checks pass)
python ast_walk_to_filecontext.py --target-dir ./theauditor/ast_extractors/python/

# 6. IMMEDIATELY update dispatcher files!
```

---

## 9. Conclusion

**Current Status:** NOT READY for migration due to 2 critical context variable collisions.

**Estimated Time to Migration Ready:** 30 minutes (fix 2 files)

**Total Migration Time:** 4-6 hours including testing and verification

**Risk Level After Fixes:** MEDIUM - Manageable with proper procedure

---

**Document Prepared By:** AI Coder following Lead Auditor risk analysis
**Next Action:** Fix the 2 context variable collisions, then re-run verifier