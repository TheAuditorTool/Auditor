## 0. Verification (SOP v4.20 alignment)
- [x] 0.1 Confirmed `.graphql`/`.gql` extensions are absent from `SUPPORTED_AST_EXTENSIONS` and from the extractor registry (`theauditor/indexer/config.py:128`, `rg -n "graphql" theauditor/indexer/extractors`).
- [x] 0.2 Searched `theauditor/indexer/database.py` and `theauditor/indexer/schema.py` to verify no GraphQL tables or batches exist today.
- [x] 0.3 Reviewed pipeline staging logic around `theauditor/pipelines.py:565-619` to confirm there is no GraphQL command in Stage 2/3.
- [x] 0.4 Audited `theauditor/rules/security/api_auth_analyze.py` and `input_validation_analyze.py` to document current GraphQL heuristics.
- [x] 0.5 Verified `theauditor/fce.py` and taint source definitions contain no GraphQL-specific handling.

## 1. Implementation
- [ ] 1.1 Add `.graphql`, `.gql`, and `.graphqls` coverage to the extractor registry, implement `theauditor/indexer/extractors/graphql.py` with `graphql-core` AST parsing, and extend `FileWalker`/config as needed.
- [ ] 1.2 Extend `theauditor/indexer/schema.py`, `theauditor/indexer/database.py`, and `DatabaseManager` with new tables/batch writers for schemas, types, fields, arguments, and resolver mappings (including execution edges).
- [ ] 1.3 Enhance the JavaScript and Python extractors to recognise Apollo Server, Yoga, Graphene, and Ariadne resolver registrations, emitting rows keyed to existing `symbols` entries without regex heuristics.
- [ ] 1.4 Introduce `aud graphql build` within `theauditor/commands/graphql.py`, invoked during Stage 2 of `aud full`, to populate the execution graph tables and export `.pf/raw/graphql_schema.json` plus `.pf/raw/graphql_execution.json`.
- [ ] 1.5 Update taint (`theauditor/taint/core.py`, `memory_cache.py`, `sources.py`, `database.py`) so GraphQL arguments register as sources and resolver->sink flows traverse the execution graph.
- [ ] 1.6 Create `theauditor/rules/graphql` with orchestrator-compliant rules for auth coverage, taint-based injection, over-fetching, and N+1 detection, persisting findings into `findings_consolidated`.
- [ ] 1.7 Teach the FCE (`theauditor/fce.py`) to incorporate GraphQL findings, attach provenance to the new tables, and expose aggregated output for downstream agents.
- [ ] 1.8 Refresh CLI/docs (`theauditor/cli.py`, README/HOWTOUSE) to document the GraphQL command group, pipeline integration, and new courier artefacts.
- [ ] 1.9 Add unit/integration coverage for the extractor, resolver mapping, new rules, taint paths, and FCE reporting (e.g., tests under `tests/graphql/`).

## 2. Validation
- [ ] 2.1 Run `openspec validate add-graphql-execution-graph --strict`.
- [ ] 2.2 Execute `aud index`, `aud graphql build`, `aud full`, and ensure `.pf/raw/graphql_*.json` plus new database tables populate as expected on the sample project.
- [ ] 2.3 Run targeted test suites (`pytest tests/graphql`, `pytest tests/taint`, `pytest tests/rules`) along with `ruff check .` and `mypy theauditor --strict`.
