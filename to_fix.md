# TheAuditor Bug Report & Handoff Document

**Date**: 2025-11-23 00:17 (Architect went to sleep)
**Session Type**: Dry run / Demo testing on PlantFlow project
**Written By**: Claude Sonnet 4.5 (AI Coder)
**Written For**: Future AI that will fix these bugs


NOT A CODE BUG! It's MINGW/Git Bash auto-converting /orders to C:/Program Files/Git/orders.

  Workarounds:
  - Use //orders (double slash)
  - Use MSYS_NO_PATHCONV=1
  - Use orders without leading slash

  ---
  FINAL VERIFIED BUG LIST

  | #   | Bug                           | Status           | Root Cause                                     | Fix
    |
  |-----|-------------------------------|------------------|------------------------------------------------|---------------------
  --|
  | 1   | blueprint --structure crash   | CODE BUG         | cursor undefined in drilldown function         | Pass conn to
  function |
  | 2   | boundaries 0 entry points     | CODE BUG         | Missing api_endpoints table lookup             | Add to table list
    |
  | 3   | --component "table not found" | CODE BUG         | hooks_used column doesn't exist                | Fix SELECT columns
    |
  | 4   | --symbol --show-callers empty | CODE BUG         | Exact match fails, need fuzzy                  | Add LIKE fallback
    |
  | 5   | --show-dependents empty       | NOT A BUG        | OrderDetails is a page, correctly not imported | N/A
    |
  | 6   | --api "/orders" empty         | NOT A BUG        | MINGW path conversion                          | Document workaround
    |
  | 7   | --type multi-tenant           | KNOWN INCOMPLETE | Explicitly says "not yet wired"                | Future work
    |

  ---
  ACTUAL FIXES NEEDED: 4 bugs

  1. blueprint.py:793 - cursor scope
  2. input_validation_analyzer.py:88 - add api_endpoints
  3. query.py:515 - fix column list (remove hooks_used)
  4. query.py:297 - add fuzzy symbol matching

  Ready to implement? Start with which one?
---

## Context: What Happened This Session

The Architect (human boss) just merged TheAuditor to main after a 4-month development effort. This session was a dry run to test the tool's functionality on the PlantFlow project (a cannabis POS system with a broken frontend variant migration).

**We tested these commands:**
- `aud refactor --file profile.yaml`
- `aud query` (multiple variants)
- `aud deadcode`
- `aud blueprint --structure` and `--security`
- `aud boundaries`
- `aud planning` (full workflow)

**Project tested on**: `C:\Users\santa\Desktop\PlantFlow`
**TheAuditor location**: `C:\Users\santa\Desktop\TheAuditor`

---

## Architecture Notes (From Architect)

The database structure:
```
.pf/
├── repo_index.db    → Regenerated on `aud full` (symbols, calls, api_endpoints, etc.)
├── graphs.db        → Import/call graph edges (separate file)
├── planning.db      → PERSISTENT - survives aud full (task tracking)
├── ml.db            → PERSISTENT - ML models
└── history/full/... → Old data archived here (versioned, not destroyed)
```

**Key Design Principle**: Database is source of truth. Work isn't "done" until the database proves it deterministically. No self-assessment.

---

## What Worked Perfectly

### 1. `aud refactor --file profile.yaml`
**Status**: FULLY WORKING

Tested with a sophisticated 8-rule YAML profile for PlantFlow's variant migration. The command:
- Found 82 old references across 8 files
- Correctly identified which rules had old refs vs new refs
- Generated a prioritized file queue
- Detected rules with missing new schema patterns

Output was excellent - exactly what an AI coder needs to understand the refactor state.

### 2. `aud planning` (Full Workflow)
**Status**: FULLY WORKING

Successfully:
- `aud planning init --name "PlantFlow Variant Migration"`
- `aud planning add-phase 1 --phase-number N --title "..." --success-criteria "..."`
- `aud planning add-task 1 --phase N --title "..." --description "..."`
- `aud planning show 1`

