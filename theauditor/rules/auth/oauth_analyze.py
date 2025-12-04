"""OAuth/SSO Security Analyzer - Database-First Approach."""

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
    name="oauth_security",
    category="auth",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["test/", "spec.", ".test.", "__tests__", "demo/", "example/"],
    execution_scope="database")


OAUTH_URL_KEYWORDS = frozenset(["oauth", "authorize", "callback", "redirect", "auth", "login"])


STATE_KEYWORDS = frozenset(["state", "csrf", "oauthState", "csrfToken", "oauthstate", "csrftoken"])


REDIRECT_KEYWORDS = frozenset(
    ["redirect", "returnUrl", "return_url", "redirectUri", "redirect_uri", "redirect_url"]
)


USER_INPUT_SOURCES = frozenset(
    ["req.query", "req.params", "request.query", "request.params", "request.args"]
)


VALIDATION_KEYWORDS = frozenset(["validate", "whitelist", "allowed", "check", "verify"])


TOKEN_URL_PATTERNS = frozenset(
    [
        "#access_token=",
        "#token=",
        "#accessToken=",
        "#id_token=",
        "#refresh_token=",
        "?access_token=",
        "&access_token=",
        "?token=",
        "&token=",
        "?accessToken=",
        "&accessToken=",
    ]
)


def find_oauth_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect OAuth and SSO security vulnerabilities."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        findings.extend(_check_missing_oauth_state(cursor))

        findings.extend(_check_redirect_validation(cursor))

        findings.extend(_check_token_in_url(cursor))

    finally:
        conn.close()

    return findings


def _check_missing_oauth_state(cursor) -> list[StandardFinding]:
    """Detect OAuth flows without state parameter."""
    findings = []

    query = build_query(
        "api_endpoints",
        ["file", "line", "method", "pattern"],
        where="method IN ('GET', 'POST')",
        order_by="file",
    )
    cursor.execute(query)

    oauth_endpoints = []
    for file, line, method, pattern in cursor.fetchall():
        pattern_lower = pattern.lower()
        if any(keyword in pattern_lower for keyword in OAUTH_URL_KEYWORDS):
            oauth_endpoints.append((file, line, method, pattern))

    for file, line, method, pattern in oauth_endpoints:
        check_query = build_query(
            "function_call_args", ["argument_expr"], where="file = ?", limit=100
        )
        cursor.execute(check_query, [file])

        has_state = False
        for (arg_expr,) in cursor.fetchall():
            arg_lower = arg_expr.lower()
            if any(keyword in arg_lower for keyword in STATE_KEYWORDS):
                has_state = True
                break

        if not has_state:
            assign_query = build_query(
                "assignments", ["target_var", "source_expr"], where="file = ?", limit=100
            )
            cursor.execute(assign_query, [file])

            for target_var, source_expr in cursor.fetchall():
                target_lower = target_var.lower()
                source_lower = source_expr.lower() if source_expr else ""
                if any(
                    keyword in target_lower or keyword in source_lower for keyword in STATE_KEYWORDS
                ):
                    has_state = True
                    break

        if not has_state:
            findings.append(
                StandardFinding(
                    rule_name="oauth-missing-state",
                    message=f"OAuth endpoint {pattern} missing state parameter (CSRF risk)",
                    file_path=file,
                    line=line or 1,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-352",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{method} {pattern}",
                    recommendation="Generate random state parameter and validate on callback",
                )
            )

    return findings


