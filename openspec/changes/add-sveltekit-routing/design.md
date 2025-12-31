## 0. Verification
- [x] Baseline evidence is captured in `C:\Users\santa\Desktop\TheAuditor\openspec\changes\add-sveltekit-routing\verification.md`.
- [x] api_endpoints schema and write paths are 8-column only (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py:108-133, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:41-61).
- [x] Cross-boundary graph uses api_endpoints (C:\Users\santa\Desktop\TheAuditor\theauditor\graph\dfg_builder.py:415-421).
- [x] Framework detection relies on the registry and lacks SvelteKit (C:\Users\santa\Desktop\TheAuditor\theauditor\framework_registry.py:142-193, C:\Users\santa\Desktop\TheAuditor\theauditor\framework_detector.py:10-198).
- [x] Storage handlers list no SvelteKit route table (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:16-62, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py:20-26).

## Context
The normalization layer promotes language-specific routes into `api_endpoints` for graph building (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:17-67), and the graph builder reads `api_endpoints` for cross-boundary edges (C:\Users\santa\Desktop\TheAuditor\theauditor\graph\dfg_builder.py:415-421). Any SvelteKit routing model must integrate with these canonical tables without breaking fidelity reconciliation (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:108-161, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:798-806).

## Goals / Non-Goals
- Goals:
  - Detect SvelteKit projects and compute canonical route paths from `src/routes`.
  - Store routes in `sveltekit_routes` and keep pages/layouts out of `api_endpoints`.
  - Classify API endpoints with `endpoint_kind` and include SvelteKit actions and `+server` handlers.
  - Create explicit dataflow edges across loader to `$page.data` to component consumption.
  - Populate `svelte_files.route_id` and `svelte_files.is_route_component` for `+page.svelte` and `+layout.svelte`.
- Non-Goals:
  - Implement Svelte file parsing (covered by svelte-extraction change).
  - Add partial indexing when route parsing fails.

## Decisions
- Decision: Add `endpoint_kind` column to `api_endpoints` with default `http`.
  - Allowed values: `http`, `sveltekit_endpoint`, `sveltekit_action`.
  - Schema: update `API_ENDPOINTS` to add `endpoint_kind TEXT NOT NULL DEFAULT 'http'` and index `idx_api_endpoints_kind` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84).
  - Migration: existing DBs must run `ALTER TABLE api_endpoints ADD COLUMN endpoint_kind TEXT NOT NULL DEFAULT 'http'` or be rebuilt.
  - Update schema and all insertion paths (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py:108-133, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:41-61).
  - Cross-boundary graph: filter `api_endpoints` to `endpoint_kind IN ('http', 'sveltekit_endpoint')` to avoid matching actions (C:\Users\santa\Desktop\TheAuditor\theauditor\graph\dfg_builder.py:395-421).
- Decision: Create `sveltekit_routes` table with explicit schema.
  - Columns:
    - `route_id TEXT PRIMARY KEY`
    - `route_path TEXT NOT NULL`
    - `route_kind TEXT NOT NULL` (values: `page`, `layout`, `endpoint`)
    - `fs_path TEXT NOT NULL` (route directory under `src/routes`, relative to project root)
    - `entry_file TEXT NOT NULL` (for page/layout: `component_file` if present else `load_file`; for endpoints: `+server` file)
    - `component_file TEXT NULL` (`+page.svelte` or `+layout.svelte`)
    - `load_file TEXT NULL` (`+page.(js|ts)`, `+page.server.(js|ts)`, `+layout.(js|ts)`, or `+layout.server.(js|ts)` that exports `load`)
    - `params_json TEXT NULL`
    - `has_group_segments BOOLEAN NOT NULL DEFAULT 0`
    - `has_rest_params BOOLEAN NOT NULL DEFAULT 0`
    - `has_optional_params BOOLEAN NOT NULL DEFAULT 0`
  - Indexes: `idx_sveltekit_routes_path` (`route_path`), `idx_sveltekit_routes_kind` (`route_kind`), `idx_sveltekit_routes_entry_file` (`entry_file`), `idx_sveltekit_routes_fs_path` (`fs_path`).
  - Foreign keys: `entry_file`, `component_file`, and `load_file` reference `files.path` (preferred if supported).
  - Registration: add to `NODE_TABLES` and `TABLES` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:1048-1061, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py:20-32).
- Decision: `route_id` algorithm is `sha256(route_path + "|" + route_kind)` with lowercase hex output. Store all 64 hex characters; no truncation.
- Decision: `params_json` schema is a JSON array of objects:
  - Keys: `name` (string), `kind` (`param`, `rest`, `optional`), `matcher` (string or null), `segment_index` (0-based index of non-group path segments), `raw` (original segment text).
  - Example: `[{"name":"id","kind":"optional","matcher":"uuid","segment_index":0,"raw":"[[id=uuid]]"}]`.
