# TheAuditor Database Schema Reference

## CRITICAL UPDATE: True Golden Standard Rule Architecture (2024-12-13)

### Executive Summary - MAJOR CORRECTION

**THE PROBLEM**: The previous "Golden Standard" with jwt_detect.py (505 lines of AST traversal) is **fundamentally wrong**. It ignores the database and re-parses everything from scratch, defeating the entire purpose of the indexer.

**THE SOLUTION**: Rules must query the database, NOT traverse ASTs. The indexer has already extracted ALL the data we need into 19 tables with 100,000+ records.

### The Truth About Rule Architecture

#### What We Were Doing WRONG ❌
```python
# jwt_detect.py - 505 lines of UNNECESSARY AST traversal
class TreeSitterJWTAnalyzer(BaseJWTAnalyzer):
    def _visit_node(self, node, depth: int = 0):
        # Re-parsing AST that indexer already parsed!
        if node.type == "call_expression":
            self._analyze_call(node)
        for child in node.children:
            self._visit_node(child, depth + 1)  # Wasteful recursion
```

#### What We Should Be Doing RIGHT ✅
```python
# jwt_detect.py - TRUE Golden Standard (~100 lines)
def find_jwt_flaws(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect JWT vulnerabilities using INDEXED DATA."""
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    # Query pre-indexed JWT calls
    cursor.execute("""
        SELECT file, line, argument_expr, param_name
        FROM function_call_args
        WHERE callee_function IN ('jwt.sign', 'jsonwebtoken.sign')
    """)
    
    # Process results - NO AST traversal needed!
    for file, line, arg_expr, param in cursor.fetchall():
        if param == 'arg1' and len(arg_expr) < 32:
            # Weak secret detected
        if param == 'arg2' and 'expiresIn' not in arg_expr:
            # Missing expiration detected
```

### Migration Strategy - Complete Rewrite Required

**All 36 rules need COMPLETE rewrite**, not refactoring. The current approach is architecturally wrong.

#### Phase 1: Foundation ✅ COMPLETE (but needs revision)
- Created StandardRuleContext and StandardFinding
- BUT: Context helpers like `get_ast()` encourage wrong patterns
- SHOULD: Provide database query helpers instead

#### Phase 2: TRUE Golden Standard (TO DO)
Create a REAL reference implementation that:
1. **Queries the database** (function_call_args, assignments, symbols)
2. **Never parses ASTs** (indexer already did this)
3. **~100 lines total** (not 500+)
4. **SQL-based detection** (not tree traversal)

### Rule Categories by Implementation Pattern

#### 1. Function Call Analysis Rules
Query `function_call_args` table:
- JWT (jwt.sign, jwt.verify)
- Crypto (bcrypt.hash, md5, sha1)
- Express middleware (helmet, cors, csrf)
- Database operations (query, execute)

#### 2. Assignment Analysis Rules
Query `assignments` table:
- Hardcoded secrets (JWT_SECRET = "weak")
- Environment variables (process.env.SECRET)
- Configuration values

#### 3. API Endpoint Rules
Query `api_endpoints` table:
- Missing authentication
- Exposed admin routes
- CORS misconfigurations

#### 4. SQL Injection Rules
Query `sql_queries` table:
- String concatenation in queries
- Non-parameterized queries
- Dynamic table names

#### 5. Symbol Analysis Rules
Query `symbols` table:
- Unused functions
- Missing exports
- Circular dependencies

### Database Tables Summary (What's Actually Available)

| Table | Records | Purpose |
|-------|---------|---------|
| **function_call_args** | 9,679 | All function calls with arguments |
| **assignments** | 2,752 | All variable assignments |
| **symbols** | 84,434 | All code symbols (functions, classes, properties) |
| **sql_queries** | 4,723 | All SQL queries found |
| **api_endpoints** | 97 | All REST endpoints |
| **refs** | 2,063 | All imports/exports |
| **files** | 186 | All analyzed files |
| **cfg_blocks** | 10,439 | Control flow graph blocks |
| **function_returns** | 1,163 | All return statements |

### The Real Golden Standard Checklist

✅ **DO**:
- Query the database first
- Use SQL for pattern matching
- Join tables for complex analysis
- Keep rules under 150 lines
- Return StandardFinding objects