def _check_redirect_validation(cursor) -> list[StandardFinding]:
    """Detect OAuth redirect URI validation issues."""
    findings = []

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        order_by="file, line",
    )
    cursor.execute(query)

    redirect_calls = []
    for file, line, func, args in cursor.fetchall():
        if "redirect" in func.lower():
            args_lower = args.lower()
            if any(user_input in args_lower for user_input in USER_INPUT_SOURCES):
                redirect_calls.append((file, line, func, args))

    for file, line, _func, _args in redirect_calls:
        val_query = build_query(
            "function_call_args",
            ["callee_function", "argument_expr"],
            where="file = ? AND line >= ? AND line < ?",
        )
        cursor.execute(val_query, [file, max(1, line - 10), line])

        has_validation = False
        for val_func, val_args in cursor.fetchall():
            val_func_lower = val_func.lower()
            val_args_lower = val_args.lower()
            if any(
                keyword in val_func_lower or keyword in val_args_lower
                for keyword in VALIDATION_KEYWORDS
            ):
                has_validation = True
                break

        if not has_validation:
            findings.append(
                StandardFinding(
                    rule_name="oauth-unvalidated-redirect",
                    message="OAuth redirect without URI validation (open redirect risk)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-601",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(user input)",
                    recommendation="Validate redirect_uri against whitelist of registered URIs",
                )
            )

    query = build_query(
        "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
    )
    cursor.execute(query)

    redirect_assignments = []
    for file, line, var, expr in cursor.fetchall():
        var_lower = var.lower()
        expr_lower = expr.lower() if expr else ""

        if any(keyword in var_lower for keyword in REDIRECT_KEYWORDS) and any(
            user_input in expr_lower for user_input in USER_INPUT_SOURCES
        ):
            redirect_assignments.append((file, line, var, expr))

    for file, line, var, expr in redirect_assignments:
        val_query = build_query(
            "function_call_args",
            ["callee_function", "argument_expr"],
            where="file = ? AND line > ? AND line <= ?",
        )
        cursor.execute(val_query, [file, line, line + 10])

        has_validation = False
        for val_func, val_args in cursor.fetchall():
            val_func_lower = val_func.lower()
            val_args_lower = val_args.lower()

            if var.lower() in val_args_lower and any(
                keyword in val_func_lower for keyword in VALIDATION_KEYWORDS
            ):
                has_validation = True
                break

        if not has_validation:
            findings.append(
                StandardFinding(
                    rule_name="oauth-redirect-assignment-unvalidated",
                    message="Redirect URI from user input without validation",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-601",
                    confidence=Confidence.LOW,
                    snippet=f"{var} = {expr[:40]}"
                    if len(expr) <= 40
                    else f"{var} = {expr[:40]}...",
                    recommendation="Validate redirect_uri before use: check against whitelist",
                )
            )

    return findings


def _check_token_in_url(cursor) -> list[StandardFinding]:
    """Detect OAuth tokens in URL fragments or parameters."""
    findings = []

    query = build_query(
        "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
    )
    cursor.execute(query)

    all_assignments = cursor.fetchall()

    for file, line, _var, expr in all_assignments:
        if any(
            pattern in expr
            for pattern in [
                "#access_token=",
                "#token=",
                "#accessToken=",
                "#id_token=",
                "#refresh_token=",
            ]
        ):
            findings.append(
                StandardFinding(
                    rule_name="oauth-token-in-url-fragment",
                    message="OAuth token in URL fragment (exposed in browser history)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.HIGH,
                    snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
                    recommendation="Use authorization code flow; never put tokens in URL",
                )
            )

    for file, line, _var, expr in all_assignments:
        token_patterns = [
            "?access_token=",
            "&access_token=",
            "?token=",
            "&token=",
            "?accessToken=",
            "&accessToken=",
        ]
        if any(pattern in expr for pattern in token_patterns):
            findings.append(
                StandardFinding(
                    rule_name="oauth-token-in-url-param",
                    message="OAuth token in URL query parameter (logged by servers)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.HIGH,
                    snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
                    recommendation="Send tokens in Authorization header or POST body, not URL",
                )
            )

    # CHECK 3C: Implicit flow usage (response_type=token)
    for file, line, _var, expr in all_assignments:
        expr_lower = expr.lower()
        if "response_type" in expr_lower and "token" in expr_lower and "code" not in expr_lower:
            findings.append(
                StandardFinding(
                    rule_name="oauth-implicit-flow",
                    message="OAuth implicit flow detected (response_type=token)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.MEDIUM,
                    snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
                    recommendation="Use authorization code flow (response_type=code) instead of implicit flow",
                )
            )

    return findings
