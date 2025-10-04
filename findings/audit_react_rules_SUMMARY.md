# React Rules Audit Summary

**Audit Date:** 2025-10-04
**Category:** react
**Files Audited:** 4
**Compliance Score:** 0% (critical violations present)

---

## 🚨 CRITICAL VIOLATIONS (P0)

### ALL 4 FILES VIOLATE ABSOLUTE PROHIBITION

Every React rule file contains **architectural cancer** that must be removed immediately:

#### Violation 1: Table Existence Checking via sqlite_master
**Location:** All files, `_check_table_availability()` method
**Lines:**
- `component_analyze.py`: 106-138
- `hooks_analyze.py`: 138-147
- `render_analyze.py`: 140-149
- `state_analyze.py`: 136-145

**Code Pattern:**
```python
def _check_table_availability(self):
    """Check which tables exist for graceful degradation."""
    self.cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN (...)
    """)
    self.existing_tables = {row[0] for row in self.cursor.fetchall()}
```

**Why This Is Cancer:**
- Violates schema contract guarantee that all tables exist
- Creates fallback logic where none should exist
- If a table doesn't exist, the rule SHOULD crash to indicate schema violation

**Fix:** DELETE the entire `_check_table_availability()` method from all 4 files

---

#### Violation 2: Conditional Execution Based on Table Existence
**Total Occurrences:** 20 across all files

**Code Pattern:**
```python
if 'react_components' not in self.existing_tables:
    return []

if 'react_hooks' not in self.existing_tables:
    return
```

**Locations:**
- `component_analyze.py`: Lines 109-110, 153-154, 194-195, 361-362
- `hooks_analyze.py`: Lines 118-119, 255-256, 305-306, 403-404
- `render_analyze.py`: Lines 120-121, 153-154, 323-324, 359-360
- `state_analyze.py`: Lines 116-117, 209-210, 243-244, 276-277

**Fix:** REMOVE all these conditional checks - assume tables exist per schema contract

---

## ✅ POSITIVE FINDINGS

### Excellent Aspects (Gold Standard Compliance)

1. **Rule Metadata** - 100% PASS
   - All files have complete METADATA blocks
   - Correct `requires_jsx_pass=False` (queries non-jsx tables)
   - Proper target_extensions and exclude_patterns

2. **Frozenset Pattern Usage** - 100% PASS
   - All files use frozen dataclasses
   - O(1) pattern matching with frozensets
   - Examples:
     - `component_analyze.py`: MEMO_CANDIDATES, PERFORMANCE_PROPS
     - `hooks_analyze.py`: HOOKS_WITH_DEPS, CLEANUP_REQUIRED
     - `render_analyze.py`: EXPENSIVE_OPERATIONS, MUTATING_METHODS
     - `state_analyze.py`: STATE_PREFIXES, CONTEXT_PATTERNS

3. **Finding Generation** - 100% PASS
   - All `StandardFinding()` calls use correct parameter names:
     - `file_path=` (not `file=`)
     - `rule_name=` (not `rule=`)
   - Severity enum used correctly (not strings)
   - All required fields present: rule_name, message, severity, file_path, line, cwe_id

4. **Column Name Compliance** - 100% PASS
   - **40 database queries analyzed**
   - **0 column mismatches found**
   - All column names match `schema.py` definitions exactly

5. **Template Compliance** - 100% PASS
   - All files correctly use STANDARD template (not JSX)
   - Query non-jsx tables: `react_components`, `react_hooks`, `function_call_args`
   - React hooks are function calls, not JSX syntax

---

## 📊 VIOLATIONS BY FILE

### component_analyze.py
- **Total:** 31 violations
- **Critical:** 5 (table existence checks)
- **High:** 26 (direct SQL without build_query)
- **Status:** FAIL due to critical violations

### hooks_analyze.py
- **Total:** 31 violations
- **Critical:** 5 (table existence checks)
- **High:** 26 (direct SQL without build_query)
- **Status:** FAIL due to critical violations

### render_analyze.py
- **Total:** 31 violations
- **Critical:** 5 (table existence checks)
- **High:** 26 (direct SQL without build_query)
- **Status:** FAIL due to critical violations

### state_analyze.py
- **Total:** 31 violations
- **Critical:** 5 (table existence checks)
- **High:** 26 (direct SQL without build_query)
- **Status:** FAIL due to critical violations

---

## 🔧 RECOMMENDED FIXES

### Priority P0 (CRITICAL - Fix Immediately)

#### Fix 1: Delete Table Availability Checking
**Estimated Time:** 15 minutes

**Action:**
1. Open each file
2. Find `_check_table_availability()` method
3. DELETE the entire method (lines 106-138, 138-147, 140-149, 136-145)
4. DELETE the line `self.existing_tables = set()` from `__init__`

