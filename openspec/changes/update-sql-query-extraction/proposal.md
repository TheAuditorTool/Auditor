## Why
- Python SQL extraction currently ignores any call where the first argument is not an `ast.Constant`/`ast.Str`. In practice this drops every f-string or concatenated literal, as confirmed by running `_extract_sql_queries_ast()` against a `cursor.execute(f"...")` sample which returned `[]` while the AST node at `theauditor/indexer/extractors/python.py:411-421` short-circuited. Those misses leave taint analysis blind to high-risk dynamic queries.
- JavaScript SQL extraction discards template literals altogether. `_extract_sql_from_function_calls()` bails out whenever a string starts with `` ` `` (see `theauditor/indexer/extractors/javascript.py:823-832`), so the indexer never records the multi-line queries emitted by popular drivers like Prisma, Knex, or PlanetScale.
- Internal runbooks still attribute widespread `sql_queries.command = 'UNKNOWN'` values to regex-based `SQL_QUERY_PATTERNS`. Modern code already calls `sqlparse`, but every extractor reimplements command detection and silently drops work when the dependency is missing. We need a single, enforced parsing path that guarantees classification parity across Python and JavaScript.

## What Changes
- Introduce a shared SQL parsing helper in the indexer that requires `sqlparse`, normalises whitespace, and surfaces command type plus table references for both Python and JavaScript extractors. If `sqlparse` is unavailable we will emit a structured error so the pipeline cannot quietly skip SQL analysis.
- Extend Python SQL extraction to recognise `ast.JoinedStr`, literal concatenations, and `.format()` chains by evaluating static segments, collapsing literal parts, and tracking placeholders used for parameter binding.
- Teach the JavaScript extractor to accept template literals without interpolation (backticks but no `${...}`), unescape them, and feed the resulting query text through the shared parser while keeping existing guards against dynamic expressions.
- Persist the parsed command and normalized table list back into `sql_queries`, ensuring the `command` column never falls back to `'UNKNOWN'` for the supported statement types.
- Add focused regression tests that (a) exercise f-strings, template literals, and chained literals, and (b) assert the `sql_queries` table records high-confidence results for each language.
- Update the indexer spec to document the new SQL extraction guarantees so future regressions are caught at the verification stage.

## Impact
- Restores visibility into SQL hotspots embedded in modern Python and Node codebases, reducing false negatives for SQL injection and query auditing.
- Aligns extraction semantics across languages, enabling downstream tooling (taint engine, findings consolidation, metadata dashboards) to trust command labels and table mappings.
- Provides early-signal failure when `sqlparse` is missing instead of silently skipping critical analysis.

## Verification Alignment
- Pre-change evidence (recorded in `verification.md`) shows `_extract_sql_queries_ast()` ignoring f-strings and `_extract_sql_from_function_calls()` skipping template literals, leaving real queries out of `sql_queries`.
- Post-change plan covers unit-level extractor tests, database integration checks on the golden snapshot, and a sanity query ensuring no `'UNKNOWN'` commands remain for the exercised fixtures.
