# Verification

## Hypotheses
1. `.svelte` is not in the JS/TS extension lists or parser mapping.
2. JS extractor already has Vue SFC preprocessing and manifest logic that can be mirrored for Svelte.
3. Node schema and storage define Vue tables but no Svelte metadata table.
4. JS extractor output schema includes Vue outputs but no Svelte outputs.
5. JS extractor dependencies do not include `svelte2tsx`.

## Evidence
- Extension and parser gaps: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\extractors\javascript.py:18-20`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\extractors\javascript_resolvers.py:466-469`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\extractors\javascript_resolvers.py:533-536`, `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\ast_parser.py:287-305`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\config.py:80-101`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:313-318`.
- Vue SFC preprocessing and virtual path sanitization: `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:164-417`, `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:77-118`.
- Manifest/receipt pipeline in JS extractor and indexer: `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:964-973`, `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\fidelity.ts:46-66`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\extractors\javascript.py:428-446`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py:108-161`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:798-806`.
- Vue-only schema/storage: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:127-147`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:1048-1061`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\node_database.py:133-243`, `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py:147-209`.
- JS extractor schema includes Vue outputs only: `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\schema.ts:623-660`.
- JS extractor dependencies show no `svelte2tsx`: `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\package.json:11-20`.
