"""Express.js-specific XSS Detection.

This module detects XSS vulnerabilities specific to Express.js applications.
Uses database-only approach with framework awareness.
"""


import sqlite3
from typing import List

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA - Phase 3B Addition (2025-10-02)
# ============================================================================
METADATA = RuleMetadata(
    name="express_xss",
    category="xss",
    target_extensions=['.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=['test/', '__tests__/', 'node_modules/', '*.test.js', '*.spec.js', 'frontend/', 'client/'],
    requires_jsx_pass=False,
    execution_scope="database"  # Database-wide query, not per-file iteration
)


# Express-specific safe methods (JSON-encoded)
EXPRESS_SAFE_METHODS = frozenset([
    'res.json', 'res.jsonp', 'res.status().json',
    'response.json', 'response.jsonp', 'response.status().json',
    'res.redirect', 'response.redirect'  # URL-encoded
])

# Express-specific dangerous patterns
EXPRESS_DANGEROUS_PATTERNS = frozenset([
    'res.send', 'res.write', 'res.end',
    'response.send', 'response.write', 'response.end'
])

# Template engines used with Express
EXPRESS_TEMPLATE_ENGINES = frozenset([
    'ejs', 'pug', 'handlebars', 'mustache', 'jade', 'hbs'
])

# User input sources in Express
EXPRESS_INPUT_SOURCES = frozenset([
    'req.body', 'req.query', 'req.params', 'req.cookies',
    'req.headers', 'req.get', 'req.header',
    'req.signedCookies', 'req.fresh', 'req.hostname',
    'req.ip', 'req.ips', 'req.originalUrl', 'req.path',
    'req.protocol', 'req.route', 'req.secure', 'req.subdomains',
    'req.xhr', 'req.accepts', 'req.acceptsCharsets',
    'req.acceptsEncodings', 'req.acceptsLanguages',
    'req.is', 'req.range'
])


# NO FALLBACKS. NO TABLE EXISTENCE CHECKS. SCHEMA CONTRACT GUARANTEES ALL TABLES EXIST.
# If tables are missing, the rule MUST crash to expose indexer bugs.


def find_express_xss(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Express.js-specific XSS vulnerabilities.

    Returns:
        List of Express-specific XSS findings
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)

    try:
        # Only run if Express is detected
        if not _is_express_app(conn):
            return findings

        findings.extend(_check_unsafe_res_send(conn))
        findings.extend(_check_template_rendering(conn))
        findings.extend(_check_middleware_injection(conn))
        findings.extend(_check_cookie_injection(conn))
        findings.extend(_check_header_injection(conn))
        findings.extend(_check_jsonp_callback(conn))

    finally:
        conn.close()

    return findings


def _is_express_app(conn) -> bool:
    """Check if this is an Express.js application.

    Modernization (2025-11-22):
    - Removed LIMIT 1000 symbol scan fallback (non-deterministic, violates ZERO FALLBACK POLICY)
    - Trust the indexer: if frameworks table doesn't list Express, return False immediately
    - This exposes indexer bugs rather than masking them with guesswork
    """
    cursor = conn.cursor()

    # Trust the Schema Contract
    cursor.execute("""
        SELECT 1 FROM frameworks
        WHERE name IN ('express', 'express.js')
          AND language = 'javascript'
        -- REMOVED LIMIT: was hiding bugs
        """)

    return cursor.fetchone() is not None


def _check_unsafe_res_send(conn) -> list[StandardFinding]:
    """Check for res.send() with HTML content containing user input.

    Modernization (2025-11-22):
    - Performance: Push HTML tag and template literal filtering to SQL
    - Memory safe: Stream results with cursor iteration instead of fetchall()
    """
    findings = []
    cursor = conn.cursor()

    # OPTIMIZATION: Filter for HTML content and template literals in SQL
    # Pareto principle: <html, <div, <script cover 80% of cases
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.send', 'response.send')
          AND f.argument_index = 0
          AND f.argument_expr IS NOT NULL
          AND (
              f.argument_expr LIKE '%`%'
              OR f.argument_expr LIKE '%<html%'
              OR f.argument_expr LIKE '%<div%'
              OR f.argument_expr LIKE '%<script%'
              OR f.argument_expr LIKE '%<img%'
              OR f.argument_expr LIKE '%<iframe%'
          )
    """)

    # Memory safe: Iterate cursor directly
    for file, line, func, args in cursor:
        # Already filtered by SQL for HTML-like content
        # Just verify user input now
        has_user_input = any(src in args for src in EXPRESS_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='express-xss-res-send-html',
                message='XSS: res.send() with HTML containing user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                cwe_id='CWE-79'
            ))

    return findings


def _check_template_rendering(conn) -> list[StandardFinding]:
    """Check for unsafe template rendering in Express.

    Modernization (2025-11-22):
    - Fixed N+1: Single self-JOIN instead of loop + query per render call
    - Performance: Push user input filtering to SQL
    - Memory safe: Stream results with cursor iteration
    """
    findings = []
    cursor = conn.cursor()

    # OPTIMIZATION: Self-JOIN to get both template name and locals in one query
    # Eliminates N+1 pattern: fetch locals → query template name for each
    cursor.execute("""
        SELECT f1.file, f1.line, f0.argument_expr as template_name, f1.argument_expr as locals_arg
        FROM function_call_args f1
        JOIN function_call_args f0
          ON f1.file = f0.file
          AND f1.line = f0.line
          AND f0.argument_index = 0
        WHERE f1.callee_function IN ('res.render', 'response.render')
          AND f1.argument_index = 1
          AND f1.argument_expr IS NOT NULL
          AND (
              f1.argument_expr LIKE '%req.body%'
              OR f1.argument_expr LIKE '%req.query%'
              OR f1.argument_expr LIKE '%req.params%'
          )
    """)

    # Memory safe: Iterate cursor directly
    for file, line, template_name, locals_arg in cursor:
        template = template_name or ''

        # Check for unsafe template engine patterns
        if '.ejs' in template and '<%- ' in locals_arg:
            findings.append(StandardFinding(
                rule_name='express-xss-ejs-unescaped',
                message='XSS: EJS template with unescaped user input (<%- syntax)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'res.render("{template}", {{...req.body}})',
                cwe_id='CWE-79'
            ))
        elif '.pug' in template and '!{' in locals_arg:
            findings.append(StandardFinding(
                rule_name='express-xss-pug-unescaped',
                message='XSS: Pug template with unescaped user input (!{} syntax)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'res.render("{template}", {{...req.body}})',
                cwe_id='CWE-79'
            ))
        elif '.hbs' in template and '{{{' in locals_arg:
            findings.append(StandardFinding(
                rule_name='express-xss-handlebars-unescaped',
                message='XSS: Handlebars with triple mustache ({{{}}}) allows XSS',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'res.render("{template}", {{...req.body}})',
                cwe_id='CWE-79'
            ))

    return findings


def _check_middleware_injection(conn) -> list[StandardFinding]:
    """Check for XSS in custom Express middleware."""
    findings = []
    cursor = conn.cursor()

    # Express user input patterns to check
    user_input_patterns = ['req.body', 'req.query', 'req.params']

    # Find middleware that modifies response
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'app.use'
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, middleware in cursor.fetchall():
        # Filter in Python: Check if middleware contains res.write and user input
        has_res_write = 'res.write' in middleware
        has_user_input = any(pattern in middleware for pattern in user_input_patterns)

        if has_res_write and has_user_input:
            findings.append(StandardFinding(
                rule_name='express-xss-middleware',
                message='XSS: Express middleware writing user input to response',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet='app.use((req, res, next) => { res.write(req.body...) })',
                cwe_id='CWE-79'
            ))

    return findings


def _check_cookie_injection(conn) -> list[StandardFinding]:
    """Check for XSS via cookie injection in Express."""
    findings = []
    cursor = conn.cursor()

    # Express user input patterns to check
    user_input_patterns = ['req.body', 'req.query', 'req.params']

    # Check res.cookie with user input
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.cookie', 'response.cookie')
          AND f.argument_index = 1
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, cookie_value in cursor.fetchall():
        # Filter in Python: Check if cookie value contains user input
        # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
        #       Rewrite with JOIN or CTE to eliminate per-row queries
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        has_user_input = any(pattern in cookie_value for pattern in user_input_patterns)

        if not has_user_input:
            continue

        # Check if httpOnly is set
        cursor.execute("""
            SELECT f2.argument_expr
            FROM function_call_args f2
            WHERE f2.file = ? AND f2.line = ?
              AND f2.argument_index = 2
        """, [file, line])

        options_row = cursor.fetchone()
        has_httponly = options_row and 'httpOnly' in (options_row[0] or '')

        if not has_httponly:
            findings.append(StandardFinding(
                rule_name='express-xss-cookie',
                message='XSS: Cookie set with user input without httpOnly flag',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet=f'res.cookie("name", req.body.value)',
                cwe_id='CWE-79'
            ))

    return findings


def _check_header_injection(conn) -> list[StandardFinding]:
    """Check for header injection that could lead to XSS."""
    findings = []
    cursor = conn.cursor()

    # Express user input patterns to check
    user_input_patterns = ['req.body', 'req.query', 'req.params', 'req.headers']

    # Check res.set/setHeader with user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.set', 'res.setHeader',
                                   'response.set', 'response.setHeader')
          AND f.argument_index = 1
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, header_value in cursor.fetchall():
        # Filter in Python: Check if header value contains user input
        # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
        #       Rewrite with JOIN or CTE to eliminate per-row queries
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        has_user_input = any(pattern in header_value for pattern in user_input_patterns)

        if not has_user_input:
            continue

        # Check which header is being set
        cursor.execute("""
            SELECT f2.argument_expr
            FROM function_call_args f2
            WHERE f2.file = ? AND f2.line = ?
              AND f2.argument_index = 0
        """, [file, line])

        header_row = cursor.fetchone()
        if header_row:
            header_name = header_row[0] or ''

            # Some headers can lead to XSS
            dangerous_headers = ['Content-Type', 'X-XSS-Protection', 'Link', 'Refresh']
            if any(h.lower() in header_name.lower() for h in dangerous_headers):
                findings.append(StandardFinding(
                    rule_name='express-header-injection',
                    message=f'Header Injection: {header_name} set with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='injection',
                    snippet=f'{func}("{header_name}", req.body...)',
                    cwe_id='CWE-113'
                ))

    return findings


def _check_jsonp_callback(conn) -> list[StandardFinding]:
    """Check for JSONP callback injection."""
    findings = []
    cursor = conn.cursor()

    # Express user input patterns to check
    user_input_patterns = ['req.query', 'req.params']

    # Check res.jsonp with callback parameter from user
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.jsonp', 'response.jsonp')
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, data in cursor.fetchall():
        # Check if app has custom callback name nearby
        # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
        #       Rewrite with JOIN or CTE to eliminate per-row queries
        cursor.execute("""
            SELECT a.target_var, a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND ABS(a.line - ?) <= 10
              AND a.target_var IS NOT NULL
              AND a.source_expr IS NOT NULL
        """, [file, line])

        # Filter in Python: Check for callback assignments with user input
        for target_var, source_expr in cursor.fetchall():
            has_callback = 'callback' in target_var
            has_user_input = any(pattern in source_expr for pattern in user_input_patterns)

            if has_callback and has_user_input:
                findings.append(StandardFinding(
                    rule_name='express-jsonp-injection',
                    message='JSONP Callback Injection: User controls callback name',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='xss',
                    snippet='res.jsonp(data) with user-controlled callback',
                    cwe_id='CWE-79'
                ))
                break  # Only report once per jsonp call

    return findings


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_express_xss(context)