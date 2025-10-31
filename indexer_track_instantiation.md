# Database Schema Gap: Class Instantiation Tracking

**Date**: 2025-11-01
**Reporter**: Dead Code Detection System
**Severity**: Medium (blocks class-level dead code detection)
**Component**: Indexer - Database Schema
**Assigned To**: Database Layer 3 Person

---

## TL;DR

Class instantiation (e.g., `parser = ASTParser()`) is NOT tracked in `function_call_args` table, making it impossible to detect dead classes. We need either:
1. Add class instantiations to `function_call_args.callee_function`, OR
2. Create new table `class_instantiations` with same structure

---

## The Problem

### What We Can Do Now ✅

```python
# Function calls ARE tracked
result = some_function(arg1, arg2)
```

**Database entry:**
```sql
SELECT * FROM function_call_args WHERE callee_function = 'some_function';
-- Returns: file, line, caller_function, callee_function='some_function', argument_expr
```

### What We CANNOT Do ❌

```python
# Class instantiation NOT tracked
parser = ASTParser()
user = User(name="foo", email="bar@example.com")
```

**Database query:**
```sql
SELECT * FROM function_call_args WHERE callee_function = 'ASTParser';
-- Returns: NOTHING (empty result)
```

**Impact:** We cannot detect:
- Dead classes (defined but never instantiated)
- Class usage patterns
- Constructor argument tracking (security risk - passwords/secrets passed to constructors)

---

## Why This Matters

### 1. Dead Code Detection (PRIMARY USE CASE)

**Current Query (BROKEN):**
```sql
-- Find classes never instantiated
SELECT s.path, s.name, s.line
FROM symbols s
WHERE s.type = 'class'
AND s.name NOT IN (
    SELECT DISTINCT callee_function
    FROM function_call_args
)
```

**Result:** 100% false positives. Every class is flagged as dead, even actively used ones.

**Example False Positive:**
```python
# theauditor/graph/builder.py:15
from theauditor.ast_parser import ASTParser

class GraphBuilder:
    def __init__(self):
        self.ast_parser = ASTParser()  # ← THIS IS NOT TRACKED
```

**Verification:**
```bash
$ grep -r "ASTParser()" theauditor/
theauditor/graph/builder.py:15:        self.ast_parser = ASTParser()
theauditor/indexer/orchestrator.py:42:        self.ast_parser = ASTParser()

# These files PROVE ASTParser is used, but database has no record.
```

### 2. Security Analysis (SECONDARY USE CASE)

**Security Rule Example:**
```python
# rules/security/constructor_secrets.py
def find_secrets_in_constructors(cursor):
    """Find hardcoded secrets passed to class constructors."""

    # WANTED: Track this pattern
    # db = Database(password="hardcoded123")

    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ('Database', 'ApiClient', 'AWSClient')
        AND argument_expr LIKE '%password%'
    """)
    # Currently returns NOTHING because constructors not tracked
```

### 3. Taint Analysis (TERTIARY USE CASE)

**Wanted:** Track data flow through constructor parameters.

```python
# Taint source
user_input = request.get('query')

# Constructor call (NOT TRACKED)
query = SQLQuery(user_input)  # ← Tainted data passed to constructor

# Sink
query.execute()
```

**Current limitation:** Taint tracking breaks at constructor boundary.

---

## Proposed Solution

### Option A: Extend `function_call_args` Table (RECOMMENDED)

**No schema changes needed.** Just populate existing table with class instantiations.

**Python Example:**
```python
parser = ASTParser()
user = User(name="Alice", email="alice@example.com")
```

**Database entries:**
```sql
INSERT INTO function_call_args (file, line, caller_function, callee_function, argument_expr, argument_index)
VALUES
  ('builder.py', 15, '__init__', 'ASTParser', '', 0),
  ('models.py', 42, 'create_user', 'User', 'name="Alice"', 0),
  ('models.py', 42, 'create_user', 'User', 'email="alice@example.com"', 1);
```

**Advantages:**
- ✅ No schema changes
- ✅ Reuses existing query infrastructure
- ✅ Works with existing security rules
- ✅ Taint analysis works automatically

**Disadvantages:**
- ⚠️ Ambiguity: Is `User` a function or class? (Can check `symbols.type = 'class'`)

---

### Option B: New Table `class_instantiations`

**Schema:**
```sql
CREATE TABLE class_instantiations (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    caller_function TEXT,
    class_name TEXT NOT NULL,
    argument_expr TEXT,
    argument_index INTEGER,

    -- Optional: Resolved class path
    class_file TEXT,
    class_line INTEGER,

    PRIMARY KEY (file, line, class_name, argument_index)
);

CREATE INDEX idx_class_instantiations_class ON class_instantiations(class_name);
CREATE INDEX idx_class_instantiations_file ON class_instantiations(file);
```

