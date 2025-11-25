# Design: Python Extractor Consolidation & Data Fidelity Control

## Context

### Background

The Python extraction pipeline has 5 layers:
1. **Extractors** (`theauditor/ast_extractors/python/*.py`) - 28 files, ~150 `extract_*` functions
2. **Orchestrator** (`theauditor/ast_extractors/python_impl.py`) - Maps outputs to result keys
3. **Storage** (`theauditor/indexer/storage/python_storage.py`) - 27 handlers
4. **Database Mixin** (`theauditor/indexer/database/python_database.py`) - 28 `add_python_*` methods
5. **Schema** (`theauditor/indexer/schemas/python_schema.py`) - 28 `TableSchema` definitions

The previous ticket (`wire-extractors-to-consolidated-schema`) reduced tables from 149 to 28 but introduced a critical bug: **schema columns were invented without verifying actual extractor output**.

### Constraints

1. **ZERO FALLBACK POLICY** - No try/except fallbacks, no table existence checks
2. **Database-first architecture** - All analysis uses SQL queries, not file I/O
3. **Schema contract system** - Tables guaranteed to exist, rules must crash if missing
4. **3-Layer file path responsibility** - Indexer provides path, extractors return data without path

### Stakeholders

- **Taint analyzer** - Needs to JOIN on method names, field names
- **Pattern rules** - Query columns by name
- **FCE** - Correlates findings across tables
- **Graph builder** - Does not use Python extraction tables
- **aud explain** - Queries symbols and relationships

---

## Goals / Non-Goals

### Goals

1. **Eliminate silent data loss** - Fidelity control catches mismatches
2. **Align schema to reality** - Every column matches extractor output
3. **Enable SQL JOINs** - No JSON blobs, proper junction tables
4. **Preserve extractor subtype** - Two-discriminator pattern
5. **Reduce sparsity** - Max 50% NULL per table

### Non-Goals

1. **Changing extractor logic** - Extractors are source of truth (for now)
2. **Node.js extraction changes** - Separate schema, separate ticket
3. **Performance optimization** - Focus is correctness, not speed
4. **New extractor features** - Wire existing outputs, don't add new ones

---

## Decisions

### Decision 1: Two-Discriminator Pattern

**What:** Use two columns per consolidated table: `*_kind` (table discriminator) + `*_type` (extractor subtype)

**Why:**
- Current code overwrites extractor's `loop_type` with 'for_loop'
- Lose valuable information: 'enumerate', 'zip', 'range', 'items'
- Two columns preserve both table grouping AND pattern detail

**How:**
```python
# In python_impl.py
for loop in extract_for_loops(context):
    loop['loop_kind'] = 'for'       # NEW: Table discriminator
    # loop['loop_type'] preserved   # Extractor's value: 'enumerate', 'zip', etc.
    result['python_loops'].append(loop)
```

**Alternatives Considered:**
- **Single discriminator (current)** - Rejected: loses subtype info
- **Concatenated value** (`for:enumerate`) - Rejected: harder to query, breaks existing code

### Decision 2: Junction Tables for JSON Blobs

**What:** Replace JSON array/object columns with normalized junction tables

**Why:**
- JSON columns block SQL JOINs
- Cannot index JSON content efficiently
- Cannot use in WHERE clauses without JSON functions
- Taint analyzer needs to JOIN on method names

**How:**
```sql
-- BEFORE (JSON blob in python_protocols)
implemented_methods TEXT  -- '["__iter__", "__next__"]'

-- AFTER (junction table)
CREATE TABLE python_protocol_methods (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    protocol_id INTEGER NOT NULL,
    method_name TEXT NOT NULL,
    FOREIGN KEY (protocol_id) REFERENCES python_protocols(id)
);

-- Query: Find protocols implementing __iter__
SELECT p.* FROM python_protocols p
JOIN python_protocol_methods pm ON p.id = pm.protocol_id
WHERE pm.method_name = '__iter__';
```

**Alternatives Considered:**
- **Keep JSON with JSON functions** - Rejected: SQLite JSON functions are slow, not indexed
- **Expand to fixed columns** - Used where cardinality is bounded (e.g., type_param_1..5)

### Decision 3: Data Fidelity Control Architecture

**What:** Three-component system: Extraction Manifest + Storage Receipt + Reconciliation Check

**Why:**
- 22MB data loss went undetected
- No mechanism to catch extraction vs storage mismatch
- Silent failures violate ZERO FALLBACK POLICY

**How:**
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Extractor  │ ──▶ │ Orchestrator│ ──▶ │   Storage   │ ──▶ │  Database   │
│  (N rows)   │     │  manifest   │     │   receipt   │     │  (N rows)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │                   ▼                   ▼                   │
       │            ┌─────────────────────────────┐                │
       │            │   RECONCILIATION CHECK      │                │
       │            │   extracted > 0 && stored == 0 → CRASH      │
       │            │   extracted != stored → WARNING              │
       │            └─────────────────────────────┘                │
       └──────────────────────────────────────────────────────────┘
