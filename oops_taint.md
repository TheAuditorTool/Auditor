# OOPS: Taint Analysis is Express-Only

**Discovery Date**: 2025-11-22
**Discovered By**: Multi-agent audit (3 models, parallel analysis)
**Severity**: CRITICAL ARCHITECTURAL FLAW
**Status**: UNFIXED

---

## TL;DR

The entire taint analysis engine (FlowResolver + IFDS) is **hard-coded for Express/Node.js**. Python projects (Django, FastAPI, Flask) get essentially **zero taint analysis**.

---

## The Two Taint Engines

### 1. FlowResolver (`theauditor/taint/flow_resolver.py`)

**Purpose**: Forward analysis - traces data from entry points to exit points

**The Problem**: Entry and exit point detection is 100% Express-specific.

#### Entry Points (lines 139-242)

```python
# EXPRESS ONLY - queries express_middleware_chains table
repo_cursor.execute("""
    SELECT DISTINCT file, handler_function
    FROM express_middleware_chains
    WHERE handler_type IN ('middleware', 'controller')
      AND execution_order = 0
""")

# For each handler, looks for req.body, req.params, req.query, req
for req_field in ['req.body', 'req.params', 'req.query', 'req']:
    node_id = f"{file}::{handler_func}::{req_field}"
```

**What's missing for Python:**
- Django: `request.GET`, `request.POST`, `request.body`, `request.FILES`
- FastAPI: Function parameters with type hints, `Depends()` injection
- Flask: `request.args`, `request.form`, `request.json`, `request.files`

#### Exit Points (lines 244-414)

```python
# NODE.JS ONLY - ORM patterns
WHERE (
    callee_function LIKE '%.create%'
    OR callee_function LIKE 'prisma.%'
    OR callee_function LIKE 'sequelize.query%'
)

# EXPRESS ONLY - Response functions
WHERE callee_function IN (
    'res.send', 'res.json', 'res.render', 'res.write'
)

# NODE.JS ONLY - External calls
WHERE callee_function IN (
    'axios.post', 'axios.get', 'fetch', 'request',
    'fs.writeFile', 'fs.writeFileSync'
)
```

**What's missing for Python:**
- Django ORM: `Model.objects.raw()`, `Model.objects.extra()`
- SQLAlchemy: `session.execute()`, `engine.execute()`
- Raw SQL: `cursor.execute()`, `conn.execute()`
- Dangerous: `pickle.loads()`, `yaml.load()`, `eval()`, `exec()`
- Subprocess: `subprocess.run()`, `os.system()`, `os.popen()`
- File: `open()`, `Path.write_text()`, `shutil.copy()`

---

### 2. IFDS Analyzer (`theauditor/taint/ifds_analyzer.py`)

**Purpose**: Backward analysis - traces from sinks back to sources

**The Problem**: Entry point detection (`_is_true_entry_point`) is Express-specific.

#### True Entry Point Detection (lines 563-623)

```python
def _is_true_entry_point(self, node_id: str) -> bool:
    # EXPRESS ONLY patterns
    request_patterns = ['req.body', 'req.params', 'req.query', 'req.headers']

    # EXPRESS ONLY - checks express_middleware_chains
    self.repo_cursor.execute("""
        SELECT COUNT(*)
        FROM express_middleware_chains
        WHERE (handler_function = ? OR handler_expr LIKE ?)
    """, (function_name, f'%{function_name}%'))

    # NODE.JS ONLY - environment variables
    if 'process.env' in variable:
        return True

    # NODE.JS ONLY - CLI args
    if 'process.argv' in variable:
        return True
```

**What's missing for Python:**
- `os.environ`, `os.getenv()`
- `sys.argv`
- Django/Flask/FastAPI request object patterns

#### The Silver Lining

The actual **graph traversal** in `_get_predecessors()` (lines 312-394) IS language-agnostic:

```python
# This works for ANY language - just follows edges in graphs.db
self.graph_cursor.execute("""
    SELECT target, type, metadata
    FROM edges
    WHERE source = ?
      AND graph_type = 'data_flow'
      AND type LIKE '%_reverse'
""", (ap.node_id,))
```

So if we fix the source/sink detection, IFDS backward traversal would work for Python.

---

## Evidence: project_anarchy Analysis

During the 7-project validation test, we discovered this bug:

```
Project: project_anarchy (polyglot - Express + Django + FastAPI)

Express middleware chains: 31    <- Has entry points
Cross-boundary edges: 0          <- ZERO connections to frontends

FlowResolver flows: 0            <- COMPLETELY FAILED
IFDS vulnerabilities: 7          <- Only worked because of registry sinks
```

FlowResolver found Express middleware chains but **zero cross-boundary edges** because:
1. The frontends (React/Angular/Vue) are in separate directories
2. They don't actually call the Express backends
3. The Python backends (Django/FastAPI) have no entry point detection at all

---

## Impact Assessment

| Project Type | FlowResolver | IFDS | Effective Coverage |
|--------------|--------------|------|-------------------|
| Express + React monorepo | FULL | FULL | 100% |
| Express standalone | PARTIAL | PARTIAL | 60% |
| Django | ZERO | PARTIAL* | 20% |
| FastAPI | ZERO | PARTIAL* | 20% |
| Flask | ZERO | PARTIAL* | 20% |
| Python standalone | ZERO | PARTIAL* | 10% |

