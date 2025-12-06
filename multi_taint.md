# Multi-Hop Taint Analysis Test Projects

## Problem Statement

### The Gap Between Claims and Reality

On 2024-12-06, we conducted a rigorous verification of TheAuditor's cross-file dataflow tracking claims against two real codebases:

| Codebase | repo_index.db | graphs.db | Taint Vulns | Max Depth |
|----------|---------------|-----------|-------------|-----------|
| plant (TS/JS) | 516 MB | 150 MB | 325 | **3 hops** |
| plantflow (TS/JS) | 56 MB | 70 MB | 253 | **2 hops** |
| TheAuditor (Python) | 243 MB | 263 MB | 726 | **3 hops** |

The original marketing claim was "59 hops, 19 cross-file transitions, 8 files traversed, 10 functions traced."

**Reality check:**
- Maximum actual depth observed in taint paths: **3 hops**
- Maximum cross-file transitions in a single chain: **2-3 files**
- Depth distribution in plant: `{depth=1: 275, depth=2: 8, depth=3: 2}`

### Why The Gap Exists

The depth limits were found in TheAuditor's own code:

```python
# theauditor/context/query.py:610-611 (BEFORE fix)
if depth < 1 or depth > 5:
    raise ValueError("Depth must be between 1 and 5")

# theauditor/taint/core.py:370 (BEFORE fix)
max_depth: int = 10

# theauditor/taint/ifds_analyzer.py:59 (BEFORE fix)
max_depth: int = 10
```

**These have been raised to 20** as of this session. But here's the critical insight:

Even with limits raised, **the actual codebases don't have deep dataflow chains**. Real-world code typically follows this pattern:

```
req -> accountId -> service.method(accountId) -> ORM.query()
 (1)      (2)              (3)                     (sink)
```

Most vulnerabilities are found in 2-3 hops because:
1. Code is well-structured (short call chains)
2. Data transformations are minimal before reaching sinks
3. Services are relatively flat (not deeply nested)

### What We Need

Two purpose-built test projects that:
1. **Actually run** (not test fixtures - real HTTP servers with databases)
2. **Have intentionally deep dataflow chains** (10-20+ hops)
3. **Cross many files** (controller -> service -> helper -> utility -> model -> ...)
4. **Transform data at each step** (not just pass-through)
5. **Include both vulnerable AND sanitized paths**
6. **Cover multiple vulnerability types** (SQLi, XSS, command injection, path traversal)

---

## Project 1: DeepFlow Python (Flask/FastAPI)

### Architecture Overview

```
deepflow-python/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Configuration loader
│   ├── database.py                # SQLAlchemy setup
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── users.py           # HOP 1: Request entry
│   │   │   ├── reports.py
│   │   │   └── admin.py
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── auth.py            # HOP 2: Auth processing
│   │       └── logging.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py        # HOP 3: Business logic
│   │   ├── report_service.py
│   │   └── notification_service.py
│   │
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── data_transformer.py    # HOP 4: Transform data
│   │   ├── validator.py           # HOP 5: Validate (or not)
│   │   └── enricher.py            # HOP 6: Enrich with more data
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base_repository.py     # HOP 7: Repository pattern
│   │   ├── user_repository.py
│   │   └── report_repository.py
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── cache_adapter.py       # HOP 8: Cache layer
│   │   ├── external_api.py        # HOP 9: External calls
│   │   └── file_storage.py        # HOP 10: File operations
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── query_builder.py       # HOP 11: Build SQL
│   │   ├── command_executor.py    # HOP 12: Execute commands
│   │   └── template_renderer.py   # HOP 13: Render templates
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── string_utils.py        # HOP 14: String operations
│   │   ├── path_utils.py          # HOP 15: Path operations
│   │   └── serializers.py         # HOP 16: Serialization
│   │
│   └── models/
│       ├── __init__.py
│       ├── user.py
│       └── report.py
│
├── tests/
│   └── ...
├── requirements.txt
├── docker-compose.yml
└── README.md
```

