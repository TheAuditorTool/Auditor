# Greenfield API Fixture

## Purpose
Simulates a realistic Python Flask REST API with:
- SQLAlchemy ORM models with bidirectional relationships
- Authentication and authorization middleware
- Raw SQL queries for data analysis
- Multi-source taint flows
- Complex assignment patterns

This fixture is designed to test **advanced TheAuditor capabilities**, particularly junction table queries.

## Framework Patterns Included

### 1. SQLAlchemy ORM Models (models.py)
- **5 models**: Role, User, Product, Order, OrderItem
- **Bidirectional relationships**: 8 relationships with back_populates
- **Foreign keys**: 4 FK constraints with ondelete behaviors
- **Cascade delete flags**: Order → OrderItem, User → Order
- **Hybrid properties**: User.is_admin computed field
- **Methods as sinks**: User.verify_password(), User.to_dict()

### 2. Authentication Middleware (middleware/auth.py)
- **4 decorators**: @require_auth, @require_role, @require_permission, @rate_limit
- **Parameterized controls**: require_role('admin'), require_permission('products:create')
- **JWT token validation**: Demonstrates taint from request.headers to jwt.decode()
- **Multiple middleware chaining**: Tests api_endpoint_controls with stacked decorators

### 3. Service Layer with Raw SQL (services/user_service.py)
- **6 raw SQL queries**: Not ORM, directly using sqlite3
- **Multi-table JOINs**: Queries touching users, roles, orders, order_items tables
- **Taint sources**: Functions accepting user_id, email, search_term parameters
- **Dynamic query building**: search_users() demonstrates multi-source SQL construction

### 4. API Routes with Controls (products.py)
- **7 Flask routes**: Mix of public and protected endpoints
- **Control variety**:
  - No controls: GET /api/products, GET /api/products/<id> (public)
  - Single control: GET /api/products/search (@require_auth)
  - Dual controls: DELETE /api/products/<id> (@require_auth + @require_role)
  - Triple controls: POST /api/products (@require_auth + @require_role + @require_permission)
- **Raw SQL in routes**: search_products() and get_product_analytics() use direct queries
- **Multi-source assignments**: search query building from multiple request params

## Populated Database Tables

After running `aud index`, the following junction tables are populated:

| Table | Count | What It Tests |
|---|---|---|
| **python_orm_models** | 5 | Model extraction (Role, User, Product, Order, OrderItem) |
| **python_orm_fields** | 32 | Field extraction with PK/FK flags |
| **orm_relationships** | 8 | Bidirectional relationships with cascade flags |
| **python_routes** | 7 | Flask route extraction |
| **api_endpoint_controls** | 6+ | Decorator tracking (auth, role, permission, rate_limit) |
| **sql_queries** | 6 | Raw SQL query extraction |
| **sql_query_tables** | 0* | Table references in SQL (parser limitation) |
| **assignment_sources** | 364 | Multi-source assignments |
| **function_return_sources** | 162 | Cross-function taint flows |

**Note**: sql_query_tables extraction is not yet implemented for Python SQL strings.

## Sample JOIN Queries

### Query 1: Find Endpoints Missing Authentication

```sql
SELECT
    pr.pattern,
    pr.method,
    pr.handler_function
FROM python_routes pr
LEFT JOIN api_endpoint_controls aec
    ON pr.file = aec.endpoint_file AND pr.line = aec.endpoint_line
WHERE aec.control_name IS NULL  -- No controls at all
ORDER BY pr.pattern;
```

**Expected Results**: 2 endpoints (GET /api/products, GET /api/products/<id>)

### Query 2: Find Endpoints with Multiple Controls

```sql
SELECT
    pr.pattern,
    pr.handler_function,
    GROUP_CONCAT(aec.control_name, ', ') AS controls,
    COUNT(aec.control_name) AS control_count
FROM python_routes pr
LEFT JOIN api_endpoint_controls aec
    ON pr.file = aec.endpoint_file AND pr.line = aec.endpoint_line
GROUP BY pr.file, pr.line
HAVING control_count > 1
ORDER BY control_count DESC;
```

**Expected Results**: create_product (3 controls: require_auth, require_role, require_permission)

### Query 3: Track ORM Relationships with Cascade Delete

```sql
SELECT
    source_model,
    as_name,
    target_model,
    relationship_type,
    cascade_delete
FROM orm_relationships
WHERE cascade_delete = 1
ORDER BY source_model, as_name;
```

**Expected Results**:
- Order.items → OrderItem (cascade)
- Order.user → User (cascade)
- User.orders → Order (cascade)

### Query 4: Find Models Exposing PII in Methods

```sql
-- Find User model fields that might be exposed
SELECT
    pof.model_name,
    pof.field_name,
    pof.field_type
FROM python_orm_fields pof
WHERE pof.model_name = 'User'
    AND pof.field_name IN ('email', 'password_hash')
ORDER BY pof.field_name;
```

**Expected Results**: email and password_hash fields (potential data leaks in to_dict())

### Query 5: Multi-Source Assignment Detection

