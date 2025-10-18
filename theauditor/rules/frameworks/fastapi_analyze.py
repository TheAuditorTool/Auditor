"""FastAPI Framework Security Analyzer - Database-First Approach.

Analyzes FastAPI applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces fastapi_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# METADATA
# ============================================================================

METADATA = RuleMetadata(
    name="fastapi_security",
    category="frameworks",
    target_extensions=['.py'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'migrations/'],
    requires_jsx_pass=False
)


# ============================================================================
# SECURITY PATTERNS (Golden Standard: Use Frozensets)
# ============================================================================

# Synchronous operations that block event loop
SYNC_OPERATIONS = frozenset([
    'time.sleep', 'requests.get', 'requests.post', 'requests.put',
    'requests.delete', 'urllib.request.urlopen', 'urllib.urlopen',
    'open', 'input', 'subprocess.run', 'subprocess.call'
])

# Database operations indicating direct access
DB_OPERATIONS = frozenset([
    'query', 'execute', 'executemany', 'commit', 'rollback',
    'fetchone', 'fetchall', 'fetchmany'
])

# Debug endpoints that shouldn't be exposed
DEBUG_ENDPOINTS = frozenset([
    '/debug', '/test', '/_debug', '/_test',
    '/health/full', '/metrics/internal', '/admin/debug',
    '/dev', '/_dev', '/testing'
])

# File operation functions
FILE_OPERATIONS = frozenset([
    'open', 'Path', 'os.path.join', 'os.mkdir',
    'shutil.copy', 'shutil.move'
])


def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect FastAPI security vulnerabilities using indexed data.

    Detects (from database):
    - Direct database access without dependency injection
    - Missing CORS middleware
    - Blocking file operations (limited - can't detect async context)
    - Raw SQL in route handlers
    - Background tasks without proper error handling
    - WebSocket endpoints without authentication
    - Debug endpoints exposed
    - Form data injection risks

    Known Limitations (requires AST/type analysis):
    - Cannot detect async functions (not stored in database)
    - Cannot detect unvalidated path parameters (requires type hints)
    - Cannot detect Pydantic validation usage
    - Cannot detect middleware order

    Returns:
        List of security findings
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Verify this is a FastAPI project - use schema-compliant query
        query = build_query('refs', ['src'],
                           where="value IN ('fastapi', 'FastAPI')")
        cursor.execute(query)
        # Deduplicate file paths in Python
        fastapi_files = list(set(cursor.fetchall()))

        if not fastapi_files:
            return findings  # Not a FastAPI project
        
        # ========================================================
        # CHECK 1: Synchronous Operations in Routes (DEGRADED)
        # ========================================================
        # NOTE: Cannot detect if function is async - database doesn't store this metadata
        # Checking for sync operations in ANY route handler as a fallback
        sync_ops_list = ['time.sleep', 'requests.get', 'requests.post', 'requests.put',
                        'requests.delete', 'urllib.request.urlopen', 'urllib.urlopen',
                        'subprocess.run', 'subprocess.call']
        placeholders = ','.join('?' * len(sync_ops_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           where=f"""callee_function IN ({placeholders})
                             AND EXISTS (
                                 SELECT 1 FROM api_endpoints e
                                 WHERE e.file = function_call_args.file
                             )""",
                           order_by="file, line")
        cursor.execute(query, sync_ops_list)
        # Deduplicate in Python
        seen = set()
        results = []
        for row in cursor.fetchall():
            key = (row[0], row[1], row[2])  # (file, line, callee_function)
            if key not in seen:
                seen.add(key)
                results.append(row)

        for file, line, sync_op in results:
            # Extract just the function name
            func_name = sync_op.split('.')[-1] if '.' in sync_op else sync_op
            if func_name in SYNC_OPERATIONS:
                findings.append(StandardFinding(
                    rule_name='fastapi-potential-sync-in-async',
                    message=f'Potentially blocking operation {sync_op} in route handler - may block event loop if in async function',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,  # Reduced severity since we can't confirm async
                    category='performance',
                    confidence=Confidence.LOW,  # Low confidence without async detection
                    cwe_id='CWE-407'
                ))
        
        # ========================================================
        # CHECK 2: Direct Database Access Without Dependency Injection
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           where="""(callee_function LIKE '%.query%'
                                    OR callee_function LIKE '%.execute%'
                                    OR callee_function LIKE 'db.%'
                                    OR callee_function LIKE 'session.%')
                             AND EXISTS (
                                 SELECT 1 FROM api_endpoints e
                                 WHERE e.file = function_call_args.file
                             )
                             AND NOT EXISTS (
                                 SELECT 1 FROM function_call_args f2
                                 WHERE f2.file = function_call_args.file
                                   AND f2.callee_function = 'Depends'
                             )""",
                           order_by="file, line")
        cursor.execute(query)
        # Deduplicate in Python
        db_access_results = list(set(cursor.fetchall()))

        for file, line, db_call in db_access_results:
            findings.append(StandardFinding(
                rule_name='fastapi-no-dependency-injection',
                message=f'Direct database access ({db_call}) without dependency injection',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='architecture',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-1061'
            ))
        
        # ========================================================
        # CHECK 3: Missing CORS Middleware
        # ========================================================
        query = build_query('refs', ['value'],
                           where="value = 'CORSMiddleware'")
        cursor.execute(query)
        has_cors = cursor.fetchone() is not None

        query2 = build_query('function_call_args', ['callee_function'],
                            where="callee_function = 'FastAPI'")
        cursor.execute(query2)
        has_fastapi_app = cursor.fetchone() is not None

        if has_fastapi_app and not has_cors:
            findings.append(StandardFinding(
                rule_name='fastapi-missing-cors',
                message='FastAPI application without CORS middleware configuration',
                file_path=fastapi_files[0][0],
                line=1,
                severity=Severity.MEDIUM,
                category='security',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-346'
            ))
        
        # ========================================================
        # CHECK 4: Blocking File Operations (DEGRADED)
        # ========================================================
        # NOTE: Cannot detect if in async context - checking for file ops without aiofiles
        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           where="""callee_function = 'open'
                             AND EXISTS (
                                 SELECT 1 FROM api_endpoints e
                                 WHERE e.file = function_call_args.file
                             )
                             AND NOT EXISTS (
                                 SELECT 1 FROM refs r
                                 WHERE r.src = function_call_args.file AND r.value = 'aiofiles'
                             )""",
                           order_by="file, line")
        cursor.execute(query)
        # Deduplicate in Python
        file_op_results = list(set(cursor.fetchall()))

        for file, line, _ in file_op_results:
            findings.append(StandardFinding(
                rule_name='fastapi-potential-blocking-file-op',
                message='File I/O without aiofiles in route file - may block if in async route',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,  # Reduced severity
                category='performance',
                confidence=Confidence.LOW,  # Low confidence without async detection
                cwe_id='CWE-407'
            ))
        
        # ========================================================
        # CHECK 5: Raw SQL in Route Handlers
        # ========================================================
        sql_commands = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE']
        placeholders = ','.join('?' * len(sql_commands))

        query = build_query('sql_queries', ['file_path', 'line_number', 'command'],
                           where=f"""command IN ({placeholders})
                             AND EXISTS (
                                 SELECT 1 FROM api_endpoints e
                                 WHERE e.file = sql_queries.file_path
                             )""",
                           order_by="file_path, line_number")
        cursor.execute(query, sql_commands)
        # Deduplicate in Python
        sql_results = list(set(cursor.fetchall()))

        for file, line, sql_command in sql_results:
            findings.append(StandardFinding(
                rule_name='fastapi-raw-sql-in-route',
                message=f'Raw SQL {sql_command} in route handler - use ORM or repository pattern',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='architecture',
                confidence=Confidence.HIGH,
                cwe_id='CWE-89'
            ))
        
        # ========================================================
        # CHECK 6: Background Tasks Without Error Handling
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'caller_function'],
                           where="callee_function = 'BackgroundTasks.add_task' OR callee_function = 'add_task'",
                           order_by="file, line")
        cursor.execute(query)
        # ✅ FIX: Store results before loop to avoid cursor state bug
        background_tasks = cursor.fetchall()

        for file, line, func in background_tasks:
            # Check for error handling nearby
            query2 = build_query('cfg_blocks', ['id'],
                                where="file = ? AND block_type IN ('try', 'except', 'finally') AND start_line BETWEEN ? AND ?")
            cursor.execute(query2, (file, line - 20, line + 20))

            has_error_handling = cursor.fetchone() is not None

            if not has_error_handling:
                findings.append(StandardFinding(
                    rule_name='fastapi-background-task-no-error-handling',
                    message='Background task without exception handling - failures will be silent',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='error-handling',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-248'
                ))
        
        # ========================================================
        # CHECK 7: WebSocket Endpoints Without Authentication
        # ========================================================
        query = build_query('api_endpoints', ['file', 'pattern'],
                           where="pattern LIKE '%websocket%' OR pattern LIKE '%ws%'")
        cursor.execute(query)
        # Deduplicate in Python
        websocket_results = list(set(cursor.fetchall()))
        for file, pattern in websocket_results:
            # Check if authentication functions are called in the same file
            query2 = build_query('function_call_args', ['callee_function'],
                                where="file = ? AND (callee_function LIKE '%auth%' OR callee_function LIKE '%verify%' OR callee_function LIKE '%current_user%' OR callee_function LIKE '%token%')")
            cursor.execute(query2, (file,))

            has_auth = cursor.fetchone() is not None

            if not has_auth:
                findings.append(StandardFinding(
                    rule_name='fastapi-websocket-no-auth',
                    message=f'WebSocket endpoint {pattern} without authentication',
                    file_path=file,
                    line=1,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-306'
                ))
        
        # ========================================================
        # CHECK 8: Exposed Debug Endpoints
        # ========================================================
        # Build SQL IN clause from frozenset
        debug_patterns_list = list(DEBUG_ENDPOINTS)
        placeholders = ','.join('?' * len(debug_patterns_list))

        query = build_query('api_endpoints', ['file', 'pattern', 'method'],
                           where=f"pattern IN ({placeholders})",
                           order_by="file")
        cursor.execute(query, debug_patterns_list)

        for file, pattern, method in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='fastapi-debug-endpoint-exposed',
                message=f'Debug endpoint {pattern} exposed in production',
                file_path=file,
                line=1,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                cwe_id='CWE-489'
            ))
        
        # ========================================================
        # CHECK 9: Form Data Used in File Operations (Path Traversal Risk)
        # ========================================================
        form_funcs = ['Form', 'File', 'UploadFile']
        file_funcs = ['open', 'Path', 'os.path.join']
        form_placeholders = ','.join('?' * len(form_funcs))
        file_placeholders = ','.join('?' * len(file_funcs))

        query = build_query('function_call_args', ['file', 'line'],
                           where=f"""callee_function IN ({form_placeholders})
                             AND EXISTS (
                                 SELECT 1 FROM function_call_args f2
                                 WHERE f2.file = function_call_args.file
                                   AND f2.callee_function IN ({file_placeholders})
                                   AND f2.line > function_call_args.line
                                   AND f2.line < function_call_args.line + 20
                             )""",
                           order_by="file, line")
        cursor.execute(query, form_funcs + file_funcs)
        # Deduplicate in Python
        form_traversal_results = list(set(cursor.fetchall()))

        for file, line in form_traversal_results:
            findings.append(StandardFinding(
                rule_name='fastapi-form-path-traversal',
                message='Form/file data used in file operations - path traversal risk',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-22'
            ))
        
        # ========================================================
        # CHECK 10: Missing Request Timeout Configuration
        # ========================================================
        query = build_query('function_call_args', ['callee_function'],
                           where="callee_function = 'FastAPI' AND argument_expr LIKE '%timeout%'")
        cursor.execute(query)
        has_timeout = cursor.fetchone() is not None

        if has_fastapi_app and not has_timeout:
            query = build_query('refs', ['value'],
                               where="value IN ('slowapi', 'timeout_middleware')")
            cursor.execute(query)
            has_timeout_middleware = cursor.fetchone() is not None
            
            if not has_timeout_middleware:
                findings.append(StandardFinding(
                    rule_name='fastapi-missing-timeout',
                    message='FastAPI application without request timeout configuration',
                    file_path=fastapi_files[0][0],
                    line=1,
                    severity=Severity.MEDIUM,
                    category='availability',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-400'
                ))
        
        # ========================================================
        # CHECK 11: Unhandled Exceptions in Routes
        # ========================================================
        exception_funcs = ['HTTPException', 'exception_handler', 'add_exception_handler']
        exception_placeholders = ','.join('?' * len(exception_funcs))

        query = build_query('api_endpoints', ['file'],
                           where=f"""NOT EXISTS (
                                 SELECT 1 FROM function_call_args f
                                 WHERE f.file = api_endpoints.file
                                   AND f.callee_function IN ({exception_placeholders})
                             )""")
        cursor.execute(query, exception_funcs)
        # Deduplicate and limit in Python
        exception_results = list(set(cursor.fetchall()))[:5]

        for (file,) in exception_results:
            findings.append(StandardFinding(
                rule_name='fastapi-no-exception-handler',
                message='API routes without exception handlers - may leak error details',
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category='error-handling',
                confidence=Confidence.LOW,
                cwe_id='CWE-209'
            ))
    
    finally:
        conn.close()
    
    return findings


def register_taint_patterns(taint_registry):
    """Register FastAPI-specific taint patterns.
    
    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.
    
    Args:
        taint_registry: TaintRegistry instance
    """
    # FastAPI response sinks
    FASTAPI_RESPONSE_SINKS = [
        'JSONResponse', 'HTMLResponse', 'PlainTextResponse',
        'StreamingResponse', 'FileResponse', 'RedirectResponse'
    ]
    
    for pattern in FASTAPI_RESPONSE_SINKS:
        taint_registry.register_sink(pattern, 'response', 'python')
    
    # FastAPI input sources
    FASTAPI_INPUT_SOURCES = [
        'Request', 'Body', 'Query', 'Path', 'Form',
        'File', 'Header', 'Cookie', 'Depends'
    ]
    
    for pattern in FASTAPI_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'python')
    
    # FastAPI-specific SQL sinks
    FASTAPI_SQL_SINKS = [
        'execute', 'executemany', 'execute_async',
        'fetch', 'fetchone', 'fetchall'
    ]
    
    for pattern in FASTAPI_SQL_SINKS:
        taint_registry.register_sink(pattern, 'sql', 'python')