# Design: GraphQL Resolver Execution Graph

## Verification Summary (SOP v4.20)
- `theauditor/indexer/config.py:128` lists `SUPPORTED_AST_EXTENSIONS` without any GraphQL extensions, and `rg -n "graphql" theauditor/indexer/extractors` produced no matches, proving there is no extractor coverage today.
- `rg -n "graphql" theauditor/indexer/database.py` and `rg -n "graphql" theauditor/indexer/schema.py` returned zero results, so the SQLite schema and `DatabaseManager` lack GraphQL tables or batch writers.
- Pipeline staging at `theauditor/pipelines.py:565-619` only recognises index/workset/graph/cfg/metadata commands in Stage 2 and has no GraphQL command wiring.
- `theauditor/rules/security/api_auth_analyze.py:301-321` and `theauditor/rules/security/input_validation_analyze.py:505-520` rely on string searches against `function_call_args` rather than resolver metadata, yielding medium-confidence findings.
- `rg -n "graphql" theauditor/fce.py` and `rg -n "graphql" theauditor/taint/sources.py` confirmed neither the Factual Correlation Engine nor the taint engine understands GraphQL artefacts.

## Goals
1. Parse GraphQL schemas and resolvers with deterministic AST tooling, persisting canonical metadata into `repo_index.db` and exporting courier artefacts without guessing.
2. Build a resolver execution graph that links GraphQL fields to concrete backend symbols, enabling taint traces, auth analysis, and performance checks across languages.
3. Integrate the new data with the existing pipeline, taint engine, rules orchestrator, and FCE so GraphQL risks surface alongside REST findings using the same database-first guarantees.

## Database Schema Additions
All tables live in `theauditor/indexer/schema.py` and `theauditor/indexer/database.py` with matching batch queues in `DatabaseManager`.

| Table | Purpose | Key Columns | Notes |
|-------|---------|-------------|-------|
| `graphql_schemas` | Track each schema file and fingerprint | `file_path` (PK), `schema_hash`, `language` (`'sdl'`, `'code-first'`), `last_modified` | Enables change detection and multi-schema projects. |
| `graphql_types` | Normalised type definitions | `type_id` (PK AUTOINCREMENT), `schema_path` (FK to `graphql_schemas.file_path`), `type_name`, `kind`, `implements`, `description` | One row per type/interface/input/enum. |
| `graphql_fields` | Field metadata per type | `field_id` (PK AUTOINCREMENT), `type_id` FK, `field_name`, `return_type`, `is_list`, `is_nullable`, `directives_json`, `line`, `column` | Captures directives/nullable/list semantics. |
| `graphql_field_args` | Argument definitions | Composite PK `(field_id, arg_name)`, columns: `arg_type`, `has_default`, `default_value`, `is_nullable`, `directives_json` | Normalises arguments instead of JSON blobs. |
| `graphql_resolver_mappings` | Bridge fields to backend code | Composite PK `(field_id, resolver_symbol_id)`, columns: `resolver_path`, `resolver_line`, `resolver_language`, `resolver_export`, `binding_style` (`'apollo-object'`, `'apollo-class'`, `'graphene-decorator'`, etc.) | Links to `symbols` for precise taint + rule queries. |
| `graphql_resolver_params` | Map GraphQL args to function params | Composite PK `(resolver_symbol_id, arg_name)`, columns: `param_name`, `param_index`, `is_kwargs`, `is_list_input` | Enables correct taint parameter mapping. |
| `graphql_execution_edges` | Derived resolver execution graph | Composite PK `(from_field_id, to_symbol_id, edge_kind)`, where `edge_kind` in `('resolver', 'downstream_call')` | `resolver` edges connect field -> resolver symbol; `downstream_call` edges connect resolver symbol -> callee symbol ID sourced from the existing call graph. |
| `graphql_findings_cache` | Optional summary for FCE fast paths | `finding_id` (PK AUTOINCREMENT), `field_id`, `resolver_symbol_id`, `rule`, `severity`, `details_json`, `provenance` | Mirrors other domain caches to avoid recomputing heavy joins inside FCE. |

