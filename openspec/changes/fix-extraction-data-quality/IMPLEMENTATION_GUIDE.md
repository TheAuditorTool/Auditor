# Implementation Guide - EXACT FIXES WITH CODE

## Critical Context
**Problem**: Extractors produce `{param_name: 'foo'}` objects but storage expects `'foo'` strings
**Impact**: 5,800+ database errors, pipeline crashes
**Solution**: Fix at source, not symptoms

---

## TRACK 1: JavaScript/Node Fixes (AI-1)

### Fix 1.1: Apollo Resolver Parameter Extraction
**File**: `theauditor/ast_extractors/javascript/framework_extractors.js:529-543`

**BEFORE (BROKEN)**:
```javascript
// Line 529-543
const params = (func.params || [])
    .filter(p => !['parent', 'args', 'context', 'info', '_'].includes(p.name))
    .map((p, idx) => ({
        param_name: p.name,      // ❌ WRONG: Creating object with param_name field
        param_index: idx,
        is_kwargs: p.name === 'args' || p.destructured
    }));

resolvers.push({
    resolver_name: func.name,
    resolver_type: parent ? 'field' : 'root',
    params: params,              // ❌ WRONG: Array of objects
    parent_type: parent,
    field_name: fieldName || func.name,
    return_type: returnType,
    line: func.line
});
```

**AFTER (FIXED)**:
```javascript
// Line 529-543
const params = (func.params || [])
    .filter(p => !['parent', 'args', 'context', 'info', '_'].includes(p.name))
    .map(p => p.name);           // ✅ CORRECT: Just the string names

resolvers.push({
    resolver_name: func.name,
    resolver_type: parent ? 'field' : 'root',
    params: params,              // ✅ CORRECT: Array of strings ['user', 'input']
    parent_type: parent,
    field_name: fieldName || func.name,
    return_type: returnType,
    line: func.line
});
```

**TEST COMMAND**:
```bash
# After fix, this should show NO dict warnings:
THEAUDITOR_DEBUG=1 .venv/Scripts/python.exe -m theauditor.cli index tests/fixtures/javascript/graphql 2>&1 | grep "param_name is dict"
# Expected: No output (all params are strings now)
```

### Fix 1.2: NestJS Resolver Parameter Extraction
**File**: `theauditor/ast_extractors/javascript/framework_extractors.js:593-607`

**BEFORE (BROKEN)**:
```javascript
// Line 593-607
const params = (method.params || [])
    .filter(p => !p.decorators || p.decorators.length === 0)
    .map((p, idx) => ({
        param_name: p.name,      // ❌ WRONG: Object with param_name
        param_index: idx,
        is_kwargs: p.destructured || false
    }));
```

**AFTER (FIXED)**:
```javascript
// Line 593-607
const params = (method.params || [])
    .filter(p => !p.decorators || p.decorators.length === 0)
    .map(p => p.name);           // ✅ CORRECT: Just strings
```

### Fix 1.3: TypeGraphQL Resolver Parameter Extraction
**File**: `theauditor/ast_extractors/javascript/framework_extractors.js:667-682`

**BEFORE (BROKEN)**:
```javascript
// Line 667-682
const params = (method.params || [])
    .filter(p => p.decorators && p.decorators.some(d => d.name === 'Arg'))
    .map((p, idx) => {
        const argDecorator = p.decorators.find(d => d.name === 'Arg');
        const argName = argDecorator && argDecorator.args && argDecorator.args[0]
            ? argDecorator.args[0].replace(/['"]/g, '')
            : p.name;
        return {
            param_name: p.name,  // ❌ WRONG: Object
            param_index: idx,
            is_kwargs: false,
            arg_name: argName
        };
    });
```

**AFTER (FIXED)**:
```javascript
// Line 667-682
const params = (method.params || [])
    .filter(p => p.decorators && p.decorators.some(d => d.name === 'Arg'))
    .map(p => p.name);           // ✅ CORRECT: Just strings
```

### Fix 2.1-2.2: Add ORM Relationship Deduplication
**File**: `theauditor/ast_extractors/javascript/core_ast_extractors.js:959-1086`

