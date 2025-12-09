# Tasks: Multi-Hop Taint Validation Fixtures

## 0. Verification (Pre-Implementation) - COMPLETED

- [x] 0.1 Confirm depth limits in codebase (verified 2024-12-09)
  - `theauditor/context/query.py:604-608` - `trace_variable_flow(depth: int = 10)`, validation `depth < 1 or depth > 10`
  - `theauditor/taint/core.py:368-370` - `trace_taint(max_depth: int = 25)`
  - `theauditor/taint/ifds_analyzer.py:58-59` - `analyze_sink_to_sources(max_depth: int = 15)`
  - **Effective limits**: query=10, IFDS=15, trace=25
- [x] 0.2 Verify current taint output format in `taint_flows` table (database is source of truth)
  - Uses `path_length`, `vulnerability_type`, `path_json` columns
  - Query: `SELECT vulnerability_type, path_length, path_json FROM taint_flows`
  - Full schema documented in design.md
- [x] 0.3 Decide hosting location
  - **Decision**: Separate repo `theauditor-fixtures` (see design.md Decision 6)

## 1. Python Project Setup (deepflow-python)

- [ ] 1.1 Create project directory structure (16 layers as per design.md)
- [ ] 1.2 Initialize FastAPI application with PostgreSQL connection
- [ ] 1.3 Create docker-compose.yml for PostgreSQL
- [ ] 1.4 Write requirements.txt with pinned versions

## 2. Python Vulnerability Chains

- [ ] 2.1 Implement SQL Injection chain (16 hops, 8 files)
  - Source: `routes/users.py` - `request.query_params.get("q")`
  - Path: routes -> middleware -> services -> processors (3) -> repositories -> adapters -> core
  - Sink: `core/query_builder.py` - f-string SQL concatenation
- [ ] 2.2 Implement Command Injection chain (12 hops, 6 files)
  - Source: `routes/reports.py` - `request.json.get("format")`
  - Sink: `core/command_executor.py` - `subprocess.run(cmd, shell=True)`
- [ ] 2.3 Implement Path Traversal chain (10 hops, 5 files)
  - Source: `routes/admin.py` - `filename` path parameter
  - Sink: `adapters/file_storage.py` - `open(path, 'rb')`
- [ ] 2.4 Implement SSRF chain (8 hops, 4 files)
  - Source: `routes/reports.py` - `request.json.get("callback_url")`
  - Sink: `adapters/external_api.py` - `requests.get(url)`
- [ ] 2.5 Implement XSS chain (14 hops, 7 files)
  - Source: `routes/reports.py` - `request.json.get("title")`
  - Sink: `core/template_renderer.py` - unescaped template variable

## 3. Python Sanitized Paths

- [ ] 3.1 Implement sanitized email validation path
  - Sanitizer: `processors/validator.py` - regex validation
  - Verify: taint chain should terminate at sanitizer
- [ ] 3.2 Implement sanitized parameterized query path
  - Sanitizer: `repositories/user_repository.py` - using `?` placeholders
  - Verify: even with tainted input, parameterized query is safe
- [ ] 3.3 Implement sanitized HTML escaping path
  - Sanitizer: `core/template_renderer.py` - using Jinja2 autoescaping
  - Verify: taint chain shows as sanitized

## 4. TypeScript Project Setup (deepflow-typescript)

- [ ] 4.1 Create project directory structure (20 layers as per design.md)
- [ ] 4.2 Initialize Express application with Sequelize + PostgreSQL
- [ ] 4.3 Create React frontend with Vite
- [ ] 4.4 Create docker-compose.yml for PostgreSQL + Redis
- [ ] 4.5 Write package.json with pinned versions

## 5. TypeScript Vulnerability Chains

- [ ] 5.1 Implement SQL Injection chain (18 hops, 10 files)
  - Source: `controllers/user.controller.ts` - `req.query`
  - Path: controllers -> middleware -> services -> processors (4) -> repositories -> adapters (3) -> core
  - Sink: `core/query.builder.ts` - template literal SQL
- [ ] 5.2 Implement XSS chain (15 hops, 8 files)
  - Source: `controllers/report.controller.ts` - `req.body.title`
  - Sink: `core/template.engine.ts` - unescaped string replacement
- [ ] 5.3 Implement Command Injection chain (10 hops, 5 files)
  - Source: `controllers/report.controller.ts` - `req.body.outputFormat`
  - Sink: `core/command.runner.ts` - `exec()` with string concatenation
- [ ] 5.4 Implement NoSQL Injection chain (12 hops, 6 files)
  - Source: `controllers/user.controller.ts` - `req.body.filter`
  - Sink: `adapters/elasticsearch.adapter.ts` - unvalidated query DSL
- [ ] 5.5 Implement Prototype Pollution chain (8 hops, 4 files)
  - Source: `controllers/user.controller.ts` - `req.body.settings`
  - Sink: `utils/serializer.ts` - recursive object merge

## 6. TypeScript Frontend-to-Backend Traces

- [ ] 6.1 Implement UserSearch component with API call
  - Source: `frontend/src/components/UserSearch.tsx` - `useState` input
  - API: `frontend/src/api/client.ts` - `fetch()` call
  - Backend: Full 18-hop chain through Express
- [ ] 6.2 Implement ReportViewer with dynamic content
  - Source: User-provided report title
  - Verify: Cross-stack trace from React -> Express -> Template -> Response
- [ ] 6.3 Verify TheAuditor connects frontend source to backend sink
  - Expected: 20-hop chain spanning 12 files

## 7. TypeScript Sanitized Paths

- [ ] 7.1 Implement sanitized input validation path
  - Sanitizer: `processors/input.validator.ts` - Joi schema validation
  - Verify: taint chain terminates at validator
- [ ] 7.2 Implement sanitized prepared statement path
  - Sanitizer: `repositories/user.repository.ts` - Sequelize parameterized
  - Verify: safe sink classification
- [ ] 7.3 Implement sanitized HTML encoding path
  - Sanitizer: `utils/string.utils.ts` - `he.encode()` call
  - Verify: XSS chain marked as sanitized

## 8. Validation and Documentation

- [ ] 8.1 Run `aud full --offline` on deepflow-python
  - Verify: Max depth >= 16 hops
  - Verify: At least 5 vulnerability types detected
  - Verify: Sanitized paths NOT reported as vulnerable
- [ ] 8.2 Run `aud full --offline` on deepflow-typescript
  - Verify: Max depth >= 20 hops
  - Verify: At least 6 vulnerability types detected
  - Verify: Frontend-to-backend traces detected
  - Verify: Sanitized paths NOT reported as vulnerable
- [ ] 8.3 Document verification results in each project's README.md
- [ ] 8.4 Create GitHub Actions workflow for CI validation

## 9. Integration

- [ ] 9.1 Add fixture projects to TheAuditor test suite (optional)
- [ ] 9.2 Update TheAuditor marketing claims with verifiable evidence
- [ ] 9.3 Archive this change after fixtures are deployed and validated
