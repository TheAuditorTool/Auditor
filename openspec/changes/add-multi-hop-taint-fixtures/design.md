# Design: Multi-Hop Taint Validation Fixtures

## Context

On 2024-12-06, rigorous verification of TheAuditor's cross-file dataflow tracking revealed a significant gap between marketing claims and reality:

| Codebase | repo_index.db | graphs.db | Max Depth |
|----------|---------------|-----------|-----------|
| plant (TS/JS) | 516 MB | 150 MB | **3 hops** |
| plantflow (TS/JS) | 56 MB | 70 MB | **2 hops** |
| TheAuditor (Python) | 243 MB | 263 MB | **3 hops** |

**Root cause identified**: Depth limits in code (now raised to 20):
- `theauditor/context/query.py:606` - default depth 3 -> 10, max 5 -> 20
- `theauditor/taint/core.py:370` - max_depth 10 -> 20
- `theauditor/taint/ifds_analyzer.py:59` - max_depth 10 -> 20

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

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Projects become stale/unmaintained | Minimal dependencies, pinned versions |
| Tests pass but real codebases still show 3 hops | These prove engine works; real codebases have flat architecture |
| False sense of security from passing fixtures | Document clearly: fixtures prove capability, not guarantee detection |
| Maintenance burden of two projects | Simple architectures, no complex business logic |

## Migration Plan

N/A - These are new test projects, not modifications to existing code.

## Open Questions

1. **Where to host projects?**
   - Separate repo `theauditor-fixtures`?
   - Subdirectory in TheAuditor repo (`test-fixtures/`)?
   - **Recommendation**: Separate repo - keeps TheAuditor clean

2. **CI integration?**
   - Run `aud full` on fixtures as part of CI?
   - **Recommendation**: Yes, add GitHub Action that indexes fixtures and validates depth

3. **Docker or native?**
   - Both projects need PostgreSQL
   - **Recommendation**: docker-compose for DB, native Python/Node for app