❌ **DON'T**:
- Parse ASTs (ever!)
- Read files from disk
- Traverse trees
- Re-analyze code
- Duplicate indexer work

### Estimated Refactor Scope

- **Current State**: 36 rules, ~20,000 lines of AST traversal code
- **Target State**: 36 rules, ~3,600 lines of SQL queries
- **Code Reduction**: 80-90%
- **Performance Gain**: 10-100x faster
- **Complexity Reduction**: Massive

### Next Steps

1. **STOP** using jwt_detect.py as reference - it's wrong
2. **CREATE** new true_jwt_detect.py using only database queries
3. **REWRITE** all 36 rules to query database
4. **DELETE** all AST traversal code
5. **UPDATE** orchestrator to not pass ASTs at all

---

## Original Database Documentation

This document provides a complete reference of the database schema created by the indexer.
Use this to understand what data is available when writing security rules.

## Quick Reference

### Most Useful Tables for Rules
- **function_call_args**: All function calls with arguments (jwt.sign, bcrypt.hash, etc.)
- **assignments**: All variable assignments (secrets, configs, tokens)
- **symbols**: All code symbols (functions, classes, properties)
- **api_endpoints**: REST API endpoints with methods and paths
- **sql_queries**: All SQL query strings found
- **config_files**: Parsed configuration files

---

## Database Tables

### Table: `api_endpoints`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file | TEXT | Yes | NULL | File path relative to project root |
| method | TEXT | Yes | NULL |  |
| pattern | TEXT | Yes | NULL |  |
| controls | TEXT | No | NULL |  |

**Total Records**: 97

#### Sample Data
```sql
-- Columns: file, method, pattern, controls
-- Sample rows:
-- Row 1: backend/src/app.ts | GET | /health | ["Request"]
-- Row 2: backend/src/app.ts | GET | /health/secrets | ["Request"]
-- Row 3: backend/src/app.ts | GET | /api/csrf-token | ["Request"]
```

### Table: `assignments`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file | TEXT | Yes | NULL | File path relative to project root |
| line | INTEGER | Yes | NULL | Line number in source file |
| target_var | TEXT | Yes | NULL | Variable name |
| source_expr | TEXT | Yes | NULL | Source expression/code |
| source_vars | TEXT | No | NULL | Variable name |
| in_function | TEXT | Yes | NULL |  |

**Total Records**: 2,752

#### Sample Data
```sql
-- Columns: file, line, target_var, source_expr, source_vars, in_function
-- Sample rows:
-- Row 1: backend/src/app.ts | 24 | createApp | (): Application => {
  const app = express();... | ["Application", "app", "express", "Trust", "pro... | createApp
-- Row 2: backend/src/app.ts | 25 | app | express() | ["express"] | createApp
-- Row 3: backend/src/app.ts | 96 | allowedOriginsSet | new Set(
    Array.isArray(config.cors.origin)... | ["Set", "Array", "isArray", "config", "cors", "... | _callback
```

#### Useful Queries
```sql
-- Find secret/key assignments
SELECT * FROM assignments WHERE target_var LIKE '%secret%' OR target_var LIKE '%key%';

-- Find hardcoded values
SELECT * FROM assignments WHERE source_expr LIKE '"%"' OR source_expr LIKE "'%'";
```

### Table: `cfg_block_statements`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| block_id | INTEGER | Yes | NULL |  |
| statement_type | TEXT | Yes | NULL |  |
| line | INTEGER | Yes | NULL | Line number in source file |
| statement_text | TEXT | No | NULL |  |

**Total Records**: 2,542

#### Sample Data
```sql
-- Columns: block_id, statement_type, line, statement_text
-- Sample rows:
-- Row 1: 2 | if | 24 | NULL
-- Row 2: 5 | if | 24 | NULL
-- Row 3: 8 | if | 24 | NULL
```

### Table: `cfg_blocks`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| id (PK) | INTEGER | No | NULL |  |
| file | TEXT | Yes | NULL | File path relative to project root |
| function_name | TEXT | Yes | NULL |  |
| block_type | TEXT | Yes | NULL |  |
| start_line | INTEGER | Yes | NULL |  |
| end_line | INTEGER | Yes | NULL |  |
| condition_expr | TEXT | No | NULL | Source expression/code |

