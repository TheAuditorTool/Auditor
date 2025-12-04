"""Next.js Framework Security Analyzer - Database-First Approach."""

import sqlite3

from theauditor.indexer.schema import build_query
from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="nextjs_security",
    category="frameworks",
    target_extensions=[".js", ".jsx", ".ts", ".tsx"],
    exclude_patterns=["node_modules/", "test/", "spec.", "__tests__"])


RESPONSE_FUNCTIONS = frozenset(
    ["res.json", "res.send", "NextResponse.json", "NextResponse.redirect", "NextResponse.rewrite"]
)


REDIRECT_FUNCTIONS = frozenset(
    ["router.push", "router.replace", "redirect", "permanentRedirect", "NextResponse.redirect"]
)


USER_INPUT_SOURCES = frozenset(
    ["query", "params", "searchParams", "req.query", "req.body", "req.params", "formData"]
)


SENSITIVE_ENV_PATTERNS = frozenset(
    ["SECRET", "PRIVATE", "KEY", "TOKEN", "PASSWORD", "API_KEY", "CREDENTIAL", "AUTH"]
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
    ["escape", "sanitize", "validate", "DOMPurify", "escapeHtml", "sanitizeHtml", "xss"]
)


VALIDATION_LIBRARIES = frozenset(
    ["zod", "yup", "joi", "validator", "express-validator", "class-validator", "superstruct"]
)


RATE_LIMIT_LIBRARIES = frozenset(
    ["rate-limiter", "express-rate-limit", "next-rate-limit", "rate-limiter-flexible", "slowDown"]
)