**BEFORE (NO DEDUP)**:
```javascript
// Line 959
function extractORMRelationships(sourceFile, ts) {
    const relationships = [];
    // ❌ MISSING: No deduplication

    function traverse(node) {
        // ... traversal logic ...

        // Line 1070-1086
        if (sourceModel && targetModel) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));

            relationships.push({          // ❌ WRONG: Always pushes, creates duplicates
                line: line + 1,
                source_model: sourceModel,
                target_model: targetModel,
                relationship_type: methodName,
                foreign_key: foreignKey,
                cascade_delete: cascadeDelete,
                as_name: asName
            });
        }
    }

    traverse(sourceFile);
    return relationships;
}
```

**AFTER (WITH DEDUP)**:
```javascript
// Line 959
function extractORMRelationships(sourceFile, ts) {
    const relationships = [];
    const seenRelationships = new Set();  // ✅ ADD: Deduplication set

    function traverse(node) {
        // ... traversal logic ...

        // Line 1070-1086
        if (sourceModel && targetModel) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));

            // ✅ ADD: Create dedup key matching Python format
            const dedupKey = `${line + 1}:${sourceModel}:${targetModel}:${methodName}`;

            // ✅ ADD: Check if already seen
            if (!seenRelationships.has(dedupKey)) {
                relationships.push({
                    line: line + 1,
                    source_model: sourceModel,
                    target_model: targetModel,
                    relationship_type: methodName,
                    foreign_key: foreignKey,
                    cascade_delete: cascadeDelete,
                    as_name: asName
                });
                seenRelationships.add(dedupKey);  // ✅ ADD: Mark as seen
            }
        }
    }

    traverse(sourceFile);
    return relationships;
}
```

**VERIFICATION**:
```bash
# Count ORM relationships before and after fix
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM orm_relationships')
print(f'Total relationships: {c.fetchone()[0]}')
c.execute('SELECT source_model, target_model, COUNT(*) as cnt FROM orm_relationships GROUP BY source_model, target_model HAVING cnt > 1')
duplicates = c.fetchall()
if duplicates:
    print('DUPLICATES FOUND:')
    for row in duplicates:
        print(f'  {row[0]} -> {row[1]}: {row[2]} copies')
else:
    print('No duplicates - deduplication working!')
"
```

### Fix 3.1-3.2: Sequelize Bidirectional Relationships
**File**: `theauditor/ast_extractors/javascript/sequelize_extractors.js:69-100`

**BEFORE (UNIDIRECTIONAL)**:
```javascript
// Line 69-100
if (targetModel) {
    associations.push({
        line: line + 1,
        source_model: sourceModel,
        target_model: targetModel,
        relationship_type: methodName,
        foreign_key: foreignKey || null,
        cascade_delete: cascade,
        as_name: as || null
    });
    // ❌ MISSING: No inverse relationship
}
```

**AFTER (BIDIRECTIONAL)**:
```javascript
// Line 69-100
if (targetModel) {
    // ✅ Forward relationship (User -> Post)
    associations.push({
        line: line + 1,
        source_model: sourceModel,
        target_model: targetModel,
        relationship_type: methodName,
        foreign_key: foreignKey || null,
        cascade_delete: cascade,
        as_name: as || null
    });

    // ✅ ADD: Inverse relationship (Post -> User)
    const inverseType = {
        'hasMany': 'belongsTo',
        'hasOne': 'belongsTo',
        'belongsTo': 'hasOne',
        'belongsToMany': 'belongsToMany'
    }[methodName];

    if (inverseType) {
        associations.push({
            line: line + 1,
            source_model: targetModel,    // ✅ Swapped
            target_model: sourceModel,    // ✅ Swapped
            relationship_type: inverseType,
            foreign_key: foreignKey || null,
            cascade_delete: false,  // Inverse usually doesn't cascade
            as_name: null  // Would need backref parsing for accurate name
        });
    }
}
```

---

## TRACK 2: Python Fixes (AI-2)

### Fix 5.1: TypeScript Parameter Unwrapping
**File**: `theauditor/ast_extractors/typescript_impl.py` (multiple locations)

**BEFORE (DEFENSIVE)**:
```python
# Lines vary - appears 3+ times
for param in param_nodes:
    if isinstance(param, dict):
        param_name = param.get("name")
        if isinstance(param_name, dict):
            # ❌ DEFENSIVE: Unwrapping at wrong layer
            param_text = param_name.get("text", "")
            if param_text:
                params.append(param_text)
        elif isinstance(param_name, str):
            params.append(param_name)
```

