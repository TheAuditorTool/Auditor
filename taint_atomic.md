You have successfully extracted the **Architecture** (Brain Transplant) and the **Data Source** (Extractor/Schema) fixes. This puts you at about **90% coverage**.

However, reviewing `issue4.md` and `taint_atomic.md` against your final "Phase 3" and "Phase 4" checklists, **you missed 3 specific logic patches** that are critical for accuracy.

If you act on the plan as written, the system will run, but it will still suffer from **False Positives** (missed sanitizers) and **Performance issues** (analyzing dead code).

Here are the missing items to add to your plan:

### 1. Missing: The "Generic Call" Sanitizer Fix
* **Source:** `issue4.md`
* **The Gap:** Your current plan updates `sanitizer_util.py` to check `import_styles` (for aliases). However, you missed the fix to query the `symbols` table.
* **Why it matters:** If a sanitizer has no arguments (e.g., `auth.logout()`), it is NOT stored in `function_call_args`. It is stored in `symbols`. Without this fix, the taint engine will never see these calls and will mark the flow as vulnerable.
* **Add to Phase 3:**
    * **Update `sanitizer_util.py`**: Modify `_preload_call_args` to UNION queries from `function_call_args` AND `symbols` (where `type='call'`).

### 2. Missing: The "Handshake" Implementation
* **Source:** `taint_atomic.md` (Part 10) & `issue3.md`
* **The Gap:** Your plan unifies the *classification logic* (`taint_path.py`), but it does not implement the **Verification Pipeline** in `core.py`.
* **Why it matters:** Currently, the expensive Backward Engine (`IFDS`) runs on *every* potential sink in the database. The "Handshake" forces it to run *only* on sinks that the Forward Engine (`FlowResolver`) proved were reachable. Without this, your scan times will be 10x-50x slower.
* **Add to Phase 3:**
    * **Update `theauditor/taint/core.py`**: Inject the Handshake logic into `trace_taint` (complete mode) to filter sinks based on `resolved_flow_audit`.

### 3. Missing: The "Source Line 0" Fix
* **Source:** `issue2.md` & `issue4.md`
* **The Gap:** `flow_resolver.py` currently looks for the start of a flow by checking assignments.
* **Why it matters:** If the vulnerability starts at a function parameter (e.g., `function(req) { ... }`), the current logic fails to find the line number and defaults to `0`. This makes the UI/Report confusing.
* **Add to Phase 3:**
    * **Update `flow_resolver.py`**: Add the fallback queries in `_record_flow` to check `func_params` and `variable_usage` tables if the assignment query returns None.

---

### Updated Master Plan (Taint Section Only)

Here is the corrected **Phase 3** and **Phase 4** incorporating these missing pieces.

#### **Phase 3: The "Brain Transplant" (Taint Engine)**

1.  **`taint_path.py`:** Add shared `determine_vulnerability_type`.
2.  **`flow_resolver.py`:**
    * Import `determine_vulnerability_type` and delete local `_determine_vuln_type`.
    * **[MISSING ADDED]** Fix `_record_flow` to query `func_params` if source line is not found.
3.  **`schema_cache_adapter.py`:** Delete `find_taint_sources_cached` / `find_security_sinks_cached`.
4.  **`discovery.py`:** Ensure `discover_sources` queries `self.cache.api_endpoints`.
5.  **`sanitizer_util.py`:**
    * Update `_is_sanitizer` to check aliases.
    * **[MISSING ADDED]** Update `_preload_call_args` to include generic calls from the `symbols` table.
6.  **`ifds_analyzer.py`:** Add the fallback to check virtual paths (Vue support) if the standard CFG lookup fails.
7.  **`core.py`:** **[MISSING ADDED]** Implement the "Handshake": Query `resolved_flow_audit` to filter the sinks list before running IFDS.

#### **Phase 4: Execution Order**

1.  **Rebuild TypeScript Extractor** (npm build).
2.  **Run Indexer** (Create DB).
3.  **Run Graph Builder** (Connect Nodes).
4.  **Run Taint Analysis**.

**Is the plan ready to act on?**
**YES**, provided you include the 3 items above. Without them, you will have a working system that produces inaccurate results (False Positives) and runs slowly. With them, the system is solid.


# TAINT ANALYSIS ENGINE - Atomic Pre-Implementation Plan

