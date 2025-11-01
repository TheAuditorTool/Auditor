# Track 2 (Python) - Handoff from Node AI

**Date**: 2025-11-01
**From**: AI-1 (Node Specialist - Sonnet 4.5)
**To**: AI-2 (Python Specialist)
**Status**: Track 1 (Node/JavaScript) COMPLETE - Critical Python bug discovered during verification

---

## Executive Summary

Track 1 (Node/JavaScript) is complete with all fixes verified. During verification, I discovered a **CRITICAL BUG in Python framework extractors** that causes data loss in ORM relationship deduplication. This is Track 2's responsibility to fix.

---

## The Python Bug - ORM Deduplication Keys

### Problem Description

Python framework extractors (`theauditor/ast_extractors/python/framework_extractors.py`) use **INCORRECT deduplication keys** that **EXCLUDE `relationship_type`** from the composite key. This causes data loss when:

- Same source model has multiple relationship types to same target model on same line
- Example: `User.posts = relationship(Post); User.authored_posts = relationship(Post)` on same line would deduplicate to only one relationship

### Affected Code Locations

**File**: `theauditor/ast_extractors/python/framework_extractors.py`

**Location 1 - SQLAlchemy (Lines 220, 352):**
```python
# Line 220: Dedup set declaration
seen_relationships: Set[Tuple[str, str, str]] = set()

# Line 352: BROKEN dedup key (missing relationship_type)
key = (rel_line, source_model, target_name)  # ❌ WRONG - only 3 elements
if key in seen_relationships:
    return

relationships.append({
    "line": rel_line,
    "source_model": source_model,
    "target_model": target_name,
    "relationship_type": rel_type,  # ← This SHOULD be in the key!
    "foreign_key": fk_name,
    "cascade_delete": cascade_flag,
    "as_name": alias,
})
seen_relationships.add(key)
```

**Location 2 - Django (Lines 420, 465):**
```python
# Line 420: Dedup set declaration
seen_relationships: Set[Tuple[int, str, str, str]] = set()  # 4 elements but still wrong

# Line 465: BROKEN dedup key (missing relationship_type)
rel_key = (line_no, node.name, target or "Unknown")  # ❌ WRONG - only 3 elements
if rel_key not in seen_relationships:
    relationships.append({
        "line": line_no,
        "source_model": node.name,
        "target_model": target or "Unknown",
        "relationship_type": "belongsTo",  # ← This SHOULD be in the key!
        "foreign_key": attr_name,
        "cascade_delete": cascade,
        "as_name": attr_name,
    })
    seen_relationships.add(rel_key)
```

---

## The Correct Implementation (Node Reference)

**File**: `theauditor/ast_extractors/javascript/core_ast_extractors.js`

**Lines 1071-1079 (CORRECT):**
```javascript
// Create deduplication key matching Python implementation
const dedupKey = `${sourceModel}-${targetModel}-${methodName}-${lineNum}`;
//                                               ^^^^^^^^^^^ relationship_type included!

// Skip if we've already seen this relationship
if (seenRelationships.has(dedupKey)) {
    return;
}

// Add to deduplication set
seenRelationships.add(dedupKey);
```

**Key format**: `sourceModel-targetModel-relationshipType-line`

---

## Required Fix for Python

### SQLAlchemy Fix (Line 352):

**Before (BROKEN):**
```python
key = (rel_line, source_model, target_name)  # Missing relationship_type
```

**After (FIXED):**
```python
key = (rel_line, source_model, target_name, rel_type)  # Include relationship_type
```

### Django Fix (Line 465):

**Before (BROKEN):**
```python
rel_key = (line_no, node.name, target or "Unknown")  # Missing relationship_type
```

**After (FIXED):**
```python
rel_key = (line_no, node.name, target or "Unknown", "belongsTo")  # Include relationship_type
```

**IMPORTANT**: Also update the Set type hints at lines 220 and 420 to match:
```python
# Line 220 (SQLAlchemy)
seen_relationships: Set[Tuple[int, str, str, str]] = set()  # 4 elements now

# Line 420 (Django) - already 4 elements, but verify the pattern matches
```

---

## Why This Matters

### Data Integrity Issue

Without `relationship_type` in the dedup key:

