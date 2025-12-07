"""Rate Limit Analyzer.

Detects rate limiting misconfigurations and missing protections:
- Middleware ordering issues (auth before rate limit)
- Critical endpoints without rate limiting
- Bypassable rate limit keys (spoofable headers)
- Memory-based storage in distributed environments
- Expensive operations before rate limiting

CWE-770: Allocation of Resources Without Limits or Throttling
CWE-307: Improper Restriction of Excessive Authentication Attempts
CWE-290: Authentication Bypass by Spoofing
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
    name="rate_limiting",
    category="security",
    target_extensions=[".py", ".js", ".ts"],
    exclude_patterns=["test/", "spec.", "__tests__"],
    execution_scope="database",
    primary_table="function_call_args",
)


AUTH_PATTERNS = frozenset(
    [
        "authenticate",
        "auth",
        "requireauth",
        "isAuthenticated",
        "passport.authenticate",
        "jwt.verify",
        "verifytoken",
        "ensureAuthenticated",
        "requireLogin",
        "checkAuth",
        "login_required",
        "@auth",
        "@authenticated",
        "authorize",
        "checktoken",
        "validatetoken",
        "session.check",
        "user.validate",
        "identity.verify",
    ]
)


RATE_LIMIT_PATTERNS = frozenset(
    [
        "express-rate-limit",
        "ratelimit",
        "rate-limit",
        "express-slow-down",
        "slowdown",
        "slow-down",
        "express-brute",
        "expressbrute",
        "brute",
        "rate-limiter-flexible",
        "rateLimiterMemory",
        "rateLimiterRedis",
        "@limit",
        "@ratelimit",
        "@throttle",
        "limiter",
        "flask-limiter",
        "django-ratelimit",
        "throttle",
        "api-rate-limit",
        "koa-ratelimit",
        "fastify-rate-limit",
    ]
)


EXPENSIVE_OPERATIONS = frozenset(
    [
        "bcrypt",
        "scrypt",
        "argon2",
        "pbkdf2",
        "hash",
        "compare",
        "crypto.scrypt",
        "crypto.pbkdf2",
        "hashPassword",
        "verifyPassword",
        "database",
        "query",
        "findone",
        "findall",
        "select",
        "execute",
        "mongoose.find",
        "sequelize.query",
        "prisma.find",
        "sendEmail",
        "sendMail",
        "mailer.send",
        "nodemailer",
        "fetch",
        "axios",
        "request",
        "http.get",
        "got",
        "superagent",
        "s3.upload",
        "s3.getObject",
        "cloudinary.upload",
        "stripe.charge",
        "paypal.payment",
        "twilio.send",
    ]
)


CRITICAL_ENDPOINTS = frozenset(
    [
        "/login",
        "/signin",
        "/auth",
        "/authenticate",
        "/register",
        "/signup",
        "/create-account",
        "/join",
        "/reset-password",
        "/forgot-password",
        "/password-reset",
        "/verify",
        "/confirm",
        "/validate",
        "/activate",
        "/api/auth",
        "/api/login",
        "/api/register",
        "/token",
        "/oauth",
        "/oauth2",
        "/2fa",
        "/mfa",
        "/payment",
        "/checkout",
        "/subscribe",
        "/purchase",
        "/admin",
        "/api-key",
        "/webhook",
        "/graphql",
    ]
)


SPOOFABLE_HEADERS = frozenset(
    [
        "x-forwarded-for",
        "x-real-ip",
        "cf-connecting-ip",
        "x-client-ip",
        "x-originating-ip",
        "x-remote-ip",
        "x-forwarded-host",
        "x-original-ip",
        "true-client-ip",
        "x-cluster-client-ip",
        "x-forwarded",
        "forwarded-for",
        "client-ip",
        "real-ip",
        "x-proxyuser-ip",
    ]
)


MEMORY_STORAGE_PATTERNS = frozenset(
    [
        "memorystore",
        "memory",
        "inmemory",
        "localstore",
        "rateLimiterMemory",
        "new memory",
        "store: memory",
        "storage: memory",
        "cache: memory",
        "local",
        "memoryadapter",
        "memcache",
        "inmemorycache",
    ]
)


PERSISTENT_STORAGE_PATTERNS = frozenset(
    [
        "redis",
        "mongodb",
        "postgres",
        "mysql",
        "dynamodb",
        "rateLimiterRedis",
        "redisStore",
        "mongoStore",
        "storage_uri",
        "database_url",
        "redis://",
        "mongodb://",
        "elasticache",
        "memcached",
        "hazelcast",
    ]
)


BYPASS_TECHNIQUES = frozenset(
    [
        "proxy",
        "tor",
        "vpn",
        "rotate",
        "spoof",
        "bypass",
        "override",
        "whitelist",
        "skip",
        "disable",
        "ignore",
        "exclude",
        "exempt",
    ]
)


FRAMEWORK_PATTERNS = frozenset(
    [
        "express",
        "fastify",
        "koa",
        "hapi",
        "restify",
        "flask",
        "django",
        "fastapi",
        "bottle",
        "rails",
        "sinatra",
        "spring",
        "laravel",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect rate limiting misconfigurations.

    Checks for:
    1. Middleware ordering (auth before rate limit = DoS)
    2. Critical endpoints without rate limiting
    3. Bypassable keys using spoofable headers
    4. Memory storage in distributed environments
    5. Expensive operations before rate limiting
    6. Weak rate limit values on auth endpoints

    Returns RuleResult with findings and fidelity manifest.
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        findings.extend(_detect_middleware_ordering(db))
        findings.extend(_detect_unprotected_endpoints(db))
        findings.extend(_detect_bypassable_keys(db))
        findings.extend(_detect_memory_storage(db))
        findings.extend(_detect_expensive_operations(db))
        findings.extend(_detect_api_rate_limits(db))
        findings.extend(_detect_decorator_ordering(db))
        findings.extend(_detect_bypass_configs(db))
        findings.extend(_detect_missing_user_limits(db))
        findings.extend(_detect_weak_rate_limits(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _determine_confidence(
    pattern_type: str,
    has_context: bool = True,
    is_critical: bool = False,
    has_fallback: bool = True,
) -> Confidence:
    """Determine confidence level based on detection context."""
    if is_critical and not has_fallback:
        return Confidence.HIGH
    elif pattern_type in ["middleware_order", "critical_endpoint"]:
        return Confidence.HIGH if has_context else Confidence.MEDIUM
    elif pattern_type in ["bypassable_key", "memory_storage"]:
        return Confidence.HIGH
    elif pattern_type == "expensive_operation":
        return Confidence.MEDIUM
    else:
        return Confidence.LOW


def _detect_framework(file_path: str) -> str:
    """Detect the framework based on file path and patterns."""
    file_lower = file_path.lower()

    if ".js" in file_lower or ".ts" in file_lower:
        if "express" in file_lower:
            return "Express.js"
        elif "fastify" in file_lower:
            return "Fastify"
        elif "koa" in file_lower:
            return "Koa"
        return "Node.js"
    elif ".py" in file_lower:
        if "flask" in file_lower:
            return "Flask"
        elif "django" in file_lower:
            return "Django"
        elif "fastapi" in file_lower:
            return "FastAPI"
        return "Python"
    return "Unknown"


def _get_attack_scenario(rule_name: str) -> str:
    """Generate attack scenario descriptions."""

    scenarios = {
        "rate-limit-after-auth": "Attacker can trigger expensive auth operations (DB queries, bcrypt) repeatedly, causing DoS",
        "missing-rate-limit": "Attacker can brute-force passwords, enumerate users, or trigger password resets without limits",
        "bypassable-key": "Attacker spoofs X-Forwarded-For header to bypass rate limits using different IPs",
        "memory-storage": "Rate limits reset on server restart or are not shared across instances",
        "expensive-before-limit": "Attacker triggers resource-intensive operations before being rate limited",
    }

    return scenarios.get(rule_name, "Attacker can abuse unprotected functionality")


def _detect_middleware_ordering(db: RuleDB) -> list[StandardFinding]:
    """Detect incorrect middleware ordering (auth before rate limit)."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    file_middleware = {}
    for file, line, func, args in rows:
        func_lower = func.lower()
        if not ("use" in func_lower or "middleware" in func_lower):
            continue

        if file not in file_middleware:
            file_middleware[file] = []

        if not args:
            continue

        args_lower = args.lower()

        mw_type = None
        if any(pattern in args_lower for pattern in RATE_LIMIT_PATTERNS):
            mw_type = "rate_limit"
        elif any(pattern in args_lower for pattern in AUTH_PATTERNS):
            mw_type = "auth"
        elif any(pattern in args_lower for pattern in EXPENSIVE_OPERATIONS):
            mw_type = "expensive"

        if mw_type:
            file_middleware[file].append(
                {"line": line, "type": mw_type, "func": func, "args": args[:100]}
            )

    for file, middlewares in file_middleware.items():
        middlewares.sort(key=lambda x: x["line"])

        rate_limit_pos = -1
        auth_positions = []
        expensive_positions = []

        for i, mw in enumerate(middlewares):
            if mw["type"] == "rate_limit":
                rate_limit_pos = i
            elif mw["type"] == "auth":
                auth_positions.append((i, mw))
            elif mw["type"] == "expensive":
                expensive_positions.append((i, mw))

        if rate_limit_pos > -1:
            for auth_pos, auth_mw in auth_positions:
                if auth_pos < rate_limit_pos:
                    framework = _detect_framework(file)

                    findings.append(
                        StandardFinding(
                            rule_name="rate-limit-after-auth",
                            message="Authentication middleware executes before rate limiting",
                            file_path=file,
                            line=auth_mw["line"],
                            severity=Severity.HIGH,
                            confidence=_determine_confidence("middleware_order", True, True, False),
                            category="security",
                            snippet=f"{auth_mw['func']}({auth_mw['args']})",
                            cwe_id="CWE-770",
                            additional_info={
                                "framework": framework,
                                "attack_scenario": _get_attack_scenario("rate-limit-after-auth"),
                                "regulations": ["OWASP A6:2021", "PCI-DSS 8.1.8"],
                                "middleware_type": "authentication",
                                "position": f"Line {auth_mw['line']} before rate limiter",
                            },
                        )
                    )

            for exp_pos, exp_mw in expensive_positions:
                if exp_pos < rate_limit_pos:
                    findings.append(
                        StandardFinding(
                            rule_name="expensive-before-limit",
                            message="Expensive operation executes before rate limiting",
                            file_path=file,
                            line=exp_mw["line"],
                            severity=Severity.HIGH,
                            confidence=_determine_confidence(
                                "expensive_operation", True, False, False
                            ),
                            category="security",
                            snippet=f"{exp_mw['func']}({exp_mw['args']})",
                            cwe_id="CWE-770",
                            additional_info={
                                "operation_type": exp_mw["type"],
                                "attack_scenario": _get_attack_scenario("expensive-before-limit"),
                            },
                        )
                    )

    return findings


