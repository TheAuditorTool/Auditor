# Priority 1: Frontend→Backend Taint Flow Connector
**Handoff Document for Lead Auditor Review**

**Date**: 2025-11-10
**Phase**: 6.8 → 7.0 (Pending Approval)
**Prepared By**: Janitor (Claude)
**Reviewed By**: [PENDING - Lead Auditor]
**Protocol**: Template C-4.20 (teamsop.md v4.20)

---

## EXECUTIVE SUMMARY

**Problem**: TheAuditor cannot trace taint flows across browser→server boundaries despite having all necessary data.

**Current State**:
- Frontend indexing: 95% file coverage (209 API calls detected in plant)
- Backend indexing: 100% working (181 endpoints with full_path)
- Cross-boundary taint flows: **0%** (zero flows connect frontend to backend)

**Impact**:
- Primary attack vector (user input → API → database) completely blind
- Cannot detect: XSS, injection, CSRF, data exfiltration
- Missing 200+ potential vulnerability paths

**Previous Attempt**:
- 550 lines of forbidden heuristics deleted (2025-11-10)
- Produced 52 "synthetic sources" but **0 working flows** (database verified)
- Violated ZERO FALLBACK POLICY (regex, string patterns, path normalization)

**Correct Approach**:
- AST extraction (frontend_api_calls table)
- Database joins (no heuristics)
- IFDS flow function (call graph traversal)

**Estimate**: 3-5 days (requires schema change + AST extractor + IFDS integration)

**Decision Required**: Approve/reject proposed architecture before implementation

---

## PROBLEM STATEMENT

### The Gap

TheAuditor has excellent indexing of both frontend and backend code but **cannot connect them**:

```
Frontend (Browser):
  User types malicious input in form
  ↓
  JavaScript: fetch('/api/users', {body: formData})
  ↓
  [BLACK HOLE - NO CONNECTION]
  ↓
Backend (Server):
  Express: app.post('/api/users', handler)
  ↓
  Controller: req.body.name
  ↓
  ORM: User.create(req.body)
```

**What we detect:**
- ✅ Frontend: 209 API calls (fetch/axios)
- ✅ Backend: 181 endpoints with full_path
- ✅ Backend: 92 taint flows (req.body → ORM)

**What we miss:**
- ❌ Connection: frontend API call → backend endpoint
- ❌ Provenance: which form input reaches which database table
- ❌ Full chain: `<input>` → fetch → req.body → User.create

### Database Evidence

**plant project verification (2025-11-10):**

```sql
-- Frontend API calls detected
SELECT COUNT(*) FROM function_call_args
WHERE file LIKE '%frontend%'
  AND (callee_function LIKE '%fetch%' OR callee_function LIKE '%axios%');
Result: 148 calls

-- Backend endpoints with full paths
SELECT COUNT(*) FROM api_endpoints
WHERE full_path IS NOT NULL AND full_path != '';
Result: 181 endpoints

-- Cross-boundary flows in taint analysis
SELECT COUNT(*) FROM resolved_flow_audit
WHERE source_file LIKE '%frontend%' AND sink_file LIKE '%backend%';
Result: 0 flows ❌

-- Backend-only flows (working)
SELECT COUNT(*) FROM resolved_flow_audit;
Result: 92 flows ✅
```

**Conclusion**: We have all the pieces but no glue to connect them.

---

## CURRENT STATE ANALYSIS

### What Works (Verified 2025-11-10)

**Backend Taint Analysis:**
- 92 flows detected (49 vulnerable + 43 sanitized)
- 5-hop provenance chains (route → middleware → controller → service → ORM)
- Sanitizer detection (Zod validation recognized)
- Database: `resolved_flow_audit` table fully populated

**Example working backend flow:**
```
Source: backend/src/routes/account.routes.ts:42 (req.body)
  ↓ (express_middleware_chain)
Middleware: backend/src/middleware/validate.ts:19 (zod.parseAsync)
  ↓ (call_argument)
Controller: backend/src/controllers/account.controller.ts:28
  ↓ (assignment)
Service: backend/src/services/account.service.ts:15
  ↓ (call_argument)
Sink: backend/src/models/Account.ts:82 (Account.create)

Status: SANITIZED (Zod validation at depth 2)
```