### Intentional Vulnerability Chains

#### Chain 1: SQL Injection (16 hops, 8 files)

```python
# HOP 1: routes/users.py
@router.get("/users/search")
async def search_users(request: Request):
    query = request.query_params.get("q")  # TAINT SOURCE
    user_id = request.query_params.get("user_id")
    return await user_service.search(query, user_id)

# HOP 2: middleware/auth.py
async def extract_context(request, query, user_id):
    context = {"query": query, "user_id": user_id, "tenant": get_tenant(request)}
    return context

# HOP 3: services/user_service.py
async def search(self, query: str, user_id: str):
    context = build_search_context(query, user_id)
    transformed = await self.transformer.prepare_search(context)
    return await self.repository.find_by_criteria(transformed)

# HOP 4: processors/data_transformer.py
def prepare_search(self, context: dict):
    criteria = {
        "search_term": context["query"],
        "filters": self.build_filters(context)
    }
    return self.enricher.add_metadata(criteria)

# HOP 5: processors/enricher.py
def add_metadata(self, criteria: dict):
    criteria["timestamp"] = datetime.now()
    criteria["formatted_term"] = self.format_term(criteria["search_term"])
    return criteria

# HOP 6: processors/validator.py (INTENTIONALLY WEAK)
def format_term(self, term: str):
    # VULNERABLE: No real sanitization
    return term.strip()

# HOP 7: repositories/user_repository.py
async def find_by_criteria(self, criteria: dict):
    query_parts = self.query_builder.build(criteria)
    return await self.execute_query(query_parts)

# HOP 8: adapters/cache_adapter.py
async def check_cache_or_query(self, query_parts):
    cache_key = self.build_cache_key(query_parts)
    cached = await self.cache.get(cache_key)
    if cached:
        return cached
    return await self.query_builder.execute(query_parts)

# HOP 9: core/query_builder.py
def build(self, criteria: dict):
    where_clause = f"name LIKE '%{criteria['formatted_term']}%'"  # VULNERABLE
    return {"select": "*", "from": "users", "where": where_clause}

# HOP 10: core/query_builder.py
def execute(self, query_parts: dict):
    sql = f"SELECT {query_parts['select']} FROM {query_parts['from']} WHERE {query_parts['where']}"
    return self.db.execute(sql)  # SINK: SQL Injection
```

#### Chain 2: Command Injection (12 hops, 6 files)

```python
# HOP 1: routes/reports.py
@router.post("/reports/generate")
async def generate_report(request: Request):
    format_type = request.json.get("format")  # TAINT SOURCE
    return await report_service.generate(format_type)

# HOP 2-4: Through service/processor layers...

# HOP 5: adapters/file_storage.py
def convert_format(self, data: bytes, format_type: str):
    command_args = self.command_builder.build_convert_args(format_type)
    return self.executor.run(command_args)

# HOP 6: core/command_executor.py
def run(self, args: dict):
    cmd = f"convert {args['input']} -format {args['format']} {args['output']}"
    return subprocess.run(cmd, shell=True)  # SINK: Command Injection
```

#### Chain 3: Path Traversal (10 hops, 5 files)

```python
# HOP 1: routes/admin.py
@router.get("/admin/files/{filename}")
async def get_file(filename: str):  # TAINT SOURCE
    return await file_service.retrieve(filename)

# Through multiple layers...

# HOP 10: adapters/file_storage.py
def retrieve(self, filename: str):
    path = os.path.join(self.base_path, filename)  # VULNERABLE
    return open(path, 'rb').read()  # SINK: Path Traversal
```

#### Chain 4: SANITIZED Path (proves sanitizer detection works)

