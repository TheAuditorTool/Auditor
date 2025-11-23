# Boundary Analysis Design

## Overview

Boundary analysis detects **where trust boundaries exist in code** and **whether they're enforced correctly**. This is critical for:

- **Multi-tenant SaaS**: Tenant isolation (RLS enforcement)
- **Input validation**: External data validation before use
- **Authorization**: Permission checks before protected operations
- **Sanitization**: User input sanitization before sensitive sinks

## Core Concept: Boundary Distance

**Distance** = Number of function calls between entry point and control point

```
Distance 0 (PERFECT):
    @app.post('/user')
    def create_user(data: UserSchema):  # ← Validation IN signature
        db.insert(data)

Distance 1 (GOOD):
    @app.post('/user')
    def create_user(request):
        data = validate(request.json)   # ← First line validates
        db.insert(data)

Distance 3 (BAD):
    @app.post('/user')
    def create_user(request):
        service.create(request.json)    # ← Distance 1
            def create(data):
                process(data)            # ← Distance 2
                    def process(data):
                        validate(data)   # ← Distance 3 (TOO LATE!)
```

## Why Distance Matters

**Low Distance** (0-1):
- Data validated before spreading
- Single validation point (consistent)
- Easy to audit
- Hard to bypass

**High Distance** (3+):
- Data spreads to multiple code paths before validation
- Partial validation (some paths skip it)
- Hard to audit (validation buried deep)
- Easy to bypass (call process() directly)

## Real-World Example: Multi-Tenant RLS

### BAD (Distance = 2):
```javascript
// Entry point - tenant_id from user input (UNTRUSTED)
app.get('/api/documents', (req, res) => {
    const tenantId = req.query.tenant_id;  // ← USER CONTROLLED!
    documentService.getAll(tenantId);       // ← Distance 1
        function getAll(tenantId) {
            db.query('SELECT * FROM docs WHERE tenant_id = ?', [tenantId]);  // ← Distance 2
        }
});

// VIOLATION: User can pass ANY tenant_id and access other tenants' data
```

### GOOD (Distance = 0):
```javascript
// Tenant ID from auth token (TRUSTED)
app.get('/api/documents', authenticateUser, (req, res) => {
    const tenantId = req.user.tenantId;    // ← FROM AUTH MIDDLEWARE (distance 0)
    db.query('SELECT * FROM docs WHERE tenant_id = ?', [tenantId]);
});

// SECURE: tenantId source is authenticated, not user-controlled
```

## Architecture

### 1. Distance Calculator (`boundaries/distance.py`)

Core algorithm:
```python
def calculate_distance(entry_file, entry_line, control_file, control_line):
    """
    1. Find function containing entry point
    2. Find function containing control point
    3. BFS through call_graph table
    4. Return shortest path distance
    """
```

### 2. Boundary Analyzers (one per boundary type)

Each analyzer defines:
- **Entry Points**: Where to measure from (HTTP routes, CLI commands, etc.)
- **Control Patterns**: What to look for (validate, sanitize, check_permission, etc.)
- **Violation Rules**: When distance is too high or control missing

Implemented:
- ✅ `boundary_analyzer.py` - Validates entry points have validation
- ✅ `multi_tenant_analyze.py` (existing) - RLS enforcement for multi-tenant

Planned:
- ⏳ `authorization_analyzer.py` - Auth checks at protected endpoints
- ⏳ `sanitization_analyzer.py` - XSS/SQL injection prevention
- ⏳ `output_encoding_analyzer.py` - Safe data rendering

### 3. CLI Command: `aud boundaries`

```bash
# Analyze all boundary types
aud boundaries

# Specific boundary type
aud boundaries --type input-validation
aud boundaries --type multi-tenant
aud boundaries --type authorization

# Output format
aud boundaries --format json
aud boundaries --format report
```

## Output Example

```
=== INPUT VALIDATION BOUNDARY ANALYSIS ===

Entry Points Analyzed: 47
  Clear Boundaries:      21 (45%)
  Acceptable Boundaries: 12 (26%)
  Fuzzy Boundaries:       8 (17%)
  Missing Boundaries:     6 (13%)

Boundary Score: 70%

❌ CRITICAL VIOLATIONS (6):

1. POST /api/products
   File: src/routes/products.js:34
   Issue: Entry point has no input validation
   Fix: Add schema validation at entry point

2. POST /api/users
   File: src/routes/users.js:56
   Issue: Validation at distance 3 - data may have spread
   Path: create_user → processUser → validateUser
   Fix: Move validation to entry point

✅ GOOD PATTERNS (21):

1. POST /api/orders
   File: src/routes/orders.js:23
   Validation: OrderSchema (distance: 0)
   Single validation at entry point (perfect boundary)
```

