"""Next.js Framework Security Analyzer - Database-First Approach.

Analyzes Next.js applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces nextjs_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


def find_nextjs_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Next.js security vulnerabilities using indexed data.
    
    Detects:
    - API route secret exposure
    - Open redirect vulnerabilities
    - Server-side rendering injection
    - NEXT_PUBLIC sensitive data exposure
    - Missing CSRF in API routes
    - Server Actions without validation
    - Exposed error details in production
    - Insecure cookies configuration
    
    Returns:
        List of security findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, verify this is a Next.js project
        cursor.execute("""
            SELECT DISTINCT file FROM refs
            WHERE value IN ('next', 'next/router', 'next/navigation', 'next/server')
        """)
        nextjs_files = cursor.fetchall()
        
        if not nextjs_files:
            # Also check for Next.js specific patterns in file paths
            cursor.execute("""
                SELECT DISTINCT path FROM files
                WHERE path LIKE '%pages/api/%'
                   OR path LIKE '%app/api/%'
                   OR path LIKE '%next.config%'
                LIMIT 1
            """)
            nextjs_files = cursor.fetchall()
            
            if not nextjs_files:
                return findings  # Not a Next.js project
        
        # ========================================================
        # CHECK 1: API Route Secret Exposure
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function IN ('res.json', 'res.send', 'NextResponse.json')
                   AND f.argument_expr LIKE '%process.env%')
               AND (f.file LIKE '%pages/api/%' OR f.file LIKE '%app/api/%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, response_data in cursor.fetchall():
            # Check if it's exposing non-public env vars
            if 'NEXT_PUBLIC' not in response_data:
                findings.append(StandardFinding(
                    rule_name='nextjs-api-secret-exposure',
                    message='Server-side environment variables exposed in API route response',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=response_data[:100] if len(response_data) > 100 else response_data,
                    fix_suggestion='Never expose process.env directly in API responses',
                    cwe_id='CWE-200'
                ))
        
        # ========================================================
        # CHECK 2: Open Redirect Vulnerabilities
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('router.push', 'router.replace', 'redirect')
              AND (f.argument_expr LIKE '%query%'
                   OR f.argument_expr LIKE '%params%'
                   OR f.argument_expr LIKE '%searchParams%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, redirect_arg in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='nextjs-open-redirect',
                message='Unvalidated user input in redirect - open redirect vulnerability',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                confidence=Confidence.HIGH,
                snippet=redirect_arg[:100] if len(redirect_arg) > 100 else redirect_arg,
                fix_suggestion='Validate redirect URLs against a whitelist',
                cwe_id='CWE-601'
            ))
        
        # ========================================================
        # CHECK 3: SSR Injection Risks
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('getServerSideProps', 'getStaticProps', 'getInitialProps')
               OR f.caller_function IN ('getServerSideProps', 'getStaticProps', 'getInitialProps')
            ORDER BY f.file, f.line
        """)
        
        ssr_files = set()
        for file, line, func, args in cursor.fetchall():
            ssr_files.add(file)
        
        # Check if these SSR files have user input without sanitization
        for file in ssr_files:
            cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND (argument_expr LIKE '%req.query%' 
                       OR argument_expr LIKE '%req.body%'
                       OR argument_expr LIKE '%params%')
                  AND callee_function NOT IN ('escape', 'sanitize', 'validate')
            """, (file,))
            
            has_unsanitized_input = cursor.fetchone()[0] > 0
            
            if has_unsanitized_input:
                findings.append(StandardFinding(
                    rule_name='nextjs-ssr-injection',
                    message='Server-side rendering with unvalidated user input',
                    file_path=file,
                    line=1,
                    severity=Severity.HIGH,
                    category='injection',
                    confidence=Confidence.MEDIUM,
                    fix_suggestion='Sanitize user input before using in SSR functions',
                    cwe_id='CWE-79'
                ))
        
        # ========================================================
        # CHECK 4: NEXT_PUBLIC Sensitive Data Exposure
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.target_var LIKE 'NEXT_PUBLIC_%'
              AND (a.target_var LIKE '%SECRET%'
                   OR a.target_var LIKE '%PRIVATE%'
                   OR a.target_var LIKE '%KEY%'
                   OR a.target_var LIKE '%TOKEN%'
                   OR a.target_var LIKE '%PASSWORD%'
                   OR a.target_var LIKE '%API_KEY%')
            ORDER BY a.file, a.line
        """)
        
        for file, line, var_name, value in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='nextjs-public-env-exposure',
                message=f'Sensitive data in {var_name} - exposed to client-side code',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.HIGH,
                snippet=f'{var_name} = {value[:50]}...' if len(value) > 50 else f'{var_name} = {value}',
                fix_suggestion='Remove NEXT_PUBLIC_ prefix for sensitive variables',
                cwe_id='CWE-200'
            ))
        
        # ========================================================
        # CHECK 5: Missing CSRF in API Routes
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT e.file, e.method
            FROM api_endpoints e
            WHERE (e.file LIKE '%pages/api/%' OR e.file LIKE '%app/api/%')
              AND e.method IN ('POST', 'PUT', 'DELETE', 'PATCH')
        """)
        
        for file, method in cursor.fetchall():
            # Check if CSRF protection exists
            cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND (callee_function LIKE '%csrf%' 
                       OR callee_function LIKE '%CSRF%'
                       OR argument_expr LIKE '%csrf%')
            """, (file,))
            
            has_csrf = cursor.fetchone()[0] > 0
            
            if not has_csrf:
                findings.append(StandardFinding(
                    rule_name='nextjs-api-csrf-missing',
                    message=f'API route handling {method} without CSRF protection',
                    file_path=file,
                    line=1,
                    severity=Severity.HIGH,
                    category='csrf',
                    confidence=Confidence.MEDIUM,
                    fix_suggestion='Implement CSRF protection using tokens or double-submit cookies',
                    cwe_id='CWE-352'
                ))
        
        # ========================================================
        # CHECK 6: Server Actions Without Validation (Next.js 13+)
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f.file, f.line
            FROM function_call_args f
            WHERE f.file LIKE '%app/%'
              AND (f.callee_function = 'formData.get'
                   OR f.callee_function = 'searchParams.get')
        """)
        
        for file, line in cursor.fetchall():
            # Check if validation libraries are used
            cursor.execute("""
                SELECT COUNT(*) FROM refs
                WHERE src = ?
                  AND value IN ('zod', 'yup', 'joi', 'validator')
            """, (file,))
            
            has_validation = cursor.fetchone()[0] > 0
            
            if not has_validation:
                # Check for "use server" directive (indicates Server Action)
                cursor.execute("""
                    SELECT COUNT(*) FROM symbols
                    WHERE path = ?
                      AND name LIKE '%use server%'
                """, (file,))
                
                is_server_action = cursor.fetchone()[0] > 0
                
                if is_server_action:
                    findings.append(StandardFinding(
                        rule_name='nextjs-server-action-no-validation',
                        message='Server Action without input validation - injection risk',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='validation',
                        confidence=Confidence.MEDIUM,
                        fix_suggestion='Use zod, yup, or joi to validate Server Action inputs',
                        cwe_id='CWE-20'
                    ))
        
        # ========================================================
        # CHECK 7: Exposed Error Details in Production
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function IN ('res.json', 'res.send', 'NextResponse.json')
                   AND (f.argument_expr LIKE '%error.stack%'
                        OR f.argument_expr LIKE '%err.stack%'
                        OR f.argument_expr LIKE '%error.message%'))
               AND (f.file LIKE '%pages/%' OR f.file LIKE '%app/%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, error_data in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='nextjs-error-details-exposed',
                message='Error stack trace or details exposed to client',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='information-disclosure',
                confidence=Confidence.HIGH,
                snippet=error_data[:100] if len(error_data) > 100 else error_data,
                fix_suggestion='Log errors server-side, return generic error messages to client',
                cwe_id='CWE-209'
            ))
        
        # ========================================================
        # CHECK 8: Insecure Cookie Configuration
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('res.setHeader', 'cookies.set')
              AND f.argument_expr LIKE '%Set-Cookie%'
              AND (f.argument_expr NOT LIKE '%Secure%'
                   OR f.argument_expr NOT LIKE '%HttpOnly%'
                   OR f.argument_expr NOT LIKE '%SameSite%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, cookie_config in cursor.fetchall():
            issues = []
            if 'Secure' not in cookie_config:
                issues.append('missing Secure flag')
            if 'HttpOnly' not in cookie_config:
                issues.append('missing HttpOnly flag')
            if 'SameSite' not in cookie_config:
                issues.append('missing SameSite attribute')
            
            if issues:
                findings.append(StandardFinding(
                    rule_name='nextjs-insecure-cookie',
                    message=f'Insecure cookie configuration: {", ".join(issues)}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='session',
                    confidence=Confidence.HIGH,
                    snippet=cookie_config[:100] if len(cookie_config) > 100 else cookie_config,
                    fix_suggestion='Set Secure, HttpOnly, and SameSite=Strict for cookies',
                    cwe_id='CWE-614'
                ))
        
        # ========================================================
        # CHECK 9: Dangerous HTML Serialization
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'dangerouslySetInnerHTML'
               OR f.argument_expr LIKE '%dangerouslySetInnerHTML%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, html_content in cursor.fetchall():
            # Check if sanitization is nearby
            cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND line BETWEEN ? AND ?
                  AND (callee_function LIKE '%sanitize%'
                       OR callee_function LIKE '%DOMPurify%'
                       OR callee_function LIKE '%escape%')
            """, (file, line - 10, line + 10))
            
            has_sanitization = cursor.fetchone()[0] > 0
            
            if not has_sanitization:
                findings.append(StandardFinding(
                    rule_name='nextjs-dangerous-html',
                    message='Use of dangerouslySetInnerHTML without sanitization - XSS risk',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    confidence=Confidence.HIGH,
                    snippet=html_content[:100] if len(html_content) > 100 else html_content,
                    fix_suggestion='Sanitize HTML with DOMPurify before using dangerouslySetInnerHTML',
                    cwe_id='CWE-79'
                ))
        
        # ========================================================
        # CHECK 10: API Routes Without Rate Limiting
        # ========================================================
        cursor.execute("""
            SELECT COUNT(*) FROM api_endpoints
            WHERE file LIKE '%pages/api/%' OR file LIKE '%app/api/%'
        """)
        has_api_routes = cursor.fetchone()[0] > 0
        
        if has_api_routes:
            cursor.execute("""
                SELECT COUNT(*) FROM refs
                WHERE value IN ('rate-limiter', 'express-rate-limit', 'next-rate-limit')
            """)
            has_rate_limiting = cursor.fetchone()[0] > 0
            
            if not has_rate_limiting:
                cursor.execute("""
                    SELECT DISTINCT file FROM api_endpoints
                    WHERE file LIKE '%pages/api/%' OR file LIKE '%app/api/%'
                    LIMIT 1
                """)
                api_file = cursor.fetchone()
                
                if api_file:
                    findings.append(StandardFinding(
                        rule_name='nextjs-missing-rate-limit',
                        message='API routes without rate limiting - vulnerable to abuse',
                        file_path=api_file[0],
                        line=1,
                        severity=Severity.MEDIUM,
                        category='security',
                        confidence=Confidence.MEDIUM,
                        fix_suggestion='Implement rate limiting using next-rate-limit or similar',
                        cwe_id='CWE-307'
                    ))
    
    finally:
        conn.close()
    
    return findings


def register_taint_patterns(taint_registry):
    """Register Next.js-specific taint patterns.
    
    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.
    
    Args:
        taint_registry: TaintRegistry instance
    """
    # Next.js response sinks
    NEXTJS_RESPONSE_SINKS = [
        'NextResponse.json', 'NextResponse.redirect', 'res.json', 'res.send',
        'router.push', 'router.replace', 'redirect', 'revalidatePath', 'revalidateTag'
    ]
    
    for pattern in NEXTJS_RESPONSE_SINKS:
        taint_registry.register_sink(pattern, 'nextjs', 'javascript')
    
    # Next.js input sources
    NEXTJS_INPUT_SOURCES = [
        'req.query', 'req.body', 'searchParams', 'params',
        'cookies', 'headers', 'formData'
    ]
    
    for pattern in NEXTJS_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')
    
    # Next.js-specific dangerous sinks
    NEXTJS_DANGEROUS_SINKS = [
        'dangerouslySetInnerHTML', 'eval', 'Function', 'setTimeout', 'setInterval'
    ]
    
    for pattern in NEXTJS_DANGEROUS_SINKS:
        taint_registry.register_sink(pattern, 'code_execution', 'javascript')