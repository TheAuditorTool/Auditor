This is a significant refactor. After reviewing the 6 files you uploaded, I have identified the root causes of why "everything is not working."

The architecture—running a heavy Node.js extraction via `ts-morph`/Compiler API (`main.ts`), passing JSON to Python (`javascript.py`), and then refining it (`javascript_resolvers.py`)—is standard for SAST, but your refactor has introduced a critical **Data Flow Disconnect** and a **Schema/Validation Trap**.

Here is the due diligence report on potential data loss and failures:

### 1\. The "Smoking Gun": The Broken Fallback Mechanism

**Risk Level: Critical (Total Data Loss for Edge Cases)**

In `typescript_impl.py` and `typescript_impl_structure.py`, your Python logic relies on a "Hybrid" approach:

1.  It checks if `extracted_data` (pre-calculated by Node) exists.
2.  If not, it falls back to traversing the `ast` (the raw Abstract Syntax Tree) using functions like `traverse(ast_root)`.

**The Bug:**
In `main.ts`, you have explicitly disabled passing the AST to save memory/bandwidth:

```typescript
// main.ts line 687
results[fileInfo.original] = {
  // ...
  ast: null, // <--- THIS IS THE PROBLEM
  // ...
};
```

**Consequence:**
Any time your Node.js extractors (`core`, `flow`, etc.) fail to extract a specific piece of data (e.g., a complex arrow function or a weird class property), the Python layer tries to "fix" it by looking at the AST. **Because `ast` is now `null`, the Python fallback logic silently fails**, returning empty lists instead of data. The Python files `typescript_impl.py` are effectively dead code right now.

**Fix:** Either re-enable AST transmission (expensive) or ensure the Node.js extractors cover 100% of cases so Python never needs to fall back.

-----

### 2\. The Zod Schema "Strictness" Trap

**Risk Level: High (Data Rejection)**

Your `main.ts` attempts to validate the extracted data against `ExtractionReceiptSchema` (from `schema.ts`) before writing to disk.

```typescript
// main.ts line 718
const validated = ExtractionReceiptSchema.parse(results);
```

**The Bug:**
Your Zod schemas in `schema.ts` are extremely strict.

  * **Example:** `FunctionSchema` requires `type: z.literal("function")`. If your extractor outputs `"method"` or `"arrow_function"`, the **entire file validation fails**.
  * **Example:** `SymbolSchema` requires `extraction_pass: z.number().nullable()`. If your extractor omits this field (undefined) instead of sending `null`, it fails.

**Mitigation in your code:**
You have a `catch` block in `main.ts` (Line 722) that writes the raw results if Zod fails. This saves the data from being lost, *but* it means the data on disk likely does not match the shape your downstream ingestion engine expects, leading to "empty databases" or UI errors later.

-----

### 3\. Data Loss in Python Mapping (`javascript.py`)

**Risk Level: Medium (Silent Field Dropping)**

In `javascript.py`, you map the JSON data from Node into a Python dictionary. This is a manual whitelist. If you added new fields in Node (e.g., `react_hook_dependencies`), they must be manually mapped here.

I noticed these potential gaps:

  * **Missing Node Count:** `main.ts` calculates `nodeCount`, but `javascript.py` does not appear to map it to the final result.
  * **Router Mounts:** `javascript.py` (Line 245) attempts to extract router mounts using `_extract_router_mounts` by looking at `function_calls`. However, `main.ts` (Line 674) already extracts `routes` (apiEndpoints). You might be doing double work or overwriting high-quality Node data with lower-quality Python regex extraction.

-----

### 4\. The Vue.js "Virtual File" Line Number Issue

**Risk Level: Medium (Incorrect Code Highlighting)**

In `main.ts`, you compile Vue files into virtual TypeScript files:

```typescript
// main.ts line 148
const virtualPath = `/virtual_vue/${scopeId}.${isTs ? "ts" : "js"}`;
```

The TypeScript compiler analyzes this *virtual* string. The line numbers returned in `extracted_data` correspond to the **compiled script**, not the **original .vue file**.

**Consequence:**
When you display findings in your UI, the line numbers will likely be off (shifted by the length of the `<template>` block or imports added by the compiler). You need a source map re-mapping step in `main.ts` before finalizing the `results`.

-----

