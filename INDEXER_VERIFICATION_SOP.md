# INDEXER SYSTEM VERIFICATION SOP

**Version:** 1.0
**Last Updated:** 2025-10-03
**Purpose:** Atomic verification protocol for ANY file in the TheAuditor indexer system

---

## HOW TO USE THIS SOP

1. Identify the file type (Database, Extractor, Schema, Storage, Config, Core)
2. Run ALL applicable checklists for that file type
3. Verify ALL upstream and downstream contracts
4. Report ALL violations found

---

## SECTION 1: DATABASE METHODS (`database.py`)

### For EVERY `add_*()` method:

#### ✅ **Checklist A: Method Signature**

```
□ Count parameters in method signature
□ Document parameter names and types
□ Check for Optional[] types (should match nullable columns)
□ Verify default values are appropriate
```

**Example:**
```python
def add_ref(self, src: str, kind: str, value: str, line: Optional[int] = None):
    # 4 parameters: src, kind, value, line (optional)
```

---

#### ✅ **Checklist B: Batch Append**

```
□ Find the self.*_batch.append() line in the method
□ Count tuple elements in append()
□ Verify tuple element count MATCHES parameter count
□ Check tuple element order matches parameter order
□ Verify JSON encoding for List/Dict types
```

**Example:**
```python
def add_ref(self, src: str, kind: str, value: str, line: Optional[int] = None):
    self.refs_batch.append((src, kind, value, line))  # 4 elements ✓
```

**VIOLATION:** If tuple has 3 elements but method has 4 parameters → MISMATCH

---

#### ✅ **Checklist C: CREATE TABLE Schema**

```
□ Find CREATE TABLE statement for this batch's table
□ Count columns in CREATE TABLE
□ Verify column count MATCHES tuple element count
□ Verify column names match parameter names
□ Verify column order matches tuple order
□ Check column types match parameter types:
  - str → TEXT
  - int → INTEGER
  - bool → BOOLEAN
  - List/Dict → TEXT (should be JSON encoded)
□ Verify NOT NULL constraints match non-Optional params
□ Check FOREIGN KEY constraints reference existing tables
□ Verify CHECK constraints don't reject valid data
```

**Example:**
```sql
CREATE TABLE IF NOT EXISTS refs(
    src TEXT NOT NULL,        -- param 1: src (str, not optional)
    kind TEXT NOT NULL,       -- param 2: kind (str, not optional)
    value TEXT NOT NULL,      -- param 3: value (str, not optional)
    line INTEGER,             -- param 4: line (Optional[int])
    FOREIGN KEY(src) REFERENCES files(path)
)
-- 4 columns ✓ matches 4 parameters
```

**VIOLATION:** If CREATE TABLE has 3 columns but method has 4 parameters → MISMATCH

---

#### ✅ **Checklist D: INSERT Statement in flush_batch()**

```
□ Find the cursor.executemany() for this batch in flush_batch()
□ Count column names in INSERT INTO (...)
□ Count ? placeholders in VALUES (...)
□ Verify column count = placeholder count = tuple element count
□ Verify column order matches tuple order
□ Check table name matches batch name
```

**Example:**
```python
cursor.executemany(
    "INSERT INTO refs (src, kind, value, line) VALUES (?, ?, ?, ?)",
    #                   4 columns          4 placeholders ✓
    self.refs_batch
)
```

**VIOLATION:** If INSERT has 3 columns but batch has 4-element tuples → MISMATCH

---

#### ✅ **Checklist E: schema.py Definition**

```
□ Open theauditor/indexer/schema.py
□ Find table name in TABLES dict
□ Verify table EXISTS in TABLES
□ Count columns in schema definition
□ Verify column names EXACTLY match CREATE TABLE
□ Verify column order matches CREATE TABLE
□ Check types match (use TYPE_MAPPINGS if needed)
□ Note: Foreign keys intentionally omitted (design pattern)
```

**Example:**
```python
TABLES = {
    'refs': [
        'src',      # Column 1
        'kind',     # Column 2
        'value',    # Column 3
        'line'      # Column 4
    ],
    # 4 columns ✓ matches CREATE TABLE
}
```

