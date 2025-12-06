## Context

TheAuditor's taint analysis engine has evolved organically to handle Express.js projects well, but has accumulated hardcoded patterns that prevent proper polyglot support. This design document captures the architectural decisions to transform it into a true data-driven polyglot engine.

### Stakeholders
- **Architect**: Final authority on all decisions
- **AI Lead Coder (Opus)**: Implementation specialist
- **Lead Auditor (Gemini)**: Technical strategist

### Constraints
1. **ZERO FALLBACK POLICY** - No silent failures, no alternative paths
2. **Database-first architecture** - All patterns from DB tables, not hardcoded
3. **Backward compatibility** - Express detection must continue working
4. **Three languages** - Python (full), Node.js (full), Rust (basic)

---

## Goals / Non-Goals

### Goals
1. Replace ALL hardcoded language patterns with database-driven lookups
2. Create proper separation: **Graph builds roads, Registry defines destinations, Taint drives the car**
3. Support Python (Flask/Django/FastAPI), Node.js (Express/Koa/Fastify), Rust (Actix/Axum) equally
4. Enable ORM relationship expansion for Sequelize/TypeORM/Prisma (currently Python-only)
5. Provide type identity for aliasing without graph edges

### Non-Goals
1. Full Rust semantic analysis (basic support only)
2. Runtime taint tracking (static analysis only)
3. Cross-repository analysis
4. Machine learning-based pattern detection

---

## Architecture Overview

### Current State (Express-Locked)

```
                   BUILD TIME                              ANALYSIS TIME
                   ----------                              -------------
repo_index.db --> DFGBuilder                              IFDSTaintAnalyzer
                     |                                          |
                     v                                          v
              +----------------+                         +---------------+
              |   Strategies   |                         |  HARDCODED    |
              | - python_orm   |--> graphs.db edges -->  | - 'req.body'  |
              | - node_express |                         | - 'controller'|
              | - interceptors |                         | - validateBody|
              +----------------+                         +---------------+
                     |                                         |
                     v                                         v
              PythonOrmContext                          FAILS for Python
              (from taint/orm_utils.py)                 FAILS for Rust
```

**Problems:**
1. `orm_utils.py` in `taint/` but only used by graph strategy - LAYERING VIOLATION
2. No `NodeOrmStrategy` - Sequelize data orphaned in DB
3. IFDS hardcodes `'controller'`, `'req.body'` - Express-only
4. SanitizerRegistry hardcodes validation patterns - Express-only
5. No mechanism for Python's `request.form`, `request.args` patterns
6. No mechanism for Rust's `web::Json`, `web::Query` patterns

### Target State (Polyglot Ferrari)

```
                   BUILD TIME                              ANALYSIS TIME
                   ----------                              -------------
repo_index.db --> DFGBuilder                              IFDSTaintAnalyzer
                     |                                          |
                     v                                          v
              +----------------+                         +------------------+
              |   Strategies   |                         |  TaintRegistry   |
              | - python_orm   |                         | .get_sources(py) |
              | - node_orm NEW |-->  graphs.db   -->     | .get_sources(js) |
              | - node_express |     (with ORM           | .get_sources(rs) |
              | - interceptors |      edges)             +------------------+
              +----------------+                                 |
                                                                 v
                                                         +------------------+
                                                         |  TypeResolver    |
                                                         | .is_same_type()  |
                                                         | (reads metadata) |
                                                         +------------------+
```

**Key Architectural Changes:**
1. **Graph Layer** owns ALL edge building (ORM relationships, middleware chains)
2. **Registry Layer** owns ALL pattern definitions (sources, sinks, sanitizers)
3. **Taint Layer** is a DUMB WALKER - asks registry, walks graph, reports paths

---

## Decisions

### Decision 1: Delete `taint/orm_utils.py`

**What:** Remove the file entirely. Move any remaining logic to `graph/strategies/python_orm.py`.

**Why:**
- Currently imported by ONLY `graph/strategies/python_orm.py:19`
- Contains ORM context loading which is graph-building logic
- Lives in wrong layer (taint/ vs graph/)
- Vestigial after strategy refactoring

**Alternatives Considered:**
- Move to `graph/utils/orm_utils.py` - Rejected: strategy should own its helpers
- Keep and refactor - Rejected: only one consumer, consolidate instead

