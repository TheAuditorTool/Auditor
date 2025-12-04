# Verification: Add Rules Data Fidelity Layer

## Status: COMPLETE

All hypotheses verified against live codebase on 2025-12-05.

---

## 0. Pre-Implementation Verification Checks

### 0.1 TABLES Export
- **Hypothesis**: `theauditor/indexer/schema.py:20` exports `TABLES: dict[str, TableSchema]`
- **Verification**: CONFIRMED
- **Evidence**: Line 20 contains `TABLES: dict[str, TableSchema] = {`
- **File**: `theauditor/indexer/schema.py:20-32`

### 0.2 TableSchema.column_names()
- **Hypothesis**: `TableSchema` at `schemas/utils.py:74` has `column_names()` method returning `list[str]`
- **Verification**: CONFIRMED
- **Evidence**: Lines 85-87 define `def column_names(self) -> list[str]: return [col.name for col in self.columns]`
- **File**: `theauditor/indexer/schemas/utils.py:74-87`

### 0.3 ForeignKey Structure
- **Hypothesis**: `TableSchema.foreign_keys` is `list[ForeignKey]` with `local_columns`, `foreign_table`, `foreign_columns`
- **Verification**: CONFIRMED
- **Evidence**:
  - Line 83: `foreign_keys: list[ForeignKey] = field(default_factory=list)`
  - Lines 36-42: `@dataclass class ForeignKey` with `local_columns: list[str]`, `foreign_table: str`, `foreign_columns: list[str]`
- **File**: `theauditor/indexer/schemas/utils.py:36-71, 83`

### 0.4 StandardFinding Dataclass
- **Hypothesis**: `theauditor/rules/base.py:83` has `StandardFinding` dataclass
- **Verification**: CONFIRMED
- **Evidence**: Line 83-129 contains `@dataclass class StandardFinding` with all expected fields
- **File**: `theauditor/rules/base.py:83-129`

### 0.5 StandardRuleContext Dataclass
- **Hypothesis**: `theauditor/rules/base.py:29` has `StandardRuleContext` dataclass
- **Verification**: CONFIRMED (minor offset)
- **Evidence**: Dataclass decorator at line 28, class definition `class StandardRuleContext:` at line 29
- **File**: `theauditor/rules/base.py:28-80`
- **Note**: Tasks.md says line 29, decorator is at 28. Not a blocker.

### 0.6 _execute_rule Method
- **Hypothesis**: `theauditor/rules/orchestrator.py:483` has `_execute_rule()` method
- **Verification**: CONFIRMED
- **Evidence**: Line 483 contains `def _execute_rule(self, rule: RuleInfo, context: RuleContext) -> list[dict[str, Any]]:`
- **File**: `theauditor/rules/orchestrator.py:483`

### 0.7 Hook Point for RuleResult
- **Hypothesis**: Orchestrator line 490 is where `rule.function(std_context)` is called
- **Verification**: CONFIRMED
- **Evidence**: Line 490 contains `findings = rule.function(std_context)`
- **File**: `theauditor/rules/orchestrator.py:490`

---

## Additional Verification (Design References)

### build_query() Location
- **Hypothesis**: `build_query()` exists at `schema.py:430`
- **Verification**: CONFIRMED
- **Evidence**: Line 430 contains `def build_query(`
- **File**: `theauditor/indexer/schema.py:430-467`

### build_join_query() Location
- **Hypothesis**: `build_join_query()` exists at `schema.py:470`
- **Verification**: CONFIRMED
- **Evidence**: Line 470 contains `def build_join_query(`
- **File**: `theauditor/indexer/schema.py:470-504+`

### CTE Pattern in Rules
- **Hypothesis**: Rules use CTE patterns that current helpers cannot express
- **Verification**: CONFIRMED
- **Evidence**: `sql_injection_analyze.py:164-180` contains raw SQL with `WITH tainted_vars AS (...)`
- **Files with CTEs**:
  - `theauditor/rules/sql/sql_injection_analyze.py`
  - `theauditor/rules/sql/sql_safety_analyze.py`
  - `theauditor/rules/sql/multi_tenant_analyze.py`

### New Files (Do Not Exist)
- **Hypothesis**: `theauditor/rules/query.py` does not exist (will be created)
- **Verification**: CONFIRMED - file not found
- **Hypothesis**: `theauditor/rules/fidelity.py` does not exist (will be created)
- **Verification**: CONFIRMED - file not found

---

## Polyglot Check

| Component | Python | Node.js | Rust |
|-----------|--------|---------|------|
| Q class | NEW | N/A | N/A |
| RuleResult | NEW | N/A | N/A |
| Orchestrator | MODIFIED | N/A | N/A |

**Rationale**: Rules are Python-only. No Node.js or Rust components involved in rule execution.

---

## Discrepancies Summary

| Item | Expected | Actual | Impact |
|------|----------|--------|--------|
| StandardRuleContext line | 29 | 28 (decorator), 29 (class) | None - cosmetic |

**No material discrepancies found. Proposal matches codebase reality.**

---

## Verification Sign-off

- Verified by: Opus AI Lead Coder
- Date: 2025-12-05
- Status: READY FOR IMPLEMENTATION
