# EXTRACTION Layer Pre-Implementation Plan

**Document Version:** 1.0
**Status:** Pre-Implementation Analysis
**Scope:** Complete audit of Extraction Layer bugs from taint analysis review
**Confidence Level:** High (based on comprehensive code review)

---

## Executive Summary

The Extraction Layer is the root cause of 40% data loss in the TheAuditor platform. Issues cascade through Storage, Graph, and Taint layers, ultimately causing 99.6% of flows to hit max_depth with "unknown" vulnerability classification. This document catalogs every extraction-related bug identified across the taint analysis review.

---

## Part 1: TypeScript Extractor Core Issues

### 1.1 The "Headless" Bug - AST Disabled

**Location:** `theauditor/ast_extractors/javascript/src/main.ts` (Line ~687)
**Severity:** CRITICAL
**Impact:** Total Data Loss for Edge Cases

**The Bug:**
```typescript
// main.ts line 687
results[fileInfo.original] = {
  // ...
  ast: null, // <--- THIS IS THE PROBLEM
  // ...
};
```

**Root Cause:** AST transmission was disabled to save memory/bandwidth.

**Consequence:** When TypeScript extractors fail to extract specific data (complex arrow functions, weird class properties), the Python layer tries to "fix" it by examining the AST. Because `ast` is now `null`, the Python fallback logic silently fails, returning empty lists instead of data. The files `typescript_impl.py` and `typescript_impl_structure.py` are effectively dead code.

**Fix Required:**
- Option A: Re-enable AST transmission (expensive)
- Option B: Ensure TypeScript extractors cover 100% of cases so Python never needs fallback

---

### 1.2 The Zod Schema "Strictness" Trap

**Location:** `theauditor/ast_extractors/javascript/src/schema.ts`
**Severity:** HIGH
**Impact:** Data Rejection - Entire Files Lost

**The Bug:**
```typescript
// main.ts line 718
const validated = ExtractionReceiptSchema.parse(results);
```

Zod schemas are extremely strict:
- `FunctionSchema` requires `type: z.literal("function")`. If extractor outputs `"method"` or `"arrow_function"`, entire file validation fails.
- `SymbolSchema` requires `extraction_pass: z.number().nullable()`. If extractor omits field (undefined) instead of `null`, it fails.

**Mitigation Present (But Problematic):**
A `catch` block in `main.ts` (Line 722) writes raw results if Zod fails. This saves data but means data on disk doesn't match expected shape, causing "empty databases" or UI errors downstream.

**Fix Required:**
- Change `.nullable()` to `.nullable().optional()` for almost every field
- Check `[BATCH WARN] Zod validation failed` logs for exact breaking fields

---

### 1.3 The "Silent Error" Black Hole

**Location:** `main.ts` + `javascript.py`
**Severity:** HIGH
**Impact:** Silent Data Loss - 100% of file data lost on single error

**The Bug Chain:**

1. In `main.ts`: If ANY error occurs (even minor parsing warning), sets `success: false`
```typescript
results[filePath] = { success: false, error: ... };
```

2. In `javascript.py`: Discards ENTIRE file if success is false
```python
if tree.get("success") is False:
    continue  # <--- 100% Data Loss for this file
```

**Consequence:** A 5,000-line legacy file with ONE obscure syntax error loses ALL functions and exports.

**Fix Required:**
- Modify `main.ts` to return `partial: true` even on error
- Modify `javascript.py` to attempt salvaging `imports` and `exports` from `extracted_data` even if `success` is false

---

### 1.4 Vue.js "Virtual File" Line Number Issue

**Location:** `main.ts` (Line ~148)
**Severity:** MEDIUM
**Impact:** Incorrect Code Highlighting

**The Bug:**
```typescript
// main.ts line 148
const virtualPath = `/virtual_vue/${scopeId}.${isTs ? "ts" : "js"}`;
```

TypeScript compiler analyzes the VIRTUAL string. Line numbers returned in `extracted_data` correspond to the COMPILED script, not the original `.vue` file.

**Consequence:** When displaying findings in UI, line numbers are off (shifted by length of `<template>` block or imports added by compiler).

**Additional Problem:** `builder.py` and `javascript_resolvers.py` have no idea these virtual paths exist:
- `builder.py` iterates files on disk, finds `Component.vue`
- DB contains symbols linked to `/virtual_vue/12345678.ts`
- Result: All Vue script block logic is detached from file on disk

