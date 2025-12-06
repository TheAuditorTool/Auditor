"""Session Management Security Analyzer - Database-First Approach.

Detects session/cookie vulnerabilities including:
- Missing httpOnly flag on cookies (CWE-1004)
- Missing secure flag on cookies (CWE-614)
- Missing or weak SameSite attribute (CWE-352)
- Session fixation vulnerabilities (CWE-384)
- Missing session expiration/timeout (CWE-613)
- Missing __Host-/__Secure- cookie prefixes (CWE-1275)
- Session ID in URL parameters (CWE-598)
- Session ID predictability/weak randomness (CWE-330)
- Missing session invalidation on logout (CWE-613)
- Missing concurrent session controls (CWE-384)
- Session isolation issues (CWE-488)
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
        findings.extend(_check_session_in_url(db))
        findings.extend(_check_session_predictability(db))
        findings.extend(_check_logout_invalidation(db))
        findings.extend(_check_concurrent_sessions(db))
        findings.extend(_check_session_isolation(db))

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
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
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
            Q("function_call_args").select("callee_function", "line").where("file = ?", file)
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
                    snippet=f"{var} = {expr[:50]}"
                    if len(expr) <= 50
                    else f"{var} = {expr[:50]}...",
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

        is_cookie_function = any(keyword in func_lower for keyword in COOKIE_FUNCTION_KEYWORDS)
        if not is_cookie_function:
            continue

        args_lower = (args or "").lower()

        is_sensitive_cookie = any(keyword in args_lower for keyword in SESSION_COOKIE_KEYWORDS)
        if not is_sensitive_cookie:
            continue

        if arg_idx == 0:
            cookie_name = args.strip('"').strip("'")

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

    assign_rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target_var, source_expr in assign_rows:
        target_lower = target_var.lower()
        source_lower = (source_expr or "").lower()

        if "cookie" not in target_lower or "name" not in target_lower:
            continue

        if not any(keyword in source_lower for keyword in SESSION_COOKIE_KEYWORDS):
            continue

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


def _check_session_in_url(db: RuleDB) -> list[StandardFinding]:
    """Detect session IDs passed via URL query parameters or path.

    Session IDs in URLs leak via Referer header, browser history, server logs,
    and can be easily shared/bookmarked. CWE-598.
    """
    findings = []

    session_url_patterns = [
        "?sessionid=",
        "&sessionid=",
        "?session_id=",
        "&session_id=",
        "?sid=",
        "&sid=",
        "?jsessionid=",
        "&jsessionid=",
        ";jsessionid=",
        "?phpsessid=",
        "&phpsessid=",
        "?aspsessionid",
        "&aspsessionid",
        "/session/",
        "/sid/",
    ]

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, _target_var, source_expr in rows:
        source_lower = (source_expr or "").lower()

        if any(pattern in source_lower for pattern in session_url_patterns):
            findings.append(
                StandardFinding(
                    rule_name="session-id-in-url",
                    message="Session ID in URL parameter. Leaks to browser history, Referer headers, and server logs. Use cookies instead.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.HIGH,
                    snippet=source_expr[:60] if len(source_expr) <= 60 else source_expr[:57] + "...",
                )
            )

    # Also check function calls for URL construction with session
    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in func_rows:
        func_lower = func.lower()
        args_lower = (args or "").lower()

        url_funcs = ["url", "redirect", "href", "location", "navigate"]
        if not any(uf in func_lower for uf in url_funcs):
            continue

        session_keywords = ["sessionid", "session_id", "sid", "jsessionid", "phpsessid"]
        if any(sk in args_lower for sk in session_keywords):
            findings.append(
                StandardFinding(
                    rule_name="session-id-in-url-construction",
                    message="Session ID included in URL construction. Never pass session IDs via URL - use cookies.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(...session...)",
                )
            )

    return findings


def _check_session_predictability(db: RuleDB) -> list[StandardFinding]:
    """Detect session ID generation using weak randomness.

    Predictable session IDs can be brute-forced or guessed. Must use
    cryptographically secure random number generators. CWE-330.
    """
    findings = []

    weak_random_patterns = frozenset([
        "math.random",
        "random.random",
        "random.randint",
        "date.now",
        "new date",
        "timestamp",
        "time.time",
        "datetime.now",
        "uuid.v1",  # v1 is time-based, predictable
        "counter",
        "++",
        "auto_increment",
    ])

    secure_random_patterns = frozenset([
        "crypto.randombytes",
        "crypto.randomuuid",
        "uuid.v4",
        "uuidv4",
        "secrets.token",
        "os.urandom",
        "nanoid",
        "csprng",
        "securerandom",
        "randomuuid",
    ])

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target_var, source_expr in rows:
        target_lower = target_var.lower()
        source_lower = (source_expr or "").lower()

        # Check if this is session ID related
        session_keywords = ["sessionid", "session_id", "sid", "sessid"]
        if not any(sk in target_lower for sk in session_keywords):
            continue

        # Skip if using secure random
        if any(secure in source_lower for secure in secure_random_patterns):
            continue

        # Check for weak random patterns
        if any(weak in source_lower for weak in weak_random_patterns):
            findings.append(
                StandardFinding(
                    rule_name="session-id-weak-random",
                    message="Session ID uses weak randomness. Use crypto.randomBytes (Node) or secrets.token_urlsafe (Python) for unpredictable session IDs.",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-330",
                    confidence=Confidence.HIGH,
                    snippet=f"{target_var} = {source_expr[:40]}..."
                    if len(source_expr) > 40
                    else f"{target_var} = {source_expr}",
                )
            )

    return findings


def _check_logout_invalidation(db: RuleDB) -> list[StandardFinding]:
    """Detect logout implementations that don't properly invalidate server-side sessions.

    Client-side only logout (cookie deletion) leaves the session valid for replay.
    Server must explicitly destroy the session. CWE-613.
    """
    findings = []

    # Find logout handlers
    endpoint_rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "method", "pattern")
        .order_by("file")
    )

    logout_patterns = ["logout", "signout", "sign-out", "logoff", "log-off"]

    logout_endpoints = []
    for file, line, _method, pattern in endpoint_rows:
        pattern_lower = pattern.lower()
        if any(lp in pattern_lower for lp in logout_patterns):
            logout_endpoints.append((file, line, pattern))

    for file, line, pattern in logout_endpoints:
        # Check for server-side session destruction
        func_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("file = ?", file)
            .limit(200)
        )

        has_session_destroy = False
        session_destroy_patterns = [
            "session.destroy",
            "session.invalidate",
            "req.session.destroy",
            "request.session.flush",
            "session.clear",
            "logout",
            "signout",
            "delete_session",
            "remove_session",
        ]

        for callee, _args in func_rows:
            callee_lower = callee.lower()
            if any(sd in callee_lower for sd in session_destroy_patterns):
                has_session_destroy = True
                break

        if not has_session_destroy:
            # Check assignments for session = null patterns
            assign_rows = db.query(
                Q("assignments")
                .select("target_var", "source_expr")
                .where("file = ?", file)
                .limit(100)
            )

            for target_var, source_expr in assign_rows:
                target_lower = target_var.lower()
                source_lower = (source_expr or "").lower()

                if "session" in target_lower and source_lower in ("null", "none", "{}", "undefined"):
                    has_session_destroy = True
                    break

        if not has_session_destroy:
            findings.append(
                StandardFinding(
                    rule_name="logout-no-session-invalidation",
                    message=f"Logout handler {pattern} may not invalidate server-side session. Call session.destroy() to prevent session replay.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-613",
                    confidence=Confidence.MEDIUM,
                    snippet=f"Logout endpoint: {pattern}",
                )
            )

    return findings


def _check_concurrent_sessions(db: RuleDB) -> list[StandardFinding]:
    """Detect missing concurrent session limits.

    Without limits, compromised credentials can be used indefinitely across
    multiple sessions without detection. CWE-384.
    """
    findings = []

    # Look for session/login configuration without concurrent limits
    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    session_config_files = {}

    for file, line, target_var, _source_expr in rows:
        target_lower = target_var.lower()

        # Detect session configuration
        config_patterns = ["sessionconfig", "session_config", "sessionoptions", "session_options"]
        if any(cp in target_lower for cp in config_patterns):
            if file not in session_config_files:
                session_config_files[file] = (line, target_var)

    for file, (first_line, config_var) in session_config_files.items():
        # Check if concurrent session handling exists
        all_assigns = db.query(
            Q("assignments")
            .select("target_var", "source_expr")
            .where("file = ?", file)
            .limit(200)
        )

        has_concurrent_limit = False
        concurrent_patterns = [
            "maxsessions",
            "max_sessions",
            "concurrentsessions",
            "concurrent_sessions",
            "sessionlimit",
            "session_limit",
            "activesessions",
            "active_sessions",
        ]

        for target_var, source_expr in all_assigns:
            target_lower = target_var.lower()
            source_lower = (source_expr or "").lower()

            if any(cp in target_lower or cp in source_lower for cp in concurrent_patterns):
                has_concurrent_limit = True
                break

        if not has_concurrent_limit:
            func_rows = db.query(
                Q("function_call_args")
                .select("callee_function", "argument_expr")
                .where("file = ?", file)
                .limit(200)
            )

            for callee, args in func_rows:
                callee_lower = callee.lower()
                args_lower = (args or "").lower()

                if any(cp in callee_lower or cp in args_lower for cp in concurrent_patterns):
                    has_concurrent_limit = True
                    break

        if not has_concurrent_limit:
            findings.append(
                StandardFinding(
                    rule_name="session-no-concurrent-limit",
                    message="Session configuration lacks concurrent session limits. Consider limiting active sessions per user to detect credential compromise.",
                    file_path=file,
                    line=first_line,
                    severity=Severity.LOW,
                    category="authentication",
                    cwe_id="CWE-384",
                    confidence=Confidence.LOW,
                    snippet=f"{config_var} = ...",
                )
            )

    return findings


def _check_session_isolation(db: RuleDB) -> list[StandardFinding]:
    """Detect session data that could leak between users.

    Session pollution occurs when session data is stored in shared/global state
    without proper user scoping. CWE-488.
    """
    findings = []

    # Look for global/static variables used with session data
    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    global_session_patterns = frozenset([
        "global.session",
        "global.user",
        "window.session",
        "window.user",
        "app.session",
        "app.user",
        "this.session",  # In class context could be shared
    ])

    static_patterns = frozenset([
        "static session",
        "static user",
        "class.session",
        "class.user",
    ])

    for file, line, target_var, source_expr in rows:
        target_lower = target_var.lower()
        source_lower = (source_expr or "").lower()

        # Check for global session storage
        if any(gp in target_lower for gp in global_session_patterns):
            findings.append(
                StandardFinding(
                    rule_name="session-global-storage",
                    message="Session data stored in global variable. Use request-scoped storage to prevent session pollution between users.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-488",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{target_var} = ...",
                )
            )

        # Check for static session storage
        if any(sp in source_lower for sp in static_patterns):
            findings.append(
                StandardFinding(
                    rule_name="session-static-storage",
                    message="Session data in static/class variable. Static state is shared across requests - use request-local storage.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-488",
                    confidence=Confidence.MEDIUM,
                    snippet=source_expr[:50] if len(source_expr) <= 50 else source_expr[:47] + "...",
                )
            )

    # Check for shared cache without user scoping
    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    cache_functions = ["cache.set", "cache.put", "redis.set", "memcached.set"]

    for file, line, func, args in func_rows:
        func_lower = func.lower()
        args_lower = (args or "").lower()

        is_cache = any(cf in func_lower for cf in cache_functions)
        if not is_cache:
            continue

        # Check if session data is being cached without user ID in key
        session_in_value = "session" in args_lower or "user" in args_lower
        has_user_key = "userid" in args_lower or "user_id" in args_lower or "uid" in args_lower

        if session_in_value and not has_user_key:
            findings.append(
                StandardFinding(
                    rule_name="session-cache-no-user-scope",
                    message="Session data cached without user ID in key. Include user identifier in cache keys to prevent data leakage.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-488",
                    confidence=Confidence.LOW,
                    snippet=f"{func}(...session...)",
                )
            )

    return findings
