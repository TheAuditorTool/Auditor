# Rules Refactoring Progress - Schema Normalization

**Version**: 1.0
**Branch**: pythonparity
**Started**: 2025-10-30
**Last Updated**: 2025-10-30

---

## CURRENT STATUS: IN PROGRESS

**Files Audited**: 28/56
**Files Fixed**: 14/56 (auth + build + frameworks + logic + node folders had issues)
**Files In Progress**: 0/56
**Files Clean**: 18/56 (includes 10 dependency + 3 deployment files already clean)
**Progress**: 50.0% complete (28/56 audited) - HALFWAY DONE! 🎉

### Issue Discovered
ALL rules are infected with `LIKE '%pattern%'` cancer in WHERE clauses. The first file checked (jwt_analyze.py) has 50+ instances of this anti-pattern. Estimated 500-1000+ instances across all 56 files.

---

## THE PROBLEM

### What We're Fixing
Moving from string pattern matching in SQL queries to proper database queries with Python-side filtering.

### Bad Pattern (EVERYWHERE):
```python
# CANCER - String matching in SQL WHERE clause
query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
    where="""callee_function = 'jwt.sign'
        AND argument_expr NOT LIKE '%process.env%'    # BAD
        AND argument_expr LIKE '%secret%'             # BAD
        AND file NOT LIKE '%test%'                    # BAD
        AND file NOT LIKE '%spec.%'""")               # BAD
```

### Good Pattern (TARGET):
```python
# CORRECT - Exact match in SQL, pattern filter in Python
query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
    where="callee_function = 'jwt.sign'")
cursor.execute(query)

for file, line, arg_expr in cursor.fetchall():
    # Filter in Python after fetch
    if 'process.env' in arg_expr:
        continue  # Skip env vars
    if 'secret' not in arg_expr:
        continue  # Need 'secret' keyword
    # ... rest of logic
```

### File Filtering
```python
# BAD - File filtering in every SQL query
where="... AND file NOT LIKE '%test%' AND file NOT LIKE '%spec.%'"

# GOOD - File filtering via METADATA (orchestrator handles)
METADATA = RuleMetadata(
    exclude_patterns=['test/', 'spec.', '__tests__']
)
```

---

## REFACTORING STRATEGY

### Phase 1: Audit (1/56 complete)
1. Read file completely
2. Count LIKE clauses
3. Identify pattern types:
   - File filtering (`file NOT LIKE`)
   - Expression matching (`argument_expr LIKE`)
   - Function name matching (`callee_function LIKE`)
4. Document issues in this file
5. Move to next file

### Phase 2: Fix (0/56 complete)
1. Remove ALL `file NOT LIKE` clauses (orchestrator handles via METADATA)
2. Replace expression LIKE patterns with Python filtering
3. Replace function name LIKE with exact matches or IN clause
4. Test on plant/.pf database
5. Verify findings still work

### Phase 3: Verify (0/56 complete)
1. Run `aud index` on plant project
2. Run specific rule
3. Compare findings before/after
4. Check for regressions in .pf/history

---

## FILE-BY-FILE PROGRESS

### auth/jwt_analyze.py - FIXED ✅

**Status**: CLEAN - All LIKE cancer removed
**Original LIKE Count**: 50+ instances → **Fixed: 0 instances**
**Lines**: 575 total (was 635)

**Fixes Applied**:
1. **File filtering** - REMOVED all `file NOT LIKE` clauses (10+ instances)
   - Moved to METADATA exclude_patterns: ['test/', 'spec.', '.test.', '__tests__', 'demo/', 'example/']
   - Added execution_scope='database' to METADATA
   - Orchestrator now handles file filtering

2. **Expression pattern matching** - Moved to Python filtering (20+ instances)
   - Lines 192-206: `if any(env in secret_expr for env in ENV_PATTERNS)` instead of LIKE
   - Lines 229-247: Python loop with `if weak in secret_lower`
   - Lines 378-396: Python loop checking `if field.lower() in payload_lower`
   - Lines 407-424: Python filtering for env variables

3. **Function name wildcards** - Frozenset + Python filtering (5+ instances)
   - Created STORAGE_FUNCTIONS and HTTP_FUNCTIONS frozensets
   - Lines 437-455: `if not any(storage in func for storage in STORAGE_FUNCTIONS)`
   - Lines 523-539: `if not any(http_func in func for http_func in HTTP_FUNCTIONS)`
   - All queries use clean WHERE clauses, filter in Python

