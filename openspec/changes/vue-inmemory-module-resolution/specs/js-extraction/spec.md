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

### Requirement: TypeScript Module Resolution

The system SHALL resolve JavaScript/TypeScript import paths using the TypeScript module resolution algorithm.

#### Scenario: Relative import resolution

- **WHEN** an import path starts with `./` or `../`
- **THEN** the system resolves relative to the importing file's directory
- **AND** tries extensions in order: `.ts`, `.tsx`, `.js`, `.jsx`, `.d.ts`
- **AND** tries index files: `index.ts`, `index.tsx`, `index.js`, `index.jsx`
- **AND** returns the resolved file path relative to project root

#### Scenario: Path mapping resolution

- **WHEN** an import path matches a pattern in `tsconfig.json` paths field
- **THEN** the system applies the path mapping transformation
- **AND** resolves the mapped path to an actual file
- **AND** supports wildcard patterns like `@/*` mapping to `src/*`

#### Scenario: node_modules resolution

- **WHEN** an import path is a bare module specifier (not relative)
- **THEN** the system walks up the directory tree checking `node_modules/`
- **AND** handles scoped packages (e.g., `@vue/reactivity`)
- **AND** reads `package.json` to find entry point (`exports`, `module`, `main`)

#### Scenario: Resolution caching

- **WHEN** the same import path is resolved multiple times
- **THEN** the resolution result is cached
- **AND** subsequent lookups return cached result without disk I/O

#### Scenario: Fallback for unresolvable imports

- **WHEN** an import path cannot be resolved by the algorithm
- **THEN** the system falls back to basename extraction
- **AND** logs a debug message for troubleshooting
- **AND** does not throw an error or stop extraction

#### Scenario: Resolution rate improvement

- **WHEN** a typical JavaScript/TypeScript project is analyzed
- **THEN** at least 80% of imports are resolved to actual file paths
- **AND** this represents a 40-50% improvement over basename-only resolution

---

## Technical Notes

### Files Affected

| File | Change Type |
|------|-------------|
| `theauditor/ast_extractors/javascript/batch_templates.js` | Modified (Vue in-memory) |
| `theauditor/indexer/extractors/javascript.py` | Modified (module resolution) |

### Database Impact

- **Schema**: No changes
- **Data format**: No changes
- **Migration**: Not required

### API Impact

- **CLI**: No changes
- **Output format**: No changes
- **External behavior**: No changes (internal optimization)

### Dependencies

- TypeScript CompilerHost API (existing)
- `@vue/compiler-sfc` (existing)
- `tsconfig.json` parsing (new, read-only)
- `package.json` parsing (new, read-only)
