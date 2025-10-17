# Taint Analysis Investigation Report
**Date**: 2025-10-18
**Issue**: Taint analysis only finding direct-use patterns, missing multi-hop cross-file flows
**Severity**: CRITICAL - Core feature not working as designed

---

## Executive Summary

Taint analysis is **ONLY** finding direct-use vulnerabilities (source → sink in 2 hops within same function) and **MISSING ALL multi-hop cross-file flows**. Despite running in "Stage 3 (CFG multi-hop)" mode with `use_cfg=True`, the inter-procedural analysis is silently failing.

**Impact**: The 4.7-second runtime (down from 2-3 minutes) indicates the analyzer is NOT performing deep multi-hop tracking. Only 10 findings (all direct-use) vs expected hundreds with full tracking.

---

## Root Cause Analysis

### PRIMARY BUG: Function Name Mismatch

**Location**: `theauditor/taint/interprocedural_cfg.py:138`

**Problem**: When `InterProceduralCFGAnalyzer.analyze_function_call()` tries to create a `PathAnalyzer` for a callee function, it looks for CFG blocks using the FULL function name from `function_call_args` table:

```python
# PathAnalyzer init tries to find CFG blocks with this name:
callee_function = "accountService.createAccount"  # From function_call_args table
```

But the `cfg_blocks` table stores function names WITHOUT the object/class prefix:

```sql
-- Database evidence:
SELECT COUNT(*) FROM cfg_blocks WHERE function_name = 'accountService.createAccount';
-- Result: 0

SELECT COUNT(*) FROM cfg_blocks WHERE function_name = 'createAccount';
-- Result: 64  <-- CFG DATA EXISTS!
```

**Consequence**: PathAnalyzer init fails with "No CFG data" exception, triggering fallback at line 143:

```python
except Exception as e:
    if self.debug:
        print(f"  No CFG data for {callee_func}: {e}", file=sys.stderr)
    # Fall back to conservative analysis
    return self._analyze_without_cfg(callee_func, args_mapping, taint_state)
```

### SECONDARY BUG: _analyze_without_cfg Returns "unmodified"

**Location**: `theauditor/taint/interprocedural_cfg.py:481-483`

```python
# Assume parameters are unmodified (conservative for pass-by-ref)
for param in args_mapping.values():
    effect.param_effects[param] = 'unmodified'  # <-- WRONG!
```

**Problem**: When CFG lookup fails, the fallback returns `'unmodified'` for all parameters. This tells the taint propagation algorithm that tainted data does NOT flow through the function call.

**Debug evidence from live run**:
```
[INTER-CFG] Analyzing call to accountService.createAccount
  Args mapping: {'req.body': 'arg0'}
  Taint state: {'req.body': True}
  Effect: return_tainted=False, params={'arg0': 'unmodified'}  # <-- KILLS PROPAGATION!
```

Since `arg0` is marked `'unmodified'`, the inter-procedural worklist does NOT add it to the next step, and the taint trail dies.

---

## Evidence Chain

### 1. Database Has Rich Data
```
Symbols: 33,328
Function call args: 18,084
Assignments: 5,241
Variable usage: 61,881
CFG blocks: 16,623
CFG edges: 18,257
```

### 2. CFG Data Exists for Service Functions
```sql
-- accountService.createAccount CFG blocks:
SELECT COUNT(*) FROM cfg_blocks WHERE function_name = 'createAccount';
-- Result: 64 blocks
```

### 3. Callee File Path Partially Populated
```
Total function_call_args: 18,084
callee_file_path NOT NULL: 13,435 (74.3%)
callee_file_path NULL: 4,649 (25.7%)  <-- External framework methods
```

### 4. Taint Analysis Results
```
Taint sources found: 304
Security sinks found: 405
Taint paths found: 10  <-- ALL are direct-use (path_length: 2)
Runtime: 4.7 seconds  <-- Should be ~30s with full multi-hop
```

### 5. Debug Output Confirms Fallback
```
[INTER-CFG] Analyzing call to accountService.createAccount
  No CFG data for accountService.createAccount  <-- Lookup fails
  Effect: return_tainted=False, params={'arg0': 'unmodified'}  <-- Kills taint
```

---

## Why This Matters

### Expected Behavior (Multi-Hop Tracking)
```javascript
// Backend Controller
const userData = req.body;  // SOURCE
accountService.createAccount(userData);  // CALL → Should propagate taint

// Service Layer (different file)
function createAccount(data) {  // data is tainted via arg0
    db.execute(`INSERT ... VALUES ('${data.name}')`);  // SINK - SQL INJECTION!
}
```

**Expected**: Taint should flow: `req.body → userData → accountService.createAccount(data) → db.execute` = **VULNERABILITY**

