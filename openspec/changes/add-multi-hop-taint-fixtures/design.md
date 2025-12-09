# Design: Multi-Hop Taint Validation Fixtures

## Context

On 2024-12-06, rigorous verification of TheAuditor's cross-file dataflow tracking revealed a significant gap between marketing claims and reality:

| Codebase | repo_index.db | graphs.db | Max Depth |
|----------|---------------|-----------|-----------|
| plant (TS/JS) | 516 MB | 150 MB | **3 hops** |
| plantflow (TS/JS) | 56 MB | 70 MB | **2 hops** |
| TheAuditor (Python) | 243 MB | 263 MB | **3 hops** |

**Root cause identified**: Depth limits in code (verified 2024-12-09):
- `theauditor/context/query.py:604-608` - `trace_variable_flow(depth: int = 10)` with validation `depth < 1 or depth > 10`
- `theauditor/taint/core.py:368-370` - `trace_taint(max_depth: int = 25)`
- `theauditor/taint/ifds_analyzer.py:58-59` - `analyze_sink_to_sources(max_depth: int = 15)`

**Effective limits**: query tracing=10, IFDS analysis=15, full taint trace=25

**The insight**: Even with raised limits, real codebases don't have deep chains. We need purpose-built fixtures.

## Goals

1. Create two running applications with intentionally deep vulnerability chains
2. Validate TheAuditor can track 10-20+ hop dataflows
3. Confirm sanitizer detection works mid-chain
4. Enable honest marketing claims backed by reproducible evidence

## Non-Goals

1. Modify TheAuditor engine (already done)
2. Create unit tests (these are integration fixtures)
3. Performance benchmarking (future work)
4. Support for languages beyond Python/TypeScript

## Decisions

### Decision 1: Two separate projects, not one polyglot project

**Rationale**: Each language's extractor has different edge cases. Separate projects allow:
- Independent validation per extractor
- Cleaner reproduction steps
- Language-specific vulnerability patterns

**Alternatives considered**:
- Single monorepo with Python + TypeScript: Rejected - harder to isolate extractor issues
- Just Python: Rejected - TypeScript extractor needs validation too
- Just TypeScript: Rejected - Python is the primary language

### Decision 2: Real running applications, not test fixtures

**Rationale**:
- Test fixtures may have unrealistic patterns
- Running apps force realistic import/export patterns
- Can actually exploit vulnerabilities to confirm severity ratings

**Alternatives considered**:
- pytest fixtures: Rejected - no real HTTP/DB layer
- Synthetic AST files: Rejected - doesn't exercise full pipeline

### Decision 3: Layered architecture pattern

**Rationale**: Real enterprise apps follow layered patterns:
```
Controller -> Service -> Processor -> Repository -> Adapter -> Core -> Utils
```
Each layer = 1 hop. 16 layers = 16 hops.

**Python layers (16 total)**:
1. routes/ (API entry)
2. middleware/ (auth/logging)
3. services/ (business logic)
4. processors/transformer (data transform)
5. processors/validator (validation - intentionally weak)
6. processors/enricher (add metadata)
7. repositories/ (data access pattern)
8. adapters/cache (caching layer)
9. adapters/external (external APIs)
10. adapters/file_storage (file ops)
11. core/query_builder (SQL construction)
12. core/command_executor (shell commands)
13. core/template_renderer (template rendering)
14. utils/string_utils (string ops)
15. utils/path_utils (path ops)
16. utils/serializers (serialization)

**TypeScript layers (20 total)**: Same pattern plus frontend (React) layers.

### Decision 4: Multiple vulnerability types per project

**Python vulnerabilities**:
- SQL Injection (16 hops, 8 files)
- Command Injection (12 hops, 6 files)
- Path Traversal (10 hops, 5 files)
- SSRF (8 hops, 4 files)
- XSS via template (14 hops, 7 files)