**Advantages:**
- ✅ Clear separation (no ambiguity)
- ✅ Can add class-specific metadata (inheritance, type hints)
- ✅ Easier to extend later

**Disadvantages:**
- ❌ Schema migration required
- ❌ Duplicate query logic needed
- ❌ More complex queries (JOIN required)

---

## Implementation Guide

### What to Track

**Python:**
```python
# Direct instantiation
obj = ClassName()                          # ✅ Track: ClassName
obj = ClassName(arg1, arg2)                # ✅ Track: ClassName + args

# With arguments
user = User(name="Alice", email="foo@bar") # ✅ Track: User + 2 args

# Assigned to variables
self.parser = ASTParser()                  # ✅ Track: ASTParser

# Nested
result = process(User(name="Bob"))         # ✅ Track: User inside process() call
```

**JavaScript/TypeScript:**
```javascript
// new keyword
const parser = new ASTParser();            // ✅ Track: ASTParser
const user = new User("Alice", "alice@example.com");  // ✅ Track: User + args

// Factory pattern (harder, may skip for v1)
const user = UserFactory.create();         // ⚠️ Skip for now
```

**What NOT to Track:**
```python
# Method calls (already tracked)
obj.method()                               # ❌ Already in function_call_args

# Decorators (not instantiation)
@dataclass                                 # ❌ Different analysis
class User: pass

# Type hints (not runtime)
def foo(x: UserClass):                     # ❌ Static analysis only
    pass
```

---

## AST Extraction Points

### Python (ast module)

**Current code location:** `theauditor/indexer/extractors/python.py`

**Detection pattern:**
```python
import ast

for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        # Check if func is a Name (not Attribute)
        if isinstance(node.func, ast.Name):
            callee = node.func.id

            # Check if it's a class (uppercase first letter heuristic)
            # OR join with symbols table: symbols.type = 'class'
            if callee[0].isupper():
                # This is likely a class instantiation
                record_instantiation(
                    class_name=callee,
                    args=[arg_to_string(arg) for arg in node.args],
                    line=node.lineno
                )
```

**Precise method (JOIN with symbols):**
```python
# After extraction, query database
cursor.execute("""
    SELECT name FROM symbols WHERE type='class' AND file=?
""", (current_file,))
known_classes = {row[0] for row in cursor}

# Then filter candidates
if callee in known_classes:
    record_instantiation(...)
```

### JavaScript (Babel parser)

**Current code location:** `theauditor/indexer/extractors/javascript.py`

**Detection pattern:**
```javascript
// Babel AST node type: NewExpression
{
  type: 'NewExpression',
  callee: { type: 'Identifier', name: 'ASTParser' },
  arguments: [...]
}
```

**Extraction:**
```python
def visit_NewExpression(node):
    if node['callee']['type'] == 'Identifier':
        class_name = node['callee']['name']
        args = [arg_to_string(arg) for arg in node.get('arguments', [])]
        record_instantiation(class_name, args, node['loc']['start']['line'])
```

---

## Test Cases

### Test 1: Basic Class Detection

**File:** `test_class_tracking.py`
```python
class MyClass:
    def __init__(self, value):
        self.value = value

def test_function():
    obj = MyClass(42)  # Line 6
    return obj.value
```

**Expected database entries:**
```sql
-- symbols table (already works)
INSERT INTO symbols VALUES ('test_class_tracking.py', 'MyClass', 'class', 1, 3);

-- function_call_args table (NEW - this is what we need)
INSERT INTO function_call_args VALUES
  ('test_class_tracking.py', 6, 'test_function', 'MyClass', '42', 0);
```

**Verification query:**
```sql
SELECT callee_function, argument_expr
FROM function_call_args
WHERE file = 'test_class_tracking.py'
AND callee_function = 'MyClass';
-- Expected: 1 row with argument_expr='42'
```

---

### Test 2: Dead Class Detection

**File:** `test_dead_class.py`
```python
class UsedClass:
    pass

class DeadClass:
    pass

obj = UsedClass()  # This is tracked
# DeadClass is never instantiated
```

**Expected query result:**
```sql
-- Find dead classes
SELECT s.name
FROM symbols s
WHERE s.type = 'class'
AND s.file = 'test_dead_class.py'
AND s.name NOT IN (
    SELECT DISTINCT callee_function
    FROM function_call_args
    WHERE file = 'test_dead_class.py'
);
-- Expected: 'DeadClass' (but NOT 'UsedClass')
```

---

### Test 3: Security Rule - Constructor Secrets

**File:** `test_constructor_secrets.py`
```python
class Database:
    def __init__(self, host, password):
        self.host = host
        self.password = password

# BAD: Hardcoded password
db = Database("localhost", "hardcoded123")
```

**Expected security rule to work:**
```sql
SELECT file, line, callee_function, argument_expr
FROM function_call_args
WHERE callee_function = 'Database'
AND argument_index = 1  -- Second argument (password)
AND argument_expr NOT LIKE '%env%'
AND argument_expr NOT LIKE '%config%';
-- Expected: Find line with 'hardcoded123'
```

