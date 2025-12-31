## ADDED Requirements

### Requirement: Svelte file inclusion
The system SHALL treat `.svelte` files as JS/TS inputs for indexing, including batch parsing and import resolution. The system SHALL extract symbols, calls, and type annotations from `.svelte` files into repo_index.db so call edges appear in graph outputs.

#### Scenario: Svelte file is indexed
- **WHEN** a project contains `src/App.svelte`
- **THEN** the AST parser selects the JS/TS pipeline
- **AND** the file is parsed in the JS batch extractor.

### Requirement: Svelte transform and provenance mapping
The system SHALL transform `.svelte` files to TSX using `svelte2tsx` and SHALL map every extracted symbol, call, assignment, and reference back to the original `.svelte` line and column using v3 sourcemaps. Mapping MUST treat line numbers as 1-based and columns as 0-based; if a column is missing it MUST be treated as 0. If a mapped position is missing or falls outside the original file bounds, extraction MUST fail.

#### Scenario: Template call mapped to original line
- **WHEN** `on:click={handleClick}` appears in a Svelte template
- **THEN** the extracted call edge references the original `.svelte` line and column.

### Requirement: Template call-chain coverage
The system SHALL include call edges and variable usage originating from Svelte template expressions, bindings, and event handlers.

#### Scenario: Inline handler captured
- **WHEN** a template contains `on:submit={() => save(form)}`
- **THEN** the call edge for `save` is recorded with the correct `.svelte` location.

### Requirement: Svelte metadata table
The system SHALL store Svelte metadata in a `svelte_files` table with the following fields and constraints:
- `file_path TEXT PRIMARY KEY`
- `component_name TEXT NULL` (basename of the `.svelte` file)
- `is_route_component BOOLEAN NOT NULL DEFAULT 0`
- `route_id TEXT NULL`
- `svelte_mode TEXT NOT NULL` with allowed values `legacy` or `runes`
- `has_ts BOOLEAN NOT NULL DEFAULT 0`
- `transformer TEXT NOT NULL`
- `source_map_json TEXT NOT NULL`
- `component_props_json TEXT NULL`

#### Scenario: Metadata stored
- **WHEN** a `.svelte` file is transformed successfully
- **THEN** a `svelte_files` row exists with `transformer='svelte2tsx@0.7.46'` and `source_map_json` populated.

### Requirement: Svelte mode and script typing detection
The system SHALL set `svelte_mode` to `runes` when the instance script contains a `$props()` call; otherwise it SHALL set `svelte_mode` to `legacy`. The system SHALL set `has_ts` to true when any `<script>` tag declares `lang="ts"` or `lang="typescript"` (case-insensitive).

#### Scenario: Runes mode detected
- **WHEN** a component includes `const { data } = $props()`
- **THEN** `svelte_mode` is `runes`.

#### Scenario: TypeScript script detected
- **WHEN** a component includes `<script lang="ts">`
- **THEN** `has_ts` is true.

### Requirement: Component props binding metadata
The system SHALL record component prop bindings in `component_props_json` as a JSON array of objects with keys `prop_name`, `binding_name`, `binding_kind`, `line`, and `column`. The system MUST record `export let` bindings and `$props()` destructuring bindings; other `$props()` patterns MAY be omitted.

#### Scenario: export let binding stored
- **WHEN** a component declares `export let data`
- **THEN** `component_props_json` includes a binding with `prop_name` `data` and `binding_kind` `export_let`.

#### Scenario: $props destructuring stored
- **WHEN** a component declares `const { data: pageData } = $props()`
- **THEN** `component_props_json` includes a binding with `prop_name` `data` and `binding_name` `pageData`.

### Requirement: Fidelity enforcement
The system MUST hard-fail Svelte extraction on transform or sourcemap mapping errors and MUST NOT fall back to partial indexing.

#### Scenario: Sourcemap missing
- **WHEN** the transform step does not provide a valid sourcemap
- **THEN** extraction fails for that file and no records are written.

### Requirement: Manifest and receipt coverage
The system SHALL include Svelte extraction outputs in the fidelity manifest and receipt.

#### Scenario: Manifest includes svelte_files
- **WHEN** a `.svelte` file is indexed successfully
- **THEN** the extraction manifest and receipt include `svelte_files`.
