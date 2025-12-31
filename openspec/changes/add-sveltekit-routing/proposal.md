## 0. Verification
- [x] Evidence captured in `C:\Users\santa\Desktop\TheAuditor\openspec\changes\add-sveltekit-routing\verification.md`.
- [x] api_endpoints schema and writers are 8-column and lack endpoint_kind (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py:108-133, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:41-61).
- [x] Graph builder depends on api_endpoints (C:\Users\santa\Desktop\TheAuditor\theauditor\graph\dfg_builder.py:415-421).
- [x] Framework registry and detector have no SvelteKit entry (C:\Users\santa\Desktop\TheAuditor\theauditor\framework_registry.py:142-193, C:\Users\santa\Desktop\TheAuditor\theauditor\framework_detector.py:10-198).

## Why
SvelteKit routes, loaders, actions, and endpoints are not represented in repo_index.db today, which blocks endpoint analysis and taint continuity for SvelteKit projects. This change adds filesystem routing, endpoint classification, and boundary dataflow to keep analysis continuous.

## What Changes
- Add `sveltekit_routes` table for canonical routing facts and advanced routing metadata (route_path, params_json, component_file/load_file) registered alongside node tables in C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:1048-1061 and C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py:20-32).
- **BREAKING** Add `endpoint_kind` column to `api_endpoints` with values `http`, `sveltekit_endpoint`, `sveltekit_action` and update the schema/writers; existing DBs require rebuild or `ALTER TABLE api_endpoints ADD COLUMN endpoint_kind TEXT NOT NULL DEFAULT 'http'` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84).
- Update endpoint writers and normalization to pass endpoint_kind and keep default `http` for existing paths (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py:108-133, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:41-61).
- Add SvelteKit detection and a route walker; compute route_path with groups, params, rest, optional, and matchers, and update `svelte_files` with `route_id`/`is_route_component` for `+page.svelte` and `+layout.svelte` (detection entry in C:\Users\santa\Desktop\TheAuditor\theauditor\framework_registry.py:142-193 and detector flow in C:\Users\santa\Desktop\TheAuditor\theauditor\framework_detector.py:10-198).
- Insert `+server` handlers and form actions into `api_endpoints` with endpoint_kind and HTTP method semantics; standardize action patterns as `route_path` (default) or `route_path + \"?/\" + action_name` (named).
- Add a SvelteKit boundary graph strategy that creates synthetic DFG edges from `load` return nodes to `$page.data` and component prop bindings; exclude `sveltekit_action` from cross-boundary endpoint matching.
- Ensure new extraction writes participate in manifest/receipt reconciliation (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\fidelity_utils.py:71-94, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:108-161, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:798-806).

## Impact
- Affected specs: `sveltekit-routing` (new capability).
- Affected code paths: framework detection, schema/storage for api_endpoints, graph building, and fidelity reconciliation (see citations above).
- Consumers that assume 8-column `api_endpoints` must update for `endpoint_kind`.
- Rust: no changes required.
