## ADDED Requirements

### Requirement: Multi-Hop Taint Tracking
The taint analyzer SHALL track taint flows across multiple function calls, up to a maximum depth of 5 hops (source → intermediate1 → intermediate2 → intermediate3 → intermediate4 → sink).

**Hop Definition**:
- Hop 1: Source variable in function A
- Hop 2: Function A calls function B, passes tainted variable
- Hop 3: Function B calls function C, passes tainted variable
- ...
- Hop N: Tainted variable reaches sink

**Algorithm** (Two-Phase):
1. **Phase 1 (Backward Chaining)**: For each 2-hop path, query who calls source function, build N-hop chain backward
2. **Phase 2 (Worklist Forward)**: Fix worklist algorithm to find depth > 0 vulnerabilities forward

**Constraints**:
- `max_depth` parameter: Default 5, configurable via `trace_taint(max_depth=N)`
- Cycle prevention: Track visited functions, skip if already processed
- Performance target: <10 minutes for full codebase analysis

#### Scenario: 3-hop vulnerability detection (backward chaining)
- **GIVEN** 2-hop path exists: `controller.js:handle() → service.js:process()` with `req.body` → `db.query`
- **AND** router.js calls `controller.handle()` with `req.query.id` argument
- **WHEN** backward chaining runs
- **THEN** query: `SELECT caller_function, file FROM function_call_args WHERE callee_function = 'handle' AND argument_expr LIKE 'req.query%'`
- **AND** result: `{caller_function: 'handleRoute', file: 'router.js'}`
- **AND** new 3-hop path created: `router.js:handleRoute()` → `controller.js:handle()` → `service.js:process()`
- **AND** path includes step: `{type: 'intermediate_function', function: 'handle', file: 'controller.js'}`
- **AND** hop_count = 3

#### Scenario: 5-hop maximum depth limit
- **GIVEN** call chain: `app.js` → `router.js` → `controller.js` → `service.js` → `model.js` → `db.js`
- **WHEN** backward chaining runs with `max_depth=5`
- **THEN** detect 5-hop path: `app.js` → `router.js` → `controller.js` → `service.js` → `model.js` (stop at sink)
- **AND** do NOT attempt 6-hop: `externals.js` → `app.js` → ... (depth limit reached)
- **AND** log: "Max depth 5 reached"

#### Scenario: Cycle prevention in multi-hop tracking
- **GIVEN** recursive call chain: `functionA` → `functionB` → `functionA` (cycle)
- **WHEN** backward chaining runs
- **THEN** track visited: `{(fileA, functionA), (fileB, functionB)}`
- **AND** when attempting to add `functionA` again: skip (already visited)
- **AND** prevent infinite loop
- **AND** path ends at last non-cyclic function

#### Scenario: Multi-hop with cross-file tracking
- **GIVEN** `fix-cross-file-tracking` deployed (symbol lookup includes 'call', 'property' types)
- **AND** call chain: `controller.js:handleRequest()` → `service.js:validate()` → `model.js:save()`
- **WHEN** taint analysis runs
- **THEN** resolve `validate` symbol: `SELECT path FROM symbols WHERE name = 'validate' AND type IN ('function', 'call', 'property')`
- **AND** result: `service.js`
- **AND** resolve `save` symbol: `model.js`
- **AND** detect 3-hop cross-file vulnerability: `controller.js` → `service.js` → `model.js`

### Requirement: Hop Count Tracking
The taint analyzer SHALL track and report the number of hops for each vulnerability path.

**Data Structure**:
- TaintPath dataclass: Add `hop_count: int` field
- taint_paths table: Add `hop_count INTEGER` column
- JSON output: Include `"hop_count": N` in each path

**Hop Count Calculation**:
- 2 steps (source, sink in same function): hop_count = 1
- 3 steps (source, intermediate, sink): hop_count = 2
- N steps: hop_count = N - 1 (steps - 1 = hops)

**Reporting**:
- Include hop distribution in summary: "2-hop: 70%, 3-hop: 20%, 4-hop: 8%, 5-hop: 2%"
- Sort findings by hop count (higher = more complex, potentially more severe)

#### Scenario: Hop count in database
- **GIVEN** 3-hop path: `router.js` → `controller.js` → `service.js`
- **WHEN** taint analysis completes
- **THEN** taint_paths table row includes: `hop_count = 3`
- **AND** taint_analysis.json includes: `{"hop_count": 3, "source": {...}, "sink": {...}}`

#### Scenario: Hop distribution summary
- **GIVEN** 100 vulnerabilities detected: 70 at 2-hop, 20 at 3-hop, 8 at 4-hop, 2 at 5-hop
- **WHEN** report generated
- **THEN** summary includes:
  ```
  Multi-Hop Distribution:
    2-hop: 70 paths (70%)
    3-hop: 20 paths (20%)
    4-hop: 8 paths (8%)
    5-hop: 2 paths (2%)
  ```

### Requirement: Backward Chaining Algorithm (Phase 1)
The taint analyzer SHALL implement backward chaining to iteratively add hops to existing paths.

**Algorithm**:
1. Start with existing 2-hop paths (source → sink)
2. For each path, query: Who calls the source function with tainted argument?
3. For each caller found, create N+1-hop path
4. Recurse until max_depth reached or no more callers
5. Deduplicate paths (same source/sink/intermediate functions)

**Query Pattern**:
```sql
SELECT DISTINCT caller_function, file, line
FROM function_call_args
WHERE callee_function = ?  -- source function
  AND argument_expr LIKE ?  -- contains source variable
  AND file != ?  -- cross-file only (same-file already detected)
```

**Performance**:
- Per-hop query: ~100-500ms
- Total backward pass: <30 seconds for 5 hops