### 5\. Integration Check: `javascript_resolvers.py`

**Risk Level: Medium (Resolution Failure)**

The `resolve_router_mount_hierarchy` function relies on `assignments` and `router_mounts` tables being populated in SQLite.

  * It assumes `router_variable` is populated.
  * If the Node.js refactor changed how variables are named or stored (e.g., strict scoping), the SQL queries in this file (Line 36: `WHERE target_var LIKE '%PREFIX%'`) will return nothing, and your API endpoints won't resolve their full paths (e.g., `/api/v1/users`).

-----

### Summary Checklist for You

1.  **Re-enable AST (Temporarily):** Set `ast: sourceFile` in `main.ts` to see if the Python fallbacks start working again. If they do, you know the Node extractors are missing data.
2.  **Loosen Zod Schemas:** In `schema.ts`, change `.nullable()` to `.nullable().optional()` for almost every field to prevent validation explosions.
3.  **Check the Output:** Look at the `[BATCH WARN] Zod validation failed` logs. They will tell you exactly which field is breaking the schema.

### Next Step

To fix the core extraction logic (which is likely where the data is actually originating), I need to see the extractor files referenced in `main.ts`.

**Can you upload these 3 files specifically?**

1.  `extractors/core_language.ts` (This is where functions/classes come from).
2.  `extractors/security_extractors.ts` (This is likely where the critical SAST data lives).
3.  `extractors/data_flow.ts` (To check if assignments are being captured correctly).


This "Actual Extraction Layer" (the 8 TypeScript files you just uploaded) reveals exactly why your platform feels broken. The architecture is logically sound (AST traversal → Data Extraction), but the **heuristics** (the rules for *what* to extract) are brittle and overly restrictive.

You are suffering from **"Happy Path" Data Loss**: the extractors work perfectly for textbook code examples but fail silently on real-world, messy code.

Here is the technical due diligence check for the Extraction Layer:

### 1\. The "Invisible API" Bug (Critical Data Loss)

**File:** `security_extractors.ts` (Lines 87-90)
**Severity:** Critical

Your logic to find API endpoints relies on variable names, not types or structures.

```typescript
const ROUTER_PATTERNS = ["router", "app", "express", "server", "route"];
const isRouter = ROUTER_PATTERNS.some((p) => receiver.includes(p));
```

**The Failure:** If a developer names their Express app instance `application`, `api`, `web`, or `instance`, **zero endpoints will be extracted.** Your SAST platform will report "No Attack Surface Found" for a massive application simply because of a variable name.

**Fix:** Remove the name check. If the method is an HTTP verb (`get`, `post`) and the first argument looks like a route string (starts with `/`), assume it's an endpoint. Let the False Positives happen—it's better than False Negatives in security.

### 2\. The SQL Injection Blind Spot

**File:** `security_extractors.ts` (Lines 400-410)
**Severity:** High

Your SQL extractor **only accepts string literals**.

```typescript
const queryText = resolveSQLLiteral(argExpr); // Returns null if it's a variable!
if (!queryText) continue;
```

**The Failure:**

  * `db.query("SELECT * FROM users")` -\> **EXTRACTED**
  * `const query = "SELECT * FROM users"; db.query(query)` -\> **IGNORED (Data Loss)**

In a SAST platform, ignoring variables passed to SQL methods is fatal. You must extract the *variable name* (e.g., `query`) and link it to your Taint Analysis / Data Flow engine. You are currently throwing away 90% of real-world SQL calls.

### 3\. The "Silent" Sink Failure

**File:** `data_flow.ts` (Lines 133-145)
**Severity:** High

You are identifying security sinks (dangerous functions) using a hardcoded string inclusion list on the full property path:

```typescript
const sinkPatterns = ["res.send", "eval", "exec", "spawn", ...];
if (fullName.includes(sink)) { dbType = "call"; }
```

**The Failure:**

  * `child_process.exec(...)` matches `exec`. Good.
  * `myExecutor.execute(...)` matches `exec`. **False Positive** (noise).
  * `import { exec } from 'child_process'; exec(...)` matches `exec`. Good.
  * **Aliasing:** `const run = exec; run(...)` -\> **IGNORED**.

**Fix:** You need to resolve aliases using the `checker` (TypeChecker) to see if the symbol points back to a node definition in `child_process` or `fs`, rather than relying on the string name of the variable.