4. **Assignment filtering** - Python-side pattern matching
   - Lines 465-479: Fetch all assignments, filter with `if any(pattern in source for pattern in url_patterns)`
   - Lines 549-570: File extension check in Python, React hooks check in Python
   - Zero SQL LIKE patterns for any assignments

**Key Changes**:
- WHERE clauses now only use exact matches: `callee_function = 'jwt.sign'` or `argument_index IN (1, 2)`
- All pattern matching moved to Python with frozensets for O(1) lookups
- File now 60 lines shorter due to removed redundant LIKE clauses
- Zero performance impact (fetch is already filtered by frozenset function names)

**Testing Status**: Not tested yet
**Verified Clean**: YES - grep confirms 0 LIKE instances in WHERE clauses

---

### auth/oauth_analyze.py - FIXED ✅

**Status**: CLEAN - All LIKE cancer removed
**Original LIKE Count**: 60+ instances → **Fixed: 0 instances**
**Lines**: 433 total (was 491)

**Fixes Applied**:
1. **File filtering** - REMOVED all `file NOT LIKE` clauses (18+ instances)
   - Moved to METADATA exclude_patterns
   - Added execution_scope='database'

2. **URL pattern matching** - Moved to Python frozensets (10+ instances)
   - Created OAUTH_URL_KEYWORDS frozenset
   - Lines 189-193: Filter OAuth endpoints in Python loop
   - Zero LIKE patterns in api_endpoints query

3. **State parameter detection** - Python filtering (8+ instances)
   - Created STATE_KEYWORDS frozenset
   - Lines 203-207: Check arguments in Python
   - Lines 216-221: Check assignments in Python
   - All filtering post-fetch

4. **Redirect validation** - Python filtering (20+ instances)
   - Created USER_INPUT_SOURCES, VALIDATION_KEYWORDS frozensets
   - Lines 266-273: Filter redirect calls in Python
   - Lines 282-287: Check validation in Python
   - Lines 309-317: Filter redirect assignments in Python
   - All queries use clean WHERE clauses

5. **Token URL detection** - Python filtering (12+ instances)
   - Lines 383-396: Token fragment check with `if any(pattern in expr)`
   - Lines 399-413: Token param check with Python list
   - Lines 416-430: Implicit flow check with Python conditions
   - Fetch all assignments once, filter multiple ways

**Key Changes**:
- WHERE clauses now minimal: `method IN ('GET', 'POST')` or `file = ?`
- All pattern matching moved to Python with frozensets
- File 58 lines shorter due to removed LIKE clauses
- Fetches are broader but filtered efficiently in Python

**Testing Status**: Not tested yet
**Verified Clean**: YES - 0 LIKE instances in WHERE clauses

---

### auth/password_analyze.py - FIXED ✅

**Status**: CLEAN - All LIKE cancer removed
**Original LIKE Count**: 40+ instances → **Fixed: 0 instances**
**Lines**: 519 total (was 521)

**Fixes Applied**:
1. **File filtering** - REMOVED all file checks, added to METADATA
2. **Function matching** - Created WEAK_HASH_KEYWORDS, PASSWORD_KEYWORDS frozensets
3. **Pattern matching** - All moved to Python filtering (15+ instances)
4. **Assignment filtering** - Fetch all, filter with frozensets (10+ instances)
5. **URL detection** - Python-side pattern matching (8+ instances)

**Testing Status**: Not tested yet
**Verified Clean**: YES - 0 LIKE instances

---

### auth/session_analyze.py - FIXED ✅

**Status**: CLEAN - All LIKE cancer removed
**Original LIKE Count**: 20+ instances → **Fixed: 0 instances**
**Lines**: 490 total (was 457)

**Fixes Applied**:
1. **File filtering** - REMOVED, added to METADATA exclude_patterns
2. **Cookie function matching** - Created COOKIE_FUNCTION_KEYWORDS frozenset
3. **Session matching** - Created SESSION_FUNCTION_KEYWORDS, SESSION_VAR_PATTERNS frozensets
4. **Assignment filtering** - Fetch all assignments, filter in Python (10+ instances)
5. **Raw SQL removed** - Replaced DISTINCT query with Python filtering

**Testing Status**: Not tested yet
**Verified Clean**: YES - 0 LIKE instances

