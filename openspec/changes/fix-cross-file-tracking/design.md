# Design: Fix Cross-File Taint Tracking

## Context

TheAuditor's taint analysis added cross-file infrastructure in v1.1 (worklist with file tracking, cross-file guards removed). However, **0 cross-file paths are detected** despite code existing.

**Database Evidence**:
- Total vulnerabilities: 880
- Cross-file vulnerabilities: 0 (0.0%)
- Total symbols: 24,375
  - type='call': 22,427 (92.4%)
  - type='function': 1,727 (7.1%)
  - type='class': 193 (0.8%)
  - type='property': 28 (0.1%)

**The Bug**: Two locations in `interprocedural.py` query symbols table to find callee file locations:
```python
# Line 132 (flow-insensitive) and line 453 (CFG-based)
query = build_query('symbols', ['path'],
    where="(name = ? OR name LIKE ?) AND type = 'function'", limit=1)
```

**Problem**: JavaScript/TypeScript method calls (`db.query`, `app.post`, `res.send`) have `type='call'`, not `type='function'`. Query filters out 92.4% of symbols, returns NULL, triggers silent fallback to same-file.

## Goals

1. Fix symbol query to include all relevant symbol types (`function`, `call`, `property`)
2. Remove silent fallback to enforce CLAUDE.md "NO FALLBACK" principle
3. Enable true cross-file tracking for Controller → Service → Model patterns
4. Maintain same performance characteristics (no additional queries)

## Non-Goals

- Fix indexer to change symbol types (schema is correct, query is wrong)
- Add caching for cross-file lookups (performance optimization, separate change)
- Support dynamic imports/requires (complex, out of scope)
- Handle all edge cases (focus on common patterns first)

## Decisions

### Decision 1: Type Filter Fix

**Choice**: Include `call` and `property` types in symbol lookup query.

**Query Change**:
```python
# BEFORE (BROKEN):
where="(name = ? OR name LIKE ?) AND type = 'function'"

# AFTER (FIXED):
where="(name = ? OR name LIKE ?) AND type IN ('function', 'call', 'property')"
```

**Rationale**:
- **type='function'**: Python function definitions, JavaScript function declarations
- **type='call'**: JavaScript method calls, property accesses (db.query, app.post)
- **type='property'**: Object properties, class methods
- All three types are valid call targets for taint tracking

**Evidence**:
- Broken query: 1/4 test cases succeed (25%)
- Fixed query: 4/4 test cases succeed (100%)
- Improvement: +75% symbol resolution rate

**Alternatives Considered**:
1. ❌ Change indexer to mark methods as type='function': Wrong - 'call' is semantically correct
2. ❌ Query without type filter: Too broad, includes irrelevant symbols
3. ✅ Include specific types: Precise, maintains query performance

### Decision 2: Remove Silent Fallback

**Choice**: Hard-fail if symbol not found, log debug message, skip call path.

**Code Change**:
```python
# BEFORE (HIDES BUG):
callee_file = callee_location[0].replace("\\", "/") if callee_location else current_file

# AFTER (FAIL LOUD):
if not callee_location:
    if debug:
        print(f"[INTER-PROCEDURAL] Symbol not found: {callee_func} (normalized: {normalized_callee})", file=sys.stderr)
    continue  # Skip this call path

callee_file = callee_location[0].replace("\\", "/")
```

**Rationale**:
- **CLAUDE.md mandate**: "NO FALLBACKS. NO EXCEPTIONS."
- Database is regenerated fresh every run - if symbol missing, indexer has bug
- Silent fallback corrupts file context, hides data quality issues
- Hard failure forces immediate investigation

**Impact**:
- May expose indexer gaps (GOOD - hidden bugs become visible)
- Requires symbol table to be complete (GOOD - enforces quality)
- Debug logging helps diagnose issues (GOOD - actionable errors)

**Alternatives Considered**:
1. ❌ Keep fallback, add warning: Still corrupts analysis, violates CLAUDE.md
2. ❌ Heuristic file lookup: Complex, error-prone, masks root cause
3. ✅ Hard fail with debug log: Simple, correct, forces quality

### Decision 3: Two-Location Fix

**Choice**: Apply identical fixes to both locations (flow-insensitive and CFG-based).