CSRF_INDICATORS = frozenset(["csrf", "CSRF", "csrfToken", "X-CSRF-Token", "next-csrf", "csurf"])


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Next.js security vulnerabilities using indexed data."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT src FROM refs
            WHERE value IN ('next', 'next/router', 'next/navigation', 'next/server')
            LIMIT 1
        """)
        is_nextjs = cursor.fetchone() is not None

        if not is_nextjs:
            query = build_query("files", ["path"], limit=100)
            cursor.execute(query)

            for (path,) in cursor.fetchall():
                if "pages/api/" in path or "app/api/" in path or "next.config" in path:
                    is_nextjs = True
                    break

        if not is_nextjs:
            return findings

        response_funcs_list = list(RESPONSE_FUNCTIONS)
        placeholders = ",".join("?" * len(response_funcs_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where=f"callee_function IN ({placeholders})",
            order_by="file, line",
        )
        cursor.execute(query, response_funcs_list)

        for file, line, _callee, response_data in cursor.fetchall():
            if not ("pages/api/" in file or "app/api/" in file):
                continue

            if "process.env" not in response_data:
                continue

            if response_data and "NEXT_PUBLIC" not in response_data:
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
                    )
                )

        redirect_funcs_list = list(REDIRECT_FUNCTIONS)
        placeholders = ",".join("?" * len(redirect_funcs_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where=f"callee_function IN ({placeholders})",
            order_by="file, line",
        )
        cursor.execute(query, redirect_funcs_list)

        for file, line, func, redirect_arg in cursor.fetchall():
            if redirect_arg and any(source in redirect_arg for source in USER_INPUT_SOURCES):
                findings.append(
                    StandardFinding(
                        rule_name="nextjs-open-redirect",
                        message=f"Unvalidated user input in {func} - open redirect vulnerability",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="security",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-601",
                    )
                )

        ssr_funcs_list = list(SSR_FUNCTIONS)
        placeholders = ",".join("?" * len(ssr_funcs_list))

        cursor.execute(
            f"""
            SELECT DISTINCT file FROM function_call_args
            WHERE callee_function IN ({placeholders})
               OR caller_function IN ({placeholders})
        """,
            ssr_funcs_list + ssr_funcs_list,
        )

        ssr_files = {row[0] for row in cursor.fetchall()}

        for file in ssr_files:
            query_input = build_query("function_call_args", ["argument_expr"], where="file = ?")
            cursor.execute(query_input, (file,))

            has_user_input = False
            for (arg_expr,) in cursor.fetchall():
                if "req.query" in arg_expr or "req.body" in arg_expr or "params" in arg_expr:
                    has_user_input = True
                    break

            if has_user_input:
                sanitize_list = list(SANITIZATION_FUNCTIONS)
                placeholders_san = ",".join("?" * len(sanitize_list))

                query_sanitize = build_query(
                    "function_call_args",
                    ["callee_function"],
                    where=f"file = ? AND callee_function IN ({placeholders_san})",
                    limit=1,
                )
                cursor.execute(query_sanitize, [file] + sanitize_list)
                has_sanitization = cursor.fetchone() is not None

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

        query = build_query(
            "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
        )
        cursor.execute(query)

        for file, line, var_name, _value in cursor.fetchall():
            if not var_name.startswith("NEXT_PUBLIC_"):
                continue

            var_name_upper = var_name.upper()
            if not any(pattern in var_name_upper for pattern in SENSITIVE_ENV_PATTERNS):
                continue
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
                )
            )

        query_api = build_query(
            "api_endpoints",
            ["file", "method"],
            where="method IN ('POST', 'PUT', 'DELETE', 'PATCH')",
        )
        cursor.execute(query_api)

        api_routes = []
        seen = set()
        for file, method in cursor.fetchall():
            if "pages/api/" in file or "app/api/" in file:
                key = (file, method)
                if key not in seen:
                    seen.add(key)
                    api_routes.append((file, method))

        for file, method in api_routes:
            query_csrf = build_query(
                "function_call_args", ["callee_function", "argument_expr"], where="file = ?"
            )
            cursor.execute(query_csrf, [file])

            has_csrf = False
            for callee, arg_expr in cursor.fetchall():
                callee_lower = callee.lower()
                arg_lower = arg_expr.lower()
                if any(
                    indicator.lower() in callee_lower or indicator.lower() in arg_lower
                    for indicator in CSRF_INDICATORS
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

        response_funcs_list = list(RESPONSE_FUNCTIONS)
        placeholders = ",".join("?" * len(response_funcs_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where=f"callee_function IN ({placeholders})",
            order_by="file, line",
        )
        cursor.execute(query, response_funcs_list)

        for file, line, _callee, error_data in cursor.fetchall():
            if not ("pages/" in file or "app/" in file):
                continue

            if not (
                "error.stack" in error_data
                or "err.stack" in error_data
                or "error.message" in error_data
            ):
                continue
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
                )
            )

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        dangerous_html_calls = []
        for file, line, _callee, html_content in cursor.fetchall():
            if _callee == "dangerouslySetInnerHTML" or "dangerouslySetInnerHTML" in html_content:
                dangerous_html_calls.append((file, line, html_content))

        for file, line, _html_content in dangerous_html_calls:
            sanitize_list = list(SANITIZATION_FUNCTIONS)
            placeholders = ",".join("?" * len(sanitize_list))

            query_sanitize = build_query(
                "function_call_args",
                ["callee_function"],
                where=f"""file = ?
                  AND line BETWEEN ? AND ?
                  AND callee_function IN ({placeholders})""",
                limit=1,
            )
            cursor.execute(query_sanitize, [file, line - 10, line + 10] + sanitize_list)
            has_sanitization = cursor.fetchone() is not None

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
                    )
                )

        query_api_files = build_query("api_endpoints", ["file"])
        cursor.execute(query_api_files)

        api_route_files = set()
        for (file,) in cursor.fetchall():
            if "pages/api/" in file or "app/api/" in file:
                api_route_files.add(file)

        if len(api_route_files) >= 3:
            rate_limit_list = list(RATE_LIMIT_LIBRARIES)
            placeholders = ",".join("?" * len(rate_limit_list))

            query_rate_limit = build_query(
                "refs", ["value"], where=f"value IN ({placeholders})", limit=1
            )
            cursor.execute(query_rate_limit, rate_limit_list)
            has_rate_limiting = cursor.fetchone() is not None

            if not has_rate_limiting:
                api_file = list(api_route_files)[0] if api_route_files else None
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
                            cwe_id="CWE-307",
                        )
                    )

    finally:
        conn.close()

    return findings


DANGEROUS_SINKS = frozenset(
    ["dangerouslySetInnerHTML", "eval", "Function", "setTimeout", "setInterval"]
)


def register_taint_patterns(taint_registry):
    """Register Next.js-specific taint patterns."""

    for pattern in RESPONSE_FUNCTIONS | REDIRECT_FUNCTIONS:
        taint_registry.register_sink(pattern, "nextjs", "javascript")

    for pattern in USER_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")

    for pattern in DANGEROUS_SINKS:
        taint_registry.register_sink(pattern, "code_execution", "javascript")