**Evidence:**
```bash
# Only one import exists
$ grep -r "from.*orm_utils\|import.*orm_utils" theauditor/
theauditor/graph/strategies/python_orm.py:19:from theauditor.taint.orm_utils import PythonOrmContext
```

---

### Decision 2: Create `graph/strategies/node_orm.py`

**What:** New graph strategy for Node.js ORM relationship expansion.

**Why:**
- `sequelize_models` table has 1000+ models in typical projects
- `sequelize_associations` has relationships (hasMany, belongsTo)
- NO strategy consumes this data - it's orphaned
- Python has `python_orm.py` strategy but Node has nothing

**Implementation:**
```python
# graph/strategies/node_orm.py
class NodeOrmStrategy(GraphStrategy):
    """Strategy for building Node.js ORM relationship edges.

    Handles: Sequelize, TypeORM, Prisma
    Creates edges: User.posts -> Post (ORM relationship expansion)
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        # Query sequelize_models, sequelize_associations
        # Query typeorm tables (if they exist)
        # Query prisma tables (if they exist)
        # Create DFGEdges for relationships
```

**Tables to Query:**
- `sequelize_models` - Model definitions
- `sequelize_associations` - hasMany, belongsTo, hasOne
- `sequelize_model_fields` - Field definitions
- `typeorm_entities` (if exists)
- `prisma_models` (if exists)

---

### Decision 3: Enhance TaintRegistry with Database Methods

**What:** Add methods to load patterns from database tables by language.

**Why:**
- Current `TaintRegistry` (core.py:31-161) already has language-aware structure
- But patterns are populated by rules at runtime, not from DB
- Need deterministic, database-driven pattern loading

**Current Structure (Already Good):**
```python
class TaintRegistry:
    sources: dict[str, dict[str, list[str]]] = {}   # [language][category] = [patterns]
    sinks: dict[str, dict[str, list[str]]] = {}
    sanitizers: dict[str, list[str]] = {}
```

**New Methods to Add:**
```python
def load_from_database(self, cursor: sqlite3.Cursor):
    """Load all patterns from database tables."""
    self._load_safe_sinks(cursor)        # FROM framework_safe_sinks
    self._load_validation_sanitizers(cursor)  # FROM validation_framework_usage
    self._load_api_sources(cursor)       # FROM api_endpoints

def _load_safe_sinks(self, cursor: sqlite3.Cursor):
    """Load safe sink patterns from framework_safe_sinks table.

    Schema (node_schema.py:539-548):
        framework_safe_sinks(framework_id, sink_pattern, sink_type, is_safe, reason)

    Note: No 'language' column - JOIN with frameworks table to get language.
    """
    cursor.execute("""
        SELECT f.language, fss.sink_pattern, fss.sink_type
        FROM framework_safe_sinks fss
        JOIN frameworks f ON fss.framework_id = f.id
        WHERE fss.is_safe = 1
    """)
    for row in cursor.fetchall():
        lang = row['language'] or 'global'
        self.register_sanitizer(row['sink_pattern'], lang)

def get_source_patterns(self, language: str) -> list[str]:
    """Get source patterns for a language.

    Args:
        language: 'python', 'javascript', 'rust'

    Returns:
        ['request.args', 'request.form'] for python
        ['req.body', 'req.params', 'req.query'] for javascript
        ['web::Json', 'web::Query'] for rust
    """
```

---

### Decision 4: Create `taint/type_resolver.py`

**What:** Lightweight utility for checking if two variables represent the same Data Model type.

**Why:**
- Graph has no edge between `u = User.get(1)` (File A) and `admin = User.get(1)` (File B)
- Both are `User` model instances - if `u` is tainted, `admin` might be too
- This is ALIASING without graph edges
- TypeResolver reads metadata populated by graph strategies

**NOT the same as `orm_utils.py`:**
- `orm_utils.py` BUILDS edges (graph layer)
- `type_resolver.py` READS metadata (taint layer)
- Clear separation of concerns

**Implementation:**
```python
# taint/type_resolver.py
class TypeResolver:
    """Polyglot Identity Checker.

    Answers: "Do these two variables represent the same Data Model?"
    Uses metadata already on nodes from Graph Strategies.
    """

    def __init__(self, graph_cursor: sqlite3.Cursor):
        self.graph_cursor = graph_cursor
        self._model_cache: dict[str, str] = {}  # node_id -> model_name

    def is_same_type(self, node_a_id: str, node_b_id: str) -> bool:
        """Check if two nodes represent the same model type.

        Args:
            node_a_id: Node ID like "file::func::var"
            node_b_id: Node ID like "file::func::var"

        Returns:
            True if both nodes have same 'model' in metadata
        """
        model_a = self._get_model_for_node(node_a_id)
        model_b = self._get_model_for_node(node_b_id)

        if model_a and model_b:
            return model_a == model_b
        return False
```

