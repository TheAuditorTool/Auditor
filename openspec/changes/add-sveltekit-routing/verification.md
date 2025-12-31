# Verification

## Hypotheses
1. `api_endpoints` lacks `endpoint_kind` and uses 8-column inserts.
2. Endpoint writes are centralized in the FrameworksDatabaseMixin/CoreStorage/normalization paths.
3. Graph builder reads `api_endpoints` for cross-boundary edges.
4. Framework detection relies on the registry which has no SvelteKit entry.
5. Storage handlers do not include `sveltekit_routes`, and schema has no SvelteKit tables.

## Evidence
- api_endpoints schema: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\frameworks_schema.py:65-84`.
- Insert paths: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\frameworks_database.py:7-22`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py:108-133`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\normalization.py:41-61`.
- Graph builder: `C:\Users\santa\Desktop\TheAuditor\theauditor\graph\dfg_builder.py:415-421`.
- Framework detection: `C:\Users\santa\Desktop\TheAuditor\theauditor\framework_registry.py:142-193`, `C:\Users\santa\Desktop\TheAuditor\theauditor\framework_detector.py:10-198`.
- Storage handlers list: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:16-62`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py:20-26`.
- Node tables registry: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:1048-1061`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py:20-32`.