**VIOLATION:** If table missing from TABLES → MISMATCH

---

#### ✅ **Checklist F: Call Sites (Upstream)**

```
□ Search codebase for all calls to this method
□ For EACH call site:
  □ Count arguments passed
  □ Verify argument count MATCHES parameter count
  □ Check argument order matches parameter order
  □ Verify argument types match parameter types
  □ Check if keyword arguments are used (safer)
```

**Example:**
```python
# Call site: __init__.py:611
self.db_manager.add_ref(file_path, kind, resolved, line)
# 4 arguments ✓ matches 4 parameters
```

**VIOLATION:** If call passes 4 arguments but method accepts 3 → MISMATCH

---

### ✅ **Checklist G: CHECK Constraints**

```
□ Find all CHECK constraints in CREATE TABLE
□ For each CHECK:
  □ Find extractor code that populates this field
  □ Verify extractor NEVER returns values that violate CHECK
  □ Check for .get() with empty string defaults
  □ Check for UNKNOWN values
□ If violation possible, add validation before add_* call
```

**Example:**
```sql
CREATE TABLE function_call_args(
    callee_function TEXT NOT NULL CHECK(callee_function != ''),
    -- CHECK constraint rejects empty strings
)
```

**Extractor code:**
```python
callee = call.get('callee_function', '')  # ❌ Returns '' if missing
```

**VIOLATION:** Extractor can return empty string → violates CHECK → INSERT fails

**Fix:** Add validation:
```python
callee = call.get('callee_function', '')
if callee.strip():  # Only add if non-empty
    self.db_manager.add_function_call_arg(...)
```

---

## SECTION 2: EXTRACTORS (`extractors/*.py`)

### For EVERY extractor class:

#### ✅ **Checklist H: Extract Method Return Structure**

```
□ Find the extract() method
□ Document ALL keys in result dict
□ For EACH key:
  □ Document data structure (List[tuple], List[dict], etc.)
  □ If List[tuple]: count tuple elements
  □ If List[dict]: list all dict keys
  □ Document field types and meanings
```

**Example:**
```python
result = {
    'imports': [],      # List[tuple] - (kind, module, line)
    'routes': [],       # List[dict] - {method, pattern, path, ...}
    'symbols': [],      # List[dict] - {name, type, line, col}
}
```

---

#### ✅ **Checklist I: Storage Contract (Downstream)**

```
□ Open theauditor/indexer/__init__.py
□ Find _store_extracted_data() method
□ For EACH key your extractor returns:
  □ Verify key is processed in _store_extracted_data()
  □ Check expected data structure matches what you return
  □ Verify field names match exactly
  □ Check iteration logic (for loop expecting list)
  □ Find which db_manager.add_*() method is called
  □ Verify arguments passed match your data structure
```

**Example:**
```python
# Extractor returns:
result['imports'] = [(kind, module, line), ...]

# Storage expects (__init__.py:595-611):
if 'imports' in extracted:
    for import_tuple in extracted['imports']:  # ✓ Expects list
        if len(import_tuple) == 3:             # ✓ Expects 3-tuple
            kind, value, line = import_tuple
        # Calls add_ref() - verify signature matches
```

**VIOLATION:** If extractor returns 4-tuple but storage unpacks 3 → MISMATCH

---

#### ✅ **Checklist J: Tree Type Handling**

```
□ Find all tree.get() or tree access in extractor
□ Check if tree type is validated before use
□ Verify isinstance() checks match actual tree types:
  - Tree-sitter: tree_sitter.Node or dict with type='tree_sitter'
  - Python AST: ast.Module and dict with type='python_ast'
  - Semantic AST: dict with type='semantic_ast'
□ Add defensive checks if missing
□ Document expected tree format in docstring
```

**Example - WRONG:**
```python
if not isinstance(tree.get("tree"), ast.Module):  # ❌ Assumes Python AST
    return []
```