---

### Decision 5: Refactor Hardcoded Patterns in Three Files

**Files and Exact Locations:**

#### 5a. `ifds_analyzer.py`

| Line | Current (Hardcoded) | Target (Registry) |
|------|---------------------|-------------------|
| 437 | `'controller' in ap1.file.lower()` | `self.type_resolver.is_controller_file(ap1.file)` |
| 589 | `['req.body', 'req.params', ...]` | `self.registry.get_source_patterns(lang)` |
| 592 | `'routes' in file_path or 'middleware'...` | Query `api_endpoints` table |

#### 5b. `sanitizer_util.py`

| Line | Current (Hardcoded) | Target (Registry) |
|------|---------------------|-------------------|
| 199-221 | `validation_patterns = [...]` | `self.registry.get_sanitizer_patterns(lang)` |
| 233-246 | DUPLICATE of above | DELETE (consolidate) |

**Evidence of Duplication:**
```python
# Line 199-221
validation_patterns = [
    'validateBody', 'validateParams', 'validateQuery', ...
]

# Line 233-246 (EXACT SAME LIST!)
validation_patterns = [
    'validateBody', 'validateParams', 'validateQuery', ...
]
```

#### 5c. `flow_resolver.py`

| Line | Current (Hardcoded) | Target (Registry) |
|------|---------------------|-------------------|
| 151-176 | Express middleware chains, `['req.body', 'req.params', 'req.query', 'req']` | `self.registry.get_entry_patterns(lang)` |
| 334-369 | `res.json()`, `res.send()`, `res.render()`, `res.write()` | `self.registry.get_exit_patterns(lang)` |

---

## Risks / Trade-offs

### Risk 1: Performance Regression
**Risk:** Database lookups slower than hardcoded patterns
**Mitigation:** Pre-load all patterns in `__init__` into memory dict
**Trade-off:** Slightly higher memory for O(1) lookups

### Risk 2: Breaking Express Detection
**Risk:** Refactoring breaks currently-working Express detection
**Mitigation:**
1. Seed database with current hardcoded patterns
2. Unit tests comparing old vs new detection
3. Phased rollout (Phase 1/2 before Phase 3)

### Risk 3: Orphaned orm_utils.py References
**Risk:** Hidden imports we didn't find
**Mitigation:**
1. Verified with grep - only 1 import exists
2. Delete file first, let errors surface if any

### Risk 4: Graph Strategy Ordering
**Risk:** New NodeOrmStrategy runs before data is ready
**Mitigation:** dfg_builder.py already orders strategies correctly:
```python
self.strategies = [PythonOrmStrategy(), NodeExpressStrategy(), InterceptorStrategy()]
# Add NodeOrmStrategy() after PythonOrmStrategy()
```

---

## Migration Plan

### Step 1: Seed Database (No Code Changes)
Before any refactoring, ensure DB tables have the patterns:
```sql
-- Actual schema (from indexer/schemas/node_schema.py:539-548):
-- framework_safe_sinks(framework_id, sink_pattern, sink_type, is_safe, reason)
-- NOTE: No 'language' column - use frameworks.language via JOIN on framework_id

-- First ensure frameworks exist (frameworks.id is referenced by framework_id)
INSERT INTO frameworks (name, language) VALUES
('express', 'javascript'),
('flask', 'python'),
('django', 'python');

-- Then seed safe sinks (framework_id references frameworks.id)
INSERT INTO framework_safe_sinks (framework_id, sink_pattern, sink_type, is_safe, reason) VALUES
(1, 'validateBody', 'validation', 1, 'Express validation middleware'),
(1, 'validateParams', 'validation', 1, 'Express validation middleware'),
(1, 'validateQuery', 'validation', 1, 'Express validation middleware'),
(2, 'escape', 'sanitizer', 1, 'Flask HTML escaping'),
(3, 'mark_safe', 'sanitizer', 1, 'Django safe string marker');
```

