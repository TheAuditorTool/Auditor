# Design: Rules Data Fidelity Layer

## Context

TheAuditor rules system has 128 Python files containing ~200 security rules. These rules query the SQLite index database (`repo_index.db`) to find vulnerabilities.

**Current Pain Points:**
1. Rules write raw `cursor.execute("SELECT ...")` - no schema validation
2. `build_query()` exists but only handles single-table SELECT
3. `build_join_query()` exists but cannot express CTEs (needed by taint rules)
4. No tracking of what rules actually scanned - silent failures invisible

**Stakeholders:**
- Rule authors (need ergonomic API)
- Orchestrator (needs fidelity verification)
- Schema maintainers (need to refactor without breaking 128 files)

---

## Schema Reference (CRITICAL - Embed for Actionability)

### TABLES Dict Structure

Location: `theauditor/indexer/schema.py:20-32`

```python
from theauditor.indexer.schema import TABLES

# TABLES is dict[str, TableSchema] composed from sub-modules:
TABLES: dict[str, TableSchema] = {
    **CORE_TABLES,           # symbols, refs, files, assignments, function_call_args
    **SECURITY_TABLES,       # sql_queries, taint_flows, vulnerabilities
    **FRAMEWORKS_TABLES,     # react_hooks, sequelize_models, express_routes
    **PYTHON_TABLES,         # python_orm_models, python_validators
    **NODE_TABLES,           # node_dependencies, package_configs
    **RUST_TABLES,           # rust_structs, rust_unsafe_blocks
    **GO_TABLES,             # go_structs, go_interfaces
    **BASH_TABLES,           # bash_commands, shell_scripts
    **INFRASTRUCTURE_TABLES, # docker_configs, k8s_resources
    **PLANNING_TABLES,       # plans, plan_tasks
    **GRAPHQL_TABLES,        # graphql_types, graphql_resolvers
}
```

**Key tables for rules:**
- `symbols` - functions, classes, variables (name, path, line, type)
- `function_call_args` - function calls (file, line, callee_function, argument_expr)
- `assignments` - variable assignments (file, line, target_var, source_expr, in_function)
- `sql_queries` - detected SQL strings (file_path, line_number, query_text, has_interpolation)

### TableSchema Structure

Location: `theauditor/indexer/schemas/utils.py:74-87`

```python
@dataclass
class TableSchema:
    """Represents a complete table schema."""
    name: str
    columns: list[Column]
    indexes: list[tuple[str, list[str]]] = field(default_factory=list)
    primary_key: list[str] | None = None
    unique_constraints: list[list[str]] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    def column_names(self) -> list[str]:
        """Get list of column names in definition order."""
        return [col.name for col in self.columns]
```

### ForeignKey Structure

Location: `theauditor/indexer/schemas/utils.py:36-71`

```python
@dataclass
class ForeignKey:
    """Foreign key relationship metadata for JOIN query generation."""
    local_columns: list[str]      # Columns in this table
    foreign_table: str            # Referenced table name
    foreign_columns: list[str]    # Columns in referenced table
```

**Usage for Q class FK auto-detection:**
```python
# Q looks up FK like this:
schema = TABLES["function_call_args"]
for fk in schema.foreign_keys:
    if fk.foreign_table == "symbols":
        # Found: can auto-generate JOIN condition
        # fk.local_columns = ["file", "callee_function"]
        # fk.foreign_columns = ["path", "name"]
```

---

## Representative Query Patterns (CRITICAL - What Q Must Support)

### Pattern 1: Simple Single Table (build_query equivalent)

Current in `sql_injection_analyze.py:92-98`:
```python
query = build_query(
    "function_call_args",
    ["file", "line", "callee_function", "argument_expr"],
    where="callee_function LIKE '%execute%' OR callee_function LIKE '%query%'",
    order_by="file, line",
)
```

**Q equivalent:**
```python
Q("function_call_args") \
    .select("file", "line", "callee_function", "argument_expr") \
    .where("callee_function LIKE ? OR callee_function LIKE ?", "%execute%", "%query%") \
    .order_by("file, line") \
    .build()
```

### Pattern 2: Two-Table JOIN (build_join_query equivalent)

Common pattern for correlating calls with assignments:
```python
# Find function calls where argument is a tainted variable
Q("function_call_args") \
    .select("file", "line", "callee_function", "argument_expr") \
    .join("assignments", on=[("file", "file"), ("argument_expr", "target_var")]) \
    .where("source_expr LIKE ?", "%request%") \
    .build()
```

### Pattern 3: CTE Query (NEW - Cannot Express Today)

This is the pattern rules NEED but `build_join_query()` cannot express:

