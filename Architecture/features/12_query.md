# TheAuditor Query Engines

## Overview

TheAuditor provides two complementary **database-first query engines** that replace traditional file-based code navigation:

1. **CodeQueryEngine** - Direct code structure queries
2. **FCEQueryEngine** - Vector-based convergence analysis

**Philosophy**: "I am not the judge, I am the evidence locker."

---

## Why Database-First?

### Traditional Approach (Abandoned)
```
User asks question → Read files → Parse ASTs → Traverse → Return (seconds-minutes)
```

### TheAuditor Approach
```
aud full → Parse once → Store in SQLite → Query instantly (milliseconds)
```

**Advantages**:
- Instant queries (all relationships pre-computed)
- No re-parsing
- Cross-tool correlation
- PRAGMA optimizations (WAL mode, 64MB cache)
- Recursive CTEs for complex traversals

---

## CodeQueryEngine

**Location**: `theauditor/context/query.py`
**Purpose**: Query code structure relationships

### Key Methods

| Method | Purpose |
|--------|---------|
| `find_symbol()` | Symbol definitions by name |
| `get_callers()` | Who calls this (transitive via CTE) |
| `get_callees()` | What this calls |
| `get_file_dependencies()` | Import relationships |
| `trace_variable_flow()` | Def-use chains via BFS |
| `get_api_security_coverage()` | API endpoints + auth controls |
| `get_component_tree()` | React component hierarchy |

### Symbol Resolution Strategy

```
Priority 1: Exact match
Priority 2: Suffix match (%.methodName)
Priority 3: Last segment match
Priority 4: Argument expressions
```

Single UNION query instead of 12-18 separate queries.

### Recursive CTEs for Call Graphs

```sql
WITH RECURSIVE caller_graph AS (
    -- BASE: Direct callers
    SELECT ... FROM function_call_args WHERE callee = ?
    UNION ALL
    -- RECURSIVE: Callers of callers
    SELECT ... FROM function_call_args
    JOIN caller_graph ON callee = caller
    WHERE depth < max_depth
)
```

**Performance**: O(1) queries vs O(depth × symbols)

---

## FCEQueryEngine

**Location**: `theauditor/fce/query.py`
**Purpose**: Identify where multiple analysis vectors converge

### Four Vectors

| Vector | Source |
|--------|--------|
| STATIC | Linters (ESLint, Ruff) |
| STRUCTURAL | CFG complexity |
| PROCESS | Code churn |
| FLOW | Taint propagation |

### Vector Density

```python
VectorSignal:
    file_path: str
    vectors_present: set[Vector]
    density: float  # 0.0 - 1.0
```

**Interpretation**:
- 1 vector = single tool says risk
- 2 vectors = independent tools agree (stronger)
- 3+ vectors = high-confidence convergence

---

## CLI: `aud query`

### Query Targets
```bash
--symbol NAME       # Function/class lookup
--file PATH         # File dependencies
--api ROUTE         # API endpoint handler
--component NAME    # React/Vue component
--variable NAME     # Variable data flow
--pattern PATTERN   # SQL LIKE search
```

### Action Flags
```bash
--show-callers      # Who calls this?
--show-callees      # What does this call?
--show-dependencies # What does file import?
--show-dependents   # Who imports file?
--show-flow         # Variable def-use chains
--show-taint-flow   # Cross-function taint
```

### Examples

```bash
# Find callers recursively
aud query --symbol validateUser --show-callers --depth 3

# List functions in file
aud query --file src/auth.ts --list functions

# API endpoint handler
aud query --api "/users/:id"

# Variable flow trace
aud query --variable userToken --show-flow --depth 3

# Search by security category
aud query --category jwt --format json
```

---

## Q Query Builder

**Location**: `theauditor/rules/query.py`
**Purpose**: Composable SQL builder with validation

```python
# Build query
sql, params = Q("symbols")\
    .select("name", "line")\
    .where("type = ?", "function")\
    .where("path LIKE ?", "%auth%")\
    .build()

# With CTE
tainted = Q("assignments").select("file", "target_var").where("source_expr LIKE ?", "%request%")
sql, params = Q("function_call_args")\
    .with_cte("tainted_vars", tainted)\
    .join("tainted_vars", on=[("file", "file")])\
    .build()
```

---

## Performance Benefits

| Operation | Traditional | Database-First |
|-----------|-------------|----------------|
| Symbol resolution | 18 queries | 1 UNION query |
| Call graph (depth 3) | 50-100 queries | 1 recursive CTE |
| Vector density (10K files) | 40K queries | 2 queries |

**Result**: 10-60x faster, sub-second all queries
