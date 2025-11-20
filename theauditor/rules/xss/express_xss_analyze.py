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
    requires_jsx_pass=False
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
    cursor = conn.cursor()

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
    """Check if this is an Express.js application."""
    cursor = conn.cursor()

    # Check frameworks table
    cursor.execute("""
        SELECT COUNT(*) FROM frameworks
        WHERE name IN ('express', 'express.js')
          AND language = 'javascript'
    """)

    if cursor.fetchone()[0] > 0:
        return True

    # Fallback: Check for Express patterns in code
    express_patterns = ['express', 'app.use', 'app.get', 'app.post']

    cursor.execute("""
        SELECT name FROM symbols
        WHERE name IS NOT NULL
        LIMIT 1000
    """)

    # Filter in Python: Check for Express-like symbol names
    for (name,) in cursor.fetchall():
        if any(name.startswith(pattern) for pattern in express_patterns):
            return True

    return False


def _check_unsafe_res_send(conn) -> list[StandardFinding]:
    """Check for res.send() with HTML content containing user input."""
    findings = []
    cursor = conn.cursor()

    # HTML tag patterns to detect
    html_patterns = ['<html', '<div', '<script', '<style', '<img', '<iframe']

    # Find res.send calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.send', 'response.send')
          AND f.argument_index = 0
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python: Check if argument contains HTML tags or template literals
        has_html = any(tag in args for tag in html_patterns)
        has_template_literal = '`' in args

        if not (has_html or has_template_literal):
            continue

        # Check for user input
        has_user_input = any(src in args for src in EXPRESS_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='express-xss-res-send-html',
                message='XSS: res.send() with HTML containing user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{func}(`<html>...{{{args[:40]}}}...`)',
                cwe_id='CWE-79'
            ))

    return findings


def _check_template_rendering(conn) -> list[StandardFinding]:
    """Check for unsafe template rendering in Express."""
    findings = []
    cursor = conn.cursor()

    # Check res.render with user input in locals
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.render', 'response.render')
          AND f.argument_index = 1  -- The locals object
        ORDER BY f.file, f.line
    """)

    for file, line, locals_arg in cursor.fetchall():
        # Check if locals contains user input directly
        has_user_input = any(src in (locals_arg or '') for src in EXPRESS_INPUT_SOURCES)

        if has_user_input:
            # Check template engine for unescaped output
            cursor.execute("""
                SELECT f2.argument_expr
                FROM function_call_args f2
                WHERE f2.file = ? AND f2.line = ?
                  AND f2.argument_index = 0
            """, [file, line])

            template_row = cursor.fetchone()
            if template_row:
                template = template_row[0] or ''

                # Check for known unsafe patterns
                if '.ejs' in template and '<%- ' in locals_arg:  # EJS unescaped
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
                elif '.pug' in template and '!{' in locals_arg:  # Pug unescaped
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
                elif '.hbs' in template and '{{{' in locals_arg:  # Handlebars unescaped
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