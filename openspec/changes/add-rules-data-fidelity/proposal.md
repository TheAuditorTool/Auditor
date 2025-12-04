# Proposal: Add Rules Data Fidelity Layer

## Why

The rules system (128 files, ~200 rules) has a fundamental problem: **rules bypass schema abstractions and write raw SQL everywhere**. This creates:

1. **Schema Fragility** - If a column is renamed, 128 files break. No compile-time safety.
2. **No Fidelity Tracking** - If a rule crashes silently or returns 0 findings due to a bug, we think the code is secure. False negatives are invisible.
3. **Inconsistent Patterns** - `build_query()` exists but rules don't use it. `build_join_query()` exists but can't express CTEs (Common Table Expressions) which complex taint rules need.

**Current state verified:**
- `build_query()` at `theauditor/indexer/schema.py:430` - single table SELECT only
- `build_join_query()` at `theauditor/indexer/schema.py:470` - two-table JOIN only
- **Cannot express**: CTEs, subqueries, 3+ table joins, UNION
- Rules like `sql_injection_analyze.py:164-180` use CTEs that current helpers cannot build

## What Changes

### New: Composable Query Builder (Q class)
- Single unified class replacing `build_query()` and `build_join_query()`
- Chainable API: `Q("symbols").select("name").where("type = ?", "function").build()`
- **CTE support**: `Q("table").with_cte("name", subquery).join("name").build()`
- Schema validation at build time - unknown tables/columns raise immediately
- Returns `(sql_string, params)` tuple for parameterized execution

### New: Fidelity Tracking
- `RuleResult` dataclass wrapping findings + manifest
- Manifest tracks: items_scanned, tables_queried, rule_name
- Orchestrator verifies manifest against receipt (fidelity reconciliation)
- Rules that scan 0 items when file has data = fidelity failure

### New: RuleDB Helper
- Thin wrapper for rules to use Q class with connection management
- `helper = RuleDB(context.db_path)` -> `helper.query(Q("symbols")...)`
- Auto-closes connections, tracks queries for manifest

## Impact

- **Affected specs**: None (new capability)
- **Affected code**:
  - NEW: `theauditor/rules/query.py` - Q class implementation
  - NEW: `theauditor/rules/fidelity.py` - RuleResult, manifest generation
  - MODIFIED: `theauditor/rules/base.py` - Add RuleResult type
  - MODIFIED: `theauditor/rules/orchestrator.py` - Fidelity verification
  - FUTURE: 128 rule files migrate to use RuleDB (separate change)

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Q class SQL generation bugs | HIGH | Extensive unit tests, compare output to hand-written SQL |
| Performance regression | MEDIUM | Q.build() is string concat, benchmark vs raw SQL |
| Migration breaks rules | HIGH | Old `build_query()` stays, rules migrate incrementally |
| Fidelity false positives | MEDIUM | Manifest thresholds configurable per rule |

## Success Criteria

1. Q class can express 100% of queries currently in rules (including CTEs)
2. All queries validated against TABLES schema at build time
3. Fidelity manifest generated for every rule execution
4. Zero fallback policy enforced - invalid queries fail immediately
