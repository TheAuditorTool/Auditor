# Design: Implement Multi-Hop Taint Tracking

## Context

TheAuditor's taint analysis has NEVER successfully tracked taint flows beyond 2 hops (source → sink in same function).

**Current State**:
- Database: 158 paths with 2 steps (source, sink)
- Worklist algorithm EXISTS with max_depth=5 parameter
- Worklist processes callees and adds to queue
- **BUT**: 0 vulnerabilities found at depth > 0

**Evidence**:
- No `argument_pass`, `return_flow`, or `call` step types in taint_paths
- The 2 "3-hop" paths are CFG conditions (if/while), not function calls
- Debug tracing (if enabled) would show worklist continuing but not finding sinks

**Root Cause**: Same symbol lookup bug as `fix-cross-file-tracking`. Once that's fixed, worklist SHOULD work but likely has additional issues preventing depth > 0 detection.

## Goals

1. **Phase 1 (Quick Win)**: Implement incremental 3-hop backward chaining (works independently)
2. **Phase 2 (Root Cause Fix)**: Debug and fix worklist to enable true max_depth=5 multi-hop
3. Enable detection of Controller → Service → Model → DAO → DB patterns
4. Maintain performance: <10 min total runtime

## Non-Goals

- Datalog/CodeQL rewrite (4-6 weeks, separate change)
- Unbounded depth (keep max_depth=5 for performance)
- Pointer analysis (too complex)
- Dynamic imports (out of scope)

## Two-Phase Approach

### Phase 1: Incremental Backward Chaining (Quick Win)

**Why**: Provides immediate value while debugging worklist. Works independently of worklist fixes.

**Algorithm**:
```python
def add_backward_hop_pass(paths, cursor, cache, max_depth=5):
    """
    For each existing 2-hop path (source → sink), iteratively add backward hops.

    Example:
      Initial: req.body (source, controller.js) → db.query (sink, service.js)
      Query: Who calls the controller function?
      Result: Router.handleRequest (router.js)
      New path: router.js → controller.js → service.js (3 hops)
    """
    new_paths = []
    visited = set()  # Prevent cycles

    for path in paths:
        if path.hop_count >= max_depth:
            continue

        # Query: SELECT caller_function, file FROM function_call_args
        #        WHERE callee_function = path.source_function
        #          AND argument_expr LIKE path.source_var
        callers = query_callers(cursor, path.source_function, path.source_var)

        for caller in callers:
            if (caller.file, caller.function) in visited:
                continue  # Prevent cycle

            # Build new path with additional hop
            new_path = TaintPath(
                source={...caller...},
                sink=path.sink,
                path=[
                    {'type': 'source', ...},
                    {'type': 'intermediate_function', 'function': path.source_function, 'file': path.source_file},
                    *path.path[1:],  # Rest of original path
                    {'type': 'sink', ...}
                ],
                hop_count=path.hop_count + 1
            )
            new_paths.append(new_path)
            visited.add((caller.file, caller.function))

    return paths + new_paths
```

**Advantages**:
- Simple, works with existing data
- No worklist changes needed
- Can be added in <2 days
- Provides immediate value

**Disadvantages**:
- Limited to 5 hops (acceptable)
- Backward only (forward worklist better but broken)
- Duplicate effort if worklist fixed (acceptable temporary trade-off)

### Phase 2: Fix Worklist Algorithm (Root Cause Fix)

**Why**: Worklist SHOULD work once symbol lookup fixed. But may have additional bugs preventing depth > 0.

**Debug Strategy**:
1. Enable `THEAUDITOR_TAINT_DEBUG=1`
2. Run on 3-hop test fixture
3. Look for evidence of worklist processing:
   - "Added callee to worklist (depth 1)"
   - "Processing function X at depth 1"
   - "Checking sink Y in function X"
4. Identify WHERE it fails:
   - Sink function matching?
   - Taint state propagation?
   - Cycle detection too aggressive?

**Hypothesis: Sink Function Matching Fails**

Code location: `interprocedural.py:356-393` (CFG-based)

