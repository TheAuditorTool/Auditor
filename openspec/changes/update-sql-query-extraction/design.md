## Design: SQL Extraction Modernisation

### Goals
1. **Parity Across Languages** – Ensure Python and JavaScript/TypeScript extractors capture the same breadth of SQL literals (plain, concatenated, f-strings/template literals without interpolation).
2. **Single Source of Truth** – Centralise SQL parsing and classification logic so both extractors rely on an identical `sqlparse`-backed helper.
3. **Fail Fast** – Treat a missing `sqlparse` dependency as an actionable error instead of silently skipping extraction.
4. **Stable Metadata** – Keep the `sql_queries` schema unchanged while guaranteeing non-`UNKNOWN` `command` values for supported statements.

### Architecture Overview
```
Extractor (Python/JS) ──╮
                        │  query text
                        ▼
            SQLParsingHelper (new module)
                        │  {command, normalized_sql, tables, placeholders}
                        ▼
        DatabaseManager.add_sql_query (unchanged)
```

#### New Module: `theauditor/indexer/sql_parsing.py`
- Exposes `parse_sql(query_text: str) -> ParsedSQL` where `ParsedSQL` is a TypedDict/dataclass:
  ```python
  {
      "command": str,            # e.g. SELECT, INSERT, MERGE
      "tables": List[str],       # deduped table names
      "normalized": str,         # whitespace-normalised SQL (<= 1000 chars)
  }
  ```
- Imports `sqlparse` once at module import. If unavailable, raises `RuntimeError` with remediation instructions.
- Handles trimming, collapsing whitespace, and deduping tables via token walk that recognises keywords (`FROM`, `JOIN`, `INTO`, `UPDATE`, etc.).
- Adds optional detection for placeholder style (future use) but does not yet modify DB schema.

### Python Extractor Changes
File: `theauditor/indexer/extractors/python.py`

1. **Literal Resolution**
   - Extend `_extract_sql_queries_ast` to accept outputs from `_resolve_sql_literal(node)`:
     - `ast.Constant` / `ast.Str`: return value unchanged.
     - `ast.JoinedStr`: ensure all components are `ast.Constant` or `ast.FormattedValue` where the formatted value is a constant string; join literal parts while replacing formatted values with placeholder tokens (e.g., `%s` or `{param}`) to signal dynamic content. If any dynamic expression is non-static, skip.
     - Concatenations: detect `ast.BinOp` with `Add` where both operands resolve to static strings; recursively combine.
     - `.format()` chains: detect `ast.Call` where `func` is `Attribute` on a literal string with `attr == "format"` and arguments are all constants. Produce a query with named placeholders.
   - Maintain guardrails—if any part is not statically resolvable, bail out (existing behaviour).

2. **Parser Integration**
   - Replace direct `sqlparse.parse` calls with `sql_parsing.parse_sql`.
   - Capture `ParsedSQL.command` / `ParsedSQL.tables`, store unchanged `extraction_source`.
   - Log debug warnings (behind `THEAUDITOR_DEBUG`) when `_resolve_sql_literal` fails, aiding SOP verification.

### JavaScript Extractor Changes
File: `theauditor/indexer/extractors/javascript.py`

1. **Literal Acceptance**
   - Update `_extract_sql_from_function_calls` to pass template literals with **no interpolation** (`${...}`) through:
     - Strip enclosing backticks and unescape `\`` / `\\`.
     - Continue skipping strings containing `${` to avoid dynamic cases.

2. **Shared Parser Use**
   - Import `sql_parsing.parse_sql` and feed sanitized query text.
   - Remove duplicate table parsing logic; rely on helper return values.
   - Preserve extraction source determination logic.

### Dependency Handling
- `pyproject.toml` already pins `sqlparse==0.5.3`; the helper’s runtime check prevents stale environments from proceeding unnoticed.
- Document installation requirement in README / CONTRIBUTING as needed.

### Testing Strategy
1. **Unit Tests (`tests/test_extractors.py`)**
   - Python cases: plain string, f-string, concatenated literals, `.format()`; ensure results include command/table + placeholder handling.
   - JavaScript cases: template literal without interpolation, template literal with interpolation (assert skipped), standard single/double quotes.
2. **Database Integration (`tests/test_database_integration.py`)**
   - Seed fixtures containing the new literal forms; assert rows exist with `command != 'UNKNOWN'`.
   - Add negative test ensuring runtime error when `sqlparse` import fails (use monkeypatch to simulate).
3. **Golden Snapshot Verification**
   - Re-run existing snapshot queries ensuring counts/commands remain classified.

### Rollout Considerations
- Shared helper introduces a hard dependency; ensure pipeline error messaging references `python -m pip install sqlparse` or `poetry install`.
- No schema migrations required; update docs/spec to reflect enforced behaviour.
- Monitor potential increases in `sql_queries` counts (due to formerly skipped queries) and adjust downstream analytics thresholds if needed.
