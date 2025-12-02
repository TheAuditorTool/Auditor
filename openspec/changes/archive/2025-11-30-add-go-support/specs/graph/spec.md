# Go Graph Strategies Specification

## Overview

This spec defines two Go-specific graph strategies for data flow analysis:
1. **GoHttpStrategy** - Tracks data flow through HTTP handlers and middleware chains
2. **GoOrmStrategy** - Tracks data flow through GORM/sqlx ORM relationships

Graph strategies enable cross-function data flow analysis. Without them, taint analysis cannot track data through HTTP handlers or ORM operations.

## Architecture Context

```
repo_index.db (go_* tables populated by indexer)
       |
       v Reads normalized data
       |
graph/strategies/go_http.py     <-- NEW
graph/strategies/go_orm.py      <-- NEW
       |
       v Produces DFG nodes/edges
       |
graph/dfg_builder.py            <-- Add Go strategies to self.strategies list
       |
       v Stores in graphs.db
       |
graphs.db
```

## Reference Patterns

| Go Strategy | Reference Pattern | What to Copy |
|-------------|-------------------|--------------|
| GoHttpStrategy | `graph/strategies/node_express.py` | Middleware chain + controller flow |
| GoOrmStrategy | `graph/strategies/python_orm.py` | ORM context + relationship expansion |
| Base class | `graph/strategies/base.py` | GraphStrategy abstract class |

## Strategy 1: GoHttpStrategy

### Purpose
Track data flow through Go HTTP handlers and middleware chains for:
- Gin, Echo, Fiber, Chi frameworks
- net/http standard library
- Custom middleware

### Input Tables
- `go_routes` - Route definitions (file, line, framework, method, path, handler_func)
- `go_middleware` - Middleware registrations (file, line, framework, router_var, middleware_func, is_global)
- `go_func_params` - Handler function parameters

### Output
DFG edges representing:
1. **Request flow**: HTTP request -> middleware chain -> handler
2. **Middleware chain**: middleware1 -> middleware2 -> ... -> handler
3. **Context propagation**: gin.Context / echo.Context passed through chain

### Implementation

```python
# graph/strategies/go_http.py
"""Go HTTP Strategy - Handles net/http and framework middleware chains."""

import sqlite3
from pathlib import Path
from typing import Any

from .base import GraphStrategy
from ..types import DFGEdge, DFGNode, create_bidirectional_edges


class GoHttpStrategy(GraphStrategy):
    """Strategy for building Go HTTP handler data flow edges."""

    name = "go_http"
    priority = 50  # After Python/Node strategies

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Go HTTP handlers and middleware."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        # 1. Load routes
        cursor.execute("""
            SELECT file, line, framework, method, path, handler_func
            FROM go_routes
            ORDER BY file, line
        """)
        routes = cursor.fetchall()

        # 2. Load middleware
        cursor.execute("""
            SELECT file, line, framework, router_var, middleware_func, is_global
            FROM go_middleware
            ORDER BY file, line
        """)
        middlewares = cursor.fetchall()

        # 3. Build middleware chains per file/framework
        middleware_chains = self._build_middleware_chains(middlewares)

        # 4. Create nodes for routes
        for route in routes:
            route_id = f"{route['file']}::{route['handler_func']}"
            nodes[route_id] = DFGNode(
                id=route_id,
                file=route["file"],
                variable_name=route["handler_func"],
                scope="http_handler",
                type="handler",
                metadata={
                    "framework": route["framework"],
                    "method": route["method"],
                    "path": route["path"],
                    "line": route["line"],
                },
            )

            # 5. Create edges from middleware to handler
            chain_key = (route["file"], route["framework"])
            if chain_key in middleware_chains:
                for mw in middleware_chains[chain_key]:
                    mw_id = f"{route['file']}::{mw['middleware_func']}"
                    if mw_id not in nodes:
                        nodes[mw_id] = DFGNode(
                            id=mw_id,
                            file=route["file"],
                            variable_name=mw["middleware_func"],
                            scope="middleware",
                            type="middleware",
                            metadata={"is_global": mw["is_global"]},
                        )

                    # Edge from middleware to handler
                    edges.extend(
                        create_bidirectional_edges(
                            source=mw_id,
                            target=route_id,
                            edge_type="middleware_chain",
                            file=route["file"],
                            line=route["line"],
                        )
                    )

        conn.close()

        return {
            "nodes": [n.__dict__ for n in nodes.values()],
            "edges": [e.__dict__ for e in edges],
            "metadata": {
                "strategy": self.name,
                "routes_processed": len(routes),
                "middlewares_processed": len(middlewares),
            },
        }

    def _build_middleware_chains(
        self, middlewares: list
    ) -> dict[tuple[str, str], list[dict]]:
        """Group middleware by file and framework."""
        chains: dict[tuple[str, str], list[dict]] = {}
        for mw in middlewares:
            key = (mw["file"], mw["framework"])
            if key not in chains:
                chains[key] = []
            chains[key].append(dict(mw))
        return chains
```

