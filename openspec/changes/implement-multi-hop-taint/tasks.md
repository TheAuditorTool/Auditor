# Implementation Tasks

## Prerequisites
- [ ] 0.1 Verify `fix-cross-file-tracking` is completed and deployed
- [ ] 0.2 Verify symbol lookup query includes type IN ('function', 'call', 'property')
- [ ] 0.3 Verify silent fallback removed from interprocedural.py

## Phase 1: Incremental 3-Hop Backward Chaining (2 days)

### 1. Design Backward Chaining Algorithm (2 hours)
- [ ] 1.1 Read existing 2-hop detection in `propagation.py:90-628`
- [ ] 1.2 Design backward query: For each 2-hop path, find calls to source function
- [ ] 1.3 Design forward query: From caller, trace to source function, verify taint propagates
- [ ] 1.4 Define `intermediate_function` step type for hop representation
- [ ] 1.5 Document algorithm in design.md

### 2. Implement Backward Pass (4 hours)
- [ ] 2.1 Create new function: `add_backward_hop_pass(paths, cursor, cache)` in propagation.py
- [ ] 2.2 For each 2-hop path, query: `SELECT caller_function, file FROM function_call_args WHERE callee_function = ? AND file != ?`
- [ ] 2.3 For each caller found, verify taint propagates through function call: Check if source var is in argument_expr
- [ ] 2.4 Build 3-hop path: `{type: 'source'} → {type: 'intermediate_function'} → {type: 'sink'}`
- [ ] 2.5 Add to paths list, deduplicate if already exists

### 3. Extend to 4-5 Hops (2 hours)
- [ ] 3.1 Recursively apply backward chaining up to max_depth
- [ ] 3.2 Track visited functions to prevent cycles: `visited = set()`
- [ ] 3.3 Stop when max_depth reached or no more callers found
- [ ] 3.4 Verify performance: each hop adds ~5-10s

### 4. Update Data Structures (1 hour)
- [ ] 4.1 Update TaintPath class: Add `hop_count` field
- [ ] 4.2 Update JSON serialization: Include hop_count in taint_analysis.json
- [ ] 4.3 Update database schema: Add `hop_count INTEGER` to taint_paths table
- [ ] 4.4 Update extraction logic: Preserve hop_count in readthis output

### 5. Testing Phase 1 (3 hours)
- [ ] 5.1 Create 3-hop test fixture: caller.js → controller.js → service.js
- [ ] 5.2 Run taint analysis, verify 3-hop path detected
- [ ] 5.3 Create 5-hop test fixture: verify recursion works
- [ ] 5.4 Test cycle prevention: A → B → A (verify stops)
- [ ] 5.5 Verify hop_count: 2, 3, 4, 5 in database
- [ ] 5.6 Performance test: measure backward pass time on full codebase

## Phase 2: Fix Worklist Depth > 0 (1 week)

### 6. Debug Worklist Algorithm (1 day)
- [ ] 6.1 Enable debug logging: `export THEAUDITOR_TAINT_DEBUG=1`
- [ ] 6.2 Run taint analysis on 3-hop test fixture
- [ ] 6.3 Analyze debug output: Look for "Added callee to worklist (depth 1)" messages
- [ ] 6.4 Look for "VULNERABILITY FOUND" messages at depth > 0
- [ ] 6.5 Identify why worklist continues but doesn't find sinks

### 7. Investigate Sink Checking Logic (4 hours)
- [ ] 7.1 Read interprocedural.py:356-393 (CFG-based sink checking)
- [ ] 7.2 Add debug logging: Print tainted_state at each worklist iteration
- [ ] 7.3 Add debug logging: Print sinks checked at each depth
- [ ] 7.4 Verify sink function matching: Does `sink_function["name"] == current_func` work?
- [ ] 7.5 Check if tainted variables persist across hops

### 8. Fix Identified Issues (1-2 days)
- [ ] 8.1 If sink matching fails: Fix get_containing_function query
- [ ] 8.2 If taint doesn't propagate: Fix args_mapping logic in lines 463-478
- [ ] 8.3 If cycle detection too aggressive: Relax visited state to allow multiple contexts
- [ ] 8.4 If file context wrong: Verify fix-cross-file-tracking applied correctly
- [ ] 8.5 Add unit tests for each fix

### 9. Integration Testing Phase 2 (1 day)
- [ ] 9.1 Re-run 3-hop test fixture with worklist fix
- [ ] 9.2 Verify worklist NOW finds 3-hop vulnerability (not just backward chaining)
- [ ] 9.3 Create 5-hop test fixture: Controller → Service → Model → DAO → DB
- [ ] 9.4 Verify max_depth=5 works correctly
- [ ] 9.5 Compare Phase 1 (backward) vs Phase 2 (worklist): should find same paths

### 10. Performance & Accuracy Testing (1 day)
- [ ] 10.1 Run full analysis on TheAuditor codebase
- [ ] 10.2 Measure hop distribution: 2-hop: X%, 3-hop: Y%, 4-hop: Z%, 5-hop: W%
- [ ] 10.3 Verify no false positives: Sample 20 multi-hop paths, manually verify
- [ ] 10.4 Measure runtime: Expect <10 minutes total (vs 3.9min baseline)
- [ ] 10.5 Document findings in performance_report.md

## 11. Documentation (2 hours)
- [ ] 11.1 Update CLAUDE.md: Add "Multi-Hop Taint Tracking" section with hop counts
- [ ] 11.2 Update propagation.py docstring: Document backward chaining algorithm
- [ ] 11.3 Update interprocedural.py docstring: Document worklist fixes
- [ ] 11.4 Add troubleshooting guide: "Max 2 hops detected" → Check debug logs
- [ ] 11.5 Add test documentation: How to create multi-hop test fixtures
