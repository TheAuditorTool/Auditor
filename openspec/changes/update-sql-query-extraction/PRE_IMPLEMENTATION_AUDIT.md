# Pre-Implementation Audit: SQL Query Extraction Enhancement
**Date:** 2025-10-25
**Mode:** Truth Courier (deterministic, anchored in code)
**Status:** READY TO IMPLEMENT

---

## TRUTH: Current State

### What EXISTS
1. ✅ `theauditor/indexer/extractors/sql.py` - Handles .sql FILES (not strings in code)
2. ✅ `python.py:378-490` - Python SQL extraction (ast.Constant/ast.Str only)
3. ✅ `javascript.py:842-952` - JavaScript SQL extraction (skips ALL backticks)
4. ✅ `security_extractors.js:line 24` - Comment shows SQL extraction is PLANNED
5. ✅ `database.py:480-510` - Storage method for sql_queries
6. ✅ `sqlparse==0.5.3` - Dependency already in pyproject.toml

### What DOES NOT EXIST
1. ❌ `theauditor/indexer/sql_parsing.py` - Shared SQL parsing helper (NOT CREATED)
2. ❌ `_resolve_sql_literal()` - Python function to handle f-strings/concatenation (NOT IMPLEMENTED)
3. ❌ `extractSQLQueries()` - JavaScript function in security_extractors.js (NOT IMPLEMENTED)
4. ❌ F-string/template literal handling - Both extractors skip these (GAP CONFIRMED)

---

## TRUTH: Extraction Flow

### Python Flow (CURRENT)
```
1. python.py:378 _extract_sql_queries_ast() called
2. python.py:417-427 Walk AST for SQL method calls (execute, query, raw)
3. python.py:437-443 Check if first_arg is ast.Constant or ast.Str
   ❌ IF ast.JoinedStr (f-string): Continue → SKIPPED
   ❌ IF ast.BinOp (concatenation): Continue → SKIPPED
   ❌ IF ast.Call(.format): Continue → SKIPPED
4. python.py:446-488 Parse with sqlparse, extract command/tables
5. indexer/__init__.py:829 Call db_manager.add_sql_query()
6. database.py:502 Batch to sql_queries table
```

### JavaScript Flow (CURRENT)
```
1. javascript.py:661 _extract_sql_from_function_calls() called
2. javascript.py:875-906 Walk function_calls for SQL methods
3. javascript.py:904-906 Skip if starts with backtick OR contains ${
   ❌ IF `SELECT * FROM users`: Continue → SKIPPED (even if no ${})
4. javascript.py:908-950 Parse with sqlparse, extract command/tables
5. indexer/__init__.py:829 Call db_manager.add_sql_query()
6. database.py:502 Batch to sql_queries table
```

**GAP:** Lines 437-443 (Python) and 904-906 (JavaScript) are HARD GATES blocking f-strings/template literals.

---

## TRUTH: Where To Insert Code

### Python Extractor: `theauditor/indexer/extractors/python.py`

**LOCATION 1: Add helper function BEFORE line 378**
```python
# INSERT AT LINE 345 (after _determine_sql_source, before _extract_sql_queries_ast)

def _resolve_sql_literal(self, node: ast.AST) -> Optional[str]:
    """Resolve AST node to static SQL string.

    Handles:
    - ast.Constant / ast.Str: Plain strings
    - ast.JoinedStr: F-strings (if all parts are static)
    - ast.BinOp(Add): String concatenation
    - ast.Call(.format): Format strings

    Returns:
        Static SQL string if resolvable, None if dynamic
    """
    # Plain string literal
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    elif isinstance(node, ast.Str):  # Python 3.7
        return node.s

    # F-string: f"SELECT * FROM {table}"
    elif isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                # Dynamic expression - can't resolve statically
                # BUT: If it's a simple constant, we can resolve
                if isinstance(value.value, ast.Constant):
                    parts.append(str(value.value.value))
                else:
                    # Dynamic variable/expression - return None (can't analyze)
                    return None
            else:
                return None
        return ''.join(parts)

    # String concatenation: "SELECT * " + "FROM users"
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = self._resolve_sql_literal(node.left)
        right = self._resolve_sql_literal(node.right)
        if left is not None and right is not None:
            return left + right
        return None

    # .format() call: "SELECT * FROM {}".format("users")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'format':
            # Get base string
            base = self._resolve_sql_literal(node.func.value)
            if base is None:
                return None

            # Check if all format arguments are constants
            args = []
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    args.append(str(arg.value))
                else:
                    return None  # Dynamic argument

            try:
                return base.format(*args)
            except (IndexError, KeyError):
                return None  # Malformed format string

    return None
```

