"""Flask Framework Security Analyzer - Database-First Approach.

Analyzes Flask applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces flask_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


def find_flask_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Flask security vulnerabilities using indexed data.
    
    Detects:
    - Server-Side Template Injection (SSTI)
    - XSS via Markup()
    - Debug mode enabled
    - Hardcoded secret keys
    - Unsafe file uploads
    - SQL injection risks
    - Open redirect vulnerabilities
    - Eval usage with user input
    - CORS wildcard configuration
    - Unsafe deserialization
    - Werkzeug debugger exposure
    
    Returns:
        List of security findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, verify this is a Flask project
        cursor.execute("""
            SELECT DISTINCT file FROM refs
            WHERE value IN ('flask', 'Flask')
        """)
        flask_files = cursor.fetchall()
        
        if not flask_files:
            return findings  # Not a Flask project
        
        # ========================================================
        # CHECK 1: Server-Side Template Injection (SSTI)
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'render_template_string'
            ORDER BY f.file, f.line
        """)
        
        for file, line, template_arg in cursor.fetchall():
            # Check if user input is involved
            if any(src in template_arg for src in ['request.', 'user_input', 'data']):
                severity = Severity.CRITICAL
                confidence = Confidence.HIGH
            else:
                severity = Severity.HIGH
                confidence = Confidence.MEDIUM
            
            findings.append(StandardFinding(
                rule_name='flask-ssti-risk',
                message='Use of render_template_string - Server-Side Template Injection risk',
                file_path=file,
                line=line,
                severity=severity,
                category='injection',
                confidence=confidence,
                snippet=template_arg[:100] if len(template_arg) > 100 else template_arg,
                fix_suggestion='Use render_template() with static template files instead',
                cwe_id='CWE-1336'
            ))
        
        # ========================================================
        # CHECK 2: XSS via Markup()
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'Markup'
            ORDER BY f.file, f.line
        """)
        
        for file, line, markup_content in cursor.fetchall():
            # Check if user input is involved
            if any(src in markup_content for src in ['request.', 'user_', 'input']):
                findings.append(StandardFinding(
                    rule_name='flask-markup-xss',
                    message='Use of Markup() with potential user input - XSS risk',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    confidence=Confidence.HIGH,
                    snippet=markup_content[:100] if len(markup_content) > 100 else markup_content,
                    fix_suggestion='Sanitize user input before using Markup() or use escape()',
                    cwe_id='CWE-79'
                ))
        
        # ========================================================
        # CHECK 3: Debug Mode Enabled
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE '%.run'
              AND f.argument_expr LIKE '%debug%True%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-debug-mode-enabled',
                message='Flask debug mode enabled - exposes interactive debugger',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.HIGH,
                snippet=args[:100] if len(args) > 100 else args,
                fix_suggestion='Set debug=False in production environments',
                cwe_id='CWE-489'
            ))
        
        # ========================================================
        # CHECK 4: Hardcoded Secret Keys
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE '%SECRET_KEY%' 
                   OR a.target_var LIKE '%secret_key%')
              AND a.source_expr LIKE '"%"'
              AND a.source_expr NOT LIKE '%environ%'
              AND a.source_expr NOT LIKE '%getenv%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, var_name, secret_value in cursor.fetchall():
            # Check secret strength
            clean_secret = secret_value.strip('"\'')
            if len(clean_secret) < 32:
                findings.append(StandardFinding(
                    rule_name='flask-weak-secret-key',
                    message=f'Weak/hardcoded SECRET_KEY ({len(clean_secret)} chars) - compromises session security',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=f'{var_name} = {secret_value[:30]}...',
                    fix_suggestion='Use environment variables and generate strong random secrets',
                    cwe_id='CWE-798'
                ))
        
        # ========================================================
        # CHECK 5: Unsafe File Uploads
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f1.file, f1.line
            FROM function_call_args f1
            WHERE f1.callee_function LIKE '%.save'
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.line BETWEEN f1.line - 10 AND f1.line
                    AND f2.argument_expr LIKE '%request.files%'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f3
                  WHERE f3.file = f1.file
                    AND f3.line BETWEEN f1.line - 10 AND f1.line + 10
                    AND (f3.callee_function = 'secure_filename'
                         OR f3.callee_function LIKE '%validate%'
                         OR f3.callee_function LIKE '%allowed%')
              )
            ORDER BY f1.file, f1.line
        """)
        
        for file, line in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-unsafe-file-upload',
                message='File upload without validation - malicious file upload risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.MEDIUM,
                fix_suggestion='Use secure_filename() and validate file extensions',
                cwe_id='CWE-434'
            ))
        
        # ========================================================
        # CHECK 6: SQL Injection Risks
        # ========================================================
        cursor.execute("""
            SELECT q.file_path, q.line_number, q.query_text
            FROM sql_queries q
            WHERE (q.query_text LIKE '%' || '%' || '%'
                   OR q.query_text LIKE '%.format(%'
                   OR q.query_text LIKE '%f"%'
                   OR q.query_text LIKE "%f'%")
              AND EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = q.file_path
                    AND f.argument_expr LIKE '%request.%'
              )
            ORDER BY q.file_path, q.line_number
        """)
        
        for file, line, query in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-sql-injection',
                message='String formatting in SQL query - SQL injection vulnerability',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=query[:100] if len(query) > 100 else query,
                fix_suggestion='Use parameterized queries with ? or :param placeholders',
                cwe_id='CWE-89'
            ))
        
        # ========================================================
        # CHECK 7: Open Redirect Vulnerabilities
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'redirect'
              AND (f.argument_expr LIKE '%request.args.get%'
                   OR f.argument_expr LIKE '%request.values.get%'
                   OR f.argument_expr LIKE '%request.form.get%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, redirect_arg in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-open-redirect',
                message='Unvalidated redirect from user input - open redirect vulnerability',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                snippet=redirect_arg[:100] if len(redirect_arg) > 100 else redirect_arg,
                fix_suggestion='Validate redirect URLs against a whitelist',
                cwe_id='CWE-601'
            ))
        
        # ========================================================
        # CHECK 8: Eval Usage with User Input
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'eval'
              AND f.argument_expr LIKE '%request.%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, eval_arg in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-eval-injection',
                message='Use of eval() with user input - code injection vulnerability',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=eval_arg[:100] if len(eval_arg) > 100 else eval_arg,
                fix_suggestion='Never use eval() with user input - use ast.literal_eval() for safe evaluation',
                cwe_id='CWE-95'
            ))
        
        # ========================================================
        # CHECK 9: CORS Wildcard Configuration
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE '%CORS%' 
                   OR a.target_var LIKE '%Access-Control-Allow-Origin%')
              AND a.source_expr LIKE '%*%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, cors_config in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-cors-wildcard',
                message='CORS with wildcard origin - allows any domain access',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                snippet=cors_config[:100] if len(cors_config) > 100 else cors_config,
                fix_suggestion='Specify explicit allowed origins instead of wildcard',
                cwe_id='CWE-346'
            ))
        
        # Also check for CORS in function calls
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'CORS'
              AND f.argument_expr LIKE '%*%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, cors_arg in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-cors-wildcard',
                message='CORS with wildcard origin - allows any domain access',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                snippet=cors_arg[:100] if len(cors_arg) > 100 else cors_arg,
                fix_suggestion='Specify explicit allowed origins instead of wildcard',
                cwe_id='CWE-346'
            ))
        
        # ========================================================
        # CHECK 10: Unsafe Deserialization (Pickle)
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('pickle.loads', 'loads', 'pickle.load', 'load')
              AND f.argument_expr LIKE '%request.%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, pickle_arg in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-unsafe-pickle',
                message='Pickle deserialization of user input - Remote Code Execution risk',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=pickle_arg[:100] if len(pickle_arg) > 100 else pickle_arg,
                fix_suggestion='Never unpickle untrusted data - use JSON instead',
                cwe_id='CWE-502'
            ))
        
        # ========================================================
        # CHECK 11: Werkzeug Debugger Exposure
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.target_var = 'WERKZEUG_DEBUG_PIN'
               OR a.source_expr LIKE '%use_debugger%True%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, var, value in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-werkzeug-debugger',
                message='Werkzeug debugger exposed - allows arbitrary code execution',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.HIGH,
                snippet=f'{var} = {value[:50]}',
                fix_suggestion='Disable Werkzeug debugger in production',
                cwe_id='CWE-489'
            ))
        
        # ========================================================
        # CHECK 12: Missing CSRF Protection
        # ========================================================
        cursor.execute("""
            SELECT COUNT(*) FROM refs 
            WHERE value IN ('flask_wtf', 'CSRFProtect', 'csrf')
        """)
        has_csrf = cursor.fetchone()[0] > 0
        
        # Check if there are forms or state-changing endpoints
        cursor.execute("""
            SELECT COUNT(*) FROM api_endpoints
            WHERE method IN ('POST', 'PUT', 'DELETE', 'PATCH')
        """)
        has_state_changing = cursor.fetchone()[0] > 0
        
        if has_state_changing and not has_csrf:
            findings.append(StandardFinding(
                rule_name='flask-missing-csrf',
                message='State-changing endpoints without CSRF protection',
                file_path=flask_files[0][0],
                line=1,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.MEDIUM,
                fix_suggestion='Use Flask-WTF for CSRF protection: from flask_wtf.csrf import CSRFProtect',
                cwe_id='CWE-352'
            ))
        
        # ========================================================
        # CHECK 13: Session Cookie Security
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE '%SESSION_COOKIE_SECURE%'
                   OR a.target_var LIKE '%SESSION_COOKIE_HTTPONLY%'
                   OR a.target_var LIKE '%SESSION_COOKIE_SAMESITE%')
              AND a.source_expr = 'False'
            ORDER BY a.file, a.line
        """)
        
        for file, line, config in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='flask-insecure-session',
                message='Insecure session cookie configuration',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='session',
                confidence=Confidence.HIGH,
                snippet=config,
                fix_suggestion='Set SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax"',
                cwe_id='CWE-614'
            ))
    
    finally:
        conn.close()
    
    return findings


def register_taint_patterns(taint_registry):
    """Register Flask-specific taint patterns.
    
    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.
    
    Args:
        taint_registry: TaintRegistry instance
    """
    # Flask response sinks
    FLASK_RESPONSE_SINKS = [
        'render_template', 'render_template_string', 'jsonify',
        'make_response', 'redirect', 'send_file', 'send_from_directory',
        'Markup', 'flash'
    ]
    
    for pattern in FLASK_RESPONSE_SINKS:
        taint_registry.register_sink(pattern, 'response', 'python')
    
    # Flask input sources
    FLASK_INPUT_SOURCES = [
        'request.args', 'request.form', 'request.values', 'request.json',
        'request.data', 'request.files', 'request.cookies', 'request.headers',
        'request.environ', 'request.view_args', 'get_json', 'get_data'
    ]
    
    for pattern in FLASK_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'python')
    
    # Flask-specific dangerous sinks
    FLASK_DANGEROUS_SINKS = [
        'eval', 'exec', 'compile', '__import__',
        'pickle.loads', 'pickle.load'
    ]
    
    for pattern in FLASK_DANGEROUS_SINKS:
        taint_registry.register_sink(pattern, 'code_execution', 'python')