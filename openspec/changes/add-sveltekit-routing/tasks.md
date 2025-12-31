## 0. Verification
- [x] 0.1 Populate verification.md with hypotheses and evidence (C:\Users\santa\Desktop\TheAuditor\openspec\changes\add-sveltekit-routing\verification.md).
- [x] 0.2 Capture baseline line references for api_endpoints writers and framework detection (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22, C:\Users\santa\Desktop\TheAuditor\theauditor\framework_registry.py:142-193).

## 1. Implementation
- [ ] 1.1 Add `sveltekit_routes` table definition (component_file/load_file columns, defaults, indexes) and register in `NODE_TABLES` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:1048-1061).
- [ ] 1.2 Register `sveltekit_routes` in schema `TABLES` and `FLUSH_ORDER` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py:20-55).
- [ ] 1.3 Add database batch writer for `sveltekit_routes`, storage handler registration, and a `svelte_files` updater for `route_id`/`is_route_component` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\node_database.py:133-243, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py:147-209, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:16-62, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:108-161).
- [ ] 1.4 Add `endpoint_kind` column to api_endpoints, backfill default `http`, and update writers (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py:108-133, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:41-61).
- [ ] 1.5 Update JS extractor APIEndpoint schema to accept endpoint_kind when provided (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\schema.ts:432-441).
- [ ] 1.6 Add SvelteKit framework detection entry and heuristics (C:\Users\santa\Desktop\TheAuditor\theauditor\framework_registry.py:142-193, C:\Users\santa\Desktop\TheAuditor\theauditor\framework_detector.py:10-198).
- [ ] 1.7 Wire SvelteKit route extraction into the indexer pipeline after framework detection (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:90-119, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:303-318).
- [ ] 1.8 Implement SvelteKit route walker for `src/routes` with group/param/rest/optional/matcher rules, full sha256 route_id, and params_json schema.
- [ ] 1.9 Detect `load` and `actions` exports from `+page`/`+layout`/`+page.server` files using JS extractor exports, and set `component_file`/`load_file`/`entry_file` accordingly.
- [ ] 1.10 Insert `+server` handlers and form actions into `api_endpoints` with endpoint_kind; enforce POST for actions and apply action pattern rules.
- [ ] 1.11 Update `svelte_files` route_id/is_route_component for `+page.svelte` and `+layout.svelte`.
- [ ] 1.12 Add `SvelteKitBoundaryStrategy` to generate synthetic dataflow edges for `load` -> `$page.data` -> component consumption and register it in `DFGBuilder`.
- [ ] 1.13 Filter cross-boundary endpoint matching to exclude `endpoint_kind='sveltekit_action'`.
- [ ] 1.14 Add routing fixture tests covering route groups, `[slug]`, `[[id]]`, `[...rest]`, matchers, `+page`, `+layout`, `+page(.server)` load/actions, and `+server` endpoints.
- [ ] 1.15 Add taint continuity tests for loader output -> `$page.data` -> component usage and action endpoints classified as POST.