#### Scenario: Backward chaining finds additional hop
- **GIVEN** 2-hop path: `controller.handle(data)` → `db.query(data)` in service.js
- **AND** source function: `controller.handle`
- **AND** source variable: `data`
- **WHEN** backward chaining queries callers
- **THEN** query: `SELECT caller_function, file FROM function_call_args WHERE callee_function = 'handle' AND argument_expr LIKE '%data%'`
- **AND** result: `{caller_function: 'route', file: 'router.js'}`
- **AND** create 3-hop path: `router.route()` → `controller.handle()` → `service.js:db.query()`

#### Scenario: Backward chaining recursion
- **GIVEN** 3-hop path created in previous step
- **WHEN** backward chaining recurses (depth < max_depth)
- **THEN** query callers of `router.route`
- **AND** if found, create 4-hop path
- **AND** continue until max_depth=5 or no more callers

### Requirement: Worklist Depth > 0 Fix (Phase 2)
The taint analyzer SHALL fix the existing worklist algorithm to detect vulnerabilities at depth > 0.

**Root Cause** (to be debugged):
- Symbol lookup failure (fixed in `fix-cross-file-tracking`)
- Sink function matching failure (hypothesis)
- Taint state propagation failure (hypothesis)
- Cycle detection too aggressive (hypothesis)

**Debug Strategy**:
1. Enable `THEAUDITOR_TAINT_DEBUG=1`
2. Run on 3-hop test fixture
3. Analyze debug output for worklist processing
4. Identify where worklist fails to find depth > 0 vulnerabilities
5. Fix identified issues

**Expected Fix Locations**:
- `interprocedural.py:356-393` (sink function matching)
- `interprocedural.py:463-478` (taint state propagation)
- `interprocedural.py:343-350` (cycle detection)

#### Scenario: Worklist detects 3-hop vulnerability
- **GIVEN** call chain: `controller.js:handle()` → `service.js:validate()` → `model.js:save()`
- **AND** tainted variable `req.body` passed through chain
- **WHEN** worklist runs (after Phase 2 fix)
- **THEN** depth 0: Check sinks in `controller.handle()`, find 0
- **AND** depth 1: Add `service.validate()` to worklist with taint_state={data: True}
- **AND** depth 1: Check sinks in `service.validate()`, find 0
- **AND** depth 2: Add `model.save()` to worklist with taint_state={input: True}
- **AND** depth 2: Check sinks in `model.save()`, find `db.query(input)`
- **AND** VULNERABILITY FOUND at depth 2 (3-hop path)

#### Scenario: Debug logging for worklist processing
- **GIVEN** `THEAUDITOR_TAINT_DEBUG=1` enabled
- **WHEN** worklist processes 3-hop chain
- **THEN** log output includes:
  ```
  [INTER-PROCEDURAL] Depth 0: Processing controller.handle in controller.js
  [INTER-PROCEDURAL] Found 1 calls passing tainted data
  [INTER-PROCEDURAL] Added service.validate to worklist (depth 1)
  [INTER-PROCEDURAL] Depth 1: Processing service.validate in service.js
  [INTER-PROCEDURAL] Found 1 calls passing tainted data
  [INTER-PROCEDURAL] Added model.save to worklist (depth 2)
  [INTER-PROCEDURAL] Depth 2: Processing model.save in model.js
  [INTER-PROCEDURAL] VULNERABILITY FOUND: tainted data reaches db.query at line 45
  ```

## MODIFIED Requirements

### Requirement: Taint Path Data Structure
The TaintPath dataclass SHALL include `hop_count` field to track multi-hop depth.

**Previous Structure**:
```python
@dataclass
class TaintPath:
    source: dict
    sink: dict
    path: List[dict]
    severity: str
```

**New Structure**:
```python
@dataclass
class TaintPath:
    source: dict
    sink: dict
    path: List[dict]
    severity: str
    hop_count: int  # NEW: Number of function calls in chain
```

**Path Step Types** (extended):
- `source`: Taint source location
- `sink`: Taint sink location
- `intermediate_function`: Function hop in multi-hop chain (NEW)
- `argument_pass`: Argument passing step (existing, now used)
- `return_flow`: Return value flow step (existing, now used)
- `call`: Function call step (existing, now used)
- `conditions`: CFG conditions (existing)
- `direct_use`: Direct variable use (existing)

#### Scenario: Multi-hop path structure
- **GIVEN** 3-hop vulnerability: `router.js` → `controller.js` → `service.js`
- **WHEN** taint path created
- **THEN** path structure:
  ```json
  {
    "source": {"file": "router.js", "line": 10, "pattern": "req.query.id"},
    "sink": {"file": "service.js", "line": 45, "pattern": "db.query"},
    "path": [
      {"type": "source", "location": "router.js:10"},
      {"type": "intermediate_function", "function": "handle", "file": "controller.js", "line": 22},
      {"type": "intermediate_function", "function": "process", "file": "service.js", "line": 38},
      {"type": "sink", "location": "service.js:45"}
    ],
    "hop_count": 3,
    "severity": "high"
  }
  ```

### Requirement: Database Schema Extension
The `taint_paths` table SHALL include `hop_count` column.

**Schema Addition**:
```sql
CREATE TABLE taint_paths (
    ... existing columns ...
    hop_count INTEGER NOT NULL DEFAULT 1
)
```

**Migration**: None needed (database regenerated fresh every run per CLAUDE.md)

#### Scenario: Hop count persisted to database
- **GIVEN** 4-hop path detected
- **WHEN** taint analysis writes to database
- **THEN** `INSERT INTO taint_paths (..., hop_count) VALUES (..., 4)`
- **AND** query: `SELECT hop_count FROM taint_paths WHERE id = ?` returns 4