### Query Patterns

```sql
-- Find all middleware protecting a route
SELECT m.middleware_func, r.path, r.method
FROM go_middleware m
JOIN go_routes r ON m.file = r.file AND m.framework = r.framework
WHERE r.path = '/api/users'
  AND m.is_global = 1
ORDER BY m.line;

-- Find unprotected routes (no auth middleware)
SELECT r.path, r.method, r.handler_func
FROM go_routes r
WHERE r.file NOT IN (
    SELECT DISTINCT file FROM go_middleware
    WHERE middleware_func LIKE '%auth%'
);
```

---

## Strategy 2: GoOrmStrategy

### Purpose
Track data flow through Go ORM relationships for:
- GORM (gorm.io/gorm)
- sqlx (github.com/jmoiron/sqlx)
- ent (entgo.io/ent)

### Input Tables
- `go_structs` - Model definitions
- `go_struct_fields` - Field definitions with tags
- `go_imports` - To detect ORM framework

### Output
DFG edges representing:
1. **Relationship edges**: User -> Posts (has_many), Post -> User (belongs_to)
2. **Eager loading**: Preload chains
3. **Database flow**: Model -> db.Query -> Result

### Implementation

```python
# graph/strategies/go_orm.py
"""Go ORM Strategy - Handles GORM/sqlx relationship expansion."""

import re
import sqlite3
from pathlib import Path
from typing import Any

from .base import GraphStrategy
from ..types import DFGEdge, DFGNode


class GoOrmStrategy(GraphStrategy):
    """Strategy for building Go ORM relationship edges."""

    name = "go_orm"
    priority = 51  # After GoHttpStrategy

    # GORM tag patterns
    GORM_RELATIONSHIP_PATTERNS = [
        r"belongsTo",
        r"hasOne",
        r"hasMany",
        r"many2many",
        r"foreignKey:(\w+)",
        r"references:(\w+)",
    ]

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Go ORM relationships."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        # 1. Find files with GORM import
        cursor.execute("""
            SELECT DISTINCT file
            FROM go_imports
            WHERE path LIKE '%gorm.io/gorm%'
               OR path LIKE '%github.com/jmoiron/sqlx%'
               OR path LIKE '%entgo.io/ent%'
        """)
        orm_files = {row["file"] for row in cursor.fetchall()}

        if not orm_files:
            conn.close()
            return {"nodes": [], "edges": [], "metadata": {"strategy": self.name}}

        # 2. Load structs from ORM files
        placeholders = ",".join("?" * len(orm_files))
        cursor.execute(
            f"""
            SELECT file, name, line
            FROM go_structs
            WHERE file IN ({placeholders})
            """,
            list(orm_files),
        )
        structs = cursor.fetchall()

        # 3. Create nodes for models
        for struct in structs:
            model_id = f"{struct['file']}::{struct['name']}"
            nodes[model_id] = DFGNode(
                id=model_id,
                file=struct["file"],
                variable_name=struct["name"],
                scope="model",
                type="orm_model",
                metadata={"line": struct["line"]},
            )

        # 4. Load struct fields with tags
        cursor.execute(
            f"""
            SELECT file, struct_name, field_name, field_type, tag
            FROM go_struct_fields
            WHERE file IN ({placeholders})
              AND tag IS NOT NULL
              AND tag != ''
            """,
            list(orm_files),
        )
        fields = cursor.fetchall()

        # 5. Parse relationship tags and create edges
        for field in fields:
            tag = field["tag"] or ""
            relationships = self._parse_gorm_tag(tag)

            if relationships:
                source_id = f"{field['file']}::{field['struct_name']}"
                target_type = field["field_type"].replace("[]", "").replace("*", "")
                target_id = f"{field['file']}::{target_type}"

                if source_id in nodes and target_id in nodes:
                    edges.append(
                        DFGEdge(
                            source=source_id,
                            target=target_id,
                            type="orm_relationship",
                            file=field["file"],
                            metadata={
                                "field": field["field_name"],
                                "relationships": relationships,
                            },
                        )
                    )

        conn.close()

        return {
            "nodes": [n.__dict__ for n in nodes.values()],
            "edges": [e.__dict__ for e in edges],
            "metadata": {
                "strategy": self.name,
                "models_found": len(structs),
                "relationships_found": len(edges),
            },
        }

    def _parse_gorm_tag(self, tag: str) -> list[str]:
        """Extract GORM relationship types from struct tag."""
        relationships = []
        gorm_match = re.search(r'gorm:"([^"]*)"', tag)
        if gorm_match:
            gorm_value = gorm_match.group(1)
            for pattern in self.GORM_RELATIONSHIP_PATTERNS:
                if re.search(pattern, gorm_value, re.IGNORECASE):
                    relationships.append(pattern.replace(r"(\w+)", ""))
        return relationships
```

