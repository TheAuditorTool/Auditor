# RULE METADATA SYSTEM & TEMPLATES

**Added:** 2025-10-01 (Phase 3B Implementation)
**Status:** PRODUCTION READY
**Templates:** `/rules/TEMPLATE_STANDARD_RULE.py` and `/rules/TEMPLATE_JSX_RULE.py`

---

## **CRITICAL: Read This Before Writing Rules**

TheAuditor now has **smart rule filtering** via metadata. Rules declare their requirements, and the orchestrator automatically skips irrelevant files.

---

## **Available Templates**

### **1. TEMPLATE_STANDARD_RULE.py** - Backend/Database Rules
- **For:** SQL injection, authentication, API security, ORM patterns
- **Targets:** `.py`, `.js`, `.ts` files (server-side code)
- **Queries:** Standard tables (`function_call_args`, `symbols`, `assignments`)
- **Auto-skips:** Frontend JSX/TSX files, migrations, tests

### **2. TEMPLATE_JSX_RULE.py** - JSX-Specific Rules
- **For:** JSX element injection, React/Vue component security
- **Targets:** `.jsx`, `.tsx`, `.vue` files ONLY
- **Queries:** JSX-specific tables (`symbols_jsx`, `assignments_jsx`, `function_call_args_jsx`)
- **Requires:** `requires_jsx_pass=True` metadata flag

---

## **Rule Metadata Explained**

Every rule MUST include this metadata block:

```python
from theauditor.rules.base import RuleMetadata

METADATA = RuleMetadata(
    name="your_rule_name",              # snake_case identifier
    category="sql",                      # sql, xss, auth, secrets, etc.

    # File targeting - orchestrator uses this to skip irrelevant files
    target_extensions=['.py', '.js', '.ts'],     # ONLY run on these
    exclude_patterns=['frontend/', 'migrations/'], # SKIP these paths

    # Optional: Include specific patterns (alternative to exclude)
    # target_file_patterns=['backend/', 'server/'],

    # JSX settings (CRITICAL for React/Vue rules)
    requires_jsx_pass=False,  # True = query *_jsx tables, not standard tables
    jsx_pass_mode='preserved', # Only if requires_jsx_pass=True
)
```

---

## **Why This Matters**

### **Before (No Metadata):**
```
❌ SQL injection rule runs on ALL 340 files
❌ Wastes time analyzing React.jsx (no SQL in frontend)
❌ Wastes time on migrations (DDL, not user input)
❌ Output polluted with "0 findings in App.jsx" spam
```

### **After (With Metadata):**
```
✅ SQL injection rule runs on 120 backend files only
⊘ Skipped 43 migrations (exclude_patterns=['migrations/'])
⊘ Skipped 150 frontend files (not in target_extensions)
✅ Clean output, 10x faster rule execution
```

---

## **Quick Decision Tree**

**Question: What type of rule am I writing?**

### **Option A: Backend/Database Rule** → Use `TEMPLATE_STANDARD_RULE.py`
**Detects:**
- SQL injection (string interpolation in queries)
- Authentication issues (hardcoded secrets, weak JWT)
- API security (CORS, rate limiting)
- ORM patterns (N+1 queries, missing transactions)

**Queries:**
- `function_call_args` - Function calls like `db.execute(query)`
- `symbols` - Function/variable definitions
- `assignments` - Variable assignments for data flow
- `sql_queries` WHERE `extraction_source='code_execute'` (not migrations)

**Example rules:**
- `rules/sql/sql_injection_analyze.py`
- `rules/auth/jwt_analyze.py`
- `rules/security/cors_analyze.py`

---

### **Option B: JSX-Specific Rule** → Use `TEMPLATE_JSX_RULE.py`
**Detects:**
- JSX element injection: `<{UserComponent} />`
- JSX spread operator dangers: `<div {...userProps} />`
- Dynamic component rendering from user input
- JSX attribute injection patterns

**Queries:**
- `symbols_jsx` WHERE `jsx_mode='preserved'` - Preserved JSX elements
- `assignments_jsx` - Assignments in JSX context
- `function_call_args_jsx` - Function calls within JSX

