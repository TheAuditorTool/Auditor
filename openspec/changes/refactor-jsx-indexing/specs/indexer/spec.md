## ADDED Requirements
### Requirement: Dual-Pass JavaScript Extraction
The indexer SHALL parse every JavaScript or TypeScript source file once with the TypeScript compiler in `jsx_mode="transformed"`, and SHALL re-parse every file containing JSX syntax (`.jsx`, `.tsx`) with `jsx_mode="preserved"`. The two passes SHALL write their results into separate caches so that transformed-mode data lands in the standard tables while preserved-mode data lands in the `_jsx` tables.

#### Scenario: JSX project produces dual caches
- **GIVEN** a project that contains both `.ts` and `.tsx` files
- **WHEN** the operator runs `aud index`
- **THEN** the command finishes without compiler errors
- **AND** the resulting `.pf/repo_index.db` contains symbol rows for the `.ts` files in `symbols`
- **AND** the same `.tsx` file appears twice: once in `symbols` (transformed data) and once in `symbols_jsx` (preserved data with `jsx_mode='preserved'` and `extraction_pass=2`)

### Requirement: Standard Tables Receive Transformed-Mode Data
The indexer SHALL populate the `files`, `symbols`, `assignments`, `function_call_args`, `function_returns`, `cfg_blocks`, `cfg_edges`, `variable_usage`, `orm_queries`, and `sql_queries` tables using the transformed-mode AST from the first pass so that downstream taint, graph, and rules analysis can rely on complete data flow information.

#### Scenario: Transformed pass populates taint inputs
- **GIVEN** a `.ts` file where `userInput` flows into `handleClick(userInput)`
- **WHEN** `aud index` is executed
- **THEN** `repo_index.db` records the file in `files`
- **AND** `assignments` contains the assignment of `userInput`
- **AND** `function_call_args` includes a row linking `handleClick` with an argument expression referencing `userInput`

### Requirement: Preserved-Mode Tables Store JSX Structure
The indexer SHALL persist preserved-mode extraction results in parallel `_jsx` tables (`symbols_jsx`, `assignments_jsx`, `function_call_args_jsx`, `function_returns_jsx`) with `jsx_mode` metadata so that JSX-aware analysis can read the untouched component structure.

#### Scenario: Preserved pass captures JSX return
- **GIVEN** a `.tsx` component that returns `<Button title={label} />`
- **WHEN** `aud index` runs
- **THEN** `function_returns_jsx` contains a row for that component whose `has_jsx` flag is true and `jsx_mode='preserved'`

### Requirement: Framework Detection Runs Inline and Persists
The indexer SHALL run framework detection before processing files, SHALL persist detected frameworks and safe sinks inside the same indexing transaction (both in `frameworks` and `framework_safe_sinks` tables), and SHALL continue emitting the legacy `raw/frameworks.json` artifact for backward compatibility.

#### Scenario: Express app is indexed once
- **GIVEN** a project with `express` in `package.json`
- **WHEN** `aud index` runs
- **THEN** `frameworks` in `repo_index.db` contains an Express row marked as `is_primary`
- **AND** `framework_safe_sinks` contains the default Express sink patterns
- **AND** `.pf/raw/frameworks.json` is updated with the same detection results

### Requirement: JavaScript Extractor Stores Accurate References
The JavaScript extractor SHALL insert import references into the `refs` table, capture HTTP route definitions in `api_endpoints`, and avoid classifying non-React back-end classes or non-hook method calls as React-specific artefacts by requiring JSX evidence and React imports for components/hooks.

#### Scenario: Backend controller avoided, frontend stored
- **GIVEN** a project containing `AccountController` (no JSX, no React import) and `Dashboard.tsx` (React component with hooks)
- **WHEN** `aud index` executes
- **THEN** `react_components` does not contain `AccountController`
- **AND** `react_components` and `react_hooks` include the entries from `Dashboard.tsx`
- **AND** `refs` contains import rows for both files while `api_endpoints` records any Express routes discovered

### Requirement: Indexer Refactor Upholds DRY and KISS Principles
The dual-pass indexer implementation SHALL consolidate shared behaviours into reusable helpers and SHALL avoid unnecessary abstractions so that the code remains easy to reason about while preventing duplicated logic across transformed and preserved passes.

#### Scenario: Shared batching logic reused without duplication
- **GIVEN** both transformed and preserved parsing passes need to batch files through the TypeScript compiler
- **WHEN** the implementation prepares those batches
- **THEN** the batching helper is defined once and reused by each pass
- **AND** no copy-pasted loops or redundant wrapper classes are introduced for the second pass