## Database Schema (Future)

Store boundary analysis results for trend tracking:

```sql
CREATE TABLE boundary_analysis (
    id INTEGER PRIMARY KEY,
    analysis_date TEXT,
    boundary_type TEXT,        -- 'input-validation', 'multi-tenant', 'authorization'

    entry_point TEXT,          -- Route/command name
    entry_file TEXT,
    entry_line INTEGER,

    control_function TEXT,     -- Validation/auth function
    control_file TEXT,
    control_line INTEGER,

    distance INTEGER,          -- Call chain distance (0 = perfect, NULL = missing)
    quality TEXT,              -- 'clear', 'acceptable', 'fuzzy', 'missing'

    violations TEXT,           -- JSON array of violation details
    severity TEXT              -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
);
```

## Integration with Existing Features

### 1. `aud blueprint` - Show boundary architecture
```
=== ARCHITECTURAL BOUNDARIES ===

Entry Layer (HTTP Routes)
  ↓ [Validation: distance 0] ✅
Service Layer
  ↓
Data Layer
```

### 2. `aud context query` - Answer boundary questions
```bash
aud context query --boundary "/api/users"

Shows:
- Entry point details
- Validation points and distances
- Auth checks
- Data flow to sinks
```

### 3. `aud taint-analyze` - Boundary-aware taint analysis
```
Taint flow detected:
  Source: req.body (line 34)
  Sink: db.query() (line 45)
  Distance to validation: 3 (HIGH RISK - validated too late)
  Recommendation: Move validation to line 35 (distance 0)
```

## Project-Agnostic Detection

We use **semantic patterns** from the database, not hardcoded library checks:

**Validation Patterns**:
- Any call to `.validate()`, `.parse()`, `.check()`, `.sanitize()`
- Schema classes: Pydantic, Joi, Zod, Yup, Marshmallow
- Type checking: `isinstance()`, TypeScript interfaces
- `python_validators` table (auto-detected validators)

**Auth Patterns**:
- Decorators: `@*auth*`, `@*permission*`, `@*login_required*`
- Property access: `req.user`, `req.session`, `ctx.state.user`
- Functions: `*verify*`, `*authenticate*`, `*authorize*`

**RLS Patterns**:
- Tenant fields: `tenant_id`, `facility_id`, `organization_id`
- RLS context: `SET LOCAL app.current_tenant_id`
- Trusted sources: `req.user.tenantId` (from auth middleware)
- Untrusted sources: `req.query.tenant_id` (from user input)

## Why This Matters

### The "Joi/Zod Triple Handlers" Problem

What happens without boundary analysis:
1. Add validation library (Joi, Zod, etc.)
2. Validation scattered across codebase
3. **Some code paths skip validation**
4. **Validation happens AFTER data used**
5. False sense of security ("we have validation!")

What boundary analysis catches:
1. ❌ Missing validation (some entry points have none)
2. ❌ Validation too late (distance 3+)
3. ❌ Scattered validation (inconsistent boundaries)
4. ❌ Wrong validation source (user input vs auth)

### Multi-Tenant Lawsuit Prevention

For your multi-tenant SaaS use case:
- ✅ Detects user-controlled `tenant_id` (CRITICAL)
- ✅ Finds missing `tenant_id` filters in queries
- ✅ Catches tenant check AFTER database access (too late)
- ✅ Identifies superuser connections that bypass RLS
- ✅ Validates RLS context in transactions

**One missed tenant filter = lawsuit.** Boundary analysis automates the audit.

## Next Steps

1. **Test on TheAuditor codebase** - Run on our own code to validate
2. **Add CLI command** - `aud boundaries` entry point
3. **Database persistence** - Store results for trend tracking
4. **Additional analyzers** - Authorization, sanitization, output encoding
5. **Integration** - Connect with `aud blueprint`, `aud context`, `aud taint-analyze`