**Total Records**: 10,439

#### Sample Data
```sql
-- Columns: id, file, function_name, block_type, start_line, end_line, condition_expr
-- Sample rows:
-- Row 1: 1 | backend/src/app.ts | createApp | entry | 24 | 24 | NULL
-- Row 2: 2 | backend/src/app.ts | createApp | condition | 24 | 24 | if_condition
-- Row 3: 3 | backend/src/app.ts | createApp | basic | 24 | 24 | NULL
```

### Table: `cfg_edges`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| id (PK) | INTEGER | No | NULL |  |
| file | TEXT | Yes | NULL | File path relative to project root |
| function_name | TEXT | Yes | NULL |  |
| source_block_id | INTEGER | Yes | NULL | Source expression/code |
| target_block_id | INTEGER | Yes | NULL | Variable name |
| edge_type | TEXT | Yes | NULL |  |

**Total Records**: 10,617

#### Sample Data
```sql
-- Columns: id, file, function_name, source_block_id, target_block_id, edge_type
-- Sample rows:
-- Row 1: 1 | backend/src/app.ts | createApp | 1 | 2 | normal
-- Row 2: 2 | backend/src/app.ts | createApp | 2 | 3 | true
-- Row 3: 3 | backend/src/app.ts | createApp | 2 | 4 | false
```

### Table: `compose_services`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file_path (PK) | TEXT | Yes | NULL | File path relative to project root |
| service_name (PK) | TEXT | Yes | NULL |  |
| image | TEXT | No | NULL |  |
| ports | TEXT | No | NULL |  |
| volumes | TEXT | No | NULL |  |
| environment | TEXT | No | NULL |  |
| is_privileged | BOOLEAN | No | 0 |  |
| network_mode | TEXT | No | NULL |  |

**Total Records**: 0

#### Sample Data
```sql
-- No data in this table
```

### Table: `config_files`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| path (PK) | TEXT | No | NULL | File path relative to project root |
| content | TEXT | Yes | NULL |  |
| type | TEXT | Yes | NULL | Symbol/entity type |
| context_dir | TEXT | No | NULL |  |

**Total Records**: 3

#### Sample Data
```sql
-- Columns: path, content, type, context_dir
-- Sample rows:
-- Row 1: backend/tsconfig.json | {
  "compilerOptions": {
    // Language and En... | tsconfig | backend
-- Row 2: frontend/tsconfig.json | {
  "compilerOptions": {
    "target": "ES2020"... | tsconfig | frontend
-- Row 3: tsconfig.json | {
  "files": [],
  "include": [],
  "references... | tsconfig | NULL
```

### Table: `docker_images`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file_path (PK) | TEXT | No | NULL | File path relative to project root |
| base_image | TEXT | No | NULL |  |
| exposed_ports | TEXT | No | NULL |  |
| env_vars | TEXT | No | NULL | Variable name |
| build_args | TEXT | No | NULL | Function argument |
| user | TEXT | No | NULL |  |
| has_healthcheck | BOOLEAN | No | 0 |  |

**Total Records**: 0

#### Sample Data
```sql
-- No data in this table
```

### Table: `docker_issues`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file | TEXT | Yes | NULL | File path relative to project root |
| line | INTEGER | Yes | NULL | Line number in source file |
| issue_type | TEXT | Yes | NULL |  |
| severity | TEXT | Yes | NULL | Issue severity level |

**Total Records**: 0

#### Sample Data
```sql
-- No data in this table
```

### Table: `files`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| path (PK) | TEXT | No | NULL | File path relative to project root |
| sha256 | TEXT | Yes | NULL | File content hash |
| ext | TEXT | Yes | NULL | File extension |
| bytes | INTEGER | Yes | NULL | File size in bytes |
| loc | INTEGER | Yes | NULL | Lines of code |

**Total Records**: 186

