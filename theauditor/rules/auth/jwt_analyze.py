"""JWT Security Detector - Full-Stack Database-First Approach.

Detects JWT vulnerabilities including:
- Hardcoded secrets (CWE-798)
- Weak secrets and insufficient key length (CWE-326)
- Missing expiration claims (CWE-613)
- Algorithm confusion attacks (CWE-327)
- None algorithm vulnerability (CWE-347)
- Decode without verification (CWE-347)
- Sensitive data in payload (CWE-312)
- Insecure storage in localStorage/sessionStorage (CWE-922)
- JWT exposure in URL parameters (CWE-598)
- Cross-origin transmission concerns (CWE-346)
- JKU header injection (CWE-918) - SSRF via unvalidated key URL
- KID header injection (CWE-89) - SQLi/path traversal via key ID lookup
- Missing jti claim for replay protection (CWE-294)
- Missing audience validation (CWE-287)
- Missing issuer validation (CWE-287)
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="jwt_security",
    category="auth",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["test/", "spec.", ".test.", "__tests__", "demo/", "example/"],
    execution_scope="database",
    primary_table="function_call_args",
)


JWT_SIGN_FUNCTIONS = frozenset(
    [
        "jwt.sign",
        "jsonwebtoken.sign",
        "jose.JWT.sign",
        "jose.sign",
        "JWT.sign",
        "jwt.encode",
        "PyJWT.encode",
        "pyjwt.encode",
        "njwt.create",
        "jws.sign",
    ]
)


JWT_VERIFY_FUNCTIONS = frozenset(
    [
        "jwt.verify",
        "jsonwebtoken.verify",
        "jose.JWT.verify",
        "jose.verify",
        "JWT.verify",
        "jwt.decode",
        "PyJWT.decode",
        "pyjwt.decode",
        "njwt.verify",
        "jws.verify",
    ]
)


JWT_DECODE_FUNCTIONS = frozenset(
    [
        "jwt.decode",
        "jsonwebtoken.decode",
        "jose.JWT.decode",
        "JWT.decode",
        "PyJWT.decode",
        "pyjwt.decode",
    ]
)


JWT_SENSITIVE_FIELDS = frozenset(
    [
        "password",
        "secret",
        "creditCard",
        "ssn",
        "apiKey",
        "privateKey",
        "cvv",
        "creditcard",
        "social_security",
    ]
)


ENV_PATTERNS = frozenset(["process.env", "import.meta.env", "os.environ", "getenv", "config"])


WEAK_ENV_NAMES = frozenset(["TEST", "DEMO", "DEV", "LOCAL"])


STORAGE_FUNCTIONS = frozenset(["localStorage.setItem", "sessionStorage.setItem"])


HTTP_FUNCTIONS = frozenset(
    [
        "fetch",
        "axios",
        "axios.get",
        "axios.post",
        "request",
        "http.get",
        "http.post",
        "https.get",
        "https.post",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect JWT vulnerabilities using database queries with Python-side filtering."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_hardcoded_secrets(db))
        findings.extend(_check_weak_secrets(db))
        findings.extend(_check_missing_expiration(db))
        findings.extend(_check_algorithm_confusion(db))
        findings.extend(_check_none_algorithm(db))
        findings.extend(_check_decode_without_verify(db))
        findings.extend(_check_sensitive_payload(db))
        findings.extend(_check_weak_env_secrets(db))
        findings.extend(_check_insecure_storage(db))
        findings.extend(_check_jwt_in_url(db))
        findings.extend(_check_weak_secret_length(db))
        findings.extend(_check_cross_origin_transmission(db))
        findings.extend(_check_react_state_storage(db))
        findings.extend(_check_jku_injection(db))
        findings.extend(_check_kid_injection(db))
        findings.extend(_check_missing_jti(db))
        findings.extend(_check_missing_audience_validation(db))
        findings.extend(_check_missing_issuer_validation(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _build_jwt_sign_condition() -> str:
    """Build SQL OR condition for JWT sign functions."""
    return " OR ".join([f"callee_function = '{func}'" for func in JWT_SIGN_FUNCTIONS])


def _build_jwt_verify_condition() -> str:
    """Build SQL OR condition for JWT verify functions."""
    return " OR ".join([f"callee_function = '{func}'" for func in JWT_VERIFY_FUNCTIONS])


def _build_jwt_decode_condition() -> str:
    """Build SQL OR condition for JWT decode functions."""
    return " OR ".join([f"callee_function = '{func}'" for func in JWT_DECODE_FUNCTIONS])


def _check_hardcoded_secrets(db: RuleDB) -> list[StandardFinding]:
    """Check for hardcoded JWT secrets in sign calls."""
    findings = []
    jwt_sign_condition = _build_jwt_sign_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr", "argument_index")
        .where(f"({jwt_sign_condition}) AND argument_index IN (1, 2)")
        .order_by("file, line")
    )

    for file, line, func, secret_expr, _arg_idx in rows:
        if not secret_expr:
            continue
        if any(env in secret_expr for env in ENV_PATTERNS):
            continue

        if not (secret_expr.startswith('"') or secret_expr.startswith("'")):
            continue

        secret_clean = secret_expr.strip('"').strip("'").strip("`")
        if secret_clean.lower() in [
            "secret",
            "your-secret",
            "changeme",
            "your_secret_here",
            "placeholder",
        ]:
            continue

        if len(secret_clean) < 8:
            continue

        findings.append(
            StandardFinding(
                rule_name="jwt-hardcoded-secret",
                message="JWT secret is hardcoded in source code",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="cryptography",
                snippet=f"{func}(..., {secret_expr[:50]}, ...)",
                cwe_id="CWE-798",
            )
        )

    return findings


def _check_weak_secrets(db: RuleDB) -> list[StandardFinding]:
    """Check for weak JWT secret variable names."""
    findings = []
    jwt_sign_condition = _build_jwt_sign_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"({jwt_sign_condition}) AND argument_index IN (1, 2)")
        .order_by("file, line")
    )

    for file, line, func, secret_expr in rows:
        if secret_expr.startswith('"') or secret_expr.startswith("'"):
            continue

        secret_lower = secret_expr.lower()
        weak_keywords = ["123", "test", "demo", "example"]

        if any(weak in secret_lower for weak in weak_keywords):
            findings.append(
                StandardFinding(
                    rule_name="jwt-weak-secret",
                    message=f"JWT secret variable appears weak: {secret_expr}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="cryptography",
                    snippet=f"{func}(..., {secret_expr}, ...)",
                    cwe_id="CWE-326",
                )
            )

    return findings


def _check_missing_expiration(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT tokens created without expiration claims."""
    findings = []
    jwt_sign_condition = _build_jwt_sign_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where(f"({jwt_sign_condition}) AND argument_index = 0")
        .order_by("file, line")
    )

    jwt_sign_calls = list(rows)

    for file, line, func in jwt_sign_calls:
        options_rows = db.query(
            Q("function_call_args")
            .select("argument_expr")
            .where(
                "file = ? AND line = ? AND callee_function = ? AND argument_index = 2",
                file,
                line,
                func,
            )
        )

        options_row = options_rows[0] if options_rows else None
        options = options_row[0] if options_row else None

        has_expiration = False
        if options:
            has_expiration = (
                "expiresIn" in options
                or "exp" in options
                or "maxAge" in options
                or "expires_in" in options
            )

        if not has_expiration:
            findings.append(
                StandardFinding(
                    rule_name="jwt-missing-expiration",
                    message="JWT token created without expiration claim",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    snippet=options[:100]
                    if options and len(options) > 100
                    else options or "No options provided",
                    cwe_id="CWE-613",
                )
            )

    return findings


