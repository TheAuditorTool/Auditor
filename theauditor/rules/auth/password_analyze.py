"""Password Security Analyzer - Database-First Approach.

Detects password vulnerabilities including:
- Weak hash algorithms (MD5/SHA1) for passwords (CWE-327)
- Hardcoded passwords in source code (CWE-259)
- Weak/default passwords (CWE-521)
- Insufficient password length (NIST 800-63B: 8+ min, 12+ recommended) (CWE-521)
- Password exposure in URL parameters (CWE-598)
- Timing-unsafe password comparisons (CWE-208)
- Passwords in logging statements (CWE-532)
- Bcrypt cost factor too low (CWE-916)
- Insecure password recovery flows (CWE-640)
- Missing credential stuffing protections (CWE-307)
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
    name="password_security",
    category="auth",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["test/", "spec.", ".test.", "__tests__", "demo/", "example/"],
    execution_scope="database",
    primary_table="function_call_args",
)


WEAK_HASH_KEYWORDS = frozenset(["md5", "sha1", "sha", "createhash"])


STRONG_HASH_ALGORITHMS = frozenset(["bcrypt", "scrypt", "argon2", "pbkdf2"])


PASSWORD_KEYWORDS = frozenset(["password", "passwd", "pwd", "passphrase", "pass"])


WEAK_PASSWORDS = frozenset(
    [
        "password",
        "admin",
        "123456",
        "changeme",
        "default",
        "test",
        "demo",
        "sample",
        "password123",
        "admin123",
        "root",
        "toor",
        "secret",
        "qwerty",
        "letmein",
    ]
)


PASSWORD_PLACEHOLDERS = frozenset(
    [
        "your_password_here",
        "your_password",
        "password_here",
        "change_me",
        "changeme",
        "placeholder",
        "<password>",
        "${password}",
        "{{password}}",
    ]
)


ENV_PATTERNS = frozenset(
    ["process.env", "import.meta.env", "os.environ", "getenv", "config", "process.argv"]
)


URL_FUNCTION_KEYWORDS = frozenset(["url", "uri", "query", "querystring"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect password security vulnerabilities."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_weak_password_hashing(db))
        findings.extend(_check_hardcoded_passwords(db))
        findings.extend(_check_weak_complexity(db))
        findings.extend(_check_password_in_url(db))
        findings.extend(_check_timing_unsafe_comparison(db))
        findings.extend(_check_password_logging(db))
        findings.extend(_check_bcrypt_cost(db))
        findings.extend(_check_insecure_recovery(db))
        findings.extend(_check_credential_stuffing_protection(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_weak_password_hashing(db: RuleDB) -> list[StandardFinding]:
    """Detect weak hash algorithms used for passwords."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func:
            continue
        func_lower = func.lower()

        is_weak_hash = any(keyword in func_lower for keyword in WEAK_HASH_KEYWORDS)
        if not is_weak_hash:
            continue

        args_lower = args.lower() if args else ""
        has_password_context = any(keyword in args_lower for keyword in PASSWORD_KEYWORDS)
        if not has_password_context:
            continue

        algo = "MD5" if "md5" in func_lower else "SHA1" if "sha1" in func_lower else "weak hash"

        findings.append(
            StandardFinding(
                rule_name="password-weak-hashing",
                message=f"Weak hash algorithm {algo} used for passwords. Use bcrypt, scrypt, or argon2 instead.",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="authentication",
                cwe_id="CWE-327",
                confidence=Confidence.HIGH,
                snippet=f"{func}({args[:40]})" if len(args) <= 40 else f"{func}({args[:40]}...)",
            )
        )

    createhash_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in createhash_rows:
        if not func or "createhash" not in func.lower():
            continue

        args_lower = args.lower()
        is_weak = "md5" in args_lower or "sha1" in args_lower
        if not is_weak:
            continue

        algo = "MD5" if "md5" in args_lower else "SHA1"

        nearby_rows = db.query(
            Q("assignments").select("target_var", "source_expr", "line").where("file = ?", file)
        )

        nearby_password = False
        for target, source, assign_line in nearby_rows:
            if abs(assign_line - line) > 5:
                continue

            target_lower = (target or "").lower()
            source_lower = (source or "").lower()

            if any(kw in target_lower or kw in source_lower for kw in PASSWORD_KEYWORDS):
                nearby_password = True
                break

        if nearby_password:
            findings.append(
                StandardFinding(
                    rule_name="password-weak-hashing-createhash",
                    message=f'crypto.createHash("{algo.lower()}") used in password context. Use bcrypt, scrypt, or argon2 instead.',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    cwe_id="CWE-327",
                    confidence=Confidence.HIGH,
                    snippet=f'{func}("{algo.lower()}")',
                )
            )

    return findings


