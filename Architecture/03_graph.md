# TheAuditor Graph Engine

## Overview

A multi-layer dependency analysis system constructing and analyzing **4 graph types**:

1. **Import Graph** - File/module-level dependencies
2. **Call Graph** - Function-level call relationships
3. **CFG (Control Flow Graph)** - Execution paths within functions
4. **DFG (Data Flow Graph)** - Variable and data flow relationships

**Key Stats:**
- Main builder: `builder.py` (1125 lines)
- 9 specialized DFG strategies for ORM/middleware patterns
- Lazy-loading cache with bounded LRU (2K imports, 2K exports, 5K resolve)
- Bidirectional edges for IFDS backward traversal (G3 fix)

---

## Graph Types

### Import Graph
```python
# Nodes: {"id": "file.py", "type": "module", "lang": "python"}
# Edges: {"source": "a.py", "target": "b.py", "type": "import"}
```
- Internal vs external module distinction
- Language-aware resolution (Python relative imports, JS tsconfig)

### Call Graph
```python
# Nodes: {"id": "file.py::function_name", "type": "function"}
# Edges: {"source": "caller", "target": "callee", "type": "call"}
```
- Resolution status: local_def, imported_def, ambiguous, unresolved

### Control Flow Graph (CFG)
- Block types: entry, exit, condition, loop_condition, normal, try
- Edge types: fall_through, true, false, back_edge
- Analytics: cyclomatic complexity, max nesting, dead code detection

### Data Flow Graph (DFG)
- Assignment flow: Variable → Variable through assignments
- Return flow: Function return values
- **9 pluggable strategies** for framework-specific edges

---

## Key Algorithms

### Cycle Detection (Iterative DFS)
```python
def detect_cycles(graph: dict) -> list[dict]:
    # Filter out _reverse edges (G3 fix)
    for edge in graph["edges"]:
        if edge.get("type", "").endswith("_reverse"):
            continue
    # Iterative DFS with path tracking...
```

### Impact Analysis (Bidirectional BFS)
```python
def impact_of_change(targets, import_graph, call_graph, max_depth=3):
    # Upstream: Who depends on me? (files that break if I change)
    # Downstream: What do I depend on? (files my changes might affect)
    return {"upstream": set, "downstream": set, "total_impacted": int}
```

### Hotspot Detection (Degree Centrality)
- Ranks nodes by in_degree + out_degree
- High-degree nodes = architectural hubs requiring careful modification

---

## Key Fixes

| Fix | Problem | Solution |
|-----|---------|----------|
| **G3** | IFDS needs reverse edges for backward traversal | Create bidirectional edges: forward + `*_reverse` |
| **G7** | Cache corruption from consumer modifications | Use `MappingProxyType` for immutable cached dicts |
| **G13/G14** | Path format mismatches (./ vs \\) | Normalize to forward-slash format everywhere |

---

## Database Caching (Phase 0.2)

**Problem**: Eager loading of 500K+ rows exhausts memory

**Solution**: Lazy-loading LRU cache
```python
class GraphDatabaseCache:
    IMPORTS_CACHE_SIZE = 2000
    EXPORTS_CACHE_SIZE = 2000
    RESOLVE_CACHE_SIZE = 5000

    @lru_cache(maxsize=IMPORTS_CACHE_SIZE)
    def get_imports(self, file_path: str) -> tuple[MappingProxyType, ...]:
        # Returns immutable proxies (G7 fix)
```

**Memory Impact**:
- Old: 500K+ rows loaded
- New: Only file list loaded eagerly; imports/exports on demand

---

## DFG Strategies

| Strategy | Purpose | Language |
|----------|---------|----------|
| `PythonOrmStrategy` | SQLAlchemy, Django ORM | Python |
| `NodeOrmStrategy` | Prisma, TypeORM | Node.js |
| `NodeExpressStrategy` | Middleware chains | Node.js/Express |
| `GoHttpStrategy` | HTTP handler patterns | Go |
| `RustTraitStrategy` | Trait implementations | Rust |
| `BashPipeStrategy` | Pipe chains | Bash |
| `InterceptorStrategy` | HTTP interceptor chains | Cross-language |

---

## Storage Schema (graphs.db)

```sql
TABLE nodes:
  id TEXT PRIMARY KEY,
  file TEXT,
  lang TEXT,
  type TEXT,          -- "module", "function", "variable"
  graph_type TEXT,    -- "import", "call", "data_flow"
  metadata JSON

TABLE edges:
  source TEXT,
  target TEXT,
  type TEXT,          -- "import", "call", "assignment", "*_reverse"
  graph_type TEXT,
  metadata JSON
```

---

## Performance

| Size | Time | Memory |
|------|------|--------|
| 100 files | 2-5s | ~150MB |
| 500 files | 10-20s | ~300MB |
| 2K+ files | 30-60s | ~500MB |
