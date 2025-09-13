# TheAuditor Rule Migration Roadmap

## CRITICAL: Database-First Architecture

### The Golden Standard
**ALL rules must query the database, NOT traverse ASTs!**

The indexer has already parsed everything into 19 tables with 100,000+ records:
- **function_call_args** (9,679): All function calls with arguments
- **assignments** (2,752): All variable assignments  
- **symbols** (84,434): All code symbols
- **sql_queries** (4,723): All SQL queries
- **api_endpoints** (97): All REST endpoints
- **cfg_blocks** (10,439): Control flow graph blocks

### Correct Pattern
```python
def find_*_issues(context: StandardRuleContext) -> List[StandardFinding]:
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    # Query indexed data - NO AST traversal!
    cursor.execute("""
        SELECT file, line, argument_expr
        FROM function_call_args
        WHERE callee_function LIKE '%dangerous%'
    """)
    
    # Process results
    for file, line, arg in cursor.fetchall():
        # Create findings...
```

## Current Status: 33 Working, 32 Legacy

### ✅ WORKING RULES (33)
These have correct `StandardRuleContext` signature and will run:

#### /auth (2)
- `jwt.py` - find_jwt_flaws ✅
- `jwt_detect.py` - find_jwt_flaws ✅

#### /build (1)
- `bundle_analyze.py` - find_bundle_issues ✅

#### /deployment (2)
- `compose_analyze.py` - find_compose_issues ✅
- `nginx_analyze.py` - find_nginx_issues ✅

#### /frameworks (6)
- `express_analyze.py` - find_express_issues ✅
- `fastapi_analyze.py` - find_fastapi_issues ✅
- `flask_analyze.py` - find_flask_issues ✅
- `nextjs_analyze.py` - find_nextjs_issues ✅
- `react_analyze.py` - find_react_issues ✅
- `vue_analyze.py` - find_vue_issues ✅

#### /logic (1)
- `general_logic_analyze.py` - find_logic_issues ✅

#### /node (2)
- `async_concurrency_analyze.py` - find_async_concurrency_issues ✅
- `runtime_issue_analyze.py` - find_runtime_issues ✅

#### /orm (3)
- `prisma_analyze.py` - find_prisma_issues ✅
- `sequelize_analyze.py` - find_sequelize_issues ✅
- `typeorm_analyze.py` - find_typeorm_issues ✅

#### /performance (1)
- `perf.py` - find_performance_issues ✅

#### /python (1)
- `async_concurrency_analyze.py` - find_async_concurrency_issues ✅

#### /react (1)
- `hooks_analyze.py` - find_react_hooks_issues ✅

#### /secrets (1)
- `hardcoded_secret_analyze.py` - find_hardcoded_secrets ✅

#### /security (7)
- `cors_analyze.py` - find_cors_issues ✅
- `crypto_analyze.py` - find_crypto_issues ✅
- `input_validation_analyze.py` - find_input_validation_issues ✅
- `pii_analyze.py` - find_pii_issues ✅
- `rate_limit_analyze.py` - find_rate_limit_issues ✅
- `sourcemap_detect.py` - find_sourcemap_issues ✅
- `websocket_analyze.py` - find_websocket_issues ✅

#### /sql (3)
- `multi_tenant_analyze.py` - find_multi_tenant_issues ✅
- `sql_injection_analyze.py` - find_sql_injection_issues ✅
- `sql_safety_analyze.py` - find_sql_safety_issues ✅

#### /typescript (1)
- `type_safety_analyze.py` - find_type_safety_issues ✅

#### /xss (1)
- `xss_analyze.py` - find_xss_issues ✅

### ❌ LEGACY FILES (32) - Old backups, won't run
These are kept for safety but have wrong signatures:
- All `*_analyzer.py` files
- All `*_detector.py` files
- `performance.py` (replaced by `perf.py`)
- `xssdetection.py` (replaced by `xss_analyze.py`)
- `reactivity_analyzer.py` (no replacement yet)
- `api_auth_detector.py` (replaced by functionality in other files)

## Verification Checklist

### Each rule MUST have:
1. ✅ Function name starting with `find_`
2. ✅ Single parameter: `context: StandardRuleContext`
3. ✅ Return type: `List[StandardFinding]`
4. ✅ Database queries ONLY (no AST traversal)
5. ✅ Proper SQL queries against indexed tables
6. ✅ No file I/O operations
7. ✅ No tree walking/parsing

### Common Tables to Query:
- `function_call_args` - For detecting dangerous function calls
- `assignments` - For finding hardcoded secrets, configs
- `symbols` - For tracking variables, functions, classes
- `sql_queries` - For SQL injection detection
- `api_endpoints` - For authentication/authorization issues
- `cfg_blocks` - For control flow analysis
- `function_returns` - For return value analysis

## Roadmap for Completion

### Phase 1: Critical Verification ✅ DONE
- Fixed `__init__.py` imports in /auth, /build, /deployment
- All 33 rules now properly discoverable and runnable

### Phase 2: Clean Legacy References
1. Update all `__init__.py` files to import from `*_analyze.py` not `*_analyzer.py`
2. Remove references to old backup files from any imports

### Phase 3: Quality Assurance
1. Verify each rule uses database queries, not AST
2. Check for any remaining file I/O operations
3. Ensure all follow StandardRuleContext/StandardFinding pattern

### Phase 4: Documentation
1. Update this roadmap as rules are verified
2. Document any legitimate hybrid approaches (like React hooks needing semantic analysis)
3. Create examples of proper database queries for common patterns

## Migration Patterns

### Pattern 1: Function Call Detection
```sql
SELECT file, line, callee_function, argument_expr
FROM function_call_args
WHERE callee_function LIKE '%dangerous%'
```

### Pattern 2: Assignment Detection
```sql
SELECT file, line, target_var, source_expr
FROM assignments
WHERE target_var LIKE '%secret%'
  AND source_expr LIKE '"%"'
```

### Pattern 3: SQL Injection Detection
```sql
SELECT file_path, line_number, query_text
FROM sql_queries
WHERE query_text LIKE '%||%'
   OR query_text LIKE '%+%'
   OR query_text LIKE '%${%'
```

### Pattern 4: API Authentication
```sql
SELECT file, pattern, method, controls
FROM api_endpoints
WHERE controls IS NULL
   OR controls NOT LIKE '%auth%'
```

## Success Metrics
- ✅ 33/65 rules are standardized and working
- ❌ 32 legacy files remain as backups
- 🎯 Goal: 100% of active rules using database queries
- 📊 Current: ~50% properly migrated

## Next Steps
1. Continue verifying all `*_analyze.py` files use proper database queries
2. Remove any AST traversal code
3. Update documentation with examples
4. Test each rule with sample projects
5. Create performance benchmarks

---
*Last updated: 2024-12-13*