Created a 5-phase, 10-task plan with success criteria. The hierarchical Phase → Task → Job structure works great.

### 3. `aud deadcode`
**Status**: WORKING (with expected false positives)

Found 331 dead code items. Many are entry points (app.ts, seeders, configs) which is expected - they're not imported, they're entry points.

**Useful finding**: `frontend/src/services/variants.ts` has unused functions - someone wrote a variant service but never wired it up. This is relevant to the refactor!

### 4. `aud blueprint --security`
**Status**: WORKING

Excellent output:
- 118 API endpoints found
- 75% unprotected (88/118) - flagged as security risk
- 83 dynamic SQL queries (100%), 0 parameterized - flagged SQLi risk
- 6 JWT usages detected
- 3 potential hardcoded secrets

This is exactly what security auditing needs.

### 5. Direct Database Queries
**Status**: WORKING

The data is there and rich:
- 250 tables in repo_index.db
- 21,765 symbols
- 11,139 function calls
- 447 React components
- 118 API endpoints
- 35,029 variable usages
- 72,798 edges (in graphs.db)
- 30,102 nodes (in graphs.db)

---

## What's Broken

### 1. `aud query --show-dependents` / `--show-dependencies`
**Status**: BROKEN - Returns empty results

**Symptom**:
```bash
aud query --file frontend/src/pages/dashboard/OrderDetails.tsx --show-dependents
# Returns: Incoming Dependencies (0): (none)
```

**Root Cause Identified**:
The `edges` table is in `graphs.db`, NOT in `repo_index.db`. The query command is looking in `repo_index.db` and finding no edges table.

```python
# This fails:
sqlite3.connect('.pf/repo_index.db')
cursor.execute('SELECT * FROM edges')  # OperationalError: no such table

# But this works:
sqlite3.connect('.pf/graphs.db')
cursor.execute('SELECT * FROM edges')  # 72,798 rows!
```

**Fix Required**:
`aud query` needs to connect to `graphs.db` for `--show-dependents` and `--show-dependencies` queries, or the edges need to be copied/linked to repo_index.db.

---

### 2. `aud query --symbol X` and `--show-callers`
**Status**: BROKEN - Returns empty results

**Symptom**:
```bash
aud query --symbol OrderDetails --show-callers
# Returns: []

aud query --symbol product_variant_id --show-callers
# Returns: []
```

**Data Exists**:
- 21,765 symbols in `symbols` table
- 11,139 function calls in `function_call_args` table

**Possible Causes**:
1. Symbol name matching is too strict (case-sensitive? needs exact canonical name?)
2. The query isn't finding the right tables
3. JOIN logic between symbols and function_call_args is broken

**Help text says**: "ALL class/instance methods are indexed as ClassName.methodName" - maybe I needed to query `OrderController.getAllOrders` not just `OrderDetails`?

**Fix Required**: Debug why symbol queries return empty when data clearly exists.

---

### 3. `aud query --component X`
**Status**: BROKEN - Says table not found

**Symptom**:
```bash
aud query --component Sale --show-tree
# Returns: ERROR: react_components table not found. Project may not use React.
```

**But the table exists with data**:
```python
sqlite3.connect('.pf/repo_index.db')
cursor.execute('SELECT COUNT(*) FROM react_components')
# Returns: 447
```

**Fix Required**: The table existence check is wrong, or it's looking in the wrong database.

---

### 4. `aud blueprint --structure`
**Status**: PARTIALLY BROKEN - Crashes at end

**Symptom**: Runs successfully, outputs useful info, then crashes:
```
Error: NameError: name 'cursor' is not defined

Detailed error information has been logged to: .pf\error.log
```

**Fix Required**: There's an undefined `cursor` variable somewhere in the structure analysis code path. Check `.pf/error.log` for traceback.

---

### 5. `aud boundaries`
**Status**: BROKEN - 0 entry points analyzed