**Actual**: Inter-procedural analysis fails at the function call boundary because:
1. PathAnalyzer can't find CFG for "accountService.createAccount"
2. Fallback returns `'unmodified'`
3. Taint propagation stops
4. **NO FINDING**

### Current Behavior (Direct-Use Only)
```javascript
// Same function scope
const data = req.body;  // SOURCE
res.send(csv);  // SINK (within same function) - DETECTED!
```

This is why all 10 findings have `path_length: 2` and `type: "direct_use"`.

---

## Fix Strategy

### Option 1: Normalize Function Names Before Lookup (RECOMMENDED)

**Location**: `theauditor/taint/cfg_integration.py` (PathAnalyzer.__init__)

Add function name normalization before CFG lookup:

```python
def __init__(self, cursor, file_path, function_name):
    self.file_path = file_path
    # STRIP object/class prefix for CFG lookup
    self.function_name = self._normalize_function_name(function_name)
    # ... rest of init

def _normalize_function_name(self, func_name: str) -> str:
    """Strip object/class prefix for CFG lookup.

    Examples:
        'accountService.createAccount' → 'createAccount'
        'BatchController.constructor' → 'constructor'
        'ApiService.setupInterceptors' → 'setupInterceptors'
    """
    if '.' in func_name:
        return func_name.split('.')[-1]
    return func_name
```

### Option 2: Change _analyze_without_cfg Fallback

**Location**: `theauditor/taint/interprocedural_cfg.py:481-483`

Make fallback CONSERVATIVE (assume taint propagates):

```python
# OLD (WRONG):
effect.param_effects[param] = 'unmodified'  # Kills taint

# NEW (CONSERVATIVE):
effect.param_effects[param] = 'tainted'  # Allows taint to continue
effect.return_tainted = True  # Conservative: assume return is tainted
```

**Rationale**: It's better to have false positives than miss real vulnerabilities.

### Option 3: Fix Indexer to Store Fully Qualified Names in CFG

**NOT RECOMMENDED** - Would require schema migration and re-indexing all projects.

---

## Verification Plan

1. **Implement Fix #1** (normalize function names)
2. **Re-run taint analysis** with debug flags:
   ```bash
   export THEAUDITOR_TAINT_DEBUG=1
   aud taint-analyze --db .pf/repo_index.db
   ```
3. **Expected changes**:
   - Debug output shows: `[INTER-CFG] PathAnalyzer initialized for createAccount` (SUCCESS)
   - Effect shows: `params={'arg0': 'tainted'}` (PROPAGATES)
   - Runtime increases to ~30 seconds (doing real work)
   - Finding count increases to 50-200+ (multi-hop flows detected)

4. **Validate with known vulnerable path**:
   ```
   backend/src/controllers/account.controller.ts:34 (req.body)
   → accountService.createAccount(userData)
   → backend/src/services/account.service.ts (data parameter)
   → db.execute() / ORM query
   ```

---

## Additional Issues Found

### 1. NULL callee_file_path (25.7% of calls)

**Impact**: Inter-procedural analysis skips these calls entirely.

**Evidence**:
```python
# interprocedural.py:128-131
if not callee_file_path:
    if debug:
        print(f"WARNING: Could not resolve file for call to '{callee_func}'")
    continue  # Skip calls we cannot resolve
```

**Triage**: Check if any LOCAL function calls have NULL callee_file_path (indexer bug) vs only EXTERNAL framework calls (expected).

### 2. Simplified CFG Path Tracing

**Location**: `theauditor/taint/interprocedural_cfg.py:391-393`

```python
# Simplified path check
if block_id <= exit_block_id:  # <-- NOT PROPER CFG TRAVERSAL!
    current_state = analyzer._process_block_for_assignments(current_state, block)
```

**Comment in code**:
```python
# This is simplified - real implementation would
# follow actual CFG paths
```

**Impact**: Even when CFG is found, path analysis may not be accurate.

---

## Confidence Level: **CRITICAL - 99% Certain**

**Verified facts**:
- ✅ Database has CFG data for service functions
- ✅ CFG lookup fails due to function name mismatch
- ✅ Fallback returns `'unmodified'` (confirmed in debug logs)
- ✅ All findings are direct-use only (path_length: 2)
- ✅ Runtime is suspiciously fast (4.7s vs expected ~30s)

**Recommended action**: **IMPLEMENT FIX IMMEDIATELY** - This is a critical feature regression.

---

## Next Steps

1. **Implement function name normalization** (Option 1)
2. **Run full test suite** to ensure no regressions
3. **Re-analyze plant project** and verify multi-hop findings
4. **Update documentation** about function naming conventions
5. **Add unit test** for function name normalization
6. **Consider caching PathAnalyzer instances** to avoid repeated CFG lookups

---

**END OF REPORT**