#### Sample Data
```sql
-- Columns: path, sha256, ext, bytes, loc
-- Sample rows:
-- Row 1: backend/package.json | 62533aa0bdaabf57ce0fa73f8470d17567a9260ff4582e4... | .json | 3689 | 104
-- Row 2: backend/src/app.ts | 761708a5926bb22db3b8b5c0cc4cd8d857e51481acc3a92... | .ts | 12576 | 378
-- Row 3: backend/src/config/app.ts | 82e25ba3c1abdd9137b30e186fab1f1157145878db469f9... | .ts | 3536 | 131
```

### Table: `function_call_args`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file | TEXT | Yes | NULL | File path relative to project root |
| line | INTEGER | Yes | NULL | Line number in source file |
| caller_function | TEXT | Yes | NULL | Function making the call |
| callee_function | TEXT | Yes | NULL | Function being called |
| argument_index | INTEGER | Yes | NULL | Function argument |
| argument_expr | TEXT | Yes | NULL | Source expression/code |
| param_name | TEXT | Yes | NULL |  |

**Total Records**: 9,679

#### Sample Data
```sql
-- Columns: file, line, caller_function, callee_function, argument_index, argument_expr, param_name
-- Sample rows:
-- Row 1: backend/src/app.ts | 28 | createApp | // Trust proxy - important for rate limiting an... | 0 | 'trust proxy' | arg0
-- Row 2: backend/src/app.ts | 28 | createApp | // Trust proxy - important for rate limiting an... | 1 | 1 | arg1
-- Row 3: backend/src/app.ts | 31 | createApp | // Security middleware - Comprehensive configur... | 0 | helmet({
    // Frame Options - Prevent clickj... | arg0
```

#### Useful Queries
```sql
-- Find JWT sign/verify calls
SELECT * FROM function_call_args WHERE callee_function LIKE '%jwt%';

-- Find bcrypt/crypto calls
SELECT * FROM function_call_args WHERE callee_function LIKE '%crypt%';

-- Find SQL query executions
SELECT * FROM function_call_args WHERE callee_function IN ('query', 'execute', 'run');
```

### Table: `function_returns`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file | TEXT | Yes | NULL | File path relative to project root |
| line | INTEGER | Yes | NULL | Line number in source file |
| function_name | TEXT | Yes | NULL |  |
| return_expr | TEXT | Yes | NULL | Source expression/code |
| return_vars | TEXT | No | NULL | Variable name |

**Total Records**: 1,163

#### Sample Data
```sql
-- Columns: file, line, function_name, return_expr, return_vars
-- Sample rows:
-- Row 1: backend/src/app.ts | 112 | _callback |  | []
-- Row 2: backend/src/app.ts | 162 | _callback |  | []
-- Row 3: backend/src/app.ts | 257 | get_arg1 |  | []
```

### Table: `nginx_configs`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file_path (PK) | TEXT | Yes | NULL | File path relative to project root |
| block_type (PK) | TEXT | Yes | NULL |  |
| block_context (PK) | TEXT | No | NULL |  |
| directives | TEXT | No | NULL |  |
| level | INTEGER | No | 0 |  |

**Total Records**: 0

#### Sample Data
```sql
-- No data in this table
```

### Table: `orm_queries`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file | TEXT | Yes | NULL | File path relative to project root |
| line | INTEGER | Yes | NULL | Line number in source file |
| query_type | TEXT | Yes | NULL |  |
| includes | TEXT | No | NULL |  |
| has_limit | BOOLEAN | No | 0 |  |
| has_transaction | BOOLEAN | No | 0 |  |

**Total Records**: 0

#### Sample Data
```sql
-- No data in this table
```

### Table: `prisma_models`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| model_name (PK) | TEXT | Yes | NULL |  |
| field_name (PK) | TEXT | Yes | NULL |  |
| field_type | TEXT | Yes | NULL |  |
| is_indexed | BOOLEAN | No | 0 |  |
| is_unique | BOOLEAN | No | 0 |  |
| is_relation | BOOLEAN | No | 0 |  |

**Total Records**: 0

#### Sample Data
```sql
-- No data in this table
```

### Table: `refs`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| src | TEXT | Yes | NULL |  |
| kind | TEXT | Yes | NULL |  |
| value | TEXT | Yes | NULL |  |

**Total Records**: 2,063

#### Sample Data
```sql
-- Columns: src, kind, value
-- Sample rows:
-- Row 1: backend/src/app.ts | from | express
-- Row 2: backend/src/app.ts | from | crypto
-- Row 3: backend/src/app.ts | from | cors
```

