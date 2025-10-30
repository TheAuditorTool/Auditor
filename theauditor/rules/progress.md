# Rules Refactoring Progress - Schema Normalization

**Version**: 1.0
**Branch**: pythonparity
**Started**: 2025-10-30
**Last Updated**: 2025-10-30

---


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

## 🔥 AUDIT PROTOCOL - ABSOLUTE RULES 🔥

**ALPHABETICAL ORDER - NO EXCEPTIONS**

### Folder Order (A → Z):
1. auth/
2. build/
3. frameworks/
4. github_actions/
5. logic/
6. node/
7. orm/
8. performance/
9. python/
10. react/
11. secrets/
12. security/
13. sql/
14. terraform/
15. typescript/
16. vue/
17. xss/
18. TEMPLATE files (at root)

### File Processing (PER FOLDER, A → Z):

**Example - auth/ folder:**
1. jwt_analyze.py (first alphabetically)
2. oauth_analyze.py
3. password_analyze.py
4. session_analyze.py

**Example - build/ folder:**
1. bundle_analyze.py

### PER FILE WORKFLOW:

**STEP 1: READ ENTIRE FILE**
- Use Read tool with NO offset, NO limit
- Read ENTIRE file start to finish
- **BANNED**: grep, search, partial reads, line ranges
- **AUDIT FAILURE** if you use grep/search/partial

**STEP 2: AUDIT AGAINST SCHEMA.PY**
- Check ALL `cursor.execute()` calls
- Verify columns exist in schema.py
- Look for removed columns:
  - ❌ `api_endpoints.controls`
  - ❌ `sql_queries.tables`
  - ❌ `assignments.source_vars`
  - ❌ `function_returns.return_vars`
  - ❌ `react_components.hooks_used`
  - ❌ `react_hooks.dependency_vars`
  - ❌ `imports.imported_names`
- Look for missed JOIN opportunities with junction tables

**STEP 3: FIX ON THE SPOT**
- Replace removed columns with proper JOINs
- Use `GROUP_CONCAT()` to aggregate junction table rows
- Anchor ALL fixes to schema.py definitions

**STEP 4: COMPILE**
- Run `python -m py_compile <file>`
- Verify no syntax errors

**STEP 5: DOCUMENT IN PROGRESS.MD**
- Add one line: `- [x] folder/filename.py - FIXED/CLEAN - Quick description`
- Example: `- [x] auth/jwt_analyze.py - CLEAN - No schema violations`
- Example: `- [x] security/api_auth_analyze.py - FIXED - controls → api_endpoint_controls JOIN`

**STEP 6: MOVE TO NEXT FILE**
- Next alphabetical file in same folder
- If folder complete, move to next alphabetical folder

---

## 📊 AUDIT PROGRESS TRACKING

**Current Folder**: sql/
**Current File**: multi_tenant_analyze.py
**Files Completed**: 48/62 (77%)

