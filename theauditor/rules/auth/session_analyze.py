"""Session Management Security Analyzer - Database-First Approach.

Detects session and cookie security vulnerabilities using database-driven approach.
Follows gold standard patterns from jwt_analyze.py.

NO AST TRAVERSAL. NO FILE I/O. PURE DATABASE QUERIES.

Detects:
- Missing httpOnly flag on session cookies (XSS can steal sessions)
- Missing secure flag on cookies (MITM attacks)
- Missing SameSite attribute (CSRF attacks)
- Session fixation vulnerabilities
- Missing session timeout/expiration

CWE Coverage:
- CWE-1004: Sensitive Cookie Without 'HttpOnly' Flag
- CWE-614: Sensitive Cookie in HTTPS Session Without 'Secure' Attribute
- CWE-352: Cross-Site Request Forgery (CSRF)
- CWE-384: Session Fixation
- CWE-613: Insufficient Session Expiration
"""

import sqlite3

from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    Confidence,
    RuleMetadata,
)
from theauditor.indexer.schema import build_query


METADATA = RuleMetadata(
    name="session_security",
    category="auth",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=[
        "frontend/",
        "client/",
        "test/",
        "spec.",
        ".test.",
        "__tests__",
        "demo/",
        "example/",
    ],
    requires_jsx_pass=False,
    execution_scope="database",
)


COOKIE_FUNCTION_KEYWORDS = frozenset([".cookie", "cookies.set", "setcookie"])


SESSION_FUNCTION_KEYWORDS = frozenset(["session", "express-session", "cookie-session"])


SESSION_VAR_PATTERNS = frozenset(["session.", "req.session.", "request.session."])


AUTH_VAR_KEYWORDS = frozenset(["user", "userid", "authenticated", "logged", "loggedin"])


SESSION_COOKIE_KEYWORDS = frozenset(["session", "auth", "token", "sid"])


def find_session_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect session and cookie security vulnerabilities.

    This is a database-first rule following the gold standard pattern.
    NO file I/O, NO AST traversal - only SQL queries on indexed data.
    All pattern matching done in Python after database fetch.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of session security findings

    Example findings:
        - res.cookie('token', jwt) without httpOnly flag
        - session() middleware without maxAge configuration
        - req.session.userId = user.id without session.regenerate()
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        findings.extend(_check_missing_httponly(cursor))

        findings.extend(_check_missing_secure(cursor))

        findings.extend(_check_missing_samesite(cursor))

        findings.extend(_check_session_fixation(cursor))

        findings.extend(_check_missing_timeout(cursor))

    finally:
        conn.close()

    return findings


def _check_missing_httponly(cursor) -> list[StandardFinding]:
    """Detect cookies set without httpOnly flag.

    Without httpOnly flag, JavaScript can access cookies via document.cookie,
    making them vulnerable to XSS attacks.

    CWE-1004: Sensitive Cookie Without 'HttpOnly' Flag
    """
    findings = []

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        order_by="file, line",
    )
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()

        is_cookie_function = any(keyword in func_lower for keyword in COOKIE_FUNCTION_KEYWORDS)
        if not is_cookie_function:
            continue

        args_str = args if args else ""

        args_normalized = args_str.replace(" ", "").lower()

        if "httponly" not in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-missing-httponly",
                    message="Cookie set without httpOnly flag (XSS can steal session)",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-1004",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...)",
                    recommendation="Set httpOnly: true in cookie options to prevent JavaScript access",
                )
            )

        elif "httponly:false" in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-httponly-disabled",
                    message="Cookie httpOnly flag explicitly disabled",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-1004",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...httpOnly: false...)",
                    recommendation="Remove httpOnly: false to enable default protection",
                )
            )

    return findings


def _check_missing_secure(cursor) -> list[StandardFinding]:
    """Detect cookies set without secure flag.

    Without secure flag, cookies can be transmitted over unencrypted HTTP,
    making them vulnerable to man-in-the-middle attacks.

    CWE-614: Sensitive Cookie in HTTPS Session Without 'Secure' Attribute
    """
    findings = []

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        order_by="file, line",
    )
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()

        is_cookie_function = any(keyword in func_lower for keyword in COOKIE_FUNCTION_KEYWORDS)
        if not is_cookie_function:
            continue

        args_str = args if args else ""

        args_normalized = args_str.replace(" ", "").lower()

        if "secure" not in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-missing-secure",
                    message="Cookie set without secure flag (vulnerable to MITM)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-614",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...)",
                    recommendation="Set secure: true to ensure cookies only sent over HTTPS",
                )
            )

        elif "secure:false" in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-secure-disabled",
                    message="Cookie secure flag explicitly disabled",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-614",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...secure: false...)",
                    recommendation="Set secure: true for production environments",
                )
            )

    return findings