```python
# Step 1: Find tainted variables (user input sources)
tainted = Q("assignments") \
    .select("file", "target_var", "line") \
    .where("source_expr LIKE ? OR source_expr LIKE ?", "%request.%", "%req.%")

# Step 2: Find where tainted vars flow to SQL functions
Q("function_call_args") \
    .with_cte("tainted_vars", tainted) \
    .select("f.file", "f.line", "f.callee_function", "t.target_var") \
    .join("tainted_vars", on=[("file", "file")]) \
    .where("f.callee_function LIKE ? AND f.argument_expr LIKE '%' || t.target_var || '%'", "%execute%") \
    .build()

# Produces:
# WITH tainted_vars AS (
#     SELECT file, target_var, line FROM assignments
#     WHERE source_expr LIKE ? OR source_expr LIKE ?
# )
# SELECT f.file, f.line, f.callee_function, t.target_var
# FROM function_call_args f
# INNER JOIN tainted_vars t ON f.file = t.file
# WHERE f.callee_function LIKE ? AND f.argument_expr LIKE '%' || t.target_var || '%'
```

---

## Goals / Non-Goals

**Goals:**
- Single composable query builder that handles SELECT, JOIN, CTE, subquery
- Schema validation at query build time (not execution time)
- Fidelity manifest tracking for every rule execution
- Zero fallback - invalid queries fail immediately with clear errors
- Incremental migration path - old helpers stay, rules migrate gradually

**Non-Goals:**
- ORM/ActiveRecord pattern (we want SQL visibility, not hiding)
- Query optimization/caching (premature - measure first)
- Automatic query generation from rule intent (too magical)
- Node.js/Rust implementation (Python-only, rules are Python)

---

## Decisions

### Decision 1: Single Q Class vs Multiple Helpers

**Choice:** Single composable `Q` class

**Rationale:**
- `build_query()` + `build_join_query()` + `build_cte_query()` = 3 things to learn
- Composable builder = one concept, arbitrary complexity
- CTEs are just named Q objects, subqueries are Q objects

**Alternatives Rejected:**
- Keep adding `build_*` functions: Gets unwieldy, can't compose
- SQLAlchemy Core: Heavy dependency, learning curve, overkill

### Decision 2: Validation Timing

**Choice:** Validate at `.build()` time, not construction time

**Rationale:**
- `Q("table")` doesn't know columns yet - can't validate
- `.select("col")` could validate, but error location unclear
- `.build()` has full context - can give precise error with full query

**Implementation:**
```python
Q("symbols").select("name", "INVALID_COL").where("type = ?", "function").build()
# Raises: ValueError: Unknown column 'INVALID_COL' in table 'symbols'.
#         Valid columns: name, path, line, type, ...
#         Full query: SELECT name, INVALID_COL FROM symbols WHERE type = ?
```

### Decision 3: CTE Representation

**Choice:** CTEs are Q objects passed to `.with_cte(name, query)`

**Rationale:**
- Natural composition: subquery is just another Q
- Can validate CTE columns when referenced in main query
- Matches mental model of "name this subquery, then use it"

### Decision 4: Fidelity Manifest Structure

**Choice:** Manifest is dict with standardized keys, attached to RuleResult

**Structure:**
```python
@dataclass
class RuleResult:
    findings: list[StandardFinding]
    manifest: dict  # Fidelity tracking

# Manifest schema:
{
    "rule_name": "sql_injection_analyze",
    "items_scanned": 1547,
    "tables_queried": ["function_call_args", "assignments", "sql_queries"],
    "queries_executed": 5,
    "execution_time_ms": 42,
    "file_filter": None,  # or specific file path
}
```

**Rationale:**
- Dict is flexible for per-rule custom tracking
- Standardized keys allow orchestrator verification
- Can compute "expected scans" from table row counts

### Decision 5: Parameter Handling

**Choice:** Parameters collected during chain, returned with SQL

**Rationale:**
- Parameterized queries prevent SQL injection
- Caller needs params for `cursor.execute(sql, params)`
- Order matters - params collected in query order

**API:**
```python
sql, params = Q("symbols").select("name").where("type = ?", "function").build()
# sql = "SELECT name FROM symbols WHERE type = ?"
# params = ["function"]

cursor.execute(sql, params)
```

### Decision 6: File Location

**Choice:** `theauditor/rules/query.py` for Q class, `theauditor/rules/fidelity.py` for RuleResult

**Rationale:**
- Rules import from rules package - keeps imports clean
- Not in `indexer/` because this is rules-specific (fidelity, helpers)
- `schema.py` stays in indexer - Q imports TABLES from there

### Decision 7: Q.raw() Escape Hatch

**Choice:** Allow `Q.raw(sql, params)` with logged warning

**Rationale:**
- Edge cases exist that Q cannot express (complex regex, vendor-specific SQL)
- Logging ensures visibility - can audit raw SQL usage
- Better than rules falling back to completely untracked queries

**Implementation:**
```python
@classmethod
def raw(cls, sql: str, params: list = None) -> tuple[str, list]:
    """Escape hatch for raw SQL. Logs warning for tracking."""
    logger.warning(f"Q.raw() bypassing validation: {sql[:50]}...")
    return (sql, params or [])
```

### Decision 8: Fidelity Failure Behavior

**Choice:** Default warn, configurable strict mode via `THEAUDITOR_FIDELITY_STRICT=1`