### Completed Files:
- [x] auth/jwt_analyze.py - Passed inspection
- [x] auth/oauth_analyze.py - Passed inspection
- [x] auth/password_analyze.py - Passed inspection
- [x] auth/session_analyze.py - Passed inspection
- [x] build/bundle_analyze.py - Passed inspection
- [x] deployment/aws_cdk_encryption_analyze.py - Passed inspection
- [x] deployment/aws_cdk_iam_wildcards_analyze.py - Passed inspection
- [x] deployment/aws_cdk_s3_public_analyze.py - Passed inspection
- [x] deployment/aws_cdk_sg_open_analyze.py - Passed inspection
- [x] deployment/compose_analyze.py - Passed inspection
- [x] deployment/docker_analyze.py - Passed inspection
- [x] deployment/nginx_analyze.py - Passed inspection
- [x] frameworks/express_analyze.py - Passed inspection
- [x] frameworks/fastapi_analyze.py - Passed inspection
- [x] frameworks/flask_analyze.py - Passed inspection
- [x] frameworks/nextjs_analyze.py - Passed inspection
- [x] frameworks/react_analyze.py - Passed inspection
- [x] github_actions/artifact_poisoning.py - Passed inspection
- [x] github_actions/excessive_permissions.py - Passed inspection
- [x] github_actions/reusable_workflow_risks.py - Passed inspection (user verified)
- [x] github_actions/script_injection.py - Passed inspection (user verified)
- [x] github_actions/unpinned_actions.py - Passed inspection (user verified)
- [x] github_actions/untrusted_checkout.py - Passed inspection (user verified)
- [x] logic/general_logic_analyze.py - Passed inspection
- [x] node/async_concurrency_analyze.py - Passed inspection
- [x] node/runtime_issue_analyze.py - Passed inspection
- [x] orm/prisma_analyze.py - Passed inspection
- [x] orm/sequelize_analyze.py - Passed inspection
- [x] orm/typeorm_analyze.py - Passed inspection
- [x] performance/perf_analyze.py - Passed inspection
- [x] python/async_concurrency_analyze.py - Passed inspection
- [x] python/python_crypto_analyze.py - Passed inspection
- [x] python/python_deserialization_analyze.py - Passed inspection
- [x] python/python_globals_analyze.py - Passed inspection
- [x] python/python_injection_analyze.py - Passed inspection
- [x] react/component_analyze.py - Passed inspection
- [x] react/hooks_analyze.py - FIXED - dependency_vars → react_hook_dependencies JOIN (2 locations)
- [x] react/render_analyze.py - Passed inspection
- [x] react/state_analyze.py - Passed inspection
- [x] secrets/hardcoded_secret_analyze.py - Passed inspection
- [x] security/api_auth_analyze.py - Passed inspection
- [x] security/cors_analyze.py - Passed inspection
- [x] security/crypto_analyze.py - Passed inspection
- [x] security/input_validation_analyze.py - Passed inspection
- [x] security/pii_analyze.py - Passed inspection
- [x] security/rate_limit_analyze.py - Passed inspection
- [x] security/sourcemap_analyze.py - Passed inspection
- [x] security/websocket_analyze.py - Passed inspection


## 🎯 AUDIT ONBOARDING FOR FUTURE SESSIONS

**If you're continuing this audit** (me, future me, or another AI):

1. **Read schema.py** (2851 lines) - ABSOLUTE REQUIREMENT before touching ANY rule
2. **Check progress.md** - Find "NEXT TO AUDIT" marker above
3. **For each file**:
   - Read entire file (no grep shortcuts)
   - Search for ALL `cursor.execute()` calls
   - Check each query against schema.py column definitions
   - Look for removed columns (controls, hooks_used, dependency_vars, imported_names, tables)
   - Look for junction tables that should be JOINed (api_endpoint_controls, sql_query_tables, assignment_sources, react_hook_dependencies, etc.)
   - Fix on the spot if schema violation found
   - Mark as [x] FIXED or [ ] CLEAN in audit log above
   - Compile with `python -m py_compile`
   - Document fix in "POST-AUDIT FIXES" section
   - Move to next file

4. **Common Schema Violations to Check**:
   - ❌ `api_endpoints.controls` → ✅ `JOIN api_endpoint_controls`
   - ❌ `sql_queries.tables` → ✅ `JOIN sql_query_tables`
   - ❌ `assignments.source_vars` → ✅ `JOIN assignment_sources`
   - ❌ `function_returns.return_vars` → ✅ `JOIN function_return_sources`
   - ❌ `react_components.hooks_used` → ✅ `JOIN react_component_hooks`
   - ❌ `react_hooks.dependency_vars` → ✅ `JOIN react_hook_dependencies`
   - ❌ `import_styles.imported_names` → ✅ `JOIN import_style_names`

5. **Prefix/Suffix Matching Audit**:
   - `LIKE 'pattern%'` → `startswith('pattern')`
   - `LIKE '%pattern'` → `endswith('pattern')`
   - `LIKE '%pattern%'` → `'pattern' in string`

6. **Update This Section** after each file with findings

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
