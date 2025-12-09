# DeepFlow TypeScript

Multi-hop taint analysis validation fixture for TheAuditor.

## WARNING

**This application contains intentional security vulnerabilities for testing purposes.**
**DO NOT deploy in production.**

## Purpose

This fixture validates TheAuditor's interprocedural dataflow analysis by providing:

- **20-layer architecture** with intentional vulnerability chains
- **6 vulnerability types**: SQLi, XSS, Command Injection, NoSQL Injection, Prototype Pollution, Frontend-to-Backend
- **3 sanitized paths** that should NOT be flagged as vulnerable

## Architecture (20 Hops)

```
Backend:
controllers/       (HOP 1)  - HTTP request sources
middleware/        (HOP 2)  - Auth passes data through
services/          (HOP 3)  - Business logic layer
processors/        (HOP 4-7) - Transform, validate, enrich, format
repositories/      (HOP 8)  - Data access pattern
adapters/          (HOP 9-11) - Redis, Elasticsearch, S3
core/              (HOP 12-14) - Query builder, command runner, template engine (SINKS)
utils/             (HOP 15-18) - String, path, crypto, serializer utilities

Frontend:
api/client.ts      (HOP 19) - API calls to backend
components/        (HOP 20) - React components (user input sources)
```

## Vulnerability Chains

| Type | Hops | Files | Source | Sink |
|------|------|-------|--------|------|
| SQL Injection | 18 | 10 | `controllers/user:req.query` | `core/query.builder:execute` |
| XSS | 15 | 8 | `controllers/report:req.body.title` | `core/template.engine:render` |
| Command Injection | 10 | 5 | `controllers/order:req.body.format` | `core/command.runner:exec` |
| NoSQL Injection | 12 | 6 | `controllers/user:req.body.filter` | `adapters/elasticsearch:search` |
| Prototype Pollution | 8 | 4 | `controllers/user:req.body.settings` | `utils/serializer:deepMerge` |
| Frontend-to-Backend | 20 | 12 | `components/UserSearch:useState` | `core/query.builder:execute` |

## Sanitized Paths

1. **Parameterized queries** - `repositories/safe.repository.ts`
2. **Input validation** - `controllers/safe.controller.ts` (regex validation)
3. **HTML escaping** - `utils/string.utils.ts:escapeHtml`

## Running

```bash
# Start databases
docker-compose up -d

# Install backend dependencies
npm install

# Build and run backend
npm run build
npm start

# Install frontend dependencies
cd frontend
npm install

# Run frontend
npm run dev
```

## Validation with TheAuditor

```bash
# Index the fixture
cd tests/deepflow-typescript
aud full --offline

# Check taint results (using Python since sqlite3 command not available)
python -c "
import sqlite3
import json

conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

c.execute('SELECT path_length, COUNT(*) FROM taint_flows GROUP BY path_length ORDER BY path_length')
for row in c.fetchall():
    print(f'Depth {row[0]}: {row[1]} chains')

conn.close()
"
```

## Expected Results

- Max chain depth: >= 20 hops
- Cross-file transitions: >= 10 files per chain
- Vulnerability types detected: 6
- Frontend-to-backend traces: >= 2
- Sanitized paths: NOT flagged as vulnerable