**Example use cases:**
- Detecting `<{props.ComponentName} />` (component injection)
- Detecting `{...userControlledObject}` (spread injection)
- Vue `v-html` with user input

**Why preserved JSX?**
JSX transformation loses syntax information:
```jsx
// BEFORE (preserved - detectable):
<{UserComponent} />

// AFTER (transformed - information lost):
React.createElement(UserComponent)
```

---

### **Option C: React/Vue Hooks Rule** → Use `TEMPLATE_STANDARD_RULE.py` ⚠️ NOT JSX!
**Detects:**
- `useState` / `useEffect` dependency issues
- Hook call order violations
- Improper cleanup in `useEffect`

**Queries:**
- `function_call_args` WHERE `callee_function LIKE 'use%'`
- Standard `react_hooks` table

**Why standard template:**
Hooks work on TRANSFORMED data. They're function calls, not JSX syntax:
```javascript
// This is the SAME in both preserved and transformed passes:
const [state, setState] = useState(0);
```

**Rule of thumb:**
- Need to detect **JSX SYNTAX** (`< >` tags, `{...props}`) → JSX template
- Need to detect **FUNCTION CALLS** (hooks, APIs) → Standard template

---

## **File Category System** (Added Phase 3B)

Files are now tagged with categories for intelligent filtering:

| Category | Example Files | Rule Behavior |
|----------|---------------|---------------|
| `source` | `backend/src/users.js` | ✅ Run all security rules |
| `migration` | `migrations/20250913-create-users.js` | ⚠️ Run migration-specific rules only |
| `test` | `__tests__/users.test.js` | ⊘ Skip most security rules |
| `config` | `webpack.config.js` | ✅ Run config security rules |

**SQL queries also tagged by source:**

| extraction_source | Example | Priority for SQL Injection |
|-------------------|---------|---------------------------|
| `code_execute` | `db.execute("SELECT * FROM users WHERE id = " + userId)` | 🔴 **HIGH** (user input risk) |
| `orm_query` | `User.findAll({ where: { id: userId } })` | 🟡 **MEDIUM** (usually parameterized) |
| `migration_file` | `CREATE TABLE users (id SERIAL PRIMARY KEY)` | 🟢 **LOW** (DDL, skip in injection rules) |

**How to filter in rules:**
```python
# SQL injection rule - skip migrations
cursor.execute("""
    SELECT file, line, argument_expr
    FROM function_call_args
    JOIN sql_queries sq ON sq.file_path = function_call_args.file
    WHERE sq.extraction_source != 'migration_file'  -- Skip DDL
      AND callee_function LIKE '%.execute%'
""")
```

---

## **Examples from Production Rules**

### **Example 1: SQL Injection Rule (Standard Template)**
```python
from theauditor.rules.base import RuleMetadata

METADATA = RuleMetadata(
    name="sql_injection",
    category="sql",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=['frontend/', 'client/', 'migrations/', 'test/'],
    requires_jsx_pass=False  # Uses standard tables
)

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect SQL injection using database queries only."""
    # Query function_call_args for .query()/.execute() calls
    # Check for string interpolation patterns
    # Exclude migrations via extraction_source filtering
```

### **Example 2: React XSS Rule (Standard Template - NOT JSX!)**
```python
METADATA = RuleMetadata(
    name="react_dangerously_set_inner_html",
    category="xss",
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],  # JSX AND JS (components in both)
    target_file_patterns=['frontend/', 'client/', 'src/components/'],
    requires_jsx_pass=False  # dangerouslySetInnerHTML available in standard tables
)

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Check for dangerouslySetInnerHTML with user input."""
    # Query standard assignments table (not assignments_jsx)
    # Pattern detected via function call args, not JSX syntax
```

### **Example 3: JSX Element Injection (JSX Template)**
```python
METADATA = RuleMetadata(
    name="jsx_element_injection",
    category="xss",
    target_extensions=['.jsx', '.tsx'],  # JSX files ONLY
    target_file_patterns=['frontend/', 'client/'],
    requires_jsx_pass=True,  # MUST use symbols_jsx table
    jsx_pass_mode='preserved'
)

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect dynamic JSX element injection: <{UserComponent} />"""
    # Query symbols_jsx WHERE jsx_mode='preserved'
    # This pattern is LOST in transformed AST
```

