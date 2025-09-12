"""FastAPI Framework Security Analyzer - Database-First Approach.

Analyzes FastAPI applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces fastapi_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


def find_fastapi_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect FastAPI security vulnerabilities using indexed data.
    
    Detects:
    - Synchronous operations in async routes
    - Direct database access without dependency injection
    - Missing CORS middleware
    - Blocking file operations
    - Raw SQL in route handlers
    - Background tasks without error handling
    - WebSocket endpoints without authentication
    - Debug endpoints exposed
    - Form data injection risks
    
    Returns:
        List of security findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, verify this is a FastAPI project
        cursor.execute("""
            SELECT DISTINCT file FROM refs
            WHERE value IN ('fastapi', 'FastAPI')
        """)
        fastapi_files = cursor.fetchall()
        
        if not fastapi_files:
            return findings  # Not a FastAPI project
        
        # ========================================================
        # CHECK 1: Synchronous Operations in Async Routes
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, s.name as function_name
            FROM function_call_args f
            JOIN symbols s ON f.file = s.path 
                AND f.caller_function = s.name
                AND s.type = 'function'
            WHERE f.callee_function IN (
                'time.sleep', 'requests.get', 'requests.post',
                'urllib.request.urlopen', 'input', 'open'
            )
            AND s.name LIKE 'async %'
            ORDER BY f.file, f.line
        """)
        
        for file, line, sync_op, func_name in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='fastapi-sync-in-async',
                message=f'Synchronous operation {sync_op} in async function {func_name} - blocks event loop',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='performance',
                confidence=Confidence.HIGH,
                fix_suggestion=f'Use async alternative: await asyncio.sleep() for time.sleep, httpx for requests, aiofiles for file ops',
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
        # CHECK 4: Blocking File Operations in Async Functions
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            JOIN symbols s ON f.file = s.path 
                AND f.caller_function = s.name
            WHERE f.callee_function = 'open'
              AND s.name LIKE 'async %'
              AND NOT EXISTS (
                  SELECT 1 FROM refs r
                  WHERE r.src = f.file AND r.value = 'aiofiles'
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, _ in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='fastapi-blocking-file-op',
                message='Blocking file I/O (open) in async route - use aiofiles',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='performance',
                confidence=Confidence.HIGH,
                fix_suggestion='Use aiofiles: async with aiofiles.open(...) as f:',
                cwe_id='CWE-407'
            ))
        
        # ========================================================
        # CHECK 5: Raw SQL in Route Handlers
        # ========================================================
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
            # Check if there's error handling nearby
            cursor.execute("""
                SELECT COUNT(*) FROM symbols
                WHERE path = ? 
                  AND line BETWEEN ? AND ?
                  AND name IN ('try', 'except', 'finally')
            """, (file, line - 10, line + 10))
            
            has_error_handling = cursor.fetchone()[0] > 0
            
            if not has_error_handling:
                findings.append(StandardFinding(
                    rule_name='fastapi-background-task-no-error-handling',
                    message='Background task without exception handling - failures will be silent',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='error-handling',
                    confidence=Confidence.MEDIUM,
                    fix_suggestion='Wrap background task code in try/except to handle errors',
                    cwe_id='CWE-248'
                ))
        
        # ========================================================
        # CHECK 7: WebSocket Endpoints Without Authentication
        # ========================================================
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
        cursor.execute("""
            SELECT e.file, e.pattern, e.method
            FROM api_endpoints e
            WHERE e.pattern IN (
                '/debug', '/test', '/_debug', '/_test',
                '/health/full', '/metrics/internal', '/admin/debug'
            )
            ORDER BY e.file
        """)
        
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