**TypeScript vulnerabilities**:
- SQL Injection via Sequelize raw (18 hops, 10 files)
- XSS via template engine (15 hops, 8 files)
- Command Injection (10 hops, 5 files)
- NoSQL Injection (12 hops, 6 files)
- Prototype Pollution (8 hops, 4 files)
- Frontend-to-backend traces (20 hops, 12 files)

### Decision 5: Include sanitized paths

**Rationale**: Must prove sanitizer detection works. Each project includes:
- At least 3 paths where sanitization SHOULD break the chain
- Using real patterns: regex validation, parameterized queries, escaping

**Example sanitized path**:
```python
# Input: user email from request
# HOP 5: processors/validator.py
def validate_email(email: str):
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationError("Invalid email")
    return email  # SANITIZED - taint should end here

# HOP 10: repositories/user_repository.py
# Even if this used raw SQL, the chain should show as sanitized
```

## Architecture Diagrams

### Python Project Structure

```
deepflow-python/
|-- app/
|   |-- __init__.py
|   |-- main.py                    # FastAPI entry
|   |-- config.py
|   |-- database.py
|   |-- api/
|   |   |-- routes/
|   |   |   |-- users.py           # HOP 1: Sources (request.query_params)
|   |   |   |-- reports.py
|   |   |   |-- admin.py
|   |   |-- middleware/
|   |       |-- auth.py            # HOP 2
|   |       |-- logging.py
|   |-- services/
|   |   |-- user_service.py        # HOP 3
|   |   |-- report_service.py
|   |   |-- notification_service.py
|   |-- processors/
|   |   |-- data_transformer.py    # HOP 4
|   |   |-- validator.py           # HOP 5 (weak validation)
|   |   |-- enricher.py            # HOP 6
|   |-- repositories/
|   |   |-- base_repository.py     # HOP 7
|   |   |-- user_repository.py
|   |   |-- report_repository.py
|   |-- adapters/
|   |   |-- cache_adapter.py       # HOP 8
|   |   |-- external_api.py        # HOP 9
|   |   |-- file_storage.py        # HOP 10
|   |-- core/
|   |   |-- query_builder.py       # HOP 11: SQL construction (SINK)
|   |   |-- command_executor.py    # HOP 12: Shell (SINK)
|   |   |-- template_renderer.py   # HOP 13: XSS (SINK)
|   |-- utils/
|   |   |-- string_utils.py        # HOP 14
|   |   |-- path_utils.py          # HOP 15
|   |   |-- serializers.py         # HOP 16
|   |-- models/
|       |-- user.py
|       |-- report.py
|-- tests/
|-- requirements.txt
|-- docker-compose.yml
|-- README.md
```

### TypeScript Project Structure

```
deepflow-typescript/
|-- src/
|   |-- index.ts                   # Express entry
|   |-- config/
|   |   |-- database.ts
|   |-- controllers/
|   |   |-- user.controller.ts     # HOP 1: Sources (req.query, req.body)
|   |   |-- order.controller.ts
|   |   |-- report.controller.ts
|   |-- middleware/
|   |   |-- auth.middleware.ts     # HOP 2
|   |   |-- validation.middleware.ts
|   |   |-- logging.middleware.ts
|   |-- services/
|   |   |-- user.service.ts        # HOP 3
|   |   |-- order.service.ts
|   |   |-- notification.service.ts
|   |-- processors/
|   |   |-- data.transformer.ts    # HOP 4
|   |   |-- input.validator.ts     # HOP 5
|   |   |-- data.enricher.ts       # HOP 6
|   |   |-- output.formatter.ts    # HOP 7
|   |-- repositories/
|   |   |-- base.repository.ts     # HOP 8
|   |   |-- user.repository.ts
|   |   |-- order.repository.ts
|   |-- adapters/
|   |   |-- redis.adapter.ts       # HOP 9
|   |   |-- elasticsearch.adapter.ts # HOP 10
|   |   |-- s3.adapter.ts          # HOP 11
|   |-- core/
|   |   |-- query.builder.ts       # HOP 12: SQL construction (SINK)
|   |   |-- command.runner.ts      # HOP 13: Shell (SINK)
|   |   |-- template.engine.ts     # HOP 14: XSS (SINK)
|   |-- utils/
|   |   |-- string.utils.ts        # HOP 15
|   |   |-- path.utils.ts          # HOP 16
|   |   |-- crypto.utils.ts        # HOP 17
|   |   |-- serializer.ts          # HOP 18
|   |-- models/
|   |   |-- user.model.ts
|   |   |-- order.model.ts
|   |-- types/
|       |-- index.ts
|-- frontend/
|   |-- src/
|   |   |-- App.tsx
|   |   |-- api/
|   |   |   |-- client.ts          # HOP 19: API calls
|   |   |-- components/
|   |   |   |-- UserSearch.tsx     # HOP 20: User input entry
|   |   |   |-- ReportViewer.tsx
|   |   |-- hooks/
|   |       |-- useApi.ts
|   |-- package.json
|   |-- vite.config.ts
|-- package.json
|-- tsconfig.json
|-- docker-compose.yml
|-- README.md
```

