## 0. Verification (SOP v4.20 - COMPLETED POST-REFACTOR)
- [x] 0.1 Verified `.graphql`/`.gql` extensions absent from `SUPPORTED_AST_EXTENSIONS` (`config.py:128-138`) and NO graphql.py in extractors/
- [x] 0.2 Discovered MAJOR REFACTOR: database.py → database/ package (mixin architecture), schema.py → schemas/ package (modular)
- [x] 0.3 Verified NO GraphQL tables in repo_index.db via sqlite3 query, NO graphql_schema.py in schemas/, NO graphql_database.py in database/
- [x] 0.4 Verified pipeline changed from simple Stage 2/3 to 4-stage architecture with parallel tracks (pipelines.py:594-629)
- [x] 0.5 Verified storage layer extracted to storage.py with DataStorer class (66 handlers) - extractors NO longer directly call DatabaseManager
- [x] 0.6 Verified security rules use string heuristics (`api_auth_analyze.py:318-347` with GRAPHQL_PATTERNS frozenset)
- [x] 0.7 Verified NO GraphQL support in fce.py or taint/sources.py via grep
- [x] 0.8 Updated ALL proposal documents (verification.md, design.md, proposal.md) with corrected architecture references

## 1. Schema Layer Implementation
- [ ] 1.1 Create `theauditor/indexer/schemas/graphql_schema.py` following TableSchema pattern from utils.py
- [ ] 1.2 Define 8 GraphQL tables using Column/ForeignKey/TableSchema classes: graphql_schemas, graphql_types, graphql_fields, graphql_field_args, graphql_resolver_mappings, graphql_resolver_params, graphql_execution_edges, graphql_findings_cache
- [ ] 1.3 Export GRAPHQL_TABLES dict at module level
- [ ] 1.4 Update `theauditor/indexer/schema.py:62-70` to import and merge GRAPHQL_TABLES (update assertion from 108 → 116 tables)
- [ ] 1.5 Verify schema loads without errors by running Python: `from theauditor.indexer.schema import TABLES; print(len(TABLES))`

## 2. Database Layer Implementation
- [ ] 2.1 Create `theauditor/indexer/database/graphql_database.py` as GraphQLDatabaseMixin class
- [ ] 2.2 Implement 7 add_* methods (add_graphql_schema, add_graphql_type, add_graphql_field, add_graphql_field_arg, add_graphql_resolver_mapping, add_graphql_resolver_param, add_graphql_execution_edge) using self.generic_batches pattern
- [ ] 2.3 Ensure NO try/except fallbacks, NO table existence checks (CRITICAL: Zero Fallback Policy from CLAUDE.md)
- [ ] 2.4 Update `theauditor/indexer/database/__init__.py:44-73` to import GraphQLDatabaseMixin and add to DatabaseManager inheritance chain
- [ ] 2.5 Verify DatabaseManager instantiates without errors by running: `from theauditor.indexer.database import DatabaseManager; print(DatabaseManager.__mro__)`

## 3. Storage Layer Implementation
- [ ] 3.1 Update `theauditor/indexer/storage.py:42-110` to register 6 new handlers in DataStorer.__init__ handlers dict
- [ ] 3.2 Implement 6 _store_graphql_* handler methods (after line ~1800) following existing pattern from _store_imports, _store_routes, etc.
- [ ] 3.3 Each handler must: iterate records, call db_manager.add_graphql_*, update self.counts, NO try/except
- [ ] 3.4 Verify DataStorer loads without errors: `from theauditor.indexer.storage import DataStorer; print(len(DataStorer(None, {}).handlers))`

## 4. Extractor Layer Implementation
- [ ] 4.1 Create `theauditor/indexer/extractors/graphql.py` with @register_extractor decorator
- [ ] 4.2 Implement GraphQLExtractor.supported_extensions property returning ['.graphql', '.gql', '.graphqls']
- [ ] 4.3 Implement GraphQLExtractor.extract() using graphql-core for SDL parsing, returning dict with keys: graphql_schemas, graphql_types, graphql_fields, graphql_field_args
- [ ] 4.4 Update `theauditor/indexer/config.py:128-138` to add ['.graphql', '.gql', '.graphqls'] to SUPPORTED_AST_EXTENSIONS
- [ ] 4.5 Update `theauditor/indexer/extractors/javascript.py` to detect Apollo/NestJS resolver patterns, return graphql_resolver_mappings and graphql_resolver_params (AST-only, NO regex)
- [ ] 4.6 Update `theauditor/indexer/extractors/python.py` to detect Graphene/Ariadne resolver patterns, return graphql_resolver_mappings and graphql_resolver_params (AST-only, NO regex)
- [ ] 4.7 Verify extractor registration: `from theauditor.indexer.extractors import ExtractorRegistry; print([e.__class__.__name__ for e in ExtractorRegistry(Path('.'), None).extractors.values()])`

