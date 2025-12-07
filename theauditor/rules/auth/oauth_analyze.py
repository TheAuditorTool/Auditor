"""OAuth/SSO Security Analyzer - Database-First Approach.

Detects OAuth vulnerabilities including:
- Missing state parameter for CSRF protection (CWE-352)
- Weak/predictable state parameter (CWE-330)
- State parameter fixation (CWE-384)
- Missing PKCE for authorization code flows (CWE-287)
- Unvalidated redirect URIs leading to open redirect (CWE-601)
- OAuth tokens exposed in URL fragments or parameters (CWE-598)
- Deprecated implicit flow usage (CWE-598)
- OAuth scope escalation/validation issues (CWE-269)
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


STATE_KEYWORDS = frozenset(
    [
        "state",
        "csrf",
        "oauthState",
        "csrfToken",
        "oauthstate",
        "csrftoken",
        "nonce",
        "oauth_nonce",
    ]
)


PKCE_KEYWORDS = frozenset(
    [
        "code_challenge",
        "codechallenge",
        "codeChallenge",
        "code_verifier",
        "codeverifier",
        "codeVerifier",
        "pkce",
        "S256",
        "plain",
    ]
)


REDIRECT_KEYWORDS = frozenset(
    ["redirect", "returnUrl", "return_url", "redirectUri", "redirect_uri", "redirect_url"]
)


USER_INPUT_SOURCES = frozenset(
    ["req.query", "req.params", "request.query", "request.params", "request.args"]
)


VALIDATION_KEYWORDS = frozenset(["validate", "whitelist", "allowed", "check", "verify"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect OAuth and SSO security vulnerabilities."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_missing_oauth_state(db))
        findings.extend(_check_weak_state(db))
        findings.extend(_check_missing_pkce(db))
        findings.extend(_check_redirect_validation(db))
        findings.extend(_check_token_in_url(db))
        findings.extend(_check_scope_escalation(db))

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
        if not pattern:
            continue
        pattern_lower = pattern.lower()
        if any(keyword in pattern_lower for keyword in OAUTH_URL_KEYWORDS):
            oauth_endpoints.append((file, line, method, pattern))

    for file, line, method, pattern in oauth_endpoints:
        func_args_rows = db.query(
            Q("function_call_args").select("argument_expr").where("file = ?", file).limit(100)
        )

        has_state = False
        for (arg_expr,) in func_args_rows:
            if not arg_expr:
                continue
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

                if any(
                    keyword in target_lower or keyword in source_lower for keyword in STATE_KEYWORDS
                ):
                    has_state = True
                    break

                if (
                    ".state" in target_lower
                    or ": state" in source_lower
                    or '"state"' in source_lower
                ):
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
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    code_flow_files = {}

    for file, line, target_var, source_expr in assign_rows:
        expr_lower = source_expr.lower() if source_expr else ""
        target_lower = target_var.lower()

        if "response_type" in expr_lower and "code" in expr_lower:
            if file not in code_flow_files:
                code_flow_files[file] = (line, source_expr[:60])

        if any(kw in target_lower for kw in ["oauth", "auth", "oidc"]) and "config" in target_lower:
            if "code" in expr_lower:
                if file not in code_flow_files:
                    code_flow_files[file] = (line, source_expr[:60])

    for file, (first_line, snippet) in code_flow_files.items():
        func_args_rows = db.query(
            Q("function_call_args").select("argument_expr").where("file = ?", file).limit(200)
        )

        has_pkce = False
        for (arg_expr,) in func_args_rows:
            if not arg_expr:
                continue
            arg_lower = arg_expr.lower()
            if any(keyword in arg_lower for keyword in PKCE_KEYWORDS):
                has_pkce = True
                break

        if not has_pkce:
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
                    keyword in target_lower or keyword in source_lower for keyword in PKCE_KEYWORDS
                ):
                    has_pkce = True
                    break

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
        if not func or not args:
            continue
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
            if not val_func or not val_args:
                continue
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
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    redirect_assignments = []
    for file, line, var, expr in assign_rows:
        if not var:
            continue
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
            if not val_func or not val_args:
                continue
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
                    snippet=f"{var} = {expr[:40]}"
                    if len(expr) <= 40
                    else f"{var} = {expr[:40]}...",
                )
            )

    return findings


def _check_token_in_url(db: RuleDB) -> list[StandardFinding]:
    """Detect OAuth tokens in URL fragments or parameters."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    all_assignments = list(rows)

    for file, line, _var, expr in all_assignments:
        if not expr:
            continue
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
        if not expr:
            continue
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
        if not expr:
            continue
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