## Complete Code Example: 16-Hop SQL Injection Chain

This section provides a complete worked example showing how to implement a vulnerability chain that TheAuditor can trace across 16 hops and 8 files.

### File 1: app/api/routes/users.py (HOP 1 - SOURCE)
```python
from fastapi import APIRouter, Query
from app.api.middleware.auth import require_auth
from app.services.user_service import UserService

router = APIRouter()

@router.get("/users/search")
@require_auth
async def search_users(q: str = Query(..., description="Search query")):
    """HOP 1: Taint source - user input from query parameter."""
    service = UserService()
    return await service.search(q)  # q is TAINTED, passed to HOP 2
```

### File 2: app/api/middleware/auth.py (HOP 2)
```python
from functools import wraps

def require_auth(func):
    """HOP 2: Middleware passes tainted data through."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Auth check here (doesn't sanitize q)
        return await func(*args, **kwargs)  # kwargs['q'] still TAINTED
    return wrapper
```

### File 3: app/services/user_service.py (HOP 3)
```python
from app.processors.data_transformer import DataTransformer

class UserService:
    def __init__(self):
        self.transformer = DataTransformer()

    async def search(self, query: str):
        """HOP 3: Service layer passes query to processor."""
        transformed = self.transformer.prepare_search(query)  # query TAINTED
        return transformed
```

### File 4: app/processors/data_transformer.py (HOP 4)
```python
from app.processors.validator import Validator

class DataTransformer:
    def __init__(self):
        self.validator = Validator()

    def prepare_search(self, term: str):
        """HOP 4: Transformer adds metadata but doesn't sanitize."""
        # INTENTIONALLY WEAK: Only checks length, not content
        validated = self.validator.check_length(term)  # term TAINTED
        return {"search_term": validated, "timestamp": "now"}
```

### File 5: app/processors/validator.py (HOP 5 - WEAK VALIDATION)
```python
from app.processors.enricher import Enricher

class Validator:
    def __init__(self):
        self.enricher = Enricher()

    def check_length(self, value: str):
        """HOP 5: INTENTIONALLY WEAK - only checks length, SQL chars pass through."""
        if len(value) > 1000:
            raise ValueError("Too long")
        # NOTE: Does NOT sanitize SQL special chars like ' or --
        return self.enricher.add_context(value)  # value still TAINTED
```

### File 6: app/processors/enricher.py (HOP 6)
```python
from app.repositories.user_repository import UserRepository

class Enricher:
    def __init__(self):
        self.repo = UserRepository()

    def add_context(self, term: str):
        """HOP 6: Enricher adds metadata and queries repository."""
        # Still passing tainted input
        return self.repo.find_by_term(term)  # term TAINTED
```

### File 7: app/repositories/user_repository.py (HOP 7)
```python
from app.adapters.cache_adapter import CacheAdapter

class UserRepository:
    def __init__(self):
        self.cache = CacheAdapter()

    def find_by_term(self, term: str):
        """HOP 7: Repository checks cache then queries."""
        cached = self.cache.get_or_fetch(term)  # term TAINTED
        return cached
```

