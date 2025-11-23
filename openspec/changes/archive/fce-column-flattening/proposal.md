# FCE Column Flattening

**Status**: 🔴 PROPOSAL
**Complexity**: TRIVIAL
**Time**: 2 hours
**Breaking**: No (backwards compatible)

---

## Why

FCE spends 125-700ms parsing JSON from `details_json` column. This is stupid. Just use columns.

**Current reality** (verified 2025-11-24):
- 21,900 rows in findings_consolidated
- Only 4,521 rows (20.6%) have details_json
- 97% of those are trivial mypy data: `{"mypy_severity": "error"}`
- Only ~124 rows have actual complex data

**Breakdown**:
- mypy: 4,397 rows - just severity level
- cfg-analysis: 66 rows - 9 fields (complexity, block_count, etc)
- graph-analysis: 50 rows - 7 fields (centrality, in_degree, etc)
- terraform: 7 rows - resource info
- taint: 1 row - complex nested path (keep in JSON for now)

---

## What

Add columns for the actual data being stored. Use partial indexes for sparse data.

```sql
-- Add columns for actual data
ALTER TABLE findings_consolidated
ADD COLUMN mypy_severity TEXT;      -- 4,397 rows
ADD COLUMN mypy_code TEXT;          -- Some mypy findings have error codes

-- CFG analysis columns (66 rows)
ADD COLUMN complexity INTEGER;
ADD COLUMN block_count INTEGER;
ADD COLUMN function_name TEXT;
ADD COLUMN max_nesting INTEGER;

-- Graph analysis columns (50 rows)
ADD COLUMN in_degree INTEGER;
ADD COLUMN out_degree INTEGER;
ADD COLUMN centrality REAL;
ADD COLUMN hotspot_score REAL;

-- Keep details_json for now (1 complex taint path)
-- Drop it later after taint is refactored

-- Partial indexes - only index non-NULL values
CREATE INDEX idx_fce_complexity ON findings_consolidated(complexity)
    WHERE complexity IS NOT NULL;
CREATE INDEX idx_fce_hotspot ON findings_consolidated(hotspot_score)
    WHERE hotspot_score IS NOT NULL;
CREATE INDEX idx_fce_centrality ON findings_consolidated(centrality)
    WHERE centrality IS NOT NULL;
```

---

## Impact

### Files to Change (6 total)

**Writers (4 files)**:
1. `theauditor/aws_cdk/analyzer.py:252` - Already writes NULL, no change
2. `theauditor/vulnerability_scanner.py:650` - Update to write columns
3. `theauditor/terraform/analyzer.py:176` - Update to write columns
4. `theauditor/indexer/database/base_database.py:688` - Update generic writer

**Readers (2 files)**:
1. `theauditor/fce.py` - 6 SELECT queries at lines 54, 71, 121, 162, 201, 257
2. `theauditor/aws_cdk/analyzer.py:142-145` - Update parser

**Total changes**: ~200 lines

---

## Before/After

### Before (JSON parsing hell)
```python
# fce.py line 63 - SLOW
details = json.loads(details_json)  # 5-500ms depending on size
complexity = details.get('complexity', 0)
```

### After (Direct column access)
```python
# fce.py - FAST
cursor.execute("""
    SELECT file, complexity, block_count
    FROM findings_consolidated
    WHERE tool='cfg-analysis' AND complexity > 20
""")
# 0.1ms with index
```

**Performance**: 125-700ms → <1ms (99.9% reduction)

---

## Migration Strategy

### Phase 1: Add Columns (Non-breaking)
1. ALTER TABLE to add columns
2. Keep details_json for compatibility
3. No code breaks

### Phase 2: Dual Write (1 hour)
```python
# Write to both for safety
cursor.execute("""
    INSERT INTO findings_consolidated
    (file, line, tool, complexity, block_count, details_json)
    VALUES (?, ?, ?, ?, ?, ?)
""", (file, line, tool, complexity, block_count,
      json.dumps({'complexity': complexity, 'block_count': block_count})))
```

### Phase 3: Update Readers (1 hour)
```python
# Read from columns, fallback to JSON if needed
complexity = row['complexity']
if complexity is None and row['details_json']:
    # Fallback for old data
    details = json.loads(row['details_json'])
    complexity = details.get('complexity')
```

### Phase 4: Cleanup (Later)
- Stop writing to details_json
- Drop column after all data migrated

---

## Testing

1. **Add columns** - Verify schema updated
2. **Run writers** - Verify columns populated
3. **Run FCE** - Verify reads from columns
4. **Performance test** - Verify <1ms queries
5. **Rollback test** - Verify fallback to JSON works

---

## Success Criteria

- [ ] Columns added to schema
- [ ] 4 writers updated
- [ ] 2 readers updated
- [ ] FCE query time <1ms (from 125-700ms)
- [ ] Zero data loss
- [ ] Backwards compatible

---

## Why This is Better Than Junction Tables

My first proposal had 5 junction tables, 700+ lines of changes, complex migrations.

This approach:
- 10 columns added
- 200 lines changed
- 2 hours work
- Same performance gain
- Actually maintainable

Partial indexes are the key - they stay tiny on sparse columns.