### Step 2: Phase 1 (Graph Foundation)
1. Verify strategies work
2. Create NodeOrmStrategy
3. Delete orm_utils.py
4. Run `aud graph build` - verify edges created

### Step 3: Phase 2 (Infrastructure)
1. Add TaintRegistry methods
2. Create TypeResolver
3. Both are NEW code paths - no breaking changes

### Step 4: Phase 3 (Refactor)
1. Modify IFDS analyzer
2. Modify SanitizerRegistry
3. Modify FlowResolver
4. Run full test suite

### Rollback
Each phase is independently deployable. If Phase 3 breaks:
1. Revert Phase 3 changes only
2. Hardcoded patterns still work
3. Debug with new infrastructure in place

---

## Open Questions

1. **Rust Support Depth**: How much Rust taint analysis do we need?
   - Current: Zero
   - Proposed: Basic (entry points, obvious sinks)
   - Full: Would require Actix/Axum extractors

2. **Pattern Versioning**: Should patterns be versioned per framework version?
   - Express 4.x vs 5.x have different middleware patterns
   - Proposal: Framework table has version column, query by version

3. **Cross-Language Flows**: Can taint flow from Python to Node.js (microservices)?
   - Current: No
   - Future: Would need API boundary analysis

---

## Appendix: Verified Code Locations

### A. Current Hardcoded Patterns Found

```
theauditor/taint/sanitizer_util.py:199-221 - validation_patterns list
theauditor/taint/sanitizer_util.py:233-246 - DUPLICATE validation_patterns list
theauditor/taint/ifds_analyzer.py:437 - 'controller' in file.lower()
theauditor/taint/ifds_analyzer.py:589 - request_patterns = ['req.body', ...]
theauditor/taint/ifds_analyzer.py:592 - 'routes' in file_path checks
theauditor/taint/flow_resolver.py:151-176 - Express middleware chain patterns (entry points)
theauditor/taint/flow_resolver.py:334-369 - res.json(), res.send() patterns (exit points)
```

### B. Database Tables (Already Exist)

```sql
-- Sources of truth for patterns
framework_safe_sinks       -- Safe sink patterns by framework (column: sink_pattern, NOT pattern)
validation_framework_usage -- Validation sanitizers (Zod, Joi, Pydantic)
api_endpoints              -- Entry points by framework

-- ORM relationship data
sequelize_models           -- Node.js Sequelize models
sequelize_associations     -- Sequelize relationships
sequelize_model_fields     -- Sequelize field definitions
python_orm_models          -- SQLAlchemy/Django models (columns: file, line, model_name, table_name, orm_type)
orm_relationships          -- ORM relationships (NOT python_orm_relationships!)
                           -- columns: file, line, source_model, target_model, relationship_type, foreign_key, cascade_delete, as_name
```

**IMPORTANT (2025-11-27 Schema Verification):**
- Table `python_orm_relationships` does NOT exist - the actual table is `orm_relationships`
- Column `base_class` does NOT exist in `python_orm_models` - it's `orm_type`
- Column `pattern` does NOT exist in `framework_safe_sinks` - it's `sink_pattern`

### C. File Dependency Graph

```
                    dfg_builder.py
                          |
          +---------------+---------------+
          |               |               |
    python_orm.py    node_express.py  interceptors.py
          |               |               |
    orm_utils.py     (standalone)    (standalone)
    (TO DELETE)
```

### D. graphs.db Schema (for TypeResolver)

The TypeResolver queries the `nodes` table in graphs.db. Here is the schema:

```sql
-- graphs.db nodes table (from graph/analyzer.py)
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,           -- format: "file::function::variable"
    graph_type TEXT NOT NULL,      -- 'data_flow', 'call_graph', 'control_flow'
    file TEXT,                     -- source file path
    variable_name TEXT,            -- variable or symbol name
    scope TEXT,                    -- containing function name
    type TEXT,                     -- 'variable', 'parameter', 'function', 'call'
    metadata TEXT                  -- JSON blob for extensible attributes
);

-- Example metadata JSON structure (populated by ORM strategies):
-- {
--     "model": "User",           -- ORM model name (for TypeResolver)
--     "association_type": "hasMany",
--     "target_model": "Post",
--     "language": "javascript"
-- }

-- TypeResolver queries:
-- 1. Get model for a node:
SELECT json_extract(metadata, '$.model') as model
FROM nodes
WHERE id = ? AND graph_type = 'data_flow';

-- 2. Check if two nodes have same model type:
SELECT n1.id, n2.id,
       json_extract(n1.metadata, '$.model') as model1,
       json_extract(n2.metadata, '$.model') as model2
FROM nodes n1, nodes n2
WHERE n1.id = ? AND n2.id = ?
  AND json_extract(n1.metadata, '$.model') = json_extract(n2.metadata, '$.model');
```

