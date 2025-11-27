# js-extraction Capability Delta

This delta defines changes to JavaScript/TypeScript extraction capabilities.

---

## ADDED Requirements

### Requirement: Vue In-Memory Compilation

The system SHALL compile Vue Single File Components (SFC) in-memory without writing temporary files to disk.

#### Scenario: Vue SFC compilation without disk I/O

- **WHEN** a `.vue` file is processed during extraction
- **THEN** the compiled script content is passed directly to TypeScript API
- **AND** no temporary files are written to `os.tmpdir()`
- **AND** no cleanup operations are required
- **AND** extraction output is identical to disk-based compilation

#### Scenario: Custom CompilerHost for virtual files

- **WHEN** Vue files are processed in a TypeScript program
- **THEN** a custom CompilerHost intercepts file read operations
- **AND** virtual Vue file content is served from memory
- **AND** non-Vue files are read from disk normally

#### Scenario: Performance improvement target

- **WHEN** 100 Vue files are processed
- **THEN** total extraction time is at least 60% faster than disk-based approach
- **AND** memory usage does not increase by more than 10%

---

### Requirement: TypeScript Module Resolution (Post-Indexing, Database-First)

The system SHALL resolve JavaScript/TypeScript import paths using database queries against indexed files (NO filesystem I/O).

#### Scenario: Post-indexing execution

- **WHEN** all files have been indexed
- **THEN** `resolve_import_paths()` runs as a post-indexing step
- **AND** queries the `files` table for indexed paths
- **AND** performs ZERO filesystem existence checks

#### Scenario: Relative import resolution

- **WHEN** an import path starts with `./` or `../`
- **THEN** the system resolves relative to the importing file's directory
- **AND** tries extensions in order: `.ts`, `.tsx`, `.js`, `.jsx`, `.vue`
- **AND** tries index files: `index.ts`, `index.tsx`, `index.js`, `index.jsx`
- **AND** checks candidates against the indexed `files` table (O(1) set lookup)

#### Scenario: Path mapping resolution

- **WHEN** an import path starts with `@/` or `~/`
- **THEN** the system expands the alias using detected conventions
- **AND** resolves the mapped path against indexed files
- **AND** stores result in `import_styles.resolved_path` column

#### Scenario: Database storage

- **WHEN** an import is successfully resolved
- **THEN** the resolved path is stored in `import_styles.resolved_path`
- **AND** unresolved imports have NULL in this column
- **AND** the schema change is additive (non-breaking)

#### Scenario: node_modules skipped

- **WHEN** an import path is a bare module specifier (e.g., `lodash`)
- **THEN** the system does NOT attempt resolution
- **AND** leaves `resolved_path` as NULL
- **BECAUSE** node_modules packages are not indexed

#### Scenario: Resolution rate improvement

- **WHEN** a typical JavaScript/TypeScript project is analyzed
- **THEN** at least 80% of relative/aliased imports are resolved
- **AND** this represents a 40-50% improvement over basename-only resolution

---

## Technical Notes

### Files Affected

| File | Change Type |
|------|-------------|
| `theauditor/ast_extractors/javascript/batch_templates.js` | Modified (Vue in-memory) |
| `theauditor/indexer/extractors/javascript_resolvers.py` | Modified (module resolution) |

### Database Impact

- **Schema**: `import_styles.resolved_path TEXT` column added to schema definition
- **Data format**: No changes to existing columns
- **Migration**: None required - database is regenerated on each `aud full`

### API Impact

- **CLI**: No changes
- **Output format**: No changes
- **External behavior**: No changes (internal optimization)

### Dependencies

- TypeScript CompilerHost API (existing, for Vue in-memory)
- `@vue/compiler-sfc` (existing, for Vue in-memory)
- `files` table in repo_index.db (existing, for module resolution)
- `import_styles` table in repo_index.db (existing, for module resolution)
