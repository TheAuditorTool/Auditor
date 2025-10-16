# Verification Log

## Hypotheses & Evidence (Pre-Implementation)

### H1: Python extractor drops SQL queries built with f-strings
- **Hypothesis:** `_extract_sql_queries_ast()` only accepts plain string constants, so `cursor.execute(f"...")` calls are ignored.
- **Evidence:** Running the snippet below returned an empty list, confirming the extractor rejects f-strings:
  ```bash
  python3 - <<'PY'
  import ast
  from pathlib import Path
  from theauditor.indexer.extractors.python import PythonExtractor

  code = """
  def get_user(uid):
      cursor.execute(f"SELECT * FROM users WHERE id = {uid}")
  """
  tree = ast.parse(code)
  extractor = PythonExtractor(root_path=Path('.'))
  print(extractor._extract_sql_queries_ast({'tree': tree, 'type': 'python_ast'}, code, 'app.py'))
  PY
  ```
  Output: `[]`
- **Source inspection:** `theauditor/indexer/extractors/python.py:411-421` guards on `ast.Constant` / `ast.Str`, skipping any `ast.JoinedStr` nodes produced by f-strings.

### H2: JavaScript extractor skips template literal SQL queries
- **Hypothesis:** Template literals without interpolation are currently filtered out, so multi-line backtick queries never reach `sqlparse`.
- **Evidence:** Code inspection shows `_extract_sql_from_function_calls()` returns early when `query_text` starts with `` ` `` (see `theauditor/indexer/extractors/javascript.py:823-832`), regardless of whether `${}` is present.
- **Impact sample:** Prisma/Knex snippets typically emit `` db.$queryRaw`SELECT * FROM users` ``; these would be discarded under the current guard.

### H3: Existing datasets no longer suffer from `command = 'UNKNOWN'`
- **Observation:** Querying the bundled golden snapshots showed zero `UNKNOWN` records (e.g., `docs/fakeproj/project_anarchy/.pf/repo_index.db` has 38 rows, all classified). This confirms modern deployments already rely on `sqlparse`, and reinforces the need to keep the column clean once the new extraction paths land.
- **Command used:**
  ```bash
  python3 - <<'PY'
  import sqlite3, pathlib
  path = pathlib.Path('docs/fakeproj/project_anarchy/.pf/repo_index.db')
  conn = sqlite3.connect(path)
  cur = conn.cursor()
  cur.execute("SELECT COUNT(*) FROM sql_queries")
  total = cur.fetchone()[0]
  cur.execute("SELECT COUNT(*) FROM sql_queries WHERE command = 'UNKNOWN'")
  unknown = cur.fetchone()[0]
  print({'total': total, 'unknown': unknown})
  conn.close()
  PY
  ```
  Output: `{'total': 38, 'unknown': 0}`

## Discrepancies
- None observed so far; gaps are confined to string literal forms rather than database schema issues.

## Pending Questions / Follow-ups
- Confirm whether additional statement types (e.g., `PRAGMA`, `MERGE`) currently end up as `UNKNOWN`; plan to cover these in the new tests once the helper abstraction is in place.
