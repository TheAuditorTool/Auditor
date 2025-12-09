## ADDED Requirements

### Requirement: Multi-Hop Taint Validation Fixtures

TheAuditor SHALL provide purpose-built test projects that validate its interprocedural dataflow analysis capabilities with intentionally deep vulnerability chains.

#### Scenario: Python fixture with 16-hop chains

- **WHEN** `aud full --offline` is run on `deepflow-python/`
- **THEN** the taint analysis SHALL detect vulnerability chains with depth >= 16 hops
- **AND** the chains SHALL span >= 8 distinct source files
- **AND** at least 5 distinct vulnerability types SHALL be detected (SQLi, Command Injection, Path Traversal, SSRF, XSS)

#### Scenario: TypeScript fixture with 20-hop chains

- **WHEN** `aud full --offline` is run on `deepflow-typescript/`
- **THEN** the taint analysis SHALL detect vulnerability chains with depth >= 20 hops
- **AND** the chains SHALL span >= 10 distinct source files
- **AND** at least 6 distinct vulnerability types SHALL be detected (SQLi, XSS, Command Injection, NoSQL Injection, Prototype Pollution, plus frontend-to-backend)

#### Scenario: Sanitizer detection terminates chains

- **WHEN** a taint source flows through a recognized sanitizer pattern
- **THEN** the vulnerability chain SHALL NOT be reported as exploitable
- **AND** each fixture project SHALL contain at least 3 sanitized paths demonstrating this behavior

### Requirement: Fixture Project Executability

Each fixture project SHALL be a fully runnable application, not a test fixture or synthetic code.

#### Scenario: Python fixture runs locally

- **WHEN** user runs `docker-compose up -d db && uvicorn app.main:app`
- **THEN** the FastAPI application SHALL start and respond to HTTP requests
- **AND** the vulnerable endpoints SHALL be exploitable (for demonstration purposes)

#### Scenario: TypeScript fixture runs locally

- **WHEN** user runs `docker-compose up -d && npm run build && npm start`
- **THEN** the Express backend SHALL start and respond to HTTP requests
- **AND** the React frontend SHALL connect to the backend
- **AND** frontend-to-backend vulnerability chains SHALL be traceable

### Requirement: Realistic Architecture Patterns

Fixture projects SHALL use enterprise architecture patterns to ensure vulnerability chains are realistic, not synthetic.

#### Scenario: Python layered architecture

- **WHEN** the Python fixture is examined
- **THEN** it SHALL contain these layers: routes, middleware, services, processors (transformer/validator/enricher), repositories, adapters (cache/external/file), core (query_builder/command_executor/template_renderer), utils
- **AND** each layer SHALL be in a separate file to force cross-file dataflow

#### Scenario: TypeScript layered architecture

- **WHEN** the TypeScript fixture is examined
- **THEN** it SHALL contain these layers: controllers, middleware, services, processors (transformer/validator/enricher/formatter), repositories, adapters (redis/elasticsearch/s3), core (query_builder/command_runner/template_engine), utils
- **AND** the frontend SHALL be a separate React application with API client
- **AND** each layer SHALL be in a separate file to force cross-file dataflow

### Requirement: Verifiable Success Criteria

Fixture validation SHALL be automated and produce machine-readable output.

#### Scenario: Depth distribution analysis

- **WHEN** `aud full --offline` completes on either fixture
- **THEN** the `.pf/repo_index.db` database SHALL contain `taint_flows` table entries with `path_json` data
- **AND** a verification script SHALL report:
  - Maximum depth observed
  - Depth distribution histogram
  - Cross-file transition count per chain
  - Vulnerability type breakdown

#### Scenario: CI validation workflow

- **WHEN** changes are pushed to the fixture repositories
- **THEN** a GitHub Actions workflow SHALL run `aud full --offline`
- **AND** the workflow SHALL fail if maximum depth < expected threshold
- **AND** the workflow SHALL fail if sanitized paths are reported as vulnerable

### Requirement: Intentional Vulnerability Patterns

Each vulnerability type SHALL follow a documented pattern ensuring the chain is actually exploitable.

#### Scenario: SQL Injection pattern

- **WHEN** a SQL Injection chain is traced
- **THEN** it SHALL contain:
  - Source: HTTP request parameter (`req.query`, `request.query_params`)
  - Propagation: Variable assignments through each layer
  - Sink: String concatenation or f-string into SQL query
  - Execution: `cursor.execute(sql)` or `sequelize.query(sql)`

#### Scenario: Command Injection pattern

- **WHEN** a Command Injection chain is traced
- **THEN** it SHALL contain:
  - Source: HTTP request body field
  - Propagation: Through service/processor layers
  - Sink: String concatenation into shell command
  - Execution: `subprocess.run(cmd, shell=True)` or `child_process.exec()`

#### Scenario: Path Traversal pattern

- **WHEN** a Path Traversal chain is traced
- **THEN** it SHALL contain:
  - Source: URL path parameter or query parameter
  - Propagation: Through file handling layers
  - Sink: `os.path.join()` or path concatenation without validation
  - Execution: `open(path)` or `fs.readFile(path)`

#### Scenario: XSS pattern

- **WHEN** an XSS chain is traced
- **THEN** it SHALL contain:
  - Source: HTTP request body field
  - Propagation: Through template data layers
  - Sink: Unescaped template variable or string replacement
  - Execution: HTML response sent to browser

#### Scenario: Sanitizer interruption pattern

- **WHEN** a sanitized path is traced
- **THEN** the chain SHALL contain:
  - Source: HTTP request parameter
  - Sanitizer: Recognized pattern (regex validation, parameterized query, HTML escaping)
  - Post-sanitizer: Even if data reaches a "sink", it SHALL be marked as SAFE
  - Output: Vulnerability SHALL NOT appear in final report
