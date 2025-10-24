## ADDED Requirements
### Requirement: Codebase Context Overview
The CLI MUST expose `aud context code --overview` to emit a factual snapshot of the repository using only data captured by prior analysis runs.

#### Scenario: Overview Without Extra Crawls
- **GIVEN** `.pf/repo_index.db` and `.pf/graphs.db` exist from a completed `aud full`
- **WHEN** the user runs `aud context code --overview`
- **THEN** the command reads language, framework, entrypoint, service, and dependency metrics from the existing `files`, `frameworks`, `refs`, `package_configs`, and `edges` tables
- **AND** writes `.pf/raw/context_overview.json` plus chunked `.pf/readthis/context_overview_*.json` files that stay within the configured courier limits
- **AND** each section includes provenance metadata referencing the exact source table or JSON file

### Requirement: Targeted Dependency Neighborhood
The system MUST return focused relationship context for a requested file, symbol, or route without inventing data.

#### Scenario: File-Level Context Request
- **GIVEN** a repo analyzed with `aud full` and a file `services/payments.py` recorded in the `files` table
- **WHEN** the user runs `aud context code --target services/payments.py`
- **THEN** the command returns inbound/outbound imports and calls (from `edges` with `graph_type='import'` and `graph_type='call'`), linked symbols (`symbols`, `function_call_args`, `function_returns`), and taint flows from `.pf/raw/taint_analysis.json` if present
- **AND** the result is stored as `.pf/raw/context_target_services_payments.py.json` plus chunked AI-ready files, each fact citing its provenance

#### Scenario: Symbol-Level Context Request
- **GIVEN** call graph data for `AuthService.login` stored in `graphs.db`
- **WHEN** the user runs `aud context code --symbol AuthService.login`
- **THEN** the response lists defining file, callers, callees, and related return metadata derived from `edges` (`graph_type='call'`) and `function_returns`
- **AND** every relationship item includes provenance referencing the contributing table and row identifiers

#### Scenario: Route-Level Context Request
- **GIVEN** HTTP route metadata stored in `api_endpoints` after `aud full`
- **WHEN** the user runs `aud context code --route /api/payments`
- **THEN** the command returns handler files, upstream callers, and downstream services using `api_endpoints`, call/import edges, and `compose_services` data
- **AND** the payload is saved as `.pf/raw/context_route__api_payments.json` with chunked variants and provenance for each fact

### Requirement: Cross-Stack Map Presets
The CLI MUST surface curated cross-stack relationship presets that bundle frontend, backend, and infrastructure links.

#### Scenario: Cross-Stack Output
- **GIVEN** the project includes Vue frontend components (`vue_components`), HTTP endpoints (`api_endpoints`), and service definitions (`compose_services` or import edges)
- **WHEN** the user runs `aud context code --cross-stack`
- **THEN** the command assembles chains that join components to API handlers and downstream services using existing tables (`vue_components`, `api_endpoints`, relevant `edges`) without fabricating data
- **AND** the resulting `.pf/raw/context_cross_stack.json` file and chunked outputs group each chain with clear provenance and remain within courier chunk limits

### Requirement: Full Context Export
The CLI MUST provide a `--full` option that emits a consolidated payload containing every preset.

#### Scenario: Full Context Dump
- **GIVEN** prior analysis artifacts are available
- **WHEN** the user runs `aud context code --full`
- **THEN** the command aggregates overview, cross-stack, top dependency hotspots, and any requested targets into `.pf/raw/context_full.json`
- **AND** chunked `.pf/readthis/context_full_*.json` files are produced by the courier chunker, each embedding provenance for every fact and metadata describing which presets were combined

### Requirement: Truth Courier Compliance
The feature MUST preserve the Truth Courier vs Insights separation and record provenance for every context fact.

#### Scenario: Provenance Included
- **GIVEN** any `aud context code` invocation completes successfully
- **WHEN** examining generated context payloads
- **THEN** each fact includes machine-readable provenance (table name or JSON artifact) and omits severity scoring or speculation
- **AND** the command aborts with an actionable error if required caches (`repo_index.db`, `graphs.db`) are missing, instead of running partial queries

### Requirement: AI-Focused Help Guidance
The CLI help MUST highlight AI-first usage patterns, including direct database access options for assistants.

#### Scenario: Updated Help Output
- **GIVEN** the new `code` subcommand is available
- **WHEN** running `aud context --help` or `aud context code --help`
- **THEN** the help text documents the overview/target/cross-stack/full presets, explains raw vs chunked output locations, and provides runnable Python/SQLite examples against `.pf/repo_index.db` and `.pf/graphs.db`
- **AND** the top-level `aud --help` summary references the expanded `context` command group so autonomous agents discover the new capability