### Table: `sql_objects`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file | TEXT | Yes | NULL | File path relative to project root |
| kind | TEXT | Yes | NULL |  |
| name | TEXT | Yes | NULL |  |

**Total Records**: 0

#### Sample Data
```sql
-- No data in this table
```

### Table: `sql_queries`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| file_path | TEXT | Yes | NULL | File path relative to project root |
| line_number | INTEGER | Yes | NULL |  |
| query_text | TEXT | Yes | NULL |  |
| command | TEXT | Yes | NULL |  |
| tables | TEXT | No | NULL |  |

**Total Records**: 4,723

#### Sample Data
```sql
-- Columns: file_path, line_number, query_text, command, tables
-- Sample rows:
-- Row 1: backend/src/app.ts | 104 | );
  }
  
  const corsOptions = {
    origin: f... | UNKNOWN | []
-- Row 2: backend/src/app.ts | 104 | );
  }
  
  const corsOptions = {
    origin: f... | UNKNOWN | []
-- Row 3: backend/src/app.ts | 104 | );
  }
  
  const corsOptions = {
    origin: f... | UNKNOWN | []
```

#### Useful Queries
```sql
-- Find queries with string concatenation (SQL injection risk)
SELECT * FROM sql_queries WHERE query_template LIKE '%' || '%';

-- Find SELECT * queries
SELECT * FROM sql_queries WHERE query_template LIKE 'SELECT * %';
```

### Table: `symbols`

#### Schema
| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| path | TEXT | Yes | NULL | File path relative to project root |
| name | TEXT | Yes | NULL |  |
| type | TEXT | Yes | NULL | Symbol/entity type |
| line | INTEGER | Yes | NULL | Line number in source file |
| col | INTEGER | Yes | NULL | Column position in line |

**Total Records**: 84,434

#### Sample Data
```sql
-- Columns: path, name, type, line, col
-- Sample rows:
-- Row 1: backend/src/app.ts | _req | function | 86 | 0
-- Row 2: backend/src/app.ts | __function | function | 86 | 0
-- Row 3: backend/src/app.ts | isArray | function | 96 | 0
```

---

## Common Query Patterns for Rules

### Authentication & JWT
```sql
-- Find all JWT operations
SELECT * FROM function_call_args
WHERE callee_function IN ('jwt.sign', 'jwt.verify', 'jsonwebtoken.sign', 'jsonwebtoken.verify');

-- Find weak secrets
SELECT * FROM assignments
WHERE target_var LIKE '%SECRET%'
  AND LENGTH(source_expr) < 32;
```

### SQL Injection
```sql
-- Find dynamic SQL construction
SELECT * FROM assignments
WHERE target_var LIKE '%query%'
  AND (source_expr LIKE '%+%' OR source_expr LIKE '%${%');
```

### Cryptography
```sql
-- Find weak hashing algorithms
SELECT * FROM function_call_args
WHERE callee_function LIKE '%md5%' OR callee_function LIKE '%sha1%';
```

### API Security
```sql
-- Find unprotected endpoints
SELECT * FROM api_endpoints
WHERE auth_required = 0 OR auth_required IS NULL;
```

---

## Notes for Rule Writers

1. **Always query the database first** - The indexer has already parsed everything
2. **Use indexed data** - Don't re-parse ASTs or files
3. **Join tables when needed** - Combine data from multiple tables
4. **Check for NULL values** - Not all columns are always populated
5. **Use LIKE for patterns** - SQL LIKE operator is powerful for matching

## Security-Specific Query Examples

### JWT/Authentication Issues
```sql
-- Find JWT sign calls without expiration
SELECT f.file, f.line, f.argument_expr
FROM function_call_args f
WHERE f.callee_function IN ('jwt.sign', 'jsonwebtoken.sign')
  AND f.param_name = 'arg2'
  AND f.argument_expr NOT LIKE '%expiresIn%';

-- Find hardcoded JWT secrets
SELECT a.file, a.line, a.target_var, a.source_expr
FROM assignments a
WHERE (a.target_var LIKE '%JWT_SECRET%' OR a.target_var LIKE '%jwtSecret%')
  AND a.source_expr LIKE '"%"';

-- Find algorithm confusion (both HS256 and RS256)
SELECT DISTINCT f1.file
FROM function_call_args f1
JOIN function_call_args f2 ON f1.file = f2.file
WHERE f1.argument_expr LIKE '%HS256%'
  AND f2.argument_expr LIKE '%RS256%';
```