**Note:** The `metadata` column is a JSON TEXT field. SQLite's `json_extract()` function is used to query nested fields. This allows strategies to add arbitrary metadata without schema changes.

### E. api_endpoints Schema (for Controller Detection)

```sql
-- api_endpoints table (from indexer/schemas/frameworks_schema.py:86-100)
CREATE TABLE api_endpoints (
    file TEXT NOT NULL,            -- source file path
    line INTEGER,                  -- line number of endpoint definition
    method TEXT NOT NULL,          -- HTTP method: 'GET', 'POST', etc.
    pattern TEXT NOT NULL,         -- route pattern: '/users/:id'
    path TEXT,                     -- base path
    full_path TEXT,                -- resolved full path: '/api/v1/users/:id'
    has_auth BOOLEAN DEFAULT 0,    -- whether endpoint requires auth
    handler_function TEXT          -- function that handles this endpoint
);

-- TypeResolver.is_controller_file() query:
SELECT 1 FROM api_endpoints WHERE file = ? LIMIT 1;
```

### F. validation_framework_usage Schema (Anchored)

```sql
-- Source: theauditor/indexer/schemas/node_schema.py:550-566
-- TableSchema for validation framework usage tracking

CREATE TABLE validation_framework_usage (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    framework TEXT NOT NULL,           -- 'zod', 'joi', 'yup'
    method TEXT NOT NULL,              -- 'parse', 'parseAsync', 'validate'
    variable_name TEXT,                -- 'schema', 'userSchema' or NULL for direct calls
    is_validator BOOLEAN DEFAULT 1,    -- True for validators, False for schema builders
    argument_expr TEXT                 -- Expression being validated (e.g., 'req.body')
);

-- Indexes:
CREATE INDEX idx_validation_framework_file_line ON validation_framework_usage(file_path, line);
CREATE INDEX idx_validation_framework_method ON validation_framework_usage(framework, method);
CREATE INDEX idx_validation_is_validator ON validation_framework_usage(is_validator);
```

### G. frameworks Schema (Anchored)

```sql
-- Source: theauditor/indexer/schemas/node_schema.py:522-536
-- TableSchema for detected frameworks

CREATE TABLE frameworks (
    id INTEGER PRIMARY KEY,            -- Auto-increment
    name TEXT NOT NULL,                -- 'express', 'flask', 'django'
    version TEXT,                      -- Framework version if detected
    language TEXT NOT NULL,            -- 'javascript', 'python', 'rust'
    path TEXT DEFAULT '.',             -- Path within repo
    source TEXT,                       -- Detection source (package.json, requirements.txt)
    package_manager TEXT,              -- 'npm', 'pip', 'cargo'
    is_primary BOOLEAN DEFAULT 0       -- Primary framework for the project
);

-- Unique constraint:
CREATE UNIQUE INDEX idx_frameworks_unique ON frameworks(name, language, path);
```

### H. express_middleware_chains Schema (Anchored)

```sql
-- Source: theauditor/indexer/schemas/node_schema.py:572-593
-- TableSchema for Express middleware chain tracking

CREATE TABLE express_middleware_chains (
    id INTEGER PRIMARY KEY,            -- AUTOINCREMENT handled by SQLite
    file TEXT NOT NULL,                -- Route file (e.g., account.routes.ts)
    route_line INTEGER NOT NULL,       -- Line where router.METHOD called
    route_path TEXT NOT NULL,          -- Endpoint path (e.g., "/account")
    route_method TEXT NOT NULL,        -- HTTP method (GET, POST, etc.)
    execution_order INTEGER NOT NULL,  -- 1, 2, 3... (order in argument list)
    handler_expr TEXT NOT NULL,        -- Function expression (e.g., "validateBody(...)")
    handler_type TEXT NOT NULL,        -- 'middleware' or 'controller'
    handler_file TEXT,                 -- Resolved file (if possible)
    handler_function TEXT,             -- Resolved function name
    handler_line INTEGER               -- Resolved line number
);

-- Indexes:
CREATE INDEX idx_express_middleware_chains_file ON express_middleware_chains(file);
CREATE INDEX idx_express_middleware_chains_route ON express_middleware_chains(route_line);
CREATE INDEX idx_express_middleware_chains_path ON express_middleware_chains(route_path);
CREATE INDEX idx_express_middleware_chains_method ON express_middleware_chains(route_method);
CREATE INDEX idx_express_middleware_chains_handler_type ON express_middleware_chains(handler_type);
```

