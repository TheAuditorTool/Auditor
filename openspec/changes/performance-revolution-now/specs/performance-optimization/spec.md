# Performance Optimization Specification

**Capability**: `performance-optimization`

**Status**: NEW (Created by `performance-revolution-now` change)

---

## ADDED Requirements

### Requirement: Single-Pass AST Traversal

Python AST extraction SHALL traverse each file's AST exactly once, regardless of the number of extractors.

**Rationale**: Eliminates 80x redundancy (80 separate `ast.walk()` calls → 1 unified traversal)

#### Scenario: Python file with multiple frameworks

- **GIVEN** a Python file using SQLAlchemy, Flask, and Pydantic
- **WHEN** the indexer processes the file
- **THEN** the AST SHALL be traversed exactly once
- **AND** all framework data SHALL be extracted (SQLAlchemy models, Flask routes, Pydantic validators)
- **AND** extraction results SHALL match the output of independent extractors (byte-for-byte database equivalence)

#### Scenario: Python file with no frameworks

- **GIVEN** a plain Python file with no framework imports
- **WHEN** the indexer processes the file
- **THEN** the AST SHALL be traversed exactly once
- **AND** only core extraction data SHALL be collected (functions, classes, imports)
- **AND** framework-specific extractions SHALL return empty lists (not null)

#### Scenario: Extraction performance target

- **GIVEN** a project with 1,000 Python files (average 500 AST nodes each)
- **WHEN** the indexer runs on the project
- **THEN** Python extraction SHALL complete in ≤5 seconds
- **AND** total node visits SHALL be ≤500,000 (1 visit per node per file)
- **AND** extraction SHALL be 5-8x faster than baseline (30 seconds)

---

### Requirement: Spatial Indexing for Taint Analysis

Taint analysis data structures SHALL support O(1) lookup for location-based queries.

**Rationale**: Eliminates N+1 linear scans (60 billion operations → 1 million operations)

#### Scenario: Symbol lookup by type

- **GIVEN** a taint analysis query for symbols of type "function"
- **WHEN** the analyzer searches for containing functions
- **THEN** the lookup SHALL use a type-indexed data structure (not linear scan)
- **AND** the lookup SHALL be O(1) average case
- **AND** all symbols of the requested type SHALL be returned

#### Scenario: Location-based assignment lookup

- **GIVEN** a file path and line range (e.g., lines 100-150)
- **WHEN** the analyzer searches for assignments in that range
- **THEN** the lookup SHALL use a spatial index (file → line_block → assignments)
- **AND** only assignments within the specified range SHALL be scanned
- **AND** the lookup SHALL NOT scan the entire assignments table

#### Scenario: CFG block successor lookup

- **GIVEN** a CFG block ID
- **WHEN** the analyzer searches for successor blocks
- **THEN** the lookup SHALL use an adjacency list (not nested loop over edges × blocks)
- **AND** successors SHALL be returned in O(1) time
- **AND** the result SHALL match the output of the original nested loop implementation

#### Scenario: Taint analysis performance target

- **GIVEN** a project with 10,000 LOC and 1,000 taint sources
- **WHEN** taint analysis runs on the project
- **THEN** analysis SHALL complete in ≤40 seconds
- **AND** analysis SHALL be 20-40x faster than baseline (600 seconds)
- **AND** findings SHALL match the output of the original implementation (no regressions)

---

### Requirement: Indexed Database Queries

Database queries SHALL use indexed columns for filtering before applying pattern matching.

**Rationale**: Eliminates full table scans from LIKE wildcards (50 million rows → 500,000 rows)

#### Scenario: Assignment pattern search

- **GIVEN** a taint source pattern (e.g., "req.body")
- **WHEN** the propagation phase searches for matching assignments
- **THEN** the query SHALL pre-filter by file and line range using indexes
- **AND** pattern matching SHALL be applied in Python on the filtered result set
- **AND** the query SHALL NOT use `LIKE '%pattern%'` with leading wildcard

#### Scenario: Function call argument search

