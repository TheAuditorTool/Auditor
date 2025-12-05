"""Session Management Security Analyzer - Database-First Approach.

Detects session/cookie vulnerabilities including:
- Missing httpOnly flag on cookies (CWE-1004)
- Missing secure flag on cookies (CWE-614)
- Missing or weak SameSite attribute (CWE-352)
- Session fixation vulnerabilities (CWE-384)
- Missing session expiration/timeout (CWE-613)
- Missing __Host-/__Secure- cookie prefixes (CWE-1275)
"""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

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
    execution_scope="database",
    primary_table="function_call_args",
)


COOKIE_FUNCTION_KEYWORDS = frozenset([".cookie", "cookies.set", "setcookie"])


SESSION_FUNCTION_KEYWORDS = frozenset(["session", "express-session", "cookie-session"])


SESSION_VAR_PATTERNS = frozenset(["session.", "req.session.", "request.session."])


AUTH_VAR_KEYWORDS = frozenset(["user", "userid", "authenticated", "logged", "loggedin"])


SESSION_COOKIE_KEYWORDS = frozenset(["session", "auth", "token", "sid"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect session and cookie security vulnerabilities."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_missing_httponly(db))
        findings.extend(_check_missing_secure(db))
        findings.extend(_check_missing_samesite(db))
        findings.extend(_check_session_fixation(db))
        findings.extend(_check_missing_timeout(db))
        findings.extend(_check_missing_cookie_prefix(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_missing_httponly(db: RuleDB) -> list[StandardFinding]:
    """Detect cookies set without httpOnly flag."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
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
                    message="Cookie set without httpOnly flag (XSS can steal session). Set httpOnly: true to prevent JavaScript access.",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-1004",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...)",
                )
            )

        elif "httponly:false" in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-httponly-disabled",
                    message="Cookie httpOnly flag explicitly disabled. Remove httpOnly: false to enable default protection.",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-1004",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...httpOnly: false...)",
                )
            )

    return findings


def _check_missing_secure(db: RuleDB) -> list[StandardFinding]:
    """Detect cookies set without secure flag."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
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
                    message="Cookie set without secure flag (vulnerable to MITM). Set secure: true for HTTPS-only cookies.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-614",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...)",
                )
            )

        elif "secure:false" in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-secure-disabled",
                    message="Cookie secure flag explicitly disabled. Set secure: true for production environments.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-614",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...secure: false...)",
                )
            )

    return findings


def _check_missing_samesite(db: RuleDB) -> list[StandardFinding]:
    """Detect cookies set without SameSite attribute."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
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
                    message='Cookie set without SameSite attribute (CSRF risk). Set sameSite: "strict" or "lax".',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-352",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(...)",
                )
            )

        elif 'samesite:"none"' in args_normalized or "samesite:'none'" in args_normalized:
            findings.append(
                StandardFinding(
                    rule_name="session-samesite-none",
                    message='Cookie SameSite set to "none" (disables CSRF protection). Use "strict" or "lax" instead.',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-352",
                    confidence=Confidence.HIGH,
                    snippet=f'{func}(...sameSite: "none"...)',
                )
            )

    return findings


def _check_session_fixation(db: RuleDB) -> list[StandardFinding]:
    """Detect session fixation vulnerabilities."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    session_assignments = []
    for file, line, var, expr in rows:
        var_lower = var.lower()

        has_session_prefix = any(pattern in var_lower for pattern in SESSION_VAR_PATTERNS)
        if not has_session_prefix:
            continue

        has_auth_keyword = any(keyword in var_lower for keyword in AUTH_VAR_KEYWORDS)
        if not has_auth_keyword:
            continue

        session_assignments.append((file, line, var, expr))

    for file, line, var, expr in session_assignments:
        regenerate_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "line")
            .where("file = ?", file)
        )

        has_regenerate = False
        for callee, call_line in regenerate_rows:
            if abs(call_line - line) <= 10 and "session.regenerate" in callee.lower():
                has_regenerate = True
                break

        if not has_regenerate:
            findings.append(
                StandardFinding(
                    rule_name="session-fixation",
                    message=f"Session variable {var} set without session.regenerate() (session fixation risk). Regenerate session before setting auth state.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-384",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{var} = {expr[:50]}" if len(expr) <= 50 else f"{var} = {expr[:50]}...",
                )
            )

    return findings


