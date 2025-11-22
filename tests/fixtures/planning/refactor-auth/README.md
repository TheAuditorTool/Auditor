# Refactor Auth Fixture (Auth0 → AWS Cognito Migration)

## Purpose
Simulates a real-world authentication provider migration project:
- **Before**: Auth0-based authentication
- **After**: AWS Cognito-based authentication

Tests TheAuditor's ability to track:
- Import chain resolution across 3+ modules
- Taint flow from request → validation → database
- API migration patterns (Auth0 SDK → Cognito SDK)
- Cross-file dependency tracking

This fixture demonstrates **how TheAuditor handles refactoring scenarios** where function signatures, import paths, and security boundaries change.

## Project Structure

```
refactor-auth/
├── spec.yaml           # Verification rules for both before/after states
├── before/             # Auth0 implementation
│   ├── auth.py         # Main auth service (Auth0)
│   ├── validators/
│   │   └── token_validator.py
│   └── exceptions.py
└── after/              # Cognito implementation
    ├── auth.py         # Main auth service (Cognito)
    ├── validators.py   # Consolidated validators
    └── exceptions.py   # Same exceptions (reused)
```

## Framework Patterns Included

### 1. Import Chain Resolution (before/)
- **3-level import chain**: `auth.py` → `validators/token_validator.py` → `exceptions.py`
- **Cross-module taint**: Token flows through validate_auth0_token() → extract_user_id() → SQL query
- **Package imports**: Tests resolution of `from validators import X` package-style imports

### 2. Import Chain Resolution (after/)
- **2-level import chain**: `auth.py` → `validators.py` (flattened)
- **Import consolidation**: Multiple validator functions in single module
- **Tests migration tracking**: validators/ package → validators.py single file

### 3. Taint Flow Analysis (Both Versions)

**Taint Source**: HTTP request token (request.headers['Authorization'])

**Taint Flow Chain**:
```
request.headers['Authorization']
  → AuthService.verify_token(token)
    → validate_auth0_token(token) / validate_cognito_token(token)
      → extract_user_id(payload)
        → AuthService._get_user_from_database(user_id)
          → sqlite3.execute("SELECT ... WHERE cognito_user_id = ?", (user_id,))
```

**Sink**: Raw SQL query with untrusted token-derived parameter

### 4. API Migration Patterns

| Pattern | Before (Auth0) | After (Cognito) |
|---|---|---|
| **SDK Import** | `from auth0 import Auth0Client` | `from aws_cognito import CognitoIdentityClient` |
| **Client Init** | `Auth0Client(domain, client_id, client_secret)` | `CognitoIdentityClient(user_pool_id, client_id)` |
| **Token Validation** | `validate_auth0_token(token)` | `validate_cognito_token(token)` |
| **User ID Extraction** | `payload['sub']` | `payload['cognito:username']` |
| **Database Column** | `auth0_user_id` | `cognito_user_id` |

### 5. Security Controls Tested

Both versions include:
- **JWT token validation** with expiry checking
- **User lookup** from local database using token claims
- **Exception handling** for InvalidTokenError, ExpiredTokenError
- **Environment variable** configuration (Auth0/Cognito credentials)

## Populated Database Tables

After running `aud index` from TheAuditor root:

| Table | Before Count | After Count | What It Tests |
|---|---|---|---|
| **symbols** | ~50 | ~50 | Function/class extraction |
| **imports** | 8 | 7 | Import chain tracking (3-level → 2-level) |
| **function_calls** | ~30 | ~30 | Call chain analysis |
| **sql_queries** | 1 | 1 | Raw SQL extraction from _get_user_from_database() |
| **assignments** | ~20 | ~20 | Variable flow tracking |
| **refs** | ~40 | ~40 | Cross-file symbol references |

**Key Difference**: After has 1 fewer import (validators package collapsed to single file)

## Sample Verification Queries

### Query 1: Find All Token Validation Functions