**Example - CORRECT:**
```python
tree_type = tree.get("type") if isinstance(tree, dict) else None
if tree_type != "python_ast":
    return []  # ✓ Checks type first
actual_tree = tree.get("tree")
if not isinstance(actual_tree, ast.Module):
    return []
```

**VIOLATION:** If extractor assumes tree type without checking → MISMATCH

---

#### ✅ **Checklist K: Database-First Extractors**

```
□ Check if extractor uses self.db_manager directly
□ If YES:
  □ Verify db_manager is injected in __init__.py orchestrator
  □ Find injection code (lines ~66-83 in __init__.py)
  □ Verify extractor is in registry OR special extractor list
  □ Check if source code inspection is used (fragile pattern)
  □ Add validation that db_manager exists before use
```

**Example:**
```python
# In extractor:
if hasattr(self, 'db_manager') and self.db_manager:
    self.db_manager.add_prisma_model(...)
else:
    # Fallback or error
```

**VIOLATION:** If extractor uses self.db_manager but it's never injected → AttributeError

---

#### ✅ **Checklist L: Configuration Constants**

```
□ Find all pattern matching in extractor
□ Check if patterns are hardcoded or use constants from config.py
□ For EACH hardcoded pattern:
  □ Search config.py for equivalent constant
  □ If exists: replace with import
  □ If missing: add to config.py
□ Check for hardcoded skip directories
□ Check for hardcoded file extensions
□ Check for hardcoded regex patterns
```

**Example - WRONG:**
```python
dockerfile_patterns = ['dockerfile', 'dockerfile.dev', ...]  # ❌ Hardcoded
```

**Example - CORRECT:**
```python
from ..config import DOCKERFILE_PATTERNS
# Use DOCKERFILE_PATTERNS
```

**VIOLATION:** If pattern duplicates config.py constant → MISMATCH

---

## SECTION 3: SCHEMA DEFINITIONS (`schema.py`)

#### ✅ **Checklist M: Table Completeness**

```
□ Open database.py and list ALL CREATE TABLE statements
□ Open schema.py and list ALL tables in TABLES dict
□ Cross-reference:
  □ Every table in database.py MUST be in schema.py
  □ Column count must match
  □ Column names must match EXACTLY (order matters)
  □ Column order must match
```

**VIOLATION:** If table exists in database.py but not schema.py → MISMATCH

---

#### ✅ **Checklist N: build_query() Compatibility**

```
□ For each table in schema.py:
  □ Test: build_query('table_name', ['col1', 'col2'])
  □ Verify all column names are valid
  □ Check return query is syntactically correct
  □ Verify WHERE clause construction works
```

---

## SECTION 4: STORAGE LAYER (`__init__.py`)

#### ✅ **Checklist O: _store_extracted_data() Coverage**

```
□ List ALL keys that extractors can return
□ For EACH key:
  □ Find if 'key' in extracted: block in _store_extracted_data()
  □ If missing → Dead code or unused feature
  □ Verify iteration logic matches extractor return type
  □ Check field access matches extractor dict keys
  □ Verify db_manager method called matches data
```

**Example:**
```python
# Extractor returns:
result['jwt_patterns'] = [{
    'pattern_type': 'sign',
    'line': 15,
    'pattern_text': '...',
    'secret_source': 'env'
}]

# Storage must have:
if 'jwt_patterns' in extracted:
    for pattern in extracted['jwt_patterns']:  # ✓ Iterates list
        self.db_manager.add_jwt_pattern(
            file_path,
            pattern['line'],        # ✓ Accesses dict key
            pattern['pattern_type'],
            pattern['pattern_text'],
            pattern['secret_source']
        )
```

**VIOLATION:** If extractor returns key but storage doesn't process it → Data loss

---

#### ✅ **Checklist P: Call Argument Validation**

```
□ For EACH db_manager.add_*() call in _store_extracted_data():
  □ Count arguments passed
  □ Find method signature in database.py
  □ Verify argument count matches
  □ Check argument types match parameter types
  □ Verify dict.get() defaults are appropriate
  □ Check for missing None checks
```

