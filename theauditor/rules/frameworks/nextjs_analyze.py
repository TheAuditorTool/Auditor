"""Next.js Framework Security Analyzer - Database-First Approach.

Analyzes Next.js applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""


import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# METADATA (Orchestrator Discovery)
# ============================================================================

METADATA = RuleMetadata(
    name="nextjs_security",
    category="frameworks",
    target_extensions=['.js', '.jsx', '.ts', '.tsx'],
    exclude_patterns=['node_modules/', 'test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)


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

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
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
        # Verify this is a Next.js project (query refs table directly) - use raw SQL for DISTINCT and LIMIT
        cursor.execute("""
            SELECT DISTINCT src FROM refs
            WHERE value IN ('next', 'next/router', 'next/navigation', 'next/server')
            LIMIT 1
        """)
        is_nextjs = cursor.fetchone() is not None

        if not is_nextjs:
            # Check for Next.js specific paths as fallback
            query = build_query('files', ['path'], limit=100)
            cursor.execute(query)

            # Filter in Python
            for (path,) in cursor.fetchall():
                if 'pages/api/' in path or 'app/api/' in path or 'next.config' in path:
                    is_nextjs = True
                    break

        if not is_nextjs:
            return findings  # Not a Next.js project

        # ========================================================
        # CHECK 1: API Route Secret Exposure
        # ========================================================
        # Fetch response function calls, filter in Python
        response_funcs_list = list(RESPONSE_FUNCTIONS)
        placeholders = ','.join('?' * len(response_funcs_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"callee_function IN ({placeholders})",
                           order_by="file, line")
        cursor.execute(query, response_funcs_list)

        for file, line, callee, response_data in cursor.fetchall():
            # Filter for API routes in Python
            if not ('pages/api/' in file or 'app/api/' in file):
                continue

            # Check for process.env usage
            if 'process.env' not in response_data:
                continue

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

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"callee_function IN ({placeholders})",
                           order_by="file, line")
        cursor.execute(query, redirect_funcs_list)

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
        # Find files with SSR functions - use raw SQL for DISTINCT
        ssr_funcs_list = list(SSR_FUNCTIONS)
        placeholders = ','.join('?' * len(ssr_funcs_list))

        cursor.execute(f"""
            SELECT DISTINCT file FROM function_call_args
            WHERE callee_function IN ({placeholders})
               OR caller_function IN ({placeholders})
        """, ssr_funcs_list + ssr_funcs_list)

        ssr_files = {row[0] for row in cursor.fetchall()}

        # Check these files for unsanitized user input
        for file in ssr_files:
            # Fetch all arguments, filter in Python
            query_input = build_query('function_call_args', ['argument_expr'],
                where="file = ?")
            cursor.execute(query_input, (file,))

            has_user_input = False
            for (arg_expr,) in cursor.fetchall():
                if 'req.query' in arg_expr or 'req.body' in arg_expr or 'params' in arg_expr:
                    has_user_input = True
                    break

            if has_user_input:
                # Check for sanitization
                sanitize_list = list(SANITIZATION_FUNCTIONS)
                placeholders_san = ','.join('?' * len(sanitize_list))

                query_sanitize = build_query('function_call_args', ['callee_function'],
                    where=f"file = ? AND callee_function IN ({placeholders_san})",
                    limit=1
                )
                cursor.execute(query_sanitize, [file] + sanitize_list)
                has_sanitization = cursor.fetchone() is not None

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
        # Fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, var_name, value in cursor.fetchall():
            # Filter for NEXT_PUBLIC_ prefix
            if not var_name.startswith('NEXT_PUBLIC_'):
                continue

            # Check for sensitive patterns in Python
            var_name_upper = var_name.upper()
            if not any(pattern in var_name_upper for pattern in SENSITIVE_ENV_PATTERNS):
                continue
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
        # Get API routes with state-changing methods, filter in Python
        query_api = build_query('api_endpoints', ['file', 'method'],
            where="method IN ('POST', 'PUT', 'DELETE', 'PATCH')")
        cursor.execute(query_api)

        # Filter for API routes in Python
        api_routes = []
        seen = set()
        for file, method in cursor.fetchall():
            if 'pages/api/' in file or 'app/api/' in file:
                key = (file, method)
                if key not in seen:
                    seen.add(key)
                    api_routes.append((file, method))

        for file, method in api_routes:
            # Fetch function calls for this file, filter for CSRF in Python
            query_csrf = build_query('function_call_args', ['callee_function', 'argument_expr'],
                where="file = ?")
            cursor.execute(query_csrf, [file])

            has_csrf = False
            for callee, arg_expr in cursor.fetchall():
                callee_lower = callee.lower()
                arg_lower = arg_expr.lower()
                if any(indicator.lower() in callee_lower or indicator.lower() in arg_lower
                       for indicator in CSRF_INDICATORS):
                    has_csrf = True
                    break

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
        # Fetch response function calls, filter in Python
        response_funcs_list = list(RESPONSE_FUNCTIONS)
        placeholders = ','.join('?' * len(response_funcs_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"callee_function IN ({placeholders})",
                           order_by="file, line")
        cursor.execute(query, response_funcs_list)

        for file, line, callee, error_data in cursor.fetchall():
            # Filter for pages/app directories in Python
            if not ('pages/' in file or 'app/' in file):
                continue

            # Check for error details in Python
            if not ('error.stack' in error_data or 'err.stack' in error_data or 'error.message' in error_data):
                continue
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
        # Fetch all function calls, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)

        dangerous_html_calls = []
        for file, line, callee, html_content in cursor.fetchall():
            if callee == 'dangerouslySetInnerHTML' or 'dangerouslySetInnerHTML' in html_content:
                dangerous_html_calls.append((file, line, html_content))

        for file, line, html_content in dangerous_html_calls:
            # Check if sanitization is nearby
            sanitize_list = list(SANITIZATION_FUNCTIONS)
            placeholders = ','.join('?' * len(sanitize_list))

            query_sanitize = build_query('function_call_args', ['callee_function'],
                where=f"""file = ?
                  AND line BETWEEN ? AND ?
                  AND callee_function IN ({placeholders})""",
                limit=1
            )
            cursor.execute(query_sanitize, [file, line - 10, line + 10] + sanitize_list)
            has_sanitization = cursor.fetchone() is not None

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
        # Get distinct API route files, filter in Python
        query_api_files = build_query('api_endpoints', ['file'])
        cursor.execute(query_api_files)

        api_route_files = set()
        for (file,) in cursor.fetchall():
            if 'pages/api/' in file or 'app/api/' in file:
                api_route_files.add(file)

        if len(api_route_files) >= 3:  # Only flag if multiple API routes
            # Check for rate limiting libraries
            rate_limit_list = list(RATE_LIMIT_LIBRARIES)
            placeholders = ','.join('?' * len(rate_limit_list))

            query_rate_limit = build_query('refs', ['value'],
                where=f"value IN ({placeholders})",
                limit=1
            )
            cursor.execute(query_rate_limit, rate_limit_list)
            has_rate_limiting = cursor.fetchone() is not None

            if not has_rate_limiting:
                # Get first API route file
                api_file = list(api_route_files)[0] if api_route_files else None
                if api_file:
                    findings.append(StandardFinding(
                        rule_name='nextjs-missing-rate-limit',
                        message='Multiple API routes without rate limiting - vulnerable to abuse',
                        file_path=api_file,
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