def _check_weak_state(db: RuleDB) -> list[StandardFinding]:
    """Detect weak or predictable OAuth state parameter generation.

    State must be cryptographically random to prevent CSRF and state fixation.
    Weak patterns: Math.random(), timestamps, sequential IDs, hardcoded values.
    """
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    weak_random_patterns = frozenset([
        "math.random",
        "random.random",
        "random.randint",
        "date.now",
        "new date",
        "timestamp",
        "uuid.v1",  # v1 is time-based, predictable
        "time.time",
        "datetime.now",
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
    ])

    for file, line, target_var, source_expr in rows:
        if not target_var:
            continue
        target_lower = target_var.lower()
        source_lower = (source_expr or "").lower()

        # Check if this is state-related assignment
        is_state_var = any(kw in target_lower for kw in ["state", "oauth_state", "oauthstate"])
        if not is_state_var:
            continue

        # Skip if using secure random
        if any(secure in source_lower for secure in secure_random_patterns):
            continue

        # Check for weak random patterns
        if any(weak in source_lower for weak in weak_random_patterns):
            findings.append(
                StandardFinding(
                    rule_name="oauth-weak-state",
                    message="OAuth state uses weak randomness. Use crypto.randomBytes (Node) or secrets.token_urlsafe (Python) for cryptographically secure state.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-330",
                    confidence=Confidence.HIGH,
                    snippet=f"{target_var} = {source_expr[:40]}..."
                    if len(source_expr) > 40
                    else f"{target_var} = {source_expr}",
                )
            )

        # Check for hardcoded/static state values
        if not source_expr:
            continue
        is_literal = source_expr.strip().startswith('"') or source_expr.strip().startswith("'")
        if is_literal:
            findings.append(
                StandardFinding(
                    rule_name="oauth-static-state",
                    message="OAuth state is hardcoded/static. State must be unique per request to prevent CSRF.",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-384",
                    confidence=Confidence.HIGH,
                    snippet=f"{target_var} = {source_expr[:30]}..."
                    if len(source_expr) > 30
                    else f"{target_var} = {source_expr}",
                )
            )

    return findings


def _check_scope_escalation(db: RuleDB) -> list[StandardFinding]:
    """Detect OAuth scope validation issues.

    Applications should validate that granted scopes match requested scopes,
    and should not accept broader scopes than expected.
    """
    findings = []

    # Look for token response handling without scope validation
    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    token_response_files = {}

    for file, line, target_var, source_expr in rows:
        if not target_var:
            continue
        target_lower = target_var.lower()
        source_lower = (source_expr or "").lower()

        # Detect token/scope extraction from response
        if "scope" in target_lower and any(
            pattern in source_lower
            for pattern in ["response", "token", "data", "body", "json", "result"]
        ):
            if file not in token_response_files:
                token_response_files[file] = []
            token_response_files[file].append((line, target_var, source_expr))

    for file, scope_usages in token_response_files.items():
        # Check if file has scope validation
        func_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("file = ?", file)
            .limit(200)
        )

        has_scope_validation = False
        for callee, args in func_rows:
            callee_lower = callee.lower()
            args_lower = (args or "").lower()

            validation_patterns = [
                "validate",
                "verify",
                "check",
                "compare",
                "includes",
                "contains",
                "every",
                "some",
            ]
            if "scope" in args_lower and any(vp in callee_lower for vp in validation_patterns):
                has_scope_validation = True
                break

        if not has_scope_validation and scope_usages:
            first_usage = scope_usages[0]
            findings.append(
                StandardFinding(
                    rule_name="oauth-scope-not-validated",
                    message="OAuth scope extracted from response without validation. Verify granted scopes match requested scopes to prevent privilege escalation.",
                    file_path=file,
                    line=first_usage[0],
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-269",
                    confidence=Confidence.LOW,
                    snippet=f"{first_usage[1]} = {first_usage[2][:40]}..."
                    if len(first_usage[2]) > 40
                    else f"{first_usage[1]} = {first_usage[2]}",
                )
            )

    return findings