def _check_algorithm_confusion(db: RuleDB) -> list[StandardFinding]:
    """Check for algorithm confusion vulnerabilities.

    Two attack patterns:
    1. Mixed algorithms: Both symmetric (HS*) and asymmetric (RS*/ES*) allowed
    2. Public key as secret: Passing a public key where a symmetric secret is expected,
       tricking the library into using the public key as an HMAC secret
    """
    findings = []
    jwt_verify_condition = _build_jwt_verify_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where(f"({jwt_verify_condition}) AND argument_index = 2")
        .order_by("file, line")
    )

    for file, line, options in rows:
        if not options:
            continue
        if "algorithms" not in options:
            continue

        has_hs = "HS256" in options or "HS384" in options or "HS512" in options
        has_rs = "RS256" in options or "RS384" in options or "RS512" in options
        has_es = "ES256" in options or "ES384" in options or "ES512" in options

        if has_hs and (has_rs or has_es):
            findings.append(
                StandardFinding(
                    rule_name="jwt-algorithm-confusion",
                    message="Algorithm confusion vulnerability: both symmetric and asymmetric algorithms allowed. Attacker can forge tokens by signing with public key as HMAC secret.",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    snippet=options[:200],
                    cwe_id="CWE-327",
                )
            )

    secret_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"({jwt_verify_condition}) AND argument_index = 1")
        .order_by("file, line")
    )

    public_key_patterns = [
        "publickey",
        "public_key",
        "pubkey",
        "pub_key",
        "-----begin public",
        "-----begin rsa public",
        "-----begin certificate",
        ".pem",
        ".pub",
        "getpublickey",
        "get_public_key",
        "publickeypem",
    ]

    for file, line, func, secret_arg in secret_rows:
        secret_lower = secret_arg.lower()

        if any(pat in secret_lower for pat in public_key_patterns):
            findings.append(
                StandardFinding(
                    rule_name="jwt-public-key-as-secret",
                    message="Public key passed to JWT verify as secret. If HS* algorithm is used, attacker can forge tokens using the public key as HMAC secret.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    snippet=f"{func}(token, {secret_arg[:40]}...)"
                    if len(secret_arg) > 40
                    else f"{func}(token, {secret_arg})",
                    cwe_id="CWE-327",
                )
            )

    return findings