**AUTH FOLDER COMPLETE**: 4/4 files fixed ✅

---

### auth/session_analyze.py - NOT STARTED ⏸️

**Status**: Unknown
**LIKE Count**: Unknown

---

### build/bundle_analyze.py - FIXED ✅

**Status**: CLEAN - All LIKE cancer removed
**Original LIKE Count**: 10+ instances → **Fixed: 0 instances**
**Lines**: 290 total (was 255)

**Fixes Applied**:
1. **File filtering** - Removed 6 `refs.src NOT LIKE` patterns (test/spec/mock)
   - Moved to METADATA exclude_patterns + Python filtering
2. **Package LIKE pattern** - Replaced `package LIKE ?` wildcard (line 155)
   - Now uses Python loop with exact match or startswith check
3. **Relative import filtering** - Removed 4 `value NOT LIKE` patterns
   - Moved to Python: `if clean.startswith('./') or clean.startswith('../')`
4. **Test patterns frozenset** - Created TEST_FILE_PATTERNS for O(1) lookups

**Key Changes**:
- Removed raw SQL with placeholders, now uses clean WHERE clauses
- All file path filtering done in Python after fetch
- Package matching uses Python string methods instead of SQL LIKE

**Testing Status**: Not tested yet
**Verified Clean**: YES - 0 LIKE instances

**BUILD FOLDER COMPLETE**: 1/1 files fixed ✅

---

### common/ (2 files) - CLEAN ✅ (No Refactor Needed)

**Status**: Utility module only - No database queries
- [SKIP] __init__.py - Export declarations only
- [SKIP] util.py - Pure computational functions (entropy, pattern detection, Base64 validation)

**Notes**: This folder contains utility functions with zero database access. No LIKE patterns, no SQL queries. Correct architecture - nothing to refactor.

---

### dependency/ (10 files) - ALL CLEAN ✅

**Status**: All files already properly refactored
- [CLEAN] bundle_size.py - Uses parameterized queries with placeholders, frozensets
- [CLEAN] config.py - Constants and frozensets only (no queries)
- [CLEAN] dependency_bloat.py - json.loads() on columns, no LIKE patterns
- [CLEAN] ghost_dependencies.py - Frozensets, json.loads(), Python filtering
- [CLEAN] peer_conflicts.py - json.loads(), pure Python version comparison
- [CLEAN] suspicious_versions.py - Frozenset lookups, json.loads()
- [CLEAN] typosquatting.py - Dict lookups, json.loads()
- [CLEAN] unused_dependencies.py - json.loads(), set operations
- [CLEAN] update_lag.py - json.loads(), hybrid approach (documented)
- [CLEAN] version_pinning.py - Frozenset iteration, json.loads()

**Key Patterns Found**:
- All use `build_query()` correctly
- JSON column parsing via `json.loads()` (correct pattern)
- Frozensets for O(1) lookups throughout
- Python-side filtering instead of SQL LIKE
- Zero LIKE patterns found

**DEPENDENCY FOLDER COMPLETE**: 10/10 files clean ✅

---

### deployment/ (3 files) - ALL CLEAN ✅

**Status**: All files already properly refactored (4 AWS CDK files skipped per user)
- [CLEAN] compose_analyze.py (594 lines) - Uses frozensets, json.loads(), Python filtering
- [CLEAN] docker_analyze.py (603 lines) - DockerfilePatterns dataclass with frozensets
- [CLEAN] nginx_analyze.py (460 lines) - Frozensets, build_query(), Python filtering
- [SKIPPED] cdk_analyze.py, cdk_iam_analyze.py, cdk_s3_analyze.py, cdk_security_analyze.py (written today by user)

**Key Patterns Found**:
- compose_analyze.py: SENSITIVE_ENV_PATTERNS, WEAK_PASSWORDS, DANGEROUS_MOUNTS, DANGEROUS_CAPABILITIES, INSECURE_SECURITY_OPTS frozensets
- docker_analyze.py: DockerfilePatterns dataclass with SENSITIVE_ENV_KEYWORDS, WEAK_PASSWORDS, VULNERABLE_BASE_IMAGES, SECRET_VALUE_PATTERNS regex
- nginx_analyze.py: NginxPatterns dataclass with SENSITIVE_PATHS, DEPRECATED_PROTOCOLS, WEAK_CIPHERS frozensets, CRITICAL_HEADERS dict
- All use `build_query()` correctly with clean WHERE clauses
- JSON column parsing via `json.loads()` throughout
- Zero LIKE patterns found