**Fix Required:**
- Add source map re-mapping step in `main.ts` before finalizing results
- Map virtual paths back to original `.vue` file path in JSON output

---

### 1.5 Path Normalization Mismatch (The "Split-Brain")

**Location:** `main.ts` vs `builder.py`
**Severity:** CRITICAL
**Impact:** Zero Edges Created - Graph Is Empty

**The Bug:**

**Node Brain (main.ts):** Resolves everything to ABSOLUTE paths
```typescript
const absoluteFilePath = path.resolve(filePath);
// Imports resolved by TS Compiler to absolute paths on disk
```

**Python Brain (builder.py):** Relies on RELATIVE paths
```python
rel_path = file_path.relative_to(self.project_root)
```

**The Failure Chain:**
1. `main.ts` parses `src/user.ts`, finds `import { User } from '/abs/path/to/src/models/User'`
2. Sends absolute path to `javascript.py`, saves to `imports` table
3. `builder.py` looks at `files` table, sees `src/models/User.ts` (relative)
4. Tries to match `/abs/path/to/...` against `src/models/...`
5. MISMATCH - Builder assumes import is external/unknown
6. Result: Nodes exist but edge never created

**Additional Fallback Bug in builder.py:**
```python
try:
    rel_path = file_path.relative_to(self.project_root)
except ValueError:
    rel_path = file_path  # FALLBACK TO ABSOLUTE PATH - SILENT CORRUPTION
```

If `project_root` isn't perfect parent, `rel_path` silently fails over to absolute path.

**Fix Required:**
```typescript
// Add helper in main.ts
function toRelative(absPath: string, root: string): string {
  const rel = path.relative(root, absPath);
  return rel.split(path.sep).join(path.posix.sep);
}

// Apply to EVERY file path before adding to results
// Also apply to all import module paths
```

---

## Part 2: Security Extractors Issues

### 2.1 The "Invisible API" Bug

**Location:** `security_extractors.ts` (Lines 87-90)
**Severity:** CRITICAL
**Impact:** Zero Endpoints Extracted for Many Apps

**The Bug:**
```typescript
const ROUTER_PATTERNS = ["router", "app", "express", "server", "route"];
const isRouter = ROUTER_PATTERNS.some((p) => receiver.includes(p));
```

**Consequence:** If developer names Express app instance `application`, `api`, `web`, or `instance`, ZERO endpoints are extracted. SAST platform reports "No Attack Surface Found" for massive application simply because of variable name.

**Fix Required:**
- Remove name check entirely
- If method is HTTP verb (`get`, `post`) and first argument looks like route string (starts with `/`), assume it's an endpoint
- Accept False Positives - better than False Negatives in security

---

### 2.2 The SQL Injection Blind Spot

**Location:** `security_extractors.ts` (Lines 400-410)
**Severity:** HIGH
**Impact:** 90% of Real-World SQL Calls Ignored

**The Bug:**
```typescript
const queryText = resolveSQLLiteral(argExpr); // Returns null if it's a variable!
if (!queryText) continue;
```

**Consequence:**
- `db.query("SELECT * FROM users")` -> EXTRACTED
- `const query = "SELECT * FROM users"; db.query(query)` -> IGNORED (Data Loss)

In SAST, ignoring variables passed to SQL methods is fatal. Must extract VARIABLE NAME and link to Taint Analysis / Data Flow engine.

**Fix Required:**
- Modify `extractSQLQueries` to capture `call.argument_expr` even if `resolveSQLLiteral` returns null
- Flag it as `is_dynamic: true`

---

### 2.3 The "Silent" Sink Failure

**Location:** `data_flow.ts` (Lines 133-145)
**Severity:** HIGH
**Impact:** Missed Sinks, False Positives, Aliasing Failures

**The Bug:**
```typescript
const sinkPatterns = ["res.send", "eval", "exec", "spawn", ...];
if (fullName.includes(sink)) { dbType = "call"; }
```

**Consequence:**
- `child_process.exec(...)` matches `exec`. Good.
- `myExecutor.execute(...)` matches `exec`. FALSE POSITIVE (noise)
- `import { exec } from 'child_process'; exec(...)` matches `exec`. Good.
- **Aliasing:** `const run = exec; run(...)` -> IGNORED

**Fix Required:**
- Use `checker` (TypeChecker) to resolve aliases
- Check if symbol points back to node definition in `child_process` or `fs`
- Don't rely on string name of variable