### File 8: app/adapters/cache_adapter.py (HOP 8)
```python
from app.core.query_builder import QueryBuilder

class CacheAdapter:
    def __init__(self):
        self.builder = QueryBuilder()

    def get_or_fetch(self, key: str):
        """HOP 8: Cache miss triggers query builder."""
        # Simulating cache miss - always builds query
        return self.builder.build_user_search(key)  # key TAINTED
```

### File 9: app/core/query_builder.py (HOP 9-16 - SINK)
```python
import sqlite3

class QueryBuilder:
    def __init__(self):
        self.conn = sqlite3.connect("app.db")

    def build_user_search(self, term: str):
        """HOPS 9-16: Query construction with VULNERABLE f-string SQL.

        This is the SINK - tainted user input is concatenated into SQL.
        TheAuditor should detect this as SQL Injection.
        """
        # HOP 9: Build base query
        base = "SELECT * FROM users WHERE "

        # HOP 10: Add condition (VULNERABLE - string concatenation)
        condition = f"name LIKE '%{term}%'"  # term is TAINTED!

        # HOP 11: Combine
        query = base + condition

        # HOP 12: Add ordering
        query += " ORDER BY created_at DESC"

        # HOP 13: Add limit
        query += " LIMIT 100"

        # HOP 14: Log query (still tainted)
        self._log_query(query)

        # HOP 15: Execute (SINK - SQL Injection)
        cursor = self.conn.cursor()
        cursor.execute(query)  # VULNERABLE: Tainted query executed

        # HOP 16: Return results
        return cursor.fetchall()

    def _log_query(self, sql: str):
        """HOP 14: Logging doesn't sanitize."""
        print(f"Executing: {sql}")  # Still tainted in logs
```

### Expected TheAuditor Output

When `aud full --offline` runs on this project, the expected `taint_flows` database record (query with `SELECT * FROM taint_flows`):

```json
{
  "path_length": 16,
  "vulnerability_type": "SQL Injection",
  "severity": "critical",
  "source": {
    "file": "app/api/routes/users.py",
    "line": 10,
    "name": "q",
    "category": "http_request"
  },
  "sink": {
    "file": "app/core/query_builder.py",
    "line": 32,
    "name": "query",
    "category": "sql",
    "vulnerability_type": "SQL Injection"
  },
  "path": [
    {"file": "app/api/routes/users.py", "line": 10, "type": "source"},
    {"from_file": "app/api/routes/users.py", "to_file": "app/api/middleware/auth.py", "type": "call"},
    {"from_file": "app/api/middleware/auth.py", "to_file": "app/services/user_service.py", "type": "call"},
    {"from_file": "app/services/user_service.py", "to_file": "app/processors/data_transformer.py", "type": "call"},
    {"from_file": "app/processors/data_transformer.py", "to_file": "app/processors/validator.py", "type": "call"},
    {"from_file": "app/processors/validator.py", "to_file": "app/processors/enricher.py", "type": "call"},
    {"from_file": "app/processors/enricher.py", "to_file": "app/repositories/user_repository.py", "type": "call"},
    {"from_file": "app/repositories/user_repository.py", "to_file": "app/adapters/cache_adapter.py", "type": "call"},
    {"from_file": "app/adapters/cache_adapter.py", "to_file": "app/core/query_builder.py", "type": "call"},
    {"file": "app/core/query_builder.py", "line": 32, "type": "sink"}
  ]
}
```

### Sanitized Path Example (Should NOT Report as Vulnerable)

For comparison, here's a SAFE path that uses parameterized queries:

```python
# app/repositories/safe_user_repository.py
class SafeUserRepository:
    def find_by_term_safe(self, term: str):
        """SANITIZED: Uses parameterized query - NOT vulnerable."""
        cursor = self.conn.cursor()
        # Parameterized query - term is escaped by sqlite3
        cursor.execute(
            "SELECT * FROM users WHERE name LIKE ?",
            (f"%{term}%",)  # Parameter binding sanitizes input
        )
        return cursor.fetchall()
```

