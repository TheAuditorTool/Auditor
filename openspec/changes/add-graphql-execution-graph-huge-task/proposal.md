## Why
- The indexer ignores `.graphql`/`.gql` files and the SQLite schema has no tables for types, fields, or resolvers, leaving GraphQL routes invisible to downstream analysis.
- Security rules today guess at resolver behaviour by string matching `function_call_args`, which yields medium-confidence findings and misses framework-specific auth, taint, and N+1 issues.
- The Factual Correlation Engine cannot surface GraphQL risks because neither the pipeline nor the courier outputs capture schema facts or resolver execution data.

## What Changes
- Introduce an AST-backed GraphQL extractor that parses schema files, persists type/field/argument metadata, and fingerprints schema versions in `repo_index.db`.
- Extend the JavaScript and Python extractors to build a resolver execution map that links GraphQL fields to concrete `symbols` rows and stores call edges for downstream taint/graph analysis.
- Add GraphQL-aware tables (`graphql_schemas`, `graphql_types`, `graphql_fields`, `graphql_field_args`, `graphql_resolver_mappings`, and derived execution edges) plus DatabaseManager batch writers and schema contracts.
- Wire `aud full` to run a new `aud graphql build` Stage 2 step that materialises `.pf/raw/graphql_schema.json` / `.pf/raw/graphql_execution.json` while seeding the new database tables.
- Create a `theauditor/rules/graphql` package with orchestrator-compliant rules for missing auth, injection, N+1 detection, and overfetching that query the new tables and register findings in `findings_consolidated`.
- Extend the taint engine and memory cache so GraphQL arguments become taint sources and resolver->sink flows can be traced without heuristics.
- Update the FCE to ingest GraphQL-specific findings, attach provenance back to the new tables, and expose the data to downstream consumers.

## Impact
- Elevates GraphQL analysis to first-class status, enabling deterministic resolver execution graphs and eliminating name-based guessing in security scanners.
- Unlocks taint, auth, and performance findings for GraphQL APIs using the same database-first architecture that powers REST analysis, keeping orchestration and courier outputs consistent.
- Provides AI agents and humans with stable JSON/courier artefacts rooted in the SQLite ground truth, making GraphQL risks visible across the entire pipeline.

## Verification Alignment
- Evidence collected in `openspec/changes/add-graphql-execution-graph/verification.md` per SOP v4.20.
- Detailed architecture and integration notes captured in `design.md` for reviewer walkthroughs.
