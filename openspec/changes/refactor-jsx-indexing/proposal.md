## Why
Recent dual-pass JavaScript/JSX extraction work regressed key behaviours: the first pass overpopulates React/Vue tables with backend symbols, the second pass leaves `_jsx` tables incomplete, and critical metadata (imports, API endpoints, frameworks) is missing from `repo_index.db`. The indexer must be reliable before the upcoming Hacker News relaunch.

## What Changes
- Stabilise the dual-pass AST pipeline so every JS/TS file is parsed in transformed mode, every JSX/TSX file is re-parsed in preserved mode, and results land in the correct standard vs `_jsx` tables.
- Tighten the framework-aware extractors to eliminate the known false positives (React components/hooks, SQL queries) and persist the missing references/endpoints rows.
- Persist inline framework detection results during indexing so downstream rules, taint analysis, and docs always read a fully populated `repo_index.db`.
- Add regression coverage for the dual-pass flow using the `plant` sample project (or a fixture derived from it).

## Impact
- Affected specs: indexer
- Affected code: `theauditor/indexer/**`, `theauditor/ast_parser.py`, `theauditor/indexer/extractors/javascript.py`, `theauditor/indexer/database.py`, framework detection helpers, associated tests/fixtures.
- Downstream: taint analyzer, rules engine, docs generation rely on the populated tables and must continue to work unchanged.
