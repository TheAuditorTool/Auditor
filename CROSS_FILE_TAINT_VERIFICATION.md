# Cross-File Multi-Hop Taint Detection - Pre-Implementation Verification Plan

**Document Version:** 1.0
**Created:** 2025-10-17
**Status:** AWAITING EXECUTION
**Protocol:** teamsop.md v4.20 Template C-4.20

---

## Objective

Verify why cross-file multi-hop taint detection (Controller → Service → ORM) fails to detect vulnerabilities despite all data existing in database.

**Test Case:**
- Source: `backend/src/controllers/account.controller.ts:34` - `req.body`
- Call: `accountService.createAccount(req.body)`
- Sink: `backend/src/services/account.service.ts:93` - `Account.create()`
- Expected: 1 taint path found
- Actual: 0 taint paths found

---

## Phase 1: Verification Hypotheses

### H1: Database Contains All Required Data

**H1.1** - Source exists in `variable_usage` table
```sql
SELECT * FROM variable_usage
WHERE file='backend/src/controllers/account.controller.ts'
  AND variable_name='req.body'
  AND line=34;
```
**Expected:** 1 row
**Status:** ⏳ PENDING

**H1.2** - Function call exists in `function_call_args` table
```sql
SELECT * FROM function_call_args
WHERE file='backend/src/controllers/account.controller.ts'
  AND callee_function='accountService.createAccount'
  AND line=34;
```
**Expected:** 1 row with `argument_expr` containing "req.body"
**Status:** ⏳ PENDING

**H1.3** - Symbol definition exists for target function
```sql
SELECT * FROM symbols
WHERE name LIKE '%createAccount%'
  AND type='function';
```
**Expected:** 1+ rows, one pointing to `account.service.ts`
**Status:** ⏳ PENDING

**H1.4** - Sink exists in `orm_queries` table
```sql
SELECT * FROM orm_queries
WHERE file='backend/src/services/account.service.ts'
  AND line=93;
```
**Expected:** 1 row with `query_type='create'`
**Status:** ⏳ PENDING

---

### H2: Taint Core Finds Source

**H2.1** - `find_taint_sources()` returns source
```python
# theauditor/taint/database.py:find_taint_sources()
# Query: variable_usage WHERE variable_name IN ('req.body', 'req.query', ...)
```
**Expected:** Source dict with `file`, `line`, `pattern`
**Verification Method:** Add debug print after line 219 in `propagation.py`
**Status:** ⏳ PENDING

**H2.2** - `get_containing_function()` finds source function
```python
# theauditor/taint/database.py:get_containing_function()
# Query: symbols WHERE type='function' AND path=file AND line<=source_line
```
**Expected:** Function dict with `name`, `file`, `line`
**Verification Method:** Add debug print after line 238 in `core.py`
**Status:** ⏳ PENDING

---

### H3: Inter-Procedural Analysis Invoked

**H3.1** - `use_cfg=True` flag set in call chain
```python
# core.py:244 → propagation.py:97 (use_cfg parameter)
# propagation.py:426 → Should enter if block
```
**Expected:** `use_cfg=True` reaches `propagation.py:426`
**Verification Method:** Add debug print at line 428 in `propagation.py`
**Status:** ⏳ PENDING

**H3.2** - `trace_inter_procedural_flow_cfg()` called with all sinks
```python
# propagation.py:440 → interprocedural.py:285
```
**Expected:** Function called with `sinks` list containing cross-file sink
**Verification Method:** Add debug print at line 322 in `interprocedural.py`
**Status:** ⏳ PENDING

---

### H4: Worklist Initialization

**H4.1** - Worklist starts with source function and file
```python
# interprocedural.py:332
# worklist = [(source_file, source_function, {source_var: True}, 0, [])]
```
**Expected:** Worklist contains entry for `account.controller.ts:createAccount`
**Verification Method:** Add debug print at line 334 after worklist init
**Status:** ⏳ PENDING

**H4.2** - Worklist loop executes
```python
# interprocedural.py:334 → while worklist
```
**Expected:** Loop executes at least once
**Verification Method:** Add debug print inside loop at line 352
**Status:** ⏳ PENDING