def _check_hardcoded_passwords(db: RuleDB) -> list[StandardFinding]:
    """Detect hardcoded passwords in source code."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var, expr in rows:
        if not var:
            continue
        var_lower = var.lower()
        has_password_keyword = any(keyword in var_lower for keyword in PASSWORD_KEYWORDS)
        if not has_password_keyword:
            continue

        if any(env in expr for env in ENV_PATTERNS):
            continue

        expr_clean = expr.strip().strip("'\"")

        if expr_clean.lower() in PASSWORD_PLACEHOLDERS:
            continue

        if not expr_clean or expr_clean in ("", '""', "''"):
            continue

        is_literal = (
            expr.strip().startswith('"')
            or expr.strip().startswith("'")
            or expr.strip().startswith('b"')
            or expr.strip().startswith("b'")
        )

        if is_literal and len(expr_clean) > 0:
            if expr_clean.lower() in WEAK_PASSWORDS:
                findings.append(
                    StandardFinding(
                        rule_name="password-weak-default",
                        message=f'Weak/default password "{expr_clean}" in variable "{var}". Use strong, randomly generated passwords.',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="authentication",
                        cwe_id="CWE-521",
                        confidence=Confidence.HIGH,
                        snippet=f'{var} = "{expr_clean}"',
                    )
                )

            elif len(expr_clean) >= 6:
                findings.append(
                    StandardFinding(
                        rule_name="password-hardcoded",
                        message=f'Hardcoded password in variable "{var}". Store in environment variables or secure secret management.',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="authentication",
                        cwe_id="CWE-259",
                        confidence=Confidence.HIGH,
                        snippet=f'{var} = "***REDACTED***"',
                    )
                )

    return findings


def _check_weak_complexity(db: RuleDB) -> list[StandardFinding]:
    """Detect lack of password complexity enforcement."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "caller_function", "argument_expr", "callee_function")
        .order_by("file, line")
    )

    for file, line, _caller, args, callee in rows:
        if not callee:
            continue
        args_lower = (args or "").lower()

        has_password = any(kw in args_lower for kw in PASSWORD_KEYWORDS)
        if not has_password:
            continue

        callee_lower = callee.lower()
        is_validation = any(
            kw in callee_lower for kw in ["validate", "check", "verify", "test", "length"]
        )
        if not is_validation:
            continue

        if ".length" in args_lower:
            weak_comparisons = ["> 4", "> 5", "> 6", "> 7", ">= 4", ">= 5", ">= 6", ">= 7"]
            if any(weak in args_lower for weak in weak_comparisons):
                findings.append(
                    StandardFinding(
                        rule_name="password-weak-length-requirement",
                        message="Weak password length requirement. NIST 800-63B: minimum 8 characters, recommend 12+. Avoid composition rules; use breached password checks instead.",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="authentication",
                        cwe_id="CWE-521",
                        confidence=Confidence.MEDIUM,
                        snippet=args[:60] if len(args) <= 60 else args[:60] + "...",
                    )
                )

    assign_rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, _var, expr in assign_rows:
        expr_lower = expr.lower()

        has_password_length = any(
            f"{kw}.length" in expr_lower for kw in ["password", "pwd", "passwd"]
        )
        if not has_password_length:
            continue

        weak_patterns = ["> 6", "> 7", ">= 6", ">= 7"]
        if any(pattern in expr_lower for pattern in weak_patterns):
            findings.append(
                StandardFinding(
                    rule_name="password-weak-validation",
                    message="Password length requirement too weak. NIST 800-63B: minimum 8 characters, recommend 12+. Check against breached password lists (zxcvbn, HaveIBeenPwned) instead of composition rules.",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-521",
                    confidence=Confidence.MEDIUM,
                    snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
                )
            )

    return findings


