# Taint Refactor Audit Report
**Date**: 2025-11-02
**Scope**: refactor-taint-schema-driven-architecture impact analysis
**Status**: CRITICAL REGRESSIONS FOUND

---

## Executive Summary

The schema-driven refactor (Oct 31 - Nov 1) successfully reduced code complexity but **broke taint detection** by:
1. **Ignoring 62K pre-computed taint sources** in specialized tables
2. **Re-discovering sources from scratch** using incomplete patterns
3. **No parameter mapping** - taint dies at function boundaries
4. **Result**: 0/10 real vulnerabilities detected on plant codebase

---

## What Was Promised (design.md)

### Non-Goals (Promises Made)
> ❌ **Change taint algorithms** - Preserve exact taint propagation logic
> ❌ **Add new features** - Pure refactor, no new capabilities

### Validation Criteria
> - [ ] Taint results match exactly (old vs new)
> - [ ] Same sources/sinks discovered
> - [ ] No false negatives
> - [ ] 100% test pass rate

**Reality**: All validation criteria FAILED.

---

## Critical Regression #1: Source Discovery Broken

### Before Refactor (Oct 27 database)
```
assignment_sources:         42,849 rows  ← Pre-computed taint sources
function_return_sources:    19,317 rows  ← More taint sources
TOTAL:                      ~62,000 taint sources
```

These tables were populated during indexing by analyzing:
- All assignments where RHS contains tainted data
- All function returns that propagate taint
- Framework-specific sources (req.body, etc.)

### After Refactor (Current)
```python
# discovery.py lines 70-140
# Discovers sources from:
- api_endpoints table:          185 rows
- symbols with pattern match:   ~1000 rows
- env_accesses:                 ~few rows
- sql_queries (SELECT):         ~200 rows

TOTAL: ~1,124 sources discovered
```

**PROBLEM**: New implementation re-discovers from generic tables using pattern matching.
**MISSING**: The 62K pre-computed sources from specialized extraction.

### Root Cause
The refactor design document (line 283-304) shows example code:
```python
# User input: Query symbols for actual property access
for symbol in self.cache.symbols:
    if symbol['type'] == 'property':
        if any(x in symbol['name'] for x in ['req.', 'request.']):
            sources.append({...})
```

This **replaced** the specialized `assignment_sources` table without migrating the logic.

---

## Critical Regression #2: Sink Discovery Incomplete

### Before Refactor
Sinks were likely discovered from:
- Specialized sink tables (we need to check old .bak files)
- Framework-specific patterns
- Pre-analyzed dangerous function calls

### After Refactor
```python
# discovery.py lines 155-275
# Discovers sinks from:
- sql_queries:             192 sinks
- function_call_args:      Various command/file ops
- assignments (innerHTML): XSS sinks
```

**Current Result**: 196 sinks on plant (seems reasonable)
**But**: Need to verify these match pre-refactor sinks

---

## Critical Regression #3: Parameter Mapping Not Implemented

**Location**: `analysis.py:155`
```python
# Map argument to parameter (simplified - use 'param' as generic)
# TODO: Proper parameter mapping from function signatures
param_name = 'param'  # ← PLACEHOLDER KILLS CROSS-FUNCTION TAINT
```

**Impact**:
- Single-function paths work (test fixture: 1/1 detected)
- Multi-function paths fail (plant: 0/10 detected)
- Taint dies when crossing function boundaries

**Why This Exists**:
The refactor focused on simplifying architecture, NOT on implementing missing features.
This was likely a pre-existing limitation that got carried over.

---

## What Changed in Refactor

### Deleted Files (from design.md)
```
taint/database.py (1,447 lines)      ← Fallback query logic
taint/memory_cache.py (59KB)         ← Old cache loaders
taint/python_memory_cache.py (20KB)  ← Python-specific cache
taint/sources.py (18KB)              ← OLD SOURCE DISCOVERY
taint/config.py (5KB)                ← Hardcoded patterns
taint/registry.py (8KB)              ← Source/sink registry
```

**CRITICAL**: `sources.py` (18KB) was deleted.
This likely contained the logic to query `assignment_sources` and `function_return_sources`.

### Added Files
```
taint/discovery.py (334 lines)       ← NEW SOURCE DISCOVERY
taint/analysis.py (~800 lines)       ← Unified CFG analyzer
```

**NEW discovery.py queries generic tables**, not specialized taint tables.

---

## How The Breakage Happened