**Example:**
```python
# Call site:
self.db_manager.add_endpoint(
    file_path=file_path,               # ✓ Uses keyword args (safer)
    method=route.get('method', 'GET'), # ✓ Has default
    pattern=route.get('pattern', ''),
    # ... verify all params covered
)
```

**VIOLATION:** If call uses wrong argument order → Data corruption

---

## SECTION 5: CONFIGURATION (`config.py`)

#### ✅ **Checklist Q: Constant Definition**

```
□ List ALL constants defined
□ Verify type annotations exist
□ Check if configurable via environment variable
□ Document default values
□ Verify frozenset is used for O(1) lookups (not list)
```

---

#### ✅ **Checklist R: Constant Usage Audit**

```
□ For EACH constant:
  □ Search entire indexer package for imports
  □ Search for hardcoded duplicates of the value
  □ Find all usages
  □ Verify no hardcoded duplicates exist
```

**Example:**
```bash
# Search for hardcoded 200 (should use DEFAULT_BATCH_SIZE)
grep -r "batch_size = 200" theauditor/indexer/
```

**VIOLATION:** If hardcoded value duplicates constant → MISMATCH

---

## SECTION 6: CORE INFRASTRUCTURE (`core.py`)

#### ✅ **Checklist S: FileWalker Skip Logic**

```
□ Find _should_skip() method
□ Verify SKIP_DIRS import from config
□ Check no hardcoded skip patterns
□ Verify gitignore integration works
□ Test monorepo detection logic
```

---

## SECTION 7: TYPE SAFETY

#### ✅ **Checklist T: Type Annotations**

```
□ For EVERY function with parameters:
  □ Verify type hints exist for all params
  □ Check return type annotation exists
  □ Verify Optional[] used for nullable values
  □ Check List[X] / Dict[X, Y] for collections
□ Run mypy on the file:
  mypy theauditor/indexer/[file].py --strict
□ Fix all type errors
```

---

## ATOMIC FILE VERIFICATION PROTOCOL

### To verify ANY single file:

```
1. Identify file type (Database, Extractor, Schema, Storage, Config, Core)

2. Run applicable checklists:
   - database.py → A, B, C, D, E, F, G, T
   - extractors/*.py → H, I, J, K, L, T
   - schema.py → M, N
   - __init__.py → O, P, T
   - config.py → Q, R
   - core.py → S, T

3. For EACH checklist item that applies:
   - Mark ✓ if passes
   - Mark ❌ if fails
   - Document violation with line number

4. Create violation report:
   - File: [filename]
   - Violations: [count]
   - Critical (breaks functionality): [list]
   - High (data loss): [list]
   - Medium (maintainability): [list]
   - Low (type safety): [list]

5. For each violation:
   - Upstream impact: [files affected]
   - Downstream impact: [files affected]
   - Fix required: [specific change]
```

---

## CROSS-FILE VALIDATION

After verifying individual files, validate contracts:

```
□ Database methods ↔ Call sites
  - Count every add_*() method
  - Find all call sites
  - Verify signatures match

□ Database methods ↔ Schema definitions
  - Count every CREATE TABLE
  - Verify schema.py has entry
  - Check column alignment

□ Extractors ↔ Storage
  - List all extractor return keys
  - Verify _store_extracted_data() handles all
  - Check field name alignment

□ Config constants ↔ Usage
  - List all constants
  - Search for hardcoded duplicates
  - Verify all imports are correct

□ Batch tuples ↔ INSERT statements
  - Count tuple elements
  - Count INSERT placeholders
  - Verify exact match for ALL batches
```

---

## EXAMPLE VERIFICATION SESSION

**File to verify:** `theauditor/indexer/database.py` → `add_ref()` method

