## ADDED Requirements

### Requirement: Persist GraphQL Schemas
The indexer MUST parse GraphQL SDL files and persist canonical schema metadata in `repo_index.db`.

#### Scenario: SDL Extraction During `aud index`
- **GIVEN** a repository containing `.graphql`, `.gql`, or `.graphqls` schema files
- **AND** `aud index` completes successfully
- **WHEN** inspecting `.pf/repo_index.db`
- **THEN** the database contains rows in `graphql_schemas`, `graphql_types`, and `graphql_fields` with correct hashes, kinds (`OBJECT`, `INTERFACE`, `ENUM`, etc.), nullable/list flags, directives, and source locations for every definition present in the SDL
- **AND** each field has corresponding entries in `graphql_field_args` for every declared argument
- **AND** the same metadata is exported to `.pf/raw/graphql_schema.json` with provenance pointing to the inserted row IDs.

### Requirement: Resolver Execution Mapping
The system MUST map GraphQL fields to concrete backend resolver symbols and record execution edges without heuristics.

#### Scenario: Resolver Mapping in Mixed-Language Projects
- **GIVEN** a project that defines GraphQL resolvers in JavaScript/TypeScript (e.g., Apollo Server) and Python (e.g., Graphene)
- **WHEN** `aud index` runs followed by `aud graphql build`
- **THEN** `graphql_resolver_mappings` contains one row per GraphQL field and backend resolver symbol with accurate path, line, language, and binding style metadata
- **AND** `graphql_execution_edges` contains `edge_kind='resolver'` entries linking each `field_id` to the resolver's `symbols` row plus `edge_kind='downstream_call'` entries for the resolver's immediate callees as derived from the call graph
- **AND** `.pf/raw/graphql_execution.json` mirrors these relationships with stable identifiers.

### Requirement: Argument-to-Parameter Alignment
The resolver graph MUST track how GraphQL arguments bind to resolver parameters so taint analysis can seed correct sources.

#### Scenario: Argument Metadata Available for Taint
- **GIVEN** a `Query.user(id: ID!)` field resolved by a backend function whose signature is `resolve_user(parent, info, id)`
- **WHEN** `aud graphql build` finishes
- **THEN** `graphql_field_args` stores the `id` argument with type `ID!` and `graphql_resolver_params` records that the `id` GraphQL argument maps to the resolver parameter at index 2
- **AND** the taint engine can request this mapping via `build_query('graphql_resolver_params', ...)` without inspecting source files
- **AND** the courier export documents the parameter binding so downstream agents can cross-validate the mapping.
