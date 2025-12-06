"""Next.js Framework Security Analyzer.

Detects security vulnerabilities in Next.js applications including:
- Server-side environment variable exposure (CWE-200)
- Open redirect vulnerabilities (CWE-601)
- SSR injection risks (CWE-79)
- CSRF protection gaps (CWE-352)
- dangerouslySetInnerHTML without sanitization (CWE-79)
- Error details exposure (CWE-209)
- Missing rate limiting (CWE-770)
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
    name="nextjs_security",
    category="frameworks",
    target_extensions=[".js", ".jsx", ".ts", ".tsx"],
    exclude_patterns=["node_modules/", "test/", "spec.", "__tests__/"],
    execution_scope="database",
    primary_table="function_call_args",
)


RESPONSE_FUNCTIONS = frozenset(
    [
        "res.json",
        "res.send",
        "NextResponse.json",
        "NextResponse.redirect",
        "NextResponse.rewrite",
    ]
)


REDIRECT_FUNCTIONS = frozenset(
    [
        "router.push",
        "router.replace",
        "redirect",
        "permanentRedirect",
        "NextResponse.redirect",
    ]
)


USER_INPUT_SOURCES = frozenset(
    [
        "query",
        "params",
        "searchParams",
        "req.query",
        "req.body",
        "req.params",
        "formData",
    ]
)


SENSITIVE_ENV_PATTERNS = frozenset(
    [
        "SECRET",
        "PRIVATE",
        "KEY",
        "TOKEN",
        "PASSWORD",
        "API_KEY",
        "CREDENTIAL",
        "AUTH",
    ]
)


SSR_FUNCTIONS = frozenset(
    [
        "getServerSideProps",
        "getStaticProps",
        "getInitialProps",
        "generateStaticParams",
        "generateMetadata",
    ]
)


SANITIZATION_FUNCTIONS = frozenset(
    [
        "escape",
        "sanitize",
        "validate",
        "DOMPurify",
        "escapeHtml",
        "sanitizeHtml",
        "xss",
    ]
)


RATE_LIMIT_LIBRARIES = frozenset(
    [
        "rate-limiter",
        "express-rate-limit",
        "next-rate-limit",
        "rate-limiter-flexible",
        "slowDown",
    ]
)


CSRF_INDICATORS = frozenset(
    [
        "csrf",
        "CSRF",
        "csrfToken",
        "X-CSRF-Token",
        "next-csrf",
        "csurf",
    ]
)


DANGEROUS_SINKS = frozenset(
    [
        "dangerouslySetInnerHTML",
        "eval",
        "Function",
        "setTimeout",
        "setInterval",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Next.js security vulnerabilities using indexed data.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        findings.extend(_check_api_secret_exposure(db))
        findings.extend(_check_open_redirect(db))
        findings.extend(_check_ssr_injection(db))
        findings.extend(_check_public_env_exposure(db))
        findings.extend(_check_csrf_protection(db))
        findings.extend(_check_error_details_exposure(db))
        findings.extend(_check_dangerous_html(db))
        findings.extend(_check_rate_limiting(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_api_secret_exposure(db: RuleDB) -> list[StandardFinding]:
    """Check for server-side environment variables exposed in API responses."""
    findings = []

    for func in RESPONSE_FUNCTIONS:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function = ?", func)
            .order_by("file, line")
        )

        for file, line, _callee, response_data in rows:
            if not response_data:
                continue

            if "pages/api/" not in file and "app/api/" not in file:
                continue

            if "process.env" not in response_data:
                continue

            if "NEXT_PUBLIC" in response_data:
                continue

            findings.append(
                StandardFinding(
                    rule_name="nextjs-api-secret-exposure",
                    message="Server-side environment variables exposed in API route response",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-200",
                    snippet=f"{_callee}({response_data[:60]}...)"
                    if len(response_data) > 60
                    else f"{_callee}({response_data})",
                )
            )

    return findings


def _check_open_redirect(db: RuleDB) -> list[StandardFinding]:
    """Check for unvalidated user input in redirect functions."""
    findings = []

    for func in REDIRECT_FUNCTIONS:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function = ?", func)
            .order_by("file, line")
        )

        for file, line, callee, redirect_arg in rows:
            if not redirect_arg:
                continue

            if any(source in redirect_arg for source in USER_INPUT_SOURCES):
                findings.append(
                    StandardFinding(
                        rule_name="nextjs-open-redirect",
                        message=f"Unvalidated user input in {callee} - open redirect vulnerability",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="security",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-601",
                        snippet=f"{callee}({redirect_arg[:50]})"
                        if len(redirect_arg) > 50
                        else f"{callee}({redirect_arg})",
                    )
                )

    return findings


def _check_ssr_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for SSR with potentially unvalidated user input."""
    findings = []

    ssr_files = set()
    for func in SSR_FUNCTIONS:
        symbol_rows = db.query(
            Q("symbols").select("path").where("name = ? AND type = ?", func, "function")
        )
        for (file,) in symbol_rows:
            ssr_files.add(file)

        call_rows = db.query(
            Q("function_call_args")
            .select("file")
            .where("callee_function = ? OR caller_function = ?", func, func)
        )
        for (file,) in call_rows:
            ssr_files.add(file)

    for file in ssr_files:
        rows = db.query(Q("function_call_args").select("argument_expr").where("file = ?", file))

        has_user_input = False
        for (arg_expr,) in rows:
            if not arg_expr:
                continue
            if "req.query" in arg_expr or "req.body" in arg_expr or "params" in arg_expr:
                has_user_input = True
                break

        if not has_user_input:
            continue

        has_sanitization = False
        for san_func in SANITIZATION_FUNCTIONS:
            san_rows = db.query(
                Q("function_call_args")
                .select("callee_function")
                .where("file = ? AND callee_function = ?", file, san_func)
                .limit(1)
            )
            if san_rows:
                has_sanitization = True
                break

        if not has_sanitization:
            findings.append(
                StandardFinding(
                    rule_name="nextjs-ssr-injection",
                    message="Server-side rendering with potentially unvalidated user input",
                    file_path=file,
                    line=1,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_public_env_exposure(db: RuleDB) -> list[StandardFinding]:
    """Check for sensitive data in NEXT_PUBLIC_ environment variables."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var_name, _value in rows:
        if not var_name:
            continue

        if not var_name.startswith("NEXT_PUBLIC_"):
            continue

        var_name_upper = var_name.upper()
        if any(pattern in var_name_upper for pattern in SENSITIVE_ENV_PATTERNS):
            findings.append(
                StandardFinding(
                    rule_name="nextjs-public-env-exposure",
                    message=f"Sensitive data in {var_name} - exposed to client-side code",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-200",
                    snippet=var_name,
                )
            )

    return findings


def _check_csrf_protection(db: RuleDB) -> list[StandardFinding]:
    """Check for API routes handling mutations without CSRF protection."""
    findings = []

    rows = db.query(
        Q("api_endpoints")
        .select("file", "method")
        .where("method IN (?, ?, ?, ?)", "POST", "PUT", "DELETE", "PATCH")
    )

    api_routes = []
    seen = set()
    for file, method in rows:
        if "pages/api/" not in file and "app/api/" not in file:
            continue
        key = (file, method)
        if key not in seen:
            seen.add(key)
            api_routes.append((file, method))

    for file, method in api_routes:
        call_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("file = ?", file)
        )

        has_csrf = False
        for callee, arg_expr in call_rows:
            callee_lower = (callee or "").lower()
            arg_lower = (arg_expr or "").lower()
            if any(
                ind.lower() in callee_lower or ind.lower() in arg_lower for ind in CSRF_INDICATORS
            ):
                has_csrf = True
                break

        if not has_csrf:
            findings.append(
                StandardFinding(
                    rule_name="nextjs-api-csrf-missing",
                    message=f"API route handling {method} without CSRF protection",
                    file_path=file,
                    line=1,
                    severity=Severity.HIGH,
                    category="csrf",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-352",
                )
            )

    return findings


def _check_error_details_exposure(db: RuleDB) -> list[StandardFinding]:
    """Check for error stack traces or details exposed to clients."""
    findings = []

    for func in RESPONSE_FUNCTIONS:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function = ?", func)
            .order_by("file, line")
        )

        for file, line, _callee, error_data in rows:
            if not error_data:
                continue

            if "pages/" not in file and "app/" not in file:
                continue

            if (
                "error.stack" in error_data
                or "err.stack" in error_data
                or "error.message" in error_data
            ):
                findings.append(
                    StandardFinding(
                        rule_name="nextjs-error-details-exposed",
                        message="Error stack trace or details exposed to client",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="information-disclosure",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-209",
                        snippet=error_data[:80] if len(error_data) > 80 else error_data,
                    )
                )

    return findings


def _check_dangerous_html(db: RuleDB) -> list[StandardFinding]:
    """Check for dangerouslySetInnerHTML without sanitization."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            "callee_function = ? OR argument_expr LIKE ?",
            "dangerouslySetInnerHTML",
            "%dangerouslySetInnerHTML%",
        )
        .order_by("file, line")
    )

    dangerous_calls = []
    for file, line, _callee, html_content in rows:
        dangerous_calls.append((file, line, html_content))

    for file, line, html_content in dangerous_calls:
        has_sanitization = False
        for san_func in SANITIZATION_FUNCTIONS:
            san_rows = db.query(
                Q("function_call_args")
                .select("callee_function")
                .where(
                    "file = ? AND line BETWEEN ? AND ? AND callee_function = ?",
                    file,
                    line - 10,
                    line + 10,
                    san_func,
                )
                .limit(1)
            )
            if san_rows:
                has_sanitization = True
                break

        if not has_sanitization:
            findings.append(
                StandardFinding(
                    rule_name="nextjs-dangerous-html",
                    message="Use of dangerouslySetInnerHTML without sanitization - XSS risk",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-79",
                    snippet=html_content[:60]
                    if html_content and len(html_content) > 60
                    else html_content,
                )
            )

    return findings