def _check_missing_samesite(cursor) -> list[StandardFinding]:
    """Detect cookies set without SameSite attribute.

    Without SameSite attribute, cookies are sent with cross-site requests,
    making them vulnerable to CSRF attacks.

    CWE-352: Cross-Site Request Forgery (CSRF)
    """
    findings = []

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        order_by="file, line",
    )
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()

        is_cookie_function = any(keyword in func_lower for keyword in COOKIE_FUNCTION_KEYWORDS)
        if not is_cookie_function:
            continue

        args_str = args if args else ""

        args_normalized = args_str.replace(" ", "").lower()

        if "samesite" not in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-missing-samesite",
                    message="Cookie set without SameSite attribute (CSRF risk)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-352",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(...)",
                    recommendation='Set sameSite: "strict" or "lax" to prevent CSRF attacks',
                )
            )

        elif 'samesite:"none"' in args_normalized or "samesite:'none'" in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-samesite-none",
                    message='Cookie SameSite set to "none" (disables CSRF protection)',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-352",
                    confidence=Confidence.HIGH,
                    snippet=f'{func}(...sameSite: "none"...)',
                    recommendation='Use sameSite: "strict" or "lax" instead of "none"',
                )
            )

    return findings


def _check_session_fixation(cursor) -> list[StandardFinding]:
    """Detect session fixation vulnerabilities.

    Session fixation occurs when session ID is not regenerated after login,
    allowing attackers to hijack authenticated sessions.

    CWE-384: Session Fixation
    """
    findings = []

    query = build_query(
        "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
    )
    cursor.execute(query)

    session_assignments = []
    for file, line, var, expr in cursor.fetchall():
        var_lower = var.lower()

        has_session_prefix = any(pattern in var_lower for pattern in SESSION_VAR_PATTERNS)
        if not has_session_prefix:
            continue

        has_auth_keyword = any(keyword in var_lower for keyword in AUTH_VAR_KEYWORDS)
        if not has_auth_keyword:
            continue

        session_assignments.append((file, line, var, expr))

    for file, line, var, expr in session_assignments:
        query_regenerate = build_query(
            "function_call_args", ["callee_function", "line"], where="file = ?"
        )
        cursor.execute(query_regenerate, [file])

        has_regenerate = False
        for callee, call_line in cursor.fetchall():
            if abs(call_line - line) <= 10 and "session.regenerate" in callee.lower():
                has_regenerate = True
                break

        if not has_regenerate:
            findings.append(
                StandardFinding(
                    rule_name="session-fixation",
                    message=f"Session variable {var} set without session.regenerate() (session fixation risk)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-384",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{var} = {expr[:50]}"
                    if len(expr) <= 50
                    else f"{var} = {expr[:50]}...",
                    recommendation="Call session.regenerate() before setting authentication state",
                )
            )

    return findings


def _check_missing_timeout(cursor) -> list[StandardFinding]:
    """Detect session configuration without timeout/expiration.

    Sessions without expiration can be valid indefinitely, increasing
    the window for session hijacking attacks.

    CWE-613: Insufficient Session Expiration
    """
    findings = []

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        where="argument_index = 0",
        order_by="file, line",
    )
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()

        is_session_function = any(keyword in func_lower for keyword in SESSION_FUNCTION_KEYWORDS)
        if not is_session_function:
            continue

        args_str = args if args else ""

        has_expiration = "maxAge" in args_str or "expires" in args_str or "ttl" in args_str
        if not has_expiration:
            findings.append(
                StandardFinding(
                    rule_name="session-no-timeout",
                    message="Session configuration missing expiration (maxAge/expires/ttl)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-613",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(...)",
                    recommendation="Set cookie.maxAge or expires to limit session lifetime",
                )
            )

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        order_by="file, line",
    )
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()

        is_cookie_function = any(keyword in func_lower for keyword in COOKIE_FUNCTION_KEYWORDS)
        if not is_cookie_function:
            continue

        args_str = args if args else ""
        args_lower = args_str.lower()

        has_session_cookie = any(keyword in args_lower for keyword in SESSION_COOKIE_KEYWORDS)
        if not has_session_cookie:
            continue

        has_expiration = "maxAge" in args_str or "expires" in args_str
        if not has_expiration:
            findings.append(
                StandardFinding(
                    rule_name="session-cookie-no-expiration",
                    message="Session cookie set without expiration (maxAge/expires)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-613",
                    confidence=Confidence.LOW,
                    snippet=f"{func}(...)",
                    recommendation="Set maxAge or expires to automatically expire session cookies",
                )
            )

    return findings