```python
for sink in sinks:
    sink_function = get_containing_function(cursor, sink)
    if not sink_function or sink_function["name"] != current_func:
        continue  # ← MAY BE SKIPPING VALID SINKS

    # Check if tainted vars reach sink...
```

**Potential Issue**: `sink_function["name"]` may not match `current_func` due to:
- Normalization differences (qualified vs base name)
- Symbol table incomplete
- Function name mismatch (e.g., anonymous functions)

**Fix**: Log both values, check if mismatch. Add fallback matching logic if needed.

**Hypothesis: Taint State Doesn't Propagate**

Code location: `interprocedural.py:463-478`

```python
for tainted_var in taint_state:
    if arg_expr and tainted_var in arg_expr:
        if param_name:
            propagated_taint[param_name] = True
            args_mapping[tainted_var] = param_name

if not propagated_taint:
    continue  # ← MAY BE SKIPPING VALID CALLS
```

**Potential Issue**: `tainted_var in arg_expr` may fail due to:
- Exact string matching (misses variable transformations)
- Argument expressions complex (e.g., `obj.property`)
- Parameter names not in function_call_args

**Fix**: More robust matching logic. Check if ANY tainted var is substring of argument. Use CFG to trace argument origin.

**Hypothesis: Cycle Detection Too Aggressive**

Code location: `interprocedural.py:343-350`

```python
tainted_vars_frozen = frozenset(taint_state.keys())
state_key = (current_file, current_func, tainted_vars_frozen)
if state_key in visited:
    continue  # ← MAY BE PREVENTING VALID PATHS
```

**Potential Issue**: Function called multiple times with same tainted var from different call sites is only processed once.

**Fix**: Include call path in state key: `(current_file, current_func, frozenset(call_path))`

## Decisions

### Decision 1: Two-Phase Implementation

**Choice**: Implement backward chaining (Phase 1) FIRST, then fix worklist (Phase 2).

**Rationale**:
- Backward chaining provides immediate value (2 days)
- Worklist debugging may take 1+ week (unknown complexity)
- Users get multi-hop capability faster
- If worklist unfixable, backward chaining is fallback

**Timeline**:
- Week 1: Phase 1 (backward chaining) - DONE
- Week 2: Phase 2 (worklist debugging) - IN PROGRESS
- Week 3: Integration testing, performance tuning

### Decision 2: Max Depth Remains 5

**Choice**: Keep `max_depth=5` limit.

**Rationale**:
- 5 hops covers 95% of real-world patterns
- Prevents infinite loops in recursive code
- Keeps performance acceptable (<10 min)
- Can increase later if needed (separate change)

**Alternatives Considered**:
1. ❌ Unbounded depth: Risk of infinite loops, performance issues
2. ✅ max_depth=5: Proven in other tools (CodeQL, Semgrep)
3. ❌ max_depth=10: Overkill, 99% of chains are <5 hops

### Decision 3: Backward Chaining Algorithm

**Choice**: Query-based backward chaining from existing 2-hop paths.

**Query Strategy**:
```sql
-- For each 2-hop path, find who calls source function
SELECT DISTINCT caller_function, file, line
FROM function_call_args
WHERE callee_function = ?  -- source function name
  AND argument_expr LIKE ?  -- contains source variable
  AND file != ?  -- exclude same-file (already have those)
ORDER BY line
```

**Recursion**:
- Start with 2-hop paths (depth=1)
- For each, find callers (depth=2)
- Recurse up to max_depth=5
- Track visited to prevent cycles

**Performance**:
- Per-hop: ~5-10 seconds (database query + path construction)
- Total: ~30s for 5 hops (acceptable)

### Decision 4: Data Structure Changes

**Choice**: Add `hop_count` field to TaintPath and taint_paths table.

**Schema Change**:
```python
# TaintPath dataclass
@dataclass
class TaintPath:
    source: dict
    sink: dict
    path: List[dict]
    severity: str
    hop_count: int  # NEW FIELD

# Database schema
taint_paths table:
    ... existing columns ...
    hop_count INTEGER  # NEW COLUMN
```

**Migration**: None needed (database regenerated fresh every run)

**Rationale**:
- Enables hop distribution analysis
- Helps debug multi-hop vs single-hop detection
- Useful for reporting (show hop count in findings)

