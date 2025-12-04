# Tasks: Add Rules Data Fidelity Layer

## 0. Verification (Pre-Implementation)

- [x] 0.1 Verify `theauditor/indexer/schema.py:20` exports `TABLES: dict[str, TableSchema]`
- [x] 0.2 Verify `TableSchema` at `schemas/utils.py:74` has `column_names()` method returning `list[str]`
- [x] 0.3 Verify `TableSchema.foreign_keys` is `list[ForeignKey]` with `local_columns`, `foreign_table`, `foreign_columns`
- [x] 0.4 Verify `theauditor/rules/base.py:83` has `StandardFinding` dataclass
- [x] 0.5 Verify `theauditor/rules/base.py:29` has `StandardRuleContext` dataclass
- [x] 0.6 Verify `theauditor/rules/orchestrator.py:483` has `_execute_rule()` method
- [x] 0.7 Verify orchestrator line 490 is where `rule.function(std_context)` is called

## 1. Q Class Implementation

Location: `theauditor/rules/query.py`

Imports required:
```python
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.utils import TableSchema, ForeignKey
from theauditor.utils.logging import logger
```

- [x] 1.1 Create `Q` class with constructor accepting table name
  ```python
  def __init__(self, table: str):
      if table not in TABLES:
          raise ValueError(f"Unknown table: {table}. Available: {', '.join(sorted(TABLES.keys()))}")
      self._base_table = table
      self._parts = {"select": [], "where": [], "joins": [], "ctes": [], "order": None, "limit": None, "group": []}
      self._params = []
  ```

- [x] 1.2 Implement `.select(*columns)` method
  - Store column list (validation deferred to build)
  - Return `self` for chaining

- [x] 1.3 Implement `.where(condition, *params)` method
  - Store condition string and params
  - Support multiple `.where()` calls (AND together)
  - Return `self` for chaining

- [x] 1.4 Implement `.join(table, on=None, join_type="INNER")` method
  - Store join config
  - `on` formats:
    - `None`: Auto-detect FK from `TABLES[self._base_table].foreign_keys`
    - `list[tuple[str, str]]`: List of (base_col, join_col) pairs
    - `str`: Raw SQL for ON clause (escape hatch, no validation)
  - Return `self` for chaining

- [x] 1.5 Implement `.with_cte(name, subquery: Q)` method
  - Store CTE name and Q object
  - Support multiple CTEs (stored in order)
  - Return `self` for chaining

- [x] 1.6 Implement `.order_by(clause)` method
  - Store order clause as string
  - Return `self` for chaining

- [x] 1.7 Implement `.limit(n)` method
  - Store limit value as int
  - Return `self` for chaining

- [x] 1.8 Implement `.group_by(*columns)` method
  - Store group by columns
  - Return `self` for chaining

- [x] 1.9 Implement `.build()` method - Core Logic
  ```python
  def build(self) -> tuple[str, list]:
      # 1. Validate columns exist in TABLES[self._base_table].column_names()
      # 2. Validate join table columns if on is list[tuple]
      # 3. Build SQL in order: WITH -> SELECT -> FROM -> JOIN -> WHERE -> GROUP BY -> ORDER BY -> LIMIT
      # 4. Collect params: CTE params first, then main query params
      # 5. Return (sql_string, params_list)
      # 6. On any validation error, raise ValueError with full context
  ```

- [x] 1.10 Implement `_find_fk(base_table, join_table)` helper for FK auto-detection
  ```python
  def _find_fk(self, base_table: str, join_table: str) -> ForeignKey | None:
      schema = TABLES.get(base_table)
      if not schema:
          return None
      for fk in schema.foreign_keys:
          if fk.foreign_table == join_table:
              return fk
      # Also check reverse direction
      join_schema = TABLES.get(join_table)
      if join_schema:
          for fk in join_schema.foreign_keys:
              if fk.foreign_table == base_table:
                  return ForeignKey(fk.foreign_columns, base_table, fk.local_columns)
      return None
  ```

- [x] 1.11 Implement `Q.raw(sql, params)` class method
  ```python
  @classmethod
  def raw(cls, sql: str, params: list = None) -> tuple[str, list]:
      logger.warning(f"Q.raw() bypassing validation: {sql[:50]}...")
      return (sql, params or [])
  ```