```python
# Example: SQLAlchemy relationships on same line
User.posts = relationship(Post, back_populates='author')  # hasMany
User.liked_posts = relationship(Post, secondary='likes')  # belongsToMany

# With BROKEN key: (line=10, source='User', target='Post')
# Both relationships deduplicate to same key → second one is LOST

# With CORRECT key: (line=10, source='User', target='Post', type='hasMany')
#                   (line=10, source='User', target='Post', type='belongsToMany')
# Different keys → both relationships preserved
```

### Database Schema Implications

The `orm_relationships` table PRIMARY KEY is:
```sql
PRIMARY KEY (file, line, source_model, target_model)
```

Notice: **PRIMARY KEY does NOT include `relationship_type`**

This means:
1. Database schema allows multiple relationships with same (file, line, source, target) if they have different types
2. But Python dedup logic prevents extracting them in the first place
3. This is a **semantic bug** - Python should extract all relationships and let database enforce uniqueness

**Recommendation**: Keep the fix to include `relationship_type` in dedup key. If database constraint causes issues, that's a separate schema bug to fix later.

---

## Verification After Fix

Run these queries to verify the fix:

```python
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

# 1. Check for duplicate ORM relationships (should be 0)
c.execute('''
    SELECT COUNT(*) FROM (
        SELECT file, line, source_model, target_model, relationship_type, COUNT(*) as count
        FROM orm_relationships
        GROUP BY file, line, source_model, target_model, relationship_type
        HAVING count > 1
    )
''')
print(f'Duplicate ORM relationships: {c.fetchone()[0]}')  # Should be 0

# 2. Check total ORM relationships (should INCREASE after fix)
c.execute('SELECT COUNT(*) FROM orm_relationships')
print(f'Total ORM relationships: {c.fetchone()[0]}')

# 3. Show relationships with same source/target but different types
c.execute('''
    SELECT source_model, target_model, COUNT(DISTINCT relationship_type) as type_count
    FROM orm_relationships
    GROUP BY source_model, target_model
    HAVING type_count > 1
''')
print('\\nMultiple relationship types between same models:')
for row in c.fetchall():
    print(f'  {row[0]} <-> {row[1]}: {row[2]} different types')

conn.close()
```

---

## Track 1 (Node) Completion Status

✅ **GraphQL Resolver Params**: Fixed Apollo, NestJS, TypeGraphQL to return `{name: "param"}` format
✅ **ORM Relationship Deduplication**: Added with CORRECT key including relationship_type
✅ **Sequelize Bidirectional Relationships**: Added inverse generation (hasMany ↔ belongsTo)
✅ **Verification**: 0 dict param_names, 63,193 valid params, 0 duplicate relationships, 108 total relationships
✅ **Full Indexing**: Completes without errors

---

## Files Modified by Track 1 (Node)

1. `theauditor/ast_extractors/javascript/framework_extractors.js` (lines 529-532, 590-593, 661-664)
2. `theauditor/ast_extractors/javascript/core_ast_extractors.js` (lines 964, 1071-1079)
3. `theauditor/ast_extractors/javascript/sequelize_extractors.js` (lines 110-137)

**Zero overlap with Python files** - Track 1 and Track 2 are completely independent.

---

## Next Steps for Python AI

1. ✅ Read this handoff document completely
2. ✅ Fix SQLAlchemy dedup key at line 352
3. ✅ Fix Django dedup key at line 465
4. ✅ Update Set type hints at lines 220, 420 if needed
5. ✅ Run `aud index` and verify no errors
6. ✅ Run verification queries above
7. ✅ Update `openspec/changes/fix-extraction-data-quality/tasks.md` to mark Track 2 tasks complete
8. ✅ Create PYTHON_TRACK_COMPLETION_REPORT.md similar to NODE_TRACK_COMPLETION_REPORT.md

---

## Questions for Python AI

If you encounter any issues or have questions:

1. **"Should I also check other Python extractors?"** - Yes, audit all extractors in `theauditor/ast_extractors/python/` for similar patterns
2. **"What if database constraint fails after fix?"** - Report it as a separate schema bug, but keep the fix
3. **"Should I add bidirectional relationships like Node did?"** - Check if SQLAlchemy/Django already have `back_populates` handling. If not, add it.

---

## Contact

If you need clarification on Node implementation or architectural contracts, refer to:
- `NODE_TRACK_COMPLETION_REPORT.md` - Full details on Node fixes
- `theauditor/ast_extractors/typescript_impl.py:295-314` - Architectural contract for param format
- `theauditor/ast_extractors/javascript/core_ast_extractors.js:1071-1079` - Correct dedup pattern

Good luck with Track 2!

**- AI-1 (Node Specialist)**
