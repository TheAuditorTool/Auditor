# DeepFlow Python

Multi-hop taint analysis validation fixture for TheAuditor.

## WARNING

**This application contains intentional security vulnerabilities for testing purposes.**
**DO NOT deploy in production.**

## Purpose

This fixture validates TheAuditor's interprocedural dataflow analysis by providing:

- **16-layer architecture** with intentional vulnerability chains
- **5 vulnerability types**: SQLi, Command Injection, Path Traversal, SSRF, XSS
- **3 sanitized paths** that should NOT be flagged as vulnerable

## Architecture (16 Hops)

```
routes/         (HOP 1)  - HTTP request sources
middleware/     (HOP 2)  - Auth passes data through
services/       (HOP 3)  - Business logic layer
processors/     (HOP 4-6) - Transform, validate, enrich
repositories/   (HOP 7)  - Data access pattern
adapters/       (HOP 8-10) - Cache, external API, file storage
core/           (HOP 11-13) - Query builder, command executor, template renderer (SINKS)
utils/          (HOP 14-16) - String, path, serializer utilities
```

## Vulnerability Chains

| Type | Hops | Files | Source | Sink |
|------|------|-------|--------|------|
| SQL Injection | 16 | 8 | `routes/users.py:q` | `core/query_builder.py:execute` |
| Command Injection | 12 | 6 | `routes/reports.py:format` | `core/command_executor.py:shell` |
| Path Traversal | 10 | 5 | `routes/admin.py:filename` | `adapters/file_storage.py:open` |
| SSRF | 8 | 4 | `routes/reports.py:callback_url` | `adapters/external_api.py:urlopen` |
| XSS | 14 | 7 | `routes/reports.py:title` | `core/template_renderer.py:format` |

## Sanitized Paths

1. **Email validation** - `processors/validator.py` uses regex validation
2. **Parameterized queries** - `core/query_builder.py:build_email_lookup` uses `?` placeholders
3. **HTML escaping** - `core/template_renderer.py:render_safe` uses `html.escape()`

## Running

```bash
# Start database
docker-compose up -d db

# Install dependencies
pip install -r requirements.txt

# Run application
uvicorn app.main:app --reload
```

## Validation with TheAuditor

```bash
# Index the fixture
cd tests/deepflow-python
aud full --offline

# Check taint results
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

- Max chain depth: >= 16 hops
- Cross-file transitions: >= 8 files per chain
- Vulnerability types detected: 5
- Sanitized paths: NOT flagged as vulnerable