TheAuditor should recognize the `?` placeholder pattern and mark this path as **SANITIZED**, not vulnerable.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Projects become stale/unmaintained | Minimal dependencies, pinned versions |
| Tests pass but real codebases still show 3 hops | These prove engine works; real codebases have flat architecture |
| False sense of security from passing fixtures | Document clearly: fixtures prove capability, not guarantee detection |
| Maintenance burden of two projects | Simple architectures, no complex business logic |

## Migration Plan

N/A - These are new test projects, not modifications to existing code.

## Decisions (Resolved)

### Decision 6: Host in separate repository

**Decision**: Create `theauditor-fixtures` repository separate from TheAuditor main repo.

**Rationale**:
- Keeps TheAuditor repo clean (no test project bloat)
- Fixtures can have their own release cycle
- Easier to clone independently for validation
- CI can reference specific fixture versions

**Alternatives rejected**:
- Subdirectory in TheAuditor: Would add ~50MB+ to repo, complicates .gitignore

### Decision 7: CI integration via GitHub Actions

**Decision**: Add GitHub Action workflow that:
1. Clones fixtures repo
2. Runs `aud full --offline` on each project
3. Validates max depth >= threshold (16 for Python, 20 for TypeScript)
4. Fails if sanitized paths are reported as vulnerable

**Implementation**: `.github/workflows/validate-fixtures.yml` in fixtures repo

### Decision 8: Docker for DB, native for app

**Decision**:
- PostgreSQL via `docker-compose up -d db`
- Application runs natively (`uvicorn` for Python, `npm start` for TypeScript)

**Rationale**:
- Simplifies debugging (no container networking issues)
- Faster iteration during development
- DB is stateless anyway (fixtures recreate schema)

## Output Schema Reference

The `taint_flows` table in `.pf/repo_index.db` stores taint analysis results. Each row's `path_json` column contains the path structure. Query with:

```sql
SELECT vulnerability_type, path_length, severity, path_json FROM taint_flows;
```

Per-row structure (JSON in `path_json` column):

```json
{
  "paths": [
    {
      "path": [
        {"file": "...", "line": N, "name": "...", "type": "source"},
        {"depth": N, "from": "...", "from_file": "...", "to": "...", "to_file": "...", "type": "assignment_reverse"},
        {"file": "...", "line": N, "name": "...", "type": "sink"}
      ],
      "path_length": 3,
      "path_complexity": 0,
      "severity": "critical|high|medium|low",
      "vulnerability_type": "SQL Injection|Command Injection|XSS|...",
      "source": {
        "category": "http_request|file_read|env_var|...",
        "file": "...",
        "line": N,
        "name": "...",
        "pattern": "...",
        "risk": "high|medium|low",
        "type": "http_request|..."
      },
      "sink": {
        "category": "sql|command|file|template|...",
        "file": "...",
        "line": N,
        "name": "...",
        "pattern": "...",
        "risk": "high|medium|low",
        "type": "sql|command|...",
        "vulnerability_type": "SQL Injection|..."
      },
      "sanitized_vars": [],
      "tainted_vars": [],
      "flow_sensitive": true,
      "condition_summary": "",
      "conditions": []
    }
  ],
  "engine_breakdown": {
    "FlowResolver:REACHABLE": N,
    "FlowResolver:SANITIZED": N,
    "FlowResolver:VULNERABLE": N,
    "IFDS:VULNERABLE": N
  },
  "engines_used": ["IFDS (backward)", "FlowResolver (forward)"],
  "mode": "complete",
  "advanced_findings": [],
  "all_rule_findings": [],
  "discovery_findings": [],
  "infrastructure_issues": []
}
```

**Key fields for validation**:
- `paths[].path_length` - Number of hops in chain
- `paths[].path[]` - Array of steps, count unique `file`/`from_file` for cross-file count
- `paths[].vulnerability_type` - Type classification
- `engine_breakdown.FlowResolver:SANITIZED` - Count of sanitized paths (should be > 0)
