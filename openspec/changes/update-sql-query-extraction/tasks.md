## 0. Verification
- [ ] 0.1 Capture current Python behaviour: run `_extract_sql_queries_ast()` against a f-string sample, confirm it returns `[]`, and log output in `verification.md`.
- [ ] 0.2 Capture current JavaScript behaviour: document the guard at `theauditor/indexer/extractors/javascript.py:829-831` that skips template literals and note the missing records in `verification.md`.
- [ ] 0.3 Inspect a golden database to quantify any existing `'UNKNOWN'` commands and record findings in `verification.md`.

## 1. Implementation
- [ ] 1.1 Add a shared SQL parsing helper (e.g., `theauditor/indexer/sql_parsing.py`) that wraps `sqlparse`, normalises query text, extracts command/tables, and raises a clear runtime error when `sqlparse` is unavailable.
- [ ] 1.2 Enhance Python SQL extraction to resolve `ast.JoinedStr`, literal concatenations, and `.format()` chains into static query text before passing them to the helper; retain safeguards against dynamic runtime values.
- [ ] 1.3 Update JavaScript SQL extraction to accept template literals without interpolation, integrate the shared helper, and continue rejecting strings containing `${...}`.
- [ ] 1.4 Add extractor-level unit tests covering f-strings, concatenated literals, and safe template literals alongside a regression that asserts `command != 'UNKNOWN'`.
- [ ] 1.5 Extend database/integration tests to assert the golden snapshot records the new cases and surface a hard failure if `sqlparse` is missing.
- [ ] 1.6 Update OpenSpec documentation (`specs/indexer/spec.md`) plus any relevant user-facing docs to reflect the strengthened SQL guarantees.

## 2. Validation
- [ ] 2.1 Run extractor/unit/integration test suites touched above and record results in `verification.md`.
- [ ] 2.2 Perform SOP-mandated post-implementation audit by re-reading modified files and summarising the findings in `verification.md`.