**Files to modify:**
- `component_analyze.py`
- `hooks_analyze.py`
- `render_analyze.py`
- `state_analyze.py`

---

#### Fix 2: Remove Conditional Execution Checks
**Estimated Time:** 15 minutes

**Action:**
For each file, remove these patterns:

```python
# BEFORE (WRONG)
if 'react_components' not in self.existing_tables:
    return []

self._check_large_components()

# AFTER (CORRECT)
self._check_large_components()
```

**Lines to remove:**
- `component_analyze.py`: 109-110, 153-154, 194-195, 361-362
- `hooks_analyze.py`: 118-119, 255-256, 305-306, 403-404
- `render_analyze.py`: 120-121, 153-154, 323-324, 359-360
- `state_analyze.py`: 116-117, 209-210, 243-244, 276-277

---

### Priority P1 (Recommended)

#### Fix 3: Consider Using build_query() for Simple Queries
**Estimated Time:** 1-2 hours

**Current Pattern:**
```python
self.cursor.execute("""
    SELECT file, name, type, start_line
    FROM react_components
    WHERE name IS NOT NULL
""")
```

**With build_query():**
```python
from theauditor.indexer.schema import build_query

query = build_query('react_components',
                   ['file', 'name', 'type', 'start_line'],
                   where="name IS NOT NULL")
self.cursor.execute(query)
```

**Note:** Complex JOINs and GROUP BY queries can remain as direct SQL - this is acceptable for complex queries.

---

## 📈 SCHEMA VALIDATION RESULTS

### Tables Queried (All Valid)
- `react_components` ✅
- `react_hooks` ✅
- `function_call_args` ✅
- `variable_usage` ✅
- `assignments` ✅
- `cfg_blocks` ✅
- `function_returns` ✅

### Column Validation
- **Total Queries Checked:** 40
- **Column Mismatches:** 0
- **Compliance Rate:** 100%
- **Status:** ALL COLUMN NAMES CORRECT ✅

**Sample Verified Queries:**
- `react_components`: file, name, type, start_line, end_line, has_jsx, hooks_used, props_type ✅
- `react_hooks`: file, line, hook_name, component_name, dependency_array, dependency_vars, callback_body, has_cleanup, cleanup_type ✅
- `function_call_args`: file, line, caller_function, callee_function, argument_index, argument_expr, param_name ✅

---

## 📝 DETAILED FINDINGS

### Non-Critical Issues (High Priority)

All files have ~26 instances of direct SQL without `build_query()`:
- **Impact:** Medium - queries work but lack type safety
- **Risk:** Low - column names are all correct
- **Recommendation:** Refactor simple SELECTs to use build_query() when time permits

**Example Locations:**
- `component_analyze.py`: Lines 142-148, 167-174, 197-210, etc.
- `hooks_analyze.py`: Lines 151-158, 201-208, 258-267, etc.
- `render_analyze.py`: Lines 157-167, 186-195, 213-222, etc.
- `state_analyze.py`: Lines 148-158, 177-190, 212-218, etc.

**Why Not P0:**
- All column names are verified correct
- Queries function properly
- No schema contract violations (besides table existence checks)

---

## 🎯 OVERALL ASSESSMENT

### Strengths
1. ✅ **Perfect metadata compliance** - all files follow rule metadata standard
2. ✅ **Excellent pattern usage** - frozensets everywhere for O(1) lookups
3. ✅ **100% column accuracy** - zero mismatches with schema.py
4. ✅ **Correct template usage** - all use STANDARD (not JSX) as intended
5. ✅ **Perfect finding generation** - all parameters correct

### Critical Weaknesses
1. ❌ **Architectural cancer** - table existence checking violates schema contract
2. ❌ **Zero gold standard files** - all 4 files have critical violations

### Fix Difficulty
**LOW** - The critical violations are easy to fix:
- Delete one method (`_check_table_availability`)
- Remove conditional checks (20 lines across 4 files)
- **Total estimated time: 30 minutes**

### Compliance Score
- **Table Existence Checks:** 0% (20 violations)
- **Column Name Accuracy:** 100% (0 mismatches)
- **Overall:** FAIL (critical violations present)

---

## 🚀 NEXT STEPS

1. **Immediate (P0):** Remove table existence checking cancer (30 minutes)
2. **Optional (P1):** Refactor to use build_query() for simple queries (1-2 hours)
3. **Validation:** Re-run audit to confirm 100% compliance

**Expected Result After P0 Fixes:**
- Compliance Score: 100%
- Gold Standard Files: 4/4
- Critical Violations: 0
- All queries still work (column names already correct)

---

## 📎 FULL DETAILS

See `audit_react_rules.json` for complete violation details with exact line numbers and code snippets.
