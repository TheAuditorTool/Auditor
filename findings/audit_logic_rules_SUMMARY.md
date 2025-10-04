# Logic Rules Audit - Executive Summary

**Audit Date:** 2025-10-04
**Category:** `theauditor/rules/logic/`
**Files Audited:** 1/1 (100%)
**Overall Compliance Score:** 35/100

---

## 📊 Audit Results

### Files Audited
1. ✅ `general_logic_analyze.py` - **REQUIRES IMMEDIATE REFACTOR**

### Compliance Breakdown
| Check | Score | Status |
|-------|-------|--------|
| **Metadata** | 100/100 | ✅ PASS |
| **Database Contracts** | 0/100 | ❌ FAIL |
| **Finding Generation** | 100/100 | ✅ PASS |
| **Frozensets (O(1) Patterns)** | 100/100 | ✅ PASS |

---

## 🚨 Critical Violations Found: 5

### VIOLATION 1: Table Existence Checking (Lines 185-196)
**Severity:** CRITICAL
**Code:**
```python
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name IN (
        'assignments', 'function_call_args', 'symbols',
        'cfg_blocks', 'files'
    )
""")
existing_tables = {row[0] for row in cursor.fetchall()}
```

**Why This Is Wrong:**
CLAUDE.md explicitly states: **"NO FALLBACKS. NO REGEX. NO EXCEPTIONS."**
The schema contract system (`theauditor/indexer/schema.py`) **guarantees** table existence.
Any table existence check is **architectural cancer**.

**Required Fix:**
Remove the sqlite_master query entirely. Assume all contracted tables exist. If a table doesn't exist, the rule **SHOULD crash** to indicate a schema contract violation.

---

### VIOLATION 2: Conditional Execution Based on Table Existence (Lines 195-202)
**Severity:** CRITICAL
**Code:**
```python
if 'assignments' not in existing_tables and 'function_call_args' not in existing_tables:
    return findings  # Can't analyze without basic data

has_assignments = 'assignments' in existing_tables
has_function_calls = 'function_call_args' in existing_tables
has_cfg_blocks = 'cfg_blocks' in existing_tables
has_symbols = 'symbols' in existing_tables
```

**Why This Is Wrong:**
This is the **fallback logic pattern** explicitly forbidden in CLAUDE.md. It creates unreliable analysis that silently skips checks instead of failing fast when the schema is broken.

**Required Fix:**
Remove all `has_*` flags. Execute queries directly. Trust the schema contract.

---

### VIOLATION 3: Multiple Conditional Wrappers Throughout File
**Severity:** CRITICAL
**Lines Affected:** 206, 236, 265, 365, 392, 402, 463, and more

**Code Pattern:**
```python
if has_assignments:
    # Query assignments table

if has_function_calls:
    # Query function_call_args table
```

**Why This Is Wrong:**
Every query is wrapped in an `if has_*` conditional. This defeats the purpose of schema contracts.

**Required Fix:**
Remove ALL conditional wrappers. Query tables directly. Let SQLite errors surface if schema is broken.

---

### VIOLATION 4: Zero Usage of build_query()
**Severity:** CRITICAL
**Lines Affected:** Entire file (no usage found)

**Why This Is Wrong:**
The schema contract system provides `build_query()` for type-safe, validated queries. This rule uses **100% hardcoded SQL strings**, bypassing schema validation entirely.

**Required Fix:**
Import and use `build_query()` for all SELECT queries:
```python
from theauditor.indexer.schema import build_query

# Instead of:
cursor.execute("SELECT file, line, target_var FROM assignments WHERE ...")

# Use:
query = build_query('assignments', ['file', 'line', 'target_var'])
cursor.execute(query + " WHERE ...")
```

---

### VIOLATION 5: F-string SQL Injection Pattern (Lines 208-220)
**Severity:** CRITICAL
**Code:**
```python
money_conditions = ' OR '.join([f"a.target_var LIKE '%{term}%'" for term in MONEY_TERMS])

cursor.execute(f"""
    SELECT DISTINCT a.file, a.line, a.target_var, a.source_expr
    FROM assignments a
    WHERE ({money_conditions})
""")
```

**Why This Is Wrong:**
Dynamically builds WHERE clause using f-strings. While `MONEY_TERMS` is a frozenset (not user input), this pattern is dangerous and bypasses parameterized queries.

**Required Fix:**
Use parameterized queries or IN clause with placeholders instead of f-string injection.

---

## 🎯 What This File Does RIGHT

### ✅ Excellent Frozenset Usage (Lines 52-152)
The rule defines **15+ frozensets** for O(1) pattern matching:
- `MONEY_TERMS` - Money-related variable patterns
- `FLOAT_FUNCTIONS` - Float conversion functions
- `DATETIME_FUNCTIONS` - Datetime functions
- `FILE_OPERATIONS` - File operation patterns
- And many more...

**This is GOLD STANDARD pattern recognition.**

### ✅ Perfect Finding Generation
All 12 `StandardFinding()` blocks:
- ✅ Use correct parameter names (`file_path=`, not `file=`)
- ✅ Use proper enums (`Severity.CRITICAL`, not `'CRITICAL'`)
- ✅ Include all required fields
- ✅ Include CWE IDs

### ✅ Comprehensive Logic Checks
The rule detects:
- Money/float arithmetic precision problems
- Timezone-naive datetime usage
- Email regex validation anti-patterns
- Division by zero risks
- Resource leaks (files, connections, transactions, sockets, streams, locks)

**This is excellent security coverage.**

---

## 🔧 Required Refactoring

### Priority 0 (Blocking)
1. **Remove ALL table existence checks** (lines 185-196, 199-202)
2. **Adopt `build_query()`** for all SELECT queries
3. **Remove ALL `has_*` conditionals** throughout the file

### Priority 1 (High)
4. **Split 510-line function** into 12 focused check functions
5. **Replace f-string queries** with parameterized queries

### Priority 2 (Medium)
6. **Add unit tests** for each check function
7. **Consider splitting into two files**: `business_logic_analyze.py` and `resource_management_analyze.py`

---

## 📈 Estimated Refactor Effort

**4-6 hours** to fix all critical violations and moderate issues.

**Breakdown:**
- Remove table existence checks: 30 minutes
- Migrate to `build_query()`: 2 hours
- Split into focused functions: 1.5 hours
- Add unit tests: 1-2 hours

---

## 🏆 Gold Standard Files

**None.** This file cannot be gold standard due to critical schema contract violations.

---

## ✅ Audit Conclusion

**Overall Assessment:** **REQUIRES IMMEDIATE REFACTOR**

**Rationale:**
While the rule demonstrates excellent pattern recognition (frozensets) and finding generation, it fundamentally violates the schema contract system through architectural anti-patterns:
- Table existence checking
- Conditional execution
- No `build_query()` usage

The **logic is sound**, but the **implementation must be refactored** to align with v1.1+ schema contract architecture.

---

## 📚 References

- **CLAUDE.md:** Lines 1259-1338 (Schema Contract System + ABSOLUTE PROHIBITION)
- **schema.py:** Lines 954-1005 (build_query() utility)
- **base.py:** Lines 130-184 (StandardFinding contract)
- **rulecheck_sop.md:** 3-Step SOP for rule auditing

---

**Full detailed findings:** `audit_logic_rules.json`
