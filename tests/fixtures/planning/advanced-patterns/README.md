# Advanced Pattern Fixtures

**Purpose**: Test planning system verification against REAL schema normalization patterns with proper JOINs.

These fixtures demonstrate code that, when indexed by `aud index`, populates **junction tables** and requires **proper JOIN queries** for verification.

---

## What This Tests

### 1. api_with_auth.py
**Pattern**: Multiple authentication controls per API endpoint
**Junction Table**: `api_endpoint_controls`
**Schema**: `api_endpoints (1) → api_endpoint_controls (N)`

**Indexed Data**:
```
api_endpoints:
  - id=1, path='/api/admin/users', method='GET'

api_endpoint_controls:
  - (endpoint_id=1, control_name='login_required')
  - (endpoint_id=1, control_name='admin_required')
  - (endpoint_id=1, control_name='rate_limit')
```

**Verification Query** (NO LIKE %):
```sql
SELECT DISTINCT ec.control_name
FROM api_endpoints e
JOIN api_endpoint_controls ec ON e.id = ec.endpoint_id
WHERE e.path = '/api/admin/users'
```

**Expected Result**: `['login_required', 'admin_required', 'rate_limit']`

**Security Finding**: `/api/admin/payments` missing `rate_limit` control

---

### 2. sql_multi_table.py
**Pattern**: SQL queries referencing multiple tables
**Junction Table**: `sql_query_tables`
**Schema**: `sql_queries (1) → sql_query_tables (N)`

**Indexed Data**:
```
sql_queries:
  - id=1, query_text='SELECT u.username... FROM users u JOIN orders o...'

sql_query_tables:
  - (query_id=1, table_name='users')
  - (query_id=1, table_name='orders')
  - (query_id=1, table_name='order_items')
```

**Verification Query**:
```sql
SELECT DISTINCT sqt.table_name
FROM sql_queries sq
JOIN sql_query_tables sqt ON sq.id = sqt.query_id
WHERE sq.file = 'sql_multi_table.py'
  AND sq.function_name = 'admin_dashboard_stats'
```

**Expected Result**: `['users', 'orders', 'payments', 'products']`

**Taint Risk**: All 4 tables contain sensitive data → high taint surface area

---

### 3. taint_multi_source.py
**Pattern**: Assignments with multiple source variables
**Junction Table**: `assignment_sources`
**Schema**: `assignments (1) → assignment_sources (N)`

**Indexed Data**:
```
assignments:
  - id=1, file='taint_multi_source.py', target_var='query', line=15

assignment_sources:
  - (assignment_id=1, variable_name='username')
  - (assignment_id=1, variable_name='email')
  - (assignment_id=1, variable_name='role')
```

**Verification Query**:
```sql
SELECT DISTINCT as2.variable_name
FROM assignments a
JOIN assignment_sources as2 ON a.id = as2.assignment_id
WHERE a.target_var = 'query'
  AND a.file = 'taint_multi_source.py'
```

**Expected Result**: `['username', 'email', 'role']`

**Taint Analysis**:
- All 3 sources are user input (tainted)
- Assignment target `query` is used in SQL execution (sink)
- Multi-source taint = SQL injection risk

---

### 4. react_hook_deps.jsx
**Pattern**: React hooks with multiple dependencies
**Junction Table**: `react_hook_dependencies`
**Schema**: `react_hooks (1) → react_hook_dependencies (N)`

**Indexed Data**:
```
react_hooks:
  - id=1, file='react_hook_deps.jsx', hook_name='useEffect', line=15

react_hook_dependencies:
  - (hook_id=1, dependency_name='userId')
  - (hook_id=1, dependency_name='sessionToken')
```

**Verification Query**:
```sql
SELECT rhd.dependency_name
FROM react_hooks rh
JOIN react_hook_dependencies rhd ON rh.id = rhd.hook_id
WHERE rh.file = 'react_hook_deps.jsx'
  AND rh.hook_name = 'useEffect'
  AND rh.line = 15
```

**Expected Result**: `['userId', 'sessionToken']`

