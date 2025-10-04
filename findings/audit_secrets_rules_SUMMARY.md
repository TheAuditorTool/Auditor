# Atomic Rules Audit - Secrets Category

**Audit Date:** 2025-10-04
**Category:** secrets
**Files Audited:** 1
**Compliance Score:** 0/100 ❌

---

## Executive Summary

The secrets category contains **1 rule file** (`hardcoded_secret_analyze.py`). This file is **HIGH QUALITY CODE** with sophisticated pattern matching and comprehensive secret detection, but contains **ONE CRITICAL ARCHITECTURAL VIOLATION** that disqualifies it from gold standard compliance.

**Status:** ⚠️ **REQUIRES IMMEDIATE FIX**

---

## Detailed Analysis: hardcoded_secret_analyze.py

### ✅ Check 1: Metadata Verification - PASSED (100%)

**GOLD STANDARD** metadata configuration:

```python
METADATA = RuleMetadata(
    name="hardcoded_secrets",
    category="secrets",
    target_extensions=[
        '.py', '.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs',  # Code
        '.env', '.json', '.yml', '.yaml', '.toml', '.ini',    # Config
        '.sh', '.bash', '.zsh'                                 # Scripts
    ],
    exclude_patterns=[
        'node_modules/', 'venv/', '.venv/', 'migrations/',
        'test/', '__tests__/', 'tests/', '.env.example',
        '.env.template', 'package-lock.json', 'yarn.lock',
        'dist/', 'build/', '.git/'
    ],
    requires_jsx_pass=False
)
```