---

## Database Layer Requirements

### Input (What Indexer Provides)

For each class instantiation found during AST parsing:

```python
{
    'file': 'theauditor/graph/builder.py',
    'line': 15,
    'caller_function': '__init__',
    'class_name': 'ASTParser',
    'arguments': [],  # Empty for no-arg constructor
}

{
    'file': 'theauditor/models/user.py',
    'line': 42,
    'caller_function': 'create_user',
    'class_name': 'User',
    'arguments': ['name="Alice"', 'email="alice@example.com"'],
}
```

### Output (What Gets Stored)

**Option A (Recommended):** Add to existing `function_call_args`:

```sql
INSERT INTO function_call_args (file, line, caller_function, callee_function, argument_expr, argument_index)
VALUES
  ('builder.py', 15, '__init__', 'ASTParser', '', 0),
  ('user.py', 42, 'create_user', 'User', 'name="Alice"', 0),
  ('user.py', 42, 'create_user', 'User', 'email="alice@example.com"', 1);
```

**Option B:** New table `class_instantiations` (same structure).

### Query Interface

**Consumers of this data need:**

```python
# 1. Check if class is ever instantiated
cursor.execute("""
    SELECT COUNT(*) FROM function_call_args
    WHERE callee_function = ?
""", (class_name,))

# 2. Find all instantiation sites
cursor.execute("""
    SELECT file, line, argument_expr
    FROM function_call_args
    WHERE callee_function = ?
""", (class_name,))

# 3. Dead class detection
cursor.execute("""
    SELECT s.name FROM symbols s
    WHERE s.type = 'class'
    AND s.name NOT IN (
        SELECT DISTINCT callee_function FROM function_call_args
    )
""")
```

---

## Migration Strategy

### Phase 1: Schema Update (if Option B chosen)

```sql
-- Add new table
CREATE TABLE class_instantiations (...);

-- Backward compatibility view (combines tables)
CREATE VIEW all_call_sites AS
    SELECT file, line, caller_function, callee_function AS name, 'function' AS type
    FROM function_call_args
    UNION ALL
    SELECT file, line, caller_function, class_name AS name, 'class' AS type
    FROM class_instantiations;
```

### Phase 2: Indexer Changes

1. Update `theauditor/indexer/extractors/python.py`:
   - Add `extract_class_instantiations()` function
   - Call from `extract()` method
   - Return in result dict under `'class_instantiations': [...]`

2. Update `theauditor/indexer/__init__.py`:
   - Store instantiations in database (around line 948+)
   - Use same pattern as `function_call_args` storage

### Phase 3: Validation

Run on test codebase:
```bash
aud index
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM function_call_args WHERE callee_function = 'ASTParser'"
# Should return > 0 (currently returns 0)
```

---

## Acceptance Criteria

✅ **DONE WHEN:**

1. `ASTParser()` instantiation in `graph/builder.py:15` appears in database:
   ```sql
   SELECT * FROM function_call_args WHERE callee_function='ASTParser';
   -- Returns at least 2 rows (builder.py + orchestrator.py)
   ```

2. Dead class query returns ONLY truly dead classes:
   ```bash
   aud deadcode --classes
   # ASTParser NOT in results (it's used)
   # VerboseGroup NOT in results (it's used in cli.py)
   ```

3. Security rule can find constructor secrets:
   ```python
   db = Database(password="hardcoded")  # ← This gets flagged
   ```

---

## Additional Context

### Similar Systems

**How other SAST tools handle this:**

1. **Semgrep**: Tracks instantiation via pattern `new $CLASS(...)` in AST
2. **CodeQL**: Has separate `ClassInstantiation` predicate
3. **Snyk**: Merges into call graph (like Option A)

### Performance Impact

**Estimated rows added:** +5-10% increase in `function_call_args` table size.

**Example:**
- Current: 42,633 function calls (per last `aud index`)
- After: ~45,000 rows (adding ~2,500 class instantiations)

**Query performance:** No impact (same indexes work).

---

## Questions for Database Layer 3

1. **Preferred option:** Option A (extend function_call_args) or Option B (new table)?
2. **Disambiguation:** How to distinguish function call from class instantiation in queries?
   - Add `call_type` column? (`'function'` | `'class'`)
   - Query `symbols.type` on each lookup?
3. **JavaScript `new` keyword:** Should we track ALL `new X()` or only known classes?
4. **Timeline:** What sprint can this be included in?

---

## Related Issues

- Dead code detection blocked: #DEAD-001
- Taint tracking gaps: #TAINT-015
- Security rule limitations: #SEC-042

---

**Contact:** Dead Code Detection Module
**Priority:** Medium (P2)
**Estimated Effort:** 2-3 days (Option A) or 5-7 days (Option B)