**DEPLOYMENT FOLDER COMPLETE**: 3/3 files clean ✅

---

### frameworks/ (6 files) - ALL FIXED ✅

**Status**: 6/6 files fixed, 0 remaining

- [FIXED] express_analyze.py (646 lines) - **11+ LIKE instances removed**
  - Line 262: `callee_function LIKE '%helmet%'`, `argument_expr LIKE '%helmet%'` → Python filter
  - Line 416: `callee_function LIKE '%bodyParser%'` → Python filter
  - Lines 458-460: 3x `caller_function NOT LIKE` → Python filter for service/repository/model
  - Lines 490-492: `argument_expr LIKE '%origin:%*%'`, `LIKE '%origin:%true%'` → Python filter
  - Line 541: `argument_expr LIKE '%csrf%'` → Python filter
  - Line 570: `callee_function LIKE '%session%'`, `argument_expr LIKE '%session%'` → Python filter
  - **Fix**: Fetch all calls, filter with frozenset patterns in Python

- [FIXED] fastapi_analyze.py (473 lines) - **11+ LIKE instances removed**
  - Lines 148-151: 4x database LIKE (`callee_function LIKE '%.query%'`, etc.) → Python filter with `.query in`, `startswith('db.')`
  - Line 297: `pattern LIKE '%websocket%'`, `LIKE '%ws%'` → Python filter
  - Line 304: 4x auth LIKE (`callee_function LIKE '%auth%'`, etc.) → Python filter
  - Line 383: `argument_expr LIKE '%timeout%'` → Python filter
  - **Fix**: Fetch broader queries, filter in Python with string operations

- [FIXED] flask_analyze.py (691 lines) - **32+ LIKE instances removed** (worst file so far!)
  - Line 265: 2x debug LIKE → Python filter with `.endswith('.run')`
  - Lines 294-298: 11x SECRET_VARS LIKE + environ/getenv LIKE → Python filter with frozenset
  - Lines 336-341: 2x file upload LIKE in raw SQL → Rewrote with multi-pass Python logic
  - Lines 378-381: 4x SQL injection LIKE (string format patterns) → Python filter
  - Lines 411-413: 3x open redirect LIKE → Python filter for request.*.get patterns
  - Line 442: 1x eval LIKE → Python filter
  - Lines 472-475, 493: 4x CORS wildcard LIKE → Python filter for assignments and function calls
  - Line 523: 1x deserialization LIKE → Python filter
  - Line 552: 1x werkzeug LIKE → Python filter
  - Lines 622-623: 3x session security LIKE → Python filter with SESSION_CONFIGS frozenset
  - **Fix**: Major refactoring across 10 methods, all patterns moved to Python

- [FIXED] nextjs_analyze.py (450 lines) - **46+ LIKE instances removed** (heavily infected!)
  - Lines 143-145: 3x path LIKE → Python filter with `'pages/api/' in path`
  - Line 161: 3x LIKE (argument_expr + 2 file) → Python filter for API routes and process.env
  - Lines 224-226: 3x LIKE (req.query/body/params) → Python filter
  - Line 264: 9x LIKE (NEXT_PUBLIC_ + 8 SENSITIVE_ENV_PATTERNS) → Python filter with startswith() and frozenset
  - Lines 285-286, 383, 403: 6x file LIKE → Python filter `'pages/api/' in file or 'app/api/' in file`
  - Lines 296-297: 16x LIKE (8 CSRF indicators x 2) → Python filter with CSRF_INDICATORS frozenset
  - Line 327: 5x LIKE (3 error patterns + 2 file) → Python filter
  - Line 347: 1x LIKE (dangerouslySetInnerHTML) → Python filter
  - **Fix**: Major refactoring across 8 checks, all LIKE patterns moved to Python

