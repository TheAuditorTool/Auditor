## MODIFIED Requirements
### Requirement: SQL Query Extraction Handles Modern Literals
The indexer MUST recognise statically-defined SQL queries regardless of whether they are expressed as plain strings, f-strings, concatenated literals, or template literals without interpolation, and persist them to `sql_queries`.

#### Scenario: Python f-string database call
- **GIVEN** a Python source file that executes `cursor.execute(f"SELECT * FROM users WHERE id = {uid}")`
- **AND** the extractor runs with AST support enabled
- **WHEN** the indexer processes that file
- **THEN** the resulting `sql_queries` row MUST exist for that line
- **AND** the stored `command` MUST be `SELECT`
- **AND** the `tables` field MUST include `users`

#### Scenario: JavaScript template literal query
- **GIVEN** a JavaScript/TypeScript file that calls `db.$queryRaw\`UPDATE orders SET status = 'shipped'\``
- **AND** the template literal contains no `${...}` interpolation
- **WHEN** the indexer processes that file
- **THEN** the query MUST be stored in `sql_queries` with `command = UPDATE`
- **AND** the row MUST record the table name `orders`

### Requirement: SQL Command Classification Consistency
SQL extraction MUST route through a single parser that depends on `sqlparse`, yielding consistent `command` values and failing fast when the dependency is unavailable.

#### Scenario: Supported statement type
- **GIVEN** a project containing `connection.execute("MERGE INTO target USING source ...")`
- **WHEN** the indexer parses the query text
- **THEN** the shared parser MUST classify the statement with a concrete `command` (e.g., `MERGE`)
- **AND** the recorded `sql_queries.command` MUST NOT be `'UNKNOWN'`

#### Scenario: Missing sqlparse dependency
- **GIVEN** `sqlparse` is not importable in the runtime environment
- **WHEN** the indexer initialises SQL extraction
- **THEN** it MUST raise an actionable error that blocks indexing and explains how to install `sqlparse`
- **AND** it MUST NOT silently skip SQL extraction.