- **GIVEN** a search for function calls with specific argument patterns
- **WHEN** the analyzer queries function_call_args
- **THEN** the query SHALL filter by indexed columns (file, callee_function, argument_index) before pattern matching
- **AND** pattern matching SHALL be applied in Python (not SQL LIKE)
- **AND** the query SHALL return identical results to LIKE wildcard query

#### Scenario: Required indexes exist

- **GIVEN** a fresh database created by `aud index`
- **WHEN** the database schema is inspected
- **THEN** the following indexes SHALL exist:
  - `idx_files_ext` on files(ext)
  - `idx_function_call_args_argument_index` on function_call_args(argument_index)
  - `idx_function_call_args_param_name` on function_call_args(param_name) [OPTIONAL]
- **AND** index creation SHALL NOT require manual migration (auto-created on index)

---

### Requirement: Batch Database Operations

Database queries in hot paths SHALL batch load related data upfront instead of querying per-item.

**Rationale**: Eliminates 10,000 database round-trips (1 query per CFG block → 1 batch query)

#### Scenario: CFG block statements batch load

- **GIVEN** a taint analysis run on a function with 100 CFG blocks
- **WHEN** the analyzer processes the function
- **THEN** all CFG block statements SHALL be loaded in a single query
- **AND** per-block processing SHALL use in-memory lookups (not database queries)
- **AND** the total number of CFG-related queries SHALL be ≤3 (blocks, edges, statements)

#### Scenario: Batch load performance

- **GIVEN** a function with 100 CFG blocks and 10 paths
- **WHEN** path analysis executes
- **THEN** statement lookups SHALL NOT trigger 1,000 database queries
- **AND** all lookups SHALL use the pre-loaded batch data
- **AND** performance SHALL be 100-1000x faster than per-block queries

---

### Requirement: In-Memory Compilation for Vue SFC

Vue Single File Component (SFC) compilation SHALL be performed in-memory without disk I/O.

**Rationale**: Eliminates 10-30ms disk I/O overhead per .vue file

#### Scenario: Vue SFC extraction

- **GIVEN** a .vue file with `<script setup>` and `<template>` sections
- **WHEN** the JavaScript extractor processes the file
- **THEN** the SFC SHALL be compiled to JavaScript in-memory
- **AND** the compiled code SHALL be passed directly to TypeScript API (no temp file)
- **AND** no disk I/O SHALL occur (no `fs.writeFileSync`, no `fs.unlinkSync`)

#### Scenario: Vue extraction performance target

- **GIVEN** a project with 100 .vue files
- **WHEN** the indexer processes the project
- **THEN** Vue extraction SHALL complete in ≤3 seconds
- **AND** Vue extraction SHALL be 2-5x faster than baseline with disk I/O (9 seconds)
- **AND** extraction results SHALL match the output of disk-based compilation

#### Scenario: Vue compilation error handling

- **GIVEN** a .vue file with syntax errors in `<script>` section
- **WHEN** compilation fails
- **THEN** the error SHALL be logged with file path and line number
- **AND** extraction SHALL skip the file gracefully (no crash)
- **AND** other .vue files SHALL continue to be processed

---

### Requirement: TypeScript Module Resolution

Import paths SHALL be resolved to actual file paths using TypeScript module resolution algorithm.

**Rationale**: Enables cross-file taint analysis (40-60% more imports resolved)

#### Scenario: Relative import resolution

- **GIVEN** a file `src/utils/validator.ts` that imports `./helper`
- **WHEN** the import is resolved
- **THEN** the resolved path SHALL be `src/utils/helper.ts` (or `.js`, `.tsx` based on file system)
- **AND** the resolution SHALL respect file extensions in precedence order (.ts, .tsx, .js, .jsx)

#### Scenario: tsconfig.json path mapping resolution

- **GIVEN** a tsconfig.json with `paths: { "@/*": ["src/*"] }`
- **AND** a file that imports `@/utils/validation`
- **WHEN** the import is resolved
- **THEN** the resolved path SHALL be `src/utils/validation.ts`
- **AND** the path mapping SHALL be read from tsconfig.json (not hardcoded)

#### Scenario: node_modules resolution

- **GIVEN** a file that imports `lodash`
- **AND** `node_modules/lodash/package.json` exists with `main: "lodash.js"`
- **WHEN** the import is resolved
- **THEN** the resolved path SHALL be `node_modules/lodash/lodash.js`
- **AND** package.json "exports" field SHALL be respected if present