**Locations**:
1. `interprocedural.py:130-137` - Flow-insensitive inter-procedural (Stage 2)
2. `interprocedural.py:452-456` - CFG-based inter-procedural (Stage 3)

**Rationale**:
- Both code paths have identical bug
- Both use same worklist pattern
- Both need same fix for consistency

**Implementation Pattern**:
1. Fix line 132 and 453 (query)
2. Fix line 136-137 and 456 (fallback removal)
3. Verify fixes are identical (copy-paste acceptable here)

## Risks & Trade-offs

### Risk 1: Exposed Indexer Bugs
**Description**: If indexer doesn't populate symbols for some functions, taint tracking will skip them.

**Mitigation**:
- Add debug logging to identify missing symbols
- Run full analysis on TheAuditor codebase to validate coverage
- If widespread failures, create separate issue to fix indexer

**Acceptance**: Better to expose and fix indexer bugs than hide them with fallbacks.

### Risk 2: Reduced Path Count
**Description**: If many calls were using broken same-file fallback, removing it may reduce total paths.

**Mitigation**:
- Measure before/after path counts
- Investigate any significant drops (>10%)
- Paths should increase (cross-file) or stay same (existing same-file)

**Acceptance**: Correct cross-file paths > incorrect same-file paths.

### Risk 3: Performance Impact
**Description**: Query now checks 3 types instead of 1.

**Mitigation**:
- Type filter is indexed (fast)
- Query still returns limit=1 (single result)
- No additional queries added

**Acceptance**: Performance impact negligible (<1% expected).

## Migration Plan

### Phase 1: Fix and Validate (Day 1)
1. Apply type filter fix to both locations
2. Run validation script on test database
3. Verify 100% symbol lookup success on common callees
4. Commit fix if validation passes

### Phase 2: Remove Fallback (Day 1)
1. Apply fallback removal to both locations
2. Add debug logging for missing symbols
3. Run full analysis on TheAuditor codebase
4. Document any missing symbols found
5. Commit if no critical gaps

### Phase 3: Integration Testing (Day 2)
1. Create cross-file test fixture (Controller → Service → Model)
2. Verify at least 1 cross-file path detected
3. Verify inter-procedural step types present
4. Add regression test to ensure cross-file tracking works

### Rollback Plan
If critical failures occur:
1. Revert fallback removal (keep type filter fix)
2. Add warning log instead of hard failure
3. Create issue to fix indexer gaps
4. Re-apply fallback removal after indexer fixed

## Testing Strategy

### Unit Tests
1. Symbol query validation: Test type filter on sample database
2. Normalize function name: Verify `service.method` → `method`
3. Fallback removal: Verify `continue` executed when NULL

### Integration Tests
1. **Cross-file chain**: Controller → Service → Model (3 files)
2. **Same-file chain**: Function A → Function B (1 file, verify still works)
3. **Missing symbol**: Call to unknown function (verify skip with debug log)
4. **Mixed types**: Python functions + JavaScript methods

### Validation Queries
```sql
-- Before fix: Expect 0
SELECT COUNT(*) FROM taint_paths
WHERE source_file != sink_file;

-- After fix: Expect > 0
SELECT COUNT(*) FROM taint_paths
WHERE source_file != sink_file;

-- Inter-procedural steps
SELECT COUNT(*) FROM taint_paths p, json_each(p.path) step
WHERE json_extract(step.value, '$.type') IN ('argument_pass', 'return_flow', 'call');
```

## Open Questions

1. **Q**: What if indexer legitimately can't find some symbols (external libraries)?
   **A**: Skip those paths, log debug message. External library calls are out of scope for now.

2. **Q**: Should we add heuristic file lookup as backup?
   **A**: No - violates CLAUDE.md. If needed, fix indexer to populate symbols correctly.

3. **Q**: What about dynamic imports/requires?
   **A**: Out of scope. Static analysis only. May add in future change.

## Success Metrics

- ✅ Symbol lookup success rate: 25% → 100%
- ✅ Cross-file paths detected: 0 → >0 (expect 5-10% of 880 paths)
- ✅ Inter-procedural steps: 0 → >0 (argument_pass, return_flow, call)
- ✅ No silent fallbacks: 100% (enforced by code review)
- ✅ Debug logs: Present for all skipped symbols
- ✅ Performance: <5% regression (negligible)