*IFDS only works if the taint registry happens to include Python sinks, and even then entry point detection fails.

---

## What Needs To Be Fixed

### Phase 1: Python Entry Points

Add to `_get_entry_nodes()` in FlowResolver:

```python
# Django views
repo_cursor.execute("""
    SELECT DISTINCT file, name as handler_function
    FROM symbols
    WHERE type = 'function'
      AND (
        file LIKE '%views.py'
        OR file LIKE '%views/%'
      )
""")

# For Django handlers, look for request patterns
for req_field in ['request.GET', 'request.POST', 'request.body', 'request.FILES']:
    node_id = f"{file}::{handler_func}::{req_field}"

# FastAPI endpoints (uses python_routes table)
repo_cursor.execute("""
    SELECT DISTINCT file, handler_function
    FROM python_routes
    WHERE framework = 'fastapi'
""")

# Flask routes
repo_cursor.execute("""
    SELECT DISTINCT file, handler_function
    FROM python_routes
    WHERE framework = 'flask'
""")
```

### Phase 2: Python Exit Points

Add to `_get_exit_nodes()` in FlowResolver:

```python
# Python ORM sinks
repo_cursor.execute("""
    SELECT DISTINCT file, line, caller_function, argument_expr
    FROM function_call_args
    WHERE (
        callee_function LIKE '%.objects.raw%'
        OR callee_function LIKE '%.objects.extra%'
        OR callee_function LIKE 'cursor.execute%'
        OR callee_function LIKE 'session.execute%'
        OR callee_function LIKE 'engine.execute%'
    )
""")

# Python dangerous functions
repo_cursor.execute("""
    SELECT DISTINCT file, line, caller_function, argument_expr
    FROM function_call_args
    WHERE callee_function IN (
        'pickle.loads', 'pickle.load',
        'yaml.load', 'yaml.unsafe_load',
        'eval', 'exec', 'compile',
        'subprocess.run', 'subprocess.call', 'subprocess.Popen',
        'os.system', 'os.popen', 'os.exec'
    )
""")
```

### Phase 3: Fix IFDS Entry Point Detection

Update `_is_true_entry_point()`:

```python
# Python request patterns
python_request_patterns = [
    'request.GET', 'request.POST', 'request.body', 'request.FILES',  # Django
    'request.args', 'request.form', 'request.json',  # Flask
]

# Python environment variables
if 'os.environ' in variable or 'os.getenv' in variable:
    return True

# Python CLI args
if 'sys.argv' in variable:
    return True
```

### Phase 4: Cross-Boundary for Python

The DFG builder needs to create cross-boundary edges for Python:
- Django: Template → View → Model
- FastAPI: Pydantic schema → Endpoint → ORM
- Flask: Jinja template → Route → DB

---

## Estimated Effort

| Task | Hours | Priority |
|------|-------|----------|
| Python entry points (FlowResolver) | 8 | P0 |
| Python exit points (FlowResolver) | 8 | P0 |
| Python entry points (IFDS) | 4 | P0 |
| Python cross-boundary edges (DFG) | 16 | P1 |
| Test coverage | 12 | P1 |
| **TOTAL** | **48 hours** | - |

---

## Workaround (For Now)

Until this is fixed, Python projects rely on:

1. **IFDS backward analysis** - Works if sinks are in the registry
2. **Pattern detection rules** - Static rules in `theauditor/rules/` that don't use taint analysis
3. **Lint findings** - Bandit, semgrep, etc. catch some issues

But you're not getting:
- Full data flow tracking
- Cross-function taint propagation
- Sanitizer detection for Python
- Vulnerability classification based on flow analysis

---

## Files To Modify

1. `theauditor/taint/flow_resolver.py`
   - `_get_entry_nodes()` - Add Python framework support
   - `_get_exit_nodes()` - Add Python sink patterns

2. `theauditor/taint/ifds_analyzer.py`
   - `_is_true_entry_point()` - Add Python patterns

3. `theauditor/graph/dfg_builder.py`
   - Add Python cross-boundary edge creation

4. `theauditor/taint/registry.py` (if exists)
   - Ensure Python sources/sinks are registered

---

## Handoff Notes for Future Claude

1. **Read both files fully** before making changes - the architecture is complex
2. **FlowResolver uses in-memory graph** (lines 69-94) - very fast but loads all edges at startup
3. **IFDS uses reverse edges** - the DFG has `_reverse` suffix edges for backward traversal
4. **Don't break Express support** - many production users rely on it
5. **The `express_middleware_chains` table** is populated by the indexer - Python needs equivalent tables
6. **Test on real projects** - plant and PlantFlow are good Express tests, DEIC is Flask

---

## Related Documentation

- `docs/modules/04_taint_analysis.md` - Claims Python support (lies!)
- `CLAUDE.md` - Lists Python as supported language
- `Architecture.md` - Overall system design

---

**Bottom Line**: TheAuditor's taint analysis is a **Node.js/Express tool cosplaying as a multi-language SAST**. Python support needs 48+ hours of work to be real.