### Design Phase Error
The design document (line 283) shows example discovery code that queries `symbols` table.
**It never mentions `assignment_sources` or `function_return_sources` tables.**

This means:
1. Design document didn't account for specialized taint tables
2. Implementation followed the design
3. Specialized tables were ignored, not migrated
4. Sources_found dropped from 62K → 1K

### Implementation Phase Error
Phase 3 validation criterion:
> - [ ] Same sources/sinks discovered

**This was never validated** because:
- Refactor marked as COMPLETE
- No comparison between old/new source counts
- Test fixture still passed (1/1 detection)

---

## Current State

### Test Fixture (Simple Case)
```
File: tests/fixtures/node-express-api/routes/products.js
Detection: 1/1 SQL injection ✅
Why it works: Entire path in ONE function (lines 25-34)
```

### Plant Codebase (Real Case)
```
Sources discovered: 1,124
Sinks discovered: 196
Taint paths detected: 0/10 ❌
Why it fails:
1. Missing 62K specialized sources
2. No parameter mapping across functions
3. Taint dies at call boundaries
```

---

## Recovery Plan

### Option 1: Restore Specialized Source Tables (RECOMMENDED)
**Pros**: Keeps refactor architecture, restores functionality
**Cons**: Need to wire specialized tables into new discovery layer

**Implementation**:
1. Add to `discovery.py`:
```python
# Specialized taint sources (pre-computed during indexing)
if hasattr(self.cache, 'assignment_sources'):
    for src in self.cache.assignment_sources:
        sources.append({
            'type': 'assignment_source',
            'name': src.get('target_var', 'unknown'),
            'file': src.get('file', ''),
            'line': src.get('line', 0),
            'pattern': src.get('source_expr', ''),
            'category': 'taint_propagation',
            'risk': 'high',
            'metadata': src
        })

if hasattr(self.cache, 'function_return_sources'):
    for src in self.cache.function_return_sources:
        sources.append({
            'type': 'function_return',
            'name': src.get('function', 'unknown'),
            'file': src.get('file', ''),
            'line': src.get('line', 0),
            'pattern': src.get('return_expr', ''),
            'category': 'taint_propagation',
            'risk': 'medium',
            'metadata': src
        })
```

2. Verify sources_found increases from 1,124 → ~63,000
3. Test on plant codebase

### Option 2: Revert Refactor
**Pros**: Immediate restoration of functionality
**Cons**: Loses architectural improvements

### Option 3: Rewrite Source Discovery from Scratch
**Pros**: Clean slate
**Cons**: Time-consuming, risky

---

## Lessons Learned

### What Went Wrong
1. **Incomplete specification** - Design doc didn't inventory all source tables
2. **No regression testing** - Validation criteria defined but not executed
3. **Premature "COMPLETE" status** - Marked done before validation
4. **"Zero breaking changes" promise broken** - Functionality regressed

### What Should Have Happened
1. **Before refactor**: Document all tables used by taint analysis
2. **During refactor**: Map old tables → new discovery logic
3. **Before marking COMPLETE**: Run on plant codebase, compare results
4. **Rollback trigger**: 0 detections on real codebase = failed validation

---

## Recommendations

### Immediate (This Session)
1. ✅ **Audit complete** - This document
2. ⏳ **Wire specialized tables** into discovery.py
3. ⏳ **Test on plant** - Verify sources increase
4. ⏳ **Implement parameter mapping** - Fix cross-function taint

### Short-term (Next Session)
1. Check if `.bak` files have parameter mapping logic we can restore
2. Compare old sink discovery vs new (verify 196 sinks are correct)
3. Create regression test: plant must detect ≥5/10 known vulnerabilities

### Long-term (OpenSpec)
1. Create validation checklist for refactors
2. Require real codebase testing before marking COMPLETE
3. Add "results comparison" to refactor design template

---

## Questions for You

1. **Did old taint analysis work on plant?** (Before Oct 31 refactor)
   - If yes: How many detections?
   - If no: Was parameter mapping also broken before?

2. **Do `.bak` files have parameter mapping?**
   - Should I check `interprocedural.py.bak` for this logic?

3. **Priority**:
   - Fix source discovery first? (wire specialized tables)
   - Fix parameter mapping first? (cross-function taint)
   - Both in parallel?

4. **Validation target**:
   - What's acceptable detection rate? (5/10? 10/10?)
   - Are we restoring old behavior or building new capability?

---

## Status: AWAITING DIRECTION

I've identified the problems. Tell me which to fix first and I'll implement it.
