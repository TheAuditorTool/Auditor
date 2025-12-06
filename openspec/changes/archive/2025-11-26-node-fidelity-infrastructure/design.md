## Context

Node.js extraction pipeline lacks the Data Fidelity Control system that was implemented for Python in the `python-extractor-consolidation-fidelity` ticket. This leaves Node extraction vulnerable to silent data loss - the same 22MB bug that was discovered and fixed in Python.

**Stakeholders:**
- Lead Coder (Opus): Implementation
- Lead Auditor (Gemini): Verification (completed Phase 0)
- Architect: Approval

**Constraints:**
- ZERO FALLBACK POLICY (CLAUDE.md): No try/except catching to return empty
- Must use existing `generic_batches` infrastructure (no new patterns)
- Must not break existing working handlers (8 of 17 already correct)

## Goals / Non-Goals

### Goals
1. Install manifest/receipt fidelity checking for Node/JS/TS files
2. Fix 9 rogue storage handlers to use batched database methods
3. Achieve parity with Python extraction reliability

### Non-Goals
1. Schema normalization (junction tables, two-discriminator) - deferred to `node-schema-normalization` ticket
2. Contract tests - deferred to `node-schema-normalization` ticket
3. Extractor audit script (`audit_node_extractors.py`) - deferred to `node-schema-normalization` ticket
4. Performance optimization - out of scope

## Decisions

### Decision 1: Add manifest generation in `javascript.py` not `typescript_impl.py`

**Why:** `javascript.py` is the single entry point for ALL JS/TS extraction (it delegates to `typescript_impl.py`). Adding manifest at this layer ensures all paths are covered.

**Evidence:** `python_impl.py` generates manifest at the delegation layer, not in individual extractors.

**Pattern:**
```python
# At end of extract() before return
manifest = {}
for key, value in result.items():
    if key.startswith('_') or not isinstance(value, list):
        continue
    if len(value) > 0:
        manifest[key] = len(value)
result['_extraction_manifest'] = manifest
```

### Decision 2: Use `self.generic_batches[table_name].append()` pattern

**Why:** This is the established pattern in `python_database.py` and existing `node_database.py` methods. It provides:
- Transaction coherence (all inserts happen in one commit)
- Performance (batch inserts vs individual)
- Receipt tracking compatibility (storage counts items passed to handlers)

**Alternatives considered:**
- Direct cursor with batching: Rejected - bypasses receipt tracking
- Custom batch dict per handler: Rejected - duplication, error-prone

**Pattern:**
```python
def add_sequelize_model(self, file, line, model_name, table_name=None, extends_model=False):
    self.generic_batches['sequelize_models'].append((
        file, line, model_name, table_name, 1 if extends_model else 0
    ))
```

### Decision 3: Preserve extractor field name mappings in handlers

**Why:** Several Node extractors return field names that differ from schema columns. The handlers must map these correctly.

**Complete Field Name Mapping Table (verified from `node_storage.py`):**

| Handler | Line | Extractor Field | Schema Column |
|---------|------|-----------------|---------------|
| `_store_bullmq_queues` | 184 | `name` | `queue_name` |
| `_store_angular_components` | 221 | `name` | `component_name` |
| `_store_angular_services` | 242 | `name` | `service_name` |
| `_store_angular_modules` | 261 | `name` | `module_name` |
| `_store_angular_guards` | 282 | `name` | `guard_name` |
| `_store_di_injections` | 302 | `service` | `injected_service` |

**Note:** `_store_sequelize_models`, `_store_sequelize_associations`, `_store_bullmq_workers` use matching field names (no mapping needed).

**Decision:** Keep mappings in handlers, NOT in `add_*()` methods. Methods should match schema exactly.

### Decision 4: Initialize counts dict keys defensively

**Why:** Several handlers use `self.counts['key'] += 1` which fails if key doesn't exist. Must use `self.counts.get('key', 0) + 1` or pre-initialize.

**Pattern:**
```python
self.counts['sequelize_models'] = self.counts.get('sequelize_models', 0) + 1
```

## Risks / Trade-offs

### Risk 1: Fidelity check crashes immediately after enabling

**Likelihood:** HIGH - Expected behavior
**Impact:** Blocks indexing until all handlers fixed
**Mitigation:** Fix all 9 handlers in same PR. Do NOT ship manifest generation without handler fixes.

### Risk 2: Field name mapping bugs cause data loss

**Likelihood:** MEDIUM
**Impact:** Silent data loss (fields stored to wrong columns)
**Mitigation:** Compare extractor output field names against schema columns during implementation. Document mappings in handler comments.

### Risk 3: generic_batches doesn't have all Node table keys

**Status:** RESOLVED - NOT A RISK

**Evidence:** `database/__init__.py:97` initializes `generic_batches = defaultdict(list)`.
Any key access automatically creates an empty list - no pre-initialization needed.

**Conclusion:** All 9 table keys will work automatically. No action required.

## Migration Plan

1. **Enable in single PR:** All changes (manifest + methods + handlers) in one commit
2. **Test on Node-heavy codebase:** Run `aud full --offline` on React+Express project
3. **Verify no fidelity errors:** Check logs for "Fidelity Check FAILED"
4. **Rollback:** Simple git revert if issues discovered

## Open Questions

1. **Q:** Should we enable strict mode immediately or start with warnings?
   **A:** Strict mode (crash on mismatch). ZERO FALLBACK POLICY.

2. **Q:** What if extractor produces data but handler doesn't exist?
   **A:** This is already a bug (data loss). Fidelity check will catch it. Fix by adding handler.

3. **Q:** Do all 9 tables have corresponding keys in `generic_batches`?
   **A:** RESOLVED. `generic_batches = defaultdict(list)` - any key works automatically. No initialization needed.
