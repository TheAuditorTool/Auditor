# Proposal: Python Extractor Consolidation & Data Fidelity Control

## Executive Summary

The previous ticket (`wire-extractors-to-consolidated-schema`) wired 150 extractor outputs to 28 tables but **invented schema columns without verifying actual extractor output**. This caused ~22MB silent data loss.

This proposal fixes the root cause by:
1. **Aligning schemas to ground truth** (extractor_truth.txt)
2. **Implementing Data Fidelity Control** (extraction manifest + storage receipt + reconciliation)
3. **Eliminating JSON blobs** for proper SQL JOIN support
4. **Decomposing junk drawer tables** (python_expressions has 90% NULL sparsity)

**Final State**: 30 Python tables + 5 junction tables = **35 Python-related tables**

**Risk Level: HIGH** - Schema changes affect all downstream consumers (taint, graph, rules, FCE)

---

## Why

### The Problem (Current State)

```
EXTRACTORS: 87 extract_* functions with data (from extractor_truth.txt)
SCHEMA: 28 tables with INVENTED columns (not verified against extractors)
RESULT: ~22MB data loss, NULL values in key columns, broken SQL JOINs
```

### Root Cause Chain

1. **Schema columns invented** - Columns designed by reading code, not running extractors
2. **Discriminator overwrites data** - `loop['loop_type'] = 'for_loop'` destroys extractor's subtype ('enumerate', 'zip')
3. **No fidelity control** - No mechanism to detect extraction vs storage mismatch
4. **JSON blobs** - ~10 columns store JSON, blocking SQL JOINs
5. **Junk drawer tables** - `python_expressions` has 22 extractors, 55 columns, 90% NULL sparsity

### Evidence (From extractor_truth.txt)

**python_loops schema has INVENTED columns:**
| Schema Column | Status |
|---------------|--------|
| `target` | INVENTED - extractors output `target_count` |
| `iterator` | INVENTED - doesn't exist in any extractor |
| `body_line_count` | INVENTED - doesn't exist in any extractor |

**Actual extractor outputs (for_loops):**
```
['has_else', 'in_function', 'line', 'loop_type', 'nesting_level', 'target_count']
```

### Impact of Doing Nothing

1. **~22MB data permanently lost** - Cannot query what was never stored
2. **Broken analytics** - NULL values in WHERE clauses return nothing
3. **Blocked taint analysis** - Cannot JOIN on JSON blob columns
4. **Silent corruption** - No alert when extraction != storage

---

## What Changes

### Summary Table

| Action | Component | Before | After |
|--------|-----------|--------|-------|
| ADD | Data Fidelity Control | 0 checks | 3 components |
| ADD | Junction tables | 0 | 5 |
| ADD | Expression split tables | 0 | 2 |
| MODIFY | Python schema tables | 28 | 30 |
| MODIFY | Total schema tables | 129 | 136 |
| MODIFY | Storage handlers | 27 | 32 |
| MODIFY | DB mixin methods | 28 | 35 |
| REMOVE | JSON blob columns | ~10 | 0 |
| REMOVE | Invented schema columns | ~15 | 0 |

### Detailed Changes

#### 1. Data Fidelity Control (NEW)

**Files:**
- `theauditor/indexer/fidelity.py` (NEW) - Reconciliation logic
- `theauditor/indexer/exceptions.py` - Add `DataFidelityError`
- `theauditor/ast_extractors/python_impl.py` - Generate extraction manifest
- `theauditor/indexer/storage/python_storage.py` - Generate storage receipt
- `theauditor/indexer/orchestrator.py` - Call reconciliation check

**Behavior:**
- **Extraction Manifest**: Count of records per table from extractors
- **Storage Receipt**: Count of records actually stored per table
- **Reconciliation**: CRASH if extracted > 0 and stored == 0

#### 2. Schema Alignment to Ground Truth

**Files:**
- `theauditor/indexer/schemas/python_schema.py` - Fix all 20 consolidated tables

