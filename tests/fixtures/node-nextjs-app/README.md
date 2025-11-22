# Node Next.js App Fixture

Next.js full-stack fixture for testing API routes, middleware, SSR patterns, and complex taint flows across Next.js framework.

## Purpose

Simulates a production Next.js application with:
- Dynamic API routes (`/api/users/[id]`)
- API route middleware (authentication)
- Next.js Edge middleware with rate limiting
- Server-side rendering with `getServerSideProps`
- Multi-source taint flows (query params + body + route params)
- Raw SQL queries with JOINs across multiple tables
- SQL transactions spanning multiple tables
- Security vulnerabilities (SQL injection, missing validation)

## Framework Patterns Included

### 1. Dynamic API Routes: `/api/users/[id]` (130 lines)

**Pattern**: Next.js dynamic route with authentication middleware

```javascript
// pages/api/users/[id].js
export default requireAuth(async function handler(req, res) {
  const { id } = req.query; // TAINT SOURCE: Dynamic route parameter

  switch (req.method) {
    case 'GET':
      // TAINT FLOW: req.query.id -> getUserById -> SQL SELECT users
      const user = await getUserById(parseInt(id));
      return res.json({ user });

    case 'PUT':
      // MULTI-SOURCE TAINT: id (route) + body (request) -> SQL UPDATE
      const { username, email, bio } = req.body;
      await pool.query('UPDATE users SET username = $1, email = $2, bio = $3 WHERE id = $4',
        [username, email, bio, parseInt(id)]);
      return res.json({ user });
  }
});
```

**Tests**:
- Dynamic route extraction: `[id]` pattern
- api_endpoint_controls: requireAuth middleware
- Taint flows: route param → SQL query
- Multi-source taint: route param + request body → SQL UPDATE

### 2. Products Search API: `/api/products` (83 lines)

**Pattern**: Multi-source taint with dynamic query building

```javascript
// pages/api/products.js
export default async function handler(req, res) {
  const {
    search,    // TAINT SOURCE 1: Search term
    category,  // TAINT SOURCE 2: Category filter
    minPrice,  // TAINT SOURCE 3: Min price
    maxPrice   // TAINT SOURCE 4: Max price
  } = req.query;

  // MULTI-SOURCE TAINT: All query params -> searchProducts -> SQL
  const products = await searchProducts(search, category, minPrice, maxPrice);
  return res.json({ products });
}
```

**Database function**:
```javascript
async function searchProducts(searchTerm, category, minPrice, maxPrice) {
  let query = `
    SELECT p.*, c.name AS category_name, AVG(r.rating) AS avg_rating
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    LEFT JOIN reviews r ON p.id = r.product_id
  `;

  const conditions = [];
  const params = [];

  if (searchTerm) {
    conditions.push(`(p.name ILIKE $1 OR p.description ILIKE $2)`);
    params.push(`%${searchTerm}%`, `%${searchTerm}%`);
  }
  // ... more conditions

  // Touches tables: products, categories, reviews
  return await pool.query(query, params);
}
```

**Tests**:
- Multi-source taint: 4 query params → single SQL query
- sql_query_tables: 3 tables (products, categories, reviews)
- Dynamic query building with parameterized queries

### 3. Orders API: `/api/orders` (117 lines)

**Pattern**: SQL transaction spanning multiple tables

```javascript
// pages/api/orders.js
export default requireAuth(async function handler(req, res) {
  switch (req.method) {
    case 'POST':
      const { items } = req.body; // TAINT SOURCE: Request body

      // TAINT FLOW: req.user.id (token) + req.body.items -> SQL transaction
      const { orderId, totalAmount } = await createOrder(req.user.id, items);
      return res.json({ orderId, totalAmount });
  }
});
```

**Transaction implementation**:
```javascript
async function createOrder(userId, items) {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    // INSERT order
    const orderResult = await client.query(
      'INSERT INTO orders (user_id, total_amount, status) VALUES ($1, $2, $3) RETURNING id',
      [userId, totalAmount, 'pending']
    );

    // INSERT order_items
    for (const item of items) {
      await client.query(
        'INSERT INTO order_items (order_id, product_id, quantity, price) VALUES ($1, $2, $3, $4)',
        [orderId, item.productId, item.quantity, item.price]
      );
    }

    // UPDATE product stock
    for (const item of items) {
      await client.query('UPDATE products SET stock = stock - $1 WHERE id = $2',
        [item.quantity, item.productId]);
    }

    await client.query('COMMIT');
    // Touches tables: orders, order_items, products
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  }
}
```