**LOCATION 2: Modify lines 436-443**
```python
# REPLACE lines 436-443:
            # OLD CODE:
            # first_arg = node.args[0]
            # query_text = None
            #
            # # Extract string literal
            # if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            #     query_text = first_arg.value
            # elif isinstance(first_arg, ast.Str):  # Python 3.7 compatibility
            #     query_text = first_arg.s

# WITH:
            first_arg = node.args[0]

            # Resolve SQL literal (handles plain strings, f-strings, concatenations, .format())
            query_text = self._resolve_sql_literal(first_arg)
```

**LOCATION 3: Add debug logging at line 442**
```python
            if not query_text:
                # DEBUG: Log skipped queries
                if os.environ.get("THEAUDITOR_DEBUG"):
                    node_type = type(first_arg).__name__
                    print(f"[SQL EXTRACT] Skipped dynamic query at {file_path}:{node.lineno} (type: {node_type})")
                continue  # Not a string literal (variable, complex f-string, etc.)
```

---

### JavaScript Extractor: `theauditor/ast_extractors/javascript/security_extractors.js`

**LOCATION 1: Add extractSQLQueries() function AFTER extractValidationFrameworkUsage (after line 361)**
```javascript
/**
 * Extract raw SQL queries from database execution calls.
 * Detects: db.execute, connection.query, pool.raw, etc.
 *
 * PURPOSE: Enable SQL injection detection for raw query strings
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @returns {Array} - SQL query records
 */
function extractSQLQueries(functionCallArgs) {
    const SQL_METHODS = new Set([
        'execute', 'query', 'raw', 'exec', 'run',
        'executeSql', 'executeQuery', 'execSQL', 'select',
        'insert', 'update', 'delete', 'query_raw'
    ]);

    const queries = [];

    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee.includes('.')) continue;

        // Check if method name matches SQL execution pattern
        const methodName = callee.split('.').pop();
        if (!SQL_METHODS.has(methodName)) continue;

        // Only check first argument (SQL query string)
        if (call.argument_index !== 0) continue;

        const argExpr = call.argument_expr || '';
        if (!argExpr) continue;

        // Check if it looks like SQL (contains SQL keywords)
        const upperArg = argExpr.toUpperCase();
        if (!['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER'].some(kw => upperArg.includes(kw))) {
            continue;
        }

        // Resolve query text from argument expression
        const queryText = resolveSQLLiteral(argExpr);
        if (!queryText) {
            // DEBUG: Log skipped queries
            if (process.env.THEAUDITOR_DEBUG === '1') {
                console.error(`[SQL EXTRACT] Skipped dynamic query at line ${call.line} (${argExpr.substring(0, 50)})`);
            }
            continue;
        }

        // Build query record (Python will parse with sqlparse)
        queries.push({
            line: call.line,
            query_text: queryText.substring(0, 1000),  // Truncate long queries
            // NOTE: command and tables will be parsed by Python using sqlparse
            // We just extract the raw text here
        });
    }

    return queries;
}

/**
 * Resolve SQL literal from argument expression string.
 * Handles:
 * - Plain strings: 'SELECT * FROM users'
 * - Template literals WITHOUT interpolation: `SELECT * FROM users`
 * - Template literals WITH interpolation: SKIP (can't analyze)
 *
 * @param {string} argExpr - Argument expression string
 * @returns {string|null} - Resolved SQL text or null if dynamic
 */
function resolveSQLLiteral(argExpr) {
    const trimmed = argExpr.trim();

    // Plain string (single or double quotes)
    if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
        (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
        return trimmed.slice(1, -1);
    }

    // Template literal
    if (trimmed.startsWith('`') && trimmed.endsWith('`')) {
        // Check for interpolation
        if (trimmed.includes('${')) {
            // Dynamic interpolation - can't analyze
            return null;
        }

        // Static template literal - unescape and return
        let unescaped = trimmed.slice(1, -1);  // Remove backticks
        unescaped = unescaped.replace(/\\`/g, '`').replace(/\\\\/g, '\\');
        return unescaped;
    }

    // Complex expression (variable, concatenation, etc.) - can't analyze
    return null;
}
```

**LOCATION 2: Wire into batch_templates.js at lines 269-271 and 584-586**
```javascript
// MODIFY line 269-271 (ES module):
                    const ormQueries = extractORMQueries(functionCallArgs);
                    const apiEndpoints = extractAPIEndpoints(functionCallArgs);
                    const validationUsage = extractValidationFrameworkUsage(functionCallArgs, assignments, imports);
                    // ADD THIS LINE:
                    const sqlQueries = extractSQLQueries(functionCallArgs);

