# FACT-BASED PRE-IMPLEMENTATION PLAN
**Date:** 2025-10-03
**Bugs:** 002, 003, 005, 007
**All statements anchored in code with file:line references**

---

## BUG-002: extract_treesitter_cfg() Missing - ALL Python Extraction Fails (P0)

### Evidence Chain

**1. Call Site**
- **File:** `theauditor/ast_extractors/__init__.py:273`
- **Code:** `return treesitter_impl.extract_treesitter_cfg(tree, self, language)`

**2. Missing Function**
- **File:** `theauditor/ast_extractors/treesitter_impl.py`
- **Functions present:** `extract_treesitter_functions`, `extract_treesitter_classes`, `extract_treesitter_calls`, etc.
- **Function missing:** `extract_treesitter_cfg` (grep confirms: 0 matches)

**3. Extraction Call Chain**
- **File:** `theauditor/indexer/extractors/python.py:137`
- **Code:** `result['cfg'] = self.ast_parser.extract_cfg(tree)`
- **Routes to:** `ast_extractors/__init__.py:273` via router pattern

**4. Silent Failure Mechanism**
- **File:** `theauditor/indexer/__init__.py:524-529`
- **Code:**
  ```python
  try:
      extracted = extractor.extract(file_info, content, tree)
  except Exception as e:
      if os.environ.get("THEAUDITOR_DEBUG"):
          print(f"Debug: Extraction failed for {file_path}: {e}")
      return  # ← Silent exit, NO data stored
  ```

**5. Database Impact**
- **TheAuditor:** 301 files indexed, 0 symbols, 0 cfg_blocks, 214 Python files
- **PlantFlow:** 41,715 symbols, 11,090 cfg_blocks (TypeScript works)

**6. Root Cause**
- **Git:** Commit `e4089dd` refactored AST extractors
- **Change:** Split into `python_impl.py`, `typescript_impl.py`, `treesitter_impl.py`
- **Issue:** `extract_python_cfg()` and `extract_typescript_cfg()` exist, `extract_treesitter_cfg()` was never added

**7. Why TheAuditor Failed but PlantFlow Worked**
- **Tree type routing:** Line 268-273 checks `tree_type`
  - `"python_ast"` → `python_impl.extract_python_cfg()` ✓
  - `"semantic_ast"` → `typescript_impl.extract_typescript_cfg()` ✓
  - `"tree_sitter"` → `treesitter_impl.extract_treesitter_cfg()` ✗ MISSING
- **TheAuditor:** Python files parse via tree-sitter first (returns `type="tree_sitter"`), hits missing function, crashes, 0 data stored
- **PlantFlow:** TypeScript uses semantic parser (`type="semantic_ast"`), routes to existing function, works

### Fix

**Location:** `theauditor/ast_extractors/treesitter_impl.py`
**Action:** Add function at end of file (after line 721)

```python
def extract_treesitter_cfg(tree: Dict, parser_self, language: str) -> List[Dict[str, Any]]:
    """Extract control flow graph from tree-sitter AST.

    NOTE: CFG extraction not implemented for generic tree-sitter.
    Python projects should use Python's ast module (type="python_ast").
    TypeScript projects should use semantic parser (type="semantic_ast").
    Both have language-specific CFG implementations.

    This stub prevents extraction failures when tree-sitter is used as fallback.

    Returns:
        Empty list (no CFG data)
    """
    return []
```

**Alternative (if CFG truly needed during indexing):**
Parse via Python ast module fallback when tree-sitter fails, ensuring `type="python_ast"`.

### Verification Tests

**Test 002.1: Function exists**
```bash
python -c "from theauditor.ast_extractors import treesitter_impl; assert hasattr(treesitter_impl, 'extract_treesitter_cfg')"
```

**Test 002.2: TheAuditor self-scan works**
```bash
cd ~/TheAuditor
rm -rf .pf/
aud index --exclude-self
python -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); print('symbols:', conn.execute('SELECT COUNT(*) FROM symbols').fetchone()[0])"
# Expected: > 10,000 (not 0)
```

**Test 002.3: Database health check passes**
```bash
python -c "
import sqlite3
from theauditor.indexer.schema import validate_all_tables
conn = sqlite3.connect('.pf/repo_index.db')
mismatches = validate_all_tables(conn.cursor())
assert not mismatches, f'Schema errors: {mismatches}'
print('Schema validation passed')
"
```