## Risks & Trade-offs

### Risk 1: Backward Chaining Finds False Positives
**Description**: Caller may not actually propagate taint (complex control flow).

**Mitigation**:
- Only add hop if `argument_expr LIKE source_var` (basic taint check)
- Phase 2 worklist fix provides more accurate CFG-based validation
- Sample and manually verify 20 multi-hop paths

**Acceptance**: Some false positives acceptable in Phase 1 for quick win. Phase 2 improves accuracy.

### Risk 2: Worklist Unfixable (Unknown Complexity)
**Description**: Worklist may have deep architectural issues preventing fix.

**Mitigation**:
- Backward chaining provides working multi-hop capability
- Can defer worklist fix or rewrite if needed
- Phase 1 success decouples feature from worklist status

**Acceptance**: Backward chaining is acceptable long-term solution if worklist unfixable.

### Risk 3: Performance Degradation
**Description**: Backward chaining adds 30s, worklist fix may add more.

**Mitigation**:
- Measure at each step
- Optimize queries (indexes, caching)
- Limit backward chaining to depth=3 if needed
- Target: <10 min total (vs 3.9min baseline)

**Acceptance**: 2-3x slowdown acceptable for multi-hop capability.

## Testing Strategy

### Phase 1 Tests

**3-Hop Chain**:
```javascript
// router.js
function handleRoute(req, res) {
    controller.handle(req.query.id);  // HOP 1
}

// controller.js
function handle(id) {
    const data = id;  // SOURCE (actually HOP 2 start)
    service.process(data);  // HOP 2
}

// service.js
function process(input) {
    db.query(`DELETE FROM users WHERE id = ${input}`);  // SINK
}
```

Expected: 3-hop path detected via backward chaining.

**5-Hop Chain**:
```javascript
// app.js → router.js → controller.js → service.js → model.js
```

Expected: 5-hop path detected, stops at max_depth.

**Cycle Prevention**:
```javascript
// A.js calls B.js calls A.js (cycle)
```

Expected: Cycle detected, doesn't infinite loop.

### Phase 2 Tests

**Same 3-Hop Chain** (as above):
Expected: Detected by BOTH backward chaining AND worklist.

**5-Hop with Complex Control Flow**:
```javascript
// Multiple branches, loops, conditionals
```

Expected: Worklist's CFG-based analysis more accurate than backward chaining.

### Integration Tests

- Run on TheAuditor codebase (24K LOC)
- Measure hop distribution (expect 70% 2-hop, 20% 3-hop, 8% 4-hop, 2% 5-hop)
- Sample 50 paths, manually verify accuracy
- Measure runtime (expect 5-10 min)

## Success Metrics

### Phase 1 (Backward Chaining)
- ✅ 3-hop paths detected: >0 (expect 10-20% of paths)
- ✅ 4-hop paths detected: >0 (expect 5-10% of paths)
- ✅ 5-hop paths detected: >0 (expect 1-5% of paths)
- ✅ Runtime: <5 minutes total (3.9min baseline + 1min backward)
- ✅ False positive rate: <10% (sample 20 paths)

### Phase 2 (Worklist Fix)
- ✅ Worklist finds depth > 0 vulnerabilities: >0
- ✅ Agreement: Worklist paths match backward chaining paths (>80%)
- ✅ Accuracy: Worklist more accurate than backward (fewer false positives)
- ✅ Runtime: <10 minutes total (acceptable for multi-hop)
- ✅ Coverage: Finds vulnerabilities backward chaining misses

## Open Questions

1. **Q**: Should Phase 1 be removed after Phase 2 works?
   **A**: No - keep both. Backward is fast, worklist is accurate. Use both for coverage.

2. **Q**: What if worklist debugging takes >1 week?
   **A**: Ship Phase 1, defer Phase 2. Users get multi-hop immediately.

3. **Q**: Should we add inter-procedural CFG (call graph integration)?
   **A**: Out of scope. Worklist + CFG already exists, just needs debugging.

4. **Q**: How to handle library calls (external code)?
   **A**: Stop at library boundary. External code out of scope for static analysis.