def _check_password_in_url(db: RuleDB) -> list[StandardFinding]:
    """Detect passwords in GET request parameters."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    url_param_patterns = ["?password=", "&password=", "?passwd=", "&passwd=", "?pwd=", "&pwd="]

    for file, line, _var, expr in rows:
        if not expr:
            continue
        if any(pattern in expr for pattern in url_param_patterns):
            findings.append(
                StandardFinding(
                    rule_name="password-in-url",
                    message="Password transmitted in URL query parameter. Use POST with password in request body.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.HIGH,
                    snippet=expr[:60] if len(expr) <= 60 else expr[:60] + "...",
                )
            )

    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in func_rows:
        if not func:
            continue
        func_lower = func.lower()

        is_url_function = any(kw in func_lower for kw in URL_FUNCTION_KEYWORDS)
        if not is_url_function:
            continue

        if not args:
            continue
        args_lower = args.lower()

        has_password = any(kw in args_lower for kw in PASSWORD_KEYWORDS)
        has_query_params = "?" in args or "&" in args

        if has_password and has_query_params:
            findings.append(
                StandardFinding(
                    rule_name="password-in-url-construction",
                    message=f"Password used in URL construction via {func}. Never include passwords in URLs.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-598",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(...password...)",
                )
            )

    return findings


def _check_timing_unsafe_comparison(db: RuleDB) -> list[StandardFinding]:
    """Detect timing-unsafe password/hash comparisons.

    Direct string comparison (== or !=) on passwords/hashes leaks timing information,
    enabling attackers to guess passwords character-by-character.
    Use crypto.timingSafeEqual (Node) or secrets.compare_digest (Python) instead.
    """
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    sensitive_vars = frozenset(
        [
            "password",
            "passwd",
            "pwd",
            "hash",
            "hashed",
            "digest",
            "storedpassword",
            "storedhash",
            "dbpassword",
            "dbhash",
            "inputpassword",
            "inputhash",
            "userhash",
            "userpassword",
        ]
    )

    for file, line, target_var, source_expr in rows:
        if not source_expr:
            continue

        expr_lower = source_expr.lower()
        target_lower = target_var.lower()

        has_comparison = " == " in source_expr or " === " in source_expr or " != " in source_expr
        if not has_comparison:
            continue

        has_sensitive = any(sv in expr_lower for sv in sensitive_vars)
        if not has_sensitive:
            continue

        safe_functions = ["timingsafeequal", "compare_digest", "constanttimeequal", "safeeq"]
        if any(sf in expr_lower for sf in safe_functions):
            continue

        if target_lower in ("result", "success", "valid", "ok", "match", "isvalid", "ismatch"):
            findings.append(
                StandardFinding(
                    rule_name="password-timing-unsafe-comparison",
                    message="Direct string comparison on password/hash leaks timing info. Use crypto.timingSafeEqual (Node) or secrets.compare_digest (Python).",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-208",
                    confidence=Confidence.MEDIUM,
                    snippet=source_expr[:60]
                    if len(source_expr) <= 60
                    else source_expr[:57] + "...",
                )
            )

    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in func_rows:
        if not func:
            continue
        func_lower = func.lower()
        args_lower = (args or "").lower()

        comparison_funcs = ["compare", "equals", "match", "verify"]
        is_comparison_func = any(cf in func_lower for cf in comparison_funcs)

        if not is_comparison_func:
            continue

        has_password_arg = any(kw in args_lower for kw in PASSWORD_KEYWORDS)
        has_hash_arg = "hash" in args_lower or "digest" in args_lower

        if not (has_password_arg or has_hash_arg):
            continue

        safe_functions = [
            "timingsafeequal",
            "compare_digest",
            "bcrypt.compare",
            "argon2.verify",
            "scrypt.verify",
        ]
        if any(sf in func_lower for sf in safe_functions):
            continue

        if ".compare(" in func_lower or ".equals(" in func_lower:
            findings.append(
                StandardFinding(
                    rule_name="password-timing-unsafe-method",
                    message=f"Method {func} may not be timing-safe for password comparison. Use dedicated timing-safe comparison functions.",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-208",
                    confidence=Confidence.LOW,
                    snippet=f"{func}({args[:30]}...)" if len(args) > 30 else f"{func}({args})",
                )
            )

    return findings


def _check_password_logging(db: RuleDB) -> list[StandardFinding]:
    """Detect passwords being passed to logging functions.

    Passwords in logs are exposed to anyone with log access, stored in plain text,
    and may be retained indefinitely. CWE-532.
    """
    findings = []

    logging_functions = frozenset([
        "console.log",
        "console.info",
        "console.warn",
        "console.error",
        "console.debug",
        "logger.info",
        "logger.debug",
        "logger.warn",
        "logger.error",
        "logging.info",
        "logging.debug",
        "logging.warning",
        "logging.error",
        "log.info",
        "log.debug",
        "log.warn",
        "log.error",
        "print",
        "printf",
        "fmt.print",
        "fmt.println",
    ])

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func:
            continue
        func_lower = func.lower()

        is_logging = any(lf in func_lower for lf in logging_functions)
        if not is_logging:
            continue

        args_lower = (args or "").lower()

        has_password = any(kw in args_lower for kw in PASSWORD_KEYWORDS)
        if not has_password:
            continue

        # Skip if it's clearly a label/message, not a variable
        skip_patterns = ["password:", "password =", "password is", "password must"]
        if any(sp in args_lower for sp in skip_patterns):
            continue

        findings.append(
            StandardFinding(
                rule_name="password-in-logs",
                message="Password variable passed to logging function. Never log credentials - they persist in logs indefinitely.",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="data-exposure",
                cwe_id="CWE-532",
                confidence=Confidence.MEDIUM,
                snippet=f"{func}(...password...)",
            )
        )

    return findings


def _check_bcrypt_cost(db: RuleDB) -> list[StandardFinding]:
    """Detect bcrypt usage with cost factor below 12.

    Cost factor 10 (default) is now too fast with modern GPUs.
    OWASP recommends 12+ for bcrypt. CWE-916.
    """
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr", "argument_index")
        .order_by("file, line")
    )

    bcrypt_functions = frozenset([
        "bcrypt.hash",
        "bcrypt.hashsync",
        "bcrypt.gensalt",
        "bcrypt.gensaltsync",
    ])

    for file, line, func, args, arg_idx in rows:
        if not func:
            continue
        func_lower = func.lower()

        is_bcrypt = any(bf in func_lower for bf in bcrypt_functions)
        if not is_bcrypt:
            continue

        # For bcrypt.hash/hashSync, rounds is typically arg index 1
        # For bcrypt.genSalt, rounds is arg index 0
        if "gensalt" in func_lower:
            if arg_idx != 0:
                continue
        else:
            if arg_idx != 1:
                continue

        # Check if rounds/cost is a number less than 12
        args_clean = args.strip()
        try:
            rounds = int(args_clean)
            if rounds < 12:
                findings.append(
                    StandardFinding(
                        rule_name="bcrypt-low-cost",
                        message=f"Bcrypt cost factor {rounds} is too low. OWASP recommends 12+ for adequate GPU resistance.",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="cryptography",
                        cwe_id="CWE-916",
                        confidence=Confidence.HIGH,
                        snippet=f"{func}(..., {rounds})",
                    )
                )
        except ValueError:
            # Not a literal number, could be a variable - skip
            pass

    # Also check for assignment patterns like saltRounds = 10
    assign_rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target_var, source_expr in assign_rows:
        if not target_var:
            continue
        target_lower = target_var.lower()

        salt_keywords = ["saltrounds", "salt_rounds", "bcryptrounds", "bcrypt_rounds", "cost"]
        if not any(kw in target_lower for kw in salt_keywords):
            continue

        try:
            rounds = int(source_expr.strip())
            if rounds < 12:
                findings.append(
                    StandardFinding(
                        rule_name="bcrypt-low-cost-config",
                        message=f"Bcrypt rounds configured to {rounds}. Increase to 12+ for adequate protection against GPU attacks.",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="cryptography",
                        cwe_id="CWE-916",
                        confidence=Confidence.HIGH,
                        snippet=f"{target_var} = {rounds}",
                    )
                )
        except ValueError:
            pass

    return findings


def _check_insecure_recovery(db: RuleDB) -> list[StandardFinding]:
    """Detect insecure password recovery implementations.

    Checks for:
    - Security questions (easily guessed/researched)
    - Password hints (leak information)
    - Reset tokens without expiration
    - Weak reset token generation
    """
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    security_question_patterns = frozenset([
        "securityquestion",
        "security_question",
        "secretquestion",
        "secret_question",
        "mothersmaiden",
        "mothers_maiden",
        "firstpet",
        "first_pet",
        "childhoodfriend",
    ])

    password_hint_patterns = frozenset([
        "passwordhint",
        "password_hint",
        "passhint",
        "pass_hint",
        "pwdhint",
    ])

    for file, line, target_var, source_expr in rows:
        if not target_var:
            continue
        target_lower = target_var.lower()
        source_lower = (source_expr or "").lower()

        # Check for security questions
        if any(sq in target_lower or sq in source_lower for sq in security_question_patterns):
            findings.append(
                StandardFinding(
                    rule_name="password-security-questions",
                    message="Security questions are insecure - answers are often publicly available or easily guessed. Use email/SMS verification or TOTP instead.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-640",
                    confidence=Confidence.HIGH,
                    snippet=f"{target_var} = ...",
                )
            )

        # Check for password hints
        if any(ph in target_lower for ph in password_hint_patterns):
            findings.append(
                StandardFinding(
                    rule_name="password-hint-storage",
                    message="Password hints leak information about the password. Remove password hint functionality entirely.",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="authentication",
                    cwe_id="CWE-640",
                    confidence=Confidence.HIGH,
                    snippet=f"{target_var} = ...",
                )
            )

    # Check for reset token generation patterns
    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    weak_token_patterns = frozenset([
        "math.random",
        "random.random",
        "random.randint",
        "date.now",
        "timestamp",
        "uuid.v1",
    ])

    for file, line, func, args in func_rows:
        if not func:
            continue
        func_lower = func.lower()
        args_lower = (args or "").lower()

        # Look for reset token context
        reset_context = "reset" in func_lower or "reset" in args_lower or "token" in func_lower

        if reset_context:
            if any(weak in func_lower or weak in args_lower for weak in weak_token_patterns):
                findings.append(
                    StandardFinding(
                        rule_name="password-reset-weak-token",
                        message="Password reset token uses weak randomness. Use crypto.randomBytes (128+ bits) with URL-safe encoding.",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="authentication",
                        cwe_id="CWE-640",
                        confidence=Confidence.MEDIUM,
                        snippet=f"{func}(...)",
                    )
                )

    return findings


def _check_credential_stuffing_protection(db: RuleDB) -> list[StandardFinding]:
    """Detect missing credential stuffing protections on login endpoints.

    Checks for:
    - Rate limiting middleware
    - Account lockout after failed attempts
    - CAPTCHA integration
    """
    findings = []

    # Find login/auth endpoints
    endpoint_rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "method", "pattern")
        .where("method = 'POST'")
        .order_by("file")
    )

    login_patterns = ["login", "signin", "sign-in", "authenticate", "auth"]

    login_endpoints = []
    for file, line, _method, pattern in endpoint_rows:
        if not pattern:
            continue
        pattern_lower = pattern.lower()
        if any(lp in pattern_lower for lp in login_patterns):
            login_endpoints.append((file, line, pattern))

    for file, line, pattern in login_endpoints:
        # Check for rate limiting in the same file
        func_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("file = ?", file)
            .limit(200)
        )

        has_rate_limit = False
        has_lockout = False
        has_captcha = False

        rate_limit_patterns = ["ratelimit", "rate_limit", "throttle", "limiter", "slowdown"]
        lockout_patterns = ["lockout", "lock_out", "failedattempts", "failed_attempts", "maxattempts"]
        captcha_patterns = ["captcha", "recaptcha", "hcaptcha", "turnstile"]

        for callee, args in func_rows:
            callee_lower = callee.lower()
            args_lower = (args or "").lower()

            if any(rl in callee_lower or rl in args_lower for rl in rate_limit_patterns):
                has_rate_limit = True
            if any(lo in callee_lower or lo in args_lower for lo in lockout_patterns):
                has_lockout = True
            if any(cp in callee_lower or cp in args_lower for cp in captcha_patterns):
                has_captcha = True

        # Also check assignments for middleware/config
        assign_rows = db.query(
            Q("assignments")
            .select("target_var", "source_expr")
            .where("file = ?", file)
            .limit(200)
        )

        for target_var, source_expr in assign_rows:
            target_lower = target_var.lower()
            source_lower = (source_expr or "").lower()

            if any(rl in target_lower or rl in source_lower for rl in rate_limit_patterns):
                has_rate_limit = True
            if any(lo in target_lower or lo in source_lower for lo in lockout_patterns):
                has_lockout = True
            if any(cp in target_lower or cp in source_lower for cp in captcha_patterns):
                has_captcha = True

        if not has_rate_limit and not has_lockout and not has_captcha:
            findings.append(
                StandardFinding(
                    rule_name="login-no-brute-force-protection",
                    message=f"Login endpoint {pattern} lacks brute-force protection. Add rate limiting, account lockout, or CAPTCHA.",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="authentication",
                    cwe_id="CWE-307",
                    confidence=Confidence.LOW,
                    snippet=f"POST {pattern}",
                )
            )

    return findings