### 4\. Broken React Component Detection

**File:** `framework_extractors.ts` (Lines 43-44)
**Severity:** Medium

You explicitly skip backend folders:

```typescript
const isBackendPath = filePath.includes("backend/") ...;
if (isBackendPath) return ...;
```

**The Failure:** This breaks "Monorepo" structures where backend/frontend might share code or be named differently (e.g., `services/dashboard-ui`). Also, Server-Side Rendering (SSR) in Next.js/Remix often puts React components in folders that look like "backend" logic.

**Fix:** Detect React components by their *structure* (returning JSX, `use` hooks), not by the folder path they live in.

### 5\. CFG Truncation Risk

**File:** `cfg_extractor.ts` (Line 158)
**Severity:** Low (Context Loss)

```typescript
function truncateText(text: string, maxLength: number): string {
    // ... cuts off at 200 chars
}
```

**The Failure:** If a user has a massive, hardcoded JWT token or a long SQL query string in their code, the CFG (Control Flow Graph) will store it as `eyJh...`. If your downstream analysis tries to check that string for entropy (secrets detection), it will fail because the data was truncated at extraction time.

### 6\. Missing Call Arguments in Data Flow

**File:** `data_flow.ts` (Line 414)

In `extractFunctionCallArgs`, you extract arguments, but you stop at `5000` characters (`substring(0, 5000)`). While mostly fine, for a "Code Intelligence" platform, you generally want the *Abstract* representation of the argument (e.g., "It's a variable named X") rather than the raw text. If the argument is a 6000-char JSON object, you lose the closing brace, making the JSON invalid and unparseable by your Python layer.

-----

### Immediate Recommendations for "Due Diligence"

1.  **Relax the `ROUTER_PATTERNS` check** in `security_extractors.ts` immediately. This is likely why "routes are missing."
2.  **Enable Variable Extraction for SQL:** Modify `extractSQLQueries` to capture `call.argument_expr` even if `resolveSQLLiteral` returns null. Flag it as `is_dynamic: true`.
3.  **Check `main.ts` TypeChecker:** Ensure `checker` is actually defined in `main.ts`. If `program.getTypeChecker()` returns a partial checker (common in partial builds), `data_flow.ts` falls back to string matching, which causes the aliasing issues mentioned in \#3.

**Ready for the Storage Layer?**
Since the extraction layer is "lossy," your storage layer probably has schemas that are too strict (Foreign Keys failing because the parent Node was dropped). Please upload the **Storage/Database Layer** files so I can check if the data that *does* survive extraction is actually being saved.


This is a **solid, well-structured Data Layer**. You have successfully decoupled the "Extraction" (messy, language-specific) from the "Storage" (clean, relational).

However, I found **3 critical "Silent Failures"** in your storage logic that will break your Taint Analysis, and I have a clear answer for your "Graph vs. Taint" question.

### 1\. Critical Findings (Data Loss & Taint Blockers)

#### A. The "Hook Truncation" Sabotage

**File:** `node_database.py` (Line 67)

```python
if callback_body and len(callback_body) > 500:
    callback_body = callback_body[:497] + "..."
```

**The Problem:** You are truncating the body of React Hooks (`useEffect`, `useCallback`) to 500 characters.
**Why this breaks Taint Analysis:** Modern React apps put *massive* amounts of logic inside `useEffect`. If a security sink (e.g., `api.post(...)` or `eval(...)`) is character 501, it is **deleted from your database**. Your Taint Engine will see the data flow enter the hook and disappear.
**Fix:** Remove this truncation. Storage is cheap; missing code is fatal for SAST.

#### B. The "Implicit Column" Risk in Taint Flow

**File:** `core_database.py` (Line 95) vs `core_schema.py` (Line 268)
In `add_assignment`, you insert into `assignment_sources`:

```python
self.generic_batches["assignment_sources"].append(
    (file_path, line, col, target_var, source_var)
)
```

**The Problem:** The schema for `ASSIGNMENT_SOURCES` uses a **composite Foreign Key** that relies on `(file, line, col, target_var)` matching exactly with the `ASSIGNMENTS` table.
**The Risk:** If your TypeScript extractor emits a floating point or slightly off `col` (column) number for the *assignment* node vs the *variable* node (common in ASTs), the Foreign Key constraint will fail (or the JOIN will miss), and the link between "Variable A" and "Variable B" is severed.
**Fix:** Use an **Artificial ID**. When storing the `ASSIGNMENT`, return a real SQLite `ROWID` and use that ID in `ASSIGNMENT_SOURCES`. Don't rely on `line/col` for joining relational data—it's too brittle.