- [FIXED] react_analyze.py (812 lines) - **36+ LIKE instances removed**
  - Lines 193-194: 2x react imports LIKE → Python filter with `startswith('react/')`
  - Line 228: 1x dangerouslySetInnerHTML LIKE → Python filter
  - Line 314: 4x eval/JSX LIKE → Python filter for JSX patterns
  - Line 343: 5x target="_blank" LIKE → Python filter
  - Line 373: 2x innerHTML/outerHTML LIKE → Python filter with `endswith()`
  - Line 421: 3x hardcoded creds LIKE → Python filter for env vars
  - Line 531: 2x validation LIKE → Python filter for function names
  - Line 570: 3x useEffect LIKE → Python filter
  - Line 612: 2x auth LIKE → Python filter
  - Line 656: 1x form LIKE → Python filter `'<form' in`
  - Lines 680-681: 4x CSRF LIKE → Python filter
  - Line 713: 7x JSX user input LIKE → Python filter for patterns
  - **Fix**: Complete refactoring across 12 methods, all LIKE moved to Python

- [FIXED] vue_analyze.py (438 lines) - **33+ LIKE instances removed**
  - Lines 149-151: 5x v-html LIKE → Python filter with VUE_XSS_DIRECTIVES frozenset
  - Lines 223-229: 10x env/sensitive LIKE → Python filter with VUE_ENV_PREFIXES + SENSITIVE_PATTERNS frozensets
  - Line 249: 1x triple mustache LIKE → Python filter `'{{{' in`
  - Lines 270-274: 7x user input LIKE → Python filter with user_input_sources list
  - Line 294: 4x target="_blank" LIKE → Python filter
  - Line 315: 2x $refs LIKE → Python filter
  - Line 369: 6x storage LIKE → Python filter for sensitive patterns
  - **Fix**: Complete refactoring across 8 checks, all LIKE moved to Python