**Pattern - Two-Discriminator:**
```python
# BEFORE (destructive):
loop['loop_type'] = 'for_loop'  # Overwrites extractor's value

# AFTER (preserving):
loop['loop_kind'] = 'for'       # Table discriminator (NEW)
# loop['loop_type'] preserved   # Extractor's subtype ('enumerate', 'zip', etc.)
```

#### 3. Expression Table Decomposition

**NEW Tables:**
- `python_comprehensions` - List/dict/set/generator comprehensions
- `python_control_statements` - break/continue/pass/assert/del/with

**Re-routed Extractors:**
| Extractor | From | To |
|-----------|------|-----|
| `extract_copy_protocol` | python_expressions | python_protocols |
| `extract_class_decorators` | python_expressions | python_class_features |
| `extract_recursion_patterns` | python_expressions | python_functions_advanced |
| `extract_memoization_patterns` | python_expressions | python_functions_advanced |
| `extract_loop_complexity` | python_expressions | python_loops |

#### 4. Junction Tables for JSON Blob Elimination

**NEW Tables:**
- `python_protocol_methods` - Methods implemented by protocols
- `python_typeddict_fields` - TypedDict field definitions
- `python_fixture_params` - Pytest fixture parameters
- `python_schema_validators` - Validation schema validators
- `python_framework_methods` - Framework config methods

---

## Impact

### Affected Specs
- `python-extraction` (MODIFIED - schema alignment, new tables)

### Affected Code

**Schema Layer:**
- `theauditor/indexer/schemas/python_schema.py`
- `theauditor/indexer/schema.py` (table count assertion)

**Database Layer:**
- `theauditor/indexer/database/python_database.py`
- `theauditor/indexer/database/base_database.py` (flush_order)

**Storage Layer:**
- `theauditor/indexer/storage/python_storage.py`

**Orchestrator Layer:**
- `theauditor/ast_extractors/python_impl.py`
- `theauditor/indexer/orchestrator.py`

**NEW Files:**
- `theauditor/indexer/fidelity.py`
- `tests/test_schema_contract.py`

### Breaking Changes

| Change | Impact | Migration |
|--------|--------|-----------|
| Schema column renames | Queries using old names fail | Re-index with `aud full` |
| JSON blob removal | Code parsing JSON fails | Use junction table JOINs |
| Table additions | No impact | Automatic on re-index |

### Downstream Consumer Impact

| Consumer | Impact | Verification |
|----------|--------|--------------|
| Taint analyzer | Positive - can JOIN on methods | Run taint tests |
| Graph builder | None - doesn't use Python tables | N/A |
| Pattern rules | Verify column names | Run rule tests |
| FCE | Verify column names | Run FCE tests |
| Query command | Verify column names | Manual test |

---

## Polyglot Assessment

**Does this need Python + Node + Rust implementations?**

**NO** - This is Python extraction pipeline only:
- Python extractors (`theauditor/ast_extractors/python/`)
- Python schema (`theauditor/indexer/schemas/python_schema.py`)
- Python storage (`theauditor/indexer/storage/python_storage.py`)

Node.js extraction has its own schema (`node_schema.py`) and is not affected.
Rust is not used in the extraction pipeline.

**Orchestrator consideration:**
The orchestrator (`theauditor/indexer/orchestrator.py`) coordinates both Python and Node extraction, but the fidelity control we're adding only affects the Python path.

---

## Verification Criteria

- [ ] `len(PYTHON_TABLES) == 30` (28 current + 2 new)
- [ ] `len(TABLES) == 136` (129 + 5 junction + 2 expression split)
- [ ] All 87 extractor outputs (from truth) map to a table
- [ ] Fidelity check passes with 0 errors on `aud full --offline`
- [ ] Zero JSON blob columns in Python tables
- [ ] Max 50% NULL sparsity per table
- [ ] All junction table JOINs work
- [ ] Existing consumers (taint, rules, FCE) still work
- [ ] DB size recovers to >150MB (was 176MB before loss)

---

## Approval Gate

**DO NOT PROCEED** until:
1. Architect reviews and approves proposal
2. Lead Auditor validates technical design
3. Both approve the fidelity control approach

**STATUS: PENDING APPROVAL**