def _check_none_algorithm(db: RuleDB) -> list[StandardFinding]:
    """Check for none algorithm vulnerability."""
    findings = []
    jwt_verify_condition = _build_jwt_verify_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where(f"({jwt_verify_condition}) AND argument_index = 2")
        .order_by("file, line")
    )

    for file, line, options in rows:
        if not options:
            continue
        options_lower = options.lower()
        if "none" in options_lower:
            findings.append(
                StandardFinding(
                    rule_name="jwt-none-algorithm",
                    message="JWT none algorithm vulnerability - allows unsigned tokens",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    snippet=options[:100],
                    cwe_id="CWE-347",
                )
            )

    return findings


def _check_decode_without_verify(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT decode usage without verification."""
    findings = []
    jwt_decode_condition = _build_jwt_decode_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where(f"({jwt_decode_condition}) AND argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func in rows:
        findings.append(
            StandardFinding(
                rule_name="jwt-decode-usage",
                message="JWT.decode does not verify signatures - tokens can be forged",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="authentication",
                snippet=f"{func}() call detected",
                cwe_id="CWE-347",
            )
        )

    return findings


def _check_sensitive_payload(db: RuleDB) -> list[StandardFinding]:
    """Check for sensitive data in JWT payloads."""
    findings = []
    jwt_sign_condition = _build_jwt_sign_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where(f"({jwt_sign_condition}) AND argument_index = 0")
        .order_by("file, line")
    )

    for file, line, payload in rows:
        if not payload:
            continue
        payload_lower = payload.lower()
        sensitive_found = []

        for field in JWT_SENSITIVE_FIELDS:
            if field.lower() in payload_lower:
                sensitive_found.append(field)

        if sensitive_found:
            findings.append(
                StandardFinding(
                    rule_name="jwt-sensitive-data",
                    message=f"Sensitive data in JWT payload: {', '.join(sensitive_found[:3])}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="data-exposure",
                    snippet=payload[:100],
                    cwe_id="CWE-312",
                )
            )

    return findings


def _check_weak_env_secrets(db: RuleDB) -> list[StandardFinding]:
    """Check for weak environment variable names for JWT secrets."""
    findings = []
    jwt_sign_condition = _build_jwt_sign_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where(f"({jwt_sign_condition}) AND argument_index IN (1, 2)")
        .order_by("file, line")
    )

    for file, line, env_var in rows:
        if not env_var:
            continue
        if not any(env in env_var for env in ENV_PATTERNS):
            continue

        env_var_upper = env_var.upper()
        if any(weak in env_var_upper for weak in WEAK_ENV_NAMES):
            findings.append(
                StandardFinding(
                    rule_name="jwt-weak-env-secret",
                    message=f"JWT secret uses potentially weak environment variable: {env_var}",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="cryptography",
                    snippet=env_var,
                    cwe_id="CWE-326",
                )
            )

    return findings


def _check_insecure_storage(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT stored in localStorage/sessionStorage."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func, key_expr in rows:
        if not func or not key_expr:
            continue
        if not any(storage in func for storage in STORAGE_FUNCTIONS):
            continue

        key_lower = key_expr.lower()
        jwt_keywords = ["token", "jwt", "auth", "access", "refresh", "bearer"]

        if any(keyword in key_lower for keyword in jwt_keywords):
            findings.append(
                StandardFinding(
                    rule_name="jwt-insecure-storage",
                    message="JWT stored in localStorage/sessionStorage - vulnerable to XSS attacks, use httpOnly cookies instead",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="data-exposure",
                    snippet=f"Storage key: {key_expr}",
                    cwe_id="CWE-922",
                )
            )

    return findings


def _check_jwt_in_url(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT exposed in URL parameters."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target, source in rows:
        if not source:
            continue
        url_patterns = [
            "?token=",
            "&token=",
            "?jwt=",
            "&jwt=",
            "?access_token=",
            "&access_token=",
            "/token/",
        ]

        if any(pattern in source for pattern in url_patterns):
            findings.append(
                StandardFinding(
                    rule_name="jwt-in-url",
                    message="JWT in URL parameters - leaks to browser history, server logs, and referrer headers",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="data-exposure",
                    snippet=f"{target} = {source[:80]}"
                    if len(source) <= 80
                    else f"{target} = {source[:80]}...",
                    cwe_id="CWE-598",
                )
            )

    return findings


def _check_weak_secret_length(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT secrets that are too short for HMAC-SHA256."""
    findings = []
    jwt_sign_condition = _build_jwt_sign_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where(f"({jwt_sign_condition}) AND argument_index IN (1, 2)")
        .order_by("file, line")
    )

    for file, line, secret_expr in rows:
        if not secret_expr:
            continue
        if any(env in secret_expr for env in ENV_PATTERNS):
            continue

        if not (secret_expr.startswith('"') or secret_expr.startswith("'")):
            continue

        secret_clean = secret_expr.strip('"').strip("'")
        secret_length = len(secret_clean)

        if secret_length < 32:
            findings.append(
                StandardFinding(
                    rule_name="jwt-weak-secret-length",
                    message=f"JWT secret is too short ({secret_length} characters) - HMAC-SHA256 requires at least 32 characters for security",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="cryptography",
                    snippet=f"Secret length: {secret_length} chars",
                    cwe_id="CWE-326",
                )
            )

    return findings


