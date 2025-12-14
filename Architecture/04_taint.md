# TheAuditor Taint Analysis Engine

## Overview

A **dual-mode, multi-hop data flow analysis system** combining:

1. **IFDS (Interprocedural Finite Distributive Subsets) Analyzer** - Backward demand-driven analysis
2. **FlowResolver** - Forward flow resolution for complete reachability

Traces **untrusted data from sources to dangerous sinks** across the entire codebase with field-sensitive access path tracking.

**Key Metrics:**
- Path Length: Up to 100+ hops across function boundaries
- Coverage: Multi-file, inter-procedural analysis
- Precision: Field-sensitive (tracks `.field` chains)
- Vulnerability Types: 18+ classes (SQLi, XSS, Command Injection, SSRF, etc.)
- Performance: 5-10x faster with in-memory caching

**Requirements:**
- **Python 3.14+**: Required for PEP 649 (Deferred Evaluation of Annotations). TheAuditor uses deferred annotation evaluation to resolve Pydantic models and FastAPI dependencies without runtime import errors, enabling static taint tracking through framework code that cannot be imported.

---

## Dual-Mode Architecture

### Mode 1: Backward (Default) - IFDS Only
- Starts at dangerous sinks, traces predecessors back to sources
- Demand-driven: only analyzes sinks that exist
- Fast: 30 seconds - 5 minutes
- Most accurate: respects path-sensitive sanitization

### Mode 2: Forward - FlowResolver Only
- Complete reachability from entry points to exit points
- Faster: 10-30 seconds
- Less precise: may miss complex sanitization

### Mode 3: Complete - Dual Engine
1. FlowResolver identifies ALL reachable sinks
2. IFDS analyzes those sinks with backward analysis
3. Handshake: Mark sinks confirmed by FlowResolver
4. Result: Union of both engines' findings

---

## IFDS Analyzer Deep Dive

### Backward Worklist Algorithm
```python
worklist = [(sink_ap, depth=0, [], matched_source=None)]
visited_states = set()

while worklist:
    current_ap, depth, hop_chain, matched_source = worklist.popleft()

    if current_ap matches any source: matched_source = source

    if depth >= max_depth OR no predecessors:
        if matched_source:
            if path_goes_through_sanitizer(hop_chain):
                record as SANITIZED
            else:
                record as VULNERABLE
        continue

    for pred_ap in _get_predecessors(current_ap):
        worklist.append((pred_ap, depth+1, [hop]+hop_chain, matched_source))
```

### Predecessor Resolution (Dual-Direction)
```python
# 1. Explicit reverse edges (marked with '_reverse' suffix)
WHERE source = current AND type LIKE '%_reverse'

# 2. Forward edges traversed backward
WHERE target = current AND type NOT LIKE '%_reverse'

# 3. Call graph edges (inter-procedural)
WHERE target = current AND graph_type = 'call'
```

---

## Vulnerability Coverage

| Type | Risk | Detection Method |
|------|------|-----------------|
| SQL Injection | CRITICAL | Sink: db.query(), interpolation |
| Command Injection | CRITICAL | Sink: os.system(), subprocess |
| XSS | HIGH | Sink: innerHTML, dangerouslySetInnerHTML |
| Path Traversal | HIGH | Sink: open() with user input |
| SSRF | HIGH | Sink: requests.get() with user URL |
| Template Injection | HIGH | Sink: render_template() |
| Deserialization | CRITICAL | Sink: pickle.loads(), eval() |
| NoSQL Injection | MEDIUM | Sink: db.find(), collection queries |
| Open Redirect | MEDIUM | Sink: redirect() with user URL |

---

## Access Path: Field-Sensitive Tracking

```python
@dataclass(frozen=True)
class AccessPath:
    file: str
    function: str
    base: str           # e.g., "req"
    fields: tuple       # e.g., ("body", "email")

    # node_id = "api.py::handler::req.body.email"
```

**Example Flow:**
```
Source: req.body.email → AccessPath("api.py", "handler", "req", ("body", "email"))
Assignment: user_input = req.body.email → taint propagates
Sink: db.query(f"...{user_input}") → VULNERABLE
```

---

## Sanitizer Detection

Multiple mechanisms:
1. **Registry Lookup**: `registry.is_sanitizer(function_name, language)`
2. **Validation Framework Detection**: Zod, Joi, Yup, express-validator
3. **Safe Sink Patterns**: Pre-marked safe functions
4. **Heuristic Detection**: Names containing `validate`, `sanitize`, `escape`

---

## Source & Sink Registry

### Sources (140+ Patterns)
- HTTP: `request.args`, `request.form`, `request.json`
- Environment: `os.environ`, `process.env`, `sys.argv`
- File I/O: `open().read()`, `fs.readFile()`
- Database: `cursor.fetchall()` (secondary taint)

### Sinks (200+ Patterns)
- SQL: `cursor.execute()`, `db.query()`, `sequelize.query()`
- Command: `os.system()`, `subprocess.call()`, `eval()`
- XSS: `dangerouslySetInnerHTML`, `innerHTML`
- File: `open()`, `fs.writeFile()`

---

## Configuration

```python
max_depth = os.environ.get("AUD_IFDS_DEPTH", 100)
max_paths_per_sink = os.environ.get("AUD_IFDS_MAX_PATHS", 1000)
time_budget_seconds = os.environ.get("AUD_IFDS_BUDGET", 60)
```

---

## Performance

| Codebase | Forward | Backward | Complete |
|----------|---------|----------|----------|
| 5K LOC | 5s | 15s | 20s |
| 20K LOC | 20s | 60s | 80s |
| 100K+ LOC | 2m | 5m | 7m |