```

**Implementation Location:**
- `theauditor/indexer/fidelity.py` (NEW) - `reconcile_fidelity()` function
- Called from `theauditor/indexer/orchestrator.py` after Python storage

**Alternatives Considered:**
- **Database triggers** - Rejected: SQLite triggers are per-statement, not batch-aware
- **Post-hoc row count** - Rejected: doesn't catch which table has mismatch
- **Sampling verification** - Rejected: partial verification misses edge cases

### Decision 4: Expression Table Decomposition (Option C)

**What:** Split `python_expressions` junk drawer into logical tables + re-route misplaced extractors

**Why:**
- Current: 22 extractors, ~55 columns, 90% NULL sparsity
- Query returns 55 columns when you only need 5
- No clear data contract per row

**How:**

**NEW Tables:**
| Table | Extractors | Columns | Sparsity |
|-------|------------|---------|----------|
| `python_comprehensions` | 1 (comprehensions) | ~12 | <10% |
| `python_control_statements` | 4 (break/continue/pass, assert, del, with) | ~12 | <20% |

**Re-Routes:**
| Extractor | From | To | Discriminator |
|-----------|------|-----|---------------|
| `extract_copy_protocol` | expressions | python_protocols | `protocol_kind='copy'` |
| `extract_class_decorators` | expressions | python_class_features | `feature_kind='class_decorator'` |
| `extract_recursion_patterns` | expressions | python_functions_advanced | `function_kind='recursive'` |
| `extract_memoization_patterns` | expressions | python_functions_advanced | `function_kind='memoized'` |
| `extract_loop_complexity` | expressions | python_loops | (add complexity columns) |

**Remaining python_expressions:** ~10 extractors, ~25 columns, ~50% sparsity

**Alternatives Considered:**
- **Option A: Union all columns** - Rejected: 60+ columns, 90% NULL, lazy solution
- **Option B: Keep as-is** - Rejected: doesn't fix the architectural problem

### Decision 5: Schema Contract CI Test

**What:** Add `tests/test_schema_contract.py` to prevent future drift

**Why:**
- Current bug happened because no test verified schema matches extractor output
- Future changes could reintroduce the same bug

**How:**
```python
def test_extractor_keys_match_schema_columns():
    """Every extractor output key must exist as a schema column."""
    truth = run_audit()  # From scripts/audit_extractors.py

    for extractor, data in truth.items():
        table = EXTRACTOR_TO_TABLE.get(extractor)
        schema_columns = get_schema_columns(table)
        extractor_keys = set(data.get('keys', []))

        missing_in_schema = extractor_keys - schema_columns - IGNORED_KEYS
        assert not missing_in_schema, f"{extractor} outputs {missing_in_schema} but schema lacks these"