```python
# HOP 1: routes/users.py
@router.post("/users")
async def create_user(request: Request):
    email = request.json.get("email")  # TAINT SOURCE
    return await user_service.create(email)

# HOP 5: processors/validator.py
def validate_email(self, email: str):
    # SANITIZER: Proper validation
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationError("Invalid email")
    return email  # SANITIZED

# HOP 10: repositories/user_repository.py
async def create(self, data: dict):
    # Using parameterized query - even if email wasn't sanitized, this is safe
    return await self.db.execute(
        "INSERT INTO users (email) VALUES (?)",
        [data["email"]]  # SAFE SINK
    )
```

### Running the Python Project

```bash
cd deepflow-python
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Start PostgreSQL
docker-compose up -d db

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000

# Test endpoints
curl "http://localhost:8000/users/search?q=test"
curl -X POST "http://localhost:8000/reports/generate" -H "Content-Type: application/json" -d '{"format": "pdf"}'
```

---

## Project 2: DeepFlow TypeScript (Express/NestJS)

### Architecture Overview

```
deepflow-typescript/
├── src/
│   ├── index.ts                   # Express app entry
│   ├── config/
│   │   └── database.ts
│   │
│   ├── controllers/
│   │   ├── user.controller.ts     # HOP 1: Request entry
│   │   ├── order.controller.ts
│   │   └── report.controller.ts
│   │
│   ├── middleware/
│   │   ├── auth.middleware.ts     # HOP 2: Auth processing
│   │   ├── validation.middleware.ts
│   │   └── logging.middleware.ts
│   │
│   ├── services/
│   │   ├── user.service.ts        # HOP 3: Business logic
│   │   ├── order.service.ts
│   │   └── notification.service.ts
│   │
│   ├── processors/
│   │   ├── data.transformer.ts    # HOP 4: Transform data
│   │   ├── input.validator.ts     # HOP 5: Validate
│   │   ├── data.enricher.ts       # HOP 6: Enrich
│   │   └── output.formatter.ts    # HOP 7: Format
│   │
│   ├── repositories/
│   │   ├── base.repository.ts     # HOP 8: Repository pattern
│   │   ├── user.repository.ts
│   │   └── order.repository.ts
│   │
│   ├── adapters/
│   │   ├── redis.adapter.ts       # HOP 9: Cache layer
│   │   ├── elasticsearch.adapter.ts # HOP 10: Search
│   │   └── s3.adapter.ts          # HOP 11: File storage
│   │
│   ├── core/
│   │   ├── query.builder.ts       # HOP 12: Build queries
│   │   ├── command.runner.ts      # HOP 13: Run commands
│   │   └── template.engine.ts     # HOP 14: Render templates
│   │
│   ├── utils/
│   │   ├── string.utils.ts        # HOP 15: String ops
│   │   ├── path.utils.ts          # HOP 16: Path ops
│   │   ├── crypto.utils.ts        # HOP 17: Crypto ops
│   │   └── serializer.ts          # HOP 18: Serialization
│   │
│   ├── models/
│   │   ├── user.model.ts
│   │   └── order.model.ts
│   │
│   └── types/
│       └── index.ts
│
├── frontend/                      # React frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   └── client.ts          # API calls (trace to backend)
│   │   ├── components/
│   │   │   ├── UserSearch.tsx     # User input entry
│   │   │   └── ReportViewer.tsx
│   │   └── hooks/
│   │       └── useApi.ts
│   ├── package.json
│   └── vite.config.ts
│
├── package.json
├── tsconfig.json
├── docker-compose.yml
└── README.md
```

### Intentional Vulnerability Chains

#### Chain 1: SQL Injection via Sequelize Raw Query (18 hops, 10 files)