---

### H5: Symbol Lookup (CRITICAL FAILURE POINT)

**H5.1** - `function_call_args` query finds callee
```python
# interprocedural.py:404-408
# Query: function_call_args WHERE file=? AND caller_function=?
```
**Expected:** Returns row with `callee_function='accountService.createAccount'`
**Verification Method:** Add debug print after line 418 with `all_calls` length
**Status:** ⏳ PENDING

**H5.2** - Instance name normalization
```python
# interprocedural.py:455-462
# normalize_to_class_name_cfg('accountService.createAccount')
# Expected output: 'AccountService.createAccount'
```
**Expected:** Correct capitalization normalization
**Verification Method:** Add debug print after line 462 showing before/after
**Status:** ⏳ PENDING

**H5.3** - First symbol query (normalized name)
```sql
-- interprocedural.py:465-467
SELECT path FROM symbols
WHERE name = 'AccountService.createAccount'
  AND type = 'function'
LIMIT 1;
```
**Expected:** Returns path to `account.service.ts` OR NULL
**Verification Method:** Add debug print after line 467 with result
**Status:** ⏳ PENDING

**H5.4** - Fallback symbol query (original name)
```sql
-- interprocedural.py:471-473
SELECT path FROM symbols
WHERE name = 'accountService.createAccount'
  AND type IN ('function', 'call', 'property')
  AND path != 'backend/src/controllers/account.controller.ts'
LIMIT 1;
```
**Expected:** Returns path to `account.service.ts` OR NULL
**Verification Method:** Add debug print after line 473 with result
**Status:** ⏳ PENDING

**H5.5** - Symbol not found handling
```python
# interprocedural.py:476-479
# if not callee_location: continue
```
**Expected:** If both queries fail, path abandoned with debug message
**Verification Method:** Add debug print at line 478 showing which query failed
**Status:** ⏳ PENDING

---

### H6: Worklist Population (Cross-File Transition)

**H6.1** - Callee file extracted correctly
```python
# interprocedural.py:481
# callee_file = callee_location[0].replace("\\", "/")
```
**Expected:** `callee_file = 'backend/src/services/account.service.ts'`
**Verification Method:** Add debug print after line 481 showing file paths
**Status:** ⏳ PENDING

**H6.2** - Cross-file transition detected
```python
# interprocedural.py:483-484
# if debug and callee_file != current_file
```
**Expected:** Debug message shows file transition
**Verification Method:** Add debug print showing both file paths
**Status:** ⏳ PENDING

**H6.3** - New worklist entry created
```python
# interprocedural.py:518
# worklist.append((callee_file, callee_func, propagated_taint, depth + 1, new_call_path))
```
**Expected:** Worklist gains entry with `file='account.service.ts'`
**Verification Method:** Add debug print after line 518 showing worklist size and new entry
**Status:** ⏳ PENDING

---

### H7: Sink Detection in Service File

**H7.1** - Worklist processes service file entry
```python
# interprocedural.py:334 → Next iteration with callee entry
```
**Expected:** Loop processes `current_file='account.service.ts'`
**Verification Method:** Add debug print at line 352 showing current file
**Status:** ⏳ PENDING

**H7.2** - Sink loop checks service file sinks
```python
# interprocedural.py:356-361
# for sink in sinks:
#     sink_function = get_containing_function(cursor, sink)
```
**Expected:** Loop finds sink at line 93 in service file
**Verification Method:** Add debug print in loop showing sinks checked
**Status:** ⏳ PENDING

**H7.3** - Tainted variable reaches sink
```python
# interprocedural.py:365-372
# for tainted_var in taint_state:
#     cursor.execute(..., sink['line'], tainted_var)
```
**Expected:** Query finds `argument_expr` containing tainted param
**Verification Method:** Add debug print showing query results
**Status:** ⏳ PENDING

**H7.4** - Vulnerability reported
```python
# interprocedural.py:375-393
# TaintPath created and appended to paths
```
**Expected:** `paths.append(path_obj)` executes
**Verification Method:** Add debug print after line 393 showing paths length
**Status:** ⏳ PENDING