Batch writers will mirror existing patterns (`self.graphql_schema_batch`, etc.) with `flush_graphql_batches()` invoked during indexer finalisation. Schema validation via `TABLES['graphql_schemas']` et al. ensures migrations stay consistent.

## Extraction Workflow

### Schema Pass
- Add `theauditor/indexer/extractors/graphql.py` implementing `BaseExtractor` and using `graphql-core` (already vendored) for SDL parsing. The extractor:
  1. Registers `.graphql`, `.gql`, `.graphqls` in `supported_extensions()`.
  2. Loads the SDL file, parses to an AST (`graphql.language.parser.parse`), and walks definitions to emit `GraphQLSchemaRecord`, `GraphQLTypeRecord`, `GraphQLFieldRecord`, and `GraphQLArgumentRecord` dataclasses.
  3. Computes `schema_hash` via `hashlib.sha256` over the canonical AST dump to deduplicate identical schemas.
  4. Stores directives and descriptions as JSON-serialised metadata so downstream rules can reason about auth directives (e.g., `@auth`, `@requiresRole`).

- For code-first schemas (NestJS/TypeGraphQL, Graphene), we reuse existing JavaScript/Python extractors to capture the schema definitions alongside resolver mapping (below). GraphQL extractor remains SDL-only; code-first detection depends on the resolver mapping stage to record `language='code-first'` for relevant types.

### Resolver Mapping Pass
- **JavaScript / TypeScript** (`theauditor/indexer/extractors/javascript.py`):
  - Extend AST walkers to recognise Apollo objects like `const resolvers = { Query: { user: () => ... } }`, module exports (`export const resolvers = { ... }`), `makeExecutableSchema({ resolvers })`, and NestJS resolver classes decorated with `@Resolver('Type')` and methods decorated with `@Query`, `@Mutation`, or `@ResolveField`.
  - The walker resolves identifiers to existing `symbols` rows (function declarations, arrow functions, class methods) by matching AST node spans (path + line/column) with `symbols` entries generated earlier in the extractor.
  - For each binding, emit `graphql_resolver_mappings` and `graphql_resolver_params` entries using parameter AST metadata to capture argument ordering and destructuring.

- **Python** (`theauditor/indexer/extractors/python.py`):
  - Detect Graphene/Ariadne patterns: classes inheriting from `graphene.ObjectType` with methods returning resolvers, `@query.field("name")` decorators, and `graphql_app.add_route("/graphql", GraphQL(..., schema=schema))` to associate schema objects.
  - Use the semantic AST to locate function definitions and tie them to `symbols` rows, storing decorator metadata to populate `binding_style` and support auth directive checks.

- Both extractors rely on AST and existing symbol maps—no regex heuristics—and push resolver information via `DatabaseManager` helper methods (`add_graphql_resolver_mapping`, `add_graphql_resolver_param`). They also record the GraphQL type/field key so we can join back to SDL entries.

## Resolver Execution Graph
- After indexer batches flush, invoke a lightweight builder inside the new `aud graphql build` command that:
  1. Reads `graphql_resolver_mappings` and `symbols` to create `resolver` edges (field -> resolver symbol).
  2. Joins the call graph from `.pf/graphs.db` (call edges) to materialise `downstream_call` edges for each resolver's callees, storing them in `graphql_execution_edges`. This reuses the existing call graph rather than recomputing static analysis.
  3. Generates adjacency lists for taint (field -> resolver params) and for rule queries (e.g., fetch all DB calls reachable from a resolver).
- The builder exports `.pf/raw/graphql_execution.json` containing a serialised view (types, fields, resolver symbol metadata, immediate downstream calls) with provenance for each edge, keeping JSON consumers in sync with the SQLite truth.