def _check_cross_origin_transmission(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT transmitted via Authorization header (CORS concerns)."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func or not args:
            continue
        if not any(http_func in func for http_func in HTTP_FUNCTIONS):
            continue

        if "Authorization" in args and "Bearer" in args:
            findings.append(
                StandardFinding(
                    rule_name="jwt-cross-origin-transmission",
                    message="JWT transmitted with Authorization header - ensure CORS is properly configured to prevent token leaks",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    snippet=f"Request with Bearer token: {args[:80]}"
                    if len(args) <= 80
                    else f"Request with Bearer token: {args[:80]}...",
                    cwe_id="CWE-346",
                )
            )

    return findings


def _check_react_state_storage(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT stored in React state (lost on refresh)."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target, source in rows:
        if not file or not source:
            continue
        if not (file.endswith(".jsx") or file.endswith(".tsx")):
            continue

        if not ("useState" in source or "useContext" in source):
            continue

        jwt_terms = ["token", "jwt", "auth"]
        if any(term in source.lower() for term in jwt_terms):
            findings.append(
                StandardFinding(
                    rule_name="jwt-in-react-state",
                    message="JWT stored in React state - token lost on page refresh, consider httpOnly cookies for persistent auth",
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category="authentication",
                    snippet=f"{target} = {source[:80]}"
                    if len(source) <= 80
                    else f"{target} = {source[:80]}...",
                    cwe_id="CWE-922",
                )
            )

    return findings


def _check_jku_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for unvalidated JKU (JWK Set URL) header processing.

    The jku header claim specifies a URL to fetch the signing key.
    If not validated against a whitelist, attackers can point to their own keys.
    """
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target_var, source_expr in rows:
        if not source_expr:
            continue

        target_lower = target_var.lower()
        source_lower = source_expr.lower()

        jku_patterns = ["jku", "jwk_url", "jwkurl", "jwks_uri", "jwksuri", "x5u"]
        if any(pat in target_lower or pat in source_lower for pat in jku_patterns):
            if "header" in source_lower or "decode" in source_lower:
                findings.append(
                    StandardFinding(
                        rule_name="jwt-jku-header-extraction",
                        message="JKU/x5u header extracted from JWT. Validate URL against whitelist before fetching keys to prevent SSRF attacks.",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="authentication",
                        snippet=f"{target_var} = {source_expr[:60]}..."
                        if len(source_expr) > 60
                        else f"{target_var} = {source_expr}",
                        cwe_id="CWE-918",
                    )
                )

    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in func_rows:
        func_lower = func.lower()
        args_lower = (args or "").lower()

        is_http_call = any(hf in func_lower for hf in ["fetch", "get", "request", "axios"])
        has_jku = any(pat in args_lower for pat in ["jku", "jwks", "jwk", ".well-known"])

        if is_http_call and has_jku:
            findings.append(
                StandardFinding(
                    rule_name="jwt-jku-fetch-unvalidated",
                    message="Fetching JWK/JWKS from URL. Ensure URL is validated against whitelist of trusted issuers.",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    snippet=f"{func}({args[:50]}...)" if len(args) > 50 else f"{func}({args})",
                    cwe_id="CWE-918",
                )
            )

    return findings


def _check_kid_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for KID (Key ID) header used directly in lookups without sanitization.

    The kid header identifies which key to use for verification.
    If used directly in SQL queries or file paths, it enables SQLi or path traversal.
    """
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    kid_files = {}

    for file, line, target_var, source_expr in rows:
        if not source_expr:
            continue

        target_lower = target_var.lower()
        source_lower = source_expr.lower()

        if "kid" in target_lower or ("kid" in source_lower and "header" in source_lower):
            if file not in kid_files:
                kid_files[file] = []
            kid_files[file].append((line, target_var))

    for file, kid_usages in kid_files.items():
        sql_rows = db.query(
            Q("function_call_args")
            .select("line", "callee_function", "argument_expr")
            .where("file = ?", file)
        )

        for sql_line, func, args in sql_rows:
            func_lower = func.lower()
            args_lower = (args or "").lower()

            sql_funcs = ["query", "execute", "raw", "prepare", "findone", "findall"]
            if any(sf in func_lower for sf in sql_funcs):
                for _kid_line, kid_var in kid_usages:
                    if kid_var.lower() in args_lower:
                        findings.append(
                            StandardFinding(
                                rule_name="jwt-kid-sql-injection",
                                message=f"JWT kid header '{kid_var}' used in SQL query. Sanitize or use parameterized queries to prevent SQLi.",
                                file_path=file,
                                line=sql_line,
                                severity=Severity.CRITICAL,
                                category="authentication",
                                snippet=f"{func}(...{kid_var}...)",
                                cwe_id="CWE-89",
                            )
                        )

            fs_funcs = ["readfile", "readfilesync", "open", "path.join", "resolve"]
            if any(ff in func_lower for ff in fs_funcs):
                for _kid_line, kid_var in kid_usages:
                    if kid_var.lower() in args_lower:
                        findings.append(
                            StandardFinding(
                                rule_name="jwt-kid-path-traversal",
                                message=f"JWT kid header '{kid_var}' used in file path. Validate against whitelist to prevent path traversal.",
                                file_path=file,
                                line=sql_line,
                                severity=Severity.HIGH,
                                category="authentication",
                                snippet=f"{func}(...{kid_var}...)",
                                cwe_id="CWE-22",
                            )
                        )

    return findings


def _check_missing_jti(db: RuleDB) -> list[StandardFinding]:
    """Detect JWT tokens created without jti (JWT ID) claim for replay protection.

    Without unique token IDs, captured tokens can be replayed indefinitely until
    expiration. Critical for financial/sensitive operations.
    """
    findings = []
    jwt_sign_condition = _build_jwt_sign_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"({jwt_sign_condition}) AND argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func, payload in rows:
        payload_lower = payload.lower() if payload else ""

        has_jti = "jti" in payload_lower or "jwt_id" in payload_lower or "jwtid" in payload_lower

        if not has_jti:
            findings.append(
                StandardFinding(
                    rule_name="jwt-missing-jti",
                    message="JWT created without jti claim. Add unique token ID for replay protection, especially for sensitive operations.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    snippet=f"{func}({payload[:50]}...)" if len(payload) > 50 else f"{func}({payload})",
                    cwe_id="CWE-294",
                )
            )

    return findings


def _check_missing_audience_validation(db: RuleDB) -> list[StandardFinding]:
    """Detect JWT verification without audience (aud) claim validation.

    Tokens issued for one service can be used on another if audience isn't
    validated. This enables token confusion attacks in multi-service environments.
    """
    findings = []
    jwt_verify_condition = _build_jwt_verify_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"({jwt_verify_condition}) AND argument_index = 2")
        .order_by("file, line")
    )

    for file, line, _func, options in rows:
        if not options:
            continue

        options_lower = options.lower()

        has_audience = (
            "audience" in options_lower
            or "aud" in options_lower
            or "verify_aud" in options_lower
        )

        if not has_audience:
            findings.append(
                StandardFinding(
                    rule_name="jwt-missing-audience-validation",
                    message="JWT verification without audience validation. Add audience option to prevent token confusion attacks.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    snippet=options[:60] if len(options) <= 60 else options[:57] + "...",
                    cwe_id="CWE-287",
                )
            )

    return findings


def _check_missing_issuer_validation(db: RuleDB) -> list[StandardFinding]:
    """Detect JWT verification without issuer (iss) claim validation.

    Tokens from untrusted issuers could be accepted. Multi-tenant systems
    and microservices are especially vulnerable to issuer confusion.
    """
    findings = []
    jwt_verify_condition = _build_jwt_verify_condition()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"({jwt_verify_condition}) AND argument_index = 2")
        .order_by("file, line")
    )

    for file, line, _func, options in rows:
        if not options:
            continue

        options_lower = options.lower()

        has_issuer = (
            "issuer" in options_lower
            or "iss" in options_lower
            or "verify_iss" in options_lower
        )

        if not has_issuer:
            findings.append(
                StandardFinding(
                    rule_name="jwt-missing-issuer-validation",
                    message="JWT verification without issuer validation. Add issuer option to reject tokens from untrusted sources.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    snippet=options[:60] if len(options) <= 60 else options[:57] + "...",
                    cwe_id="CWE-287",
                )
            )

    return findings
