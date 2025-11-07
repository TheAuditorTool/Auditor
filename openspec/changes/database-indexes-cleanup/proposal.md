# Database Indexes & GraphQL Cleanup

**Status**: 🔴 PROPOSAL - Awaiting Architect approval

**Parent Proposal**: `performance-revolution-now` (TIER 2 Tasks 9 & 10)

**Assigned to**: Any AI (Trivial - recommend Sonnet or Haiku)

**Timeline**: 1-2 days (realistically 35 minutes, padded for process overhead)

**Impact**: 🟢 **LOW** - 120ms saved per run + minor GraphQL query improvements

**Priority**: LOW - Should be done LAST after all other tiers

---

## Why

### **Problem 1: Missing Database Indexes (120ms overhead)**

Two database indexes are missing, causing 120ms overhead per `aud full` run:

1. **`function_call_args.argument_index`** - Queried frequently, no index (9.82ms per query)
2. **`function_call_args.param_name`** - Optional, lower priority

**Impact**: Minor but free performance gain (add 2 lines to schema)

### **Problem 2: GraphQL LIKE Wildcard Patterns (<500ms overhead)**

Two GraphQL rules use LIKE wildcard patterns (minor anti-pattern):

1. **`graphql/injection.py:103`** - `argument_expr LIKE '%{arg}%'`
2. **`graphql/input_validation.py:38`** - `arg_type LIKE '%String%'`

**Impact**: <500ms total (low priority, but easy to fix)

---

## What Changes

### **Task 9: Add Missing Database Indexes**

**File**: `theauditor/indexer/schemas/core_schema.py`

**Change**: Add 2 index definitions (2 lines)

```python
# Add to FUNCTION_CALL_ARGS table schema:
indexes=[
    ("idx_function_call_args_callee", ["callee_function"]),  # Existing
    ("idx_function_call_args_argument_index", ["argument_index"]),  # NEW
    ("idx_function_call_args_param_name", ["param_name"]),  # NEW (optional)
]
```

**Impact**: 9.82ms → <0.5ms per query (20x speedup on indexed queries)

### **Task 10: Fix GraphQL LIKE Patterns**

**File 1**: `theauditor/rules/graphql/injection.py:103`

```python
# BEFORE:
WHERE argument_expr LIKE '%{arg}%'

# AFTER:
WHERE file = ? AND line BETWEEN ? AND ?  # Indexed pre-filter
# Then filter in Python: if arg in expr
```

**File 2**: `theauditor/rules/graphql/input_validation.py:38`

```python
# BEFORE:
WHERE arg_type LIKE '%String%' OR arg_type LIKE 'Input%'

# AFTER:
WHERE type_name = 'Mutation' AND is_nullable = 1  # Indexed
# Then filter in Python: if 'String' in arg_type or arg_type.startswith('Input')
```

**Impact**: <500ms total (minor)

---

## Impact

### **Affected Code**

**Modified Files** (minimal):
- `theauditor/indexer/schemas/core_schema.py` - Add 2 indexes (2 lines)
- `theauditor/rules/graphql/injection.py` - Fix query (10 lines)
- `theauditor/rules/graphql/input_validation.py` - Fix query (10 lines)

**Total**: ~22 lines changed

### **Breaking Changes**

**None** - Additive only:
- Indexes are additive (backward compatible)
- GraphQL rule output unchanged (same findings)

### **Performance Targets**

**Database Indexes**:
- Before: 9.82ms per query
- After: <0.5ms per query
- Total saved: ~120ms per run (minor)

**GraphQL LIKE Patterns**:
- Before: <500ms overhead
- After: <50ms overhead
- Total saved: <450ms per run (minor)

**Combined Impact**: ~570ms saved per run (negligible, but free)

---

## Dependencies

**Prerequisites**:
- ✅ Schema system exists
- ✅ GraphQL rules exist

**Required Reading** (minimal):
1. `performance-revolution-now/tasks.md` sections 9.1-9.5 (indexes) and 10.1-10.5 (GraphQL)
2. Commit d8370a7 diff (understand index pattern)

**Blocking**: None - Can start immediately

**Should be done LAST**: After TIER 0, TIER 1, TIER 1.5 (trivial cleanup)

---

## Testing Strategy

### **Index Testing**

1. **Verify indexes created**:
```bash
aud full
sqlite3 .pf/repo_index.db "SELECT name FROM sqlite_master WHERE type='index'"
```
2. **Verify speedup**: Query should be <0.5ms (down from 9.82ms)

### **GraphQL Testing**

1. **Run GraphQL rules on fixture projects**
2. **Compare findings before/after** (must match exactly)

---

## Success Criteria

**MUST MEET ALL** (trivial):

1. ✅ Indexes created successfully
2. ✅ GraphQL findings unchanged (byte-for-byte)
3. ✅ All tests passing
4. ✅ ~570ms saved per run (documented)

---

## Approval Gates

**Stage 1**: Proposal Review (Current)
- [ ] Architect approves (should be instant - trivial change)

**Stage 2**: Implementation
- [ ] Add 2 indexes (5 minutes)
- [ ] Fix 2 GraphQL queries (30 minutes)
- [ ] Test (30 minutes)

**Stage 3**: Deployment
- [ ] Merged to main

---

## Related Changes

**Parent**: `performance-revolution-now` (PAUSED AND SPLIT)

**Siblings**:
- `taint-analysis-spatial-indexes` (AI #1, TIER 0)
- `fix-python-ast-orchestrator` (AI #2, TIER 0)
- `vue-inmemory-module-resolution` (AI #3, TIER 1)
- `fce-json-normalization` (AI #4, TIER 1.5)

**Should be done LAST**: After all other proposals merged

---

**Next Step**: Architect approves trivial change
