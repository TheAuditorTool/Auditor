# Object Literals Fixture

## Purpose
Tests JavaScript object literal extraction across various syntactic patterns.

Validates that TheAuditor correctly populates `object_literal_properties` table with function references, shorthand properties, computed keys, nested objects, and edge cases.

## File Breakdown

### basic_patterns.js (35 lines)
**Patterns Tested**:
- Simple function references: `{ create: handleCreate }`
- Shorthand properties: `{ handleClick }` (ES6)
- Mixed literals and references: `{ timeout: 5000, handler: processRequest }`
- Arrow functions: `{ validate: (data) => data.length > 0 }`
- Function expressions: `{ process: function(data) { } }`

**Expected Extraction**: 15+ object literal properties

### edge_cases.js (40 lines)
**Patterns Tested**:
- ES6 method definitions: `{ async fetch() { }, getValue() { } }`
- Spread operators: `{ ...base, handler: handleExtended }`
- Computed property names: `{ [key]: value, ['literal']: literalValue }`
- String literals with commas: `{ message: "Hello, world!" }`
- Empty objects: `{}`
- Assignment expressions: `mutableHandlers = { add: addHandler }`

**Expected Extraction**: 18+ object literal properties

### nested_objects.js (26 lines)
**Patterns Tested**:
- Nested object hierarchies: `{ api: { users: { create: createUser } } }`
- Mixed nesting levels: 3-level deep objects
- Multiple keys at each level

**Expected Extraction**: 10+ object literal properties with nesting

### function_context.js (28 lines)
**Patterns Tested**:
- Object literals inside functions
- Object literals as return values
- Object literals as function parameters
- Default parameters with object literals

**Expected Extraction**: 12+ object literal properties in function contexts

## Populated Database Tables

After `aud index`:

| Table | Expected Count | What It Tests |
|---|---|---|
| **object_literal_properties** | 55+ | All object property extractions |
| **symbols** | 30+ | Function/variable symbols |
| **assignments** | 13+ | Object literal assignments |

## Sample Verification Queries

### Query 1: Find All Object Literal Properties

```sql
SELECT
    object_name,
    key,
    value,
    file
FROM object_literal_properties
WHERE file LIKE '%object_literals%'
ORDER BY file, object_name, key;
```

**Expected Results**: 55+ properties across 4 files

### Query 2: Find Function Reference Properties

```sql
SELECT
    object_name,
    key,
    value
FROM object_literal_properties
WHERE file LIKE '%object_literals%'
  AND value LIKE '%Handler%'
  OR value LIKE '%handle%'
ORDER BY object_name;
```

**Expected Results**: Properties like `{ create: handleCreate }`, `{ handleClick }`, etc.

### Query 3: Find Shorthand Properties (ES6)

```sql
SELECT
    object_name,
    key,
    value
FROM object_literal_properties
WHERE file LIKE '%object_literals%'
  AND key = value
ORDER BY object_name;
```

**Expected Results**: Shorthand properties like `{ handleClick }` where key equals value

### Query 4: Find Nested Object Properties

```sql
SELECT
    object_name,
    key,
    value,
    nesting_level
FROM object_literal_properties
WHERE file LIKE '%object_literals/nested_objects.js'
ORDER BY nesting_level DESC, object_name;
```

**Expected Results**: Properties at nesting levels 1, 2, and 3

### Query 5: Find Computed Property Names

```sql
SELECT
    object_name,
    key,
    value
FROM object_literal_properties
WHERE file LIKE '%object_literals/edge_cases.js'
  AND (key LIKE '[%' OR key = 'dynamicKey')
ORDER BY key;
```

**Expected Results**: Computed properties like `[key]`, `['literal']`

## Testing Use Cases

This fixture enables testing:

1. **Basic Object Literal Extraction**: Verify simple `{ key: value }` patterns
2. **ES6 Syntax Support**: Shorthand properties, method definitions, spread operators
3. **Computed Keys**: Dynamic property names `[expr]`
4. **Nested Objects**: Multi-level object hierarchies
5. **Edge Cases**: Empty objects, string literals with commas, assignment vs declaration
6. **Function Contexts**: Object literals inside functions, as returns, as parameters

## Expected Schema Population

When this fixture is indexed, expect:

- ✅ **55+ object literal properties** extracted
- ✅ **Function references** tracked (handleCreate, handleUpdate, etc.)
- ✅ **Shorthand properties** identified (ES6 syntax)
- ✅ **Nested objects** with correct nesting levels
- ✅ **Computed property names** extracted
- ✅ **Arrow functions** and method definitions in objects
- ✅ **Spread operators** handled correctly

## How to Use

1. **Index from TheAuditor root**:
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index
   ```

2. **Query object literals**:
   ```sql
   SELECT * FROM object_literal_properties
   WHERE file LIKE '%object_literals%';
   ```

3. **Verify specific patterns**:
   ```bash
   aud context query --file basic_patterns.js
   ```

## Why This Fixture Matters

JavaScript object literals are ubiquitous in:
- React component props: `<Button onClick={handleClick} />`
- Redux action creators: `{ type: 'ADD_USER', payload: user }`
- Express route handlers: `{ GET: getUsers, POST: createUser }`
- Configuration objects: `{ timeout: 5000, retry: true }`

Accurate extraction of object literal properties enables:
- Tracking function references across the codebase
- Understanding data flow through configuration objects
- Finding unused handlers or missing implementations
- Validating required properties are set

## Coverage Summary

| Pattern | File | Lines | Status |
|---|---|---|---|
| Function references | basic_patterns.js | 1-6 | ✅ |
| Shorthand properties | basic_patterns.js | 8-13 | ✅ |
| Mixed literals | basic_patterns.js | 15-22 | ✅ |
| Arrow functions | basic_patterns.js | 24-29 | ✅ |
| Function expressions | basic_patterns.js | 31-35 | ✅ |
| ES6 methods | edge_cases.js | 1-7 | ✅ |
| Spread operators | edge_cases.js | 9-15 | ✅ |
| Computed keys | edge_cases.js | 17-23 | ✅ |
| String edge cases | edge_cases.js | 25-30 | ✅ |
| Empty objects | edge_cases.js | 32-33 | ✅ |
| Assignment exprs | edge_cases.js | 35-40 | ✅ |
| Nested objects | nested_objects.js | 1-15 | ✅ |
| Mixed nesting | nested_objects.js | 17-26 | ✅ |
| Function context | function_context.js | all | ✅ |

**Total**: 130 lines covering 14 distinct object literal patterns