#### Scenario: Import resolution rate target

- **GIVEN** a TypeScript project with 1,000 imports
- **WHEN** the indexer resolves all imports
- **THEN** at least 60% of imports SHALL be resolved to actual file paths
- **AND** unresolved imports SHALL be logged for debugging
- **AND** resolution failures SHALL NOT crash the indexer

---

### Requirement: Performance Regression Prevention

The continuous integration pipeline SHALL enforce performance contracts to prevent future regressions.

**Rationale**: Prevents "death by 1000 cuts" from re-occurring

#### Scenario: Indexing performance regression test

- **GIVEN** a benchmark project (1,000 Python files, 10,000 JS/TS files)
- **WHEN** CI runs the indexing benchmark
- **THEN** indexing time SHALL be ≤20 seconds (allowing 20% margin over target of 15s)
- **AND** the test SHALL fail if indexing time exceeds 20 seconds
- **AND** the failure SHALL block merge

#### Scenario: Taint analysis performance regression test

- **GIVEN** a benchmark project (10,000 LOC, 1,000 taint sources)
- **WHEN** CI runs the taint analysis benchmark
- **THEN** analysis time SHALL be ≤50 seconds (allowing 20% margin over target of 40s)
- **AND** the test SHALL fail if analysis time exceeds 50 seconds
- **AND** the failure SHALL block merge

#### Scenario: Performance metrics collection

- **GIVEN** any `aud` command execution
- **WHEN** the command completes
- **THEN** timing metrics SHALL be logged (indexing time, taint time, etc.)
- **AND** metrics SHALL be available in pipeline.log
- **AND** metrics MAY be collected for performance monitoring (optional)

---

### Requirement: Extraction Correctness Preservation

Performance optimizations SHALL NOT change extraction behavior or output format.

**Rationale**: Zero regression requirement - optimizations are pure implementation changes

#### Scenario: Database schema preservation

- **GIVEN** a project indexed with the optimized indexer
- **WHEN** the database schema is inspected
- **THEN** all table schemas SHALL match the original schema (except new indexes)
- **AND** column names, types, and constraints SHALL be unchanged
- **AND** foreign key relationships SHALL be preserved

#### Scenario: Fixture output equivalence

- **GIVEN** a fixture project with known-good extraction output
- **WHEN** the optimized indexer processes the fixture
- **THEN** the database contents SHALL match the original output byte-for-byte (except timing fields)
- **AND** taint findings SHALL match the original findings exactly
- **AND** pattern detection findings SHALL match the original findings exactly

#### Scenario: Memory usage constraint

- **GIVEN** a project indexed with the optimized indexer
- **WHEN** memory usage is measured
- **THEN** peak memory usage SHALL be within 10% of baseline
- **AND** spatial indexes SHALL add ≤20MB of memory overhead
- **AND** memory leaks SHALL NOT occur (verify with repeated runs)

---

## MODIFIED Requirements

**None** - This is a new capability with no existing requirements to modify.

---

## REMOVED Requirements

**None** - No requirements are being deprecated.

---

## RENAMED Requirements

**None** - No requirements are being renamed.

---

## Cross-References

### Related Capabilities
- **indexing** - Python AST extraction is part of core indexing
- **taint-analysis** - Spatial indexes critical for taint performance
- **javascript-extraction** - Vue compilation and module resolution

### External Dependencies
- TypeScript Compiler API (ts.createSourceFile)
- Python ast module (ast.NodeVisitor)
- SQLite indexes (created automatically on schema application)

### Testing Requirements
- Fixture-based validation (10+ projects covering all frameworks)
- Performance benchmarks (CI regression tests)
- Memory profiling (verify <10% overhead)

---

## Implementation Notes

### Breaking Changes
**None** - All changes are internal implementation optimizations. Public APIs preserved.

### Migration Path
**None required** - Database indexes created automatically on next `aud index` run.

### Rollback Strategy
Git revert (no schema changes, pure code revert)

---

**Last Updated**: 2025-11-02
**Status**: 🔴 **PROPOSAL** - Awaiting approval