### Password/Secret Management
```sql
-- Find weak password hashing (MD5, SHA1)
SELECT f.file, f.line, f.callee_function
FROM function_call_args f
WHERE f.callee_function LIKE '%md5%' 
   OR f.callee_function LIKE '%sha1%'
   OR f.callee_function LIKE '%createHash%';

-- Find plaintext password storage
SELECT a.file, a.line, a.target_var, a.source_expr
FROM assignments a
WHERE a.target_var LIKE '%password%'
  AND a.source_expr NOT LIKE '%hash%'
  AND a.source_expr NOT LIKE '%encrypt%';
```

### SQL Injection
```sql
-- Find string concatenation in SQL queries
SELECT s.file_path, s.line_number, s.query_template
FROM sql_queries s
WHERE s.is_parameterized = 0
  AND (s.query_template LIKE '%+%' OR s.query_template LIKE '%${%');

-- Find dynamic queries
SELECT f.file, f.line, f.argument_expr
FROM function_call_args f
WHERE f.callee_function IN ('query', 'execute', 'run')
  AND f.argument_expr LIKE '%+%';
```

### XSS/Injection
```sql
-- Find unescaped user input in responses
SELECT f.file, f.line, f.argument_expr
FROM function_call_args f
WHERE f.callee_function IN ('res.send', 'res.write', 'res.json')
  AND f.argument_expr LIKE '%req.body%'
  AND f.argument_expr NOT LIKE '%escape%';

-- Find innerHTML assignments
SELECT a.file, a.line, a.target_var
FROM assignments a
WHERE a.target_var LIKE '%.innerHTML%'
   OR a.target_var LIKE '%dangerouslySetInnerHTML%';
```

### Access Control
```sql
-- Find endpoints without auth checks
SELECT e.file, e.pattern, e.method
FROM api_endpoints e
WHERE e.pattern NOT LIKE '%/public%'
  AND e.pattern NOT LIKE '%/health%'
  AND (e.controls IS NULL OR e.controls NOT LIKE '%auth%');

-- Find admin functions without role checks
SELECT s.path, s.name, s.line
FROM symbols s
WHERE s.type = 'function'
  AND (s.name LIKE '%admin%' OR s.name LIKE '%delete%')
  AND s.path NOT IN (
    SELECT DISTINCT f.file FROM function_call_args f
    WHERE f.callee_function LIKE '%checkRole%'
  );
```

### Sensitive Data Exposure
```sql
-- Find console.log with sensitive data
SELECT f.file, f.line, f.argument_expr
FROM function_call_args f
WHERE f.callee_function = 'console.log'
  AND (f.argument_expr LIKE '%password%'
       OR f.argument_expr LIKE '%secret%'
       OR f.argument_expr LIKE '%token%');

-- Find sensitive data in error messages
SELECT f.file, f.line, f.argument_expr
FROM function_call_args f
WHERE f.callee_function IN ('res.status', 'next')
  AND f.argument_expr LIKE '%stack%';
```

## Example Rule Using Database

```python
def find_jwt_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Find JWT vulnerabilities using indexed data."""
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    findings = []
    
    # Query for JWT sign calls
    cursor.execute("""
        SELECT file, line, argument_expr, param_name
        FROM function_call_args
        WHERE callee_function IN ('jwt.sign', 'jsonwebtoken.sign')
    """)
    
    for row in cursor.fetchall():
        file_path, line, arg_expr, param = row
        
        # Check for weak secret (usually 2nd argument)
        if param == 'arg1' and len(arg_expr) < 32:
            findings.append(StandardFinding(
                rule_name='jwt-weak-secret',
                message=f'Weak JWT secret: {len(arg_expr)} chars',
                file_path=file_path,
                line=line,
                severity=Severity.CRITICAL
            ))
    
    conn.close()
    return findings
```