**Security Finding**: `sessionToken` in dependency array = re-executes on token change (sensitive data)

---

### 5. function_return_flow.py
**Pattern**: Cross-function taint flow (return values → assignments)
**Junction Table**: `function_return_sources`
**Schema**: `function_returns (1) → function_return_sources (N)`

**Indexed Data**:
```
function_returns:
  - id=1, file='function_return_flow.py', function_name='process_payment_data', line=50

function_return_sources:
  - (return_id=1, variable_name='card_number')
  - (return_id=1, variable_name='cvv')
  - (return_id=1, variable_name='amount')
```

**Taint Flow Query**:
```sql
-- Find what variables are returned
SELECT frs.variable_name
FROM function_returns fr
JOIN function_return_sources frs ON fr.id = frs.return_id
WHERE fr.function_name = 'get_user_input'

-- Find where those variables are assigned
SELECT a.target_var, a.file, a.line
FROM assignments a
JOIN assignment_sources as2 ON a.id = as2.assignment_id
WHERE as2.variable_name IN (
  SELECT frs.variable_name
  FROM function_returns fr
  JOIN function_return_sources frs ON fr.id = frs.return_id
  WHERE fr.function_name = 'get_user_input'
)
```

**Taint Chain**:
1. `get_user_input()` returns `user_data` (SOURCE)
2. `build_sql_query()` assigns `user_data` → `username`
3. `execute_dangerous_query()` uses `username` in SQL (SINK)

---

### 6. import_chain.py
**Pattern**: Single import statement with multiple names
**Junction Table**: `import_style_names`
**Schema**: `imports (1) → import_style_names (N)`

**Indexed Data**:
```
imports:
  - id=1, file='import_chain.py', module='flask', line=1

import_style_names:
  - (import_id=1, imported_name='Blueprint')
  - (import_id=1, imported_name='request')
  - (import_id=1, imported_name='jsonify')
  - (import_id=1, imported_name='session')
  - (import_id=1, imported_name='g')
```

**Verification Query**:
```sql
SELECT isn.imported_name
FROM imports i
JOIN import_style_names isn ON i.id = isn.import_id
WHERE i.module = 'flask'
  AND i.file = 'import_chain.py'
```

**Expected Result**: `['Blueprint', 'request', 'jsonify', 'session', 'g']`

**Anti-Pattern Detection**: `from utils import *` creates row with `imported_name='*'`

---

## Verification Spec (spec.yaml)

The spec tests that planning verification can:

1. **Query with JOINs** (not LIKE % patterns)
2. **Aggregate junction table data** (GROUP_CONCAT, COUNT)
3. **Detect missing rows** (incomplete auth controls)
4. **Count dependencies** (too many React hook deps)
5. **Trace taint flows** (multi-hop function returns)
6. **Validate import completeness** (all required names imported)

---

## Usage

### Index the Fixture:
```bash
cd tests/fixtures/planning/advanced-patterns
aud init .
aud index
```

### Create Plan:
```bash
aud planning init --name "Advanced Pattern Verification"
aud planning add-task 1 --title "Verify patterns" --spec spec.yaml
```

### Verify (should detect issues):
```bash
aud planning verify-task 1 1 --verbose
```

**Expected Violations**:
- `/api/admin/payments` missing `rate_limit` control
- `build_user_query()` has multi-source SQL concatenation
- `from utils import *` uses star import

---

## What This Proves

✅ Planning system can verify:
- **Junction table queries** (proper JOINs, not LIKE %)
- **Multi-source taint tracking** (assignments with N sources)
- **Cross-function data flow** (return sources → assignment sources)
- **API security patterns** (endpoints with N auth controls)
- **SQL query analysis** (queries touching N tables)
- **React performance patterns** (hooks with N dependencies)
- **Import completeness** (single import with N names)

❌ **Old (bad) pattern**: `WHERE callee_function LIKE '%jwt%'`
✅ **New (correct) pattern**: `JOIN function_call_args WHERE callee_function = 'jwt.sign'`

This is what database normalization unlocked.