**Tests**:
- SQL transaction with BEGIN/COMMIT/ROLLBACK
- sql_query_tables: 3 tables in single transaction
- Taint from authenticated user + request body

### 4. Next.js Middleware: `middleware.js` (108 lines)

**Pattern**: Edge runtime middleware with rate limiting

```javascript
// middleware.js
export function middleware(request) {
  const { pathname } = request.nextUrl;

  // TAINT SOURCE: Client IP address
  const ip = request.ip || request.headers.get('x-forwarded-for') || 'unknown';

  // Apply rate limiting to API routes
  if (pathname.startsWith('/api/')) {
    const { allowed, remaining } = checkRateLimit(ip, 100, 60000);

    if (!allowed) {
      return NextResponse.json(
        { error: 'Too many requests' },
        { status: 429 }
      );
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/api/:path*', '/((?!_next/static|_next/image|favicon.ico).*)']
};
```

**Tests**:
- Next.js middleware extraction
- Edge runtime patterns
- Rate limiting logic
- Request header manipulation

### 5. SSR with `getServerSideProps`: `pages/index.js` (130 lines)

**Pattern**: Server-side rendering with tainted query params

```javascript
// pages/index.js
export async function getServerSideProps(context) {
  const { query } = context;

  // TAINT SOURCES: URL query parameters
  const search = query.search || null;
  const category = query.category || null;
  const minPrice = query.minPrice ? parseFloat(query.minPrice) : null;
  const maxPrice = query.maxPrice ? parseFloat(query.maxPrice) : null;

  // MULTI-SOURCE TAINT: All query params -> searchProducts -> SQL
  const products = await searchProducts(search, category, minPrice, maxPrice);

  return {
    props: { products, filters: { search, category, minPrice, maxPrice } }
  };
}

export default function HomePage({ products, filters }) {
  return (
    <div className="home-page">
      <h1>Product Catalog</h1>
      <div className="product-grid">
        {products.map(product => (
          <div key={product.id} className="product-card">
            <h3>{product.name}</h3>
            <p>${product.price.toFixed(2)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Tests**:
- getServerSideProps extraction
- SSR pattern recognition
- Taint flow: URL params → SSR → database

### 6. Database Service: `lib/database.js` (241 lines)

**Comprehensive SQL patterns**:

#### getUserProfile - Multiple JOINs
```javascript
async function getUserProfile(userId) {
  const query = `
    SELECT
      u.id, u.username, u.email,
      COUNT(DISTINCT o.id) AS order_count,
      SUM(o.total_amount) AS total_spent
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    LEFT JOIN products p ON o.product_id = p.id
    WHERE u.id = $1
    GROUP BY u.id, u.username, u.email
  `;

  // Touches tables: users, orders, products
  return await pool.query(query, [userId]);
}
```

#### adminSearchUsers - VULNERABLE (SQL Injection)
```javascript
async function adminSearchUsers(username) {
  // VULNERABLE: Direct string concatenation
  const query = `
    SELECT u.*, r.name AS role_name
    FROM users u
    LEFT JOIN roles r ON u.role_id = r.id
    WHERE u.username LIKE '%${username}%'
  `;

  // Attacker can inject: ' OR '1'='1' --
  return await pool.query(query);
}
```

**Tests**:
- 7 database functions with distinct patterns
- sql_query_tables: 9 tables (users, roles, orders, order_items, products, categories, reviews, activity_log)
- SQL injection vulnerability for security pattern detection

## Populated Tables

| Table | Row Count (est) | Purpose |
|---|---|---|
| `api_endpoints` | 5 | Next.js API routes (GET, PUT, POST) |
| `api_endpoint_controls` | 4 | requireAuth middleware entries |
| `sql_queries` | 15+ | Raw SQL queries with JOINs, transactions |
| `sql_query_tables` | 30+ | Junction table (query → table mappings) |
| `symbols` | 15+ | Functions, API handlers, middleware |
| `function_calls` | 20+ | Database function calls, middleware calls |

## Sample Verification Queries

### Find dynamic API routes

```sql
SELECT
  method,
  pattern,
  file,
  line
FROM api_endpoints
WHERE file LIKE '%node-nextjs-app%'
  AND pattern LIKE '%[id]%'
ORDER BY file, line;
```

**Expected**: 2 routes (GET /api/users/[id], PUT /api/users/[id])

### Find SQL queries with multiple table JOINs

```sql
SELECT
  sq.file_path,
  sq.line_number,
  GROUP_CONCAT(DISTINCT sqt.table_name, ', ') AS tables_touched
