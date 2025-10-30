# Node Express API Fixture

Express REST API fixture for testing middleware chains, authentication controls, and SQL taint flows in Node.js applications.

## Purpose

Simulates a production Express.js REST API with:
- Middleware chains (authentication, authorization, rate limiting)
- Multiple authentication patterns (JWT verification, role-based access control, permissions)
- Raw SQL queries with PostgreSQL
- Taint flows from user input → SQL queries
- Multi-source taint assignments
- Security vulnerabilities (SQL injection, missing auth)

## Framework Patterns Included

### 1. Express Middleware Chains

**File**: `middleware/auth.js` (150 lines)

- **requireAuth**: JWT token verification from Authorization header
- **requireRole(role)**: Role-based access control (RBAC)
- **requirePermission(permission)**: Fine-grained permission checking
- **rateLimit(requestsPerMinute)**: Rate limiting middleware

**Example**:
```javascript
router.post('/api/products',
  requireAuth,              // Middleware 1: Verify JWT
  requireRole('admin'),     // Middleware 2: Check admin role
  async (req, res) => {     // Route handler
    // Create product
  }
);
```

### 2. Raw SQL Queries

**File**: `services/database.js` (185 lines)

- **getUserByEmail(email)**: Query 'users' table
- **getAdminUsers()**: JOIN query touching 'users' + 'roles' tables
- **searchUsers(searchTerm, roleFilter)**: Multi-source dynamic query building
- **getUserOrderStats(userId)**: Aggregation query across 'orders' + 'order_items'
- **logUserActivity(userId, action, details)**: INSERT into 'activity_log'
- **vulnerableSearch(username)**: SQL injection vulnerability example

**Example**:
```javascript
async function searchUsers(searchTerm, roleFilter) {
  // MULTI-SOURCE ASSIGNMENT: query built from multiple variables
  let query = 'SELECT ... FROM users u LEFT JOIN roles r ...';
  // Dynamic WHERE clause based on inputs
  // Taint flow: searchTerm + roleFilter → SQL query
}
```

### 3. Express Routes with Authentication

**File**: `routes/products.js` (167 lines)

5 routes demonstrating different authentication patterns:

| Route | Method | Middleware | Taint Flow |
|---|---|---|---|
| `/api/products` | GET | requireAuth, rateLimit | req.query.search → SQL LIKE |
| `/api/products` | POST | requireAuth, requireRole('admin') | req.body → SQL INSERT |
| `/api/products/:id` | PUT | requireAuth, requirePermission | req.params.id + req.body → SQL UPDATE |
| `/api/products/:id` | DELETE | requireAuth, requireRole('admin') | req.params.id → SQL DELETE |
| `/api/products/search` | GET | NONE (vulnerable) | req.query.term → SQL injection |

### 4. Taint Flow Patterns

**Sources**:
- `req.query.*` - Query string parameters
- `req.params.*` - URL path parameters
- `req.body.*` - JSON request body
- `process.env.*` - Environment variables

**Sinks**:
- `pool.query(sql)` - PostgreSQL query execution
- SQL string concatenation (vulnerable)

**Example Taint Path**:
```
req.query.search (SOURCE)
  → searchTerm variable (PROPAGATION)
  → SQL query string (SINK)
```

### 5. Security Vulnerabilities (Intentional)

**SQL Injection (CRITICAL)**:
```javascript
// routes/products.js:149
const vulnerableQuery = `SELECT * FROM products WHERE name LIKE '%${searchTerm}%'`;
```

**Missing Authentication (HIGH)**:
```javascript
// routes/products.js:145 - NO requireAuth middleware
router.get('/api/products/search', async (req, res) => { ... });
```

## Populated Tables

| Table | Row Count (est) | Purpose |
|---|---|---|
| `api_endpoints` | 5 | Express routes |
| `api_endpoint_controls` | 9+ | Middleware chains (requireAuth, requireRole, etc.) |
| `sql_queries` | 10+ | Raw SQL queries |
| `sql_query_tables` | 15+ | Table references (users, roles, orders, activity_log) |
| `assignment_sources` | 20+ | Multi-source taint tracking |
| `function_calls` | 30+ | Database calls, middleware calls |
| `symbols` | 20+ | Functions (middleware, routes, database) |

## Sample Verification Queries

### Find endpoints without authentication

```sql
SELECT ae.method, ae.pattern, ae.file, ae.line
FROM api_endpoints ae
LEFT JOIN api_endpoint_controls aec
  ON ae.file = aec.endpoint_file AND ae.line = aec.endpoint_line
WHERE ae.file LIKE '%node-express-api%'
  AND aec.control_name IS NULL;
```

**Expected**: 1 endpoint (GET /api/products/search)

### Find SQL queries with JOINs

```sql
SELECT
  sq.file_path,
  sq.line_number,
  GROUP_CONCAT(DISTINCT sqt.table_name, ', ') AS tables_touched
FROM sql_queries sq
JOIN sql_query_tables sqt
  ON sq.file_path = sqt.query_file AND sq.line_number = sqt.query_line
WHERE sq.file_path LIKE '%node-express-api%'
GROUP BY sq.file_path, sq.line_number
HAVING COUNT(DISTINCT sqt.table_name) > 1;
```