### I. DFGEdge and create_bidirectional_edges (Anchored)

```python
# Source: theauditor/graph/types.py:31-42
@dataclass
class DFGEdge:
    """Represents a data flow edge in the graph."""

    source: str  # Source variable ID
    target: str  # Target variable ID
    file: str    # File containing this edge
    line: int    # Line number
    type: str = "assignment"  # assignment, return, parameter, orm_relationship
    expression: str = ""      # The assignment expression
    function: str = ""        # Function context
    metadata: dict[str, Any] = field(default_factory=dict)


# Source: theauditor/graph/types.py:45-112
def create_bidirectional_edges(
    source: str,
    target: str,
    edge_type: str,
    file: str,
    line: int,
    expression: str,
    function: str,
    metadata: dict[str, Any] = None,
) -> list[DFGEdge]:
    """
    Helper to create both a FORWARD edge and a REVERSE edge.

    Forward: Source -> Target (type)
    Reverse: Target -> Source (type_reverse)

    This enables backward traversal algorithms (IFDS) to navigate the graph
    by querying outgoing edges from a sink.

    Args:
        source: Source node ID (format: "file::function::variable")
        target: Target node ID (format: "file::function::variable")
        edge_type: Type of edge (assignment, return, parameter, orm_relationship)
        file: File containing this edge
        line: Line number
        expression: Expression for this edge (truncated to 200 chars)
        function: Function context
        metadata: Additional metadata dict (model, target_model, foreign_key, etc.)

    Returns:
        List containing both forward and reverse DFGEdge objects
    """
    if metadata is None:
        metadata = {}

    edges = []

    # 1. Forward Edge (Standard)
    forward = DFGEdge(
        source=source, target=target, type=edge_type,
        file=file, line=line, expression=expression,
        function=function, metadata=metadata,
    )
    edges.append(forward)

    # 2. Reverse Edge (Back-pointer for IFDS traversal)
    reverse_meta = metadata.copy()
    reverse_meta["is_reverse"] = True
    reverse_meta["original_type"] = edge_type

    reverse = DFGEdge(
        source=target, target=source,  # Swapped
        type=f"{edge_type}_reverse",
        file=file, line=line,
        expression=f"REV: {expression[:190]}" if expression else "REVERSE",
        function=function, metadata=reverse_meta,
    )
    edges.append(reverse)

    return edges
```

### J. TaintRegistry.register_sanitizer Method (Anchored)

```python
# Source: theauditor/taint/core.py:81-92
def register_sanitizer(self, pattern: str, language: str = None):
    """Register a sanitizer pattern, optionally language-specific.

    Args:
        pattern: Sanitizer function name (e.g., 'sanitize', 'escape', 'validateBody')
        language: Optional language identifier (None = applies to all languages)
                  Values: 'python', 'javascript', 'rust', or None for 'global'
    """
    lang_key = language if language else 'global'
    if lang_key not in self.sanitizers:
        self.sanitizers[lang_key] = []
    if pattern not in self.sanitizers[lang_key]:
        self.sanitizers[lang_key].append(pattern)
```

### K. Current DFGBuilder Strategy List (Anchored)

```python
# Source: theauditor/graph/dfg_builder.py:51-57
# Current strategy list that will be modified to add NodeOrmStrategy

class DFGBuilder:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

        # Strategy Pattern: Language-specific builders
        # Add new strategies here when supporting new languages (Rust, Go, etc.)
        self.strategies = [
            PythonOrmStrategy(),
            NodeExpressStrategy(),
            InterceptorStrategy(),
        ]

# Target modification:
        self.strategies = [
            PythonOrmStrategy(),
            NodeOrmStrategy(),       # <-- INSERT HERE (after PythonOrm, before NodeExpress)
            NodeExpressStrategy(),
            InterceptorStrategy(),
        ]
```