```sql
SELECT
    a.file,
    a.line,
    a.target_var,
    COUNT(asrc.source_var_name) AS source_count,
    GROUP_CONCAT(asrc.source_var_name, ', ') AS sources
FROM assignments a
JOIN assignment_sources asrc
    ON a.file = asrc.assignment_file
    AND a.line = asrc.assignment_line
    AND a.target_var = asrc.assignment_target
WHERE a.file LIKE '%products.py'
GROUP BY a.file, a.line, a.target_var
HAVING source_count > 1
ORDER BY source_count DESC
LIMIT 5;
```

**Expected Results**: query variable built from base_query, where_conditions, params (3+ sources)

## Use Cases

This fixture supports testing:

1. **ORM Extraction**
   - Test that all 5 models are extracted
   - Verify bidirectional relationships tracked
   - Confirm FK constraints with cascade flags

2. **API Security Analysis**
   - Find endpoints without authentication
   - Detect endpoints with admin-only controls
   - Verify permission-based access control

3. **SQL Query Tracking**
   - List all raw SQL queries in codebase
   - Find queries touching sensitive tables (users, roles)
   - Detect dynamic SQL construction patterns

4. **Taint Analysis**
   - Track user input from request params to SQL queries
   - Follow taint across function boundaries (via function_return_sources)
   - Detect multi-source taint in assignment_sources

5. **Rule Development**
   - Test "Find unauth endpoints" rule
   - Test "Find models exposing PII" rule
   - Test "Detect SQL injection risk" rule

## Testing the Fixture

### Index the Fixture

```bash
cd tests/fixtures/planning/greenfield-api
aud init
```

**Expected Output**:
- 7 files indexed
- 254+ symbols
- 7 routes
- 6+ SQL queries
- 119+ assignments

### Verify Junction Tables

```bash
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

tables = ['python_orm_models', 'orm_relationships', 'api_endpoint_controls', 'sql_queries']
for table in tables:
    c.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'{table}: {c.fetchone()[0]} rows')
"
```

**Expected Counts**:
- python_orm_models: 5
- orm_relationships: 8
- api_endpoint_controls: 6+
- sql_queries: 6

### Run Verification Spec

```bash
# Using planning workflow
aud planning init --name "Test Greenfield API"
aud planning add-task 1 --title "Verify API" --spec spec.yaml
aud planning verify-task 1 1 --verbose
```

**Expected**: All 10 rules PASS (ORM models, relationships, endpoints, SQL queries, assignments)

## Advanced Queries for Development

### Find All Cascade Delete Paths

```sql
-- Find models that will cascade delete when User is deleted
WITH RECURSIVE cascade_chain AS (
    -- Base: Direct relationships from User with cascade
    SELECT source_model, target_model, as_name, 1 AS depth
    FROM orm_relationships
    WHERE source_model = 'User' AND cascade_delete = 1

    UNION

    -- Recursive: Follow cascade chain
    SELECT r.source_model, r.target_model, r.as_name, cc.depth + 1
    FROM cascade_chain cc
    JOIN orm_relationships r ON cc.target_model = r.source_model
    WHERE r.cascade_delete = 1 AND cc.depth < 3
)
SELECT * FROM cascade_chain ORDER BY depth, source_model;
```

### Find Endpoints Without Permission Checks

```sql
SELECT
    pr.pattern,
    pr.method,
    pr.handler_function,
    GROUP_CONCAT(aec.control_name, ', ') AS controls
FROM python_routes pr
LEFT JOIN api_endpoint_controls aec
    ON pr.file = aec.endpoint_file AND pr.line = aec.endpoint_line
WHERE pr.method IN ('POST', 'PUT', 'DELETE')  -- Mutating operations
GROUP BY pr.file, pr.line
HAVING controls NOT LIKE '%require_permission%'
ORDER BY pr.method, pr.pattern;
```

## File Structure

```
greenfield-api/
├── src/
│   ├── models.py                # 5 ORM models with relationships
│   ├── products.py              # 7 Flask routes with controls
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth.py              # 4 authentication decorators
│   └── services/
│       ├── __init__.py
│       └── user_service.py      # 6 raw SQL query functions
├── spec.yaml                    # 10 SQL-based verification rules
└── README.md                    # This file
```

## What Makes This Fixture Good

### Dense Pattern Coverage
- Not minimal test cases - realistic full-featured API
- Multiple patterns per file (not one pattern per file)
- Real framework usage (not synthetic examples)

### Junction Table Focus
- Every feature is designed to populate junction tables
- Tests actual JOIN queries, not just symbol existence
- Demonstrates the VALUE of schema normalization work

### Reusable for Downstream Development
- Rule developers can test against this database
- Query optimization can benchmark against realistic data
- Documentation shows "what TheAuditor extracts"

## Limitations

1. **sql_query_tables Empty**: Python SQL string table extraction not yet implemented
2. **@require_auth Missing**: Decorator on separate line from @route not tracked (parser limitation)
3. **No Actual Database**: Models defined but no migrations/seed data (AST extraction only)

These are KNOWN LIMITATIONS of the parser, not deficiencies in the fixture code.

---

**Last Updated**: 2025-10-31
**Status**: PRODUCTION READY
**Test Coverage**: 7 capabilities (ORM, API security, SQL queries, taint flows, multi-source, decorators, relationships)
