"""CORS Security Analyzer - Database-Driven Implementation.

Detects CORS misconfigurations using indexed database data.
NO AST TRAVERSAL. Just efficient SQL queries.

This rule follows the TRUE golden standard:
1. Query the database for pre-indexed data
2. Process results with simple logic  
3. Return findings

Detects:
- Wildcard origin with credentials enabled
- Dynamic origin reflection without validation
- Null origin allowed
- Manual OPTIONS handling (pre-flight bypass)
"""

import sqlite3
import json
import re
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_cors_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect CORS misconfigurations using indexed data.
    
    Main entry point that delegates to specific detectors.
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # Run each CORS check
        findings.extend(_find_wildcard_with_credentials(cursor))
        findings.extend(_find_reflected_origin(cursor))
        findings.extend(_find_null_origin(cursor))
        findings.extend(_find_manual_options_handling(cursor))
        findings.extend(_find_permissive_headers(cursor))
        findings.extend(_find_cors_middleware_configs(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# CHECK 1: Wildcard Origin with Credentials
# ============================================================================

def _find_wildcard_with_credentials(cursor) -> List[StandardFinding]:
    """Find CORS configs with wildcard origin and credentials enabled.
    
    This is the most dangerous CORS misconfiguration - allows any website
    to read authenticated user data.
    """
    findings = []
    
    # Look for cors() function calls with problematic config
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%cors%' OR f.callee_function = 'CORS')
          AND f.argument_expr LIKE '%origin%'
          AND (f.argument_expr LIKE '%*%' OR f.argument_expr LIKE '%"*"%' OR f.argument_expr LIKE '%''*''%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        # Check if credentials are also enabled
        if ('credentials' in args.lower() and 'true' in args.lower()) or \
           ('supports_credentials' in args.lower() and 'true' in args.lower()):
            findings.append(StandardFinding(
                rule_name='cors-wildcard-with-credentials',
                message='CORS wildcard origin (*) with credentials enabled - allows any site to read authenticated data',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{func}(origin: "*", credentials: true)',
                fix_suggestion='Use specific origins whitelist instead of wildcard when credentials are enabled',
                cwe_id='CWE-942'  # Overly Permissive Cross-domain Whitelist
            ))
    
    # Check for setHeader calls setting wildcard origin
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('setHeader', 'set', 'header', 'writeHead')
          AND f.argument_expr LIKE '%Access-Control-Allow-Origin%'
          AND f.argument_expr LIKE '%*%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, args in cursor.fetchall():
        # Check if credentials header is set nearby
        cursor.execute("""
            SELECT 1 FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.callee_function IN ('setHeader', 'set', 'header')
              AND f2.argument_expr LIKE '%Access-Control-Allow-Credentials%'
              AND f2.argument_expr LIKE '%true%'
              AND ABS(f2.line - ?) <= 10
            LIMIT 1
        """, [file, line])
        
        if cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='cors-wildcard-with-credentials',
                message='Manual CORS headers with wildcard and credentials',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet='Access-Control-Allow-Origin: *',
                fix_suggestion='Never use wildcard origin with credentials',
                cwe_id='CWE-942'
            ))
    
    return findings


# ============================================================================
# CHECK 2: Reflected Origin Without Validation
# ============================================================================

def _find_reflected_origin(cursor) -> List[StandardFinding]:
    """Find origin header reflection without validation.
    
    Reflecting the Origin header without validation allows attackers
    to make their malicious site an allowed origin.
    """
    findings = []
    
    # Find assignments that copy request origin to response
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%req.headers.origin%'
               OR a.source_expr LIKE '%req.header%origin%'
               OR a.source_expr LIKE '%request.headers.origin%'
               OR a.source_expr LIKE '%request.headers[%origin%]%')
          AND (a.target_var LIKE '%origin%' 
               OR a.target_var LIKE '%Access-Control%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        # Check if there's validation nearby
        cursor.execute("""
            SELECT 1 FROM function_call_args f
            WHERE f.file = ?
              AND f.line >= ? - 10
              AND f.line <= ? + 10
              AND (f.callee_function LIKE '%includes%'
                   OR f.callee_function LIKE '%indexOf%'
                   OR f.callee_function LIKE '%match%'
                   OR f.callee_function LIKE '%test%'
                   OR f.callee_function LIKE '%whitelist%'
                   OR f.callee_function LIKE '%allowedOrigins%')
            LIMIT 1
        """, [file, line, line])
        
        if not cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='cors-reflected-origin',
                message='Origin header reflected without validation - enables targeted CORS bypass',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{var} = {expr}',
                fix_suggestion='Validate origin against a strict whitelist before reflecting',
                cwe_id='CWE-346'  # Origin Validation Error
            ))
    
    # Find setHeader calls that use request origin directly
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('setHeader', 'set', 'header')
          AND f.argument_expr LIKE '%Access-Control-Allow-Origin%'
          AND (f.argument_expr LIKE '%req.headers.origin%'
               OR f.argument_expr LIKE '%req.header%origin%'
               OR f.argument_expr LIKE '%request.headers%origin%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='cors-reflected-origin',
            message='Direct origin reflection in CORS header',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='security',
            snippet='setHeader("Access-Control-Allow-Origin", req.headers.origin)',
            fix_suggestion='Always validate origin before reflecting',
            cwe_id='CWE-346'
        ))
    
    return findings


# ============================================================================
# CHECK 3: Null Origin Allowed
# ============================================================================

