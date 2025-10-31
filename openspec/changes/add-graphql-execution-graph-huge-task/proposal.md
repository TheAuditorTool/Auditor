## Why
- The indexer ignores `.graphql`/`.gql` files and the SQLite schema has no tables for types, fields, or resolvers, leaving GraphQL routes invisible to downstream analysis.
- Security rules today guess at resolver behaviour by string matching `function_call_args` (verified at api_auth_analyze.py:318-347), which yields medium-confidence findings and misses framework-specific auth, taint, and N+1 issues.
- The Factual Correlation Engine cannot surface GraphQL risks because neither the pipeline nor the courier outputs capture schema facts or resolver execution data (verified via grep - no GraphQL mentions in fce.py or taint/sources.py).

## What Changes

**CRITICAL**: Architecture has been refactored since original design. This proposal now follows the CURRENT modular patterns (verified against source code per teamsop.md Prime Directive).

**Schema Layer** (NEW):
- Create `theauditor/indexer/schemas/graphql_schema.py` following modular TableSchema pattern (verified from schemas/ directory structure)
- Export `GRAPHQL_TABLES` dict with 8 tables: graphql_schemas, graphql_types, graphql_fields, graphql_field_args, graphql_resolver_mappings, graphql_resolver_params, graphql_execution_edges, graphql_findings_cache
- Update `schema.py:62-70` to merge GRAPHQL_TABLES into master TABLES registry (108 → 116 tables)

**Database Layer** (NEW):
- Create `theauditor/indexer/database/graphql_database.py` as GraphQLDatabaseMixin (verified from frameworks_database.py:10-81 pattern)
- Implement add_* methods: add_graphql_schema, add_graphql_type, add_graphql_field, add_graphql_field_arg, add_graphql_resolver_mapping, add_graphql_resolver_param, add_graphql_execution_edge
- Update `database/__init__.py:44-73` to inherit GraphQLDatabaseMixin in DatabaseManager

**Storage Layer** (UPDATE):
- Update `theauditor/indexer/storage.py` to register 6 new handlers in DataStorer.handlers dict (verified at storage.py:42-110)
- Implement _store_graphql_* handler methods following existing pattern (66 → 72 handlers)

**Extractor Layer** (NEW + UPDATE):
- NEW: `theauditor/indexer/extractors/graphql.py` with @register_extractor decorator for SDL parsing (.graphql/.gql/.graphqls)
- UPDATE: `extractors/javascript.py` to detect Apollo/NestJS/TypeGraphQL resolver patterns (AST-only, NO regex)
- UPDATE: `extractors/python.py` to detect Graphene/Ariadne/Strawberry resolver patterns (AST-only, NO regex)
- UPDATE: `config.py:128-138` to add GraphQL extensions to SUPPORTED_AST_EXTENSIONS

**Pipeline Layer** (UPDATE):
- NEW: `theauditor/commands/graphql.py` with build/analyze/dump subcommands following Click pattern
- UPDATE: `theauditor/cli.py` to register graphql command group
- UPDATE: `theauditor/pipelines.py:605-629` to categorize "graphql build" into data_prep_commands (Stage 2) after graph build

**Rules Layer** (NEW + UPDATE):
- NEW: `theauditor/rules/graphql/` package with auth.py, injection.py, nplus1.py, overfetch.py modules
- UPDATE: `rules/security/api_auth_analyze.py` to use graphql_resolver_mappings instead of string heuristics
- All rules use build_query for schema-contract compliance

**Taint Integration** (UPDATE):
- UPDATE: `taint/sources.py` to register GraphQL field arguments as taint sources via graphql_resolver_params mapping
- UPDATE: `taint/database.py` and `memory_cache.py` to preload GraphQL tables for O(1) lookups

**FCE Integration** (UPDATE):
- UPDATE: `fce.py` to ingest findings from graphql_findings_cache and surface in report_summary.json

## Impact
- Elevates GraphQL analysis to first-class status, enabling deterministic resolver execution graphs and eliminating name-based guessing in security scanners.
- Follows CURRENT refactored architecture (mixin pattern, modular schema, storage handlers) verified against source code.
- Unlocks taint, auth, and performance findings for GraphQL APIs using the same database-first architecture that powers REST analysis.
- Provides AI agents and humans with stable JSON/courier artefacts rooted in the SQLite ground truth.

## Verification Alignment (SOP v4.20 - UPDATED)
- **Phase 0 Verification**: All hypotheses tested against CURRENT refactored codebase (post-modular architecture).
- **Evidence**: `verification.md` captures 7 hypotheses with file paths, line numbers, and grep results.
- **Discrepancies**: 4 MAJOR discrepancies found - old assumptions about monolithic database.py/schema.py WRONG.
- **Design**: `design.md` updated with correct file paths, mixin patterns, storage handler registration, and pipeline categorization.