## Pipeline & CLI Integration
- Create `theauditor/commands/graphql.py` exposing a Click group with `build`, `analyze`, and `dump` subcommands. `aud graphql build` orchestrates the execution graph steps above and is invoked from Stage 2 of `aud full` right after `aud graph build` so the downstream tracks can consume the data.
- Update `theauditor/pipelines.py` staging logic to classify `"graphql build"` as a Stage 2 command and ensure status reporting writes to `.pf/status/graphql_build.status` like other tracks.
- `aud graphql analyze` (optional follow-up task) can summarise schema coverage, orphaned resolvers, and directive usage; this subcommand does not run during `aud full` but provides manual inspection tooling.
- CLI help and README/HOWTOUSE updates document how `aud graphql build` depends on a prior `aud index`, where to find results, and how AI agents should query the SQLite tables through `build_query` to stay orchestrator-compliant.

## Taint & Graph Integration
- Extend `theauditor/taint/sources.py` to include dynamic GraphQL sources registered at runtime: for each `graphql_fields` row, add a `GraphQLFieldSource` entry mapping GraphQL argument names to resolver parameter slots via `graphql_resolver_params`.
- Update `theauditor/taint/database.py` and `memory_cache.py` to preload the new tables into in-memory structures (`cache.graphql_fields`, `cache.graphql_resolver_edges`), enabling O(1) lookups when seeding taint flows.
- Modify `theauditor/taint/core.py` so the initial frontier includes GraphQL field arguments, automatically linking them to resolver parameters; the propagation step then leverages existing call graph edges (plus `graphql_execution_edges`) to reach sinks.
- Integrate GraphQL nodes into the existing graph database (`theauditor/graph/store.py`) by adding a `graph_type='graphql'` edge set, allowing impact analysis and context commands to traverse GraphQL relationships alongside imports/calls.

## Rules & FCE
- Add `theauditor/rules/graphql/` with orchestrator-compliant modules such as:
  - `auth.py` — verifies each resolver for sensitive fields includes auth directives or hits known auth decorators/functions (`graphql_resolver_mappings` + `function_call_args` + directives).
  - `injection.py` — leverages taint traces from GraphQL arguments through resolver execution edges into SQL/command sinks, emitting high-confidence findings when sanitisation is absent.
  - `nplus1.py` — inspects `graphql_execution_edges` and CFG metadata (`cfg_blocks`, `cfg_block_statements`) to detect DB queries executed inside per-item loops.
  - `overfetch.py` — cross-checks resolver return metadata (`function_returns`, ORM tables) with GraphQL field selections to flag exposure of sensitive model attributes not declared in the schema.
- Rules use `build_query` wrappers so they remain schema-contract compliant. Findings write to `findings_consolidated` with provenance referencing the GraphQL table rows.
- Enhance `theauditor/fce.py` to pull pre-computed GraphQL findings from `graphql_findings_cache` (or query the new tables directly) and merge them into the consolidated evidence packs and `.pf/raw/report_summary.json` outputs, preserving severity ordering.

## Outputs & Courier Artefacts
- `.pf/raw/graphql_schema.json` containing schemas, types, fields, and argument metadata with table row IDs for provenance.
- `.pf/raw/graphql_execution.json` capturing resolver bindings, downstream calls, and derived checksums.
- `.pf/readthis/graphql_schema_*.json` / `.pf/readthis/graphql_execution_*.json` chunked via `theauditor.extraction._chunk_large_file` respecting courier limits, ensuring AI assistants can ingest slices offline.
- `graphql` section in `.pf/raw/report_summary.json` summarising counts of secured vs. unsecured resolvers, detected vulnerabilities, and directive coverage.

## Non-Goals & Follow-Ups
- Do not implement mutation performance profiling or caching heuristics in this change; focus on structural truth. Future work can extend `aud graphql analyze` with latency estimations once tracing data exists.
- Insights scoring remains out of scope; GraphQL findings stay in the Truth Courier lane with no interpretive severity adjustments beyond rule metadata.
