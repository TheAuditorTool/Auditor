# Technical Onboarding: Critical Taint Analysis Issues

## Issue 1: Migration Files as False Positive Sinks (CRITICAL)

### What's Happening:
Migration files (e.g., `20250914000009-add-scan-to-audit-operation.js`) are appearing as SQL injection sinks in taint flows, creating paths like:
```
account.controller.ts (source: req.body)
  → EXPRESS_MIDDLEWARE_CHAIN
  → migration.js (sink: queryInterface.sequelize.query)
```

### Why This is Wrong:
1. **Temporal Mismatch**: Migrations run at deploy/startup time, NOT runtime
   - Controllers handle runtime user requests
   - Migrations modify database schema during deployment
   - There is NO data flow between them

2. **Invalid Edge Creation**: The path shows `EXPRESS_MIDDLEWARE_CHAIN` connecting routes to migrations
   - Express middleware chains are for HTTP request handling
   - Migrations are never part of Express middleware
   - This edge type is completely invalid for this connection

### Technical Root Cause:
```python
# In ifds_analyzer.py:_flow_function_express_controller_entry()
# The function queries express_middleware_chains table correctly
# But somewhere an edge is being created that shouldn't exist
```

The actual problem appears to be in how backward traces are constructed. When the analyzer finds a sink in a migration file, it's somehow connecting it to controllers via phantom express_middleware_chain edges.

### Impact:
- 69 of 92 flows in Plant are false positives
- Makes real vulnerabilities harder to find
- Destroys trust in the tool

### Solution Approach:
1. **Option A**: Filter out migration files from being sinks
   ```python
   # In sink discovery
   if '/migrations/' in file_path:
       continue  # Skip migration files
   ```

2. **Option B**: Fix edge creation to never connect runtime code to migrations
   ```python
   # In IFDS analyzer
   if 'migration' in target_file and edge_type == 'express_middleware_chain':
       continue  # Invalid edge
   ```

3. **Option C** (BEST): Separate static vs runtime sinks
   - Mark migrations as "static_sink" type
   - Only trace runtime sources to runtime sinks
   - Keep migrations for separate deployment security analysis

---

## Issue 2: Joi Validation Not Detected as Sanitizer

### What's Happening:
PlantFlow uses Joi validation but shows 0 sanitized flows (all 64 marked vulnerable).

### Current State:
```sql
-- validation_framework_usage table
-- Only 2 Joi validators marked with is_validator=1
-- Zod has 3 parseAsync marked
-- But Joi.validateAsync isn't being tracked properly
```

### Technical Root Cause:

1. **Extractor Issue** (`security_extractors.js`):
   ```javascript
   function isValidatorMethod(callee) {
       const VALIDATOR_METHODS = [
           'parse', 'parseAsync', 'safeParse', 'safeParseAsync',
           'validate', 'validateAsync', 'validateSync',
           'isValid', 'isValidSync'
       ];
       // This SHOULD catch Joi methods but isn't
   }
   ```

2. **Pattern Matching Issue**:
   - Joi patterns: `schema.validateAsync()`, `Joi.object().validate()`
   - Current extraction misses chained patterns
   - Only catching direct calls, not builder patterns

3. **is_validator Flag**:
   - Most Joi calls marked as `is_validator=0` (schema builders)
   - Actual validation calls not differentiated properly

### Impact:
- PlantFlow shows 100% vulnerable when it's actually ~50% sanitized
- False positives erode trust
- Can't learn from Joi validation patterns

### Solution Approach:
1. **Fix JavaScript Extractor**:
   ```javascript
   // Detect Joi validation patterns
   if (callee.includes('.validateAsync') ||
       callee.includes('.validate') ||
       callee === 'celebrate') {  // Joi middleware wrapper
       is_validator = true;
   }
   ```

2. **Post-Processing Fix**:
   ```sql
   UPDATE validation_framework_usage
   SET is_validator = 1
   WHERE framework = 'joi'
   AND method IN ('validate', 'validateAsync', 'validateSync')
   ```

---

## Issue 3: Cross-Boundary Flows (Frontend→Backend) 99.5% Broken

### What's Happening:
- 194 frontend API calls detected across all projects
- Only 1 connected to backend (0.5% success rate)
- Missing primary attack vector (browser → server → database)

### Current State:
```python
# Frontend API calls exist in function_call_args:
# fetch('/api/users'), axios.post('/api/products')

# Backend endpoints exist in api_endpoints:
# GET /api/users, POST /api/products

# But they're not connected in taint flows
```

### Technical Root Cause:

1. **No Cross-Boundary Flow Function**:
   ```python
   # MISSING in ifds_analyzer.py:
   def _flow_function_cross_boundary_api_call(self, ap: AccessPath):
       """When trace reaches req.body in backend controller,
       check if this endpoint is called from frontend."""
       # This function doesn't exist
   ```

2. **Deleted Heuristics** (Phase 6.8):
   - 550 lines of string matching were deleted
   - Created 52 "synthetic sources" but 0 working flows
   - Was using regex and path normalization (correctly identified as cancer)

3. **Missing Database Schema**:
   ```sql
   -- Need a table like:
   CREATE TABLE frontend_api_calls (
       file TEXT,
       line INTEGER,
       method TEXT,  -- GET, POST, etc
       url_literal TEXT,  -- '/api/users'
       body_variable TEXT  -- Variable being sent
   );
   ```

### Impact:
- Can't trace user input → API → database
- Missing 99.5% of real attack surface
- No visibility into client-side vulnerabilities flowing to server

### Solution Approach (CORRECT):

1. **AST Extraction Phase**:
   ```javascript
   // Extract structured API call data
   // fetch('/api/users', {method: 'POST', body: userData})
   // → {url: '/api/users', method: 'POST', body_var: 'userData'}
   ```

2. **Database Matching**:
   ```sql
   -- Match frontend calls to backend endpoints
   SELECT f.file as frontend_file,
          e.file as backend_file
   FROM frontend_api_calls f
   JOIN api_endpoints e
     ON f.url_literal = e.full_path
     AND f.method = e.method
   ```

3. **IFDS Flow Function**:
   ```python
   def _flow_function_cross_boundary(self, ap: AccessPath):
       if ap.base == 'req' and ap.fields[0] == 'body':
           # Find frontend calls to this endpoint
           # Create AccessPath for frontend body_variable
           # Continue trace in frontend code
   ```

---

## Priority Order:

1. **Fix Migration Issue FIRST** (High false positive rate)
   - Easiest fix: Filter out migration files
   - Most impact: Removes 75% of false positives

2. **Fix Cross-Boundary SECOND** (Biggest capability gap)
   - Hardest fix: Needs new extraction + flow function
   - Most value: Unlocks real security analysis

3. **Fix Joi Detection LAST** (Least critical)
   - Medium difficulty: Update extractor patterns
   - Least impact: Only affects PlantFlow

---

## Testing After Fixes:

```bash
# After migration fix
cd plant && aud full --offline
# Should see: ~20-30 flows instead of 92

# After cross-boundary fix
cd plant && aud full --offline
# Should see: 100+ cross-boundary flows

# After Joi fix
cd plantflow && aud full --offline
# Should see: ~30 sanitized flows
```

---

## Key Architecture Principles:

1. **NO HEURISTICS**: All connections must be from AST facts
2. **NO STRING MATCHING**: Use database joins, not regex
3. **RESPECT TEMPORAL BOUNDARIES**: Deploy-time ≠ Runtime
4. **TRACE ACTUAL DATA FLOW**: Not just function proximity

The migration issue is the most important to fix first because it's actively producing false positives and undermining the entire analysis.