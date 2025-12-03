## Why

Go graph strategies (`GoHttpStrategy`, `GoOrmStrategy`) were implemented during the `add-go-support` change (archived 2025-11-30) but **never wired to DFGBuilder**. This means:

- Go HTTP middleware chains (Gin, Echo, Fiber, Chi) are NOT in the unified data flow graph
- Go ORM relationships (GORM, SQLx, Ent) are NOT in the unified data flow graph
- `aud graph query` returns incomplete results for Go codebases
- Taint analysis cannot follow Go HTTP request flow or ORM relationships

This is a 2-line import + 2-line list entry fix. The strategies are fully implemented and tested - they just need to be wired.

## What Changes

> **Specs**: This proposal is governed by `specs/graph/spec.md`

**Single file change**: `theauditor/graph/dfg_builder.py`

1. Add 2 import statements (lines 13-17)
2. Add 2 strategy instances to `self.strategies` list (lines 30-36)

That's it. No new files. No schema changes. No breaking changes.

## Impact

- **Affected specs**: `graph` - Wiring existing strategies

- **Affected code**:
  - `theauditor/graph/dfg_builder.py:13-17` - Add 2 imports
  - `theauditor/graph/dfg_builder.py:30-36` - Add 2 list entries

- **Breaking changes**: None (additive only)

- **Dependencies**: None (go_http.py and go_orm.py already exist)

- **Estimated effort**: 5 minutes

- **Risk level**: LOW
  - Strategies already implemented and follow existing interface
  - If `go_middleware`, `go_routes`, or `go_struct_fields` tables are empty, strategies return empty results gracefully
  - No fallback logic (ZERO FALLBACK compliant)

## Implementation Details

### CHANGE 1: Add Go strategy imports

**Location**: `theauditor/graph/dfg_builder.py:13-17`

**Before**:
```python
from .strategies.bash_pipes import BashPipeStrategy
from .strategies.interceptors import InterceptorStrategy
from .strategies.node_express import NodeExpressStrategy
from .strategies.node_orm import NodeOrmStrategy
from .strategies.python_orm import PythonOrmStrategy
```

**After**:
```python
from .strategies.bash_pipes import BashPipeStrategy
from .strategies.go_http import GoHttpStrategy
from .strategies.go_orm import GoOrmStrategy
from .strategies.interceptors import InterceptorStrategy
from .strategies.node_express import NodeExpressStrategy
from .strategies.node_orm import NodeOrmStrategy
from .strategies.python_orm import PythonOrmStrategy
```

### CHANGE 2: Register Go strategy instances

**Location**: `theauditor/graph/dfg_builder.py:30-36`

**Before**:
```python
self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    InterceptorStrategy(),
    BashPipeStrategy(),
]
```

**After**:
```python
self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    InterceptorStrategy(),
    BashPipeStrategy(),
    GoHttpStrategy(),
    GoOrmStrategy(),
]
```

## Verification

After implementation:

```bash
# Rebuild index with Go codebase
aud full --offline

# Verify Go strategies executed
aud graph query --type data_flow | grep "go_"
```

Expected: Go HTTP middleware chains and ORM relationships appear in graph output.

## Reversion Plan

- **Reversibility**: Fully reversible
- **Steps**: Remove 2 import lines and 2 list items from dfg_builder.py