**Why this is excellent:**
- ✅ Comprehensive target extensions covering code, config, and scripts
- ✅ Intelligent exclusions for dependencies, tests, and example files
- ✅ Correct `requires_jsx_pass=False` (secrets don't require JSX syntax)

---

### ❌ Check 2: Database Contracts - FAILED (0%)

#### CRITICAL VIOLATION #1: Forbidden Table Existence Checks

**Location:** Lines 200-206

```python
# ❌ FORBIDDEN PATTERN
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name IN (
        'assignments', 'function_call_args', 'symbols', 'files'
    )
""")
existing_tables = {row[0] for row in cursor.fetchall()}
```

**Why this is forbidden:**
- Violates CLAUDE.md ABSOLUTE PROHIBITION: "NO FALLBACKS. NO REGEX. NO EXCEPTIONS."
- Schema contract system (`theauditor/indexer/schema.py`) **guarantees** all tables exist
- Any table existence check is "architectural cancer" that undermines the contract system

#### CRITICAL VIOLATION #2: Graceful Degradation Pattern

**Location:** Lines 209-217

```python
# ❌ FORBIDDEN PATTERN
has_assignments = 'assignments' in existing_tables
has_function_calls = 'function_call_args' in existing_tables
has_symbols = 'symbols' in existing_tables
has_files = 'files' in existing_tables

if has_assignments:
    findings.extend(_find_secret_assignments(cursor))
    ...
```

**Why this is forbidden:**
- Creates fallback execution paths that mask schema violations
- If a table doesn't exist, the rule **SHOULD crash** with a clear error
- Crashing indicates schema contract violation, not a condition to handle gracefully

#### ✅ Positive: All Actual Queries Are Valid

Despite the violations above, all **actual database queries** use valid tables and columns:

| Query Location | Table | Columns | Status |
|---|---|---|---|
| Lines 268-278 | `assignments` | `file`, `line`, `target_var`, `source_expr` | ✅ VALID |
| Lines 330-336 | `assignments` | `file`, `line`, `target_var`, `source_expr` | ✅ VALID |
| Lines 367-381 | `assignments` | `file`, `line`, `target_var`, `source_expr` | ✅ VALID |
| Lines 415-422 | `assignments` | `file`, `line`, `source_expr` | ✅ VALID |
| Lines 451-464 | `function_call_args` | `file`, `line`, `callee_function`, `argument_expr` | ✅ VALID |
| Lines 500-512 | `symbols` | `path`, `name` | ✅ VALID |
| Lines 517-527 | `files` | `path` | ✅ VALID |

**All columns verified against `theauditor/indexer/schema.py`**

---

### ✅ Check 3: Finding Generation - PASSED (100%)

All **8 StandardFinding calls** use correct parameter names and enums:

| Finding Type | Rule Name | Severity | Parameters |
|---|---|---|---|
| Weak password | `secret-weak-password` | CRITICAL | ✅ ALL CORRECT |
| Hardcoded assignment | `secret-hardcoded-assignment` | CRITICAL | ✅ ALL CORRECT |
| Connection string | `secret-connection-string` | CRITICAL | ✅ ALL CORRECT |
| Env fallback | `secret-env-fallback` | HIGH | ✅ ALL CORRECT |
| Dict literal | `secret-dict-literal` | CRITICAL | ✅ ALL CORRECT |
| API key in URL | `secret-api-key-in-url` | CRITICAL | ✅ ALL CORRECT |
| Pattern match | `secret-pattern-match` | CRITICAL | ✅ ALL CORRECT |
| High entropy | `secret-high-entropy` | HIGH | ✅ ALL CORRECT |

**All findings use:**
- ✅ `file_path=` (not `file=`)
- ✅ `rule_name=` (not `rule=`)
- ✅ `Severity` enum (not strings)
- ✅ `Confidence` enum (not strings)
- ✅ Proper CWE IDs

---

## Strengths (What Makes This Code High Quality)

### 1. Gold Standard Pattern Matching (Lines 72-163)

Uses **10 frozensets** for O(1) lookups:

```python
SECRET_KEYWORDS = frozenset([...])          # Line 72
WEAK_PASSWORDS = frozenset([...])           # Line 84
PLACEHOLDER_VALUES = frozenset([...])       # Line 92
NON_SECRET_VALUES = frozenset([...])        # Line 100
URL_PROTOCOLS = frozenset([...])            # Line 107
DB_PROTOCOLS = frozenset([...])             # Line 113
HIGH_CONFIDENCE_PATTERNS = frozenset([...]) # Line 120
GENERIC_SECRET_PATTERNS = frozenset([...])  # Line 138
SEQUENTIAL_PATTERNS = frozenset([...])      # Line 147
KEYBOARD_PATTERNS = frozenset([...])        # Line 157
```

**Impact:** O(1) pattern matching instead of O(n) loops

### 2. Justified Hybrid Approach (Lines 1-14, 30-35)

```python
"""
This rule demonstrates a JUSTIFIED HYBRID approach because:
1. Entropy calculation is computational, not indexed
2. Base64 decoding and verification requires runtime processing
3. Pattern matching for secret formats needs regex evaluation
4. Sequential/keyboard pattern detection is algorithmic
"""
```

**Why this is justified:**
- Shannon entropy calculation cannot be pre-indexed
- Base64 decoding requires runtime processing
- Provider-specific patterns (AWS keys, GitHub tokens) need regex evaluation
- Sequential pattern detection is algorithmic

### 3. Comprehensive Secret Detection

Detects:
- ✅ API keys (AWS, GitHub, GitLab, Stripe, Google, Dropbox, Square)
- ✅ Hardcoded passwords
- ✅ Private keys and certificates
- ✅ Database connection strings with passwords
- ✅ Environment variable fallbacks with secrets
- ✅ Dictionary/object literals with secrets
- ✅ API keys in URL parameters
- ✅ High-entropy strings (via Shannon entropy)
- ✅ Base64-encoded secrets

### 4. Sophisticated Analysis

- **Entropy calculation** (lines 598-617): Shannon entropy to detect randomness
- **Base64 decoding** (lines 648-677): Decodes and validates Base64 secrets
- **Sequential pattern detection** (lines 620-632): Filters out "abcdefg" patterns
- **Keyboard walk detection** (lines 635-645): Filters out "qwerty" patterns
- **Provider-specific patterns** (lines 120-135): AWS, GitHub, Stripe, etc.

---

## Required Fix (5 minutes)

### Step 1: Remove Table Existence Checks (Lines 200-217)

**DELETE:**
```python
# Check if required tables exist (Golden Standard)
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name IN (
        'assignments', 'function_call_args', 'symbols', 'files'
    )
""")
existing_tables = {row[0] for row in cursor.fetchall()}

# Minimum required table for secrets analysis
if 'assignments' not in existing_tables:
    return findings  # Can't analyze without assignment data

# Track which tables are available for graceful degradation
has_assignments = 'assignments' in existing_tables
has_function_calls = 'function_call_args' in existing_tables
has_symbols = 'symbols' in existing_tables
has_files = 'files' in existing_tables
```

### Step 2: Remove Conditional Execution (Lines 221-237)

**REPLACE:**
```python
if has_assignments:
    findings.extend(_find_secret_assignments(cursor))
    findings.extend(_find_connection_strings(cursor))
    findings.extend(_find_env_fallbacks(cursor))
    findings.extend(_find_dict_secrets(cursor))

if has_function_calls:
    findings.extend(_find_api_keys_in_urls(cursor))

if has_symbols and has_files:
    suspicious_files = _get_suspicious_files(cursor)
    ...
```

**WITH:**
```python
# Database-based checks (assume all tables exist)
findings.extend(_find_secret_assignments(cursor))
findings.extend(_find_connection_strings(cursor))
findings.extend(_find_env_fallbacks(cursor))
findings.extend(_find_dict_secrets(cursor))
findings.extend(_find_api_keys_in_urls(cursor))

# Pattern-based checks on suspicious files
suspicious_files = _get_suspicious_files(cursor)
for file_path in suspicious_files:
    ...
```

### Step 3: Expected Result

After fix, rule will:
- ✅ Execute all checks unconditionally
- ✅ Crash with clear error if schema contract is violated (CORRECT behavior)
- ✅ Achieve **100% compliance score**
- ✅ Become a **GOLD STANDARD** example

---

## Compliance Score Breakdown

| Check | Score | Details |
|---|---|---|
| **Metadata** | 100% | Perfect configuration |
| **Database Contracts** | 0% | CRITICAL: Forbidden table existence checks |
| **Finding Generation** | 100% | All parameters correct |
| **TOTAL** | **0%** | One critical violation disqualifies file |

---

## Recommendation

**Status:** ⚠️ **REQUIRES IMMEDIATE FIX**

This file is **95% gold standard** quality. The only issue is the forbidden table existence pattern. After removing lines 200-217 and simplifying the execution logic, this would be an **exemplary rule file** demonstrating:
- Perfect metadata configuration
- Valid database queries
- Sophisticated pattern matching with frozensets
- Correct finding generation
- Justified hybrid approach

**Estimated fix time:** 5 minutes
**Priority:** CRITICAL (violates architectural principle)

---

## Files Audited

1. ✅ `hardcoded_secret_analyze.py` - Audited ⚠️ CRITICAL VIOLATIONS

**Total:** 1 file
**Gold Standard:** 0 files
**Requires Fix:** 1 file