FROM sql_queries sq
JOIN sql_query_tables sqt
  ON sq.file_path = sqt.query_file
  AND sq.line_number = sqt.query_line
WHERE sq.file_path LIKE '%node-nextjs-app%'
GROUP BY sq.file_path, sq.line_number
HAVING COUNT(DISTINCT sqt.table_name) > 1
ORDER BY sq.file_path, sq.line_number;
```

**Expected**: 4+ queries (getUserProfile touches 3 tables, searchProducts touches 3 tables, etc.)

### Find API routes with authentication middleware

```sql
SELECT
  ae.method,
  ae.pattern,
  aec.control_name,
  ae.file
FROM api_endpoints ae
JOIN api_endpoint_controls aec
  ON ae.file = aec.endpoint_file
  AND ae.line = aec.endpoint_line
WHERE ae.file LIKE '%node-nextjs-app%'
ORDER BY ae.file, ae.line;
```

**Expected**: 4 endpoints with requireAuth (GET/PUT /api/users/[id], POST/GET /api/orders)

### Detect SQL injection vulnerability

```sql
SELECT
  file_path,
  line_number,
  query_text
FROM sql_queries
WHERE file_path LIKE '%node-nextjs-app%'
  AND query_text LIKE '%${%'
ORDER BY file_path, line_number;
```

**Expected**: 1 query (adminSearchUsers with string concatenation)

### Find multi-source taint in API routes

```sql
SELECT
  fc.function_name,
  fc.callee_function,
  fc.file,
  fc.line
FROM function_calls fc
WHERE fc.file LIKE '%node-nextjs-app%'
  AND fc.callee_function LIKE '%searchProducts%'
ORDER BY fc.file, fc.line;
```

**Expected**: 2+ calls (pages/api/products.js, pages/index.js getServerSideProps)

## Testing Use Cases

1. **Next.js API Routes**: Verify static and dynamic route extraction
2. **API Middleware**: Test api_endpoint_controls with requireAuth wrapper
3. **Edge Middleware**: Test Next.js middleware.js with rate limiting
4. **SSR Patterns**: Test getServerSideProps extraction
5. **Multi-Source Taint**: Test query params + body + route params → SQL
6. **SQL Transactions**: Test BEGIN/COMMIT/ROLLBACK with multiple tables
7. **SQL Joins**: Test sql_query_tables with 3+ table JOINs
8. **Security Patterns**: Test SQL injection detection

## How to Use

### 1. Index from TheAuditor Root

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud index
```

### 2. Query Extracted Data

```bash
# Find all Next.js API routes
aud context query --table api_endpoints --filter "file LIKE '%node-nextjs-app%'"

# Find SQL queries with JOINs
aud context query --table sql_query_tables --filter "query_file LIKE '%node-nextjs-app%'" --group-by query_line
```

### 3. Run Security Pattern Detection

```bash
# Detect SQL injection vulnerabilities
aud detect-patterns --rule sql-injection --file tests/fixtures/node-nextjs-app/
```

## Files Structure

```
node-nextjs-app/
├── package.json              # Next.js 14.x dependencies
├── lib/
│   └── database.js           # 7 SQL functions with JOINs (241 lines)
├── pages/
│   ├── index.js              # SSR page with getServerSideProps (130 lines)
│   └── api/
│       ├── users/
│       │   └── [id].js       # Dynamic API route (130 lines)
│       ├── products.js       # Products search API (83 lines)
│       └── orders.js         # Orders API with transactions (117 lines)
├── middleware.js             # Edge middleware with rate limiting (108 lines)
├── spec.yaml                 # 16 verification rules (374 lines)
└── README.md                 # This file

Total: 809 lines of Next.js code
```

## Security Patterns

### 1. SQL Injection (CRITICAL)

**Location**: `lib/database.js:adminSearchUsers`

**Vulnerable Pattern**:
```javascript
async function adminSearchUsers(username) {
  // VULNERABLE: Direct string concatenation
  const query = `SELECT * FROM users WHERE username LIKE '%${username}%'`;
  return await pool.query(query);
}
```

**Attack Vector**:
```javascript
// URL: /api/admin/search?username=' OR '1'='1' --
adminSearchUsers("' OR '1'='1' --");
// Query becomes: SELECT * FROM users WHERE username LIKE '%' OR '1'='1' --%'
```