---

## Part 3: Data Flow Extractor Issues

### 3.1 buildName Returns Empty String for ElementAccess

**Location:** `data_flow.ts`
**Severity:** MEDIUM
**Impact:** Useless Assignment Nodes

**The Bug:** `buildName` function returns `""` (empty string) for `ElementAccess` nodes like `arr[i]`.

**Consequence:** Creates assignment nodes with empty variable names, making them useless for taint tracking.

**Fix Required:** Improve `buildName` to handle `ElementAccess` patterns properly.

---

### 3.2 Argument Text Truncation

**Location:** `data_flow.ts` (Line ~414)
**Severity:** LOW
**Impact:** Invalid JSON in Downstream Processing

**The Bug:**
```typescript
argument_expr: arg.getText(sourceFile).substring(0, 5000)
```

For "Code Intelligence" platform, want ABSTRACT representation of argument (e.g., "It's a variable named X") rather than raw text. If argument is 6000-char JSON object, lose closing brace, making JSON invalid and unparseable by Python layer.

---

## Part 4: Framework Extractors Issues

### 4.1 Broken React Component Detection

**Location:** `framework_extractors.ts` (Lines 43-44)
**Severity:** MEDIUM
**Impact:** React Components in Backend Folders Skipped

**The Bug:**
```typescript
const isBackendPath = filePath.includes("backend/") ...;
if (isBackendPath) return ...;
```

**Consequence:** Breaks "Monorepo" structures where backend/frontend share code or are named differently (e.g., `services/dashboard-ui`). Also breaks Server-Side Rendering (SSR) in Next.js/Remix where React components live in folders that look like "backend" logic.

**Fix Required:**
- Detect React components by STRUCTURE (returning JSX, `use` hooks)
- Not by folder path they live in

---

## Part 5: CFG Extractor Issues

### 5.1 CFG Text Truncation

**Location:** `cfg_extractor.ts` (Line 158)
**Severity:** LOW
**Impact:** Secrets Detection Failure

**The Bug:**
```typescript
function truncateText(text: string, maxLength: number): string {
    // ... cuts off at 200 chars
}
```

**Consequence:** If user has massive hardcoded JWT token or long SQL query string, CFG stores it as `eyJh...`. If downstream analysis tries to check string for entropy (secrets detection), it fails because data was truncated at extraction time.

---

### 5.2 The "Negative ID" Bug - CFG Detachment

**Location:** `cfg_extractor.ts` -> `node_storage.py`
**Severity:** CRITICAL
**Impact:** CFG Blocks Exist But Are EMPTY

**The Bug Chain:**

1. In TypeScript (`cfg_extractor.ts`): Generates valid LOCAL Block IDs (`0, 1, 2...`)
```typescript
const blockId = createBlock(ctx, "entry", ...); // blockId = 0
statements.push({ block_id: blockId, ... });    // Statement linked to 0
```

2. In Python (`node_storage.py`): Attempts to remap Local IDs to Database IDs
```python
# 1. Add Block 0. DB Manager returns temp ID -1 (because it's batched)
temp_id = self.db_manager.add_cfg_block(...)
block_id_map[(func_id, 0)] = temp_id  # Map: 0 -> -1

# 2. Process statements.
real_id = block_id_map.get(0)         # real_id is -1
self.db_manager.add_cfg_statement(real_id, ...) # Statement saved with block_id = -1
```

3. In SQLite: `cfg_blocks` gets inserted, SQLite generates real ID (e.g., `100`), but `cfg_block_statements` is inserted with `block_id = -1`.

**Consequence:** JOIN between Blocks and Statements fails. Statements are orphaned. Taint Engine sees function exists but cannot see code inside it.

**Fix Required:**
```python
# Fix in node_storage.py -> _store_cfg_flat
# Must flush cfg_blocks immediately to get real IDs BEFORE adding statements

cursor = self.db_manager.conn.cursor()
for block in block_batch:
    cursor.execute("INSERT INTO cfg_blocks ...")
    real_id = cursor.lastrowid
    block_id_map[(block['function_id'], block['block_id'])] = real_id

# NOW process statements with real_id
for stmt in cfg_block_statements:
    real_block_id = block_id_map.get(...)
    self.db_manager.add_cfg_statement(real_block_id, ...)
```

---

## Part 6: Module/Import Resolution Issues

### 6.1 Import Resolution Gap

