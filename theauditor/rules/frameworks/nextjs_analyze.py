"""Next.js Framework Security Analyzer - Database-First Approach.

Analyzes Next.js applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows golden standard patterns from compose_analyze.py:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
- Proper confidence levels
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# SECURITY PATTERNS (Golden Standard: Use Frozensets)
# ============================================================================

# Response functions that send data to client
RESPONSE_FUNCTIONS = frozenset([
    'res.json', 'res.send', 'NextResponse.json',
    'NextResponse.redirect', 'NextResponse.rewrite'
])

# Redirect functions that could cause open redirect
REDIRECT_FUNCTIONS = frozenset([
    'router.push', 'router.replace', 'redirect',
    'permanentRedirect', 'NextResponse.redirect'
])

# User input sources
USER_INPUT_SOURCES = frozenset([
    'query', 'params', 'searchParams', 'req.query',
    'req.body', 'req.params', 'formData'
])

# Sensitive environment variable patterns
SENSITIVE_ENV_PATTERNS = frozenset([
    'SECRET', 'PRIVATE', 'KEY', 'TOKEN',
    'PASSWORD', 'API_KEY', 'CREDENTIAL', 'AUTH'
])

# SSR/SSG functions
SSR_FUNCTIONS = frozenset([
    'getServerSideProps', 'getStaticProps', 'getInitialProps',
    'generateStaticParams', 'generateMetadata'
])

# Sanitization functions
SANITIZATION_FUNCTIONS = frozenset([
    'escape', 'sanitize', 'validate', 'DOMPurify',
    'escapeHtml', 'sanitizeHtml', 'xss'
])

# Validation libraries
VALIDATION_LIBRARIES = frozenset([
    'zod', 'yup', 'joi', 'validator', 'express-validator',
    'class-validator', 'superstruct'
])

# Rate limiting libraries
RATE_LIMIT_LIBRARIES = frozenset([
    'rate-limiter', 'express-rate-limit', 'next-rate-limit',
    'rate-limiter-flexible', 'slowDown'
])

# CSRF protection indicators
CSRF_INDICATORS = frozenset([
    'csrf', 'CSRF', 'csrfToken', 'X-CSRF-Token',
    'next-csrf', 'csurf'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_nextjs_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Next.js security vulnerabilities using indexed data.

    Detects (from database):
    - API route secret exposure
    - Open redirect vulnerabilities
    - Server-side rendering injection risks
    - NEXT_PUBLIC sensitive data exposure
    - Missing CSRF in API routes
    - Exposed error details in production
    - Dangerous HTML serialization without sanitization
    - Missing rate limiting on API routes

    Known Limitations (requires AST/runtime analysis):
    - Cannot detect "use server" directives (string literals not indexed)
    - Cannot reliably detect Server Actions (Next.js 13+ feature)
    - Cannot detect middleware order or configuration
    - Cannot analyze Next.js config files (next.config.js)

    Args:
        context: Standardized rule context with database path

    Returns:
        List of StandardFinding objects for detected issues
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
            WHERE type='table' AND name IN (
                'refs', 'function_call_args', 'api_endpoints',
                'assignments', 'files', 'symbols'
            )
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Minimum required tables for any analysis
        if 'function_call_args' not in existing_tables:
            return findings  # Can't analyze without function calls

        # Verify this is a Next.js project
        is_nextjs = False

        if 'refs' in existing_tables:
            cursor.execute("""
                SELECT DISTINCT file FROM refs
                WHERE value IN ('next', 'next/router', 'next/navigation', 'next/server')
                LIMIT 1
            """)
            is_nextjs = cursor.fetchone() is not None

        if not is_nextjs and 'files' in existing_tables:
            # Check for Next.js specific paths as fallback
            cursor.execute("""
                SELECT path FROM files
                WHERE path LIKE '%pages/api/%'
                   OR path LIKE '%app/api/%'
                   OR path LIKE '%next.config%'
                LIMIT 1
            """)
            is_nextjs = cursor.fetchone() is not None

        if not is_nextjs:
            return findings  # Not a Next.js project

        # ========================================================
        # CHECK 1: API Route Secret Exposure
        # ========================================================
        # Build SQL for response functions
        response_funcs_list = list(RESPONSE_FUNCTIONS)
        placeholders = ','.join('?' * len(response_funcs_list))

        cursor.execute(f"""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ({placeholders})
              AND f.argument_expr LIKE '%process.env%'
              AND (f.file LIKE '%pages/api/%' OR f.file LIKE '%app/api/%')
            ORDER BY f.file, f.line
        """, response_funcs_list)

        for file, line, response_data in cursor.fetchall():
            # Check if it's exposing non-public env vars
            if response_data and 'NEXT_PUBLIC' not in response_data:
                findings.append(StandardFinding(
                    rule_name='nextjs-api-secret-exposure',
                    message='Server-side environment variables exposed in API route response',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-200'
                ))

        # ========================================================
        # CHECK 2: Open Redirect Vulnerabilities
        # ========================================================
        redirect_funcs_list = list(REDIRECT_FUNCTIONS)
        placeholders = ','.join('?' * len(redirect_funcs_list))

        cursor.execute(f"""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ({placeholders})
            ORDER BY f.file, f.line
        """, redirect_funcs_list)

        for file, line, func, redirect_arg in cursor.fetchall():
            # Check if using user input
            if redirect_arg and any(source in redirect_arg for source in USER_INPUT_SOURCES):
                findings.append(StandardFinding(
                    rule_name='nextjs-open-redirect',
                    message=f'Unvalidated user input in {func} - open redirect vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='security',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-601'
                ))

        # ========================================================
        # CHECK 3: SSR Injection Risks (DEGRADED)
        # ========================================================
        # Note: Complex correlation, reduced confidence
        if 'api_endpoints' in existing_tables:
            # Find files with SSR functions
            ssr_funcs_list = list(SSR_FUNCTIONS)
            placeholders = ','.join('?' * len(ssr_funcs_list))

            cursor.execute(f"""
                SELECT DISTINCT f.file
                FROM function_call_args f
                WHERE f.callee_function IN ({placeholders})
                   OR f.caller_function IN ({placeholders})
            """, ssr_funcs_list + ssr_funcs_list)

            ssr_files = {row[0] for row in cursor.fetchall()}

            # Check these files for unsanitized user input
            for file in ssr_files:
                cursor.execute("""
                    SELECT COUNT(*) FROM function_call_args
                    WHERE file = ?
                      AND (argument_expr LIKE '%req.query%'
                           OR argument_expr LIKE '%req.body%'
                           OR argument_expr LIKE '%params%')
                """, (file,))

                has_user_input = cursor.fetchone()[0] > 0

                if has_user_input:
                    # Check for sanitization
                    sanitize_list = list(SANITIZATION_FUNCTIONS)
                    placeholders = ','.join('?' * len(sanitize_list))

                    cursor.execute(f"""
                        SELECT COUNT(*) FROM function_call_args
                        WHERE file = ?
                          AND callee_function IN ({placeholders})
                    """, [file] + sanitize_list)

                    has_sanitization = cursor.fetchone()[0] > 0

                    if not has_sanitization:
                        findings.append(StandardFinding(
                            rule_name='nextjs-ssr-injection',
                            message='Server-side rendering with potentially unvalidated user input',
                            file_path=file,
                            line=1,
                            severity=Severity.HIGH,
                            category='injection',
                            confidence=Confidence.LOW,  # Low due to correlation complexity
                            cwe_id='CWE-79'
                        ))

        # ========================================================
        # CHECK 4: NEXT_PUBLIC Sensitive Data Exposure
        # ========================================================
        if 'assignments' in existing_tables:
            # Build query for sensitive patterns
            sensitive_patterns = ['%' + pattern + '%' for pattern in SENSITIVE_ENV_PATTERNS]
            conditions = ' OR '.join(['a.target_var LIKE ?' for _ in sensitive_patterns])

            cursor.execute(f"""
                SELECT a.file, a.line, a.target_var, a.source_expr
                FROM assignments a
                WHERE a.target_var LIKE 'NEXT_PUBLIC_%'
                  AND ({conditions})
                ORDER BY a.file, a.line
            """, sensitive_patterns)

            for file, line, var_name, value in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='nextjs-public-env-exposure',
                    message=f'Sensitive data in {var_name} - exposed to client-side code',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-200'
                ))

        # ========================================================
        # CHECK 5: Missing CSRF in API Routes
        # ========================================================
        if 'api_endpoints' in existing_tables:
            cursor.execute("""
                SELECT DISTINCT e.file, e.method
                FROM api_endpoints e
                WHERE (e.file LIKE '%pages/api/%' OR e.file LIKE '%app/api/%')
                  AND e.method IN ('POST', 'PUT', 'DELETE', 'PATCH')
            """)

            for file, method in cursor.fetchall():
                # Check if CSRF protection exists
                csrf_list = list(CSRF_INDICATORS)
                conditions = ' OR '.join(['callee_function LIKE ?' for _ in csrf_list])
                conditions += ' OR ' + ' OR '.join(['argument_expr LIKE ?' for _ in csrf_list])

                params = ['%' + indicator + '%' for indicator in csrf_list] * 2

                cursor.execute(f"""
                    SELECT COUNT(*) FROM function_call_args
                    WHERE file = ?
                      AND ({conditions})
                """, [file] + params)

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
                        cwe_id='CWE-352'
                    ))

        # ========================================================
        # CHECK 6: Exposed Error Details in Production
        # ========================================================
        response_funcs_list = list(RESPONSE_FUNCTIONS)
        placeholders = ','.join('?' * len(response_funcs_list))

        cursor.execute(f"""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ({placeholders})
              AND (f.argument_expr LIKE '%error.stack%'
                   OR f.argument_expr LIKE '%err.stack%'
                   OR f.argument_expr LIKE '%error.message%')
              AND (f.file LIKE '%pages/%' OR f.file LIKE '%app/%')
            ORDER BY f.file, f.line
        """, response_funcs_list)

        for file, line, error_data in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='nextjs-error-details-exposed',
                message='Error stack trace or details exposed to client',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='information-disclosure',
                confidence=Confidence.HIGH,
                cwe_id='CWE-209'
            ))

        # ========================================================
        # CHECK 7: Dangerous HTML Serialization
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
            sanitize_list = list(SANITIZATION_FUNCTIONS)
            placeholders = ','.join('?' * len(sanitize_list))

            cursor.execute(f"""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND line BETWEEN ? AND ?
                  AND callee_function IN ({placeholders})
            """, [file, line - 10, line + 10] + sanitize_list)

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
                    cwe_id='CWE-79'
                ))

        # ========================================================
        # CHECK 8: API Routes Without Rate Limiting (DEGRADED)
        # ========================================================
        # Note: Global check, not per-route - reduced confidence
        if 'api_endpoints' in existing_tables:
            cursor.execute("""
                SELECT COUNT(DISTINCT file) FROM api_endpoints
                WHERE file LIKE '%pages/api/%' OR file LIKE '%app/api/%'
            """)
            api_route_count = cursor.fetchone()[0]

            if api_route_count > 0 and 'refs' in existing_tables:
                # Check for rate limiting libraries
                rate_limit_list = list(RATE_LIMIT_LIBRARIES)
                placeholders = ','.join('?' * len(rate_limit_list))

                cursor.execute(f"""
                    SELECT COUNT(*) FROM refs
                    WHERE value IN ({placeholders})
                """, rate_limit_list)

                has_rate_limiting = cursor.fetchone()[0] > 0

                if not has_rate_limiting and api_route_count >= 3:  # Only flag if multiple API routes
                    cursor.execute("""
                        SELECT file FROM api_endpoints
                        WHERE file LIKE '%pages/api/%' OR file LIKE '%app/api/%'
                        LIMIT 1
                    """)

                    api_file = cursor.fetchone()
                    if api_file:
                        findings.append(StandardFinding(
                            rule_name='nextjs-missing-rate-limit',
                            message='Multiple API routes without rate limiting - vulnerable to abuse',
                            file_path=api_file[0],
                            line=1,
                            severity=Severity.MEDIUM,
                            category='security',
                            confidence=Confidence.LOW,  # Low because it's a broad check
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
    for pattern in RESPONSE_FUNCTIONS | REDIRECT_FUNCTIONS:
        taint_registry.register_sink(pattern, 'nextjs', 'javascript')

    # Next.js input sources
    for pattern in USER_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')

    # Dangerous sinks
    DANGEROUS_SINKS = frozenset([
        'dangerouslySetInnerHTML', 'eval', 'Function',
        'setTimeout', 'setInterval'
    ])

    for pattern in DANGEROUS_SINKS:
        taint_registry.register_sink(pattern, 'code_execution', 'javascript')