# Rules System Handoff Memo

**Date:** December 2025
**Context:** After implementing `add-rules-data-fidelity` OpenSpec ticket

---

## TL;DR - What Changed

We added a **fidelity layer** to catch rules that silently fail (scan 0 items but report no findings = invisible false negatives).

**Before:** Rules used raw `sqlite3.connect()` with no tracking
**After:** Rules use `Q` class + `RuleDB` + `RuleResult` with manifest tracking

---

## The New Pattern (MEMORIZE THIS)

```python
from theauditor.rules.base import RuleMetadata, RuleResult, Severity, StandardFinding, StandardRuleContext
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(name="my_rule", category="security", ...)

def analyze(context: StandardRuleContext) -> RuleResult:
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, "my_rule") as db:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function")
            .where("callee_function = ?", "eval")
        )
        findings = [...]  # Process rows
        return RuleResult(findings=findings, manifest=db.get_manifest())
```

---

## Key Files

| File | Purpose |
|------|---------|
| `theauditor/rules/query.py` | Q class - composable query builder with schema validation |
| `theauditor/rules/fidelity.py` | RuleResult, RuleDB, RuleManifest, verify_fidelity |
| `theauditor/rules/orchestrator.py` | Integration - handles RuleResult, calls verify_fidelity |
| `theauditor/rules/base.py` | Exports RuleResult, updated RuleFunction type |
| `theauditor/rules/TEMPLATE_FIDELITY_RULE.py` | **COPY THIS** when writing new rules |

---

## Q Class Cheat Sheet

```python
# Simple SELECT
Q("symbols").select("name", "line").where("type = ?", "function").build()

# Multiple WHERE (ANDed)
Q("symbols").where("type = ?", "function").where("name LIKE ?", "%test%").build()

# JOIN with explicit ON
Q("function_call_args").join("assignments", on=[("file", "file")]).build()

# JOIN with raw ON (escape hatch)
Q("function_call_args").join("assignments", on="a.file = b.file AND a.line < b.line").build()

# CTE for complex taint tracking
tainted = Q("assignments").select("file", "target_var").where("source_expr LIKE ?", "%request%")
Q("function_call_args").with_cte("t", tainted).join("t", on=[("file", "file")]).build()

# Raw SQL escape hatch (logs warning)
Q.raw("SELECT * FROM custom WHERE x REGEXP ?", ["pattern"])
```

---

## What Gets Tracked (Manifest)

When you use `RuleDB.query()`, it automatically tracks:

| Field | Description |
|-------|-------------|
| `rule_name` | Name passed to RuleDB constructor |
| `items_scanned` | Total rows returned across all queries |
| `tables_queried` | Set of base tables accessed |
| `queries_executed` | Count of queries run |
| `execution_time_ms` | Time from RuleDB creation to get_manifest() |

---

## Fidelity Verification

The orchestrator checks: **If `items_scanned == 0` but table has data, something is wrong.**

- **Default (warn mode):** Logs warning, continues
- **Strict mode:** Set `THEAUDITOR_FIDELITY_STRICT=1` to raise `FidelityError`

---

## Migration Status

| Status | Count | Notes |
|--------|-------|-------|
| **Migrated** | 1 | `ghost_dependencies.py` (proof of concept) |
| **Pending** | ~127 | All other rules still use raw sqlite3 |

**Next Step (Phase 2):** Migrate rules tier-by-tier:
- Tier 1: Simple single-table rules
- Tier 2: Two-table JOIN rules
- Tier 3: Multi-table rules
- Tier 4: Taint/CTE rules

---

## Common Gotchas

### 1. Unknown Table Error
```
ValueError: Unknown table: foo. Available: symbols, refs, ...
```
**Fix:** Check `theauditor/indexer/schema.py` for valid table names.

### 2. Unknown Column Error
```
ValueError: Unknown column 'xyz' in table 'symbols'. Valid columns: name, path, ...
```
**Fix:** Check `TABLES["symbols"].column_names()` for valid columns.

### 3. No FK Relationship
```
ValueError: No foreign key from 'symbols' to 'files'. Provide explicit on=
```
**Fix:** Use explicit `on=[("col1", "col2")]` parameter.

### 4. CTE Requires Explicit ON
```
ValueError: CTE 'tainted' requires explicit on= parameter.
```
**Fix:** CTEs don't have FK metadata, must provide `on=` always.

---

## Old Templates (DELETED)

The following were deleted as outdated:
- `TEMPLATE_STANDARD_RULE.py` - Used raw sqlite3
- `TEMPLATE_JSX_RULE.py` - Used raw sqlite3, referenced non-existent tables

**Use `TEMPLATE_FIDELITY_RULE.py` instead.**

---

## Questions to Ask Future Self

1. **Why is my rule not finding anything?**
   - Check manifest: `items_scanned` should be > 0
   - If 0, your WHERE clause might be too restrictive
   - Or table is actually empty for this codebase

2. **Should I use Q class or raw SQL?**
   - **Always start with Q class** - gets schema validation
   - Use `Q.raw()` only for REGEXP or vendor-specific SQL
   - `db.execute()` for edge cases (still tracked)

3. **How do I know what tables/columns exist?**
   ```python
   from theauditor.indexer.schema import TABLES
   print(list(TABLES.keys()))  # All tables
   print(TABLES["symbols"].column_names())  # Columns for 'symbols'
   ```

4. **What about the JSX stuff?**
   - `requires_jsx_pass` in METADATA controls if rule needs JSX data
   - Tables like `symbols_jsx`, `assignments_jsx` exist when JSX pass runs
   - Most rules don't need this - set `requires_jsx_pass=False`

---

## OpenSpec Reference

- Proposal: `openspec/changes/add-rules-data-fidelity/proposal.md`
- Design: `openspec/changes/add-rules-data-fidelity/design.md`
- Spec: `openspec/changes/add-rules-data-fidelity/specs/rules-data-fidelity/spec.md`
- Tasks: `openspec/changes/add-rules-data-fidelity/tasks.md` (all 44 complete)

---

*Last updated: 2025-12-05 by Opus AI*
