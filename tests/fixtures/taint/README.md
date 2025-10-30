# Taint Analysis - Dynamic Dispatch Fixture

## Purpose
Tests taint analysis through **dynamic dispatch** patterns where function handlers are selected at runtime via object literal property access.

Validates that TheAuditor's taint tracking can handle:
- Dynamic handler selection: `handlers[req.query.action](data)`
- Shorthand property dispatch: `actions[cmd]()`
- Nested object dispatch: `routes.api[resource][method]()`
- Sanitization detection: Distinguishing safe vs unsafe flows

## Dynamic Dispatch Pattern

**Challenge**: Traditional call graph analysis fails when:
```javascript
const handlers = { create: createUser, update: updateUser };
const fn = handlers[userInput];  // Runtime dispatch
fn(taintedData);  // Callee not statically determinable
```

**Required Analysis**:
1. Track object literal properties → function mappings
2. Detect property access with tainted key: `handlers[taintedKey]`
3. Propagate taint through dynamically called functions
4. Flag sinks (SQL, eval) reached via dynamic dispatch

## Test Cases

### Test 1: Direct Object Literal Dispatch (VULNERABLE)

**Lines 7-33**

```javascript
const handlers = {
    create: createUser,
    update: updateUser,
    delete: deleteUser
};

app.post('/action', (req, res) => {
    const action = req.query.action;  // TAINT SOURCE
    const handler = handlers[action];  // Dynamic dispatch
    handler(req.body);                 // TAINT SINK
});

function createUser(data) {
    const query = `INSERT INTO users VALUES ('${data.name}')`;  // SQL INJECTION
    db.execute(query);
}
```

**Expected Taint Flow**:
1. `req.query.action` (SOURCE)
2. `handlers[action]` (dynamic dispatch)
3. `createUser(req.body)` (propagation)
4. `db.execute(query)` with interpolated `data.name` (SINK)

**Vulnerability**: SQL Injection via dynamically dispatched handler

---

### Test 2: Shorthand Syntax Dispatch (VULNERABLE)

**Lines 35-59**

```javascript
const actions = {
    login,      // Shorthand: equivalent to login: login
    register,
    logout
};

app.post('/auth', (req, res) => {
    const cmd = req.body.command;   // TAINT SOURCE
    const fn = actions[cmd];        // Dynamic dispatch
    fn(req.body);                   // TAINT SINK
});

function register(userData) {
    eval(`user = ${JSON.stringify(userData)}`);  // CODE INJECTION
}
```

**Expected Taint Flow**:
1. `req.body.command` (SOURCE)
2. `actions[cmd]` (dynamic dispatch via shorthand property)
3. `register(req.body)` (propagation)
4. `eval(...)` with interpolated `userData` (SINK)

**Vulnerabilities**:
- SQL Injection in `login()` (line 49)
- **Code Injection** in `register()` (line 54) - CRITICAL
- SQL Injection in `logout()` (line 58)

---

### Test 3: Nested Object Dispatch (VULNERABLE)

**Lines 61-88**

```javascript
const routes = {
    api: {
        users: {
            get: getUsers,
            post: createUser
        },
        posts: {
            get: getPosts
        }
    }
};

app.all('/api/:resource/:method', (req, res) => {
    const resource = req.params.resource;  // TAINT SOURCE
    const method = req.params.method;      // TAINT SOURCE
    const handler = routes.api[resource][method];  // Nested dispatch
    handler(req.body, res);                // TAINT SINK
});

function getUsers(params, res) {
    const query = `SELECT * FROM users WHERE role='${params.role}'`;
    res.send(db.query(query));
}
```

**Expected Taint Flow**:
1. `req.params.resource` and `req.params.method` (SOURCES)
2. `routes.api[resource][method]` (2-level nested dispatch)
3. `getUsers(req.body)` (propagation)
4. `db.query(query)` with interpolated `params.role` (SINK)

**Vulnerability**: SQL Injection via nested dynamic dispatch

---

### Test 4: Safe Dispatch with Sanitization (NOT VULNERABLE)

**Lines 90-112**

```javascript
const safeHandlers = {
    validate: validateInput,
    sanitize: sanitizeInput
};

app.post('/safe', (req, res) => {
    const op = req.query.op;
    const handler = safeHandlers[op];
    const clean = handler(req.body);  // Sanitized
    db.query(`INSERT INTO logs VALUES ('${clean}')`);  // SAFE
});

function sanitizeInput(data) {
    return data.value.replace(/[^a-zA-Z0-9]/g, '');  // Removes SQL metacharacters
}
```

**Expected Behavior**: Taint should be **removed** after sanitization

**Analysis Required**:
1. Detect `sanitizeInput()` as sanitizer (regex replacement of dangerous chars)
2. Mark return value as CLEAN
3. SQL sink should be flagged as SAFE (taint removed by sanitizer)

## Populated Database Tables

After `aud index`:

| Table | Expected Count | What It Tests |
|---|---|---|
| **object_literal_properties** | 15+ | Handler mappings (create → createUser, etc.) |
| **function_calls** | 20+ | Dynamic dispatch calls, db.execute/query calls |
| **assignments** | 12+ | `const handler = handlers[action]` patterns |
| **taint_sources** | 6+ | req.query, req.params, req.body |
| **taint_sinks** | 8+ | db.execute, db.query, eval |

## Sample Verification Queries

### Query 1: Find All Dynamic Handler Mappings

