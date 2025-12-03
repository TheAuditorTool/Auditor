## 0. Verification
- [x] 0.1 Verify GoHttpStrategy exists at `theauditor/graph/strategies/go_http.py:15`
- [x] 0.2 Verify GoOrmStrategy exists at `theauditor/graph/strategies/go_orm.py:18`
- [x] 0.3 Verify strategies are NOT imported in `theauditor/graph/dfg_builder.py:13-17`
- [x] 0.4 Verify strategies are NOT in `self.strategies` list at `dfg_builder.py:30-36`
- [x] 0.5 Document discrepancy: Original plan was stale (BashPipeStrategy added since)

---

## 1. Implementation

> **Spec**: `specs/graph/spec.md`

### 1.1 Add Imports
> **Spec ref**: GoHttpStrategy/GoOrmStrategy import scenarios

- [ ] 1.1.1 Add `from .strategies.go_http import GoHttpStrategy` after bash_pipes import
- [ ] 1.1.2 Add `from .strategies.go_orm import GoOrmStrategy` after go_http import
- [ ] 1.1.3 Maintain alphabetical order in imports

### 1.2 Register Strategies
> **Spec ref**: GoHttpStrategy/GoOrmStrategy registration scenarios

- [ ] 1.2.1 Add `GoHttpStrategy(),` to `self.strategies` list after BashPipeStrategy
- [ ] 1.2.2 Add `GoOrmStrategy(),` to `self.strategies` list after GoHttpStrategy

---

## 2. Verification

### 2.1 Syntax Check
- [ ] 2.1.1 Run `python -m py_compile theauditor/graph/dfg_builder.py`
- [ ] 2.1.2 Confirm no import errors

### 2.2 Functional Test
- [ ] 2.2.1 Run `aud full --offline` (verify no crash)
- [ ] 2.2.2 Check unified graph metadata for `go_http` and `go_orm` in strategy_stats

---

## Summary

| Phase | Status | Completed |
|-------|--------|-----------|
| Phase 0: Verification | COMPLETE | 5/5 |
| Phase 1: Implementation | PENDING | 0/5 |
| Phase 2: Verification | PENDING | 0/4 |

**Total Progress: 5/14 tasks (36%)**
