# Database Indexes & GraphQL Cleanup Tasks

**CRITICAL**: Trivial change - Should be done LAST after all other tiers

---

## Task 9: Add Missing Database Indexes

**Estimated Time**: 5 minutes

### 9.1 Read core_schema.py
- [ ] 9.1.1 Locate FUNCTION_CALL_ARGS schema definition
- [ ] 9.1.2 Verify existing indexes

### 9.2 Add Indexes
- [ ] 9.2.1 Add `idx_function_call_args_argument_index`
- [ ] 9.2.2 Add `idx_function_call_args_param_name` (optional)

### 9.3 Test
- [ ] 9.3.1 Run `aud full`
- [ ] 9.3.2 Verify indexes created: `SELECT name FROM sqlite_master WHERE type='index'`
- [ ] 9.3.3 Benchmark query speedup: 9.82ms → <0.5ms

---

## Task 10: Fix GraphQL LIKE Patterns

**Estimated Time**: 30 minutes

### 10.1 Fix graphql/injection.py:103
- [ ] 10.1.1 Read current query
- [ ] 10.1.2 Replace LIKE with indexed pre-filter + Python search
- [ ] 10.1.3 Test on GraphQL fixture
- [ ] 10.1.4 Verify findings unchanged

### 10.2 Fix graphql/input_validation.py:38
- [ ] 10.2.1 Read current query
- [ ] 10.2.2 Replace LIKE with indexed query + Python filter
- [ ] 10.2.3 Test on GraphQL fixture
- [ ] 10.2.4 Verify findings unchanged

---

## Completion Checklist

- [ ] 2 indexes added
- [ ] 2 GraphQL queries fixed
- [ ] All tests passing
- [ ] ~570ms saved (documented)

---

**Status**: 🔴 AWAITING APPROVAL (trivial)

**Estimated Time**: 35 minutes (padded to 1-2 days for process overhead)