def _check_missing_timeout(db: RuleDB) -> list[StandardFinding]:
    """Detect session configuration without timeout/expiration."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
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
                    message="Session configuration missing expiration. Set cookie.maxAge or expires to limit session lifetime.",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-613",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(...)",
                )
            )

    cookie_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in cookie_rows:
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
                    message="Session cookie set without expiration. Set maxAge or expires to automatically expire session cookies.",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-613",
                    confidence=Confidence.LOW,
                    snippet=f"{func}(...)",
                )
            )

    return findings


def _check_missing_cookie_prefix(db: RuleDB) -> list[StandardFinding]:
    """Detect session cookies without __Host- or __Secure- prefix.

    Cookie prefixes provide browser-enforced security guarantees that attributes alone cannot:
    - __Host-: Must have Secure, Path=/, no Domain (prevents subdomain attacks)
    - __Secure-: Must have Secure (weaker but useful for subdomains)

    These prefixes prevent subdomain hijacking and man-in-the-middle cookie injection.
    """
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr", "argument_index")
        .order_by("file, line")
    )

    for file, line, func, args, arg_idx in rows:
        func_lower = func.lower()

        # Check for cookie-setting functions
        is_cookie_function = any(keyword in func_lower for keyword in COOKIE_FUNCTION_KEYWORDS)
        if not is_cookie_function:
            continue

        args_lower = (args or "").lower()

        # Check if this is a session/auth cookie (worth protecting with prefixes)
        is_sensitive_cookie = any(keyword in args_lower for keyword in SESSION_COOKIE_KEYWORDS)
        if not is_sensitive_cookie:
            continue

        # First argument (index 0) is typically the cookie name
        if arg_idx == 0:
            cookie_name = args.strip('"').strip("'")

            # Check for __Host- prefix (strongest protection)
            if not cookie_name.startswith("__Host-") and not cookie_name.startswith("__Secure-"):
                findings.append(
                    StandardFinding(
                        rule_name="session-missing-cookie-prefix",
                        message=f'Session cookie "{cookie_name}" should use __Host- or __Secure- prefix. __Host- prefix enforces Secure, Path=/, and no Domain (prevents subdomain attacks).',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="authentication",
                        cwe_id="CWE-1275",
                        confidence=Confidence.LOW,
                        snippet=f'{func}("{cookie_name}", ...)',
                    )
                )

    # Also check for cookie names in assignments (string literals)
    assign_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    for file, line, target_var, source_expr in assign_rows:
        target_lower = target_var.lower()
        source_lower = (source_expr or "").lower()

        # Check for cookie name assignments
        if "cookie" not in target_lower or "name" not in target_lower:
            continue

        # Check if it's a session-related cookie
        if not any(keyword in source_lower for keyword in SESSION_COOKIE_KEYWORDS):
            continue

        # Extract the cookie name from string literal
        cookie_name = source_expr.strip().strip('"').strip("'")

        if not cookie_name.startswith("__Host-") and not cookie_name.startswith("__Secure-"):
            findings.append(
                StandardFinding(
                    rule_name="session-cookie-name-no-prefix",
                    message=f'Cookie name "{cookie_name}" should use __Host- prefix for session cookies. Browser enforces Secure, Path=/, and blocks subdomain access.',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category="authentication",
                    cwe_id="CWE-1275",
                    confidence=Confidence.LOW,
                    snippet=f'{target_var} = "{cookie_name}"',
                )
            )

    return findings