**Location:** `module_framework.ts` vs `javascript_resolvers.py`
**Severity:** MEDIUM
**Impact:** Dangling Edges - Files Not Connected

**The Bug:**

**In TypeScript:** Extracts raw import specifiers (e.g., `import { x } from './utils'`). Does NOT use `ts.resolveModuleName` to get absolute path on disk.

**In Python:** Tries to guess file path using string manipulation:
```python
if package.startswith("."):
    file_dir = "/".join(file.split("/")[:-1])
```

Python doesn't know about:
- `tsconfig.json` "paths" (aliases like `@app/utils`)
- `node_modules` resolution
- `index.ts` priority

**Consequence:** Graph has "dangling edges" where file A imports `utils`, but graph doesn't connect to `utils.ts` because Python guessed wrong path.

**Fix Required:**
- In `module_framework.ts`, use TypeScript Compiler's `checker` to resolve ABSOLUTE file path
- Send resolved path in JSON
- Don't let Python guess

---

## Part 7: Python Extraction Layer Issues

### 7.1 javascript.py - All-or-Nothing Risk

**Location:** `javascript.py`
**Severity:** HIGH
**Impact:** Silent Data Loss on Parser Failure

Already covered in 1.3 above. Key point: If TypeScript extractor encounters single unrecoverable error, entire file is discarded.

---

### 7.2 javascript_resolvers.py - Fragile Path Resolution

**Location:** `javascript_resolvers.py`
**Severity:** MEDIUM
**Impact:** Broken Call Graph Edges

**The Bug:**
```python
if package.startswith("."):
    file_dir = "/".join(file.split("/")[:-1])
```

Does NOT handle:
- `index.ts` / `index.js` resolution (folder imports)
- Webpack/Vite aliases (e.g., `~/components`)
- Monorepo symlinks

**Fix Required:** Trust TypeScript extractor's resolution. If that fails, mark node as `unresolved` rather than guessing path that might point to wrong file.

---

### 7.3 typescript_impl.py - Recursion Depth Limit

**Location:** `typescript_impl.py`
**Severity:** MEDIUM
**Impact:** Missing Deeply Nested Logic

**The Bug:**
```python
def traverse(node, depth=0):
    if depth > 100:  # <--- Hard limit
        return
```

In modern React/Vue applications (higher-order components, deep JSX trees), depth > 100 is not uncommon. By returning early, potentially ignoring logic deep inside render tree - exactly where XSS vulnerabilities (sinks) often live.

**Fix Required:** Increase limit to 500 or make configurable via `os.getenv`.

---

### 7.4 Data Loss in Python Mapping

**Location:** `javascript.py` (Line ~245)
**Severity:** MEDIUM
**Impact:** Silent Field Dropping, Double Work

**The Bug:**
- Missing Node Count: `main.ts` calculates `nodeCount`, but `javascript.py` does not map it to final result
- Router Mounts: `javascript.py` attempts to extract router mounts using `_extract_router_mounts` by looking at `function_calls`. However, `main.ts` already extracts `routes` (apiEndpoints). Double work or overwriting high-quality Node data with lower-quality Python regex extraction.

---

## Part 8: Strategy Layer Extraction Issues

### 8.1 The "Name Collision" Trap

**Location:** `interceptors.py` (Lines 87-95)
**Severity:** HIGH
**Impact:** False Positives - Wrong Controller Connected

**The Bug:**
```python
SELECT name, path FROM symbols
WHERE type = 'function' AND name LIKE ?  # e.g. "%.updateUser"
```

**Consequence:**
If you have:
1. `AdminController.updateUser`
2. `UserController.updateUser`

And route definition is `router.post('/update', updateUser)`, extractor stores handler as just `updateUser`. SQL query `%updateUser` matches BOTH (or returns wrong one depending on sort). Creates graph edge saying "Public API" calls "Admin Controller" - catastrophic False Positive.

**Fix Required:**
- Resolve IMPORT of `updateUser` in file where route is defined
- Find exact source class/file
- Don't search global symbol table for matches

---

### 8.2 The "English Pluralization" Bug

**Location:** `node_orm.py` (Lines 66-78)
**Severity:** MEDIUM
**Impact:** Broken ORM Graph

**The Bug:**
```python
if "Many" in assoc_type:
    if lower.endswith("y"): return lower[:-1] + "ies"  # "category" -> "categories"
```