**Expected**: 2+ queries (getAdminUsers, searchUsers, getUserOrderStats)

### Find endpoints with multiple middleware

```sql
SELECT
  ae.method,
  ae.pattern,
  GROUP_CONCAT(aec.control_name, ', ') AS controls
FROM api_endpoints ae
JOIN api_endpoint_controls aec
  ON ae.file = aec.endpoint_file AND ae.line = aec.endpoint_line
WHERE ae.file LIKE '%node-express-api%'
GROUP BY ae.file, ae.line
HAVING COUNT(aec.control_name) > 1;
```

**Expected**: 4 routes (all except /search have multiple middleware)

### Track taint from request to SQL

```sql
SELECT
  a.target,
  a.source_expr,
  a.file,
  a.line
FROM assignments a
WHERE a.file LIKE '%node-express-api/routes/%'
  AND (
    a.source_expr LIKE '%req.query%'
    OR a.source_expr LIKE '%req.params%'
    OR a.source_expr LIKE '%req.body%'
  )
ORDER BY a.file, a.line;
```

**Expected**: 6+ taint sources from Express requests

## Testing Use Cases

1. **API Security Rules**: Test "find endpoints missing authentication" rule
2. **SQL Injection Detection**: Test taint flow from req.query → SQL concatenation
3. **Middleware Extraction**: Verify Express middleware chains are tracked
4. **Multi-Source Taint**: Test assignments from multiple request properties
5. **Role-Based Access Control**: Verify RBAC middleware is extracted
6. **Rate Limiting**: Test non-auth control extraction

## How to Use

### 1. Index from TheAuditor Root

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud index
```

### 2. Query Extracted Data

```bash
# Find all Express routes
aud context query --table api_endpoints --filter "file LIKE '%node-express-api%'"

# Find SQL injection vulnerabilities
aud detect-patterns --rule sql-injection --file tests/fixtures/node-express-api/
```

### 3. Verify Fixture Coverage

```bash
# Run verification queries from spec.yaml
aud planning verify-task <task_id> <verification_id> --verbose
```

## Files Structure

```
node-express-api/
├── app.js                    # Main Express app (67 lines)
├── package.json              # Dependencies
├── middleware/
│   └── auth.js               # 4 authentication middleware functions (150 lines)
├── services/
│   └── database.js           # 7 raw SQL functions (185 lines)
├── routes/
│   └── products.js           # 5 Express routes with middleware chains (167 lines)
├── spec.yaml                 # Verification rules (180 lines)
└── README.md                 # This file

Total: 569 lines of Express/Node.js code
```

## Security Patterns

### 1. SQL Injection (CRITICAL)

**Location**: `routes/products.js:149`

**Vulnerable Code**:
```javascript
const vulnerableQuery = `SELECT * FROM products WHERE name LIKE '%${searchTerm}%'`;
```

**Attack Vector**: User can inject SQL via `req.query.term`

**Example Exploit**:
```
GET /api/products/search?term=%' OR '1'='1
```

### 2. Missing Authentication (HIGH)

**Location**: `routes/products.js:145`

**Issue**: GET /api/products/search has NO authentication middleware

**Impact**: Anyone can access and exploit the SQL injection

## Advanced Capabilities Tested

From test_enhancements.md, this fixture tests **4 of 7** advanced capabilities:

1. ✅ **API Security Coverage** - api_endpoint_controls with middleware chains
2. ✅ **SQL Query Surface Area** - sql_query_tables for users, roles, orders
3. ✅ **Multi-Source Taint Origin** - assignment_sources from req.params + req.body
4. ❌ **React Hook Dependencies** - Not applicable (Node backend)
5. ❌ **Cross-Function Taint Flow** - Partially (req → route → database, but not across returns)
6. ✅ **Import Chain Analysis** - import_style_names for middleware → routes
7. ❌ **React Hook Anti-Patterns** - Not applicable (Node backend)

## Comparison to Python greenfield-api

Both fixtures test similar patterns in different languages:

| Feature | Python (Flask) | Node (Express) |
|---|---|---|
| Middleware | `@require_auth` decorator | `requireAuth` function |
| Routes | Flask blueprints | Express router |
| ORM | SQLAlchemy models | Raw SQL (Postgres) |
| Auth | JWT + bcrypt | JWT + bcrypt |
| Taint Sources | `request.args` | `req.query` |

**Node-specific patterns**:
- Middleware as functions (not decorators)
- Callback-based middleware chains
- `next()` propagation

## Related Documentation

- [test_enhancements.md](../../../test_enhancements.md) - Express patterns (lines 313-342)
- [FIXTURE_ASSESSMENT.md](../../../FIXTURE_ASSESSMENT.md) - Node ecosystem status
- [greenfield-api](../../planning/greenfield-api/) - Python equivalent

---

**Created**: 2025-10-31
**Total Code**: 569 lines (meets 500+ target)
**Language**: JavaScript (Node.js)
**Framework**: Express 4.x