### Query Patterns

```sql
-- Find all models with relationships
SELECT s.name, COUNT(sf.field_name) as relationship_count
FROM go_structs s
JOIN go_struct_fields sf ON s.file = sf.file AND s.name = sf.struct_name
WHERE sf.tag LIKE '%gorm:%'
  AND (sf.tag LIKE '%belongsTo%' OR sf.tag LIKE '%hasMany%' OR sf.tag LIKE '%hasOne%')
GROUP BY s.name;

-- Find N+1 query risks (models with hasMany but no preload)
SELECT s.name, sf.field_name, sf.field_type
FROM go_structs s
JOIN go_struct_fields sf ON s.file = sf.file AND s.name = sf.struct_name
WHERE sf.tag LIKE '%hasMany%'
  AND sf.tag NOT LIKE '%preload%';
```

---

## Registration

Add to `graph/dfg_builder.py`:

```python
# At top of file (lines 11-14)
from .strategies.go_http import GoHttpStrategy
from .strategies.go_orm import GoOrmStrategy

# In __init__ (lines 27-32)
self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    GoHttpStrategy(),      # <-- ADD
    GoOrmStrategy(),       # <-- ADD
    InterceptorStrategy(),
]
```

---

## Verification

```python
# Test strategies are registered
from theauditor.graph.dfg_builder import DFGBuilder

builder = DFGBuilder('.pf/repo_index.db')
strategy_names = [s.name for s in builder.strategies]

assert "go_http" in strategy_names, "GoHttpStrategy not registered"
assert "go_orm" in strategy_names, "GoOrmStrategy not registered"

# Test on sample project
result = builder.build_all()
print(f"Go HTTP edges: {len([e for e in result['edges'] if e.get('type') == 'middleware_chain'])}")
print(f"Go ORM edges: {len([e for e in result['edges'] if e.get('type') == 'orm_relationship'])}")
```

---

## Dependencies

- Requires Phase 1 complete (go_* tables populated)
- Requires Phase 3.1-3.4 complete (routes, middleware extraction)
- Uses existing `graph/types.py` for DFGNode/DFGEdge
- Uses existing `graph/strategies/base.py` for GraphStrategy base class

## Tasks Reference

See `tasks.md` section 3.5 for implementation tasks:
- 3.5.1.1 - 3.5.1.4: GoHttpStrategy
- 3.5.2.1 - 3.5.2.4: GoOrmStrategy
- 3.5.3.1 - 3.5.3.2: DFG Builder registration