## 5. Pipeline & CLI Implementation
- [ ] 5.1 Create `theauditor/commands/graphql.py` with @click.group() and 3 subcommands: build, analyze, dump
- [ ] 5.2 Implement graphql_build() to read graphql_resolver_mappings, join with graphs.db call edges, populate graphql_execution_edges
- [ ] 5.3 Export `.pf/raw/graphql_schema.json` and `.pf/raw/graphql_execution.json` with provenance
- [ ] 5.4 Update `theauditor/cli.py` to import and register graphql command group: `from theauditor.commands import graphql; cli.add_command(graphql.graphql)`
- [ ] 5.5 Update `theauditor/pipelines.py:605-629` to add categorization logic: `elif "graphql build" in cmd_str: data_prep_commands.append((phase_name, cmd))`
- [ ] 5.6 Ensure status reporting writes `.pf/status/graphql_build.status` file
- [ ] 5.7 Verify CLI registration: `aud graphql --help` shows build/analyze/dump subcommands

## 6. Rules Layer Implementation
- [ ] 6.1 Create `theauditor/rules/graphql/` package with __init__.py
- [ ] 6.2 Implement `auth.py` - check graphql_resolver_mappings + function_call_args for auth decorators/directives
- [ ] 6.3 Implement `injection.py` - leverage taint_flows + graphql_execution_edges to detect unsanitized argument→SQL/command flows
- [ ] 6.4 Implement `nplus1.py` - inspect graphql_execution_edges + cfg_blocks to detect DB queries in per-item loops
- [ ] 6.5 Implement `overfetch.py` - cross-check resolver returns + ORM fields with graphql_fields to flag unexposed sensitive attributes
- [ ] 6.6 All rules use build_query for schema-contract compliance, emit to findings_consolidated
- [ ] 6.7 Update `theauditor/rules/security/api_auth_analyze.py` to replace _check_graphql_mutations() with database query against graphql_resolver_mappings

## 7. Taint & FCE Integration
- [ ] 7.1 Update `theauditor/taint/sources.py` to register GraphQLFieldSource entries from graphql_fields + graphql_resolver_params
- [ ] 7.2 Update `theauditor/taint/database.py` to load graphql_* tables via build_query
- [ ] 7.3 Update `theauditor/taint/memory_cache.py` to preload graphql tables into in-memory cache structures
- [ ] 7.4 Update `theauditor/taint/core.py` to seed initial frontier with GraphQL field arguments, propagate through graphql_execution_edges
- [ ] 7.5 Update `theauditor/fce.py` to query graphql_findings_cache, merge into report_summary.json with graphql section

## 8. Testing & Validation
- [ ] 8.1 Create `tests/fixtures/graphql/` with sample .graphql schemas and resolver files (JavaScript + Python)
- [ ] 8.2 Create `tests/test_graphql_extractor.py` for SDL parsing and resolver mapping
- [ ] 8.3 Create `tests/test_graphql_database.py` for schema creation and batch operations
- [ ] 8.4 Create `tests/test_graphql_rules.py` for auth/injection/nplus1/overfetch rules
- [ ] 8.5 Run `aud index` on fixtures, verify graphql_* tables populated
- [ ] 8.6 Run `aud graphql build`, verify .pf/raw/graphql_*.json files created
- [ ] 8.7 Run `aud full --offline`, verify GraphQL findings in report_summary.json
- [ ] 8.8 Run `pytest tests/graphql/` - all tests pass
- [ ] 8.9 Run `ruff check .` - no new linting errors
- [ ] 8.10 Run `mypy theauditor --strict` - no type errors

## 9. Documentation & Final Validation
- [ ] 9.1 Update CLI help strings in graphql.py commands
- [ ] 9.2 Update README with GraphQL workflow example
- [ ] 9.3 Update HOWTOUSE.md with aud graphql command documentation
- [ ] 9.4 Run `openspec validate add-graphql-execution-graph-huge-task --strict` - passes
- [ ] 9.5 Verify all tasks.md checkboxes marked [x]