**Rationale:**
- Warn-only allows gradual rollout without breaking existing rules
- Strict mode for CI pipelines that want hard failures
- Environment variable keeps it out of code

**Implementation:**
```python
import os
STRICT_FIDELITY = os.environ.get("THEAUDITOR_FIDELITY_STRICT", "0") == "1"

def verify_fidelity(manifest: dict, expected: dict) -> tuple[bool, list[str]]:
    errors = []
    if manifest.get("items_scanned", 0) == 0 and expected.get("table_row_count", 0) > 0:
        errors.append(f"Rule scanned 0 items but table has {expected['table_row_count']} rows")

    passed = len(errors) == 0
    if not passed:
        if STRICT_FIDELITY:
            raise FidelityError(errors)
        else:
            logger.warning(f"Fidelity check failed: {errors}")
    return passed, errors
```

### Decision 9: Join Auto-Detection

**Choice:** Yes, use ForeignKey metadata; explicit `on=` always works as override

**Rationale:**
- Ergonomic for common cases (most joins follow FK relationships)
- Explicit `on=` provides escape hatch for complex joins
- Matches existing `build_join_query()` behavior

**Implementation:**
```python
def join(self, table: str, on=None, join_type="INNER"):
    if on is None:
        # Auto-detect from ForeignKey metadata
        fk = self._find_fk(self._base_table, table)
        if fk is None:
            raise ValueError(f"No FK from {self._base_table} to {table}. Provide explicit on=")
        on = list(zip(fk.local_columns, fk.foreign_columns))
    # ... store join config
```

---

## Orchestrator Integration Point

Location: `theauditor/rules/orchestrator.py:483-499`

**Current code:**
```python
def _execute_rule(self, rule: RuleInfo, context: RuleContext) -> list[dict[str, Any]]:
    """Execute a single rule with appropriate parameters."""

    if rule.is_standardized and STANDARD_CONTRACTS_AVAILABLE:
        try:
            std_context = convert_old_context(context, self.project_path)
            findings = rule.function(std_context)  # <-- HOOK POINT: line 490

            if findings and hasattr(findings[0], "to_dict"):
                return [f.to_dict() for f in findings]
            return findings if findings else []
        except Exception as e:
            # ...
```

**Modified code (after this change):**
```python
def _execute_rule(self, rule: RuleInfo, context: RuleContext) -> list[dict[str, Any]]:
    if rule.is_standardized and STANDARD_CONTRACTS_AVAILABLE:
        try:
            std_context = convert_old_context(context, self.project_path)
            result = rule.function(std_context)

            # NEW: Handle RuleResult or legacy list
            if isinstance(result, RuleResult):
                findings = result.findings
                manifest = result.manifest

                # Fidelity verification
                expected = self._compute_expected(rule, std_context)
                passed, errors = verify_fidelity(manifest, expected)
                if not passed:
                    self._fidelity_failures.append((rule.name, errors))
            else:
                # Legacy: bare list return
                findings = result
                manifest = {}

            if findings and hasattr(findings[0], "to_dict"):
                return [f.to_dict() for f in findings]
            return findings if findings else []
```

---

## Fidelity Expected Values Computation

**Source:** Orchestrator computes expected values from table row counts and rule metadata.

```python
def _compute_expected(self, rule: RuleInfo, context: StandardRuleContext) -> dict:
    """Compute expected fidelity values for a rule."""
    expected = {"table_row_count": 0, "expected_tables": []}

    # Get table row count for primary table (from rule metadata or inferred)
    rule_module = importlib.import_module(rule.module)
    metadata = getattr(rule_module, "METADATA", None)

    if metadata and hasattr(metadata, "primary_table"):
        table_name = metadata.primary_table
        cursor = self._get_cursor(context.db_path)
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        expected["table_row_count"] = cursor.fetchone()[0]
        expected["expected_tables"] = [table_name]

    return expected
```

**Note:** If a rule doesn't specify `primary_table` in METADATA, fidelity verification only checks that `items_scanned > 0`.

---

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Q class doesn't cover edge case SQL | Rules fall back to raw SQL | Document escape hatch: `Q.raw(sql, params)` |
| Fidelity thresholds too strict | False positive failures | Configurable per-rule thresholds |
| Migration takes forever | 128 files, parallel AI work | Tier rules by complexity, batch migrate |
| Performance overhead | Query building adds latency | Benchmark: expect <1ms per build() |

---

## Migration Plan

**Phase 1: Foundation (this change)**
- Implement Q class with full test coverage
- Implement RuleResult and fidelity manifest
- Update orchestrator to handle RuleResult
- Keep `build_query()` / `build_join_query()` working (not deprecated yet)

**Phase 2: Migration (separate change)**
- Migrate rules tier-by-tier (Tier 1: simple, Tier 4: taint)
- Each tier is a batch of files processed in parallel
- Validation script confirms each migrated rule

**Phase 3: Cleanup (separate change)**
- Deprecate `build_query()` / `build_join_query()`
- Remove raw SQL from rules
- Enforce Q class usage via linting
