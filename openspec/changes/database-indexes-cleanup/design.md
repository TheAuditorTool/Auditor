# Database Indexes & GraphQL Cleanup Design

**Status**: 🔴 DRAFT (trivial)

---

## 1. Index Design

### Before (no index)
Query: 9.82ms (full-table scan)

### After (indexed)
Query: <0.5ms (O(1) lookup)

**Change**: Add 2 lines to core_schema.py

---

## 2. GraphQL LIKE Pattern Fix

### Before
```sql
WHERE argument_expr LIKE '%pattern%'  -- Full-table scan
```

### After
```sql
WHERE file = ? AND line BETWEEN ? AND ?  -- Indexed
-- Then filter in Python: if pattern in expr
```

**Speedup**: <500ms → <50ms (minor)

---

## 3. Impact

**Total saved**: ~570ms per run (negligible but free)

**Effort**: 35 minutes

**Priority**: LOW (do last)