```sql
SELECT
    s.name,
    s.type,
    s.file
FROM symbols s
WHERE s.name LIKE '%validate%token%'
  AND s.file LIKE '%refactor-auth%'
ORDER BY s.file;
```

**Expected Results**:
- `before/validators/token_validator.py`: validate_auth0_token
- `after/validators.py`: validate_cognito_token

### Query 2: Track Token Taint Flow (Find SQL Sinks)

```sql
SELECT
    sq.query_string,
    sq.file,
    sq.line,
    fc.function_name
FROM sql_queries sq
JOIN function_calls fc
    ON sq.file = fc.file
WHERE sq.file LIKE '%refactor-auth%'
ORDER BY sq.file;
```

**Expected Results**: 2 queries (before and after) selecting from users table where cognito_user_id/auth0_user_id parameter

### Query 3: Compare Import Patterns (Before vs After)

```sql
SELECT
    i.file,
    i.line,
    i.module_path,
    i.imported_names
FROM imports i
WHERE i.file LIKE '%refactor-auth/before%'
   OR i.file LIKE '%refactor-auth/after%'
ORDER BY i.file, i.line;
```

**Analysis**:
- Before: `from validators.token_validator import validate_auth0_token` (package import)
- After: `from validators import validate_cognito_token` (module import)

### Query 4: Find Exception Handling Patterns

```sql
SELECT
    s.name,
    s.file,
    s.type
FROM symbols s
WHERE s.name LIKE '%Error'
  AND s.file LIKE '%refactor-auth%'
ORDER BY s.file;
```

**Expected Results**: InvalidTokenError, ExpiredTokenError in both before/after (reused)

## Testing Use Cases

This fixture enables testing:

1. **Import Resolution Changes**: Verify indexer handles package → module import refactoring
2. **Taint Analysis Continuity**: Ensure taint flow is tracked across refactor (Auth0 → Cognito)
3. **API Migration Patterns**: Detect breaking changes in authentication flow
4. **SQL Injection Risk**: Both versions have same SQL sink (should be flagged consistently)
5. **Cross-File Dependency Tracking**: Validate ref resolution through import chains

## How to Use This Fixture

1. **Index the project**:
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index
   ```

2. **Run spec.yaml verification**:
   ```bash
   # From fixture directory
   cd tests/fixtures/planning/refactor-auth
   # Verify before state
   # Verify after state
   # (spec.yaml rules should detect both patterns)
   ```

3. **Query specific patterns**:
   ```bash
   aud context query --symbol validate_auth0_token --show-callers
   aud context query --symbol validate_cognito_token --show-callers
   ```

4. **Compare taint flows**:
   ```sql
   -- Find all paths from verify_token to SQL
   SELECT * FROM function_calls
   WHERE function_name LIKE '%verify_token%'
     AND file LIKE '%refactor-auth%';
   ```

## Expected Schema Population

When this fixture is indexed, expect:

- ✅ **3-level import chain** in before/ (auth → validators.token_validator → exceptions)
- ✅ **2-level import chain** in after/ (auth → validators → exceptions)
- ✅ **Cross-file refs** from auth.py to validator functions
- ✅ **Taint flow** from function params → SQL query in both versions
- ✅ **Exception class** definitions tracked in symbols
- ✅ **Environment variable reads** (os.getenv) in both versions

## Diff Summary

| Aspect | Lines Changed | Impact |
|---|---|---|
| **Import statements** | 3 | Package → module imports |
| **SDK client init** | 5 | Auth0 → Cognito parameters |
| **Token validation** | 1 function call | Different validator name |
| **User ID extraction** | 1 field access | payload['sub'] → payload['cognito:username'] |
| **Database column** | 1 SQL string | auth0_user_id → cognito_user_id |
| **Total affected** | ~20 lines | Same security posture, different provider |

This fixture proves TheAuditor can track API migrations without losing security insights.
