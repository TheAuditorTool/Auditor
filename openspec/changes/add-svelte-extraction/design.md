## 0. Verification
- [x] Baseline evidence is captured in `C:\Users\santa\Desktop\TheAuditor\openspec\changes\add-svelte-extraction\verification.md`.
- [x] Vue SFC preprocessing, virtual path sanitization, and manifest attach are confirmed patterns (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:77-118, C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:164-417, C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:964-973, C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\fidelity.ts:46-66).

## Context
The JS extractor already implements a virtual file preprocessing model for Vue SFCs (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:164-417) and sanitizes virtual paths before writing the extraction receipt (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:77-118, C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:964-973). The AST parser hard-fails JS/TS parsing errors (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\ast_parser.py:275-283), so Svelte extraction must be equally strict.

## Goals / Non-Goals
- Goals:
  - Parse `.svelte` files through the JS/TS extractor with full call graph coverage from template expressions.
  - Preserve line/column provenance by mapping all extracted facts back to the original `.svelte` file via sourcemaps.
  - Persist Svelte metadata, sourcemaps, and prop bindings in `svelte_files` for downstream consumers.
  - Keep fidelity reconciliation (manifest + receipt) intact for new Svelte outputs.
- Non-Goals:
  - Implement SvelteKit route modeling (covered by a separate change).
  - Provide partial or best-effort Svelte parsing when transforms fail.

## Decisions
- Decision: Use `svelte2tsx@0.7.46` to transform `.svelte` to TSX with sourcemaps.
  - Why: This exposes template expressions to the TypeScript compiler, enabling full call-chain provenance.
  - Dependencies: `svelte@5.46.1` (compiler parse), `@jridgewell/trace-mapping@0.3.31` (sourcemap lookup). `svelte2tsx` peer deps require `typescript` ^4.9.4 or ^5 and `svelte` ^3.55 or ^4 or ^5.
  - Implementation: Add dependencies to `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\package.json:11-20` and implement a `prepareSvelteFile` pipeline analogous to `prepareVueSfcFile` (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:168-240).
- Decision: Use `@jridgewell/trace-mapping` for position mapping from virtual TSX to original `.svelte`.
  - Mapping rules: line is 1-based, column is 0-based (match JS extractor conventions). If column is missing, treat it as 0 for mapping.
  - Enforcement: if `originalPositionFor` returns no line/column, or the mapped position exceeds the original file bounds, fail extraction and write no rows.
  - Output: write mapped file path, line, and column back into every extracted record that references the virtual Svelte file.
- Decision: Create a `svelte_files` table with explicit schema, defaults, and indexes.
  - Table schema (SQLite):
    - `file_path TEXT NOT NULL PRIMARY KEY`
    - `component_name TEXT NULL` (basename of the `.svelte` file)
    - `is_route_component BOOLEAN NOT NULL DEFAULT 0`
    - `route_id TEXT NULL` (nullable; set by SvelteKit routing)
    - `svelte_mode TEXT NOT NULL` (allowed values: `legacy`, `runes`)
    - `has_ts BOOLEAN NOT NULL DEFAULT 0`
    - `transformer TEXT NOT NULL` (store `svelte2tsx@0.7.46`)
    - `source_map_json TEXT NOT NULL` (raw v3 sourcemap JSON)
    - `component_props_json TEXT NULL` (JSON array of prop bindings)
  - Indexes: `idx_svelte_files_route_id` (`route_id`), `idx_svelte_files_component_name` (`component_name`), `idx_svelte_files_is_route` (`is_route_component`).
  - Foreign keys: `file_path` -> `files.path`. `route_id` intentionally has no FK to avoid cross-change coupling.
  - Registration: add to `NODE_TABLES` and `TABLES` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\node_schema.py:1048-1061, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py:20-32).
- Decision: Enforce hard-fail behavior for Svelte transform or mapping errors.
  - Why: Zero-fallback policy and fidelity guarantees.
  - Implementation: missing/invalid sourcemap or out-of-range mappings abort extraction for the file; no partial writes.
- Decision: Detect `svelte_mode` and `has_ts` from the Svelte source (not the transformed TSX).
  - `svelte_mode` is `runes` if the instance script contains a CallExpression with callee identifier `$props`; otherwise `legacy`.
  - `has_ts` is true if any `<script>` tag declares `lang="ts"` or `lang="typescript"` (case-insensitive), using `svelte/compiler` parse output.
- Decision: Extract component prop bindings into `component_props_json` for dataflow bridging.
  - Supported legacy pattern: `export let <name>` creates `{ "prop_name": "<name>", "binding_name": "<name>", "binding_kind": "export_let", "line": <line>, "column": <column> }`.
  - Supported runes pattern: `const { data, data: alias } = $props()` creates `{ "prop_name": "data", "binding_name": "<data or alias>", "binding_kind": "props_destructure", "line": <line>, "column": <column> }`.
  - Unsupported pattern (no entry, log as skipped): `$props()` assigned to an identifier without destructuring.
  - `component_props_json` is NULL when no bindings are recorded; otherwise store the JSON array.
- Decision: Use a Svelte-specific virtual path map and sanitize results before writing, patterned after `sanitizeVirtualPaths` (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:77-118).

## Risks / Trade-offs
- Source map drift: mitigated by persisting `source_map_json` in `svelte_files` and failing on invalid mappings.
- Svelte 5 runes differences: mitigated by explicit `svelte_mode` classification and tests.
- Performance overhead: transform step adds cost; mitigate by batch processing in the existing JS batch pipeline.
- Props binding coverage: unsupported `$props()` patterns are skipped; mitigate with explicit logging and fixtures for recognized patterns.

## Migration Plan
1. Add `svelte_files` table to schema and register in `TABLES`/`FLUSH_ORDER` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py:20-55).
2. Add database and storage handlers for `svelte_files` (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\database\node_database.py:133-243, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py:147-209).
3. Extend JS extractor schema and preprocessing to emit `svelte_files` (including `component_props_json`) and mapped facts (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\schema.ts:623-660, C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:164-417).
4. Add dependencies (`svelte2tsx`, `svelte`, `@jridgewell/trace-mapping`) and implement `prepareSvelteFile`, `svelte_mode`/`has_ts` detection, and props binding extraction in the JS extractor (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\package.json:11-20, C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:164-417).
5. Implement strict sourcemap mapping with `@jridgewell/trace-mapping` and sanitize virtual paths (C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\src\main.ts:77-118).
6. Add `.svelte` support in parser and extension lists (C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\extractors\javascript.py:18-20, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\extractors\javascript_resolvers.py:466-469, C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\ast_parser.py:287-305, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\config.py:80-101, C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py:313-318).
7. Add tests for sourcemap fidelity, template call edges, props binding extraction, and manifest/receipt coverage.

## Open Questions
- None.
