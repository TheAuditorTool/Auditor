# Proposal: Wire Extractors to Consolidated Schema

## Executive Summary

The previous ticket (`consolidate-python-orphan-tables`) reduced Python schema from 149 to 8 tables. The 28 extractor files remain intact and produce ~150 output keys that now have nowhere to go.

This proposal completes the consolidation by adding **20 NEW consolidated tables** (grouped by domain) and wiring extractors to them.

**Final State**: 8 (kept) + 20 (new) = **28 Python tables**

**Risk Level: MEDIUM** - Requires careful mapping but no extractor logic changes

---

## Why

### The Problem (Current State)

```
EXTRACTORS: 28 files producing ~150 output keys (INTACT)
SCHEMA: 8 tables (CONSOLIDATED)
STORAGE: 7 handlers (CONSOLIDATED)

MISMATCH: Extractors produce data that has no storage destination.
Running `aud full` will silently drop ~142 extraction outputs.
```

### Root Cause

The first ticket interpreted "consolidate" as "delete". The correct interpretation:
1. **Keep extractors** - They provide coverage for ALL project types
2. **Consolidate tables** - Group related patterns into logical tables with type columns

### Impact of Doing Nothing

1. **Lost extraction data** - 142 pattern types extracted but not stored
2. **Broken coverage** - Django shops won't see Django patterns, Celery projects won't see Celery data
3. **Wasted CPU** - Extraction runs but data is discarded

---

## What Changes

### Summary

| Action | Component | Before | After |
|--------|-----------|--------|-------|
| ADD | `python_schema.py` tables | 8 | 28 |
| ADD | `python_storage.py` handlers | 7 | 27 |
| MODIFY | `python_impl.py` result dict | ~150 keys | ~28 keys |
| MODIFY | `schema.py` assertion | 109 | 129 |

---

## Consolidated Schema (28 Tables Total)

### KEPT AS-IS (8 tables with verified consumers)

| Table | Consumer |
|-------|----------|
| `python_decorators` | interceptors.py, deadcode_graph.py, query.py |
| `python_django_middleware` | interceptors.py |
| `python_django_views` | interceptors.py |
| `python_orm_fields` | graphql/overfetch.py |
| `python_orm_models` | overfetch.py, taint/discovery.py |
| `python_package_configs` | deps.py, blueprint.py |
| `python_routes` | boundary_analyzer.py, deadcode_graph.py, query.py |
| `python_validators` | taint/discovery.py |

### NEW CONSOLIDATED (20 tables)

#### Group 1: Control & Data Flow (5 Tables)

| Table | Consolidates | Discriminator |
|-------|-------------|---------------|
| `python_loops` | for_loops, while_loops, async_for_loops | `loop_type` |
| `python_branches` | if_statements, match_statements, try/except/finally | `branch_type` |
| `python_functions_advanced` | async_functions, generators, lambdas, context_managers | `function_type` |
| `python_io_operations` | file I/O, network, db, process I/O | `io_type` |
| `python_state_mutations` | global/class/instance/argument mutations | `mutation_type` |

#### Group 2: Object-Oriented & Types (5 Tables)

| Table | Consolidates | Discriminator |
|-------|-------------|---------------|
| `python_class_features` | metaclasses, slots, abstract_classes, dataclasses, enums | `feature_type` |
| `python_protocols` | iterator, container, context_manager, comparison protocols | `protocol_type` |
| `python_descriptors` | properties, descriptors, dynamic_attributes | `descriptor_type` |
| `python_type_definitions` | TypedDict, Generic, Protocol definitions | `type_kind` |
| `python_literals` | Literal types, overloads | `literal_type` |

#### Group 3: Security & Testing (5 Tables)

| Table | Consolidates | Discriminator |
|-------|-------------|---------------|
| `python_security_findings` | sql_injection, command_injection, path_traversal, crypto, eval | `finding_type` |
| `python_test_cases` | unittest, pytest test methods | `test_type` |
| `python_test_fixtures` | pytest fixtures, mock patterns, parametrize | `fixture_type` |
| `python_framework_config` | Flask config, Celery tasks/schedules, Django admin/signals | `framework`, `config_type` |
| `python_validation_schemas` | Marshmallow, DRF, WTForms schemas/fields | `framework`, `schema_type` |

#### Group 4: Low-Level & Misc (5 Tables)

| Table | Consolidates | Discriminator |
|-------|-------------|---------------|
| `python_operators` | binary, unary, boolean, comparison, walrus, ternary | `operator_type` |
| `python_collections` | dict, list, set, string operations, builtins | `collection_type` |
| `python_stdlib_usage` | regex, json, datetime, path, logging, threading | `module`, `usage_type` |
| `python_imports_advanced` | dynamic imports, namespace packages | `import_type` |
| `python_expressions` | comprehensions, slices, tuples, unpacking, formatting | `expression_type` |

---

## Impact Assessment

### Breaking Changes

| Impact | Description |
|--------|-------------|
| NONE for consumers | 8 tables with verified consumers unchanged |
| SCHEMA CHANGE | New tables added, requires re-index |

### Positive Impact

| Benefit | Metric |
|---------|--------|
| Coverage restored | All ~150 extractor outputs stored |
| Logical grouping | 149 tables -> 28 tables |
| Type discrimination | Query by discriminator for granular access |
| Future-proof | New patterns fit existing consolidated tables |

---

## Verification Criteria

- [ ] `len(PYTHON_TABLES) == 28`
- [ ] `len(TABLES) == 129`
- [ ] All ~150 extractor outputs map to a table
- [ ] `aud full --offline` stores data in all consolidated tables
- [ ] Existing consumers (interceptors, taint, etc.) still work
- [ ] Row counts match or exceed pre-consolidation levels

---

## Approval Gate

**DO NOT PROCEED** until:
1. Architect reviews consolidated table design
2. Lead Auditor validates mapping completeness
3. Both approve the discriminator column approach

**STATUS: APPROVED by Lead Auditor (Gemini) - 28 tables confirmed as architectural target**