// MODIFY line 584-586 (CommonJS):
                const ormQueries = extractORMQueries(functionCallArgs);
                const apiEndpoints = extractAPIEndpoints(functionCallArgs);
                const validationUsage = extractValidationFrameworkUsage(functionCallArgs, assignments, imports);
                // ADD THIS LINE:
                const sqlQueries = extractSQLQueries(functionCallArgs);
```

**LOCATION 3: Add to extracted_data payload**
```javascript
// SEARCH for lines that build extracted_data object (around line 280 and 595)
// ADD sql_queries to the payload:

                    // ES MODULE (around line 280):
                    const extracted_data = {
                        functions: functions,
                        classes: classes,
                        calls: calls,
                        assignments: assignments,
                        returns: returns,
                        object_literals: objectLiterals,
                        variable_usage: variableUsage,
                        cfg: cfg,
                        class_properties: classProperties,
                        env_var_usage: envVarUsage,
                        orm_relationships: ormRelationships,
                        orm_queries: ormQueries,
                        api_endpoints: apiEndpoints,
                        validation_framework_usage: validationUsage,
                        sql_queries: sqlQueries  // ADD THIS
                    };

                    // COMMONJS (around line 595):
                    const extracted_data = {
                        functions: functions,
                        classes: classes,
                        calls: calls,
                        assignments: assignments,
                        returns: returns,
                        object_literals: objectLiterals,
                        variable_usage: variableUsage,
                        cfg: cfg,
                        class_properties: classProperties,
                        env_var_usage: envVarUsage,
                        orm_relationships: ormRelationships,
                        orm_queries: ormQueries,
                        api_endpoints: apiEndpoints,
                        validation_framework_usage: validationUsage,
                        sql_queries: sqlQueries  // ADD THIS
                    };
```

---

### JavaScript Python Wrapper: `theauditor/indexer/extractors/javascript.py`

**LOCATION: Modify lines 104-130 to map sql_queries**
```python
# FIND this block (around line 104):
                for key in ['assignments', 'returns', 'object_literals', 'variable_usage', 'cfg', 'class_properties', 'env_var_usage', 'orm_relationships']:
                    if key in extracted_data:
                        result[key] = extracted_data[key]

# ADD sql_queries to the mapping:
                for key in ['assignments', 'returns', 'object_literals', 'variable_usage', 'cfg', 'class_properties', 'env_var_usage', 'orm_relationships', 'sql_queries']:
                    if key in extracted_data:
                        result[key] = extracted_data[key]
```

**CRITICAL: Parse command/tables in Python**
JavaScript extracts raw query text. Python must parse it with sqlparse before storage.

**LOCATION: Add parsing AFTER line 130 (before storing sql_queries)**
```python
# INSERT AFTER line 130 (in Phase 5 data mapping):

                # Parse SQL queries extracted by JavaScript
                if 'sql_queries' in extracted_data:
                    parsed_queries = []
                    try:
                        import sqlparse
                        HAS_SQLPARSE = True
                    except ImportError:
                        HAS_SQLPARSE = False
                        result['sql_queries'] = []  # Skip if no sqlparse

                    if HAS_SQLPARSE:
                        for query in extracted_data['sql_queries']:
                            try:
                                parsed = sqlparse.parse(query['query_text'])
                                if not parsed:
                                    continue

                                statement = parsed[0]
                                command = statement.get_type()

                                if not command or command == 'UNKNOWN':
                                    continue

                                # Extract tables (same logic as python.py:458-473)
                                tables = []
                                tokens = list(statement.flatten())
                                for i, token in enumerate(tokens):
                                    if token.ttype is None and token.value.upper() in ['FROM', 'INTO', 'UPDATE', 'TABLE', 'JOIN']:
                                        for j in range(i + 1, len(tokens)):
                                            next_token = tokens[j]
                                            if not next_token.is_whitespace:
                                                if next_token.ttype in [None, sqlparse.tokens.Name]:
                                                    table_name = next_token.value.strip('"\'`')
                                                    if '.' in table_name:
                                                        table_name = table_name.split('.')[-1]
                                                    if table_name and table_name.upper() not in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                                                        tables.append(table_name)
                                                break

                                # Determine extraction source
                                extraction_source = self._determine_sql_source(file_info['path'], 'query')

                                parsed_queries.append({
                                    'line': query['line'],
                                    'query_text': query['query_text'],
                                    'command': command,
                                    'tables': tables,
                                    'extraction_source': extraction_source
                                })
                            except Exception:
                                continue

                        result['sql_queries'] = parsed_queries