def _detect_unprotected_endpoints(db: RuleDB) -> list[StandardFinding]:
    """Detect critical endpoints without rate limiting."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        func_lower = func.lower()
        if not ("post" in func_lower or "get" in func_lower or "route" in func_lower):
            continue

        args_lower = args.lower()
        endpoint_found = None
        for endpoint in CRITICAL_ENDPOINTS:
            if endpoint in args_lower:
                endpoint_found = endpoint
                break

        if endpoint_found:
            nearby_rows = db.query(
                Q("function_call_args")
                .select("callee_function", "line", "argument_expr")
                .where("file = ?", file)
                .where("callee_function IS NOT NULL")
            )

            nearby_rate_limits = []
            for nearby_func, nearby_line, nearby_args in nearby_rows:
                if abs(nearby_line - line) > 30:
                    continue
                func_lower = nearby_func.lower()
                args_lower = (nearby_args or "").lower()
                if (
                    "limit" in func_lower
                    or "throttle" in func_lower
                    or "limit" in args_lower
                    or "throttle" in args_lower
                ):
                    nearby_rate_limits.append((nearby_func, nearby_line))

            has_rate_limit = len(nearby_rate_limits) > 0

            if not has_rate_limit:
                dec_rows = db.query(
                    Q("symbols")
                    .select("name", "line")
                    .where("path = ?", file)
                    .where("type = ?", "decorator")
                    .where("name IS NOT NULL")
                )

                for dec_name, dec_line in dec_rows:
                    if abs(dec_line - line) > 10:
                        continue
                    dec_name_lower = dec_name.lower()
                    if "limit" in dec_name_lower or "throttle" in dec_name_lower:
                        has_rate_limit = True
                        break

            if not has_rate_limit:
                framework = _detect_framework(file)

                findings.append(
                    StandardFinding(
                        rule_name="missing-rate-limit",
                        message=f"Critical endpoint {endpoint_found} lacks rate limiting",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=_determine_confidence("critical_endpoint", True, True, False),
                        category="security",
                        snippet=f'{func}("{endpoint_found}")',
                        cwe_id="CWE-307",
                        additional_info={
                            "endpoint": endpoint_found,
                            "framework": framework,
                            "attack_scenario": _get_attack_scenario("missing-rate-limit"),
                            "regulations": ["OWASP A7:2021", "PCI-DSS 8.1.6", "NIST 800-63B"],
                            "risk": "Brute force, credential stuffing, user enumeration",
                        },
                    )
                )

    return findings


def _detect_bypassable_keys(db: RuleDB) -> list[StandardFinding]:
    """Detect rate limiters using spoofable headers for keys."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        func_lower = func.lower()
        if not ("ratelimit" in func_lower or "limiter" in func_lower):
            continue

        args_lower = args.lower()
        if not ("keygenerator" in args_lower or "key_func" in args_lower or "getkey" in args_lower):
            continue

        uses_spoofable = False
        spoofable_found = None
        for header in SPOOFABLE_HEADERS:
            if header in args_lower:
                uses_spoofable = True
                spoofable_found = header
                break

        if uses_spoofable:
            has_fallback = any(
                fallback in args for fallback in ["||", "??", "req.ip", "req.connection"]
            )

            if not has_fallback:
                framework = _detect_framework(file)

                findings.append(
                    StandardFinding(
                        rule_name="bypassable-key",
                        message=f"Rate limiter uses spoofable header ({spoofable_found}) without fallback",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet=f"keyGenerator uses {spoofable_found}",
                        cwe_id="CWE-290",
                        additional_info={
                            "spoofable_header": spoofable_found,
                            "framework": framework,
                            "attack_scenario": _get_attack_scenario("bypassable-key"),
                            "regulations": ["OWASP A7:2021"],
                            "bypass_technique": f"Spoof {spoofable_found} header with different values",
                        },
                    )
                )

    assign_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
        .where("target_var IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, var, expr in assign_rows:
        expr_lower = expr.lower()
        if "headers" not in expr_lower:
            continue

        has_spoofable = any(header in expr_lower for header in SPOOFABLE_HEADERS)
        if not has_spoofable:
            continue

        var_lower = var.lower()
        if not ("ip" in var_lower or "key" in var_lower or "client" in var_lower):
            continue

        nearby_calls = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("file = ?", file)
            .where("line > ?", line)
            .where("line <= ?", line + 50)
            .where("argument_expr IS NOT NULL")
            .where("callee_function IS NOT NULL")
            .limit(1)
        )

        var_used_in_rate_limit = False
        for nearby_func, nearby_args in nearby_calls:
            if var not in nearby_args:
                continue
            func_lower = nearby_func.lower()
            if "limit" in func_lower or "throttle" in func_lower:
                var_used_in_rate_limit = True
                break

        if var_used_in_rate_limit:
            findings.append(
                StandardFinding(
                    rule_name="bypassable-key-indirect",
                    message="Rate limiting key derived from spoofable header",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category="security",
                    snippet=f"{var} = {expr[:100]}",
                    cwe_id="CWE-290",
                    additional_info={
                        "variable": var,
                        "note": "This variable appears to be used for rate limiting",
                    },
                )
            )

    return findings