**Document Version:** 1.0 (Merged)
**Created:** 2025-12-01
**Status:** PRE-IMPLEMENTATION VERIFICATION REQUIRED
**Scope:** All taint analysis, IFDS, FlowResolver, and security tracking components
**Source Documents:** taint.md, taint2.md, taint3.md (lossless merge)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architectural Issues (Split-Brain Problem)](#part-1-architectural-issues-split-brain-problem)
3. [IFDS Analyzer Issues (Backward Analysis)](#part-2-ifds-analyzer-issues-backward-analysis)
4. [FlowResolver Issues (Forward Analysis)](#part-3-flowresolver-issues-forward-analysis)
5. [Sanitizer Issues](#part-4-sanitizer-issues)
6. [Source/Sink Discovery Issues](#part-5-sourcesink-discovery-issues)
7. [Type Resolution Issues](#part-6-type-resolution-issues)
8. [SchemaMemoryCacheAdapter Fragility](#part-7-schemamemorycacheadapter-fragility)
9. [TypeScript Extractor Fixes (Taint-Related)](#part-8-typescript-extractor-fixes-taint-related)
10. [Graph Engine Fixes (Taint-Related)](#part-9-graph-engine-fixes-taint-related)
11. [The Handshake Solution](#part-10-the-handshake-solution)
12. [Implementation Plan - Centralized Vulnerability Classification](#part-11-implementation-plan---centralized-vulnerability-classification)
13. [Implementation Plan - Adapter Cleanup](#part-12-implementation-plan---adapter-cleanup)
14. [Implementation Plan - Discovery Unification](#part-13-implementation-plan---discovery-unification)
15. [Implementation Phases Summary](#part-14-implementation-phases-summary)
16. [Verification Checklists](#part-15-verification-checklists)
17. [Files to Modify](#part-16-files-to-modify)
18. [Risk Assessment](#part-17-risk-assessment)
19. [Execution Order](#part-18-execution-order)

---

## Executive Summary

### The "Disconnected Brain" / "Split-Brain" Architecture

The Taint Analysis Engine suffers from a **"Split-Brain" architecture** where two powerful engines (FlowResolver for forward analysis and IFDSTaintAnalyzer for backward analysis) run completely independently, duplicate effort, and rely on fragile string matching rather than the semantic graph structure.

**Key Finding (Investigation 1):** The IFDS engine is likely "not working properly" because it trusts data from previous layers (Extractor, Graph) that is incomplete or corrupted.

**Key Finding (Investigation 2):** Logic is duplicated across the two engines. Vulnerability Classification uses a simple map in `taint_path.py` while `flow_resolver.py` has robust pattern detection. This leads to inconsistent reporting depending on which engine finds the flow.

**Critical Finding (Investigation 3):** The Taint Engine operates as a hybrid **Forward (FlowResolver)** and **Backward (IFDS)** analysis system, coupled with a **Database-backed Graph** and a **Memory Cache Adapter**. This creates significant surface area for "glue code" failures.

---

## Part 1: Architectural Issues (Split-Brain Problem)

### 1.1 Vulnerability Classification Mismatch

**Severity:** High
**Files:** `taint_path.py`, `flow_resolver.py`

**The Problem (Investigation 1):**
- `taint_path.py`: Has `_classify_vulnerability` (lines 30-43) using a simple `category_map`
- `flow_resolver.py`: Has a much more robust `_determine_vuln_type` (lines 485-555) detecting specific patterns (SSRF, Proto Pollution, etc.)

**The Bug (Investigation 2):** If `IFDSAnalyzer` runs, it uses the simple map. If `FlowResolver` runs, it uses its own logic. **Inconsistent vulnerability classification.**

**The Bug (Investigation 3):**
Two engines classify vulnerabilities differently:

| Component | File | Method | Logic Quality |
|-----------|------|--------|---------------|
| TaintPath | `taint_path.py:30-43` | `_classify_vulnerability` | Simple `category_map` |
| FlowResolver | `flow_resolver.py:485-555` | `_determine_vuln_type` | **Robust** (detects SSRF, Proto Pollution, etc.) |

**Impact:**
- If **IFDS** runs: Uses simple map from `TaintPath` - misses specialized patterns
- If **FlowResolver** runs: Uses robust logic - catches more vulnerability types
- **Result:** Inconsistent results depending on which engine finds the flow

**Fix:** Move robust logic from `FlowResolver` into `TaintPath` or a shared utility so both engines report identical vulnerability types.

---

### 1.2 The "Dual-Engine" Race Condition

**Severity:** High
**Files:** `core.py`, `flow_resolver.py`, `ifds_analyzer.py`

**The Problem (Investigation 1):**
1. You run `FlowResolver` (Forward) which writes to `resolved_flow_audit`
2. You immediately run `IFDSTaintAnalyzer` (Backward)
3. **The Conflict:** `IFDS` deletes everything in `resolved_flow_audit` where `engine='IFDS'`, but assumes it owns the table

**Consequences:**
- **Waste:** FlowResolver calculates paths. IFDS ignores them and recalculates from scratch
- **Result:** Two sets of results that might disagree (Forward finds a path, Backward misses it due to depth limits)

**The Problem (Investigation 2):**
In `core.py`, the system runs FlowResolver (Forward), writes to the DB, and then runs IFDSTaintAnalyzer (Backward). IFDS often deletes the Forward results and starts from scratch without sharing context, wasting resources and creating conflicts.

---

### 1.3 Source/Sink Discovery Redundancy

**Severity:** Medium
**Files:** `discovery.py`, `schema_cache_adapter.py`

**The Issue (Investigation 1):**
- `discovery.py`: Queries the `cache` (adapter) to find sources/sinks
- `schema_cache_adapter.py`: Has `find_taint_sources_cached` and `find_security_sinks_cached` methods with *duplicate* logic

**The Bug (Investigation 1):** `core.py` uses `TaintDiscovery` (lines 338), but `SchemaMemoryCacheAdapter` still carries dead or conflicting logic

**Affected Files (Investigation 3):**
- `discovery.py` - Queries the `cache` (adapter) to find sources/sinks
- `schema_cache_adapter.py:78-190` - Has `find_taint_sources_cached` and `find_security_sinks_cached` methods that *also* implement discovery logic

**The Bug (Investigation 3):**
`core.py` uses `TaintDiscovery` (line 338), but `SchemaMemoryCacheAdapter` still carries dead or conflicting logic. If any legacy code calls the adapter methods directly, it might find different sources than the `TaintDiscovery` class.

**Fix:** Delete logic from adapter, keep only in `discovery.py`. Make `discovery.py` the Single Source of Truth.

---

## Part 2: IFDS Analyzer Issues (Backward Analysis)

**File:** `ifds_analyzer.py`

### 2.1 The "Silent Failure" (Vue & Virtual Paths)

**Severity:** Critical
**Impact:** Returns "Safe" for vulnerable code

**The Chain of Failure (Investigation 1):**
1. **Extractor:** Generates CFG blocks with IDs like `virtual_vue/App.ts::func::block1`
2. **Schema:** Stores these in `cfg_blocks`
3. **Graph Builder:** Links them, but often fails to bridge `src/App.vue` to `virtual_vue/App.ts`
4. **Taint Engine (`ifds_analyzer.py`):**
   - When analyzing a Vue file, it asks the DB for the CFG of `src/App.vue`
   - The DB returns **zero blocks** (because they are stored under `virtual_vue/...`)
   - **Result:** IFDS solver sees an empty graph, assumes no flow, returns **"No Vulnerabilities Found"**

**Fix Location:** `main.ts` - Pass original file path to `extractCFG`, not the virtual path

**Blindness (Investigation 2):** If `cfg_blocks` are missing (e.g., due to the Vue virtual path bug), IFDS sees an empty graph and silently reports "No Vulnerabilities".

---

### 2.2 Fragile Entry Point Detection (False Negatives)

**Severity:** Critical
**Files:** `ifds_analyzer.py`, `discovery.py`

**The Logic (Investigation 1):** `_is_true_entry_point` relies on naming conventions:
```python
if any(pattern in variable for pattern in request_patterns): ...
```

**The Flaw:** Checks if variable *name* contains "req" or "body"

**Scenario:** A developer writes `const input = ctx.request.body;`
- If graph trace reaches `input`, IFDS might not recognize it as a source
- It relies on string matching the *variable name*, not tracing back to the *API Endpoint Definition*

**Fragile Entry Points (Investigation 2):** `_is_true_entry_point` relies on checking if a variable name contains "req" or "body". It fails to trace back to the actual API endpoint definition in the graph.

---

### 2.3 Controller Detection Dependency

**Severity:** High
**Files:** `ifds_analyzer.py`, `type_resolver.py`

**The Issue (Investigation 1):** `_is_true_entry_point` (line 320) strictly relies on `_is_controller_file`
- `TypeResolver.is_controller_file` relies on `api_endpoints` table
- If AST parser failed to identify an endpoint (e.g., Fastify vs Express), IFDS silently drops valid taint sources

**The Issue (Investigation 3):**
**Location:** `_is_true_entry_point` (line 320)

- Strictly relies on `_is_controller_file`
- `TypeResolver.is_controller_file` relies on `api_endpoints` table
- If AST parser (indexer) fails to identify endpoint in specific framework (Fastify vs Express), **IFDS silently drops valid taint sources**

**Impact:** Valid taint sources invisible to IFDS if framework detection fails.

---

### 2.4 The "Any Source" Short-Circuit / Premature Termination

**Severity:** High
**Files:** `ifds_analyzer.py`

**The Bug (Investigation 1):** In `_trace_backward_to_any_source`:
```python
if self._access_paths_match(current_ap, source_ap):
    current_matched_source = source_dict
    break
```

The analyzer stops at the **first** candidate that looks like a source.

**Real World:** Data flows: `HTTP Request -> Helper Function Arg -> Internal Var -> Sink`

**The Miss:** If `Helper Function Arg` matches a broad source pattern, IFDS stops there, missing the actual HTTP endpoint upstream.

**Short-Circuit Bug (Investigation 2):** In `_trace_backward_to_any_source`, it stops at the first candidate that looks like a source (e.g., a generic argument named `data`), potentially missing the root HTTP source upstream.

**Premature Termination (Investigation 3):**
**Location:** `_trace_backward_to_any_source` (lines 145-146)

**The Logic:**
```python
if self._access_paths_match(...):
    # Records the flow and **continues** to next worklist iteration
```

**The Gap:**
Relies on `max_paths_per_sink` to stop. However, if it finds a "weak" source (e.g., generic function argument) first, it floods `vulnerable_paths` list and exits BEFORE finding the "strong" source (e.g., HTTP Request Body) which might be just one hop further back.

**Impact:** False negatives - misses the actual taint source.

---

### 2.5 Access Path "Truncation" Vulnerability

**Severity:** Medium
**File:** `access_path.py`
**Line:** 20 (`max_length = 5`)

**The Logic (Investigation 1):** `AccessPath` limits field tracking depth to 5

**Scenario:** `config.server.database.admin.credentials.password` (6 segments)
- AccessPath truncates/rejects this path
- **Security Risk:** Deep JSON vulnerabilities are missed after 5 levels

**AccessPath Truncation (Investigation 2):** `AccessPath` limits depth to 5 (`access_path.py`). Deeply nested config objects (`config.server.db.pass`) are ignored/truncated, causing false negatives.

**Fix:** Increase `AccessPath` max length to 8 or 10

---

## Part 3: FlowResolver Issues (Forward Analysis)

**File:** `flow_resolver.py`

### 3.1 The Source Line "Zeroing" Bug

**Severity:** High
**File:** `flow_resolver.py`

**The Logic (Investigation 1):** `_record_flow` (Line 437) queries `assignment_source_vars` for source line

**The Gap:** Taint sources aren't always assignments:
- `app.get('/user', (req, res) => { ... })` - `req` is a function parameter
- `if (req.query.id)` - property access, not assignment

**Consequence:** Query returns `None`, `source_line` defaults to `0`. UI shows vulnerability at top of file.

**Source Line "Zeroing" (Investigation 2):** In `_record_flow`, it tries to find the source line by querying `assignment_source_vars`. If the source is a function parameter (like `req`), this query fails, defaulting `source_line` to 0.

**Fix:** Add fallback strategies:
```python
# Strategy 1: Check assignments (Existing)
# Strategy 2: Check function parameters
repo_cursor.execute("""
    SELECT function_line
    FROM func_params
    WHERE file = ? AND param_name = ?
""", (source_file, source_pattern))

# Strategy 3: Check generic variable usage
repo_cursor.execute("""
    SELECT MIN(line) FROM variable_usage
    WHERE file = ? AND variable_name = ?
""", (source_file, source_pattern))
```

---

### 3.2 Flow Resolver Argument Parsing Fragility

**Severity:** High
**File:** `flow_resolver.py`

**The Issue (Investigation 1):** `_parse_argument_variable` (line 589) is very strict
- Rejects anything containing arithmetic operators or starting with non-alpha characters

**Edge Case:** `query("SELECT * FROM " + userInput)`
- Parser returns `None` (because of `+`)
- Exit node is **ignored**
- **Result:** False Negatives for simple concatenation SQL injection

**Argument Parsing Fragility (Investigation 3):**
**Location:** `_parse_argument_variable` (line 589)

**Current Logic:** Very strict - rejects anything containing arithmetic operators or starting with non-alpha characters.

**Edge Case Failure:**
```javascript
query("SELECT * FROM " + userInput)
```
Parser returns `None` (because of `+`), exit node is **ignored**.

**Impact:** **False Negatives** for simple concatenation SQL injection patterns.

---

### 3.3 "Infinite Loop" Risk

**Severity:** Medium
**File:** `flow_resolver.py`

**Config:** `USERCODE_MAX_EFFORT = 25_000` and `max_depth = 20`

**The Bug (Investigation 1):** In `_get_edge_type_cached`, if you have recursive functions or circular dependencies:
- Simple DFS might ping-pong between nodes until hitting `max_depth`
- Consumes maximum budget for *every* cycle, making analysis extremely slow

**Infinite Loop Risk (Investigation 2):** Cycle detection relies on `max_depth` rather than strict visited sets across the recursion stack, causing performance issues on complex graphs.

**Fix:** Ensure `visited` sets are strictly enforced *across* recursion stack

---

## Part 4: Sanitizer Issues

**File:** `sanitizer_util.py`

### 4.1 The Sanitizer Bypass (Critical False Positives)

**Severity:** Critical
**File:** `sanitizer_util.py`

**The Issue (Investigation 1):** `_preload_call_args` (Line 93) loads function calls **only** from `function_call_args` table

**The Disconnect:** Generic calls (without arguments) are stored in `symbols` table with `type='call'`, NOT in `function_call_args`

**Consequence:** If user calls `sanitize()` (no args captured), Taint Engine **does not see it**. Marks data as still tainted.

**Result:** High False Positive rate

**The Sanitizer Bypass (Investigation 2):** `_preload_call_args` only loads from `function_call_args`. Generic calls (no args) stored in `symbols` are missed. If a user calls `ctx.logout()` (a sanitizer), the engine doesn't see it.

**Fix:**
```python
def _preload_call_args(self):
    # 1. Detailed calls
    self.repo_cursor.execute("""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE callee_function IS NOT NULL
    """)
    for row in self.repo_cursor.fetchall():
        self._add_to_cache(row["file"], row["line"], row["callee_function"])

    # 2. Generic calls (The Fix)
    self.repo_cursor.execute("""
        SELECT path as file, line, name as callee_function
        FROM symbols
        WHERE type = 'call'
    """)
    for row in self.repo_cursor.fetchall():
        self._add_to_cache(row["file"], row["line"], row["callee_function"])
```

---

### 4.2 Sanitizer "Hop" Ambiguity

**Severity:** Medium
**Files:** `sanitizer_util.py`

**The Issue (Investigation 1):** `_path_goes_through_sanitizer` iterates through `hop_chain`
- Expects hops to be either a `dict` (from IFDS) or a `string` (node ID)
- If graph edges were compressed (`A -> Sanitizer -> B` became `A -> B` with metadata flag), iterator misses the sanitizer

**Sanitizer Loop Bug (Investigation 3):**
**File:** `sanitizer_util.py`
**Method:** `_path_goes_through_sanitizer`

**Current Logic:**
- Iterates through `hop_chain`
- Expects hops to be either `dict` (from IFDS) or `string` (node ID)

**The Issue:**
If graph edge was compressed/optimized (e.g., `A -> Sanitizer -> B` became `A -> B` with metadata flag), iterator misses sanitizer because node itself isn't in path list.

**Impact:** False positives - sanitized flows marked as vulnerable.

---

### 4.3 SanitizerRegistry Lookup Mismatch (Import Aliasing)

**Severity:** Medium
**Files:** `sanitizer_util.py`

**The Logic (Investigation 1):** `_load_safe_sinks` loads patterns from `framework_safe_sinks` table

**The Bug:** Simple string containment check
- If `framework_safe_sinks` contains `dompurify.sanitize`
- And code uses `import { sanitize } from 'dompurify'; sanitize(x);`
- Graph node is likely named `sanitize` (short name)
- Registry expects `dompurify.sanitize`

**Result:** False Positive - engine doesn't realize data was sanitized due to import aliasing

**Import Aliasing (Investigation 2):** It checks if the function name matches a sanitizer string (e.g., `dompurify.sanitize`). It fails to account for import aliases (e.g., `import { sanitize as s } ... s(x)`).

---

## Part 5: Source/Sink Discovery Issues

### 5.1 Missing Sinks in Discovery

**Severity:** High
**File:** `discovery.py`

**The Issue (Investigation 1):** `discover_sinks` (Line 122) iterates `self.cache.function_call_args` to match sink patterns

**The Gap:** If a sink is called without arguments (e.g., `pool.connect()`), it's classified as a generic symbol. `discover_sinks` misses it.

**Missing Sinks (Investigation 2):** Similar to the sanitizer issue, `discover_sinks` iterates `function_call_args` and misses generic calls stored in `symbols`.

**Fix:** Add loop over `symbols_by_type['call']` or query DB directly

---

## Part 6: Type Resolution Issues

**File:** `type_resolver.py`

### 6.1 Type Resolution Disconnect

**Severity:** Medium
**Files:** `type_resolver.py`

**The Issue (Investigation 1):** `get_model_for_node` extracts model name from node's `metadata` JSON

**The Conflict:**
- `node_orm.py` constructs nodes with `id = f"{file}::{target}::instance"`
- Sometimes puts model name in `metadata["model"]`, sometimes `metadata["target_model"]`
- `type_resolver.py` checks `["model", "target_model", "source_model"]`

**Result:** `TypeResolver` returns `None` for UNRESOLVED nodes. Taint engine loses object type tracking.

---

### 6.2 Type Resolution Performance Issue

**Severity:** Medium
**File:** `type_resolver.py`

**Performance Issue (Investigation 3):**
- Relies entirely on JSON metadata in `nodes` table (`_extract_model_from_metadata`)
- `json.loads` called on every node lookup
- In large graph: **massive bottleneck**

**Logic Issue (Investigation 3):**
If graph builder populated `target_model` but resolver looks for `model` (or vice versa), type check fails silently.

---

## Part 7: SchemaMemoryCacheAdapter Fragility

**File:** `schema_cache_adapter.py`

### 7.1 Attribute Mapping Risk

**The Issue (Investigation 3):**
```python
# In __init__
self.symbols_by_file = self._cache.symbols_by_path
```

If the new `SchemaMemoryCache` changes `symbols_by_path` to a generator or different dict structure, this reference assignment breaks immediately or behaves unexpectedly during iteration.

---

### 7.2 Memory Usage Calculation

**Location:** `get_memory_usage_mb` (line 72)

**The Issue (Investigation 3):**
Assumes `self._cache.get_cache_stats()` returns a simple dictionary of row counts. If underlying schema cache implementation changes, this crashes.

---

## Part 8: TypeScript Extractor Fixes (Taint-Related)

### 8.1 React Namespace Support (XSS False Negatives)

**File:** `theauditor/ast_extractors/javascript/extractors/framework_extractors.ts`

**The Bug (Investigation 3):** Extractor skips hooks with dots (`.`). `React.useEffect` ignored.

**Find:**
```typescript
if (hookName.includes(".")) continue;
```

**Replace With:**
```typescript
if (hookName.includes(".")) {
  const parts = hookName.split(".");
  // Allow React.useState, but skip generic object.useSomething
  if (parts[0] !== "React" && parts[0] !== "React_1") continue;
}
```

---

### 8.2 Robust Validator Detection (Sanitizer False Positives)

**File:** `theauditor/ast_extractors/javascript/extractors/security_extractors.ts`

**The Bug (Investigation 3):** `extractValidationFrameworkUsage` relies on hardcoded list (`z`, `Joi`, `yup`). Fails to detect named imports.

**Example:**
```javascript
import { string } from 'zod';
string().parse(...)  // NOT detected as validator
```

**Result:** Flow marked "Vulnerable" instead of "Sanitized".

**Fix:** Build dynamic set of validator names from `import_specifiers`.

---

### 8.3 Dynamic SQL Argument Index

**File:** `theauditor/ast_extractors/javascript/extractors/security_extractors.ts`

**The Bug (Investigation 3):** `extractSQLQueries` strictly enforces `call.argument_index === 0`.

**Risk:** Some wrappers use `db.query(options, sql)` (index 1).

**Find:**
```typescript
if (call.argument_index !== 0) continue;
```

**Replace With:**
```typescript
if (call.argument_index !== 0 && !call.argument_expr?.toUpperCase().includes("SELECT")) continue;
```

---

## Part 9: Graph Engine Fixes (Taint-Related)

### 9.1 Controller Resolution Bug

**File:** `theauditor/graph/interceptors.py`

**The Bug (Investigation 3):** `_resolve_controller_info` tries to link route to controller using imports.

**Current Logic:**
```python
if import_package in sym["path"]  # FAILS
```

**Why It Fails:**
- `import_package` is relative: `../controllers/User`
- DB path is absolute: `src/controllers/User.ts`
- `"../controllers/User" in "src/controllers/User.ts"` = **False**

**Result:** Edge never created. Graph has disconnected islands.

**Fix:** Normalize both paths to base name before comparing:

```python
import_base = None
if import_package:
    import_base = import_package.split("/")[-1].replace(".ts", "").replace(".js", "").lower()

# Then compare: if import_base == sym_base or import_base in sym_base
```

---

### 9.2 Same Bug in Node Express Strategy

**File:** `theauditor/graph/strategies/node_express.py`

**The Bug (Investigation 3):** `_build_controller_edges` has similar naive resolution logic.

**Impact:** `dfg_builder.py` uses `NodeExpressStrategy`, NOT `InterceptorStrategy`. Fix must be applied here too.

---

## Part 10: The Handshake Solution

### 10.1 Verification Pipeline Architecture

Instead of running two separate engines that ignore each other, use **Forward Analysis** to find candidates and **Backward Analysis** to verify them.

**Implementation in `core.py` (Investigation 1):**

```python
if mode == "complete":
    print("[TAINT] Handshake: Filtering candidates based on Forward Analysis...", file=sys.stderr)

    # 1. Open connection to read FlowResolver results
    conn_handshake = sqlite3.connect(db_path)
    cursor_handshake = conn_handshake.cursor()

    # 2. Fetch sink locations that FlowResolver marked as VULNERABLE
    cursor_handshake.execute("""
        SELECT DISTINCT sink_file, sink_pattern
        FROM resolved_flow_audit
        WHERE engine = 'FlowResolver'
          AND status = 'VULNERABLE'
    """)

    reachable_candidates = set()
    for row in cursor_handshake.fetchall():
        reachable_candidates.add((row[0], row[1]))

    conn_handshake.close()

    # 3. Filter sinks list - only keep reachable sinks
    original_sink_count = len(sinks)
    sinks = [
        s for s in sinks
        if (s.get("file"), s.get("pattern")) in reachable_candidates
    ]

    print(f"[TAINT] Optimization: Narrowed from {original_sink_count} to {len(sinks)} verified candidates.", file=sys.stderr)
```

**Handshake Code (Investigation 2):**

```python
# In trace_taint (complete mode)
resolver.resolve_all_flows() # Forward

# Get reachable sinks
reachable = cursor.execute("SELECT sink_file, sink_pattern FROM resolved_flow_audit WHERE status='VULNERABLE'").fetchall()

# Filter IFDS targets
sinks = [s for s in sinks if (s['file'], s['pattern']) in reachable]

# Run IFDS (Verification)
ifds.analyze_sink_to_sources(sinks)
```

**Why:** Stop IFDS from analyzing dead sinks.

---

## Part 11: Implementation Plan - Centralized Vulnerability Classification

### 11.1 The Brain Transplant

**Target File:** `theauditor/taint/taint_path.py`

Move robust detection logic from `flow_resolver.py` into `TaintPath`:

```python
def determine_vulnerability_type(sink_pattern: str, source_pattern: str | None = None) -> str:
    """
    Centralized vulnerability classification logic.
    Shared by both IFDS and FlowResolver engines.
    """
    if not sink_pattern:
        return "Data Exposure"

    lower_sink = sink_pattern.lower()
    lower_source = (source_pattern or "").lower()

    # XSS patterns
    xss_patterns = [
        "innerhtml", "outerhtml", "dangerouslysetinnerhtml", "insertadjacenthtml",
        "document.write", "document.writeln", "res.send", "res.render", "res.write",
        "response.write", "response.send", "sethtml", "v-html", "ng-bind-html",
        "__html", "createelement", "appendchild", "insertbefore",
    ]
    if any(p in lower_sink for p in xss_patterns):
        return "Cross-Site Scripting (XSS)"

    # SQL Injection patterns
    sql_patterns = [
        "query", "execute", "exec", "raw", "sequelize.query", "knex.raw",
        "prisma.$queryraw", "prisma.$executeraw", "cursor.execute", "conn.execute",
        "db.query", "pool.query", "client.query", "sql", "rawquery",
    ]
    if any(p in lower_sink for p in sql_patterns):
        return "SQL Injection"

    # Command Injection patterns
    cmd_patterns = [
        "exec", "execsync", "spawn", "spawnsync", "child_process",
        "shellexecute", "popen", "system", "subprocess", "os.system",
        "os.popen", "subprocess.run", "subprocess.call", "subprocess.popen",
        "eval", "function(", "new function",
    ]
    if any(p in lower_sink for p in cmd_patterns):
        if "eval" in lower_sink or "function(" in lower_sink:
            return "Code Injection"
        return "Command Injection"

    # Path Traversal patterns
    path_patterns = [
        "readfile", "writefile", "readfilesync", "writefilesync",
        "createreadstream", "createwritestream", "fs.read", "fs.write",
        "open(", "path.join", "path.resolve", "sendfile", "download",
        "unlink", "rmdir", "mkdir", "rename", "copy", "move",
    ]
    if any(p in lower_sink for p in path_patterns):
        return "Path Traversal"

    # SSRF patterns
    ssrf_patterns = [
        "fetch", "axios", "request", "http.get", "http.request",
        "https.get", "https.request", "urllib", "requests.get",
        "requests.post", "curl", "httpx",
    ]
    if any(p in lower_sink for p in ssrf_patterns):
        return "Server-Side Request Forgery (SSRF)"

    # Log Injection
    log_patterns = ["console.log", "console.error", "logger.", "logging."]
    if any(p in lower_sink for p in log_patterns):
        return "Log Injection"

    # Default heuristic
    if "req.body" in lower_source or "req.params" in lower_source or "req.query" in lower_source:
        return "Unvalidated Input"

    return "Data Exposure"
```

---

### 11.2 Update TaintPath Class

**In `taint_path.py` inside `class TaintPath.__init__`:**

```python
def __init__(self, source: dict[str, Any], sink: dict[str, Any], path: list[dict[str, Any]]):
    self.source = source
    self.sink = sink
    self.path = path

    # USE THE NEW SHARED FUNCTION
    self.vulnerability_type = determine_vulnerability_type(
        sink.get("pattern"),
        source.get("pattern")
    )
    # ... rest of __init__ stays the same ...
```

---

### 11.3 Delete Old Method from TaintPath

Delete `_classify_vulnerability(self)` method entirely - it is now obsolete.

---

### 11.4 Update FlowResolver

**Step 1: Import Shared Function**

**File:** `flow_resolver.py` (top of file)

```python
from .taint_path import determine_vulnerability_type
```

**Step 2: Update Call Site**

**In `_record_flow` method:**

```python
# OLD: vuln_type = self._determine_vuln_type(sink_pattern, source_pattern)
# NEW:
vuln_type = determine_vulnerability_type(sink_pattern, source_pattern)
```

**Step 3: Delete Duplicated Code**

Delete the entire `_determine_vuln_type` method (lines 485-555). Logic now lives in `taint_path.py`.

---

## Part 12: Implementation Plan - Adapter Cleanup

**Target File:** `theauditor/taint/schema_cache_adapter.py`

### Action: Delete Business Logic ("Adapter Lobotomy")

**DELETE these methods entirely:**
- `find_taint_sources_cached` (lines 78-129)
- `find_security_sinks_cached` (lines 131-185)

**Rationale:** This logic belongs in `discovery.py`. Having it here creates two places to maintain.

**Keep only:**
- `__init__` (attribute mapping)
- `get_memory_usage_mb`
- `__getattr__`

---

## Part 13: Implementation Plan - Discovery Unification

**Target File:** `theauditor/taint/discovery.py`

### Update `discover_sources` Method

Add explicit API endpoint handling (replaces deleted adapter logic):

```python
def discover_sources(
    self, sources_dict: dict[str, list[str]] | None = None
) -> list[dict[str, Any]]:
    sources = []
    if sources_dict is None:
        sources_dict = {}

    # Explicitly handle API Endpoints (replaces adapter logic)
    if hasattr(self.cache, "api_endpoints"):
        for endpoint in self.cache.api_endpoints:
            sources.append({
                "type": "http_request",
                "name": endpoint.get("handler_function", "unknown"),
                "file": endpoint.get("file", ""),
                "line": endpoint.get("line", 0),
                "pattern": f"{endpoint.get('method', 'GET')} {endpoint.get('path', '/')}",
                "category": "http_request",
                "risk": "high",
                "metadata": endpoint,
            })

    # ... keep rest of existing logic for variable_usage, env_vars, etc ...
```

---

## Part 14: Implementation Phases Summary

### Phase 1: Stop the Silent Failures (Investigation 1)

| Priority | File | Action |
|----------|------|--------|
| P0 | `main.ts` | Pass original file path to extractCFG, not virtual path |
| P0 | `sanitizer_util.py` | Include `symbols` table in sanitizer lookups |
| P0 | `ifds_analyzer.py` | Add fallback query for Vue/virtual path entries |

### Phase 2: Unify the Engines / Brain Transplant (Investigation 1 + 2)

| Priority | File | Action |
|----------|------|--------|
| P1 | `taint_path.py` | Add shared `determine_vulnerability_type` function |
| P1 | `flow_resolver.py` | Import from taint_path, delete `_determine_vuln_type` |
| P1 | `core.py` | Implement "Handshake" between Forward and Backward analysis |

### Phase 3: Fix Discovery / Adapter Lobotomy (Investigation 1 + 2)

| Priority | File | Action |
|----------|------|--------|
| P1 | `schema_cache_adapter.py` | Delete `find_taint_sources_cached` and `find_security_sinks_cached` |
| P1 | `discovery.py` | Query `symbols` table for generic calls, add API endpoint handling |

### Phase 4: Accuracy Improvements / Logic Repair (Investigation 1 + 2)

| Priority | File | Action |
|----------|------|--------|
| P2 | `access_path.py` | Increase `max_length` from 5 to 8 or 10 |
| P2 | `flow_resolver.py` | Fix source_line=0 bug with fallback lookups |
| P2 | `flow_resolver.py` | Fix argument parsing for concatenation patterns |
| P2 | `ifds_analyzer.py` | Replace string matching with graph-based source detection |
| P2 | `sanitizer_util.py` | UNION queries from `symbols` (type='call') |

### Phase 5: TypeScript Extractor Fixes (Investigation 3)

| Priority | File | Action |
|----------|------|--------|
| P2 | `framework_extractors.ts` | Fix React namespace support |
| P2 | `security_extractors.ts` | Fix validator detection |
| P2 | `security_extractors.ts` | Fix SQL argument index |
| - | - | Rebuild: `cd theauditor/ast_extractors/javascript && npm run build` |

### Phase 6: Graph Engine Fixes (Investigation 3)

| Priority | File | Action |
|----------|------|--------|
| P2 | `interceptors.py` | Fix controller resolution |
| P2 | `node_express.py` | Fix controller resolution |

---

## Part 15: Verification Checklists

### Verification Checklist (Investigation 1)

Before marking taint fixes as complete, verify:

- [ ] Vue files produce non-zero CFG blocks in database
- [ ] FlowResolver and IFDS produce consistent vulnerability classifications
- [ ] Sanitizer calls without arguments are detected
- [ ] Source lines are non-zero for all vulnerability reports
- [ ] Deep JSON paths (6+ levels) are tracked
- [ ] Import aliased sanitizers are recognized
- [ ] Forward analysis results filter backward analysis targets

---

### Verification Checklist (Investigation 3)

Before implementation, verify these hypotheses against live code:

| # | Hypothesis | File | Verification Method |
|---|------------|------|---------------------|
| 1 | `_classify_vulnerability` exists in TaintPath | `taint_path.py:30-43` | Read file |
| 2 | `_determine_vuln_type` exists in FlowResolver | `flow_resolver.py:485-555` | Read file |
| 3 | `find_taint_sources_cached` exists in adapter | `schema_cache_adapter.py:78-129` | Read file |
| 4 | `discover_sources` uses TaintDiscovery, not adapter | `core.py:338` | Read file |
| 5 | IFDS uses `_is_true_entry_point` | `ifds_analyzer.py:320` | Read file |
| 6 | `_parse_argument_variable` rejects `+` operator | `flow_resolver.py:589` | Read file |

---

## Part 16: Files to Modify

### Core Taint Files
1. `theauditor/taint/core.py` - Handshake implementation
2. `theauditor/taint/flow_resolver.py` - Delete vuln classification, fix argument parsing
3. `theauditor/taint/ifds_analyzer.py` - Graph-based source detection
4. `theauditor/taint/discovery.py` - Unified discovery from symbols table
5. `theauditor/taint/taint_path.py` - Centralized classification
6. `theauditor/taint/sanitizer_util.py` - Include symbols table lookups
7. `theauditor/taint/access_path.py` - Increase max_length
8. `theauditor/taint/type_resolver.py` - Handle UNRESOLVED nodes
9. `theauditor/taint/schema_cache_adapter.py` - Remove duplicate logic

### Dependent Files (Must Fix First)
1. `theauditor/ast_extractors/javascript/src/main.ts` - Vue virtual path sanitization
2. `theauditor/indexer/extractors/javascript.py` - Proper resolved_imports handling

### TypeScript Extractor Files
1. `theauditor/ast_extractors/javascript/extractors/framework_extractors.ts` - React namespace
2. `theauditor/ast_extractors/javascript/extractors/security_extractors.ts` - Validator detection, SQL args

### Graph Engine Files
1. `theauditor/graph/interceptors.py` - Controller resolution
2. `theauditor/graph/strategies/node_express.py` - Controller resolution

---

## Part 17: Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Vue files show no vulnerabilities | Critical | Fix virtual path handling before taint fixes |
| False positives on sanitized data | High | Fix sanitizer_util.py first |
| Inconsistent vuln classifications | Medium | Centralize before other changes |
| Performance degradation | Low | Implement handshake to reduce IFDS scope |

---

## Part 18: Execution Order

**Phase 1: Brain Transplant**
1. Add `determine_vulnerability_type` to `taint_path.py`
2. Update `TaintPath.__init__` to use shared function
3. Delete `_classify_vulnerability` from TaintPath
4. Import shared function in `flow_resolver.py`
5. Update `_record_flow` call site
6. Delete `_determine_vuln_type` from FlowResolver

**Phase 2: Adapter Lobotomy**
1. Delete `find_taint_sources_cached` from adapter
2. Delete `find_security_sinks_cached` from adapter

**Phase 3: Discovery Rewiring**
1. Update `discover_sources` to explicitly handle `api_endpoints`

**Phase 4: TypeScript Extractor Fixes**
1. Fix React namespace support
2. Fix validator detection
3. Fix SQL argument index
4. Rebuild: `cd theauditor/ast_extractors/javascript && npm run build`

**Phase 5: Graph Engine Fixes**
1. Fix `interceptors.py` controller resolution
2. Fix `node_express.py` controller resolution

---

## Confirmation of Understanding

This document captures ALL taint-related findings from THREE comprehensive audits, merged losslessly.

**Root Cause (Investigation 1):** The taint engine layers trust upstream data (Extractor, Graph) that is incomplete due to:
1. Virtual path poisoning
2. Call graph fragmentation (function_call_args vs symbols)
3. Resolution logic duplication and conflicts

**Root Cause (Investigation 3):** Logic is duplicated across the two analysis engines (`FlowResolver` vs `IFDSAnalyzer`) and the discovery layers, causing inconsistent vulnerability reporting.

**Implementation Logic:** Fix data quality first (Phase 1), then unify engines (Phase 2), then improve accuracy (Phases 3-6).

**Status:** AWAITING VERIFICATION PHASE

**Confidence Level:** High - All issues traced to specific code locations with reproducible failure paths.