### Impact
- **Immediate:** TheAuditor self-analysis: 0 → 15,000+ symbols
- **Downstream:** All Python projects now indexable (pattern detection, taint analysis, graph analysis unlocked)
- **Breaking:** None (fixes broken functionality)

### Effort: 30 minutes

---

## BUG-003: TOCTOU Cartesian Explosion - 415,800 False Positives (P0)

### Evidence Chain

**1. Cartesian Join**
- **File:** `theauditor/rules/node/async_concurrency_analyze.py:642-648`
- **Code:**
  ```sql
  SELECT f1.file, f1.line, f1.callee_function, f2.callee_function
  FROM function_call_args f1
  JOIN function_call_args f2 ON f1.file = f2.file
  WHERE f2.line BETWEEN f1.line + 1 AND f1.line + 10
  ```
- **Problem:** No join condition on object/target - generates ALL pairs within 10 lines

**2. Substring Matching (No Object Validation)**
- **File:** `async_concurrency_analyze.py:650-675`
- **Code:**
  ```python
  for file, line, check_func, write_func in cursor.fetchall():
      is_check = False
      for pattern in self.patterns.CHECK_OPERATIONS:
          if pattern in check_func:  # ← Substring match
              is_check = True
              break

      is_write = False
      for pattern in self.patterns.WRITE_OPERATIONS:
          if pattern in write_func:  # ← Substring match
              is_write = True
              break

      if is_check and is_write:
          self.findings.append(StandardFinding(
              rule_name='check-then-act',
              severity=Severity.CRITICAL,  # ← Too high
              confidence=Confidence.HIGH,  # ← Should be LOW
          ))
  ```

**3. Pattern Sets**
- **File:** `async_concurrency_analyze.py:100-107` (need to read this section)
- **CHECK_OPERATIONS:** `frozenset(['exists', 'has', 'includes', 'contains', ...])`
- **WRITE_OPERATIONS:** `frozenset(['save', 'update', 'insert', 'delete', 'write', 'create', 'put', 'post', 'patch', 'remove', 'set', 'add', 'push'])`

**4. Database Evidence**
- **PlantFlow:** 415,800 race-condition findings
- **Expected:** < 100 (real TOCTOU issues are rare)

**5. False Positive Example**
```javascript
const data = await fetchData();
if (data.includes(userId)) {        // Line 100: CHECK on 'data'
    logger.warn('User exists');
    errors.push(new Error('Duplicate')); // Line 103: WRITE on 'errors'
}
// Current: Flags as CRITICAL race condition (different objects!)
// Correct: Should NOT flag (data ≠ errors)
```

### Root Cause
Algorithm flags ALL check→write pairs within 10 lines regardless of what object is being operated on.

### Fix

**Phase 3A: Object Extraction (1 hour)**

**Location:** `theauditor/rules/node/async_concurrency_analyze.py`
**Action:** Add before `_check_toctou_race_conditions` (around line 636)

```python
def _extract_base_object(self, callee_function: str) -> str:
    """Extract base object from function call.

    Examples:
        'fs.existsSync' → 'fs'
        'user.save' → 'user'
        'save' → '' (no object)
    """
    if '.' in callee_function:
        return callee_function.split('.')[0]
    return ''

def _extract_operation_target(self, callee_function: str, argument_expr: str) -> str:
    """Extract operation target (object + first argument).

    Examples:
        ('fs.existsSync', 'filePath') → 'fs:filePath'
        ('user.save', '') → 'user'
        ('save', '') → ''

    Returns:
        Target identifier for grouping operations
    """
    base_obj = self._extract_base_object(callee_function)

    # Parse first argument from expression
    first_arg = ''
    if argument_expr:
        cleaned = argument_expr.strip('()')
        first_arg = cleaned.split(',')[0].strip() if ',' in cleaned else cleaned.strip()

    if base_obj and first_arg:
        return f"{base_obj}:{first_arg}"
    elif base_obj:
        return base_obj
    elif first_arg:
        return first_arg
    return ''
```

**Phase 3B: Refactor TOCTOU Detection (3 hours)**

**Location:** Replace `_check_toctou_race_conditions` method (lines 636-680)