**Symptom**:
```bash
aud boundaries --type input-validation
# Returns: Entry Points Analyzed: 0
```

**But entry points exist**:
- 118 rows in `api_endpoints` table
- 333 rows in `express_middleware_chains` table
- 25 rows in `router_mounts` table

**Additional Note**: `--type multi-tenant` returns:
```
Error: Multi-tenant boundary analysis not yet wired to this command
Use: aud full (includes multi-tenant analysis via rules)
```

**Fix Required**:
1. Wire the boundaries command to actually read from `api_endpoints`
2. Complete multi-tenant boundary implementation

---

### 6. `aud query --api` / `--show-api-coverage`
**Status**: BROKEN - Returns empty

**Symptom**:
```bash
aud query --api "/orders" --show-api-coverage
# Returns: []
```

**But data exists**: 118 API endpoints in the table, including order routes.

---

## What I Need (As AI Coder) To Do My Job

### Must Have (Blocking Workflow)

1. **`aud query --symbol X --show-callers`**
   - Before refactoring any function, I need to know every caller
   - Without this, I risk breaking unknown code paths
   - Workaround: Direct SQL queries, but defeats the purpose of the tool

2. **`aud query --file X --show-dependents`**
   - Before changing/moving a file, I need to know what imports it
   - Critical for safe refactoring
   - Workaround: grep, but loses the graph intelligence

### Nice to Have

3. **`aud boundaries`**
   - Verify auth/validation is at correct distance from entry points
   - Important for security work but not blocking

4. **`aud query --component X --show-tree`**
   - Understand React component hierarchy
   - Useful for frontend refactoring

---

## Test Commands for Verification

After fixing, run these on PlantFlow to verify:

```bash
# Should return callers of OrderController methods
aud query --symbol OrderController.getAllOrders --show-callers

# Should return files that import OrderDetails.tsx
aud query --file frontend/src/pages/dashboard/OrderDetails.tsx --show-dependents

# Should find React components
aud query --component Sale --show-tree

# Should not crash
aud blueprint --structure

# Should find entry points
aud boundaries --type input-validation

# Should find order endpoints
aud query --api "/orders" --show-api-coverage
```

---

## Files to Check

Based on the errors, these are likely locations to investigate:

1. **Query command**: Look for where it connects to database - needs to use `graphs.db` for edges
2. **Component query**: Look for table existence check logic
3. **Blueprint structure**: Search for undefined `cursor` variable
4. **Boundaries**: Look for entry point loading logic

---

## Session Artifacts Created

During this session, we created:

1. **Planning database**: `.pf/planning.db` with:
   - Plan 1: "PlantFlow Variant Migration"
   - 5 phases (Returns/Refunds, POS Cart, Products UI, Conversions, Missing Patterns)
   - 10 tasks mapped to specific files and old ref counts

2. **This document**: `C:\Users\santa\Desktop\TheAuditor\to_fix.md`

---

## Summary for Future AI

The tool is 80% there. The `aud refactor` + `aud planning` combo is already production-ready and genuinely useful. The main gap is `aud query` - it has all the data indexed (250 tables, 72k edges, 21k symbols) but the query interface can't access it properly.

Priority fix order:
1. `aud query --show-dependents` (edges in wrong DB)
2. `aud query --symbol --show-callers` (data exists, query fails)
3. `aud query --component` (table exists, check fails)
4. `aud blueprint --structure` (cursor undefined)
5. `aud boundaries` (entry points not loading)

Good luck, future me. The Architect built something impressive here - just needs the query layer debugged.

---

## ADDENDUM: Full Command Inventory (Added at 00:24)

The Architect reminded me that `aud planning` is an umbrella for many analysis commands. Here's the full inventory with test status:

### TESTED - WORKING
| Command | Status | Notes |
|---------|--------|-------|
| `aud refactor --file X` | ✅ WORKING | Profile-based detection is excellent |
| `aud planning *` | ✅ WORKING | Full workflow: init, phases, tasks, show |
| `aud deadcode` | ✅ WORKING | 331 items found (needs entry point exclusions) |
| `aud blueprint --security` | ✅ WORKING | Great security surface analysis |
| `aud structure` | ✅ WORKING | Generated STRUCTURE.md, 349 files, 76k LOC |
| `aud deps` | ✅ WORKING | Found 115 deps (100 npm, 15 Docker) |

### TESTED - BROKEN
| Command | Status | Issue |
|---------|--------|-------|
| `aud query --show-dependents` | ❌ BROKEN | Looks in wrong DB (repo_index vs graphs) |
| `aud query --symbol --show-callers` | ❌ BROKEN | Returns empty despite 21k symbols |
| `aud query --component` | ❌ BROKEN | "table not found" but 447 rows exist |
| `aud query --api --show-api-coverage` | ❌ BROKEN | Returns empty |
| `aud blueprint --structure` | ⚠️ PARTIAL | Works then crashes: `cursor` undefined |
| `aud boundaries` | ❌ BROKEN | 0 entry points despite 118 in table |

### TESTED - NEEDS RE-RUN
| Command | Status | Notes |
|---------|--------|-------|
| `aud taint-analyze` | ⚠️ TRIGGERED SCHEMA REGEN | Auto-fixed stale schema, asked to re-run |

### NOT TESTED (Need verification)
| Command | Purpose |
|---------|---------|
| `aud context` | Semantic classification (obsolete/current/transitional) |
| `aud docs` | Fetch library documentation for AI context |
| `aud impact` | Blast radius analysis for code changes |
| `aud fce` | Factual Correlation Engine - compound vulnerabilities |
| `aud detect-patterns` | Security pattern detection |
| `aud lint` | Code quality linting |
| `aud cfg` | Control flow graph analysis |
| `aud graph` | Dependency/call graph building |
| `aud workset` | Incremental analysis file subset |
| `aud report` | Consolidated audit report |
| `aud summary` | Statistics aggregation |
| `aud insights` | ML-powered scoring |
| `aud suggest` | ML priority list for risky files |
| `aud explain` | Interactive documentation |

### Command Relationships (What Planning Should Orchestrate)

Based on help text and testing, here's how commands relate:

```
aud planning (umbrella)
├── aud refactor      → Detect incomplete migrations (WORKING)
├── aud context       → Semantic classification (NOT TESTED)
├── aud query         → Code relationships (BROKEN)
├── aud boundaries    → Security distance analysis (BROKEN)
├── aud deadcode      → Unused code detection (WORKING)
├── aud blueprint     → Architecture visualization (PARTIAL)
├── aud structure     → Project overview (WORKING)
├── aud deps          → Dependency inventory (WORKING)
├── aud docs          → Library documentation (NOT TESTED)
├── aud taint-analyze → Injection detection (NEEDS RE-RUN)
├── aud fce           → Compound vulnerabilities (NOT TESTED)
└── aud impact        → Change blast radius (NOT TESTED)
```

### `aud taint-analyze` Schema Regeneration

During testing, taint-analyze auto-detected stale schema:
```
[SCHEMA STALE] Schema files have changed but generated code is out of date!
[SCHEMA STALE] Regenerating code automatically...
[SCHEMA FIX] Generated code updated successfully
[SCHEMA FIX] Please re-run the command
Generated code written to C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas
```

This is actually a nice self-healing feature! But means taint analysis results weren't captured this session.

---

## Database Table Counts (For Reference)

From direct queries on PlantFlow's `.pf/repo_index.db`:

```
api_endpoints:              118
react_components:           447
symbols:                 21,765
function_call_args:      11,139
taint_flows:                  3
variable_usage:          35,029
express_middleware_chains:  333
router_mounts:               25
```

From `.pf/graphs.db`:
```
edges:                   72,798
nodes:                   30,102
```

All the data is there. The query interface just can't reach it.

---

*End of handoff document*