**Failures:**
- Irregular Plurals: `Person` -> `People` (Sequelize does this, script guesses `Persons`)
- Explicit Aliases: `hasMany(Models.Comment, { as: 'feedback' })`
  - Extractor in `sequelize_extractors.ts` did NOT extract `as` alias
  - Python script guesses `comments`
  - Result: Graph edge created for field that doesn't exist

**Fix Required:**
- Update `sequelize_extractors.ts` to extract `as` property from association options
- Store in DB, read here
- Stop guessing plurals

---

### 8.3 The "Method Chaining" Blind Spot

**Location:** `node_express.py` (Line 42)
**Severity:** MEDIUM
**Impact:** API-to-Controller Flows Severed

**The Bug:**
```python
parts = handler_expr.split(".")
if len(parts) == 2:  # e.g. UserController.index
```

**Fails on:**
- `require('./controllers/user').index` (common in older Express)
- `new UserController().index` (Dependency Injection style)
- `services.users.update` (3 parts)

**Fix Required:**
- Don't split strings
- Use `REFS` table
- Find variable `handler_expr`
- Look up in `ASSIGNMENTS`
- If it's import, follow `REFS` to source file

---

### 8.4 The "Re-Parsing" Trap

**Location:** `dfg_builder.py` (Line 115)
**Severity:** HIGH
**Impact:** Wrong Node Types, Broken Taint Paths

**The Bug:**
```python
def _parse_argument_variable(self, arg_expr: str) -> str | None:
    if arg_expr.startswith("{") and arg_expr.endswith("}"):
        return "object_literal"
    if arg_expr[0] in "\"'`":
        return "string_literal"
```

**Failures:**
- Variable named `async_handler`? Code sees `startswith("async")` and incorrectly flags as `function_expression`
- `deleteUser(req.body.id + 1)`: After `split(" ")[0]` becomes `req.body.id`, but if previous node was `req.body`, IDs don't match and path breaks

**Fix Required:**
- Do NOT parse strings here
- Add `arg_type` column to `FUNCTION_CALL_ARGS` in `core_schema.py`
- TypeScript extractor KNOWS if it's `SyntaxKind.StringLiteral` or `SyntaxKind.Identifier`
- Pass that enum value down
- NEVER re-parse code in storage layer

---

## Part 9: Storage Layer Extraction-Related Issues

### 9.1 The "Hook Truncation" Sabotage

**Location:** `node_database.py` (Line 67)
**Severity:** HIGH
**Impact:** Sinks Inside Hooks Are Invisible

**The Bug:**
```python
if callback_body and len(callback_body) > 500:
    callback_body = callback_body[:497] + "..."