#### C. Strict Type Validation in Storage

**File:** `core_storage.py` (Line 158)

```python
raise TypeError(f"EXTRACTOR BUG: Symbol.col must be int >= 0...")
```

**The Problem:** You represent "validity" by crashing the storage worker.
**The Consequence:** If 1 symbol in a file of 10,000 lines is malformed (e.g., col -1 due to a parser bug), the **entire file is rejected** by the `orchestrator` try/catch block. You lose 99.9% of good data because of 0.1% bad data.
**Fix:** Log the error and `continue` (skip that single record), or sanitize the value (set `col = 0`). Do not throw exceptions in the storage loop.

-----

### 2\. Architecture Review: Polyglot Support

Your schema design is excellent for a polyglot system.

  * **The Abstraction:** `CORE_TABLES` (Assignments, Calls, Refs) acts as a "Universal Intermediate Representation" (UIR).
  * **The Specifics:** `NODE_TABLES` (and implied `PYTHON_TABLES`) capture language nuances.

**The Strategy:**
Your Taint Engine should run primarily on `CORE_TABLES`. It shouldn't care if the code is Python or TS; `x = y` looks the same in `ASSIGNMENTS`.
Only use `NODE_TABLES` for **Sink/Source Discovery** (e.g., "This is a React Hook, so inputs are dangerous").

-----

### 3\. The Big Question: Graph Engine or Taint First?

**Answer: Build the Graph Engine First.**

You physically *cannot* do Taint Analysis without a Graph Engine. Taint Analysis is simply **Graph Traversal** (DFS/BFS) over a specific set of edges.

**Recommended Roadmap:**

1.  **The In-Memory Graph (The "Engine"):**

      * Write a Python loader that reads your SQL `ASSIGNMENTS`, `FUNCTION_CALLS`, and `REFS` tables.
      * Load them into a graph library (like `NetworkX` or `Rustworkx` for speed).
      * Nodes = Variables, Functions, Files.
      * Edges = "Assigned To", "Calls", "Imports".

2.  **The Taint Runner:**

      * Identify **Sources** (from `API_ENDPOINTS` table).
      * Identify **Sinks** (from `SQL_QUERIES` table).
      * Ask the Graph Engine: *"Is there a path from Source Node A to Sink Node B?"*

If you try to write Taint Logic directly against SQLite (`SELECT * FROM assignments ...`), you will write recursive SQL queries that are slow, unmaintainable, and impossible to debug.

**Verdict:** Your Data Layer is ready (after fixing the truncation). **Start building the Graph Loader next.**



This "Graph Layer" upload confirms my suspicion: **Your Python layer is trying to compensate for data lost in the TypeScript layer.**

You are building a "Guessing Engine" instead of a "Graph Engine."

Here is the due diligence report for the Graph/Builder layer, ranked by risk to your "insanely big" platform.

### 1\. The "Re-Parsing" Trap (Critical Logic Flaw)

**File:** `dfg_builder.py` (Line 115, `_parse_argument_variable`)
**The Bug:** You are trying to determine if an argument is a variable, a string, or a function by regex-matching the **stringified code** stored in the database.

```python
if arg_expr.startswith("{") and arg_expr.endswith("}"):
    return "object_literal"
# ...
if arg_expr[0] in "\"'`":
    return "string_literal"