---

## **Testing Your Rule**

After writing a rule, verify the filtering works:

```bash
# 1. Test on plant project with debug output
cd C:\Users\santa\Desktop\plant
aud detect-patterns --category=your_category

# 2. Verify orchestrator filtering (check logs)
# Expected output:
#   ✓ Running sql_injection on backend/users.js
#   ⊘ Skipping sql_injection on frontend/App.jsx (not in target_extensions)
#   ⊘ Skipping sql_injection on migrations/001.js (exclude_patterns match)

# 3. Check performance
time aud detect-patterns --category=your_category
# Target: <5 seconds for 10K LOC project

# 4. Verify findings quality
aud detect-patterns --category=your_category | grep "Found"
# Check for false positives
```

---

## **Common Pitfalls to Avoid**

### **❌ DON'T:**
1. Query files directly (use database tables)
2. Use regex on file content (use indexed database fields)
3. Set `requires_jsx_pass=True` for hooks (they're function calls, not JSX)
4. Target all extensions `['.js', '.jsx', '.ts', '.tsx']` (be specific)
5. Skip the metadata block (orchestrator won't filter)

### **✅ DO:**
1. Copy the appropriate template (STANDARD vs JSX)
2. Add METADATA with precise file targeting
3. Use frozensets for pattern matching (O(1) lookups)
4. Query database with table existence checks
5. Test with `--debug` to verify filtering

---

## **Migration Notice**

**Existing rules (written before Phase 3B) still work** but lack metadata filtering.

When editing old rules:
1. Add `METADATA` block at top
2. Set `target_extensions` to skip irrelevant files
3. Set `exclude_patterns` to skip migrations/tests
4. Test that filtering works

---

## **Checklist: Writing a New Rule**

**Before you start:**
- [ ] Decided: STANDARD or JSX template?
- [ ] Read the appropriate template fully
- [ ] Identified target file extensions
- [ ] Identified exclusion patterns

**During development:**
- [ ] Copied template to `rules/category/your_rule.py`
- [ ] Updated METADATA block
- [ ] Used frozensets for patterns (not lists)
- [ ] Queried database tables (not files)
- [ ] Added table existence checks
- [ ] Filtered migrations via `extraction_source` (if SQL rule)

**Before committing:**
- [ ] Tested on plant project: `aud detect-patterns --category=your_category`
- [ ] Verified filtering: Check logs for ⊘ Skipped messages
- [ ] No false positives on test corpus
- [ ] Performance: <5 seconds for 10K LOC
- [ ] Documented in rule docstring

---

## **Reference: Metadata Fields**

```python
@dataclass
class RuleMetadata:
    """Metadata describing rule requirements for orchestrator filtering."""

    name: str                           # Required: Rule identifier (snake_case)
    category: str                        # Required: sql, xss, auth, etc.

    target_extensions: List[str] = None  # Optional: ['.py', '.js'] - ONLY these files
    exclude_patterns: List[str] = None   # Optional: ['migrations/', 'test/'] - SKIP these
    target_file_patterns: List[str] = None  # Optional: ['backend/', 'server/'] - INCLUDE these

    requires_jsx_pass: bool = False      # Critical: True = query *_jsx tables
    jsx_pass_mode: str = 'preserved'     # Only if requires_jsx_pass=True
```

---

## **Support & Documentation**

- **Templates:** `C:\Users\santa\Desktop\TheAuditor\theauditor\rules\TEMPLATE_*.py`
- **Examples:** `rules/sql/sql_injection_analyze.py`, `rules/xss/react_xss_analyze.py`
- **Full docs:** `CLAUDE.md` (search for "Rule Metadata")
- **Status report:** `rules/nightmare_fuel.md` (comprehensive audit)

---

**Last updated:** 2025-10-01
**Phase:** 3B Implementation
**Status:** PRODUCTION READY