```typescript
// HOP 1: controllers/user.controller.ts
export class UserController {
  async search(req: Request, res: Response) {
    const { query, filters } = req.query;  // TAINT SOURCE
    const context = await this.authMiddleware.extractContext(req, query);
    const result = await this.userService.searchUsers(context);
    res.json(result);
  }
}

// HOP 2: middleware/auth.middleware.ts
async extractContext(req: Request, query: string) {
  return {
    query,
    userId: req.user?.id,
    tenant: this.getTenant(req),
    permissions: await this.getPermissions(req.user)
  };
}

// HOP 3: services/user.service.ts
async searchUsers(context: SearchContext) {
  const prepared = await this.transformer.prepareSearchCriteria(context);
  const validated = await this.validator.validateCriteria(prepared);
  const enriched = await this.enricher.enrichWithMetadata(validated);
  return await this.repository.findByCriteria(enriched);
}

// HOP 4: processors/data.transformer.ts
prepareSearchCriteria(context: SearchContext): SearchCriteria {
  return {
    searchTerm: context.query,
    tenantId: context.tenant,
    filters: this.parseFilters(context)
  };
}

// HOP 5: processors/input.validator.ts
validateCriteria(criteria: SearchCriteria): SearchCriteria {
  // VULNERABLE: Only checks for null, not SQL injection
  if (!criteria.searchTerm) {
    throw new ValidationError('Search term required');
  }
  return criteria;
}

// HOP 6: processors/data.enricher.ts
async enrichWithMetadata(criteria: SearchCriteria): EnrichedCriteria {
  return {
    ...criteria,
    timestamp: new Date(),
    formattedTerm: this.formatter.format(criteria.searchTerm)
  };
}

// HOP 7: processors/output.formatter.ts
format(term: string): string {
  return term.trim().toLowerCase();  // STILL VULNERABLE
}

// HOP 8: repositories/user.repository.ts
async findByCriteria(criteria: EnrichedCriteria) {
  const queryParts = await this.queryBuilder.build(criteria);
  const cached = await this.cacheAdapter.get(queryParts);
  if (cached) return cached;
  return await this.executeQuery(queryParts);
}

// HOP 9: adapters/redis.adapter.ts
async get(queryParts: QueryParts): Promise<any | null> {
  const key = this.buildKey(queryParts);
  return await this.redis.get(key);
}

// HOP 10: core/query.builder.ts
build(criteria: EnrichedCriteria): QueryParts {
  const whereClause = `name ILIKE '%${criteria.formattedTerm}%'`;  // VULNERABLE
  return { select: '*', from: 'users', where: whereClause };
}

// HOP 11: repositories/user.repository.ts
async executeQuery(parts: QueryParts) {
  const sql = `SELECT ${parts.select} FROM ${parts.from} WHERE ${parts.where}`;
  return await this.sequelize.query(sql);  // SINK: SQL Injection
}
```

#### Chain 2: XSS via Template Rendering (15 hops, 8 files)

```typescript
// HOP 1: controllers/report.controller.ts
async generateReport(req: Request, res: Response) {
  const { title, content } = req.body;  // TAINT SOURCE
  const report = await this.reportService.generate(title, content);
  res.send(report);
}

// Through multiple layers...

// HOP 15: core/template.engine.ts
render(template: string, data: ReportData): string {
  // VULNERABLE: No escaping
  return template.replace('{{title}}', data.title)
                 .replace('{{content}}', data.content);  // SINK: XSS
}
```

#### Chain 3: Frontend to Backend Trace (20 hops, 12 files)

```typescript
// FRONTEND HOP 1: components/UserSearch.tsx
const UserSearch = () => {
  const [query, setQuery] = useState('');

  const handleSearch = async () => {
    const results = await api.searchUsers(query);  // User input
    setResults(results);
  };
};

// FRONTEND HOP 2: api/client.ts
async searchUsers(query: string) {
  return fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
  // Note: encodeURIComponent helps but backend still vulnerable
}

// BACKEND HOP 3-20: Full chain through backend...
```

### Running the TypeScript Project

```bash
cd deepflow-typescript

# Install dependencies
npm install
cd frontend && npm install && cd ..

# Start services
docker-compose up -d

# Build and run backend
npm run build
npm run start

# In another terminal, start frontend
cd frontend && npm run dev

# Access at http://localhost:5173
```