```

---

## Risks / Trade-offs

### Risk 1: Breaking Downstream Consumers

**Risk:** Renaming columns breaks queries in taint, rules, FCE

**Likelihood:** Medium

**Mitigation:**
- Phase-gated implementation with verification after each phase
- Run full test suite after each schema change
- Document all column renames in migration notes

### Risk 2: Performance Regression from Junction Tables

**Risk:** JOINs on junction tables slower than JSON column access

**Likelihood:** Low

**Mitigation:**
- Index all junction table foreign keys
- Index commonly queried columns (`method_name`, `field_name`)
- Junction tables only for unbounded arrays, not all JSON

### Risk 3: Scope Creep

**Risk:** Fixing one table leads to "while we're here" changes

**Likelihood:** High

**Mitigation:**
- Strict phase gates (complete one phase before next)
- Explicit scope: only Python extraction, no Node.js
- Each phase must pass fidelity check before proceeding

### Risk 4: Incomplete Extractor Coverage

**Risk:** Some extractors produce data for frameworks not in sample code

**Likelihood:** Medium

**Mitigation:**
- Wire ALL extractors, even those with [NO DATA] in truth file
- Framework-specific extractors (Flask, Django, Celery) get proper tables
- Fidelity check will catch missing handlers

---

## Migration Plan

### Phase 0: Fidelity Control Infrastructure (Pre-requisite)

**Goal:** Detect any data loss during subsequent phases

**Steps:**
1. Create `theauditor/indexer/fidelity.py` with `reconcile_fidelity()`
2. Add `DataFidelityError` exception
3. Generate extraction manifest in `python_impl.py`
4. Generate storage receipt in `python_storage.py`
5. Call reconciliation in orchestrator

**Verification:** Fidelity check correctly FAILS on current code (proves it works)

### Phase 1: Expression Table Decomposition

**Goal:** Fix the junk drawer before aligning columns

**Steps:**
1. Create `python_comprehensions` table
2. Create `python_control_statements` table
3. Update orchestrator mappings
4. Add storage handlers
5. Add DB mixin methods
6. Re-route 5 misplaced extractors

**Verification:** Fidelity check passes, python_expressions row count reduced

### Phase 2: Control Flow Tables (5 Tables)

**Tables:** python_loops, python_branches, python_functions_advanced, python_io_operations, python_state_mutations

**Steps per table:**
1. Diff schema vs extractor truth
2. Remove invented columns
3. Add missing columns
4. Add `*_kind` discriminator column
5. Update storage handler
6. Update DB mixin method

**Verification:** Fidelity check passes, zero NULL in required columns

### Phase 3: OOP/Types Tables (5 Tables)

**Tables:** python_class_features, python_protocols, python_descriptors, python_type_definitions, python_literals

**Steps:** Same as Phase 2, plus junction table creation

### Phase 4: Security/Testing Tables (5 Tables)

**Tables:** python_security_findings, python_test_cases, python_test_fixtures, python_framework_config, python_validation_schemas

### Phase 5: Low-Level Tables (5 Tables)

**Tables:** python_operators, python_collections, python_stdlib_usage, python_imports_advanced, python_expressions (reduced)

### Phase 6: Wire Missing Extractors

**Extractors to wire:**
- `extract_python_exports` -> python_imports_advanced
- `extract_flask_blueprints` -> python_framework_config
- `extract_celery_tasks` -> python_framework_config
- `extract_graphene_resolvers` -> python_framework_config

### Phase 7: Codegen & Final Verification

1. Regenerate generated_types.py
2. Regenerate generated_accessors.py
3. Update schema assertion (129 -> 136)
4. Run full test suite
5. Verify all consumers work

### Rollback Plan

**Full Rollback:**
```bash
git revert <commit_hash>
aud full --offline  # Re-index with old schema
```

**Partial Rollback:** Each phase is a separate commit, can revert individual phases.

---

## Open Questions

### Q1: Should we consolidate extractors too?

**Context:** Extractors were designed for 149-table schema. Now they map 150:30.

**Current Answer:** Out of scope for this ticket. Focus on schema alignment first.

**Future Ticket:** Consider merging related `extract_*` functions into consolidated extractors.

### Q2: What happens to existing data after re-index?

**Answer:** Database is deleted and rebuilt on `aud full`. No migration needed for existing projects.

### Q3: Should fidelity check be opt-out?

**Answer:** No. ZERO FALLBACK POLICY. If data loss occurs, pipeline must CRASH.

---

## Technical Specifications

### Junction Table Schema

```sql
-- Pattern: All junction tables follow this structure
CREATE TABLE python_{parent}_{items} (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,                    -- Denormalized for query performance
    {parent}_id INTEGER NOT NULL,          -- FK to parent table
    {item}_name TEXT NOT NULL,             -- The value from JSON array
    {item}_order INTEGER DEFAULT 0,        -- Preserve order if needed
    FOREIGN KEY ({parent}_id) REFERENCES python_{parent}(id) ON DELETE CASCADE
);

-- Required indexes
CREATE INDEX idx_{short}_file ON python_{parent}_{items}(file);
CREATE INDEX idx_{short}_{parent} ON python_{parent}_{items}({parent}_id);
CREATE INDEX idx_{short}_{item} ON python_{parent}_{items}({item}_name);
```

### Fidelity Control Interface

```python
# theauditor/indexer/fidelity.py

class DataFidelityError(Exception):
    """Raised when extraction and storage counts don't match."""
    pass

def reconcile_fidelity(
    extraction_manifest: dict[str, int],
    storage_receipt: dict[str, int],
    strict: bool = True
) -> dict:
    """
    Compare extraction manifest to storage receipt.

    Args:
        extraction_manifest: {table_name: count} from extractor
        storage_receipt: {table_name: count} from storage
        strict: If True, raise DataFidelityError on zero-store

    Returns:
        Reconciliation report with errors/warnings

    Raises:
        DataFidelityError: If strict and data extracted but not stored
    """
```

### Two-Discriminator Column Naming

| Table | Kind Column | Type Column |
|-------|-------------|-------------|
| python_loops | loop_kind | loop_type |
| python_branches | branch_kind | branch_type |
| python_functions_advanced | function_kind | function_type |
| python_class_features | feature_kind | feature_type |
| python_protocols | protocol_kind | protocol_type |
| python_expressions | expression_kind | expression_type |
| python_comprehensions | comp_kind | comp_type |
| python_control_statements | statement_kind | statement_type |

---

## File Change Summary

| File | Action | Lines |
|------|--------|-------|
| `theauditor/indexer/fidelity.py` | CREATE | ~150 |
| `theauditor/indexer/exceptions.py` | MODIFY | +5 |
| `theauditor/indexer/schemas/python_schema.py` | MODIFY | ~500 |
| `theauditor/indexer/database/python_database.py` | MODIFY | ~200 |
| `theauditor/indexer/database/base_database.py` | MODIFY | +7 |
| `theauditor/indexer/storage/python_storage.py` | MODIFY | ~300 |
| `theauditor/ast_extractors/python_impl.py` | MODIFY | ~150 |
| `theauditor/indexer/orchestrator.py` | MODIFY | +20 |
| `theauditor/indexer/schema.py` | MODIFY | +1 |
| `tests/test_schema_contract.py` | CREATE | ~100 |

**Total Estimated Changes:** ~1,500 lines