```

---

### Optional: Shared SQL Parsing Helper (DRY principle)

**CREATE:** `theauditor/indexer/sql_parsing.py`
```python
"""Shared SQL parsing utilities.

Centralizes sqlparse integration for both Python and JavaScript extractors.
"""

import os
from typing import Dict, List, Optional


def parse_sql_query(query_text: str) -> Optional[Dict[str, any]]:
    """Parse SQL query to extract command and table names.

    Args:
        query_text: Raw SQL query string

    Returns:
        Dict with {command: str, tables: List[str]} or None if unparseable

    Raises:
        RuntimeError: If sqlparse is not installed
    """
    try:
        import sqlparse
    except ImportError:
        raise RuntimeError(
            "sqlparse is required for SQL extraction. Install with: pip install sqlparse"
        )

    try:
        parsed = sqlparse.parse(query_text)
        if not parsed:
            return None

        statement = parsed[0]
        command = statement.get_type()

        # Skip UNKNOWN commands
        if not command or command == 'UNKNOWN':
            return None

        # Extract table names
        tables = []
        tokens = list(statement.flatten())
        for i, token in enumerate(tokens):
            if token.ttype is None and token.value.upper() in ['FROM', 'INTO', 'UPDATE', 'TABLE', 'JOIN']:
                # Look for next non-whitespace token
                for j in range(i + 1, len(tokens)):
                    next_token = tokens[j]
                    if not next_token.is_whitespace:
                        if next_token.ttype in [None, sqlparse.tokens.Name]:
                            table_name = next_token.value.strip('"\'`')
                            if '.' in table_name:
                                table_name = table_name.split('.')[-1]
                            if table_name and table_name.upper() not in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                                tables.append(table_name)
                        break

        return {
            'command': command,
            'tables': tables,
            'normalized': query_text[:1000]  # Truncate for storage
        }

    except Exception as e:
        # Failed to parse
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[SQL PARSE] Failed to parse query: {e}")
        return None
```

**THEN:** Simplify both extractors by importing this helper (optional refactor, not required for gap closure).

---

## TRUTH: Wiring Verification

### Python Extraction Chain
```
1. python.py:378 _extract_sql_queries_ast()
2. python.py:345 (NEW) _resolve_sql_literal() ← HANDLES F-STRINGS
3. python.py:446-488 sqlparse parsing (UNCHANGED)
4. python.py:184 Result returned to indexer
5. indexer/__init__.py:829 add_sql_query() called
6. database.py:502 Batched to sql_queries table
```

### JavaScript Extraction Chain
```
1. batch_templates.js:269 extractSQLQueries() called ← NEW FUNCTION
2. security_extractors.js:362+ extractSQLQueries() ← NEW IMPLEMENTATION
3. security_extractors.js:400+ resolveSQLLiteral() ← HANDLES TEMPLATE LITERALS
4. batch_templates.js:280 Added to extracted_data.sql_queries
5. javascript.py:130+ (NEW) Parse with sqlparse in Python
6. javascript.py:result['sql_queries'] mapped
7. indexer/__init__.py:829 add_sql_query() called
8. database.py:502 Batched to sql_queries table
```

### Database Schema (UNCHANGED)
```sql
-- Already exists in database.py
CREATE TABLE sql_queries (
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    command TEXT NOT NULL,
    extraction_source TEXT NOT NULL,
    PRIMARY KEY (file_path, line_number)
);

CREATE TABLE sql_query_tables (
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    table_name TEXT NOT NULL,
    PRIMARY KEY (file_path, line_number, table_name)
);
```

**NO SCHEMA CHANGES REQUIRED.**

---

## TRUTH: Test Cases

### Python F-String Test
```python
# File: tests/test_sql_extraction_fstrings.py
import ast
from theauditor.indexer.extractors.python import PythonExtractor

def test_fstring_extraction():
    code = '''
def get_user(uid):
    cursor.execute(f"SELECT * FROM users WHERE id = {uid}")
'''
    tree = ast.parse(code)
    extractor = PythonExtractor(root_path='.')
    result = extractor._extract_sql_queries_ast({'tree': tree}, code, 'test.py')

    # Should extract 1 query (was 0 before)
    assert len(result) == 1
    assert result[0]['command'] == 'SELECT'
    assert 'users' in result[0]['tables']
    assert result[0]['query_text'].startswith('SELECT * FROM users')
```

### JavaScript Template Literal Test
```javascript
// File: test_sql_template_literal.js
const db = require('./db');

