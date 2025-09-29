"""Express.js-specific XSS Detection.

This module detects XSS vulnerabilities specific to Express.js applications.
Uses database-only approach with framework awareness.
"""

import sqlite3
from typing import List

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


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


def find_express_xss(context: StandardRuleContext) -> List[StandardFinding]:
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
    cursor.execute("""
        SELECT COUNT(*) FROM symbols
        WHERE name LIKE 'express%'
           OR name LIKE 'app.use%'
           OR name LIKE 'app.get%'
           OR name LIKE 'app.post%'
        LIMIT 1
    """)

    return cursor.fetchone()[0] > 0


def _check_unsafe_res_send(conn) -> List[StandardFinding]:
    """Check for res.send() with HTML content containing user input."""
    findings = []
    cursor = conn.cursor()

    # Find res.send with HTML-like content
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.send', 'response.send')
          AND f.argument_index = 0
          AND (f.argument_expr LIKE '%<html%'
               OR f.argument_expr LIKE '%<div%'
               OR f.argument_expr LIKE '%<script%'
               OR f.argument_expr LIKE '%<style%'
               OR f.argument_expr LIKE '%<img%'
               OR f.argument_expr LIKE '%<iframe%'
               OR f.argument_expr LIKE '%`%'  -- Template literals
              )
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check for user input
        has_user_input = any(src in (args or '') for src in EXPRESS_INPUT_SOURCES)

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


def _check_template_rendering(conn) -> List[StandardFinding]:
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


def _check_middleware_injection(conn) -> List[StandardFinding]:
    """Check for XSS in custom Express middleware."""
    findings = []
    cursor = conn.cursor()

    # Find middleware that modifies response
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'app.use'
          AND f.argument_expr LIKE '%res.write%'
          AND (f.argument_expr LIKE '%req.body%'
               OR f.argument_expr LIKE '%req.query%'
               OR f.argument_expr LIKE '%req.params%')
        ORDER BY f.file, f.line
    """)

    for file, line, func, middleware in cursor.fetchall():
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


def _check_cookie_injection(conn) -> List[StandardFinding]:
    """Check for XSS via cookie injection in Express."""
    findings = []
    cursor = conn.cursor()

    # Check res.cookie with user input
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.cookie', 'response.cookie')
          AND f.argument_index = 1  -- Cookie value
          AND (f.argument_expr LIKE '%req.body%'
               OR f.argument_expr LIKE '%req.query%'
               OR f.argument_expr LIKE '%req.params%')
        ORDER BY f.file, f.line
    """)

    for file, line, cookie_value in cursor.fetchall():
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


def _check_header_injection(conn) -> List[StandardFinding]:
    """Check for header injection that could lead to XSS."""
    findings = []
    cursor = conn.cursor()

    # Check res.set/setHeader with user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.set', 'res.setHeader',
                                   'response.set', 'response.setHeader')
          AND f.argument_index = 1  -- Header value
          AND (f.argument_expr LIKE '%req.body%'
               OR f.argument_expr LIKE '%req.query%'
               OR f.argument_expr LIKE '%req.params%'
               OR f.argument_expr LIKE '%req.headers%')
        ORDER BY f.file, f.line
    """)

    for file, line, func, header_value in cursor.fetchall():
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


def _check_jsonp_callback(conn) -> List[StandardFinding]:
    """Check for JSONP callback injection."""
    findings = []
    cursor = conn.cursor()

    # Check res.jsonp with callback parameter from user
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.jsonp', 'response.jsonp')
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, data in cursor.fetchall():
        # Check if app has custom callback name
        cursor.execute("""
            SELECT a.source_expr
            FROM assignments a
            WHERE a.target_var LIKE '%callback%'
              AND (a.source_expr LIKE '%req.query%'
                   OR a.source_expr LIKE '%req.params%')
              AND ABS(a.line - ?) <= 10
              AND a.file = ?
        """, [line, file])

        if cursor.fetchone():
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

    return findings