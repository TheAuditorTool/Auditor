"""FastAPI Framework Security Analyzer - Database-First Approach.

Analyzes FastAPI applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces fastapi_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


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


def find_fastapi_issues(context: StandardRuleContext) -> List[StandardFinding]:
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
        # Check if required tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('refs', 'function_call_args', 'api_endpoints', 'sql_queries', 'cfg_blocks')
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Minimum required tables
        if 'function_call_args' not in existing_tables:
            return findings  # Can't analyze without function calls

        # Verify this is a FastAPI project
        if 'refs' in existing_tables:
            cursor.execute("""
                SELECT DISTINCT file FROM refs
                WHERE value IN ('fastapi', 'FastAPI')
            """)
            fastapi_files = cursor.fetchall()

            if not fastapi_files:
                return findings  # Not a FastAPI project
        else:
            # Can't verify FastAPI without refs table
            fastapi_files = []
        
        # ========================================================
        # CHECK 1: Synchronous Operations in Routes (DEGRADED)
        # ========================================================
        # NOTE: Cannot detect if function is async - database doesn't store this metadata
        # Checking for sync operations in ANY route handler as a fallback
        if 'api_endpoints' in existing_tables:
            cursor.execute("""
                SELECT DISTINCT f.file, f.line, f.callee_function
                FROM function_call_args f
                JOIN api_endpoints e ON f.file = e.file
                WHERE f.callee_function IN (
                    'time.sleep', 'requests.get', 'requests.post', 'requests.put',
                    'requests.delete', 'urllib.request.urlopen', 'urllib.urlopen',
                    'subprocess.run', 'subprocess.call'
                )
                ORDER BY f.file, f.line
            """)

            for file, line, sync_op in cursor.fetchall():
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
                        fix_suggestion=f'If async route: use await asyncio.sleep() instead of time.sleep, httpx instead of requests, aiofiles for file ops',
                        cwe_id='CWE-407'
                    ))
        
        # ========================================================
        # CHECK 2: Direct Database Access Without Dependency Injection
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f.file, f.line, f.callee_function
            FROM function_call_args f
            JOIN api_endpoints e ON f.file = e.file
            WHERE (f.callee_function LIKE '%.query%' 
                   OR f.callee_function LIKE '%.execute%'
                   OR f.callee_function LIKE 'db.%'
                   OR f.callee_function LIKE 'session.%')
            AND NOT EXISTS (
                SELECT 1 FROM function_call_args f2
                WHERE f2.file = f.file
                  AND f2.callee_function = 'Depends'
            )
            ORDER BY f.file, f.line
        """)
        
        for file, line, db_call in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='fastapi-no-dependency-injection',
                message=f'Direct database access ({db_call}) without dependency injection',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='architecture',
                confidence=Confidence.MEDIUM,
                fix_suggestion='Use FastAPI dependency injection: def get_db() -> Session: ...',
                cwe_id='CWE-1061'
            ))
        
        # ========================================================
        # CHECK 3: Missing CORS Middleware
        # ========================================================
        cursor.execute("""
            SELECT COUNT(*) FROM refs 
            WHERE value = 'CORSMiddleware'
        """)
        has_cors = cursor.fetchone()[0] > 0
        
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE callee_function = 'FastAPI'
        """)
        has_fastapi_app = cursor.fetchone()[0] > 0
        
        if has_fastapi_app and not has_cors:
            findings.append(StandardFinding(
                rule_name='fastapi-missing-cors',
                message='FastAPI application without CORS middleware configuration',
                file_path=fastapi_files[0][0],
                line=1,
                severity=Severity.MEDIUM,
                category='security',
                confidence=Confidence.MEDIUM,
                fix_suggestion='Add CORSMiddleware: from fastapi.middleware.cors import CORSMiddleware',
                cwe_id='CWE-346'
            ))
        
        # ========================================================
        # CHECK 4: Blocking File Operations (DEGRADED)
        # ========================================================
        # NOTE: Cannot detect if in async context - checking for file ops without aiofiles
        if 'api_endpoints' in existing_tables:
            cursor.execute("""
                SELECT DISTINCT f.file, f.line, f.callee_function
                FROM function_call_args f
                JOIN api_endpoints e ON f.file = e.file
                WHERE f.callee_function = 'open'
                  AND NOT EXISTS (
                      SELECT 1 FROM refs r
                      WHERE r.src = f.file AND r.value = 'aiofiles'
                  )
                ORDER BY f.file, f.line
            """)

            for file, line, _ in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='fastapi-potential-blocking-file-op',
                    message='File I/O without aiofiles in route file - may block if in async route',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,  # Reduced severity
                    category='performance',
                    confidence=Confidence.LOW,  # Low confidence without async detection
                    fix_suggestion='If async route: use aiofiles - async with aiofiles.open(...) as f:',
                    cwe_id='CWE-407'
                ))
        
        # ========================================================
        # CHECK 5: Raw SQL in Route Handlers
        # ========================================================
        if 'sql_queries' in existing_tables and 'api_endpoints' in existing_tables:
            cursor.execute("""
                SELECT DISTINCT q.file_path, q.line_number, q.command
                FROM sql_queries q
                JOIN api_endpoints e ON q.file_path = e.file
                WHERE q.command IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE')
                ORDER BY q.file_path, q.line_number
            """)

            for file, line, sql_command in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='fastapi-raw-sql-in-route',
                    message=f'Raw SQL {sql_command} in route handler - use ORM or repository pattern',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='architecture',
                    confidence=Confidence.HIGH,
                    fix_suggestion='Use SQLAlchemy ORM or repository pattern for database operations',
                    cwe_id='CWE-89'
                ))
        
        # ========================================================
        # CHECK 6: Background Tasks Without Error Handling
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.caller_function
            FROM function_call_args f
            WHERE f.callee_function = 'BackgroundTasks.add_task'
               OR f.callee_function = 'add_task'
            ORDER BY f.file, f.line
        """)

        for file, line, func in cursor.fetchall():
            has_error_handling = False

            # Check if cfg_blocks table exists and has error handling nearby
            if 'cfg_blocks' in existing_tables:
                cursor.execute("""
                    SELECT COUNT(*) FROM cfg_blocks
                    WHERE file = ?
                      AND block_type IN ('try', 'except', 'finally')
                      AND start_line BETWEEN ? AND ?
                """, (file, line - 20, line + 20))

                has_error_handling = cursor.fetchone()[0] > 0

            if not has_error_handling:
                findings.append(StandardFinding(
                    rule_name='fastapi-background-task-no-error-handling',
                    message='Background task without exception handling - failures will be silent',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='error-handling',
                    confidence=Confidence.MEDIUM if 'cfg_blocks' in existing_tables else Confidence.LOW,
                    fix_suggestion='Wrap background task code in try/except to handle errors',
                    cwe_id='CWE-248'
                ))
        
        # ========================================================
        # CHECK 7: WebSocket Endpoints Without Authentication
        # ========================================================
        if 'api_endpoints' in existing_tables:
            cursor.execute("""
                SELECT DISTINCT e.file, e.pattern
                FROM api_endpoints e
                WHERE e.pattern LIKE '%websocket%' OR e.pattern LIKE '%ws%'
            """)

            for file, pattern in cursor.fetchall():
                # Check if authentication functions are called in the same file
                cursor.execute("""
                    SELECT COUNT(*) FROM function_call_args
                    WHERE file = ?
                      AND (callee_function LIKE '%auth%'
                           OR callee_function LIKE '%verify%'
                           OR callee_function LIKE '%current_user%'
                           OR callee_function LIKE '%token%')
                """, (file,))

                has_auth = cursor.fetchone()[0] > 0

                if not has_auth:
                    findings.append(StandardFinding(
                        rule_name='fastapi-websocket-no-auth',
                        message=f'WebSocket endpoint {pattern} without authentication',
                        file_path=file,
                        line=1,
                        severity=Severity.CRITICAL,
                        category='security',
                        confidence=Confidence.MEDIUM,
                        fix_suggestion='Add authentication check for WebSocket connections',
                        cwe_id='CWE-306'
                    ))
        
        # ========================================================
        # CHECK 8: Exposed Debug Endpoints
        # ========================================================
        if 'api_endpoints' in existing_tables:
            # Build SQL IN clause from frozenset
            debug_patterns_list = list(DEBUG_ENDPOINTS)
            placeholders = ','.join('?' * len(debug_patterns_list))

            cursor.execute(f"""
                SELECT e.file, e.pattern, e.method
                FROM api_endpoints e
                WHERE e.pattern IN ({placeholders})
                ORDER BY e.file
            """, debug_patterns_list)

            for file, pattern, method in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='fastapi-debug-endpoint-exposed',
                    message=f'Debug endpoint {pattern} exposed in production',
                    file_path=file,
                    line=1,
                    severity=Severity.HIGH,
                    category='security',
                    confidence=Confidence.HIGH,
                    fix_suggestion='Remove debug endpoints or protect with authentication',
                    cwe_id='CWE-489'
                ))
        
        # ========================================================
        # CHECK 9: Form Data Used in File Operations (Path Traversal Risk)
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f1.file, f1.line
            FROM function_call_args f1
            JOIN function_call_args f2 ON f1.file = f2.file
            WHERE f1.callee_function IN ('Form', 'File', 'UploadFile')
              AND f2.callee_function IN ('open', 'Path', 'os.path.join')
              AND f2.line > f1.line
              AND f2.line < f1.line + 20
            ORDER BY f1.file, f1.line
        """)
        
        for file, line in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='fastapi-form-path-traversal',
                message='Form/file data used in file operations - path traversal risk',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.MEDIUM,
                fix_suggestion='Validate and sanitize file paths, use safe_join or pathlib',
                cwe_id='CWE-22'
            ))
        
        # ========================================================
        # CHECK 10: Missing Request Timeout Configuration
        # ========================================================
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE callee_function = 'FastAPI'
              AND argument_expr LIKE '%timeout%'
        """)
        has_timeout = cursor.fetchone()[0] > 0
        
        if has_fastapi_app and not has_timeout:
            cursor.execute("""
                SELECT COUNT(*) FROM refs
                WHERE value IN ('slowapi', 'timeout_middleware')
            """)
            has_timeout_middleware = cursor.fetchone()[0] > 0
            
            if not has_timeout_middleware:
                findings.append(StandardFinding(
                    rule_name='fastapi-missing-timeout',
                    message='FastAPI application without request timeout configuration',
                    file_path=fastapi_files[0][0],
                    line=1,
                    severity=Severity.MEDIUM,
                    category='availability',
                    confidence=Confidence.MEDIUM,
                    fix_suggestion='Add request timeout middleware to prevent slowloris attacks',
                    cwe_id='CWE-400'
                ))
        
        # ========================================================
        # CHECK 11: Unhandled Exceptions in Routes
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT e.file
            FROM api_endpoints e
            WHERE NOT EXISTS (
                SELECT 1 FROM function_call_args f
                WHERE f.file = e.file
                  AND f.callee_function IN (
                      'HTTPException', 'exception_handler', 
                      'add_exception_handler'
                  )
            )
            LIMIT 5
        """)
        
        for (file,) in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='fastapi-no-exception-handler',
                message='API routes without exception handlers - may leak error details',
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category='error-handling',
                confidence=Confidence.LOW,
                fix_suggestion='Add exception handlers: @app.exception_handler(Exception)',
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