def _check_rate_limiting(db: RuleDB) -> list[StandardFinding]:
    """Check for API routes without rate limiting."""
    findings = []

    rows = db.query(Q("api_endpoints").select("file"))

    api_route_files = set()
    for (file,) in rows:
        if "pages/api/" in file or "app/api/" in file:
            api_route_files.add(file)

    if len(api_route_files) < 3:
        return findings

    has_rate_limiting = False
    for lib in RATE_LIMIT_LIBRARIES:
        lib_rows = db.query(Q("refs").select("value").where("value = ?", lib).limit(1))
        if lib_rows:
            has_rate_limiting = True
            break

    if not has_rate_limiting:
        api_file = next(iter(api_route_files), None)
        if api_file:
            findings.append(
                StandardFinding(
                    rule_name="nextjs-missing-rate-limit",
                    message="Multiple API routes without rate limiting - vulnerable to abuse",
                    file_path=api_file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="security",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-770",
                )
            )

    return findings


def register_taint_patterns(taint_registry) -> None:
    """Register Next.js-specific taint patterns for dataflow analysis."""
    for pattern in RESPONSE_FUNCTIONS | REDIRECT_FUNCTIONS:
        taint_registry.register_sink(pattern, "nextjs", "javascript")

    for pattern in USER_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")

    for pattern in DANGEROUS_SINKS:
        taint_registry.register_sink(pattern, "code_execution", "javascript")