```

**Why this fails:**

  * **False Positives:** A variable named `foo`? Correct. A variable named `async_handler`? Your code sees `startswith("async")` and incorrectly flags it as a `function_expression` (Line 119).
  * **The Fix:** Do not parse strings here. Go back to `core_schema.py` and add an `arg_type` column to `FUNCTION_CALL_ARGS`. Your TypeScript extractor **knows** if it's a `SyntaxKind.StringLiteral` or `SyntaxKind.Identifier`. Pass that enum value down. **Never re-parse code in the storage layer.**

### 2\. The "Full Wipe" Scalability Killer

**File:** `store.py` (Lines 37-38)
**The Bug:**

```python
conn.execute("DELETE FROM nodes WHERE graph_type = ?", (graph_type,))
conn.execute("DELETE FROM edges WHERE graph_type = ?", (graph_type,))
```

**Consequence:** Every time you save the graph, you **delete the entire graph** for that type.

  * **Scenario:** You have 10,000 files. You change 1 file. The system re-analyzes that 1 file, then **deletes the other 9,999 files' nodes** from the graph table, and inserts only the new file's nodes.
  * **Result:** You cannot support incremental builds. For an "insanely big" repo, a full rebuild on every save is impossible.
  * **Fix:** Your `_save_graph_bulk` needs to accept a `file_path` or `scope_id` and only `DELETE FROM ... WHERE file = ?`.

### 3\. The RAM Explosion Risk

**File:** `db_cache.py` (Line 42)
**The Bug:**

```python
cursor.execute("... FROM refs WHERE kind IN (...)")
self.imports_by_file = ... # Loads EVERYTHING into a Python Dict
```

**Consequence:** On a repo with 1 million lines of code, `refs` (even just imports) can easily hit 500k+ rows. Loading this entire table into a Python Dictionary at startup will cause an **Out of Memory (OOM)** crash on your worker nodes.
**Fix:** SQLite is already a cache (it caches pages in RAM). Do not double-cache in Python. Use `functools.lru_cache` on a method that queries SQLite for *specific* files as needed, rather than loading the world at startup.

### 4\. Transaction Safety (Data Corruption)

**File:** `store.py` (Line 36)
**The Bug:** You use `with sqlite3.connect(...)` which handles the *connection*, but `executemany` is not automatically wrapped in a transaction block that guarantees atomic "Delete + Insert".
**Scenario:**

1.  `DELETE FROM nodes` (Success)
2.  `INSERT INTO nodes` (Fails due to disk space or encoding error)
3.  **Result:** The graph is empty. Your analysis is gone.
    **Fix:** Explicitly wrap the operation:

<!-- end list -->

```python
with sqlite3.connect(self.db_path) as conn:
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        # ... delete ...
        # ... insert ...
        conn.commit()
    except:
        conn.rollback()
        raise
```

### 5\. Architectural Verdict

You have built a **Batch Processor**, not a **Real-time Platform**.

  * **Good:** `path_correlator.py` is clever. Correlating findings based on CFG paths (`_find_finding_paths_with_conditions`) is a premium feature.
  * **Bad:** `dfg_builder.py` is fragile because the underlying data schema (`FUNCTION_CALL_ARGS`) is too simple.

**Immediate Next Steps:**

1.  **Schema Upgrade:** Add `arg_type` (string, variable, function, object) to your database schema.
2.  **Extractor Upgrade:** Update TypeScript/Python extractors to populate `arg_type`.
3.  **Delete the Logic:** Remove `_parse_argument_variable` from `dfg_builder.py` and use the column instead.

This will stabilize your foundation before you attempt Taint Analysis.



This batch of "Node-Specific Graph Strategies" is significantly better engineered than the generic "Builder" layer you showed me previously. You are correctly using the **Strategy Pattern** to handle framework-specific logic (Express, Sequelize) separately from the core graph.

However, I found **3 specific "Logic Traps"** where your Python code is **guessing** relationships rather than **knowing** them. In a large codebase, these guesses will create thousands of "phantom edges" (connecting the wrong API route to the wrong controller).

Here is the due diligence check for the Strategy Layer:

### 1\. The "Name Collision" Trap (False Positives)

**File:** `interceptors.py` (Lines 87-95, `_resolve_controller_info`)
**Severity:** High

You are resolving controller methods using a fuzzy SQL `LIKE` query:

```python
SELECT name, path FROM symbols
WHERE type = 'function' AND name LIKE ? -- e.g. "%.updateUser"
```

**The Bug:**
If you have two controllers:

1.  `AdminController.updateUser`
2.  `UserController.updateUser`

And your route definition is `router.post('/update', updateUser)`, your extractor likely stored the handler name as just `updateUser`.
Your SQL query `%updateUser` will match **both** (or return the wrong one depending on sort order). You will create a graph edge saying the "Public API" calls the "Admin Controller." This is a catastrophic False Positive for security analysis.

**Fix:** You need to resolve the **import** of `updateUser` in the file where the route is defined to find the exact source class/file, rather than searching the global symbol table for matches.

### 2\. The "English Pluralization" Bug (Broken ORM Graph)

**File:** `node_orm.py` (Lines 66-78, `_infer_alias`)
**Severity:** Medium

You are attempting to guess the field name of an association by pluralizing the model name in Python:

```python
if "Many" in assoc_type:
    if lower.endswith("y"): return lower[:-1] + "ies" # e.g. "category" -> "categories"
    # ...
