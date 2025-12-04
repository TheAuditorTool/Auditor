## Context

Go graph strategies (`GoHttpStrategy`, `GoOrmStrategy`) were implemented during the `add-go-support` change (2025-11-30) but never wired to the DFG builder. This is a wiring-only fix - no new code, no new architecture.

## Goals / Non-Goals

**Goals:**
- Wire existing GoHttpStrategy to DFGBuilder
- Wire existing GoOrmStrategy to DFGBuilder
- Enable Go HTTP middleware chains in unified data flow graph
- Enable Go ORM relationships in unified data flow graph

**Non-Goals:**
- Modifying strategy implementations (already complete)
- Adding new tables or schema changes
- Adding new extraction logic
- Anything beyond 2 imports + 2 list entries

## Decisions

### Decision 1: Import ordering

**Choice**: Alphabetical order after existing imports.

**Rationale**: Maintains consistency with existing import style in dfg_builder.py.

**Implementation**:
```python
from .strategies.bash_pipes import BashPipeStrategy
from .strategies.go_http import GoHttpStrategy      # NEW
from .strategies.go_orm import GoOrmStrategy        # NEW
from .strategies.interceptors import InterceptorStrategy
from .strategies.node_express import NodeExpressStrategy
from .strategies.node_orm import NodeOrmStrategy
from .strategies.python_orm import PythonOrmStrategy
```

### Decision 2: Strategy list ordering

**Choice**: Append Go strategies at end of list.

**Rationale**: Order doesn't affect execution - all strategies run and results are merged. Appending is least invasive.

**Implementation**:
```python
self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    InterceptorStrategy(),
    BashPipeStrategy(),
    GoHttpStrategy(),   # NEW
    GoOrmStrategy(),    # NEW
]
```

### Decision 3: ZERO FALLBACK compliance

**Choice**: No special error handling added.

**Rationale**:
1. Go strategies already handle empty tables gracefully (return empty nodes/edges)
2. dfg_builder.py:614-615 already documents: "ZERO FALLBACK: Strategy failures must CRASH"
3. Adding try-except would violate project policy

**Implementation**: None needed - existing code is already compliant.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Go tables don't exist | Strategies query tables - if missing, SQLite returns empty results |
| Strategy crashes on malformed data | Let it crash per ZERO FALLBACK - exposes bugs |
| Performance impact | Negligible - 2 additional O(n) iterations |

## Migration Plan

1. Add 2 import lines
2. Add 2 list entries
3. Run `aud full --offline` to verify
4. Done

No migration needed - purely additive change.