async function getUser(id) {
    // Static template literal (should be extracted)
    const users = await db.query(`SELECT * FROM users WHERE id = ${id}`);

    // Dynamic template literal (should be skipped)
    const table = 'users';
    const dynamic = await db.query(`SELECT * FROM ${table}`);
}
```

**Expected:**
- First query: EXTRACTED (even though it has `${}`, the PATTERN is static)
- Wait... CORRECTION: First query HAS `${id}` so it SHOULD be skipped (dynamic)
- Second query: SKIPPED (has `${table}`, dynamic)

**CORRECTED Test:**
```javascript
// File: test_sql_template_literal.js
const db = require('./db');

async function getUser() {
    // Static template literal (should be extracted)
    const users = await db.query(`SELECT * FROM users WHERE id = 1`);

    // Dynamic template literal (should be skipped)
    const table = 'users';
    const dynamic = await db.query(`SELECT * FROM ${table}`);
}
```

**Expected:**
- First query: EXTRACTED (no `${}`, static)
- Second query: SKIPPED (has `${table}`, dynamic)

---

## TRUTH: Implementation Checklist

### Phase 1: Python Extractor (30 minutes)
- [ ] 1.1 Add `_resolve_sql_literal()` function at line 345 in `python.py`
- [ ] 1.2 Replace lines 436-443 to call `_resolve_sql_literal()`
- [ ] 1.3 Add debug logging at line 442
- [ ] 1.4 Test with f-string example
- [ ] 1.5 Verify database has new queries

### Phase 2: JavaScript Extractor (30 minutes)
- [ ] 2.1 Add `extractSQLQueries()` function after line 361 in `security_extractors.js`
- [ ] 2.2 Add `resolveSQLLiteral()` helper function
- [ ] 2.3 Wire into `batch_templates.js` lines 269-271 and 584-586
- [ ] 2.4 Add `sql_queries` to extracted_data payload (lines ~280, ~595)
- [ ] 2.5 Test with template literal example

### Phase 3: JavaScript Python Wrapper (20 minutes)
- [ ] 3.1 Add 'sql_queries' to key mapping at line 104 in `javascript.py`
- [ ] 3.2 Add sqlparse parsing after line 130
- [ ] 3.3 Test end-to-end JavaScript → Python → Database

### Phase 4: Verification (20 minutes)
- [ ] 4.1 Run `aud index` on test project with f-strings/template literals
- [ ] 4.2 Query database: `SELECT * FROM sql_queries` - verify new queries exist
- [ ] 4.3 Check command classification (no UNKNOWN)
- [ ] 4.4 Verify table extraction works
- [ ] 4.5 Run taint analysis - verify new queries are detected as sinks

### Phase 5: Optional - Shared Helper (20 minutes, DEFER IF TIME CONSTRAINED)
- [ ] 5.1 Create `sql_parsing.py` with `parse_sql_query()` function
- [ ] 5.2 Refactor `python.py` to use helper
- [ ] 5.3 Refactor `javascript.py` to use helper
- [ ] 5.4 Remove duplicate sqlparse logic

---

## TRUTH: Estimated Time

**Phase 1-4 (Required):** 100 minutes = **1 hour 40 minutes**
**Phase 5 (Optional DRY):** 20 minutes

**Total:** **2 hours max** (human time) = **~20 minutes AI time**

---

## TRUTH: Risk Assessment

### LOW RISK
- ✅ No schema changes required
- ✅ No breaking changes to existing extraction
- ✅ Pure addition (if new functions fail, old code still works)
- ✅ Database storage unchanged

### MEDIUM RISK
- ⚠️ F-string resolution complexity (edge cases: nested f-strings, mixed expressions)
- ⚠️ JavaScript payload size increase (sql_queries added to extracted_data)

### MITIGATION
- F-string: Return None for complex cases (safe fallback = skip, not crash)
- Payload: Truncate query_text to 1000 chars (already done in existing code)

---

## TRUTH: Definition of Done

1. ✅ Python extractor captures f-strings in test case
2. ✅ JavaScript extractor captures template literals (no `${}`) in test case
3. ✅ Database shows new queries with correct command/tables
4. ✅ No UNKNOWN commands introduced
5. ✅ Debug logging works (THEAUDITOR_DEBUG=1)
6. ✅ Existing tests pass (no regression)
7. ✅ Taint analyzer sees new queries as sinks

---

## READY TO IMPLEMENT

All locations identified. All code written. All integration points mapped. All tests defined.

**START WITH:** Phase 1 (Python extractor) - 30 minutes.