```
□ Checklist A: Method Signature
  ✓ Parameters: src (str), kind (str), value (str)
  ❌ Missing: line parameter (call site passes 4 args)

□ Checklist B: Batch Append
  ✓ Line 1047: self.refs_batch.append((src, kind, value))
  ❌ Tuple has 3 elements, call site passes 4

□ Checklist C: CREATE TABLE
  ✓ Table exists at line 208
  ❌ Has 3 columns (src, kind, value), missing line column

□ Checklist D: INSERT Statement
  ✓ Found at line 1504
  ❌ INSERT has 3 columns, should have 4

□ Checklist E: schema.py
  ✓ Table exists in TABLES
  ❌ Has 3 columns, should have 4

□ Checklist F: Call Sites
  ✓ Found call at __init__.py:611
  ❌ Passes 4 arguments (file_path, kind, resolved, line)
  ❌ Method only accepts 3 parameters

VIOLATIONS: 6 critical mismatches
- Add line parameter to signature
- Add line to tuple append
- Add line column to CREATE TABLE
- Add line to INSERT statement
- Add line to schema.py definition
- All must be done atomically
```

---

## FINAL VERIFICATION COMMAND

After fixes, run this command set:

```bash
# 1. Syntax check
python -m py_compile theauditor/indexer/*.py
python -m py_compile theauditor/indexer/extractors/*.py

# 2. Type check
mypy theauditor/indexer/ --strict

# 3. Schema validation
python -c "from theauditor.indexer.schema import validate_all_tables; import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); print(validate_all_tables(conn.cursor()))"

# 4. Integration test
pytest tests/test_database_integration.py -v

# 5. Constant audit
grep -r "200" theauditor/indexer/*.py | grep -v "DEFAULT_BATCH_SIZE"
grep -r "\.git/" theauditor/indexer/*.py | grep -v "SKIP_DIRS"
```

---

## SOP USAGE BY FUTURE AI

**Prompt for future AI:**

```
Read theauditor/INDEXER_VERIFICATION_SOP.md

Verify file: [filename]

Follow ALL applicable checklists.
Report ALL violations with line numbers.
Include upstream/downstream impact.
Provide specific fixes for each violation.
```

---

## QUICK REFERENCE: COMMON VIOLATIONS

### Top 10 Most Common Mismatches

1. **add_*() parameter count ≠ call site argument count**
   - Check: Checklist F
   - Files: database.py ↔ __init__.py

2. **Batch tuple elements ≠ INSERT placeholders**
   - Check: Checklists B, D
   - Files: database.py

3. **CREATE TABLE columns ≠ schema.py columns**
   - Check: Checklists C, E
   - Files: database.py ↔ schema.py

4. **Tree type not validated before use**
   - Check: Checklist J
   - Files: extractors/*.py

5. **CHECK constraints reject valid data**
   - Check: Checklist G
   - Files: database.py ↔ extractors/*.py

6. **Hardcoded patterns duplicate config.py**
   - Check: Checklist L
   - Files: extractors/*.py ↔ config.py

7. **Extractor returns key not processed in storage**
   - Check: Checklist O
   - Files: extractors/*.py ↔ __init__.py

8. **Path objects passed to str parameters**
   - Check: Checklist T
   - Files: All

9. **Table missing from schema.py TABLES dict**
   - Check: Checklist M
   - Files: schema.py

10. **db_manager not injected into database-first extractor**
    - Check: Checklist K
    - Files: __init__.py ↔ extractors/*.py

---

## ATOMIC FIX PROTOCOL

When fixing a violation, ALL related locations must be updated atomically:

**Example: Adding `line` parameter to `add_ref()`**

```
1. database.py:1045 - Add line: Optional[int] = None parameter
2. database.py:1047 - Update append to include line
3. database.py:208-215 - Add line INTEGER column to CREATE TABLE
4. database.py:1504 - Add line to INSERT column list and placeholders
5. schema.py - Add 'line' to refs table column list
6. Verify __init__.py:611 call site matches new signature
7. Run all verification commands
8. Commit atomically with message describing full contract change
```

**NEVER fix only one location** - this creates worse mismatches.

---

## VERSION HISTORY

- **1.0** (2025-10-03): Initial SOP based on comprehensive indexer audit
  - 30 mismatches identified across 10 files
  - 20 checklists covering all verification scenarios
  - Atomic verification protocol established