def _detect_memory_storage(db: RuleDB) -> list[StandardFinding]:
    """Detect rate limiters using non-persistent storage."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        func_lower = func.lower()
        if not ("ratelimit" in func_lower or "limiter" in func_lower):
            continue

        args_lower = args.lower()
        has_memory = any(pattern in args_lower for pattern in MEMORY_STORAGE_PATTERNS)
        if not has_memory:
            continue

        has_persistent = any(pattern in args_lower for pattern in PERSISTENT_STORAGE_PATTERNS)

        if not has_persistent:
            framework = _detect_framework(file)

            findings.append(
                StandardFinding(
                    rule_name="memory-storage",
                    message="Rate limiter using in-memory storage - ineffective in distributed environment",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet=f"{func}({{store: MemoryStore}})",
                    cwe_id="CWE-770",
                    additional_info={
                        "framework": framework,
                        "attack_scenario": _get_attack_scenario("memory-storage"),
                        "impact": "Rate limits reset on restart, not shared across instances",
                        "environments_affected": ["Kubernetes", "Serverless", "Load-balanced"],
                    },
                )
            )

    flask_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function = ?", "Limiter")
    )

    for file, line, _func, args in flask_rows:
        if args and "storage_uri" in args.lower():
            continue

        findings.append(
            StandardFinding(
                rule_name="flask-memory-storage",
                message="Flask-Limiter using default in-memory storage",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category="security",
                snippet="Limiter(app)  # No storage_uri",
                cwe_id="CWE-770",
                additional_info={
                    "framework": "Flask",
                },
            )
        )

    return findings


def _detect_expensive_operations(db: RuleDB) -> list[StandardFinding]:
    """Detect expensive operations that run before rate limiting."""
    findings = []

    file_rows = db.query(
        Q("function_call_args").select("DISTINCT file").where("callee_function IS NOT NULL")
    )

    rate_limited_files = set()
    for (file,) in file_rows:
        check_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
            .limit(1)
        )

        for (func,) in check_rows:
            func_lower = func.lower()
            if "limit" in func_lower or "throttle" in func_lower or "ratelimit" in func_lower:
                rate_limited_files.add(file)
                break

    for file in rate_limited_files:
        func_rows = db.query(
            Q("function_call_args")
            .select("line", "callee_function")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
            .order_by("line")
        )

        rate_limit_line = None
        for line_num, func in func_rows:
            func_lower = func.lower()
            if "limit" in func_lower or "throttle" in func_lower or "ratelimit" in func_lower:
                rate_limit_line = line_num
                break

        if rate_limit_line is None:
            continue

        exp_rows = db.query(
            Q("function_call_args")
            .select("line", "callee_function", "argument_expr")
            .where("file = ?", file)
            .where("line < ?", rate_limit_line)
            .where("callee_function IS NOT NULL")
        )

        for exp_line, exp_func, _exp_args in exp_rows:
            exp_func_lower = exp_func.lower()
            if not any(op in exp_func_lower for op in EXPENSIVE_OPERATIONS):
                continue

            op_type = "unknown"
            if any(db in exp_func.lower() for db in ["database", "query", "find", "select"]):
                op_type = "database"
            elif any(
                crypto in exp_func.lower() for crypto in ["bcrypt", "hash", "crypto", "argon"]
            ):
                op_type = "cryptographic"
            elif any(io in exp_func.lower() for io in ["email", "mail", "fetch", "axios"]):
                op_type = "network I/O"

            findings.append(
                StandardFinding(
                    rule_name="expensive-before-limit",
                    message=f"{op_type.title()} operation ({exp_func}) executes before rate limiting",
                    file_path=file,
                    line=exp_line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category="security",
                    snippet=f"{exp_func}()",
                    cwe_id="CWE-770",
                    additional_info={
                        "operation_type": op_type,
                        "function": exp_func,
                        "rate_limit_line": rate_limit_line,
                        "attack_scenario": _get_attack_scenario("expensive-before-limit"),
                        "impact": f"{op_type} DoS vulnerability",
                    },
                )
            )

    return findings


def _detect_api_rate_limits(db: RuleDB) -> list[StandardFinding]:
    """Detect API endpoints without rate limiting."""
    findings = []

    rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "method", "path")
        .where("path IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, method, path in rows:
        is_critical = any(endpoint in path.lower() for endpoint in CRITICAL_ENDPOINTS)

        if is_critical:
            nearby_rows = db.query(
                Q("function_call_args")
                .select("callee_function", "line", "argument_expr")
                .where("file = ?", file)
                .where("callee_function IS NOT NULL")
            )

            has_rate_limit = False
            for nearby_func, nearby_line, nearby_args in nearby_rows:
                if abs(nearby_line - line) > 50:
                    continue
                func_lower = nearby_func.lower()
                args_lower = (nearby_args or "").lower()
                if "limit" in func_lower or "throttle" in func_lower or "ratelimit" in args_lower:
                    has_rate_limit = True
                    break

            if not has_rate_limit:
                findings.append(
                    StandardFinding(
                        rule_name="api-missing-rate-limit",
                        message=f"API endpoint {method} {path} lacks rate limiting",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet=f"{method} {path}",
                        cwe_id="CWE-307",
                        additional_info={
                            "method": method,
                            "path": path,
                            "risk": "API abuse, data scraping, DoS",
                        },
                    )
                )

    return findings


def _detect_decorator_ordering(db: RuleDB) -> list[StandardFinding]:
    """Detect incorrect decorator ordering in Python."""
    findings = []

    rows = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("type = ?", "decorator")
        .where("name IS NOT NULL")
        .order_by("path, line")
    )

    file_decorators = {}
    for file, line, name in rows:
        name_lower = name.lower()

        if not (
            "limit" in name_lower
            or "throttle" in name_lower
            or "auth" in name_lower
            or "login_required" in name_lower
        ):
            continue

        if file not in file_decorators:
            file_decorators[file] = []
        file_decorators[file].append({"line": line, "name": name})

    for file, decorators in file_decorators.items():
        function_groups = []
        current_group = []
        last_line = -10

        for dec in sorted(decorators, key=lambda x: x["line"]):
            if dec["line"] - last_line <= 5:
                current_group.append(dec)
            else:
                if current_group:
                    function_groups.append(current_group)
                current_group = [dec]
            last_line = dec["line"]

        if current_group:
            function_groups.append(current_group)

        for group in function_groups:
            rate_limit_line = -1
            auth_line = -1

            for dec in group:
                name_lower = dec["name"].lower()
                if any(pattern in name_lower for pattern in ["limit", "throttle", "ratelimit"]):
                    rate_limit_line = dec["line"]
                elif any(pattern in name_lower for pattern in ["auth", "login_required"]):
                    auth_line = dec["line"]

            if rate_limit_line > 0 and auth_line > 0 and auth_line < rate_limit_line:
                findings.append(
                    StandardFinding(
                        rule_name="python-decorator-order",
                        message="Authentication decorator before rate limiting decorator",
                        file_path=file,
                        line=auth_line,
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet="@login_required before @rate_limit",
                        cwe_id="CWE-770",
                        additional_info={
                            "framework": "Python/Flask/Django",
                        },
                    )
                )

    return findings


def _detect_bypass_configs(db: RuleDB) -> list[StandardFinding]:
    """Detect configurations that allow rate limit bypass."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, var, expr in rows:
        var_lower = var.lower()
        expr_lower = expr.lower()
        has_bypass = any(tech in var_lower or tech in expr_lower for tech in BYPASS_TECHNIQUES)
        if not has_bypass:
            continue

        nearby_rows = db.query(
            Q("function_call_args")
            .select("callee_function", "line", "argument_expr")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
        )

        has_rate_limit_nearby = False
        for nearby_func, nearby_line, nearby_args in nearby_rows:
            if abs(nearby_line - line) > 30:
                continue
            func_lower = nearby_func.lower()
            args_lower = (nearby_args or "").lower()
            if "limit" in func_lower or "ratelimit" in args_lower:
                has_rate_limit_nearby = True
                break

        if has_rate_limit_nearby:
            findings.append(
                StandardFinding(
                    rule_name="rate-limit-bypass-config",
                    message="Potential rate limit bypass configuration detected",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.LOW,
                    category="security",
                    snippet=f"{var} = {expr[:100]}",
                    cwe_id="CWE-770",
                    additional_info={
                        "variable": var,
                        "note": "Ensure bypass is properly restricted to internal services only",
                    },
                )
            )

    return findings