**Frontend Indexing:**
- 106 of 112 files indexed (95% coverage)
- 192 React components detected
- 1,478 React hooks tracked
- 209 API calls detected (fetch/axios patterns)

**Backend Indexing:**
- 181 API endpoints with full_path (100% coverage)
- Phase 6.7 router mount resolution working
- Template literals resolved (e.g., `` `${API_PREFIX}/auth` `` → `/api/v1/auth`)

### What's Broken (Verified 2025-11-10)

**Cross-Boundary Flows: 0%**

**Why previous attempt failed:**

The deleted code (`connect_frontend_backend`, 350 lines) attempted to match frontend→backend at **discovery time** using string heuristics:

```python
# ❌ FORBIDDEN - What was deleted
def connect_frontend_backend(frontend_api_sinks):
    # Extract path from fetch call using regex
    path_match = re.search(r"['\"`]([^'\"` ]+)['\"`]", first_arg)

    # Normalize path with string manipulation
    path_normalized = full_path.lstrip('/').replace('api/v1/', '').replace('api/', '')

    # Infer HTTP method from function name
    if 'post' in callee.lower(): method = 'POST'

    # Match using normalized strings
    if path_normalized == endpoint_normalized:
        # Create "synthetic source" at backend req.body
        sources.append({'pattern': 'req.body', 'file': endpoint_file})
```

**Results:**
- 52 "synthetic sources" created
- 0 cross-boundary flows in resolved_flow_audit (database verified)
- Violated ZERO FALLBACK POLICY (regex, string normalization, method inference)

**Root cause of failure:**
1. Matching done at **discovery time** (before IFDS runs)
2. Used **string heuristics** instead of database facts
3. Created **synthetic sources** instead of IFDS flow function
4. IFDS couldn't traverse because no dynamic flow function existed

---

## ARCHITECTURAL ANALYSIS

### Why Backend-Only Flows Work

**IFDS Backward Analysis (current implementation):**

```
1. Start: Sink (ORM query at line 82)
2. Query: assignments table for defining statement
3. Find: Service call at line 15
4. Query: function_call_args for caller
5. Find: Controller at line 28
6. Query: assignments for req.body source
7. Find: Middleware validation at line 19
8. Query: express_middleware_chains for route
9. Find: Route definition at line 42
10. Match: req.body against sources list
11. Result: 5-hop chain recorded in resolved_flow_audit
```

**Key insight**: Every hop uses **database queries**, not graph traversal. IFDS uses "dynamic flow functions" that query `assignments`, `function_call_args`, `express_middleware_chains` tables on-demand.

### Why Cross-Boundary Flows Don't Work

**The missing flow function:**

```
Current IFDS flow functions (ifds_analyzer.py):
  ✅ _flow_function_assignment()       - queries assignments table
  ✅ _flow_function_parameter()        - queries function definitions
  ✅ _flow_function_return()           - queries return statements
  ✅ _flow_function_call_argument()    - queries function_call_args
  ✅ _flow_function_field_load()       - queries property access
  ✅ _flow_function_express_middleware() - queries express_middleware_chains

  ❌ _flow_function_cross_boundary_api_call() - DOES NOT EXIST
```

**What the missing function should do:**

```python
# Pseudo-code for correct approach
def _flow_function_cross_boundary_api_call(ap: AccessPath):
    """
    When backward trace hits req.body at backend endpoint,
    check if frontend API call sends data to this endpoint.
    """
    if ap.base != 'req' or ap.fields != ('body',):
        return []  # Not req.body, skip

    # Get current endpoint path from api_endpoints table
    endpoint_path = query_api_endpoints(ap.file, ap.line)

    # Query frontend_api_calls table (NEW TABLE - doesn't exist yet)
    frontend_calls = query_frontend_api_calls_matching(endpoint_path)

    # For each matching call, create AccessPath to frontend data argument
    predecessors = []
    for call in frontend_calls:
        frontend_ap = AccessPath(
            file=call.file,
            function=call.caller_function,
            base=call.body_argument_name,  # e.g., "formData"
            fields=()
        )
        predecessors.append((frontend_ap, 'cross_boundary_api_call', metadata))

    return predecessors
```

**The problem**: This requires a **new table** (`frontend_api_calls`) that doesn't exist.

---

## PROPOSED ARCHITECTURE

### Phase 1: AST Extraction (NEW)

**Create table: `frontend_api_calls`**

Schema:
```sql
CREATE TABLE frontend_api_calls (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    caller_function TEXT,
    callee_function TEXT,  -- 'fetch', 'axios.post', 'api.get'
    method TEXT,            -- 'GET', 'POST', 'PUT', 'DELETE'
    url_literal TEXT,       -- '/api/users' (extracted from AST)
    body_argument TEXT,     -- 'formData', 'data', 'payload'
    PRIMARY KEY (file, line)
);
```

**AST Extractor (javascript.py):**

```python
def _extract_frontend_api_calls(self, node, file_info):
    """
    Extract fetch/axios calls during AST parsing.

    NO regex, NO string inference - pure AST facts.
    """
    if node.type == 'call_expression':
        callee = node.callee

        # Check if it's fetch() or axios.post()
        if callee.type == 'identifier' and callee.value == 'fetch':
            # fetch(url, options)
            url_node = node.arguments[0]
            url_literal = extract_string_literal(url_node)  # AST extraction

            options_node = node.arguments[1]
            method = extract_method_from_options(options_node)  # AST extraction
            body_arg = extract_body_argument(options_node)  # AST extraction

            return {
                'file': file_info['path'],
                'line': node.line,
                'caller_function': current_function,
                'callee_function': 'fetch',
                'method': method or 'GET',
                'url_literal': url_literal,
                'body_argument': body_arg
            }
```

**Key principle**: Extract at **indexing time** (AST parsing), NOT at query time (string patterns).

### Phase 2: Database Matching (NO HEURISTICS)

**Query to find matches:**

```sql
-- ✅ CORRECT: Database join, no string manipulation
SELECT
    fapi.file as frontend_file,
    fapi.line as frontend_line,
    fapi.body_argument as frontend_data,
    ep.file as backend_file,
    ep.line as backend_line,
    ep.full_path as backend_endpoint
FROM frontend_api_calls fapi
JOIN api_endpoints ep ON (
    fapi.url_literal = ep.full_path
    AND fapi.method = ep.method
)
WHERE ep.full_path IS NOT NULL;
```

**Expected results for plant:**
- 148 frontend API calls in table
- 181 backend endpoints with full_path
- ~50-100 matches (conservative estimate: 50% coverage)

### Phase 3: IFDS Integration

**Add flow function to ifds_analyzer.py:**

```python
def _flow_function_cross_boundary_api_call(self, ap: AccessPath):
    """
    Flow function for browser→server boundary traversal.

    Triggered when backward trace hits req.body at backend endpoint.
    Queries database to find frontend API calls that send to this endpoint.
    Creates AccessPaths for frontend data arguments.

    NO string matching - only database queries.
    """
    # Only trigger for req.body AccessPaths
    if ap.base != 'req' or ap.fields != ('body',):
        return []

    # Query 1: Get backend endpoint path
    self.repo_cursor.execute("""
        SELECT full_path, method
        FROM api_endpoints
        WHERE file = ? AND line <= ?
        ORDER BY line DESC
        LIMIT 1
    """, (ap.file, ap.line))

    endpoint = self.repo_cursor.fetchone()
    if not endpoint:
        return []

    # Query 2: Find frontend calls to this endpoint
    self.repo_cursor.execute("""
        SELECT file, line, caller_function, body_argument
        FROM frontend_api_calls
        WHERE url_literal = ? AND method = ?
    """, (endpoint['full_path'], endpoint['method']))

    # Query 3: Create AccessPath for each match
    predecessors = []
    for call in self.repo_cursor.fetchall():
        frontend_ap = AccessPath(
            file=call['file'],
            function=call['caller_function'],
            base=call['body_argument'],
            fields=()
        )

        metadata = {
            'api_method': endpoint['method'],
            'api_path': endpoint['full_path'],
            'frontend_file': call['file'],
            'frontend_line': call['line']
        }

        predecessors.append((frontend_ap, 'cross_boundary_api_call', metadata))

    return predecessors
```

**Integration point in _get_predecessors():**

```python
def _get_predecessors(self, ap: AccessPath):
    predecessors = []

    # ... existing flow functions (assignment, parameter, return) ...

    # NEW: Cross-boundary flow function
    if ap.base == 'req' and ap.fields == ('body',):
        cross_boundary_preds = self._flow_function_cross_boundary_api_call(ap)
        predecessors.extend(cross_boundary_preds)

    return predecessors
```

### Phase 4: Verification

**Test on plant project:**

```bash
# Run indexing with new extractor
aud index

# Verify extraction
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM frontend_api_calls"
Expected: 148 rows

# Verify matches
sqlite3 .pf/repo_index.db "
SELECT COUNT(*)
FROM frontend_api_calls fapi
JOIN api_endpoints ep ON (fapi.url_literal = ep.full_path AND fapi.method = ep.method)
"
Expected: 50-100 matches

# Run taint analysis
aud taint-analyze

# Verify cross-boundary flows
sqlite3 .pf/repo_index.db "
SELECT COUNT(*) FROM resolved_flow_audit
WHERE source_file LIKE '%frontend%' AND sink_file LIKE '%backend%'
"
Expected: >0 flows (success criteria: 50+ flows)
```

---

## WHAT NOT TO DO (FORBIDDEN PATTERNS)

### ❌ Pattern 1: Path Normalization
```python
# FORBIDDEN
path_normalized = full_path.lstrip('/').replace('api/v1/', '').replace('api/', '')
```
**Why**: Hardcodes API prefix structure, breaks on different projects.
**Correct**: Query router_mounts table, use full_path as-is.

### ❌ Pattern 2: Regex on Arguments
```python
# FORBIDDEN
import re
path_match = re.search(r"['\"`]([^'\"` ]+)['\"`]", argument_expr)
```
**Why**: CLAUDE.md:334-336 explicitly bans regex on file content/expressions.
**Correct**: Extract string literal from AST node during indexing.

### ❌ Pattern 3: Method Inference
```python
# FORBIDDEN
if 'post' in callee_function.lower():
    method = 'POST'
```
**Why**: False positives on functions like `postProcess`, `postpone`.
**Correct**: Extract method from options object AST node.

### ❌ Pattern 4: File Path Heuristics
```python
# FORBIDDEN
WHERE file LIKE '%frontend%'
```
**Why**: Hardcodes directory structure, breaks on different projects.
**Correct**: Use dedicated frontend_api_calls table.

### ❌ Pattern 5: Synthetic Sources at Discovery Time
```python
# FORBIDDEN
def connect_frontend_backend():
    sources.append({'pattern': 'req.body', 'file': backend_file})
```
**Why**: IFDS needs dynamic flow function, not pre-created sources.
**Correct**: Flow function queries database when IFDS reaches req.body.

---

## COMPLIANCE ANALYSIS

### ZERO FALLBACK POLICY (CLAUDE.md:304-369)

**Compliance checklist:**

✅ **NO database query fallbacks**
- Single query per flow function
- Hard fail if table doesn't exist
- No try/except with fallback logic

✅ **NO regex on file content**
- All string extraction via AST nodes
- No pattern matching on argument_expr column
- No regex in flow functions

✅ **NO table existence checks**
- Schema contract guarantees tables exist
- No `if 'frontend_api_calls' in tables:` logic
- Crash if schema contract violated

✅ **NO string heuristics**
- All matching via database joins
- No path normalization, method inference
- No LIKE '%pattern%' queries on file paths

✅ **NO conditional fallback logic**
- No "if X fails, try Y" patterns
- No multiple queries with fallback
- Single code path only

### Schema Contract

**New table registration required:**

```python
# theauditor/indexer/schemas/frameworks_schema.py
FRONTEND_API_CALLS = """
CREATE TABLE IF NOT EXISTS frontend_api_calls (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    caller_function TEXT,
    callee_function TEXT,
    method TEXT,
    url_literal TEXT,
    body_argument TEXT,
    PRIMARY KEY (file, line)
);
"""

# Add to table_schemas dict
table_schemas = {
    # ... existing tables ...
    'frontend_api_calls': FRONTEND_API_CALLS,
}
```

**Table count update:**

```python
# theauditor/indexer/schema.py
# Line 67: Update count 158 → 159
TOTAL_TABLES = 159
```

---

## RISK ANALYSIS

### Technical Risks

**Risk 1: AST Extraction Complexity**
- **Severity**: MEDIUM
- **Description**: Extracting method and body argument from fetch/axios options object
- **Mitigation**: Start with simple cases (literal strings), expand to variable references
- **Fallback**: If body argument can't be determined, store NULL (skip in flow function)

**Risk 2: URL Matching Accuracy**
- **Severity**: MEDIUM
- **Description**: Frontend may use `/api/v1/users` while backend has `/api/v1/users/:id`
- **Mitigation**: Query api_endpoints for prefix matches, handle route parameters
- **Fallback**: Exact match first, then implement path parameter matching in Phase 2

**Risk 3: IFDS Performance**
- **Severity**: LOW
- **Description**: Additional flow function may slow down backward analysis
- **Mitigation**: Flow function only triggers on req.body (narrow scope)
- **Measurement**: Compare taint analysis time before/after (expect <10% increase)

**Risk 4: Schema Contract Violation**
- **Severity**: HIGH
- **Description**: If frontend_api_calls table missing, all queries will crash
- **Mitigation**: Schema contract guarantees table exists, ZERO FALLBACK enforced
- **Detection**: Unit test verifies table creation during indexing

### Project Risks

**Risk 5: Cross-Project Portability**
- **Severity**: LOW
- **Description**: Different projects may use different API libraries
- **Mitigation**: Design supports fetch, axios, custom wrappers (extract via AST)
- **Validation**: Test on plant, PlantFlow, project_anarchy

**Risk 6: False Positives**
- **Severity**: MEDIUM
- **Description**: May match frontend calls to wrong backend endpoints
- **Mitigation**: Require exact match on method + full_path (strict matching)
- **Measurement**: Manual review of first 20 matched flows

### Schedule Risks

**Risk 7: Estimate Accuracy**
- **Severity**: MEDIUM
- **Description**: 3-5 day estimate may be optimistic
- **Mitigation**: Break into phases, test each phase independently
- **Contingency**: If Phase 1 takes >2 days, reassess and report

---

## IMPLEMENTATION PLAN

### Phase 1: Schema & Extraction (2 days)

**Day 1: Schema Setup**
- Add `frontend_api_calls` table to frameworks_schema.py
- Update TOTAL_TABLES count (158 → 159)
- Update flush_order in base_database.py
- Add batch insert method to frameworks_database.py
- Write unit test for table creation

**Day 2: AST Extractor**
- Add `_extract_frontend_api_calls()` to javascript.py
- Handle fetch() calls (method, URL, body argument)
- Handle axios.get/post/put/delete calls
- Handle custom API wrapper calls (api.get, etc.)
- Write unit test with fixture files

**Verification:**
```bash
aud index
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM frontend_api_calls"
# Expected: >0 for any project with fetch/axios
```

### Phase 2: Database Matching (1 day)

**Day 3: Join Query Implementation**
- Write SQL join query (frontend_api_calls ⋈ api_endpoints)
- Test on plant database (expect 50-100 matches)
- Add debug output for matched pairs
- Document edge cases (path parameters, query strings)

**Verification:**
```sql
SELECT fapi.file, fapi.url_literal, ep.full_path
FROM frontend_api_calls fapi
JOIN api_endpoints ep ON (fapi.url_literal = ep.full_path AND fapi.method = ep.method)
LIMIT 10;
# Manual review: Do these matches look correct?
```

### Phase 3: IFDS Integration (1-2 days)

**Day 4: Flow Function**
- Add `_flow_function_cross_boundary_api_call()` to ifds_analyzer.py
- Integrate into `_get_predecessors()` (req.body check)
- Add debug logging for cross-boundary hops
- Test on single sink manually

**Day 5: Full Integration**
- Run taint analysis on plant
- Review cross-boundary flows in resolved_flow_audit
- Verify hop chains include frontend sources
- Check for false positives (manual review of 20 flows)

**Verification:**
```bash
aud taint-analyze 2>&1 | grep "cross_boundary_api_call"
# Expected: Log messages showing frontend→backend hops

sqlite3 .pf/repo_index.db "
SELECT source_file, sink_file, path_length
FROM resolved_flow_audit
WHERE source_file LIKE '%frontend%'
LIMIT 10
"
# Expected: At least 10 flows with frontend sources
```

### Phase 4: Validation & Documentation (1 day)

**Day 6: Testing**
- Run on plant (expect 50+ flows)
- Run on PlantFlow (expect 30+ flows)
- Run on project_anarchy (expect 2-3 flows)
- Compare to baseline (92 flows in plant should still exist)

**Day 7: Documentation**
- Update taint_status_atomic.md with results
- Document new table schema in CLAUDE.md
- Add examples to query guide
- Write developer docs for AST extractor extension

---

## SUCCESS CRITERIA

### Quantitative Metrics

**Minimum Success (P0):**
- ✅ frontend_api_calls table populated (>0 rows for any project with API calls)
- ✅ Database join returns matches (>0 for plant project)
- ✅ IFDS flow function executes without errors
- ✅ At least 1 cross-boundary flow in resolved_flow_audit

**Target Success (P1):**
- ✅ plant: 50+ cross-boundary flows (50% of 100+ expected API data flows)
- ✅ PlantFlow: 30+ cross-boundary flows
- ✅ No regressions (92 backend flows in plant still exist)
- ✅ Performance: <10% increase in taint analysis time

**Stretch Success (P2):**
- ✅ plant: 100+ cross-boundary flows (>80% coverage)
- ✅ Path length: 7-8 hops (frontend → API → backend → ORM)
- ✅ Sanitizer detection: Frontend validation recognized (React Hook Form, Formik)

### Qualitative Metrics

**Code Quality:**
- ✅ ZERO FALLBACK POLICY compliance (100%)
- ✅ No regex on file content
- ✅ No string heuristics
- ✅ All data from AST + database joins

**Portability:**
- ✅ Works on plant (Express + React)
- ✅ Works on PlantFlow (Express + React)
- ✅ Works on project_anarchy (Express + vanilla JS)
- ✅ No hardcoded project directory structures

**Maintainability:**
- ✅ AST extractor follows existing patterns (javascript.py)
- ✅ Flow function follows existing patterns (ifds_analyzer.py)
- ✅ Schema follows existing patterns (frameworks_schema.py)
- ✅ Documentation complete

---

## DECISION POINTS FOR LEAD AUDITOR

### Approval Required For:

**1. Schema Change (CRITICAL)**
- **Question**: Approve addition of `frontend_api_calls` table to schema?
- **Impact**: Increases TOTAL_TABLES from 158 → 159
- **Risk**: Schema change requires reindexing all projects
- **Recommendation**: APPROVE (necessary for cross-boundary flows)

**2. AST Extractor Scope**
- **Question**: Start with fetch/axios only, or include custom API wrappers (api.get, etc.)?
- **Impact**: Custom wrappers add 1-2 days development time
- **Risk**: May miss some API calls if scope too narrow
- **Recommendation**: Start narrow (fetch/axios), expand later if needed

**3. Path Matching Strategy**
- **Question**: Exact match only, or support route parameters (/users/:id)?
- **Impact**: Route parameters add complexity but increase coverage
- **Risk**: More complex matching = more potential for false positives
- **Recommendation**: Start exact match, add parameter support in Phase 2

**4. Performance Budget**
- **Question**: What's acceptable taint analysis slowdown?
- **Impact**: Cross-boundary flow function adds database queries
- **Risk**: May exceed performance budget on large projects
- **Recommendation**: <10% increase acceptable, measure and optimize if needed

**5. OpenSpec Proposal Requirement**
- **Question**: Create OpenSpec proposal before implementation?
- **Impact**: OpenSpec adds 1 day overhead but ensures architecture review
- **Risk**: May identify issues early, prevents rework
- **Recommendation**: YES - this is a breaking change (schema + AST extractor)

### Questions to Answer:

1. **Priority**: Is this the highest priority, or should we tackle Sequelize/Validation extraction first (1-2 days each)?

2. **Timeline**: Is 3-5 day estimate acceptable, or does this need to ship faster?

3. **Scope**: Should we include frontend validation detection (React Hook Form, Formik) in this phase, or defer?

4. **Testing**: What level of manual review is required before considering this complete?

5. **Rollout**: Should we test on plant only first, or all 3 projects (plant, PlantFlow, project_anarchy) before merging?

---

## REFERENCES

### Related Documents

1. **taint_status_atomic.md** (lines 930-988)
   - Priority 1 definition
   - Forbidden patterns list
   - Correct approach outline

2. **CLAUDE.md** (lines 304-369)
   - ZERO FALLBACK POLICY
   - Absolute prohibition on regex/heuristics
   - Schema contract system

3. **teamsop.md** (v4.20)
   - Template C-4.20 (this document)
   - OpenSpec proposal requirement
   - Architect approval workflow

### Database Schema

**Existing tables used:**
- `api_endpoints` (181 rows in plant, full_path populated via Phase 6.7)
- `function_call_args` (stores all function calls including fetch/axios)
- `resolved_flow_audit` (stores taint flows, will gain cross-boundary flows)

**New table required:**
- `frontend_api_calls` (to be created)

### Code Files

**Files to modify:**
1. `theauditor/indexer/schemas/frameworks_schema.py` (+30 lines)
2. `theauditor/indexer/schema.py` (+1 line, TOTAL_TABLES update)
3. `theauditor/indexer/extractors/javascript.py` (+150 lines, new extractor)
4. `theauditor/indexer/database/frameworks_database.py` (+20 lines, batch insert)
5. `theauditor/indexer/database/base_database.py` (+1 line, flush_order)
6. `theauditor/taint/ifds_analyzer.py` (+100 lines, flow function)

**Total estimated changes**: ~300 lines across 6 files

---

## APPENDIX A: DATABASE SCHEMA SPECIFICATION

```sql
-- Table: frontend_api_calls
-- Purpose: Store frontend API calls with structured metadata for cross-boundary taint analysis
-- Populated by: javascript.py AST extractor during indexing
-- Queried by: ifds_analyzer.py flow function during taint analysis

CREATE TABLE IF NOT EXISTS frontend_api_calls (
    -- Identity
    file TEXT NOT NULL,              -- Frontend file path (e.g., "frontend/src/components/UserForm.tsx")
    line INTEGER NOT NULL,           -- Line number of API call

    -- Context
    caller_function TEXT,            -- Function containing the API call (e.g., "handleSubmit")
    callee_function TEXT,            -- API function name (e.g., "fetch", "axios.post", "api.createUser")

    -- HTTP Metadata
    method TEXT,                     -- HTTP method: GET, POST, PUT, DELETE, PATCH
    url_literal TEXT,                -- URL extracted from AST (e.g., "/api/users", "/api/v1/accounts")

    -- Data Flow
    body_argument TEXT,              -- Variable/expression passed as request body (e.g., "formData", "userData")

    -- Constraints
    PRIMARY KEY (file, line)
);

-- Index for cross-boundary matching (frequently joined with api_endpoints)
CREATE INDEX IF NOT EXISTS idx_frontend_api_calls_url
ON frontend_api_calls(url_literal, method);

-- Example data:
-- file: "frontend/src/components/UserForm.tsx"
-- line: 42
-- caller_function: "handleSubmit"
-- callee_function: "fetch"
-- method: "POST"
-- url_literal: "/api/users"
-- body_argument: "formData"
```

---

## APPENDIX B: EXAMPLE FLOW (BEFORE vs AFTER)

### Current State (Backend-Only)

```
Sink: backend/src/models/User.ts:82 (User.create)
  ↑ (call_argument)
Service: backend/src/services/user.service.ts:45 (create)
  ↑ (assignment)
Controller: backend/src/controllers/user.controller.ts:28 (userData)
  ↑ (express_middleware_chain)
Middleware: backend/src/middleware/validate.ts:19 (zod.parseAsync)
  ↑ (call_argument)
Source: backend/src/routes/user.routes.ts:15 (req.body) ← STOPS HERE

Status: SANITIZED (Zod validation)
Hops: 5
```

### Proposed State (Full-Stack)

```
Sink: backend/src/models/User.ts:82 (User.create)
  ↑ (call_argument)
Service: backend/src/services/user.service.ts:45 (create)
  ↑ (assignment)
Controller: backend/src/controllers/user.controller.ts:28 (userData)
  ↑ (express_middleware_chain)
Middleware: backend/src/middleware/validate.ts:19 (zod.parseAsync)
  ↑ (call_argument)
Route: backend/src/routes/user.routes.ts:15 (req.body)
  ↑ (cross_boundary_api_call) ← NEW FLOW FUNCTION
API Call: frontend/src/components/UserForm.tsx:42 (fetch('/api/users', {body: formData}))
  ↑ (assignment)
Form Data: frontend/src/components/UserForm.tsx:38 (formData = new FormData(form))
  ↑ (call_argument)
Input: frontend/src/components/UserForm.tsx:15 (e.target.value) ← FRONTEND SOURCE

Status: SANITIZED (Zod validation + React controlled input)
Hops: 8 (3 frontend + 5 backend)
```

---

## APPENDIX C: FORBIDDEN vs CORRECT EXAMPLES

### Example 1: Extracting URL from fetch() call

**❌ FORBIDDEN (Regex):**
```python
import re
argument_expr = "fetch('/api/users', {body: data})"
url_match = re.search(r"['\"`]([^'\"` ]+)['\"`]", argument_expr)
url = url_match.group(1) if url_match else None
```

**✅ CORRECT (AST):**
```python
# During AST traversal
if node.type == 'call_expression' and node.callee.value == 'fetch':
    url_node = node.arguments[0]
    if url_node.type == 'string_literal':
        url = url_node.value  # Direct access to AST node value
```

### Example 2: Determining HTTP method

**❌ FORBIDDEN (String inference):**
```python
callee = "axios.post"
if 'post' in callee.lower():
    method = 'POST'
```

**✅ CORRECT (AST):**
```python
# Extract method from axios.post property access
if node.callee.type == 'member_expression':
    if node.callee.object.value == 'axios':
        method = node.callee.property.value.upper()  # 'post' → 'POST'
```

### Example 3: Matching frontend to backend

**❌ FORBIDDEN (String normalization):**
```python
frontend_path = "/api/v1/users"
backend_path = "/:version/users"
normalized_frontend = frontend_path.replace('/api/v1/', '/')
normalized_backend = backend_path.replace('/:version/', '/')
if normalized_frontend == normalized_backend:
    matched = True
```

**✅ CORRECT (Database join):**
```sql
SELECT fapi.*, ep.*
FROM frontend_api_calls fapi
JOIN api_endpoints ep ON (
    fapi.url_literal = ep.full_path  -- Exact match, no normalization
    AND fapi.method = ep.method
)
```

---

**END OF HANDOFF DOCUMENT**

**Next Action**: Lead auditor review and decision on 5 approval points above.

**Status**: PENDING APPROVAL - Do not implement until architecture approved.
