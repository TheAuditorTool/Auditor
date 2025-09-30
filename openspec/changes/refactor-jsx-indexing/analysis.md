# Baseline Findings (tests/fixtures/plant)

## 1.1 Current Index Output
- Command: `python -m theauditor.cli index --root tests/fixtures/plant --manifest tests/fixtures/plant/.pf/manifest.json --db tests/fixtures/plant/.pf/repo_index.db --print-stats`
- Indexed 6 files → 40 symbols, 18 refs, 2 API endpoints, 2 SQL queries
- TypeScript compiler unavailable so semantic pass falls back to Tree-sitter-only parsing
- SQLite schema lacks the expected `_jsx`, `frameworks`, and React-specific tables

## 1.2 Regressions + Gaps
- `symbols` contains anonymous placeholders and backend classes (`AccountController`) that would currently be misclassified as React components once detection runs
- `refs` rows include syntactic fragments (`import|{`, duplicate module rows) because regex importer doesn't normalize `import` specifiers
- `api_endpoints.controls` stores parameter names like `"Request"` instead of real middleware array, meaning preserved middleware metadata is missing
- `sql_queries` rows correctly capture lines but lose SQL command metadata (`tables` is always `[]`)
- No `_jsx` tables exist, so JSX-preserved data cannot land anywhere on second pass
- Framework detection is not persisted to SQLite (`frameworks`/`framework_safe_sinks` tables absent) nor does the indexer emit the legacy JSON artefact

## Updated Index Output
- Dual pass emits `symbols` (transformed) and `symbols_jsx` (preserved) rows for `Dashboard.tsx`
- `function_returns_jsx` now contains synthetic JSX metadata with `has_jsx=1` for component functions
- `react_components`/`react_hooks` tables capture `Dashboard` and its `useState`/`useEffect` hooks while skipping `AccountController`
- `frameworks` table persists Express/React detections alongside default safe sinks and generates `.pf/raw/frameworks.json`
- `refs` deduplicated to true modules (`react`, `express`, etc.); `api_endpoints` middleware lists collapse to `[]`
- SQL queries annotated with tables `PLANTS` and `PLANT_SNAPSHOTS`