## 2. Fidelity Infrastructure

Location: `theauditor/rules/fidelity.py`

- [x] 2.1 Create `RuleResult` dataclass
  ```python
  from dataclasses import dataclass
  from theauditor.rules.base import StandardFinding

  @dataclass
  class RuleResult:
      findings: list[StandardFinding]
      manifest: dict
  ```

- [x] 2.2 Create `RuleManifest` helper class
  ```python
  class RuleManifest:
      def __init__(self, rule_name: str):
          self.rule_name = rule_name
          self.items_scanned = 0
          self.tables_queried: set[str] = set()
          self.queries_executed = 0
          self._start_time = time.time()

      def track_query(self, table_name: str, row_count: int):
          self.tables_queried.add(table_name)
          self.queries_executed += 1
          self.items_scanned += row_count

      def to_dict(self) -> dict:
          return {
              "rule_name": self.rule_name,
              "items_scanned": self.items_scanned,
              "tables_queried": sorted(self.tables_queried),
              "queries_executed": self.queries_executed,
              "execution_time_ms": int((time.time() - self._start_time) * 1000),
          }
  ```

- [x] 2.3 Create `RuleDB` helper class
  ```python
  class RuleDB:
      def __init__(self, db_path: str, rule_name: str = "unknown"):
          self.conn = sqlite3.connect(db_path)
          self.cursor = self.conn.cursor()
          self._manifest = RuleManifest(rule_name)

      def query(self, q: Q) -> list[tuple]:
          sql, params = q.build()
          self.cursor.execute(sql, params)
          rows = self.cursor.fetchall()
          self._manifest.track_query(q._base_table, len(rows))
          return rows

      def execute(self, sql: str, params: list = None) -> list[tuple]:
          self.cursor.execute(sql, params or [])
          rows = self.cursor.fetchall()
          self._manifest.queries_executed += 1
          self._manifest.items_scanned += len(rows)
          return rows

      def get_manifest(self) -> dict:
          return self._manifest.to_dict()

      def close(self):
          self.conn.close()

      def __enter__(self):
          return self

      def __exit__(self, exc_type, exc_val, exc_tb):
          self.close()
          return False
  ```

- [x] 2.4 Create `FidelityError` exception class
  ```python
  class FidelityError(Exception):
      def __init__(self, errors: list[str]):
          self.errors = errors
          super().__init__(f"Fidelity check failed: {errors}")
  ```

- [x] 2.5 Create fidelity verification function
  ```python
  import os
  STRICT_FIDELITY = os.environ.get("THEAUDITOR_FIDELITY_STRICT", "0") == "1"

  def verify_fidelity(manifest: dict, expected: dict) -> tuple[bool, list[str]]:
      errors = []

      items_scanned = manifest.get("items_scanned", 0)
      table_row_count = expected.get("table_row_count", 0)

      if items_scanned == 0 and table_row_count > 0:
          errors.append(f"Rule scanned 0 items but table has {table_row_count} rows")

      passed = len(errors) == 0

      if not passed:
          if STRICT_FIDELITY:
              raise FidelityError(errors)
          else:
              logger.warning(f"Fidelity check failed: {errors}")

      return passed, errors
  ```

## 3. Integration with Orchestrator

Location: `theauditor/rules/orchestrator.py`

Hook point: Line 490 inside `_execute_rule()` method

- [x] 3.1 Add imports at top of file
  ```python
  from theauditor.rules.fidelity import RuleResult, verify_fidelity
  ```

- [x] 3.2 Add `_fidelity_failures` list to `__init__`
  ```python
  self._fidelity_failures: list[tuple[str, list[str]]] = []
  ```

- [x] 3.3 Update `_execute_rule()` at line 486-499 to handle `RuleResult`
  ```python
  # BEFORE (line 490):
  findings = rule.function(std_context)

  # AFTER:
  result = rule.function(std_context)

  if isinstance(result, RuleResult):
      findings = result.findings
      manifest = result.manifest
      expected = self._compute_expected(rule, std_context)
      passed, errors = verify_fidelity(manifest, expected)
      if not passed:
          self._fidelity_failures.append((rule.name, errors))
  else:
      findings = result  # Legacy: bare list
  ```