---

## Phase 2: Execution Plan

### Step 1: Database Verification (5 min)
Execute all H1 queries against Plant database:
```
C:\Users\santa\Desktop\plant\.pf\history\full\20251017_205234\repo_index.db
```

**Method:** Python script with sqlite3
**Output:** `H1_database_verification.txt`
**Pass Criteria:** All 4 queries return expected rows

---

### Step 2: Add Debug Instrumentation (10 min)

**File 1:** `theauditor/taint/propagation.py`
- Line 219: After `sources = find_taint_sources()` → Print source count
- Line 428: Inside `if use_cfg:` block → Print "Stage 3 activated"
- Line 454: After `inter_paths = trace_inter_procedural_flow_cfg()` → Print paths found

**File 2:** `theauditor/taint/interprocedural.py`
- Line 322: Top of `trace_inter_procedural_flow_cfg()` → Print entry with sink count
- Line 334: After worklist init → Print worklist initial state
- Line 352: Inside `while worklist:` → Print current depth/file/func
- Line 418: After `all_calls` query → Print calls found count
- Line 462: After normalization → Print before/after names
- Line 467: After first symbol query → Print result
- Line 473: After fallback query → Print result
- Line 481: After `callee_file` assignment → Print file paths
- Line 518: After worklist.append → Print worklist size and new entry
- Line 377: Inside vulnerability detection → Print when found

**Method:** Edit files with specific debug blocks
**Pass Criteria:** All debug points added with proper conditionals

---

### Step 3: Execute Instrumented Run (5 min)

```bash
cd C:\Users\santa\Desktop\plant
set THEAUDITOR_TAINT_DEBUG=1
aud taint-analyze > taint_debug_output.txt 2>&1
```

**Output:** `taint_debug_output.txt` with all debug messages
**Pass Criteria:** File captures complete execution trace

---

### Step 4: Trace Analysis (10 min)

Parse `taint_debug_output.txt` and map to hypotheses:
- Identify last successful hypothesis
- Identify first failing hypothesis
- Extract exact failure point (file:line)
- Capture exact values at failure (variable names, query results)

**Output:** `failure_point_analysis.md`
**Pass Criteria:** Exact line number and failure reason identified

---

### Step 5: Root Cause Determination (10 min)

Based on failure point, determine ONE of:
1. **Symbol Lookup Failure** - Queries return NULL (H5.3 or H5.4 fail)
2. **Worklist Not Populated** - Cross-file entry never added (H6.3 fails)
3. **Sink Not Detected** - Service file sink not checked (H7.2 fails)
4. **Taint Not Propagated** - Variable mapping breaks (H7.3 fails)
5. **Other** - Unexpected failure mode

**Output:** Root cause statement with evidence
**Pass Criteria:** Single root cause identified with file:line evidence

---

## Phase 3: Fix Implementation (Deferred)

**NO IMPLEMENTATION UNTIL PHASE 2 COMPLETE**

Once root cause identified, create fix design:
- Exact lines to modify
- Before/after code
- Test to verify fix

---

## Verification Deliverables

1. `H1_database_verification.txt` - SQL query results
2. Instrumented files with debug code
3. `taint_debug_output.txt` - Complete execution trace
4. `failure_point_analysis.md` - Hypothesis results mapped to trace
5. Root cause statement - Single sentence with file:line:reason

---

## Execution Checklist

- [ ] Phase 1 complete - All hypotheses documented
- [ ] Phase 2 Step 1 - Database queries executed
- [ ] Phase 2 Step 2 - Debug instrumentation added
- [ ] Phase 2 Step 3 - Instrumented run completed
- [ ] Phase 2 Step 4 - Trace analyzed and mapped to hypotheses
- [ ] Phase 2 Step 5 - Root cause determined with evidence
- [ ] Phase 3 - Fix designed (only after Phase 2 complete)

**Current Status:** AWAITING EXECUTION
**Next Action:** Execute Phase 2 Step 1 database verification