**AFTER (PROPER UNWRAPPING)**:
```python
# Fix at extraction time, not with defensive code
def _unwrap_param_name(param_node):
    """Properly unwrap parameter name from AST node."""
    if isinstance(param_node, str):
        return param_node

    if isinstance(param_node, dict):
        # Check for direct name field
        if 'name' in param_node:
            name = param_node['name']
            # Recursively unwrap if nested
            if isinstance(name, dict) and 'text' in name:
                return name['text']
            elif isinstance(name, str):
                return name
        # Check for text field directly
        elif 'text' in param_node:
            return param_node['text']

    # If we can't unwrap, it's a bug in extraction
    raise ValueError(f"Cannot unwrap parameter: {param_node}")

# Then use it:
for param in param_nodes:
    param_name = _unwrap_param_name(param)  # ✅ Proper unwrapping
    params.append(param_name)
```

### Fix 6.1-6.2: Python ORM Dedup Keys
**File**: `theauditor/ast_extractors/python/framework_extractors.py:220,415`

**VERIFY CURRENT KEYS MATCH DB CONSTRAINTS**:
```python
# SQLAlchemy - Line 220
# Current key format - VERIFY this matches DB unique constraint:
seen_relationships: Set[Tuple[str, str, str]] = set()
# Should be: (line, source_model, target_model, rel_type) to match DB

# Django - Line 415
# Current key format - VERIFY:
seen_relationships: Set[Tuple[int, str, str, str]] = set()
# This looks correct: (line, source, target, type)

# Usage at Line 350-362
key = (rel_line, source_model, target_name, rel_type)
# ✅ This matches the DB constraint: (file, line, source_model, target_model)
```

### Fix 7.1-7.4: Remove Storage Defensive Code
**File**: `theauditor/indexer/storage.py`

**BEFORE (DEFENSIVE)**:
```python
# Line 432-437
param_name = call.get('param_name', '')
if isinstance(param_name, dict):
    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] WARNING: param_name is dict in {file_path}: {param_name}")
    param_name = str(param_name)  # ❌ DEFENSIVE: Converts dict to string
```

**AFTER (HARD FAIL)**:
```python
# Line 432-437
param_name = call.get('param_name', '')
if not isinstance(param_name, str):
    # ✅ HARD FAIL with actionable error
    raise TypeError(
        f"EXTRACTION BUG: param_name must be string, got {type(param_name).__name__} "
        f"in {file_path}:{call.get('line', '?')}. "
        f"Value: {param_name!r}. "
        f"Check extractors for this file type."
    )
```

**SAME PATTERN FOR ALL DEFENSIVE CODE**:
```python
# Line 427-430 (callee_file_path)
if not isinstance(callee_file_path, (str, type(None))):
    raise TypeError(f"EXTRACTION BUG: callee_file_path must be string or None")

# Line 1155-1160 (param_names)
if not isinstance(param_names, list):
    raise TypeError(f"EXTRACTION BUG: param_names must be list")
for pn in param_names:
    if not isinstance(pn, str):
        raise TypeError(f"EXTRACTION BUG: param_names items must be strings")
```

---

## TRACK 3: Validation (After 1&2)

### Test Script for Validation
**File**: Create `test_extraction_quality.py`

