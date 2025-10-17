# Implement Multi-Hop Taint Tracking

## Why

Multi-hop taint tracking **has never worked** in TheAuditor. The worklist algorithm structure exists (max_depth=5, depth tracking, callee propagation) but **0 vulnerabilities are found beyond depth 0**.

**Evidence**:
- Database: 158 paths with 2 steps (source → sink, same function)
- 2 paths with "3 steps" are CFG conditions (if/while), NOT function hops
- No inter-procedural step types exist: 0 `argument_pass`, 0 `return_flow`, 0 `call` steps
- Root cause: Function resolution failure in worklist (same bug as cross-file tracking)

**User Impact**: Cannot detect Controller → Service → Model vulnerability patterns. Only detects direct flows within single functions.

## What Changes

This change **depends on** `fix-cross-file-tracking` (symbol lookup fix) and **builds on top of it**.

- **Phase 1 (Quick Win - 2 days)**: Incremental 3-hop backward chaining
  - For each 2-hop vulnerability (source → sink), query who calls source function
  - Build 3-hop chain: Caller → Source Function → Sink
  - Add to taint_paths with `intermediate_function` step type
  - Limit: 3 hops max (source → intermediate1 → intermediate2 → sink)

- **Phase 2 (Root Cause Fix - 1 week)**: Debug and fix worklist depth > 0
  - Enable `THEAUDITOR_TAINT_DEBUG=1` and trace why worklist doesn't find depth 1+ vulnerabilities
  - Fix issues preventing worklist from finding sinks in callee functions
  - Test with 5-hop integration test
  - Enable full `max_depth=5` multi-hop

**Impact**: Enables detection of multi-function vulnerability chains. Increases vulnerability detection rate by 20-30% (estimated).

## Impact

- **Affected specs**: `taint-analysis` (multi-hop propagation)
- **Affected code**:
  - `theauditor/taint/propagation.py` - Add backward chaining pass (Phase 1)
  - `theauditor/taint/interprocedural.py` - Debug worklist depth > 0 (Phase 2)
  - `theauditor/taint/core.py` - Update result structure for hop counts
- **Breaking changes**: None (adds capability, doesn't remove)
- **Performance impact**: Phase 1 adds <30s (backward queries). Phase 2 neutral (fixes broken code).
- **Dependencies**: **REQUIRES** `fix-cross-file-tracking` to be completed first

## Non-Goals

- Datalog/CodeQL rewrite (too large, separate change if needed)
- Dynamic import/require support (complex, out of scope)
- Unbounded hop depth (keep max_depth=5 for performance)
- Pointer analysis (too complex for current scope)