- Decision: Route path computation rules:
  - Segment groups `(group)` do not affect URL path and set `has_group_segments=1`.
  - `[param]` becomes `:param`.
  - `[...rest]` becomes `:rest*` and sets `has_rest_params=1`.
  - `[[param]]` becomes `:param?` and sets `has_optional_params=1`.
  - `[param=matcher]` becomes `:param` and records `matcher` in `params_json`.
  - Root route `src/routes/+page.svelte` results in route_path `/`.
- Decision: Detection heuristics for SvelteKit projects: any 2 of the following must be present:
  - `src/routes/` directory
  - `svelte.config.*` file
  - `@sveltejs/kit` dependency in `package.json`
- Decision: Extraction rules:
  - `+page.svelte` and `+layout.svelte` create or update `sveltekit_routes` rows with `route_kind` `page` or `layout` and set `component_file`.
  - `+page.(js|ts)`, `+page.server.(js|ts)`, `+layout.(js|ts)`, and `+layout.server.(js|ts)` with an exported `load` set `load_file` (and create the route row if missing).
  - `entry_file` resolves to `component_file` if present; otherwise `load_file`.
  - `+server.(js|ts)` creates a `sveltekit_routes` row with `route_kind='endpoint'` and `entry_file` set to the `+server` file.
  - `+page.server.(js|ts)` with exported `actions` creates `api_endpoints` rows with `endpoint_kind='sveltekit_action'`, `method='POST'`, `handler_function` `actions.<name>` (default uses `actions.default`), and `pattern` set to `route_path` (default) or `route_path + "?/" + action_name` (named).
  - `+server.(js|ts)` exported HTTP handlers create `api_endpoints` rows with `endpoint_kind='sveltekit_endpoint'`, `method` set to the export name (GET/POST/PUT/PATCH/DELETE), and `pattern`/`path`/`full_path` set to `route_path`. Do not synthesize HEAD or OPTIONS.
  - Update `svelte_files` for `+page.svelte` and `+layout.svelte`: set `is_route_component=1` and `route_id` to the computed value.
- Decision: Dataflow bridging uses a dedicated graph strategy.
  - Implement `SvelteKitBoundaryStrategy` in `C:\Users\santa\Desktop\TheAuditor\theauditor\graph\strategies\` and register it in `DFGBuilder.strategies` (C:\Users\santa\Desktop\TheAuditor\theauditor\graph\dfg_builder.py:14-45).
  - For each route with `load_file` and `component_file`, resolve `load_return_id` as `{load_file}::load::return` (matches `build_return_flow_graph` IDs) and create a synthetic `$page.data` node with ID `{component_file}::global::$page.data`.
  - For each binding in `svelte_files.component_props_json` with `prop_name` `data`, create a target node `{component_file}::global::<binding_name>`.
  - Create bidirectional edges with `edge_type` `sveltekit_load_to_page_data` (load_return -> $page.data) and `sveltekit_page_data_to_prop` ($page.data -> binding), `line=0`, and metadata including `route_id`, `route_path`, and `route_kind`.
  - Synthetic nodes/edges are returned in the unified graph output and are not persisted to the database.
- Decision: Fidelity reconciliation for new tables:
  - Use `FidelityToken.attach_manifest` on extractor output (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\fidelity_utils.py:71-94) and ensure `DataStorer` handlers return receipts for `sveltekit_routes` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:108-161).

## Risks / Trade-offs
- Route parsing errors: mitigation is strict parsing with fatal errors for invalid segments.
- Endpoint_kind migration: existing consumers may assume 8 columns; mitigation is to update all insert paths and keep default `http`.
- Dataflow modeling complexity: mitigate with explicit synthetic nodes and targeted tests.

## Migration Plan
1. Schema updates: add `sveltekit_routes` (with component/load file columns and indexes) and `endpoint_kind` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:1048-1061, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py:20-55).
2. Database and storage handlers: add `add_sveltekit_route` in node_database, storage handler in node_storage, and a `svelte_files` updater for `route_id`/`is_route_component` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\node_database.py:133-243, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py:147-209, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:16-62).
3. Update endpoint writers and normalization for `endpoint_kind` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py:108-133, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:41-61).
4. Update JS extractor API endpoint schema to include endpoint_kind when provided (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\schema.ts:432-441).
5. Wire SvelteKit route extraction into the indexer pipeline after framework detection (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:90-119, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:303-318).
6. Add SvelteKit detection and route walker (with load/actions detection based on JS extractor exports).
7. Add `SvelteKitBoundaryStrategy`, register it, and filter cross-boundary endpoints by `endpoint_kind` (C:\Users\santa\Desktop\TheAuditor\theauditor\graph\dfg_builder.py:395-421).
8. Add tests for routing, endpoint_kind migration/defaults, and dataflow continuity.

## Open Questions
- None.