```

**Consequence:** Truncating React Hook bodies (`useEffect`, `useCallback`) to 500 characters. Modern React apps put MASSIVE amounts of logic inside `useEffect`. If security sink (e.g., `api.post(...)` or `eval(...)`) is character 501, it is DELETED from database. Taint Engine sees data flow enter hook and disappear.

**Fix Required:** Remove truncation. Storage is cheap; missing code is fatal for SAST.

---

### 9.2 The "Implicit Column" Risk in Taint Flow

**Location:** `core_database.py` (Line 95) vs `core_schema.py` (Line 268)
**Severity:** MEDIUM
**Impact:** Broken Data Flow Graph

**The Bug:**
In `add_assignment`:
```python
self.generic_batches["assignment_sources"].append(
    (file_path, line, col, target_var, source_var)
)
```

Schema for `ASSIGNMENT_SOURCES` uses COMPOSITE Foreign Key relying on `(file, line, col, target_var)` matching exactly with `ASSIGNMENTS` table.

**Risk:** If TypeScript extractor emits floating point or slightly off `col` (column) number for assignment node vs variable node (common in ASTs), Foreign Key constraint fails (or JOIN misses), and link between "Variable A" and "Variable B" is severed.

**Fix Required:**
- Use Artificial ID
- When storing ASSIGNMENT, return real SQLite `ROWID`
- Use that ID in `ASSIGNMENT_SOURCES`
- Don't rely on `line/col` for joining relational data - too brittle

---

### 9.3 Strict Type Validation in Storage

**Location:** `core_storage.py` (Line 158)
**Severity:** MEDIUM
**Impact:** 99.9% Good Data Lost Because of 0.1% Bad Data

**The Bug:**
```python
raise TypeError(f"EXTRACTOR BUG: Symbol.col must be int >= 0...")
```

**Consequence:** If 1 symbol in a file of 10,000 lines is malformed (e.g., col -1 due to parser bug), ENTIRE file is rejected by `orchestrator` try/catch block.

**Fix Required:**
- Log error and `continue` (skip single record)
- Or sanitize value (set `col = 0`)
- Do NOT throw exceptions in storage loop

---

### 9.4 Schema Nullability Mismatches

**Location:** `core_schema.py` vs `core_storage.py`
**Severity:** MEDIUM
**Impact:** Random Data Insertion Failures

**The Bug:**
In `core_schema.py`:
```python
Column("target_var", "TEXT", nullable=False)
Column("source_expr", "TEXT", nullable=False)
```

In `core_storage.py`:
```python
assignment["target_var"]  # Might be None if extraction failed
```

If extractor produces record where `target_var` is `None` (e.g., complex destructuring pattern `({a} = b)` that parser didn't handle), entire batch insertion for `assignments` might fail or throw integrity error, causing loss of ALL assignments in that batch.

**Fix Required:**
```python
target_var = assignment.get("target_var") or "unknown_var"
source_expr = assignment.get("source_expr") or "unknown_expr"
```

---

## Implementation Priority Order

### Phase 1: Stop the Bleeding (CRITICAL - Do First)

| Priority | Issue | Location | Impact |
|----------|-------|----------|--------|
| 1 | Path Normalization | `main.ts` | Zero edges without this fix |
| 2 | Negative ID Bug | `node_storage.py` | Empty CFG blocks |
| 3 | AST Disabled | `main.ts` | Python fallbacks dead |
| 4 | All-or-Nothing Extraction | `javascript.py` | Files discarded on single error |

### Phase 2: Restore Data Fidelity (HIGH)

| Priority | Issue | Location | Impact |
|----------|-------|----------|--------|
| 5 | Zod Schema Strictness | `schema.ts` | Files rejected on field errors |
| 6 | SQL Literal Only | `security_extractors.ts` | 90% SQL calls ignored |
| 7 | ROUTER_PATTERNS | `security_extractors.ts` | APIs invisible |
| 8 | Hook Truncation | `node_database.py` | Sinks in hooks lost |

### Phase 3: Fix Resolution & Strategies (MEDIUM)

| Priority | Issue | Location | Impact |
|----------|-------|----------|--------|
| 9 | Import Resolution | `module_framework.ts` | Dangling edges |
| 10 | Vue Virtual Paths | `main.ts` | Vue files detached |
| 11 | Name Collision | `interceptors.py` | Wrong controllers |
| 12 | Re-Parsing Trap | `dfg_builder.py` | Wrong node types |

### Phase 4: Polish (LOW)

| Priority | Issue | Location | Impact |
|----------|-------|----------|--------|
| 13 | React Path Skip | `framework_extractors.ts` | Some React missed |
| 14 | Recursion Limit | `typescript_impl.py` | Deep JSX missed |
| 15 | CFG Truncation | `cfg_extractor.ts` | Secrets detection fails |
| 16 | Pluralization | `node_orm.py` | ORM edges wrong |

---

## Verification Commands

After implementing fixes, verify with:

```bash
# Step 1: Verify paths are relative
aud full --index
sqlite3 .pf/repo_index.db "SELECT src FROM refs LIMIT 5"
# Should see: src/index.ts (NOT /Users/...)

# Step 2: Verify CFG statements linked
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM cfg_block_statements WHERE block_id > 0"
# Should be > 0

# Step 3: Verify graph edges exist
aud graph build
sqlite3 .pf/graphs.db "SELECT COUNT(*) FROM edges"
# Should be > 0

# Step 4: Verify reverse edges exist for IFDS
sqlite3 .pf/graphs.db "SELECT COUNT(*) FROM edges WHERE type LIKE '%_reverse'"
# Should be > 0
```

---

## Confirmation

This document catalogs ALL extraction layer issues identified in the taint analysis review. Fixes should be implemented in Phase order. Each fix should be verified before proceeding to next.

**Root Cause Summary:** The Extraction Layer is producing data with:
1. Path format mismatches between TypeScript and Python
2. Strict validation discarding partial data
3. Batched ID assignment breaking parent-child relationships
4. String-based resolution instead of compiler-accurate resolution

**Implementation Logic:** Fix data at source (TypeScript) before it enters storage. Remove strictness that discards data. Use compiler APIs instead of string parsing.