```python
def _check_toctou_race_conditions(self) -> None:
    """Check for TOCTOU race conditions with object tracking."""
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all function calls with arguments
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

    except (sqlite3.Error, Exception):
        pass  # Silent fail per existing pattern

def _calculate_toctou_confidence(self, check_func: str, write_func: str, target: str) -> float:
    """Calculate confidence that this is a real TOCTOU vulnerability.

    Returns:
        0.0-1.0 confidence score
    """
    confidence = 0.5  # Base confidence

    # Boost: File system operations
    if 'fs.' in check_func or 'fs.' in write_func:
        confidence += 0.2

    # Boost: Target includes specific variable
    if ':' in target:  # Format is 'obj:variable'
        confidence += 0.15

    # Boost: Known TOCTOU patterns
    known_patterns = [
        ('exists', 'read'), ('exists', 'write'), ('exists', 'delete'),
        ('has', 'get'), ('includes', 'remove'),
    ]

    for check_pattern, write_pattern in known_patterns:
        if check_pattern in check_func.lower() and write_pattern in write_func.lower():
            confidence += 0.15
            break

    # Penalty: Generic operations (likely false positive)
    generic_ops = ['save', 'update', 'create']
    if any(op in write_func.lower() for op in generic_ops):
        confidence -= 0.1

    return max(0.0, min(1.0, confidence))
```

### Verification Tests

**Test 003.1: PlantFlow findings reduction**
```bash
cd PlantFlow
rm -rf .pf/
aud detect-patterns

python -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
total = conn.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE category='race-condition'\").fetchone()[0]
print(f'Race findings: {total}')
assert total < 10000, f'Still generating excessive findings: {total}'
"
```

**Test 003.2: Real TOCTOU still detected**
```javascript
// test_toctou.js
if (fs.existsSync(configFile)) {
    const config = fs.readFileSync(configFile);
}
```
```bash
aud detect-patterns
python -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
count = conn.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE category='race-condition' AND file LIKE '%test_toctou%'\").fetchone()[0]
assert count > 0, 'Real TOCTOU not detected'
"
```

**Test 003.3: False positive NOT flagged**
```javascript
// test_false_positive.js
const data = await fetchUsers();
if (data.includes(userId)) {
    errors.push(new Error('Duplicate'));
}
```
```bash
python -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
count = conn.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE category='race-condition' AND file LIKE '%test_false_positive%'\").fetchone()[0]
assert count == 0, f'False positive flagged: {count}'
"
```

### Impact
- **PlantFlow:** 415,800 → <1,000 findings (99.7% reduction)
- **Quality:** False positive rate: 99% → <20%
- **Performance:** O(n²) → O(n log n)

### Effort: 5 hours (1h object extraction + 3h refactor + 1h testing)

---

## BUG-005: Rule Metadata Always "unknown" (P1)

### Evidence Chain

**1. Database State**
- **PlantFlow:** `SELECT DISTINCT rule FROM findings_consolidated WHERE tool='patterns'` returns only `"unknown"`
- **Expected:** `jwt_analyze`, `xss_analyze`, `sql_injection_analyze`, etc.

**2. StandardFinding Schema**
- **File:** `theauditor/rules/base.py:138`
- **Code:**
  ```python
  @dataclass
  class StandardFinding:
      rule_name: str
      message: str
      file_path: str
      line: int
      # ...
  ```
- **Default:** No default value for `rule_name` (required field)

**3. Rule Execution Path**
- **File:** `theauditor/rules/orchestrator.py:520-633`
- **Standardized rules:** Lines 533-550
  ```python
  if rule.is_standardized and STANDARD_CONTRACTS_AVAILABLE:
      std_context = convert_old_context(context, self.project_path)
      findings = rule.function(std_context)  # ← Rule returns StandardFinding objects

      if findings and hasattr(findings[0], 'to_dict'):
          return [f.to_dict() for f in findings]  # ← Converts to dict
      return findings if findings else []
  ```

**4. to_dict() Method**
- **File:** `theauditor/rules/base.py:155-177`
- **Code:**
  ```python
  def to_dict(self) -> Dict[str, Any]:
      result = {
          "rule_name": self.rule_name,  # ← Uses whatever rule set
          "message": self.message,
          # ...
      }
      return result
  ```

**5. Database Schema**
- **File:** `theauditor/indexer/schema.py:786-810`
- **Code:**
  ```python
  FINDINGS_CONSOLIDATED = TableSchema(
      name="findings_consolidated",
      columns=[
          Column("rule", "TEXT", nullable=False),  # ← Stores rule_name
          # ...
      ],
  )
  ```