def _detect_missing_user_limits(db: RuleDB) -> list[StandardFinding]:
    """Detect rate limiters that don't consider authenticated users."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        func_lower = func.lower()
        if not ("ratelimit" in func_lower or "limiter" in func_lower):
            continue

        args_lower = args.lower()

        has_user_limit = any(
            pattern in args_lower
            for pattern in [
                "user",
                "userid",
                "session",
                "account",
                "req.user",
                "req.session",
                "current_user",
            ]
        )

        ip_only = ("ip" in args_lower or "address" in args_lower) and not has_user_limit

        if ip_only:
            findings.append(
                StandardFinding(
                    rule_name="ip-only-rate-limit",
                    message="Rate limiter uses only IP address, not user identity",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category="security",
                    snippet=f"{func}(ip-based only)",
                    cwe_id="CWE-770",
                    additional_info={
                        "limitation": "Shared IPs (NAT, proxy) affect multiple users",
                    },
                )
            )

    return findings


def _detect_weak_rate_limits(db: RuleDB) -> list[StandardFinding]:
    """Detect rate limits with weak values (too high)."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        func_lower = func.lower()
        if not ("ratelimit" in func_lower or "limit" in func_lower):
            continue

        args_lower = args.lower()
        if not ("max:" in args_lower or "limit:" in args_lower or "requests:" in args_lower):
            continue

        numbers = []
        for token in (
            args.replace(",", " ")
            .replace(":", " ")
            .replace("(", " ")
            .replace(")", " ")
            .replace("=", " ")
            .split()
        ):
            if token.isdigit():
                numbers.append(token)

        for num_str in numbers:
            num = int(num_str)

            if num > 10:
                auth_rows = db.query(
                    Q("function_call_args")
                    .select("argument_expr", "line")
                    .where("file = ?", file)
                    .where("argument_expr IS NOT NULL")
                )

                is_auth_endpoint = False
                for nearby_args, nearby_line in auth_rows:
                    if abs(nearby_line - line) > 20:
                        continue
                    args_lower = nearby_args.lower()
                    if "login" in args_lower or "auth" in args_lower or "password" in args_lower:
                        is_auth_endpoint = True
                        break

                if is_auth_endpoint:
                    findings.append(
                        StandardFinding(
                            rule_name="weak-rate-limit-value",
                            message=f"Rate limit too high ({num}) for authentication endpoint",
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            confidence=Confidence.LOW,
                            category="security",
                            snippet=f"max: {num} requests",
                            cwe_id="CWE-307",
                            additional_info={"current_limit": num, "reference": "NIST 800-63B"},
                        )
                    )

    return findings


def generate_rate_limit_summary(findings: list[StandardFinding]) -> dict:
    """Generate a summary report of rate limiting findings."""
    summary = {
        "total_findings": len(findings),
        "by_severity": {},
        "by_pattern": {},
        "frameworks_affected": set(),
        "top_risks": [],
    }

    for finding in findings:
        sev = (
            finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
        )
        summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1

        pattern = finding.rule_name
        summary["by_pattern"][pattern] = summary["by_pattern"].get(pattern, 0) + 1

        if finding.additional_info and "framework" in finding.additional_info:
            summary["frameworks_affected"].add(finding.additional_info["framework"])

    summary["frameworks_affected"] = list(summary["frameworks_affected"])

    critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
    summary["top_risks"] = [
        {"rule": f.rule_name, "message": f.message, "file": f.file_path, "line": f.line}
        for f in critical_findings[:5]
    ]

    return summary