**Total LIKE Cancer Removed from frameworks/**: 169 instances (express 11 + fastapi 11 + flask 32 + nextjs 46 + react 36 + vue 33)

**FRAMEWORKS FOLDER COMPLETE**: 6/6 files fixed ✅

---

### logic/ (1 file) - FIXED ✅

**Status**: 1/1 file fixed

- [FIXED] general_logic_analyze.py (688 lines) - **54+ LIKE instances removed + 1 CRITICAL BUG FIXED**
  - Lines 207-211: 5x money/float LIKE → Python filter
  - Line 234: **CRITICAL BUG** - undefined `money_arg_conditions` → Fixed with Python filtering
  - Lines 259-261: 3x timezone LIKE → Python filter
  - Lines 283-286: 4x email regex LIKE → Python filter
  - Lines 308-314: 7x division LIKE → Python filter
  - Lines 325-328: 4x zero check LIKE → Python filter
  - Lines 420-430: 7x connection cleanup LIKE → Python fetch-filter-check pattern
  - Lines 487-499: 6x socket cleanup LIKE → Python filtering
  - Lines 521-524: 4x percentage calc LIKE → Python filtering
  - Lines 553-554: 2x stream cleanup LIKE → Python filtering
  - Lines 578-586: 4x async error handling LIKE → Python filtering
  - Lines 609-622: 8x lock/mutex LIKE → Python filtering
  - **Fix**: Complete refactoring across 12 checks, all LIKE moved to Python

**Total LIKE Cancer Removed from logic/**: 54 instances

**LOGIC FOLDER COMPLETE**: 1/1 file fixed ✅

---

### node/ (2 files) - ALL FIXED ✅

**Status**: 2/2 files fixed

- [FIXED] async_concurrency_analyze.py (950 lines) - **68+ LIKE instances removed**
  - Line 215: 6x file extension LIKE → REMOVED (METADATA filtering)
  - Line 233: 3x await check LIKE → Python filter
  - Lines 262-268: 3x promise LIKE → Python fetch-filter-check pattern
  - Line 302: 1x Promise.all LIKE → Python filter
  - Lines 367, 508, 567, 707: 16x file extension LIKE → REMOVED (METADATA filtering)
  - Lines 403-408: 8x counter LIKE (4 source_expr + 4 file) → Python filter
  - Line 456: 1x caller_function LIKE → Python filter
  - Lines 586-589: 4x stream cleanup LIKE → Python filter
  - Lines 793-802: 12x retry LIKE (3 target_var + 6 source_expr + 4 file) → Python filter
  - Lines 830-832: 5x singleton LIKE → Python filter
  - Lines 850-851: 3x lock/mutex LIKE → Python filter
  - Lines 880-888: 6x event listener LIKE → Python fetch-filter pattern
  - Lines 919-923: 6x callback hell LIKE → Python filter
  - **Fix**: All file extension checks removed (METADATA handles), all pattern matching moved to Python

- [FIXED] runtime_issue_analyze.py (598 lines) - **45 LIKE instances removed**
  - Lines 200, 245, 330, 361, 434, 536, 586: 28x file extension LIKE → REMOVED (METADATA filtering)
  - Lines 245, 260: 8x LIKE (2 template + 2 exec/spawn) → Python filter
  - Line 291: 2x spawn/shell LIKE → Python filter
  - Lines 388: 2x merge/extend LIKE → Python filter
  - Line 491: 1x RegExp LIKE → Python filter
  - **Fix**: All file extension checks removed, all pattern matching moved to Python

**Total LIKE Cancer Removed from node/**: 113 instances (68 + 45)

**NODE FOLDER COMPLETE**: 2/2 files fixed ✅

---

### orm/ (3 files) - NOT STARTED ⏸️

Files:
- prisma_analyze.py
- sequelize_analyze.py
- typeorm_analyze.py

---

### performance/ (1 file) - NOT STARTED ⏸️

Files:
- perf_analyze.py

---

### python/ (5 files) - NOT STARTED ⏸️

Files:
- async_concurrency_analyze.py
- python_crypto_analyze.py
- python_deserialization_analyze.py
- python_globals_analyze.py
- python_injection_analyze.py

---

### react/ (4 files) - NOT STARTED ⏸️

Files:
- component_analyze.py
- hooks_analyze.py
- render_analyze.py
- state_analyze.py

---

### secrets/ (1 file) - NOT STARTED ⏸️

Files:
- hardcoded_secret_analyze.py

---

### security/ (8 files) - NOT STARTED ⏸️

Files:
- api_auth_analyze.py
- cors_analyze.py
- crypto_analyze.py
- input_validation_analyze.py
- pii_analyze.py
- rate_limit_analyze.py
- sourcemap_analyze.py
- websocket_analyze.py

---

### sql/ (3 files) - NOT STARTED ⏸️

Files:
- multi_tenant_analyze.py
- sql_injection_analyze.py
- sql_safety_analyze.py

---

### terraform/ (1 file) - NOT STARTED ⏸️

Files:
- terraform_analyze.py

---

### typescript/ (1 file) - NOT STARTED ⏸️

Files:
- type_safety_analyze.py

---

### vue/ (6 files) - NOT STARTED ⏸️

Files:
- component_analyze.py
- hooks_analyze.py
- lifecycle_analyze.py
- reactivity_analyze.py
- render_analyze.py
- state_analyze.py

---

### xss/ (6 files) - NOT STARTED ⏸️

Files:
- dom_xss_analyze.py
- express_xss_analyze.py
- react_xss_analyze.py
- template_xss_analyze.py
- vue_xss_analyze.py
- xss_analyze.py

---

## ZERO FALLBACK POLICY (UNCHANGED)

This refactoring does NOT affect:
- ✅ No table existence checks
- ✅ No fallback queries
- ✅ No JSON fallbacks
- ✅ Hard failure on missing data

We're ONLY fixing the LIKE pattern cancer in WHERE clauses.

---

## TESTING CHECKLIST (Per File)

After fixing each file:

1. **Syntax Check**
   ```bash
   python -m compileall theauditor/rules/auth/jwt_analyze.py
   ```

2. **Database Test** (if plant/.pf exists)
   ```bash
   cd C:/Users/santa/Desktop/plant
   .venv/Scripts/python.exe -c "
   from theauditor.rules.auth.jwt_analyze import find_jwt_flaws
   from theauditor.rules.base import StandardRuleContext
   ctx = StandardRuleContext(
       file_path=None,
       content='',
       language='javascript',
       project_path='.',
       db_path='C:/Users/santa/Desktop/plant/.pf/repo_index.db'
   )
   findings = find_jwt_flaws(ctx)
   print(f'Found {len(findings)} issues')
   "
   ```

3. **Regression Check** (if .pf/history exists)
   ```bash
   aud full --offline  # Creates timestamped backup
   # Compare findings before/after in .pf/history/
   ```

---

## SESSION LOG

### 2025-10-30 Session 1
- Created progress.md
- **auth/ folder**: 4/4 files FIXED ✅
  - FIXED jwt_analyze.py (50+ LIKE → 0, 575 lines)
  - FIXED oauth_analyze.py (60+ LIKE → 0, 433 lines)
  - FIXED password_analyze.py (40+ LIKE → 0, 519 lines)
  - FIXED session_analyze.py (20+ LIKE → 0, 490 lines)
- **build/ folder**: 1/1 files FIXED ✅
  - FIXED bundle_analyze.py (10+ LIKE → 0, 290 lines)
- **common/ folder**: 2/2 files SKIPPED (utility module, no DB queries)
- **dependency/ folder**: 10/10 files ALREADY CLEAN ✅
  - All 10 files already use proper patterns (frozensets, json.loads, no LIKE)
  - No refactoring needed - previous work already complete
- Total LIKE instances removed: 180+
- Status: 15/56 files audited, 5 fixed, 10 already clean (26.8%)

**Patterns Established**:
- Frozensets for O(1) pattern matching
- Fetch-once-filter-multiple for large tables
- Python-side filtering replaces ALL LIKE clauses
- METADATA exclude_patterns replaces file filtering in WHERE
- Raw SQL removal (DISTINCT, complex joins → Python filtering)
- json.loads() for JSON columns is correct (not a refactor target)

**Next Steps**:
1. Move to deployment/ folder (3 files)
2. Continue alphabetically through remaining folders

---

## ONBOARDING NOTES

### For New Sessions
1. Read this file first
2. Check "CURRENT STATUS" section
3. Find file marked "IN PROGRESS"
4. Read that file's issues section
5. Start fixing

### File Naming Convention
- `*_analyze.py` = Rule files to fix
- `*_analyzer.py` = Old backups (skip these)
- `__init__.py` = Skip

### Key Files
- `theauditor/rules/base.py` - StandardRuleContext, StandardFinding
- `theauditor/indexer/schema.py` - build_query() function
- `TEMPLATE_STANDARD_RULE.py` - Reference template (may need updating)

---

## ESTIMATED TIMELINE

- **Audit Phase**: 1-2 days (56 files × 5 min/file = 5 hours)
- **Fix Phase**: 5-10 days (56 files × 1-2 hours/file = 56-112 hours)
- **Test Phase**: 2-3 days (integration testing)

**Total**: 8-15 days of focused work

---

## HANDOFF CHECKLIST

When handing off to another session:
- [ ] Update "Last Updated" date at top
- [ ] Update current file status (IN PROGRESS → FIXED)
- [ ] Add session log entry
- [ ] Mark next file as IN PROGRESS
- [ ] Commit progress.md changes

---

## KNOWN GOOD PATTERNS

### Frozenset for Function Matching
```python
JWT_FUNCTIONS = frozenset(['jwt.sign', 'jsonwebtoken.sign'])
conditions = ' OR '.join([f"callee_function = '{f}'" for f in JWT_FUNCTIONS])
where = f"({conditions})"
```

### Python-Side Filtering
```python
for file, line, expr in cursor.fetchall():
    if 'test' in file or 'spec' in file:
        continue
    if 'process.env' in expr:
        continue
    # Process finding
```

### JSON Column Parsing (OK)
```python
# This is CORRECT - parsing JSON from DB column
deps_json = row[0]
deps = json.loads(deps_json)
```

---

## VERSION HISTORY

### v1.5 - 2025-10-30
- common/ folder SKIPPED (2 files - utility module only)
- dependency/ folder COMPLETE (10/10 files already clean)
- 15/56 files audited (26.8%)
- 5 files fixed, 10 files already clean, 2 files skipped

### v1.4 - 2025-10-30
- build/ folder COMPLETE (1/1 files)
- Fixed bundle_analyze.py (10+ LIKE → 0)
- 5/56 files complete (8.9%)
- 180+ total LIKE instances removed

### v1.3 - 2025-10-30
- auth/ folder COMPLETE (4/4 files)
- Fixed password_analyze.py (40+ LIKE → 0)
- Fixed session_analyze.py (20+ LIKE → 0)
- 4/56 files complete (7.1%)
- 170+ total LIKE instances removed

### v1.2 - 2025-10-30
- Fixed oauth_analyze.py (60+ LIKE instances removed)
- 2/56 files complete (3.6%)
- Established fetch-once-filter-multiple pattern

### v1.1 - 2025-10-30
- Fixed jwt_analyze.py (50+ LIKE instances removed)
- First file complete: 1/56 done
- Pattern established for remaining files

### v1.0 - 2025-10-30
- Initial progress.md creation
- Documented jwt_analyze.py issues (50+ LIKE instances)
- Established refactoring strategy
- Set up file tracking structure