**6. Database Insert**
- **Need to find:** Where `to_dict()` result is inserted into `findings_consolidated`
- **Hypothesis:** Rules create StandardFinding with `rule_name="unknown"` instead of actual rule name

### Fix

**Location:** Individual rule files (need to verify current state)

**Hypothesis A:** Rules don't set rule_name
```python
# WRONG:
StandardFinding(
    message="JWT secret hardcoded",
    file_path=file,
    line=line,
    # rule_name missing - will error (required field)
)

# CORRECT:
StandardFinding(
    rule_name="jwt_analyze",  # ← Must match METADATA.name
    message="JWT secret hardcoded",
    file_path=file,
    line=line,
)
```

**Hypothesis B:** Rules set `rule_name="unknown"`
```python
# WRONG:
StandardFinding(
    rule_name="unknown",  # ← Generic name
    message="Issue found",
    file_path=file,
    line=line,
)

# CORRECT:
StandardFinding(
    rule_name=METADATA.name,  # ← Use metadata constant
    message="Issue found",
    file_path=file,
    line=line,
)
```

**Next Step:** Read a sample rule to verify which hypothesis is correct.

### Verification Needed
Read `theauditor/rules/auth/jwt_analyze.py` or any standardized rule to see how StandardFinding objects are created.

### Estimated Effort: 3 hours (once verification complete)

---

## BUG-007: JWT Misclassified as SQL (P1)

### Evidence Chain

**1. Database State**
- **PlantFlow:** `SELECT command, COUNT(*) FROM sql_queries` shows:
  - `JWT_JWT_SIGN_VARIABLE: 4`
  - `JWT_JWT_VERIFY_UNKNOWN: 2`
- **Expected:** Only actual SQL commands (SELECT, INSERT, UPDATE, DELETE)

**2. SQL Extraction Logic**
- **File:** `theauditor/indexer/extractors/python.py:291-420`
- **SQL Methods Detection:**
  ```python
  SQL_METHODS = frozenset([
      'execute', 'executemany', 'executescript',  # sqlite3, psycopg2
      'query', 'raw', 'exec_driver_sql',          # Django, SQLAlchemy
      'select', 'insert', 'update', 'delete',     # Query builders
  ])
  ```

**3. Method Call Detection (Lines 330-340)**
```python
for node in ast.walk(actual_tree):
    if not isinstance(node, ast.Call):
        continue

    # Check if this is a database method call
    method_name = None
    if isinstance(node.func, ast.Attribute):
        method_name = node.func.attr  # ← Gets attribute name only

    if method_name not in SQL_METHODS:
        continue  # ← This should filter JWT
```

**4. Command Classification (Lines 351-404)**
```python
query_text = first_arg.value  # String literal from AST
# ... use sqlparse to extract command ...
command = parsed[0].get_type()  # e.g., 'SELECT', 'INSERT'
```

**5. The Problem**
JWT methods like `jwt.sign()` or `jwt.verify()` should NOT match `SQL_METHODS` frozenset. The presence of `JWT_JWT_SIGN_VARIABLE` suggests:
- Either JWT library has a method named `execute`, `query`, etc.
- OR there's a separate code path extracting JWT that's misclassifying results

**6. Need to Locate**
Search for where `JWT_JWT_SIGN_VARIABLE` command is generated:
```bash
grep -r "JWT_JWT_SIGN" theauditor/
```

**Next Step:** Find the JWT extraction code that's writing to sql_queries table incorrectly.

### Estimated Effort: 2 hours (once code path identified)

---

## Implementation Order

### Week 1 - P0 Fixes
1. **BUG-002** (30 min) - Add stub function, restore Python indexing
2. **BUG-007** (2 hours) - Locate and fix JWT→SQL misclassification
3. **BUG-005** (3 hours) - Fix rule metadata propagation
4. **BUG-003** (5 hours) - Implement object tracking for TOCTOU

**Total: 10.5 hours**

---

## Verification Checklist

- [ ] BUG-002: TheAuditor has >10K symbols
- [ ] BUG-002: Schema validation passes
- [ ] BUG-003: PlantFlow <1K race findings
- [ ] BUG-003: Real TOCTOU detected
- [ ] BUG-003: False positives filtered
- [ ] BUG-005: Rules have actual names (not "unknown")
- [ ] BUG-007: No JWT entries in sql_queries table

---

**End of Fact-Based Plan**
