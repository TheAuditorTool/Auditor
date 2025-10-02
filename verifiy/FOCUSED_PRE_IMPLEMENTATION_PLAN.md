# Focused Pre-Implementation Plan
**Version:** 2.0 (Architect-Approved Scope)
**Date:** 2025-10-03
**Bugs Covered:** 2, 3, 5, 6, 7, 8, 11, 12
**Excluded:** Taint (complex), Memory Cache (complex)

---

## Phase 0: Architect Directives Summary

**CRITICAL CORRECTIONS:**
1. ❌ **No Taint Work** - Too complex, skip entirely
2. ❌ **No Memory Cache Work** - Too complex, skip entirely
3. ❌ **Don't Disable TOCTOU** - Fix the root cause, don't just disable
4. ✅ **Missing Function = ALL Python Projects** - Not just self-scan, this is universal Python indexing failure

**Approved Bugs for Implementation:**
- BUG-002: Missing function (ALL Python projects broken)
- BUG-003: TOCTOU false positives (fix algorithm, don't disable)
- BUG-005: Rule metadata propagation
- BUG-006: Phase status reporting
- BUG-007: SQL query misclassification
- BUG-008: Health check system
- BUG-011: Uniform finding distribution (related to TOCTOU)
- BUG-012: JSX symbol count mismatch

---

## BUG-002: Missing Function Breaks ALL Python Projects (P0 - CRITICAL)

### Current Understanding

**Severity:** CRITICAL - Affects ALL Python projects, not just TheAuditor
**Impact:** Any project with Tree-sitter-parsed Python files gets 0 symbols extracted

**Evidence from Code Inspection:**
```python
# File: theauditor/ast_extractors/__init__.py:273
if tree_type == "tree_sitter" and self.has_tree_sitter:
    return treesitter_impl.extract_treesitter_cfg(tree, self, language)
    # ↑ This function DOES NOT EXIST
```

**Verification:**
```bash
$ grep -n "def extract_treesitter_cfg" theauditor/ast_extractors/treesitter_impl.py
# (no output - function doesn't exist)

$ grep -n "^def " theauditor/ast_extractors/treesitter_impl.py | head -20
# Shows: extract_treesitter_functions, extract_treesitter_classes, etc.
# NO extract_treesitter_cfg
```

**Why This Went Undetected:**
1. Exception is caught silently (broad try-except)
2. Returns empty dict on error
3. Pipeline continues and reports success
4. Only way to detect: Check database has symbols > 0

### Hypotheses to Verify

**Hypothesis 2.1:** Function never existed (typo in caller)
- **Verification:** Git history search for "extract_treesitter_cfg"
- **Method:** `git log -p --all -S "extract_treesitter_cfg"`
- **Expected:** No results = function was never implemented

**Hypothesis 2.2:** Function was removed/renamed during refactoring
- **Verification:** Git history shows deletion
- **Method:** `git log -p --all -- "*treesitter_impl.py" | grep -C 5 "extract_treesitter_cfg"`
- **Expected:** Find commit where function was removed

**Hypothesis 2.3:** CFG extraction moved to separate phase
- **Verification:** Check if CFG analyzer handles this
- **Method:** Read `theauditor/commands/cfg.py`
- **Expected:** CFG analyzer extracts CFG separately (line 273 call is redundant)

**Hypothesis 2.4:** Tree-sitter type detection is wrong
- **Verification:** Check when tree_type == "tree_sitter"
- **Method:** Read parsing logic to see when this type is set
- **Expected:** This type is never actually set (dead code path)

### Files to Read (Verification Phase)

**MANDATORY READS:**
1. `theauditor/ast_extractors/__init__.py:260-280` ✅ DONE - Found call site
2. `theauditor/ast_extractors/treesitter_impl.py` ✅ DONE - Function doesn't exist
3. `theauditor/commands/cfg.py` - Check if CFG extraction elsewhere
4. `theauditor/ast_extractors/python_impl.py` - Check what returns tree_type
5. Git history for function name

**EXPECTED FINDINGS:**
- Option A: Function never existed (caller has typo)
- Option B: Function was removed (CFG moved to separate phase)
- Option C: tree_type "tree_sitter" never actually occurs (dead code)

### Implementation Strategy (3 Scenarios)

**SCENARIO A: Function Never Existed (Typo)**
```python
# File: theauditor/ast_extractors/__init__.py:273

# REMOVE LINE (dead code):
# return treesitter_impl.extract_treesitter_cfg(tree, self, language)

# OR if CFG extraction needed:
if hasattr(treesitter_impl, 'extract_cfg'):
    return treesitter_impl.extract_cfg(tree, self, language)
else:
    logger.debug("CFG extraction not available for tree-sitter")
    return []
```

**SCENARIO B: CFG Extraction Moved to Separate Phase**
```python
# File: theauditor/ast_extractors/__init__.py:273

# REMOVE LINE:
# return treesitter_impl.extract_treesitter_cfg(tree, self, language)

# ADD COMMENT:
# CFG extraction now handled by separate 'aud cfg analyze' command
# This call was redundant with the dedicated CFG analyzer phase
return []
```

**SCENARIO C: Implement Missing Function (If Actually Needed)**
```python
# NEW FUNCTION in theauditor/ast_extractors/treesitter_impl.py

def extract_treesitter_cfg(tree: Dict, parser_self, language: str) -> List[Dict]:
    """Extract control flow graph from tree-sitter AST.

    NOTE: This is a stub. Full CFG extraction is handled by
    the dedicated CFG analyzer command (aud cfg analyze).
    """
    logger.debug("CFG extraction from tree-sitter not implemented in indexer")
    return []
```

### Critical Fix: Exception Handling

**Current Code (Silent Failure):**
```python
# File: theauditor/ast_extractors/__init__.py (surrounding line 273)

try:
    # ... extraction logic ...
    if tree_type == "tree_sitter" and self.has_tree_sitter:
        return treesitter_impl.extract_treesitter_cfg(tree, self, language)
except Exception as e:
    # PROBLEM: Catches AttributeError and returns empty
    logger.debug(f"Extraction failed: {e}")
    return []
```

**Fixed Code (Proper Error Handling):**
```python
try:
    # ... extraction logic ...
    if tree_type == "tree_sitter" and self.has_tree_sitter:
        # Add existence check
        if not hasattr(treesitter_impl, 'extract_treesitter_cfg'):
            logger.warning(
                f"extract_treesitter_cfg not available in treesitter_impl. "
                f"CFG extraction skipped for {language} files."
            )
            return []

        return treesitter_impl.extract_treesitter_cfg(tree, self, language)

except SyntaxError as e:
    # EXPECTED: Malformed source files
    logger.debug(f"Syntax error in file: {e}")
    return []

except AttributeError as e:
    # UNEXPECTED: Missing functions (should not happen with check above)
    logger.error(f"CRITICAL: Missing extractor function: {e}")
    logger.error(f"This indicates a code regression. Please file a bug report.")
    # Return empty to allow pipeline to continue, but log prominently
    return []

except Exception as e:
    # UNEXPECTED: Other errors
    logger.error(f"Unexpected extraction error: {e}", exc_info=True)
    raise  # Don't silently swallow unexpected errors
```

### Verification Tests (Post-Implementation)

**Test 2.1: Function exists or code path removed**
```bash
python3 -c "
from theauditor.ast_extractors import treesitter_impl
has_func = hasattr(treesitter_impl, 'extract_treesitter_cfg')
print(f'Function exists: {has_func}')
"
# Expected: True OR code path at line 273 removed
```

**Test 2.2: TheAuditor self-analysis works**
```bash
cd ~/TheAuditor
rm -rf .pf/
aud index --exclude-self

# Check symbols extracted
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols"
# Expected: > 10,000 (not 0)

# Check files processed
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM files WHERE path LIKE '%.py'"
# Expected: > 200
```

**Test 2.3: All 6 audit projects work**
```bash
for project in plant project_anarchy PlantFlow PlantPro raicalc TheAuditor; do
    cd $project
    rm -rf .pf/
    aud index 2>&1 | grep -i "error\|critical\|failed"

    symbols=$(sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols")
    files=$(sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM files")

    echo "$project: $symbols symbols from $files files"

    # Validate reasonable ratio
    if [ $files -gt 0 ] && [ $symbols -lt $files ]; then
        echo "⚠️  WARNING: Less than 1 symbol per file (probable failure)"
    fi
done

# Expected: All projects have symbols > files (reasonable ratio)
```

**Test 2.4: Exception handling improved**
```bash
# Create malformed Python file
echo "def broken_syntax(" > /tmp/test_broken.py

# Try to index it
cd /tmp
echo "def broken_syntax(" > test.py
aud init
aud index 2>&1 | tee index_log.txt

# Check error handling
grep -i "syntax error" index_log.txt
# Expected: Logs syntax error but doesn't crash

# Check other files still processed
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM files"
# Expected: > 0 (other files still indexed despite syntax error)
```

**Test 2.5: Regression test (prevent future breakage)**
```bash
# Create integration test
cat > tests/test_treesitter_extraction.py << 'EOF'
import pytest
from theauditor.ast_extractors import treesitter_impl

def test_extract_treesitter_cfg_exists():
    """Ensure CFG extraction function exists or code path is removed."""
    # Either function exists
    has_func = hasattr(treesitter_impl, 'extract_treesitter_cfg')

    # OR the caller has been updated (check in __init__.py)
    # This test will fail if someone adds the call back without the function

    if has_func:
        # Function exists - verify it's callable
        assert callable(treesitter_impl.extract_treesitter_cfg)
    else:
        # Function doesn't exist - verify caller was updated
        import inspect
        from theauditor.ast_extractors import GenericParser

        source = inspect.getsource(GenericParser.extract_cfg)

        # Should NOT contain the function call
        assert 'extract_treesitter_cfg' not in source, \
            "extract_treesitter_cfg called but function doesn't exist"
EOF

pytest tests/test_treesitter_extraction.py
# Expected: PASS
```

### Edge Cases & Failure Modes

**Edge 2.1: Different languages use tree-sitter differently**
- **Condition:** JavaScript uses tree-sitter, Python uses ast module
- **Current:** Both code paths exist
- **Fix:** Ensure check is language-aware
- **Test:** Index both Python and JavaScript projects

**Edge 2.2: CFG extraction truly needed during indexing**
- **Condition:** Some analysis requires CFG during index phase
- **Current:** Separate CFG analyzer phase exists
- **Fix:** Verify CFG analyzer phase is sufficient
- **Test:** Run full pipeline, check cfg_blocks table populated

**Edge 2.3: Tree-sitter not available**
- **Condition:** User didn't run `aud setup-claude`
- **Current:** `self.has_tree_sitter` check exists
- **Fix:** Ensure graceful degradation
- **Test:** Run without tree-sitter, verify still extracts via ast

**Edge 2.4: Partial extraction failure**
- **Condition:** Some files extract, others fail
- **Current:** Each file exception is caught separately
- **Fix:** Ensure one file failure doesn't stop entire index
- **Test:** Mix valid and invalid Python files

### Impact Assessment

**Immediate:**
- TheAuditor self-analysis: 0 → 15,000 symbols ✅
- ALL Python projects: Successful indexing restored ✅
- Error visibility: Silent failures now logged ✅

**Downstream:**
- Pattern detection works (requires symbols)
- Graph analysis works (requires imports)
- All Python-based rules can run

**Breaking Changes:**
- None (only fixes broken functionality)

### Reversion Plan

**Reversibility:** Fully reversible
```bash
git revert <commit_hash>
```

**No data loss:** Database changes are additions only

### Estimated Effort

**Verification Phase (1.5 hours):**
- Git history search: 20 minutes
- Read cfg.py: 15 minutes
- Read python_impl.py: 15 minutes
- Determine correct scenario: 20 minutes
- Read surrounding exception handling: 20 minutes

**Implementation Phase (1.5 hours):**
- Remove/fix function call: 15 minutes
- Improve exception handling: 30 minutes
- Add existence checks: 20 minutes
- Write regression test: 25 minutes

**Testing Phase (1.5 hours):**
- Test TheAuditor self-scan: 15 minutes
- Test all 6 projects: 30 minutes
- Test malformed Python file: 15 minutes
- Validate exception handling: 15 minutes
- Run regression test: 15 minutes

**Total: 4.5 hours**

**Confidence:** High (straightforward fix once scenario determined)

---

## BUG-003: TOCTOU False Positive Explosion (P0 - CRITICAL)

### Current Understanding

**Severity:** CRITICAL - Makes output unusable (900K-3.5M findings)
**Impact:** 3/6 projects unusable due to false race condition findings

**Evidence from Code Inspection:**
```python
# File: theauditor/rules/node/async_concurrency_analyze.py:642-675

cursor.execute("""
    SELECT f1.file, f1.line, f1.callee_function, f2.callee_function
    FROM function_call_args f1
    JOIN function_call_args f2 ON f1.file = f2.file
    WHERE f2.line BETWEEN f1.line + 1 AND f1.line + 10
    ORDER BY f1.file, f1.line
""")

for file, line, check_func, write_func in cursor.fetchall():
    # Check if first is a check operation
    is_check = False
    for pattern in self.patterns.CHECK_OPERATIONS:  # 'exists', 'has', 'includes', etc.
        if pattern in check_func:
            is_check = True
            break

    # Check if second is a write operation
    is_write = False
    for pattern in self.patterns.WRITE_OPERATIONS:  # 'save', 'update', 'insert', etc.
        if pattern in write_func:
            is_write = True
            break

    if is_check and is_write:
        # ⚠️ PROBLEM: Flags ALL check→write pairs regardless of object
        self.findings.append(StandardFinding(
            rule_name='check-then-act',
            message=f'TOCTOU race: {check_func} then {write_func}',
            severity=Severity.CRITICAL,  # ⚠️ Too high for low confidence
            confidence=Confidence.HIGH,   # ⚠️ Should be LOW/MEDIUM
        ))
```

**Patterns:**
```python
CHECK_OPERATIONS = frozenset([
    'exists', 'has', 'includes', 'contains', 'indexOf',
    'hasOwnProperty', 'in', 'get', 'find', 'some', 'every'
])

WRITE_OPERATIONS = frozenset([
    'save', 'update', 'insert', 'delete', 'write', 'create',
    'put', 'post', 'patch', 'remove', 'set', 'add', 'push'
])
```

**Why It Produces False Positives:**
```javascript
// Example code:
const data = await fetchData();
if (data.includes(userId)) {        // Line 100: CHECK operation on 'data'
    logger.warn('User already exists'); // Line 102: 'warn' not in WRITE_OPERATIONS (OK)
    errors.push(new Error('Duplicate')); // Line 103: WRITE operation on 'errors'
}

// Current algorithm:
// 1. Cartesian join finds: (line 100, 'data.includes') and (line 103, 'errors.push')
// 2. 'includes' matches CHECK_OPERATIONS ✓
// 3. 'push' matches WRITE_OPERATIONS ✓
// 4. Flags as CRITICAL race condition ✗ WRONG (different objects!)

// Real TOCTOU would be:
if (fs.existsSync(filePath)) {  // CHECK file exists
    // ⚠️ Race window: file could be deleted here
    fs.readFileSync(filePath);  // USE file (TOCTOU vulnerability!)
}
```

### Hypotheses to Verify

**Hypothesis 3.1:** Algorithm doesn't extract object being operated on
- **Verification:** Read function_call_args table schema
- **Method:** `sqlite3 .pf/repo_index.db ".schema function_call_args"`
- **Expected:** Table has `callee_function` but not separate object field

**Hypothesis 3.2:** Extracting object from function name is difficult
- **Verification:** Sample function_call_args entries
- **Method:** `SELECT callee_function FROM function_call_args LIMIT 100`
- **Expected:** Various formats: `obj.method`, `method`, `module.obj.method`

**Hypothesis 3.3:** Argument expressions contain object references
- **Verification:** Check if argument_expr field exists and has data
- **Method:** `SELECT callee_function, argument_expr FROM function_call_args WHERE argument_expr IS NOT NULL LIMIT 20`
- **Expected:** Arguments like `(filePath)`, `(data, index)`, etc.

**Hypothesis 3.4:** Many legitimate patterns flagged incorrectly
- **Verification:** Sample 100 findings from PlantFlow
- **Method:** `SELECT file, line, message FROM findings_consolidated WHERE category='race-condition' ORDER BY RANDOM() LIMIT 100`
- **Expected:** >95% are different objects (false positives)

### Root Cause Analysis

**The Algorithm Problem:**
1. **Cartesian Explosion:** O(n²) pairs generated
   - 9,679 function calls → 46,427 candidate pairs
   - Only filters by 10-line proximity

2. **No Object Tracking:** Flags operations on different objects
   - `data.includes(x)` → `errors.push(y)` flagged ✗
   - `file.exists()` → `file.read()` flagged ✓ (correct)

3. **Pattern Matching Too Broad:** Substring matching catches wrong functions
   - `hasOwnProperty` matches but `has` also matches `hashCode` ✗
   - `update` matches `updateUI`, `updateCounter`, `updateTimer` (most false positives)

4. **No Context Awareness:**
   - No check if code is async
   - No check if operations in transaction
   - No check if mutex/lock present

### Implementation Strategy

**PHASE 3A: Improve Object Extraction (2 hours)**

```python
# NEW FUNCTION in async_concurrency_analyze.py

def _extract_base_object(callee_function: str) -> str:
    """
    Extract the base object being operated on.

    Examples:
        'fs.existsSync' → 'fs'
        'user.save' → 'user'
        'Array.isArray' → 'Array'
        'save' → '' (no object)
        'logger.warn' → 'logger'
    """
    if '.' in callee_function:
        # Object method: 'obj.method' → 'obj'
        parts = callee_function.split('.')
        return parts[0]
    else:
        # Plain function: 'save' → '' (no object)
        return ''

def _extract_operation_target(callee_function: str, argument_expr: str) -> str:
    """
    Extract what is being operated on (object + first argument).

    Examples:
        ('fs.existsSync', 'filePath') → 'fs:filePath'
        ('user.save', '') → 'user'
        ('Array.isArray', 'data') → 'Array:data'

    This allows matching:
        fs.existsSync(filePath) + fs.readFileSync(filePath) ✓ SAME TARGET
        data.includes(x) + errors.push(y) ✗ DIFFERENT TARGETS
    """
    base_obj = _extract_base_object(callee_function)

    # Parse first argument from expression
    first_arg = ''
    if argument_expr:
        # Simple extraction: get first identifier
        # Example: '(filePath, options)' → 'filePath'
        cleaned = argument_expr.strip('()')
        if ',' in cleaned:
            first_arg = cleaned.split(',')[0].strip()
        else:
            first_arg = cleaned.strip()

    if base_obj and first_arg:
        return f"{base_obj}:{first_arg}"
    elif base_obj:
        return base_obj
    elif first_arg:
        return first_arg
    else:
        return ''
```

**PHASE 3B: Refactor TOCTOU Detection (3 hours)**

```python
def _check_toctou_race_conditions(self) -> None:
    """Check for time-of-check-time-of-use race conditions.

    Improved algorithm:
    1. Group operations by target (object + argument)
    2. Only flag if CHECK and WRITE on SAME target
    3. Add confidence scoring based on match quality
    4. Reduce severity from CRITICAL to HIGH/MEDIUM
    """
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all function calls with their arguments
        cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE file LIKE '%.js' OR file LIKE '%.jsx'
               OR file LIKE '%.ts' OR file LIKE '%.tsx'
            ORDER BY file, line
        """)

        all_calls = cursor.fetchall()

        # Group by file
        calls_by_file = {}
        for file, line, func, args in all_calls:
            if file not in calls_by_file:
                calls_by_file[file] = []
            calls_by_file[file].append((line, func, args))

        # Process each file
        for file, calls in calls_by_file.items():
            # Build index of operations by target
            check_ops = {}  # {target: [(line, function)]}
            write_ops = {}  # {target: [(line, function)]}

            for line, func, args in calls:
                target = self._extract_operation_target(func, args)
                if not target:
                    continue  # Skip if can't determine target

                # Check if CHECK operation
                is_check = any(pattern in func for pattern in self.patterns.CHECK_OPERATIONS)
                if is_check:
                    if target not in check_ops:
                        check_ops[target] = []
                    check_ops[target].append((line, func))

                # Check if WRITE operation
                is_write = any(pattern in func for pattern in self.patterns.WRITE_OPERATIONS)
                if is_write:
                    if target not in write_ops:
                        write_ops[target] = []
                    write_ops[target].append((line, func))

            # Find TOCTOU pairs (CHECK then WRITE on SAME target)
            for target, checks in check_ops.items():
                if target not in write_ops:
                    continue  # No write on this target

                writes = write_ops[target]

                # For each CHECK operation
                for check_line, check_func in checks:
                    # Find WRITEs within 10 lines after CHECK
                    for write_line, write_func in writes:
                        if 1 <= write_line - check_line <= 10:
                            # Potential TOCTOU detected

                            # Calculate confidence
                            confidence = self._calculate_toctou_confidence(
                                check_func, write_func, target
                            )

                            # Determine severity based on confidence
                            if confidence >= 0.7:
                                severity = Severity.HIGH
                            elif confidence >= 0.5:
                                severity = Severity.MEDIUM
                            else:
                                severity = Severity.LOW

                            self.findings.append(StandardFinding(
                                rule_name='check-then-act',
                                message=f'Potential TOCTOU: {check_func} at line {check_line}, then {write_func} at line {write_line} (target: {target})',
                                file_path=file,
                                line=check_line,
                                severity=severity,
                                category='race-condition',
                                confidence=confidence,
                                snippet=f'{check_func} → {write_func} (target: {target})',
                            ))

        conn.close()

    except (sqlite3.Error, Exception) as e:
        logger.error(f"TOCTOU detection failed: {e}")


def _calculate_toctou_confidence(self, check_func: str, write_func: str, target: str) -> float:
    """
    Calculate confidence that this is a real TOCTOU vulnerability.

    Factors:
    - Object match quality (obj.method vs just method)
    - Known TOCTOU patterns (fs.exists + fs.read)
    - Argument match (same variable name)

    Returns: 0.0-1.0
    """
    confidence = 0.5  # Base confidence

    # Boost: Operations on specific file system object
    if 'fs.' in check_func or 'fs.' in write_func:
        confidence += 0.2

    # Boost: Target includes specific variable (not just object)
    if ':' in target:  # Format is 'obj:variable'
        confidence += 0.15

    # Boost: Known TOCTOU patterns
    known_patterns = [
        ('exists', 'read'),
        ('exists', 'write'),
        ('exists', 'delete'),
        ('has', 'get'),
        ('includes', 'remove'),
    ]

    for check_pattern, write_pattern in known_patterns:
        if check_pattern in check_func.lower() and write_pattern in write_func.lower():
            confidence += 0.15
            break

    # Penalty: Generic operations (likely false positive)
    generic_ops = ['save', 'update', 'create']  # Too broad
    if any(op in write_func.lower() for op in generic_ops):
        confidence -= 0.1

    # Clamp to 0.0-1.0
    return max(0.0, min(1.0, confidence))
```

**PHASE 3C: Add Pattern Refinement (1 hour)**

```python
# Refine CHECK_OPERATIONS to be more specific
CHECK_OPERATIONS = frozenset([
    # File system checks
    'existsSync', 'exists', 'accessSync', 'access',
    'stat', 'lstat', 'fstat',

    # Collection checks
    'has', 'includes', 'contains', 'hasOwnProperty',
    'indexOf',  # Keep but verify context

    # Database checks
    'find', 'findOne', 'get',

    # Generic (lower confidence)
    'some', 'every',
])

# Refine WRITE_OPERATIONS to be more specific
WRITE_OPERATIONS = frozenset([
    # File system writes
    'writeFile', 'writeFileSync', 'appendFile', 'appendFileSync',
    'unlink', 'unlinkSync', 'rmdir', 'rmdirSync',
    'mkdir', 'mkdirSync',

    # Database writes
    'save', 'insert', 'insertOne', 'insertMany',
    'update', 'updateOne', 'updateMany',
    'delete', 'deleteOne', 'deleteMany',
    'remove', 'removeOne', 'removeMany',

    # Collection modifications
    'push', 'pop', 'shift', 'unshift', 'splice',
    'set', 'add', 'clear',

    # HTTP writes
    'post', 'put', 'patch', 'delete',
])
```

### Verification Tests (Post-Implementation)

**Test 3.1: PlantFlow findings reduction**
```bash
cd PlantFlow
rm -rf .pf/
aud detect-patterns

# Check race-condition findings
total=$(sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE category='race-condition'")
echo "Total race-condition findings: $total"

# Expected: < 1,000 (down from 415,800)
if [ $total -gt 10000 ]; then
    echo "❌ FAIL: Still generating excessive findings"
    exit 1
fi
```

**Test 3.2: Sample findings for false positives**
```bash
# Get 20 random race condition findings
sqlite3 .pf/repo_index.db "
    SELECT file, line, message
    FROM findings_consolidated
    WHERE category='race-condition'
    ORDER BY RANDOM()
    LIMIT 20
" > sample_findings.txt

# Manual review: Check if they're operating on same object
# Expected: >80% should involve same object (target)
```

**Test 3.3: Confidence scoring distribution**
```bash
# Check confidence distribution
sqlite3 .pf/repo_index.db "
    SELECT
        CASE
            WHEN confidence >= 0.7 THEN 'HIGH (0.7-1.0)'
            WHEN confidence >= 0.5 THEN 'MEDIUM (0.5-0.7)'
            ELSE 'LOW (0.0-0.5)'
        END as confidence_range,
        COUNT(*) as count
    FROM findings_consolidated
    WHERE category='race-condition'
    GROUP BY confidence_range
"

# Expected distribution:
# HIGH: 10-20% (real TOCTOU vulnerabilities)
# MEDIUM: 20-30% (possible issues)
# LOW: 50-70% (low confidence, user can filter)
```

**Test 3.4: Known TOCTOU vulnerability detected**
```javascript
// Create test file with real TOCTOU
// test_toctou.js
if (fs.existsSync(configFile)) {
    // Race window: file could be deleted here by another process
    const config = fs.readFileSync(configFile);
}
```
```bash
cd /tmp
cat > test_toctou.js << 'EOF'
const fs = require('fs');
const configFile = '/tmp/config.json';

if (fs.existsSync(configFile)) {
    const config = fs.readFileSync(configFile);
    console.log(config);
}
EOF

aud init
aud detect-patterns

# Check detection
sqlite3 .pf/repo_index.db "
    SELECT message, confidence, severity
    FROM findings_consolidated
    WHERE category='race-condition'
      AND file LIKE '%test_toctou%'
"

# Expected:
# - Detected: 1 finding
# - Confidence: >= 0.7 (HIGH)
# - Severity: HIGH
# - Message mentions fs.existsSync and fs.readFileSync
```

**Test 3.5: False positive NOT flagged**
```javascript
// Create test file with false positive pattern
// test_false_positive.js
const data = await fetchUsers();

if (data.includes(userId)) {
    logger.warn('User already exists');
    errors.push(new Error('Duplicate user'));
}
```
```bash
cat > test_false_positive.js << 'EOF'
async function checkUser(userId) {
    const data = await fetchUsers();

    if (data.includes(userId)) {
        logger.warn('User already exists');
        errors.push(new Error('Duplicate user'));
    }
}
EOF

aud detect-patterns

# Check if flagged
sqlite3 .pf/repo_index.db "
    SELECT COUNT(*)
    FROM findings_consolidated
    WHERE category='race-condition'
      AND file LIKE '%test_false_positive%'
      AND message LIKE '%includes%push%'
"

# Expected: 0 (not flagged because different targets: data vs errors)
```

**Test 3.6: Total findings across all projects**
```bash
for project in plant PlantFlow PlantPro; do
    cd $project
    rm -rf .pf/
    aud detect-patterns

    total=$(sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated")
    race=$(sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE category='race-condition'")

    echo "$project: $total total findings, $race race conditions"

    # Expected:
    # - Total < 10,000 (not 900K-3.5M)
    # - Race conditions < 1,000 (not 400K+)
done
```

### Edge Cases & Failure Modes

**Edge 3.1: Complex object paths**
```javascript
// Example: user.profile.settings.save()
// Base object: 'user' or 'user.profile.settings'?
```
- **Fix:** Use first segment only (`user`)
- **Rationale:** Conservative matching reduces false negatives

**Edge 3.2: Dynamic property access**
```javascript
// Example: obj[key].save()
// Can't determine object statically
```
- **Fix:** Extract `obj` only, ignore dynamic part
- **Confidence:** Reduce by 0.1 for dynamic access

**Edge 3.3: Chained method calls**
```javascript
// Example: users.filter(x => x.active).map(u => u.save())
// Multiple operations in one expression
```
- **Fix:** Extract outermost object (`users`)
- **Note:** May miss nested TOCTOU (acceptable tradeoff)

**Edge 3.4: No object (plain function calls)**
```javascript
// Example: save(), update()
// No object to track
```
- **Fix:** Skip (can't determine target)
- **Impact:** May miss some TOCTOU, but reduces false positives

### Impact Assessment

**Immediate:**
- PlantFlow: 904,359 → <10,000 findings (usable) ✅
- PlantPro: 1,453,139 → <10,000 findings (usable) ✅
- plant: 3,530,473 → <10,000 findings (usable) ✅

**Quality:**
- False positive rate: 99% → <20% (estimated) ✅
- True TOCTOU still detected (fs.exists → fs.read) ✅
- Confidence scoring enables user filtering ✅

**Performance:**
- Algorithm: O(n²) → O(n log n) (grouping by target)
- PlantFlow: ~210s → ~30s (estimated)

**Breaking Changes:**
- Fewer findings (users expecting all CHECK→WRITE pairs will see reduction)
- New confidence field (downstream tools may need update)

### Reversion Plan

**Reversibility:** Fully reversible
```bash
git revert <commit_hash>
```

**Rollback triggers:**
- True TOCTOU vulnerabilities not detected (confidence too conservative)
- Algorithm too complex (performance regression)

### Estimated Effort

**Verification Phase (1 hour):**
- Inspect function_call_args schema: 10 minutes
- Sample findings from PlantFlow: 20 minutes
- Analyze false positive patterns: 20 minutes
- Review argument_expr data: 10 minutes

**Implementation Phase (6 hours):**
- Write _extract_base_object: 30 minutes
- Write _extract_operation_target: 1 hour
- Refactor _check_toctou_race_conditions: 3 hours
- Write _calculate_toctou_confidence: 1 hour
- Refine CHECK/WRITE patterns: 30 minutes

**Testing Phase (2 hours):**
- Test PlantFlow reduction: 15 minutes
- Sample findings review: 30 minutes
- Test known TOCTOU detection: 20 minutes
- Test false positive filtering: 20 minutes
- Test all 3 projects: 35 minutes

**Total: 9 hours**

**Confidence:** Medium-High (complex refactor but clear algorithm)

---

## BUG-005: Rule Metadata Not Propagating (P1)

### Current Understanding

**Severity:** HIGH - Cannot trace findings to rules
**Impact:** All pattern findings tagged as `rule="unknown"`

**Evidence:**
```sql
-- PlantPro database
SELECT DISTINCT rule FROM findings_consolidated WHERE tool='patterns';
-- Result: Only 'unknown'
-- Expected: 'jwt_analyze', 'xss_analyze', 'sql_injection_analyze', etc.
```

### Hypotheses to Verify

**Hypothesis 5.1:** StandardFinding has rule field but not populated
- **Verification:** Read StandardFinding class definition
- **Expected:** Field exists but defaults to "unknown"

**Hypothesis 5.2:** Rules don't set rule name when creating findings
- **Verification:** Sample rule file (e.g., jwt_analyze.py)
- **Expected:** Findings created without `rule=` parameter

**Hypothesis 5.3:** Orchestrator doesn't pass rule metadata
- **Verification:** Read rules orchestrator
- **Expected:** Executes rules but doesn't inject metadata

### Files to Read

**MANDATORY:**
1. `theauditor/rules/base.py` - StandardFinding class
2. `theauditor/rules/orchestrator.py` - Rule execution
3. `theauditor/rules/auth/jwt_analyze.py` - Sample rule
4. `theauditor/indexer/database.py` - Findings storage

### Implementation Strategy

**Step 5.1: Verify StandardFinding has rule field**
```python
# File: theauditor/rules/base.py

@dataclass
class StandardFinding:
    file_path: str
    line: int
    severity: Severity
    category: str
    message: str
    rule_name: str = "unknown"  # ← Ensure this field exists
    confidence: float = 1.0
    snippet: str = ""
```

**Step 5.2: Orchestrator injects rule name**
```python
# File: theauditor/rules/orchestrator.py

for rule_module in discovered_rules:
    try:
        findings = rule_module.analyze(context)

        # ADD: Inject rule name if not set
        for finding in findings:
            if finding.rule_name == "unknown":
                # Use METADATA.name from rule module
                finding.rule_name = rule_module.METADATA.name

        all_findings.extend(findings)
    except Exception as e:
        logger.error(f"Rule {rule_module.__name__} failed: {e}")
```

**Step 5.3: Database stores rule field**
```python
# File: theauditor/indexer/database.py
# Verify INSERT includes rule_name

INSERT INTO findings_consolidated
(file, line, severity, category, message, tool, rule, confidence)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```

### Verification Tests

**Test 5.1: Database has rule names**
```bash
aud detect-patterns

sqlite3 .pf/repo_index.db "SELECT DISTINCT rule FROM findings_consolidated WHERE tool='patterns'"
# Expected: Multiple rule names (not just "unknown")
```

**Test 5.2: Specific rule traced**
```bash
sqlite3 .pf/repo_index.db "
    SELECT COUNT(*)
    FROM findings_consolidated
    WHERE rule='jwt_analyze' OR rule LIKE '%jwt%'
"
# Expected: > 0
```

### Estimated Effort: 3 hours

---

## BUG-006: Phase Status Reporting (P1)

### Current Understanding

**Severity:** HIGH - Misleading status hides failures
**Impact:** Pipeline shows "[OK]" when phases actually failed

**Evidence:**
```
[Phase 17/20] 17. Taint analysis
[OK] 17. Taint analysis completed in 4.8s

But error.log shows:
Error in command: taint_analyze
click.exceptions.ClickException: no such column: line
```

### Implementation Strategy

**Check return status:**
```python
# File: theauditor/pipelines.py

result = run_phase(phase)

# Parse result for errors
if isinstance(result, dict) and result.get('success') == False:
    logger.error(f"[FAILED] {phase.name}: {result.get('error')}")
    phase.status = "failed"
else:
    logger.info(f"[OK] {phase.name} completed")
    phase.status = "success"
```

### Verification Tests

**Test 6.1: Failed phase shows FAILED**
```bash
# Temporarily break taint analysis
aud full 2>&1 | grep "Taint analysis"
# Expected: "[FAILED] Taint analysis" (not "[OK]")
```

### Estimated Effort: 3 hours

---

## BUG-007: SQL Query Misclassification (P1)

### Current Understanding

**Severity:** MEDIUM - JWT operations flagged as SQL
**Impact:** SQL injection analysis has false positives

**Evidence:**
```sql
SELECT command, COUNT(*) FROM sql_queries GROUP BY command;
-- Results:
-- JWT_JWT_SIGN_VARIABLE: 2
-- JWT_JWT_VERIFY_UNKNOWN: 2
-- SELECT: 1  (the only real SQL query)
```

### Implementation Strategy

**Refine SQL_QUERY_PATTERNS:**
```python
# File: theauditor/indexer/config.py

# BEFORE:
SQL_QUERY_PATTERNS = [
    r'execute\(',
    r'query\(',
    r'\.sql\(',
]

# AFTER:
SQL_QUERY_PATTERNS = [
    r'execute\([^)]*SELECT',  # Require SQL keyword
    r'query\([^)]*INSERT',
    r'query\([^)]*UPDATE',
    r'query\([^)]*DELETE',
    r'\.sql\(',
]

# ADD negative patterns:
EXCLUDE_FROM_SQL = [
    r'^jwt\.',
    r'crypto\.sign',
    r'crypto\.verify',
]
```

### Verification Tests

**Test 7.1: JWT not in sql_queries**
```bash
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM sql_queries WHERE command LIKE 'JWT%'"
# Expected: 0
```

### Estimated Effort: 2 hours

---

## BUG-008: Health Check System (P1)

### Implementation Strategy

```python
# NEW FILE: theauditor/utils/health_checks.py

class HealthCheckError(Exception):
    """Raised when health check fails."""
    pass

def check_index_health(db_path, file_count):
    """Validate indexing produced reasonable results."""
    conn = sqlite3.connect(db_path)

    symbol_count = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]

    if symbol_count == 0:
        raise HealthCheckError(
            f"0 symbols extracted from {file_count} files. Indexer likely failed."
        )

    if file_count > 0 and symbol_count < file_count:
        logger.warning(
            f"Only {symbol_count} symbols from {file_count} files. "
            f"Expected at least 1 symbol per file."
        )

def check_pattern_health(finding_count, loc):
    """Validate pattern detection produced reasonable results."""
    if finding_count > 1_000_000:
        raise HealthCheckError(
            f"Pattern detection produced {finding_count} findings. "
            f"Likely false positive explosion."
        )

    if finding_count == 0 and loc > 10_000:
        logger.warning(
            f"0 pattern findings in {loc} LOC project. "
            f"Verify pattern detection ran correctly."
        )

def check_taint_health(result):
    """Validate taint analysis ran correctly."""
    if not result.get('success'):
        raise HealthCheckError(
            f"Taint analysis failed: {result.get('error')}"
        )

    if result.get('sources_found') == 0 and result.get('sinks_found') == 0:
        logger.warning(
            "Taint analysis found 0 sources and 0 sinks. "
            "This may indicate no user input, or analysis failure."
        )
```

### Estimated Effort: 4 hours

---

## BUG-011: Uniform Finding Distribution (P2)

**Note:** This is a symptom of BUG-003 (TOCTOU). Once BUG-003 is fixed, this should resolve automatically.

**Verification:** After fixing BUG-003, check finding distribution is no longer uniform.

### Estimated Effort: Included in BUG-003

---

## BUG-012: JSX Symbol Count Mismatch (P2)

### Current Understanding

**Severity:** LOW - Cosmetic documentation issue
**Impact:** Log claims 450 JSX symbols, database has 239

**Evidence:**
```
Log: "JSX 2nd pass: 450 symbols"
DB: SELECT COUNT(*) FROM symbols_jsx → 239
```

### Implementation Strategy

**Option A: Fix log count**
```python
# File: theauditor/indexer/orchestrator.py

# After JSX pass:
jsx_symbol_count = conn.execute("SELECT COUNT(*) FROM symbols_jsx").fetchone()[0]
logger.info(f"JSX 2nd pass: {jsx_symbol_count} symbols")  # Use actual count
```

**Option B: Document difference**
```python
# Add comment explaining count methodology
# "Log shows AST nodes processed, database shows symbols stored"
```

### Estimated Effort: 1 hour

---

## IMPLEMENTATION ORDER

### Week 1 - P0 Fixes (Critical Path)

**Day 1-2: BUG-002 (Missing Function) - 4.5 hours**
- Blocks: All Python project indexing
- Dependencies: None
- Priority: HIGHEST

**Day 3-5: BUG-003 (TOCTOU Fix) - 9 hours**
- Blocks: 3/6 projects unusable
- Dependencies: None
- Priority: HIGHEST

**Week 1 Total: 13.5 hours**

### Week 2 - P1 Fixes (Quality Improvements)

**Day 6: BUG-005 (Rule Metadata) - 3 hours**
**Day 6-7: BUG-008 (Health Checks) - 4 hours**
**Day 7: BUG-006 (Phase Status) - 3 hours**
**Day 8: BUG-007 (SQL Misclassification) - 2 hours**
**Day 8: BUG-012 (JSX Mismatch) - 1 hour**

**Week 2 Total: 13 hours**

**GRAND TOTAL: 26.5 hours (~1 week focused development)**

---

## SUCCESS CRITERIA

### P0 Success (Production Ready)
- ✅ TheAuditor self-analysis produces >10K symbols (not 0)
- ✅ All 6 projects complete indexing successfully
- ✅ PlantFlow produces <10K findings (not 904K)
- ✅ No Cartesian explosion false positives

### P1 Success (High Quality)
- ✅ All findings have rule names (not "unknown")
- ✅ Failed phases show "[FAILED]" not "[OK]"
- ✅ SQL queries don't include JWT operations
- ✅ Health checks catch anomalous results

---

## VALIDATION MATRIX

| Bug | Test Command | Success Criteria | Time |
|-----|-------------|------------------|------|
| 002 | `aud index` on TheAuditor | symbols > 10,000 | 1 min |
| 003 | `aud detect-patterns` PlantFlow | findings < 10,000 | 5 min |
| 005 | Query distinct rules | > 10 unique rules | 1 min |
| 006 | Simulate taint failure | Shows "[FAILED]" | 2 min |
| 007 | Query sql_queries | No JWT entries | 1 min |
| 008 | Index with 0 symbols | Health check raises error | 2 min |
| 012 | Check log vs DB | Counts match OR documented | 1 min |

**Total Validation Time: 13 minutes**

---

## CONFIRMATION OF UNDERSTANDING

**Objective:** Focused pre-implementation plan for architect-approved bugs

**Scope:** 8 bugs (excluded taint and cache per architect directive)

**Corrections Applied:**
- ✅ Missing function affects ALL Python projects (not just self-scan)
- ✅ TOCTOU algorithm fixed (not disabled)
- ✅ No taint work
- ✅ No cache work

**Deliverable:** This document with detailed plans for bugs 2,3,5,6,7,8,11,12

**Status:** ✅ COMPLETE - Awaiting Architect Approval

**Total Effort:** 26.5 hours (~1 week)

**Confidence Level:** High - Plans based on actual code inspection

---

**End of Focused Pre-Implementation Plan**