---

## Expected TheAuditor Results

After running `aud full` on these projects, we expect:

### Python Project

```
=== TAINT ANALYSIS RESULTS ===
Vulnerabilities found: ~15-25
Max chain depth: 16 hops
Cross-file transitions: 8-10 per chain

Vulnerability Types:
- SQL Injection: 5 (16-hop chains)
- Command Injection: 3 (12-hop chains)
- Path Traversal: 2 (10-hop chains)
- SSRF: 2 (8-hop chains)
- XSS: 3 (14-hop chains)

Sanitized Paths Detected: 3-5
```

### TypeScript Project

```
=== TAINT ANALYSIS RESULTS ===
Vulnerabilities found: ~20-30
Max chain depth: 20 hops
Cross-file transitions: 10-12 per chain

Vulnerability Types:
- SQL Injection: 6 (18-hop chains)
- XSS: 5 (15-hop chains)
- Command Injection: 2 (10-hop chains)
- NoSQL Injection: 3 (12-hop chains)
- Prototype Pollution: 2 (8-hop chains)

Cross-Stack Traces (frontend->backend): 5-8
```

---

## Verification Queries

After indexing, run these to verify deep chains:

```bash
# Check max depth in taint analysis
cd deepflow-python
aud full --offline
python -c "
import json
with open('.pf/raw/taint_analysis.json') as f:
    data = json.load(f)
vulns = data.get('vulnerabilities', [])
max_depth = max(len(v.get('path', [])) for v in vulns)
print(f'Max depth: {max_depth}')
depths = {}
for v in vulns:
    d = len(v.get('path', []))
    depths[d] = depths.get(d, 0) + 1
print(f'Distribution: {dict(sorted(depths.items()))}')
"

# Check cross-file parameter bindings
python -c "
import sqlite3
conn = sqlite3.connect('.pf/graphs.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM edges WHERE type = \"parameter_binding\"')
print(f'Parameter binding edges: {c.fetchone()[0]}')
"
```

---

## Code Changes Made This Session

The following limits were raised from their original values:

| File | Line | Before | After |
|------|------|--------|-------|
| `theauditor/context/query.py` | 606 | `depth: int = 3` | `depth: int = 10` |
| `theauditor/context/query.py` | 610 | `depth > 5` | `depth > 20` |
| `theauditor/taint/core.py` | 370 | `max_depth: int = 10` | `max_depth: int = 20` |
| `theauditor/taint/ifds_analyzer.py` | 59 | `max_depth: int = 10` | `max_depth: int = 20` |

**These changes have been applied but NOT tested yet.**

---

## Next Steps

1. **Create the Python project** (`deepflow-python/`)
   - FastAPI + SQLAlchemy + PostgreSQL
   - Implement all 16 layers with intentional vulnerabilities
   - Include both vulnerable and sanitized paths

2. **Create the TypeScript project** (`deepflow-typescript/`)
   - Express + Sequelize + PostgreSQL
   - React frontend with API calls
   - Implement all 18-20 layers

3. **Run TheAuditor analysis**
   - `aud full --offline` on each project
   - Verify deep chains are detected
   - Document actual vs expected results

4. **Tune detection if needed**
   - If chains are truncated, investigate why
   - Adjust max_depth parameters
   - Add any missing edge types for cross-file tracking

---

## Success Criteria

The test projects are successful if TheAuditor produces:

1. **Taint paths with 10+ hops** (not just 2-3)
2. **Cross-file transitions of 5+ files** in a single chain
3. **Accurate sanitizer detection** (sanitized paths marked as safe)
4. **Frontend-to-backend traces** (for TypeScript project)
5. **Multiple vulnerability types** correctly classified

If we achieve this, we can confidently claim TheAuditor performs "real interprocedural dataflow analysis" without the asterisk of "but only 3 hops deep."