```sql
SELECT
    object_name,
    key,
    value
FROM object_literal_properties
WHERE file LIKE '%dynamic_dispatch.js'
  AND (
    object_name = 'handlers'
    OR object_name = 'actions'
    OR object_name = 'routes'
  )
ORDER BY object_name, key;
```

**Expected Results**: 10+ handler mappings

### Query 2: Find Dynamic Dispatch Assignments

```sql
SELECT
    target,
    source_expr,
    line
FROM assignments
WHERE file LIKE '%dynamic_dispatch.js'
  AND source_expr LIKE '%[%]%'  -- Property access
ORDER BY line;
```

**Expected Results**: `handler = handlers[action]`, `fn = actions[cmd]`, etc.

### Query 3: Find SQL Injection Sinks

```sql
SELECT
    fc.function_name AS context,
    fc.callee_function AS sink,
    fc.line
FROM function_calls fc
WHERE fc.file LIKE '%dynamic_dispatch.js'
  AND (
    fc.callee_function LIKE '%execute%'
    OR fc.callee_function LIKE '%query%'
  )
ORDER BY fc.line;
```

**Expected Results**: 6+ db.execute/query calls

### Query 4: Find Code Injection Sinks (eval)

```sql
SELECT
    function_name,
    callee_function,
    line
FROM function_calls
WHERE file LIKE '%dynamic_dispatch.js'
  AND callee_function = 'eval'
ORDER BY line;
```

**Expected Results**: 1 eval call in `register()` (line 54)

### Query 5: Find Sanitization Functions

```sql
SELECT
    s.name,
    s.type,
    s.line
FROM symbols s
WHERE s.path LIKE '%dynamic_dispatch.js'
  AND (
    s.name LIKE '%sanitize%'
    OR s.name LIKE '%validate%'
  )
ORDER BY s.line;
```

**Expected Results**: `validateInput`, `sanitizeInput`

## Expected Taint Analysis Findings

### CRITICAL Findings

1. **Code Injection via eval** (Line 54)
   - Source: `req.body.command`
   - Dispatch: `actions[cmd]` → `register()`
   - Sink: `eval()` with user data
   - Severity: CRITICAL

### HIGH Findings

2. **SQL Injection in createUser** (Line 22)
   - Source: `req.query.action`
   - Dispatch: `handlers[action]` → `createUser()`
   - Sink: `db.execute()` with interpolated `data.name`
   - Severity: HIGH

3. **SQL Injection in login** (Line 49)
   - Source: `req.body.command`
   - Dispatch: `actions[cmd]` → `login()`
   - Sink: `db.query()` with interpolated `credentials.user`
   - Severity: HIGH

4. **SQL Injection in getUsers** (Line 82)
   - Source: `req.params.resource`, `req.params.method`
   - Dispatch: `routes.api[resource][method]` → `getUsers()`
   - Sink: `db.query()` with interpolated `params.role`
   - Severity: HIGH

### MEDIUM Findings

5-7. **SQL Injections in updateUser, deleteUser, logout, getPosts**
   - All similar patterns with different sources
   - Severity: MEDIUM to HIGH

### NO FINDINGS (Correctly Sanitized)

8. **Safe dispatch pattern** (Line 100)
   - Source: `req.query.op`
   - Sanitizer: `sanitizeInput()` removes SQL metacharacters
   - Sink: `db.query()` with clean data
   - Expected: **NO VULNERABILITY** (sanitized)

## Testing Use Cases

This fixture enables testing:

1. **Dynamic Dispatch Detection**: Identify `obj[key](args)` patterns
2. **Object Literal Analysis**: Map function properties to handlers
3. **Multi-Hop Taint**: Track taint through HTTP → dispatch → handler → sink
4. **Nested Property Access**: Handle `routes.api[x][y]()` patterns
5. **Sanitizer Recognition**: Detect when taint is removed by validation/sanitization
6. **Shorthand Property Tracking**: ES6 `{ login }` equivalent to `{ login: login }`

## How to Use

1. **Index from TheAuditor root**:
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index
   ```

2. **Run taint analysis**:
   ```bash
   aud detect-patterns --file tests/fixtures/taint/dynamic_dispatch.js
   ```

3. **Query taint flows**:
   ```bash
   aud context query --symbol createUser --show-callers
   ```

## Why This Fixture Matters

Dynamic dispatch is **extremely common** in real-world JavaScript:
- Express route handlers: `app[method](path, handlers[action])`
- React event handlers: `<button onClick={handlers[type]} />`
- Redux action dispatchers: `dispatch(actions[actionType]())`
- Plugin systems: `plugins[name].execute()`

If taint analysis can't handle dynamic dispatch, it will miss:
- 30-50% of real-world vulnerabilities
- Most Express/React/Redux applications
- All plugin-based architectures

## Expected Behavior

When this fixture is indexed and analyzed:

- ✅ **4 vulnerable patterns detected** (eval + 3 SQL injections via dynamic dispatch)
- ✅ **1 safe pattern** (sanitized input correctly flagged as clean)
- ✅ **Object literal properties** tracked (15+ handler mappings)
- ✅ **Dynamic dispatch** flows reconstructed (req → dispatch → handler → sink)
- ✅ **Shorthand properties** resolved (ES6 syntax)
- ✅ **Nested dispatch** (2-level property access)
- ✅ **Sanitizer detection** (regex replacement removes taint)

**If any of these fail, taint analysis is incomplete.**