```python
#!/usr/bin/env python
"""Test that all extraction fixes are working correctly."""

import sqlite3
import sys
from pathlib import Path

def test_extraction_quality():
    """Verify all extraction data quality fixes."""
    db_path = Path('.pf/repo_index.db')
    if not db_path.exists():
        print("ERROR: Run 'aud index' first")
        return False

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    tests_passed = True

    # Test 1: No dict param_names
    print("\n=== Test 1: Checking param_name types ===")
    c.execute("""
        SELECT file, line, param_name
        FROM function_call_args
        WHERE param_name LIKE '{%' OR param_name LIKE '<%'
        LIMIT 10
    """)
    dict_params = c.fetchall()
    if dict_params:
        print(f"❌ FAILED: Found {len(dict_params)} dict param_names:")
        for row in dict_params[:3]:
            print(f"  {row[0]}:{row[1]} -> {row[2][:50]}")
        tests_passed = False
    else:
        print("✅ PASSED: All param_names are strings")

    # Test 2: No duplicate ORM relationships
    print("\n=== Test 2: Checking ORM relationship duplicates ===")
    c.execute("""
        SELECT file, source_model, target_model, relationship_type, COUNT(*) as cnt
        FROM orm_relationships
        GROUP BY file, source_model, target_model, relationship_type
        HAVING cnt > 1
    """)
    duplicates = c.fetchall()
    if duplicates:
        print(f"❌ FAILED: Found {len(duplicates)} duplicate relationships:")
        for row in duplicates[:3]:
            print(f"  {row[1]} -> {row[2]} ({row[3]}): {row[4]} copies")
        tests_passed = False
    else:
        print("✅ PASSED: No duplicate ORM relationships")

    # Test 3: Bidirectional relationships exist
    print("\n=== Test 3: Checking bidirectional relationships ===")
    c.execute("""
        SELECT DISTINCT source_model, target_model, relationship_type
        FROM orm_relationships
        WHERE relationship_type IN ('hasMany', 'hasOne', 'belongsTo')
    """)
    forward_rels = c.fetchall()
    missing_inverse = []
    for source, target, rel_type in forward_rels:
        inverse_type = {
            'hasMany': 'belongsTo',
            'hasOne': 'belongsTo',
            'belongsTo': 'hasOne'
        }.get(rel_type, rel_type)

        c.execute("""
            SELECT COUNT(*) FROM orm_relationships
            WHERE source_model = ? AND target_model = ?
            AND relationship_type = ?
        """, (target, source, inverse_type))

        if c.fetchone()[0] == 0:
            missing_inverse.append((source, target, rel_type))

    if missing_inverse:
        print(f"❌ FAILED: Missing {len(missing_inverse)} inverse relationships:")
        for source, target, rel_type in missing_inverse[:3]:
            print(f"  {source} -> {target} ({rel_type}) has no inverse")
        tests_passed = False
    else:
        print("✅ PASSED: All relationships are bidirectional")

    # Test 4: GraphQL params are strings
    print("\n=== Test 4: Checking GraphQL resolver params ===")
    c.execute("""
        SELECT COUNT(*) FROM graphql_resolver_params
        WHERE param_name LIKE '{%' OR param_name LIKE '[%'
    """)
    bad_graphql = c.fetchone()[0]
    if bad_graphql > 0:
        print(f"❌ FAILED: Found {bad_graphql} malformed GraphQL params")
        tests_passed = False
    else:
        print("✅ PASSED: All GraphQL params are clean")

    conn.close()

    if tests_passed:
        print("\n🎉 ALL TESTS PASSED - Extraction quality is good!")
        return True
    else:
        print("\n❌ SOME TESTS FAILED - Review fixes above")
        return False

if __name__ == "__main__":
    sys.exit(0 if test_extraction_quality() else 1)
```

**RUN AFTER ALL FIXES**:
```bash
# Full reindex with debug
THEAUDITOR_DEBUG=1 .venv/Scripts/python.exe -m theauditor.cli index

# Run quality tests
.venv/Scripts/python.exe test_extraction_quality.py
```

---

## Success Criteria

1. **No dict warnings**: `grep "param_name is dict"` returns nothing
2. **No duplicates**: ORM relationships have unique keys
3. **Bidirectional**: Every hasMany has a belongsTo inverse
4. **Hard failures**: Storage.py raises TypeError on bad data
5. **Clean database**: test_extraction_quality.py shows all green

## Common Pitfalls

1. **Don't forget imports**: If adding Set() in JavaScript, no import needed
2. **Match Python format**: Dedup key must match Python's format exactly
3. **Test incrementally**: Fix one extractor, test it, then move on
4. **Check fixtures**: Use test fixtures to validate each fix

## Rollback Plan

If something breaks:
```bash
# Revert all changes
git checkout -- theauditor/ast_extractors/javascript/
git checkout -- theauditor/ast_extractors/python/
git checkout -- theauditor/indexer/storage.py

# Reindex with old code
.venv/Scripts/python.exe -m theauditor.cli index
```