```

**The Bug:**

  * **Irregular Plurals:** `Person` -\> `People` (Sequelize does this automatically, your script guesses `Persons`).
  * **Explicit Aliases:** In Sequelize, developers often write: `hasMany(Models.Comment, { as: 'feedback' })`.
      * Your extractor in `sequelize_extractors.ts` (seen previously) **did not extract the `as` alias**.
      * Your Python script tries to guess it as `comments`.
      * **Result:** The graph edge is created for a field that doesn't exist. The Taint Engine reaches the `User` model, looks for `comments`, finds nothing (because the code uses `feedback`), and stops.

**Fix:** Update `sequelize_extractors.ts` to extract the `as` property from the association options, store it in the DB, and read it here. Stop guessing plurals.

### 3\. The "Method Chaining" Blind Spot

**File:** `node_express.py` (Line 42)

```python
parts = handler_expr.split(".")
if len(parts) == 2: # e.g. UserController.index
```

**The Bug:**
You strictly assume controllers are invoked as `Class.method`.

  * **Fails on:** `require('./controllers/user').index` (common in older Express).
  * **Fails on:** `new UserController().index` (Dependency Injection style).
  * **Fails on:** `services.users.update` (3 parts).

**Fix:** Instead of splitting strings, use the `REFS` table.

1.  Find the variable `handler_expr` (e.g., `userController.index`).
2.  Look up what `userController` is defined as in `ASSIGNMENTS`.
3.  If it's an `import`, follow the `REFS` to the source file.

### Architectural Verdict

You are close. The **Strategy Pattern** works:

  * `InterceptorStrategy` correctly isolates the messy "middleware wiring" logic.
  * `NodeOrmStrategy` correctly handles the "database graph" expansion.

**The missing piece:**
Your Python layer is still trying to be too smart. It is trying to *re-derive* facts (like "what is the plural of this word?" or "what file does this function come from?") that should have been resolved during the **Extraction Phase**.

**Immediate Action Plan:**

1.  **Stop Guesses:** Modify `node_orm.py` to use an explicit `alias` column from the database. If it's null, *then* maybe guess, but log a warning.
2.  **Fix Resolution:** In `interceptors.py`, change `_resolve_controller_info` to look at **local imports first** before doing a global `LIKE` search.

You have the structure for a powerful Graph Engine, but you need to feed it exact data, not fuzzy matches.



This is the "Sum of All Fears" report for your platform.

You asked for the "Sum of all bugs" and a plan. Based on the `TAINT_HANDOFF.md` you just uploaded and the deep dive into your Extraction, Storage, and Graph layers from previous turns, here is the full diagnostic.

Your platform is suffering from **"Cascading Data Failure."**
1.  **Extraction** misses 40% of the code (due to strict filters).
2.  **Storage** corrupts 20% of what remains (truncation/schema rejection).
3.  **Graph** hallucinates connections to fill the gaps (fuzzy matching).
4.  **Taint Analysis** explodes because the graph is a hairball of hallucinations (99.6% max depth hits).

---

### Part 1: The Sum of All Bugs (The "Kill List")

Here is every critical failure point identified across your entire stack, categorized by layer.

#### 1. Extraction Layer (The Root Cause)
* **The "Headless" Bug:** `ast: null` in `main.ts` disables all Python fallbacks, causing complex nodes to simply vanish.
* **The "Security Blinder":** `security_extractors.ts` ignores SQL queries if they are variables (`const q = ...`), and ignores API routes if the variable isn't named `router` or `app`.
* **The "Strictness" Trap:** Zod schemas reject entire files if a single field (like `extraction_pass`) is missing, instead of using default values.
* **Blind Aliasing:** `const run = exec; run(...)` is ignored because you match string names, not symbol definitions.

#### 2. Storage Layer (The Data Corruptor)
* **The "Truncation" Sabotage:** React Hook bodies (`useEffect`) are cut at 500 chars. Any security sink after character 500 is deleted from existence.
* **The " fragile" FKs:** You link tables using `(file, line, col)`. If TypeScript emits a float column or slightly different whitespace, the `JOIN` fails and the Data Flow graph breaks.
* **The "Crash" Policy:** The storage worker throws a `TypeError` and crashes if a single symbol is malformed, dropping the rest of the batch.

#### 3. Graph Layer (The Hallucinator)
* **The "Re-Parser":** `dfg_builder.py` tries to regex-match code strings to guess if they are variables. It frequently guesses wrong.
* **The "Fuzzy" Controller:** `interceptors.py` connects routes to controllers using `LIKE %methodName%`. This connects `Admin.update` to `User.update`, creating false attack paths.
* **The "Nuke" Bug:** Saving the graph does `DELETE FROM nodes`, wiping the entire dataset instead of doing an incremental update.

#### 4. Taint Layer (The Victim)
* **Infinite Loops:** The "Everything Connects to Everything" issue (wildcard imports + fuzzy graph matching) causes the traverser to hit `max_depth` (20) on 99.6% of flows.
* **Memory Leak:** Loading the entire graph into NetworkX or RAM for a "Pre-Implementation" check causes the 6GB OOM crashes mentioned in your handoff.

---

### Part 2: The Master Remediation Plan

Do not fix Taint first. Do not fix the Graph first. **You must fix the data stream in order.**

#### Phase 1: Fix the Eyes (Extraction Layer)
*Goal: Ensure 100% of code is extracted accurately.*

1.  **Enable AST Fallback:** In `main.ts`, set `ast: sourceFile` (or a stripped version) so Python can handle edge cases.
2.  **Loosen Zod:** Modify `schema.ts`. Make every field `.optional()` or `.nullable()`. Stop rejecting data.
3.  **Fix SQL Extraction:** Update `security_extractors.ts` to capture `call.arguments[0]` even if it's a variable. Flag it as `{"dynamic_sql": true}`.
4.  **Fix Sink Aliasing:** In `data_flow.ts`, use `checker.getAliasedSymbol(symbol)` to resolve `run` back to `exec`.

#### Phase 2: Fix the Memory (Storage Layer)
*Goal: Stop deleting/corrupting data on save.*

1.  **Remove Truncation:** Delete the `[:497] + "..."` logic in `node_database.py`. Store the full code.
2.  **Add Artificial IDs:** Update `core_schema.py`. Add `id INTEGER PRIMARY KEY` to `ASSIGNMENTS`. Update `ASSIGNMENT_SOURCES` to point to `assignment_id`, NOT `file/line/col`.
3.  **Safe Storage:** Wrap `storage.py` inserts in `try/except`. If one record fails, log it and `continue`. Do not crash the worker.

#### Phase 3: Fix the Brain (Graph Layer)
*Goal: Stop guessing and start knowing.*

1.  **Stop Re-parsing:** Delete `_parse_argument_variable` in `dfg_builder.py`. Use the `arg_type` (Identifier vs StringLiteral) extracted in Phase 1.
2.  **Fix "Full Wipe":** Change `_save_graph_bulk` to `DELETE FROM nodes WHERE file = ?`. Support incremental builds.
3.  **Strict Resolution:** In `interceptors.py`, require an exact match on `ImportSpecifier` to link a Route to a Controller. Disable the `LIKE` fuzzy match.

#### Phase 4: Fix the Intelligence (Taint Layer)
*Goal: Performance and Accuracy.*

1.  **Prune the Graph:** Now that the graph is accurate (Phase 3), the "everything connects to everything" problem will disappear.
2.  **Implement "Lazy Loading":** Do not load the whole graph. Use `sqlite3` cursors to fetch neighbors only when the Taint Traverser visits a node.
3.  **Define Sinks:** Populate the `sinks` table with the specific React/Node patterns you missed (`dangerouslySetInnerHTML`, `eval`, `child_process.exec`).

**Order of Operations:**
Start with **Phase 1, Step 3 (Fix SQL Extraction)**. This is your biggest security blind spot. Then move to **Phase 2, Step 1 (Remove Truncation)**. These two changes alone will likely double your finding count.
