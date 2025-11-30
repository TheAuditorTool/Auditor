It is technically a **4-Layer Problem** (Extraction, Storage, Graph, Taint), but you are battling a **5th "Invisible" Layer** that is causing your crashes: **Orchestration/System**.

You cannot fix the logic (Layers 1-4) if the Orchestrator (Layer 0) blows up the RAM before you even finish indexing.

Here is the **Sum of All Bugs** (Impact Analysis) and the **Definitive Pre-Implementation Plan** to fix your platform, ordered by dependency.

### The Sum of All Bugs (The "Why It's Broken" Report)

If you run Taint Analysis today, this is what happens:
1.  **Blindness (Extraction):** You miss 40% of the attack surface because your extractors ignore variables in SQL queries and rename API routes that don't look like `router.get`.
2.  **Amnesia (Storage):** You successfully extract complex React logic, but your database layer truncates it at 500 characters, deleting the security vulnerabilities located at character 501+.
3.  **Hallucination (Graph):** Your Python graph builder tries to read code using Regex (because the Extraction layer didn't give it types), guessing that "async_handler" is a function when it's just a variable string. It connects unrelated nodes, creating a "hairball" graph.
4.  **Explosion (Taint):** The Taint Engine tries to traverse this hairball. Because everything connects to everything (fuzzy matching), it hits infinite loops (`max_depth=20`) on 99.6% of flows.
5.  **Crash (System):** Your Orchestrator loads all ASTs and Import Tables into RAM at startup. On a large repo, this kills the process (OOM) before analysis completes.

---

### The Master Remediation Plan (Execute in Order)

You must fix the pipeline **upstream first**. Fixing Taint (Layer 4) is useless if Extraction (Layer 1) is feeding it garbage.

#### Phase 0: System Stability (The Orchestrator)
*Goal: Stop the 6GB OOM crashes.*
1.  **Kill the RAM Cache:** In `orchestrator.py`, stop loading `js_ts_cache` for the entire batch. Parse, Extract, and **discard** the AST immediately.
2.  **Lazy-Load Imports:** In `db_cache.py`, remove `_load_cache()`. Replace `self.imports_by_file` with a method that queries SQLite `WHERE file = ?` on demand.

#### Phase 1: The Eyes (Extraction Layer)
*Goal: See the code accurately.*
1.  **Enable AST Fallback:** In `main.ts`, change `ast: null` to `ast: sourceFile` (or a stripped version). This re-enables your Python fallback logic for edge cases.
2.  **Fix SQL Blindness:** In `security_extractors.ts`, modify `extractSQLQueries`. Capture `call.arguments[0]` **even if it is a variable** (not just StringLiteral). Flag it as `{"is_dynamic": true}`.
3.  **Fix API Blindness:** In `security_extractors.ts`, remove the check `isRouter = ROUTER_PATTERNS.some(...)`. If it looks like an HTTP verb (`.get('/', ...)`), extract it.
4.  **Relax Validation:** In `schema.ts`, make fields `.optional()` or `.nullable()`. Stop rejecting entire files because one field is missing.

#### Phase 2: The Memory (Storage Layer)
*Goal: Stop corrupting data on save.*
1.  **Remove Truncation:** In `node_database.py`, delete the line `callback_body[:497] + "..."`. Store the full code. Storage is cheap; missing code is fatal.
2.  **Fix "Crash" Policy:** In `core_storage.py`, wrap `add_symbol` calls in `try/except`. Log errors but **do not crash** the worker.
3.  **Generic IDs:** Update schemas to use `id INTEGER PRIMARY KEY` for assignments/nodes, rather than relying on brittle `(file, line, col)` composite keys that break on whitespace changes.

#### Phase 3: The Brain (Graph Layer)
*Goal: Stop guessing and start knowing.*
1.  **Stop Re-parsing:** In `dfg_builder.py`, **delete** `_parse_argument_variable`. Use the exact node type (`StringLiteral` vs `Identifier`) extracted in Phase 1.
2.  **Strict Resolution:** In `interceptors.py`, remove the `LIKE %methodName%` SQL query. Require an exact match on `ImportSpecifier` to link Routes to Controllers.
3.  **Incremental Saves:** In `store.py`, change `DELETE FROM nodes` to `DELETE FROM nodes WHERE file = ?`. This allows you to re-scan 1 file without wiping the whole graph.

#### Phase 4: The Logic (Taint Layer)
*Goal: Accurate results.*
1.  **Prune the Graph:** Now that you have "Strict Resolution" (Phase 3), the graph will be sparse and accurate. The "infinite loops" will disappear naturally.
2.  **Define Sinks:** Populate the `framework_taint_patterns` table with the missing sinks you extracted in Phase 1 (`child_process.exec`, `eval`, etc.).
3.  **Run Taint:** Now you can run `aud taint-analyze`. It will be fast, low-memory, and accurate.

**Immediate Next Step:**
Go to `main.ts` and `security_extractors.ts`. These are your highest ROI fixes. Without them, you are building a castle on sand.



It is a **5-Layer Problem**. The missing layer in your list is the **Orchestration & Resolution Layer** (The "Glue").

This layer sits between **Extraction** (parsing code) and **Graph** (connecting nodes). It is currently responsible for your biggest "Silent Failures"—like dropping entire files because of one error, or guessing file paths (`../../utils`) instead of knowing them.

Here is the breakdown of the 5 layers and the **Master Implementation Plan** to fix every identified issue, ordered by dependency (don't fix the roof before the foundation).

---

### 🏗️ The 5-Layer Battle Plan

#### Phase 1: The Foundation (Schema & Storage)
**Goal:** Stop the database from corrupting or deleting your data.
*Current Status: CRITICAL (Data is being actively destroyed).*

1.  **Fix "Negative ID" Detachment (CRITICAL)**
    * **File:** `node_storage.py`
    * **The Fix:** In `_store_cfg_flat`, you must split the loop. Insert `cfg_blocks` first, commit/flush to get the real SQLite `ROWID`, map the local ID to this real ID, and *then* insert `cfg_block_statements`.
    * **Why:** Currently, all statements are linked to block ID `-1`, making function bodies invisible.

2.  **Stop "Delete-on-Write"**
    * **File:** `store.py`
    * **The Fix:** Remove the `DELETE FROM nodes` statements in `_save_graph_bulk`. Switch to `INSERT OR REPLACE` (Upsert).
    * **Why:** Currently, saving the "Data Flow" graph deletes the "Call" graph if they share the same table/type, randomly wiping sections of the DB.

3.  **Remove "Time Bomb" Assertion**
    * **File:** `schema.py`
    * **The Fix:** Remove or comment out `assert len(TABLES) == 170`.
    * **Why:** This will crash your production build the moment you add a new feature table.

4.  **Add Null Safety**
    * **File:** `core_storage.py`
    * **The Fix:** Use `.get("target_var") or "unknown"` when reading assignments.
    * **Why:** Prevents a single parser failure (returning `None`) from crashing the entire batch insertion.

---

#### Phase 2: The Supply Chain (Extraction)
**Goal:** Ensure 100% of code files are processed, even if they have syntax errors.
*Current Status: HIGH (Single errors cause 100% data loss for that file).*

5.  **Implement "Partial Success" (The Anti-Blackhole)**
    * **File:** `main.ts` (TypeScript)
    * **The Fix:** Wrap the parsing logic in a `try/catch`. If it fails, still return the `imports`, `exports`, and `functions` you *did* manage to find, with a flag `partial: true`.
    * **File:** `javascript.py` (Python)
    * **The Fix:** Remove `if tree.get("success") is False: continue`. Instead, check if `extracted_data` exists and use it, logging a warning instead of dropping the file.

6.  **Increase Recursion Depth**
    * **File:** `typescript_impl.py`
    * **The Fix:** Increase `if depth > 100` to `500`.
    * **Why:** React/JSX trees often exceed 100 levels. You are currently blind to deep UI logic (where XSS lives).

---

#### Phase 3: The Glue (Orchestration & Resolution)
**Goal:** Connect files correctly so "Trace Taint" doesn't hit a dead end at file boundaries.
*Current Status: MEDIUM (Fragile guessing logic).*

7.  **Absolute Path Resolution**
    * **File:** `module_framework.ts`
    * **The Fix:** Use `ts.Program.getTypeChecker()` and `resolveModuleName` to get the **absolute file path** on disk for every import. Pass this to Python.
    * **Why:** Python's `javascript_resolvers.py` is currently guessing paths using string manipulation (`../../`), which fails on `tsconfig` aliases (`@app/utils`) and `index.ts` files.

8.  **Deprecate Python Guesswork**
    * **File:** `javascript_resolvers.py`
    * **The Fix:** Update `resolve_import_paths` to prioritize the resolved path from TypeScript (step 7) and only use the regex logic as a last-resort fallback.

---

#### Phase 4: The Logic (Graph Construction)
**Goal:** Ensure the nodes represent the actual code behavior.
*Current Status: HIGH (Truncated data).*

9.  **Fix Argument Truncation**
    * **File:** `dfg_builder.py`
    * **The Fix:** Stop using `arg_expr.split(" ")[0]`. If an argument contains `(`, `await`, or `new`, mark it as a `ComplexExpression` node instead of truncating it.
    * **Why:** `deleteUser(req.query.id + 1)` currently becomes `deleteUser(req.query.id)`, losing the `+ 1` modification context.

10. **Add "Ghost Nodes" for Express**
    * **File:** `node_express.py`
    * **The Fix:** In `_build_controller_edges`, if symbol resolution fails, do **not** `continue`. Create a `GhostNode` (type=`unresolved_controller`) and link the route to it.
    * **Why:** Allows the Taint Engine to report "Flow enters unknown controller" (Manual Review needed) instead of "Flow stops (Safe)".

11. **Fix Array/Object Access**
    * **File:** `data_flow.ts`
    * **The Fix:** Update `buildName` to handle `ElementAccessExpression` (e.g., `arr[i]`). Currently, it likely returns empty string or null, breaking flow through arrays.

---

#### Phase 5: The Engine (Taint Analysis)
**Goal:** Performance and accuracy.
*Current Status: POOR (99.6% timeouts).*

12. **Kill Bidirectional Noise**
    * **File:** `types.py`
    * **The Fix:** Stop creating `_reverse` edges by default.
    * **Why:** These double the graph size and trap the Taint Engine in infinite loops (Source $\to$ Target $\to$ Source), causing the "Max Depth" timeouts mentioned in your Handoff.

13. **Normalize IDs**
    * **File:** `dfg_builder.py` vs `interceptors.py`
    * **The Fix:** Ensure both files generate IDs using the exact same template (e.g., `{file}::{function}::{var}`).
    * **Why:** Ensures that Middleware variables (`req`) correctly link to Controller variables (`req`).


It is technically a **4-Layer Problem** (Extraction, Storage, Graph, Taint), but you are battling a **5th "Invisible" Layer** that is causing your crashes: **Orchestration/System**.

You cannot fix the logic (Layers 1-4) if the Orchestrator (Layer 0) blows up the RAM before you even finish indexing.

Here is the **Sum of All Bugs** (Impact Analysis) and the **Definitive Pre-Implementation Plan** to fix your platform, ordered by dependency.

### The Sum of All Bugs (The "Why It's Broken" Report)

If you run Taint Analysis today, this is what happens:
1.  **Blindness (Extraction):** You miss 40% of the attack surface because your extractors ignore variables in SQL queries and rename API routes that don't look like `router.get`.
2.  **Amnesia (Storage):** You successfully extract complex React logic, but your database layer truncates it at 500 characters, deleting the security vulnerabilities located at character 501+.
3.  **Hallucination (Graph):** Your Python graph builder tries to read code using Regex (because the Extraction layer didn't give it types), guessing that "async_handler" is a function when it's just a variable string. It connects unrelated nodes, creating a "hairball" graph.
4.  **Explosion (Taint):** The Taint Engine tries to traverse this hairball. Because everything connects to everything (fuzzy matching), it hits infinite loops (`max_depth=20`) on 99.6% of flows.
5.  **Crash (System):** Your Orchestrator loads all ASTs and Import Tables into RAM at startup. On a large repo, this kills the process (OOM) before analysis completes.

---

### The Master Remediation Plan (Execute in Order)

You must fix the pipeline **upstream first**. Fixing Taint (Layer 4) is useless if Extraction (Layer 1) is feeding it garbage.

#### Phase 0: System Stability (The Orchestrator)
*Goal: Stop the 6GB OOM crashes.*
1.  **Kill the RAM Cache:** In `orchestrator.py`, stop loading `js_ts_cache` for the entire batch. Parse, Extract, and **discard** the AST immediately.
2.  **Lazy-Load Imports:** In `db_cache.py`, remove `_load_cache()`. Replace `self.imports_by_file` with a method that queries SQLite `WHERE file = ?` on demand.

#### Phase 1: The Eyes (Extraction Layer)
*Goal: See the code accurately.*
1.  **Enable AST Fallback:** In `main.ts`, change `ast: null` to `ast: sourceFile` (or a stripped version). This re-enables your Python fallback logic for edge cases.
2.  **Fix SQL Blindness:** In `security_extractors.ts`, modify `extractSQLQueries`. Capture `call.arguments[0]` **even if it is a variable** (not just StringLiteral). Flag it as `{"is_dynamic": true}`.
3.  **Fix API Blindness:** In `security_extractors.ts`, remove the check `isRouter = ROUTER_PATTERNS.some(...)`. If it looks like an HTTP verb (`.get('/', ...)`), extract it.
4.  **Relax Validation:** In `schema.ts`, make fields `.optional()` or `.nullable()`. Stop rejecting entire files because one field is missing.

#### Phase 2: The Memory (Storage Layer)
*Goal: Stop corrupting data on save.*
1.  **Remove Truncation:** In `node_database.py`, delete the line `callback_body[:497] + "..."`. Store the full code. Storage is cheap; missing code is fatal.
2.  **Fix "Crash" Policy:** In `core_storage.py`, wrap `add_symbol` calls in `try/except`. Log errors but **do not crash** the worker.
3.  **Generic IDs:** Update schemas to use `id INTEGER PRIMARY KEY` for assignments/nodes, rather than relying on brittle `(file, line, col)` composite keys that break on whitespace changes.

#### Phase 3: The Brain (Graph Layer)
*Goal: Stop guessing and start knowing.*
1.  **Stop Re-parsing:** In `dfg_builder.py`, **delete** `_parse_argument_variable`. Use the exact node type (`StringLiteral` vs `Identifier`) extracted in Phase 1.
2.  **Strict Resolution:** In `interceptors.py`, remove the `LIKE %methodName%` SQL query. Require an exact match on `ImportSpecifier` to link Routes to Controllers.
3.  **Incremental Saves:** In `store.py`, change `DELETE FROM nodes` to `DELETE FROM nodes WHERE file = ?`. This allows you to re-scan 1 file without wiping the whole graph.

#### Phase 4: The Logic (Taint Layer)
*Goal: Accurate results.*
1.  **Prune the Graph:** Now that you have "Strict Resolution" (Phase 3), the graph will be sparse and accurate. The "infinite loops" will disappear naturally.
2.  **Define Sinks:** Populate the `framework_taint_patterns` table with the missing sinks you extracted in Phase 1 (`child_process.exec`, `eval`, etc.).
3.  **Run Taint:** Now you can run `aud taint-analyze`. It will be fast, low-memory, and accurate.

**Immediate Next Step:**
Go to `main.ts` and `security_extractors.ts`. These are your highest ROI fixes. Without them, you are building a castle on sand.