- [x] 3.4 Add `_compute_expected()` method
  ```python
  def _compute_expected(self, rule: RuleInfo, context: StandardRuleContext) -> dict:
      expected = {"table_row_count": 0, "expected_tables": []}

      try:
          rule_module = importlib.import_module(rule.module)
          metadata = getattr(rule_module, "METADATA", None)

          if metadata and hasattr(metadata, "primary_table"):
              table_name = metadata.primary_table
              conn = sqlite3.connect(context.db_path)
              cursor = conn.cursor()
              cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
              expected["table_row_count"] = cursor.fetchone()[0]
              expected["expected_tables"] = [table_name]
              conn.close()
      except Exception:
          pass  # If we can't compute expected, use defaults

      return expected
  ```

- [x] 3.5 Add `get_aggregated_manifests()` method
  ```python
  def get_aggregated_manifests(self) -> dict:
      return {
          "fidelity_failures": self._fidelity_failures,
          "failure_count": len(self._fidelity_failures),
      }
  ```

## 4. Base Module Updates

Location: `theauditor/rules/base.py`

- [x] 4.1 Create `__all__` list at top of file (does not exist currently)
  ```python
  __all__ = [
      "Severity",
      "Confidence",
      "StandardRuleContext",
      "StandardFinding",
      "RuleFunction",
      "RuleMetadata",
      "validate_rule_signature",
      "convert_old_context",
      "RuleResult",  # NEW
  ]
  ```

- [x] 4.2 Add import and re-export of RuleResult
  ```python
  from theauditor.rules.fidelity import RuleResult
  ```

- [x] 4.3 Update `RuleFunction` type hint at line 132
  ```python
  # BEFORE:
  RuleFunction = Callable[[StandardRuleContext], list[StandardFinding]]

  # AFTER:
  RuleFunction = Callable[[StandardRuleContext], list[StandardFinding] | RuleResult]
  ```

## 5. Testing

Location: `tests/rules/test_query.py`, `tests/rules/test_fidelity.py`

- [x] 5.1 Test Q class single table SELECT
  - Basic select with columns
  - Select with where clause and params
  - Select with order_by and limit
  - Validation error for unknown table
  - Validation error for unknown column

- [x] 5.2 Test Q class JOIN
  - Two-table join with explicit on (list of tuples)
  - Two-table join with explicit on (raw string)
  - Two-table join with FK auto-detect (requires test schema with FK)
  - Join validation errors

- [x] 5.3 Test Q class CTE
  - Single CTE
  - Multiple CTEs
  - CTE joined to main query
  - Parameter ordering (CTE params before main params)

- [x] 5.4 Test Q.raw() escape hatch
  - Returns sql and params unchanged
  - Logs warning (mock logger to verify)

- [x] 5.5 Test RuleDB helper
  - Query execution returns list[tuple]
  - Manifest tracks queries_executed
  - Manifest tracks tables_queried
  - Manifest tracks items_scanned (row count)
  - Context manager closes connection

- [x] 5.6 Test fidelity verification
  - Pass case (items_scanned > 0)
  - Fail case (items_scanned = 0, table_row_count > 0)
  - Strict mode raises FidelityError
  - Warn mode logs and returns (False, errors)

## 6. Documentation

- [x] 6.1 Add module docstring to query.py with usage examples
- [x] 6.2 Add module docstring to fidelity.py with usage examples
- [x] 6.3 Add inline comments showing before/after migration patterns

## 7. Validation

- [x] 7.1 Run `openspec validate add-rules-data-fidelity --strict`
- [x] 7.2 Run all tests: `pytest tests/rules/test_query.py tests/rules/test_fidelity.py -v`
- [x] 7.3 Manually test Q class against real `repo_index.db`:
  ```python
  from theauditor.rules.query import Q
  sql, params = Q("symbols").select("name", "line").where("type = ?", "function").limit(5).build()
  print(sql)
  print(params)
  ```
- [x] 7.4 Convert one existing rule as proof of concept (suggest: `ghost_dependencies.py` - simple tier 1)
