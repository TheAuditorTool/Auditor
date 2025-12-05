"""OAuth/SSO Security Analyzer - Database-First Approach.

Detects OAuth vulnerabilities including:
- Missing state parameter for CSRF protection (CWE-352)
- Missing PKCE for authorization code flows (CWE-287)
- Unvalidated redirect URIs leading to open redirect (CWE-601)
- OAuth tokens exposed in URL fragments or parameters (CWE-598)
- Deprecated implicit flow usage (CWE-598)
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
    name="oauth_security",
    category="auth",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["test/", "spec.", ".test.", "__tests__", "demo/", "example/"],
    execution_scope="database",
    primary_table="function_call_args",
)


OAUTH_URL_KEYWORDS = frozenset(["oauth", "authorize", "callback", "redirect", "auth", "login"])


STATE_KEYWORDS = frozenset([
    "state", "csrf", "oauthState", "csrfToken", "oauthstate", "csrftoken",
    "nonce", "oauth_nonce",  # OIDC replay protection
])

# PKCE (Proof Key for Code Exchange) - Required for SPAs/mobile apps (RFC 7636)
PKCE_KEYWORDS = frozenset([
    "code_challenge", "codechallenge", "codeChallenge",
    "code_verifier", "codeverifier", "codeVerifier",
    "pkce", "S256", "plain",  # S256 is recommended, plain is weak but present
])


REDIRECT_KEYWORDS = frozenset([
    "redirect", "returnUrl", "return_url", "redirectUri", "redirect_uri", "redirect_url"
])


USER_INPUT_SOURCES = frozenset([
    "req.query", "req.params", "request.query", "request.params", "request.args"
])


VALIDATION_KEYWORDS = frozenset(["validate", "whitelist", "allowed", "check", "verify"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect OAuth and SSO security vulnerabilities."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_missing_oauth_state(db))
        findings.extend(_check_missing_pkce(db))
        findings.extend(_check_redirect_validation(db))
        findings.extend(_check_token_in_url(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_missing_oauth_state(db: RuleDB) -> list[StandardFinding]:
    """Detect OAuth flows without state parameter."""
    findings = []

    rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "method", "pattern")
        .where("method IN ('GET', 'POST')")
        .order_by("file")
    )

    oauth_endpoints = []
    for file, line, method, pattern in rows:
        pattern_lower = pattern.lower()
        if any(keyword in pattern_lower for keyword in OAUTH_URL_KEYWORDS):
            oauth_endpoints.append((file, line, method, pattern))

    for file, line, method, pattern in oauth_endpoints:
        func_args_rows = db.query(
            Q("function_call_args")
            .select("argument_expr")
            .where("file = ?", file)
            .limit(100)
        )

        has_state = False
        for (arg_expr,) in func_args_rows:
            arg_lower = arg_expr.lower()
            if any(keyword in arg_lower for keyword in STATE_KEYWORDS):
                has_state = True
                break

        if not has_state:
            assign_rows = db.query(
                Q("assignments")
                .select("target_var", "source_expr")
                .where("file = ?", file)
                .limit(100)
            )

            for target_var, source_expr in assign_rows:
                target_lower = target_var.lower()
                source_lower = source_expr.lower() if source_expr else ""
                # Check variable names AND source expressions
                if any(
                    keyword in target_lower or keyword in source_lower
                    for keyword in STATE_KEYWORDS
                ):
                    has_state = True
                    break
                # Check for property access patterns: config.state, params.state, .state:
                if ".state" in target_lower or ": state" in source_lower or '"state"' in source_lower:
                    has_state = True
                    break

        if not has_state:
            findings.append(
                StandardFinding(
                    rule_name="oauth-missing-state",
                    message=f"OAuth endpoint {pattern} missing state parameter (CSRF risk). Generate random state and validate on callback.",
                    file_path=file,
                    line=line or 1,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-352",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{method} {pattern}",
                )
            )

    return findings


def _check_missing_pkce(db: RuleDB) -> list[StandardFinding]:
    """Detect authorization code flows without PKCE (RFC 7636).

    PKCE is required for SPAs and mobile apps to prevent authorization code interception.
    Public clients (no client_secret) MUST use PKCE. Confidential clients SHOULD use it.
    """
    findings = []

    # Look for authorization code flows (response_type=code) without PKCE
    assign_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    code_flow_files = {}  # file -> (line, snippet)

    for file, line, target_var, source_expr in assign_rows:
        expr_lower = source_expr.lower() if source_expr else ""
        target_lower = target_var.lower()

        # Detect authorization code flow setup
        if "response_type" in expr_lower and "code" in expr_lower:
            if file not in code_flow_files:
                code_flow_files[file] = (line, source_expr[:60])
        # Also detect OAuth config objects
        if any(kw in target_lower for kw in ["oauth", "auth", "oidc"]) and "config" in target_lower:
            if "code" in expr_lower:
                if file not in code_flow_files:
                    code_flow_files[file] = (line, source_expr[:60])

    # For each file with code flow, check if PKCE is present
    for file, (first_line, snippet) in code_flow_files.items():
        # Check function args for PKCE keywords
        func_args_rows = db.query(
            Q("function_call_args")
            .select("argument_expr")
            .where("file = ?", file)
            .limit(200)
        )

        has_pkce = False
        for (arg_expr,) in func_args_rows:
            arg_lower = arg_expr.lower()
            if any(keyword in arg_lower for keyword in PKCE_KEYWORDS):
                has_pkce = True
                break

        if not has_pkce:
            # Check assignments for PKCE
            file_assigns = db.query(
                Q("assignments")
                .select("target_var", "source_expr")
                .where("file = ?", file)
                .limit(200)
            )

            for target_var, source_expr in file_assigns:
                target_lower = target_var.lower()
                source_lower = source_expr.lower() if source_expr else ""
                if any(
                    keyword in target_lower or keyword in source_lower
                    for keyword in PKCE_KEYWORDS
                ):
                    has_pkce = True
                    break
                # Check property access patterns
                if ".code_challenge" in target_lower or ".codechallenge" in target_lower:
                    has_pkce = True
                    break
                if '"code_challenge"' in source_lower or "'code_challenge'" in source_lower:
                    has_pkce = True
                    break

        if not has_pkce:
            findings.append(
                StandardFinding(
                    rule_name="oauth-missing-pkce",
                    message="Authorization code flow without PKCE. Add code_challenge (S256) to prevent code interception attacks on SPAs/mobile.",
                    file_path=file,
                    line=first_line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-287",
                    confidence=Confidence.MEDIUM,
                    snippet=snippet if len(snippet) <= 60 else snippet[:57] + "...",
                )
            )

    return findings


def _check_redirect_validation(db: RuleDB) -> list[StandardFinding]:
    """Detect OAuth redirect URI validation issues."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    redirect_calls = []
    for file, line, func, args in rows:
        if "redirect" in func.lower():
            args_lower = args.lower()
            if any(user_input in args_lower for user_input in USER_INPUT_SOURCES):
                redirect_calls.append((file, line, func, args))

    for file, line, func, _args in redirect_calls:
        val_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("file = ? AND line >= ? AND line < ?", file, max(1, line - 10), line)
        )

        has_validation = False
        for val_func, val_args in val_rows:
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
                    message="OAuth redirect without URI validation (open redirect risk). Validate redirect_uri against whitelist of registered URIs.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-601",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(user input)",
                )
            )

    assign_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    redirect_assignments = []
    for file, line, var, expr in assign_rows:
        var_lower = var.lower()
        expr_lower = expr.lower() if expr else ""

        if any(keyword in var_lower for keyword in REDIRECT_KEYWORDS) and any(
            user_input in expr_lower for user_input in USER_INPUT_SOURCES
        ):
            redirect_assignments.append((file, line, var, expr))

    for file, line, var, expr in redirect_assignments:
        val_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("file = ? AND line > ? AND line <= ?", file, line, line + 10)
        )

        has_validation = False
        for val_func, val_args in val_rows:
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
                    message="Redirect URI from user input without validation. Check against whitelist before use.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-601",
                    confidence=Confidence.LOW,
                    snippet=f"{var} = {expr[:40]}" if len(expr) <= 40 else f"{var} = {expr[:40]}...",
                )
            )

    return findings


def _check_token_in_url(db: RuleDB) -> list[StandardFinding]:
    """Detect OAuth tokens in URL fragments or parameters."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    all_assignments = list(rows)

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
                    message="OAuth token in URL fragment (exposed in browser history). Use authorization code flow instead.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.HIGH,
                    snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
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
                    message="OAuth token in URL query parameter (logged by servers). Send tokens in Authorization header or POST body.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.HIGH,
                    snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
                )
            )

    for file, line, _var, expr in all_assignments:
        expr_lower = expr.lower()
        # Detect implicit flow: response_type=token, id_token, or id_token token (without code)
        if "response_type" in expr_lower and "code" not in expr_lower:
            is_implicit = (
                "token" in expr_lower  # response_type=token
                or "id_token" in expr_lower  # response_type=id_token (OIDC implicit)
            )
            if is_implicit:
                findings.append(
                    StandardFinding(
                        rule_name="oauth-implicit-flow",
                        message="OAuth/OIDC implicit flow detected. Tokens in URL fragments are exposed in browser history. Use authorization code flow with PKCE instead.",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="authentication",
                        cwe_id="CWE-598",
                        confidence=Confidence.MEDIUM,
                        snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
                    )
                )

    return findings