def _find_null_origin(cursor) -> List[StandardFinding]:
    """Find CORS configs that allow 'null' origin.
    
    Allowing null origin enables attacks from sandboxed iframes and
    data: URIs.
    """
    findings = []
    
    # Check CORS function calls for null origin
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%cors%' OR f.callee_function = 'CORS')
          AND f.argument_expr LIKE '%null%'
          AND f.argument_expr LIKE '%origin%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='cors-null-origin',
            message='CORS configuration allows "null" origin - enables sandbox iframe attacks',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{func}(...origin: "null"...)',
            fix_suggestion='Never allow "null" origin in production',
            cwe_id='CWE-942'
        ))
    
    # Check for null in origin whitelists
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%origin%' 
               OR a.target_var LIKE '%whitelist%'
               OR a.target_var LIKE '%allowed%')
          AND a.source_expr LIKE '%null%'
          AND a.source_expr LIKE '%[%'
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        if 'null' in expr.lower():
            findings.append(StandardFinding(
                rule_name='cors-null-origin',
                message=f'Origin whitelist includes "null": {var}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=f'{var} = [..., "null", ...]',
                fix_suggestion='Remove "null" from origin whitelist',
                cwe_id='CWE-942'
            ))
    
    return findings


# ============================================================================
# CHECK 4: Manual OPTIONS Handling
# ============================================================================

def _find_manual_options_handling(cursor) -> List[StandardFinding]:
    """Find manual OPTIONS route handling that might bypass CORS middleware.
    
    Manual pre-flight handling can introduce inconsistencies with middleware
    and create security gaps.
    """
    findings = []
    
    # Find OPTIONS route handlers
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%.options%'
               OR f.callee_function LIKE '%OPTIONS%'
               OR f.argument_expr LIKE '%OPTIONS%')
          AND f.callee_function IN ('options', 'route', 'method', 'all', 
                                    'app.options', 'router.options', 
                                    'app.route', 'router.route')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        # Check if CORS headers are being set manually nearby
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line >= ? - 20
              AND f2.line <= ? + 20
              AND f2.callee_function IN ('setHeader', 'set', 'header')
              AND f2.argument_expr LIKE '%Access-Control%'
        """, [file, line, line])
        
        cors_header_count = cursor.fetchone()[0]
        
        if cors_header_count > 0:
            findings.append(StandardFinding(
                rule_name='cors-manual-preflight',
                message='Manual OPTIONS handling detected - may bypass CORS middleware security',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'{func}("OPTIONS", ...)',
                fix_suggestion='Use CORS middleware for all CORS handling instead of manual OPTIONS routes',
                cwe_id='CWE-942'
            ))
    
    return findings


# ============================================================================
# CHECK 5: Overly Permissive Headers
# ============================================================================

def _find_permissive_headers(cursor) -> List[StandardFinding]:
    """Find overly permissive CORS headers."""
    findings = []
    
    # Check for Access-Control-Allow-Headers: *
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('setHeader', 'set', 'header')
          AND f.argument_expr LIKE '%Access-Control-Allow-Headers%'
          AND f.argument_expr LIKE '%*%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='cors-permissive-headers',
            message='Wildcard in Access-Control-Allow-Headers - allows any header',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='security',
            snippet='Access-Control-Allow-Headers: *',
            fix_suggestion='Explicitly list allowed headers instead of using wildcard',
            cwe_id='CWE-942'
        ))
    
    # Check for Access-Control-Allow-Methods: *
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('setHeader', 'set', 'header')
          AND f.argument_expr LIKE '%Access-Control-Allow-Methods%'
          AND f.argument_expr LIKE '%*%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='cors-permissive-methods',
            message='Wildcard in Access-Control-Allow-Methods - allows any HTTP method',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='security',
            snippet='Access-Control-Allow-Methods: *',
            fix_suggestion='Explicitly list allowed methods (GET, POST, etc.)',
            cwe_id='CWE-942'
        ))
    
    return findings


# ============================================================================
# CHECK 6: CORS Middleware Configuration Issues
# ============================================================================

def _find_cors_middleware_configs(cursor) -> List[StandardFinding]:
    """Find problematic CORS middleware configurations."""
    findings = []
    
    # Find CORS middleware initialization
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var LIKE '%cors%'
          AND (a.source_expr LIKE '%{%' OR a.source_expr LIKE '%origin%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, config in cursor.fetchall():
        # Check for problematic patterns in config
        config_lower = config.lower()
        
        # Check for regex patterns that might be too permissive
        if 'regexp' in config_lower or 'regex' in config_lower:
            if '.*' in config or '.+' in config:
                findings.append(StandardFinding(
                    rule_name='cors-weak-regex',
                    message='CORS origin regex may be too permissive',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{var} = {{origin: /.*/ }}',
                    fix_suggestion='Use strict regex patterns for origin validation',
                    cwe_id='CWE-942'
                ))
        
        # Check for dynamic origin without validation
        if 'function' in config_lower and 'origin' in config_lower:
            findings.append(StandardFinding(
                rule_name='cors-dynamic-origin',
                message='Dynamic origin function detected - ensure proper validation',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'{var} = {{origin: function(...)}}',
                fix_suggestion='Ensure origin validation function uses strict whitelist',
                cwe_id='CWE-942'
            ))
    
    # Check Python Flask-CORS configurations
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'CORS'
          AND f.argument_expr LIKE '%resources%'
          AND f.argument_expr LIKE '%/*%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        if 'supports_credentials' in args and 'True' in args:
            findings.append(StandardFinding(
                rule_name='cors-flask-wildcard',
                message='Flask-CORS with wildcard resources and credentials',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet='CORS(app, resources="/*", supports_credentials=True)',
                fix_suggestion='Use specific resource paths with credentials',
                cwe_id='CWE-942'
            ))
    
    return findings