**Impact**: Full database compromise, data theft, privilege escalation

### 2. Tainted Route Parameters (MEDIUM)

**Location**: `pages/api/users/[id].js`

**Vulnerable Pattern**:
```javascript
export default async function handler(req, res) {
  const { id } = req.query; // id from URL (user-controlled)
  const user = await getUserById(parseInt(id)); // Direct usage
}
```

**Attack Vector**:
```
// URL: /api/users/999
// Attacker can access any user's data by changing URL parameter
```

**Impact**: Horizontal privilege escalation (access other users' data)

### 3. Multi-Source Taint (MEDIUM)

**Location**: `pages/api/products.js`

**Pattern**:
```javascript
const { search, category, minPrice, maxPrice } = req.query;
const products = await searchProducts(search, category, minPrice, maxPrice);
// All 4 params flow into dynamic SQL query building
```

**Impact**: Increased SQL injection risk, complex validation needed

## Advanced Capabilities Tested

From test_enhancements.md, this fixture tests **5 of 7** advanced capabilities:

1. ✅ **API Security Coverage** - api_endpoint_controls with requireAuth middleware
2. ✅ **SQL Query Surface Area** - sql_query_tables with 9 tables, 15+ queries
3. ✅ **Multi-Source Taint Origin** - Query params + body + route params → SQL
4. ❌ **React Hook Dependencies** - N/A (Next.js API routes, no client hooks)
5. ✅ **Cross-Function Taint Flow** - API route → database function → SQL query
6. ✅ **Import Chain Analysis** - import { getUserById } from '../../../lib/database'
7. ❌ **React Hook Anti-Patterns** - N/A (server-side only)

**Next.js-specific capabilities**:
- ✅ Dynamic API route extraction ([id] pattern)
- ✅ API route middleware chains
- ✅ Edge middleware patterns
- ✅ getServerSideProps SSR data fetching
- ✅ SQL transactions across multiple tables

## Comparison to Test Requirements

From test_enhancements.md (lines 185-230), this fixture covers:

| Requirement | Status | Evidence |
|---|---|---|
| Next.js API routes | ✅ | 5 API routes (static + dynamic) |
| Dynamic routes [id] | ✅ | /api/users/[id] with GET/PUT |
| API middleware | ✅ | requireAuth wrapper function |
| Edge middleware | ✅ | middleware.js with rate limiting |
| getServerSideProps | ✅ | pages/index.js SSR data fetching |
| Multi-source taint | ✅ | 4 query params → searchProducts |
| SQL transactions | ✅ | createOrder with BEGIN/COMMIT |
| sql_query_tables | ✅ | 30+ junction table entries |
| SQL injection | ✅ | adminSearchUsers vulnerability |

## Taint Flow Paths

### Path 1: Route Param → SQL Query

```
req.query.id (SOURCE - dynamic route param)
  → getUserById(parseInt(id)) (PROPAGATION)
  → pool.query('SELECT * FROM users WHERE id = $1', [userId]) (SINK)
```

### Path 2: Multi-Source Query Params → SQL

```
req.query.{search, category, minPrice, maxPrice} (SOURCES - 4 inputs)
  → searchProducts(search, category, minPrice, maxPrice) (PROPAGATION)
  → Dynamic SQL query building with conditions (SINK)
```

### Path 3: Authenticated User + Request Body → Transaction

```
req.user.id (SOURCE 1 - from JWT token)
req.body.items (SOURCE 2 - POST body)
  → createOrder(req.user.id, items) (PROPAGATION)
  → SQL transaction: INSERT orders + INSERT order_items + UPDATE products (SINK)
```

### Path 4: SSR Query Params → Database

```
context.query.{search, category, minPrice, maxPrice} (SOURCES - URL params)
  → getServerSideProps(context) (PROPAGATION - SSR)
  → searchProducts(...) → SQL query (SINK)
```

## Related Documentation

- [test_enhancements.md](../../../test_enhancements.md) - Next.js patterns (lines 185-230)
- [FIXTURE_ASSESSMENT.md](../../../FIXTURE_ASSESSMENT.md) - Node ecosystem status
- [node-express-api](../node-express-api/) - Express REST API fixture
- [node-react-app](../node-react-app/) - React SPA fixture

---

**Created**: 2025-10-31
**Total Code**: 809 lines (exceeds 600+ target)
**Language**: JavaScript (Next.js)
**Framework**: Next.js 14.x
**Patterns Tested**: API routes, middleware, SSR, transactions, SQL injection
