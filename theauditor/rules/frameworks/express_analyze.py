"""Express.js Framework Security Analyzer.

Detects security misconfigurations and vulnerabilities in Express.js applications:
- Missing security middleware (Helmet, CSRF, rate limiting)
- XSS vulnerabilities (unsanitized user input in responses)
- CORS misconfigurations
- Insecure session configuration
- Sync operations blocking event loop
- Database queries directly in route handlers
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
    name="express_security",
    category="frameworks",
    target_extensions=[".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["frontend/", "client/", "test/", "spec.", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="api_endpoints",
)

# User input sources in Express.js
USER_INPUT_SOURCES = frozenset([
    "req.body",
    "req.query",
    "req.params",
    "req.cookies",
    "req.headers",
    "req.ip",
    "req.hostname",
    "req.path",
    "request.body",
    "request.query",
    "request.params",
    "request.headers",
    "request.cookies",
])

# Response sinks for XSS
RESPONSE_SINKS = frozenset([
    "res.send",
    "res.json",
    "res.jsonp",
    "res.render",
    "res.write",
    "res.end",
    "response.send",
    "response.json",
    "response.render",
    "response.write",
])

# Redirect sinks for open redirect
REDIRECT_SINKS = frozenset([
    "res.redirect",
    "response.redirect",
    "res.location",
])

# Sync operations that block event loop
SYNC_OPERATIONS = frozenset([
    "fs.readFileSync",
    "fs.writeFileSync",
    "fs.appendFileSync",
    "fs.unlinkSync",
    "fs.mkdirSync",
    "fs.rmdirSync",
    "fs.readdirSync",
    "fs.statSync",
    "fs.lstatSync",
    "fs.existsSync",
    "fs.accessSync",
    "child_process.execSync",
    "child_process.spawnSync",
])

# Rate limiting libraries
RATE_LIMIT_LIBS = frozenset([
    "express-rate-limit",
    "rate-limiter-flexible",
    "express-slow-down",
    "express-brute",
    "rate-limiter",
])

# Sanitization functions
SANITIZATION_FUNCS = frozenset([
    "sanitize",
    "escape",
    "encode",
    "DOMPurify",
    "xss",
    "validator",
    "clean",
    "strip",
])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Express.js security misconfigurations.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        # Load Express app context
        express_files = _get_express_files(db)
        if not express_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        imports = _get_imports(db)
        endpoints = _get_api_endpoints(db)

        # Run all checks
        findings.extend(_check_missing_helmet(db, express_files, imports))
        findings.extend(_check_missing_error_handler(db, endpoints))
        findings.extend(_check_sync_operations(db))
        findings.extend(_check_xss_vulnerabilities(db))
        findings.extend(_check_open_redirect(db))
        findings.extend(_check_missing_rate_limiting(imports, endpoints))
        findings.extend(_check_body_parser_limits(db))
        findings.extend(_check_db_in_routes(db, endpoints))
        findings.extend(_check_cors_wildcard(db))
        findings.extend(_check_missing_csrf(db, imports, endpoints))
        findings.extend(_check_session_security(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_express_files(db: RuleDB) -> list[str]:
    """Get files that import Express."""
    rows = db.query(
        Q("refs")
        .select("src")
        .where("value = ?", "express")
    )
    return [row[0] for row in rows]


def _get_imports(db: RuleDB) -> dict[str, set[str]]:
    """Get all imports grouped by file."""
    rows = db.query(
        Q("refs")
        .select("src", "value")
        .where("kind = ?", "import")
    )
    imports: dict[str, set[str]] = {}
    for file, import_val in rows:
        if file not in imports:
            imports[file] = set()
        imports[file].add(import_val)
    return imports


def _get_api_endpoints(db: RuleDB) -> list[dict]:
    """Get all API endpoints."""
    rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "method", "pattern", "handler_function")
        .order_by("file, line")
    )
    return [
        {"file": row[0], "line": row[1], "method": row[2], "pattern": row[3], "handler": row[4]}
        for row in rows
    ]


def _check_missing_helmet(
    db: RuleDB, express_files: list[str], imports: dict[str, set[str]]
) -> list[StandardFinding]:
    """Check for missing Helmet security middleware."""
    findings = []

    # Check if helmet is imported
    has_helmet = any("helmet" in file_imports for file_imports in imports.values())
    if has_helmet:
        return findings

    # Check if helmet is called via app.use(helmet())
    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "argument_expr")
        .where("callee_function LIKE ? OR argument_expr LIKE ?", "%helmet%", "%helmet%")
        .limit(1)
    )
    if list(rows):
        return findings

    # No helmet found
    if express_files:
        findings.append(
            StandardFinding(
                rule_name="express-missing-helmet",
                message="Express app without Helmet security middleware - missing critical security headers",
                file_path=express_files[0],
                line=1,
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.HIGH,
                snippet="Missing: app.use(helmet())",
                cwe_id="CWE-693",
            )
        )

    return findings


def _check_missing_error_handler(db: RuleDB, endpoints: list[dict]) -> list[StandardFinding]:
    """Check for routes without error handling using CFG data."""
    findings = []

    for endpoint in endpoints:
        handler = endpoint.get("handler", "")
        if not handler:
            continue

        # Check if handler has try/catch blocks
        rows = db.query(
            Q("cfg_blocks")
            .select("block_type")
            .where("file = ? AND function_name = ? AND block_type IN (?, ?, ?)",
                   endpoint["file"], handler, "try", "except", "catch")
            .limit(1)
        )

        if not list(rows):
            findings.append(
                StandardFinding(
                    rule_name="express-missing-error-handler",
                    message="Express route without error handling",
                    file_path=endpoint["file"],
                    line=endpoint["line"],
                    severity=Severity.HIGH,
                    category="error-handling",
                    confidence=Confidence.MEDIUM,
                    snippet=f"Route handler '{handler}' missing try/catch",
                    cwe_id="CWE-755",
                )
            )

    return findings


def _check_sync_operations(db: RuleDB) -> list[StandardFinding]:
    """Check for synchronous file operations in route handlers."""
    findings = []

    # Build WHERE clause for sync operations
    sync_ops_list = list(SYNC_OPERATIONS)[:10]  # Top 10 most common
    placeholders = ",".join("?" * len(sync_ops_list))

    # Use raw query for complex subquery
    sql, params = Q.raw(
        f"""
        SELECT DISTINCT file, line, callee_function, caller_function
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
        AND EXISTS (
            SELECT 1 FROM api_endpoints e
            WHERE e.file = function_call_args.file
        )
        ORDER BY file, line
        """,
        sync_ops_list,
    )
    rows = db.execute(sql, params)

    for file, line, sync_op, caller in rows:
        findings.append(
            StandardFinding(
                rule_name="express-sync-in-async",
                message=f"Synchronous operation {sync_op} blocking event loop in route",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="performance",
                confidence=Confidence.HIGH,
                snippet=f"{sync_op}(...) in {caller or 'route handler'}",
                cwe_id="CWE-400",
            )
        )

    return findings


def _check_xss_vulnerabilities(db: RuleDB) -> list[StandardFinding]:
    """Check for direct output of user input (XSS)."""
    findings = []

    # Get response outputs
    response_methods = ("res.send", "res.json", "res.write", "res.render")
    placeholders = ",".join("?" * len(response_methods))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *response_methods)
        .order_by("file, line")
    )

    for file, line, method, arg_expr in rows:
        if not arg_expr:
            continue

        # Check for user input in arguments
        input_source = None
        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                input_source = source
                break

        if not input_source:
            continue

        # Check for sanitization in nearby lines
        sanitization_funcs = ("sanitize", "escape", "encode", "DOMPurify", "xss")
        sanitization_placeholders = ",".join("?" * len(sanitization_funcs))

        sanitize_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where(f"file = ? AND line BETWEEN ? AND ? AND callee_function IN ({sanitization_placeholders})",
                   file, line - 5, line + 5, *sanitization_funcs)
            .limit(1)
        )

        if not list(sanitize_rows):
            findings.append(
                StandardFinding(
                    rule_name="express-xss-direct-send",
                    message=f"Potential XSS - {input_source} directly in response without sanitization",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    confidence=Confidence.HIGH,
                    snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_open_redirect(db: RuleDB) -> list[StandardFinding]:
    """Check for open redirect vulnerabilities."""
    # TODO(quality): Enhance with taint tracking from user input to redirect sink
    findings = []

    # Get redirect calls
    redirect_methods = tuple(REDIRECT_SINKS)
    placeholders = ",".join("?" * len(redirect_methods))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *redirect_methods)
        .order_by("file, line")
    )

    for file, line, method, arg_expr in rows:
        if not arg_expr:
            continue

        # Check for user input in redirect target
        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                findings.append(
                    StandardFinding(
                        rule_name="express-open-redirect",
                        message=f"Potential open redirect - {source} used in redirect target",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.HIGH,
                        snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                        cwe_id="CWE-601",
                    )
                )
                break

    return findings


def _check_missing_rate_limiting(
    imports: dict[str, set[str]], endpoints: list[dict]
) -> list[StandardFinding]:
    """Check for missing rate limiting on API endpoints."""
    findings = []

    # Only check if there are API routes
    api_routes = [ep for ep in endpoints if "/api" in ep.get("pattern", "")]
    if not api_routes:
        return findings

    # Check for rate limiting library import
    has_rate_limit = any(
        any(lib in file_imports for lib in RATE_LIMIT_LIBS)
        for file_imports in imports.values()
    )

    if not has_rate_limit:
        findings.append(
            StandardFinding(
                rule_name="express-missing-rate-limit",
                message="API endpoints without rate limiting - vulnerable to DoS/brute force",
                file_path=api_routes[0]["file"],
                line=api_routes[0]["line"],
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.MEDIUM,
                snippet="Add express-rate-limit middleware",
                cwe_id="CWE-400",
            )
        )

    return findings


def _check_body_parser_limits(db: RuleDB) -> list[StandardFinding]:
    """Check for body parser without size limit."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?, ?, ?)",
               "bodyParser.json", "bodyParser.urlencoded", "json", "urlencoded")
        .order_by("file, line")
    )

    for file, line, callee, config in rows:
        config_str = config or ""
        if "limit" not in config_str:
            findings.append(
                StandardFinding(
                    rule_name="express-body-parser-limit",
                    message="Body parser without size limit - vulnerable to DoS",
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{callee}() - add {{ limit: '100kb' }}",
                    cwe_id="CWE-400",
                )
            )

    return findings


def _check_db_in_routes(db: RuleDB, endpoints: list[dict]) -> list[StandardFinding]:
    """Check for database queries directly in route handlers."""
    findings = []

    if not endpoints:
        return findings

    route_files = {ep["file"] for ep in endpoints}
    db_methods = (
        "query", "find", "findOne", "findById", "create",
        "update", "updateOne", "updateMany", "delete",
        "deleteOne", "deleteMany", "save", "exec",
    )
    placeholders = ",".join("?" * len(db_methods))

    for route_file in route_files:
        rows = db.query(
            Q("function_call_args")
            .select("line", "callee_function", "caller_function")
            .where(f"file = ? AND callee_function IN ({placeholders})",
                   route_file, *db_methods)
            .order_by("line")
        )

        for line, db_method, caller in rows:
            caller_lower = (caller or "").lower()
            # Skip if already in service/repository layer
            if any(pattern in caller_lower for pattern in ("service", "repository", "model", "dao")):
                continue

            findings.append(
                StandardFinding(
                    rule_name="express-direct-db-query",
                    message=f"Database {db_method} directly in route handler - consider service layer",
                    file_path=route_file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="architecture",
                    confidence=Confidence.MEDIUM,
                    snippet=f"Move {db_method} to service/repository layer",
                    cwe_id="CWE-1061",
                )
            )

    return findings


def _check_cors_wildcard(db: RuleDB) -> list[StandardFinding]:
    """Check for CORS wildcard configuration."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function = ?", "cors")
        .order_by("file, line")
    )

    for file, line, _callee, config in rows:
        config_str = config or ""
        # Check for dangerous CORS patterns
        dangerous_patterns = (
            "origin:*",
            "origin: *",
            "origin:true",
            "origin: true",
            "'*'",
            '"*"',
        )
        if any(pattern in config_str for pattern in dangerous_patterns):
            findings.append(
                StandardFinding(
                    rule_name="express-cors-wildcard",
                    message="CORS configured with wildcard origin - allows any domain",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet="CORS with origin: * or origin: true",
                    cwe_id="CWE-346",
                )
            )

    return findings


def _check_missing_csrf(
    db: RuleDB, imports: dict[str, set[str]], endpoints: list[dict]
) -> list[StandardFinding]:
    """Check for missing CSRF protection."""
    findings = []

    # Only check state-changing endpoints
    modifying_endpoints = [
        ep for ep in endpoints
        if ep.get("method", "").upper() in ("POST", "PUT", "DELETE", "PATCH")
    ]

    if not modifying_endpoints:
        return findings

    # Check for CSRF library import
    has_csrf = any(
        "csurf" in file_imports or "csrf" in file_imports
        for file_imports in imports.values()
    )

    if has_csrf:
        return findings

    # Check for CSRF middleware usage
    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "argument_expr")
        .where("callee_function IN (?, ?) OR argument_expr LIKE ?",
               "csurf", "csrf", "%csrf%")
        .limit(1)
    )

    if not list(rows):
        findings.append(
            StandardFinding(
                rule_name="express-missing-csrf",
                message="State-changing endpoints without CSRF protection",
                file_path=modifying_endpoints[0]["file"],
                line=modifying_endpoints[0]["line"],
                severity=Severity.HIGH,
                category="csrf",
                confidence=Confidence.MEDIUM,
                snippet="POST/PUT/DELETE endpoints need CSRF tokens",
                cwe_id="CWE-352",
            )
        )

    return findings


def _check_session_security(db: RuleDB) -> list[StandardFinding]:
    """Check for insecure session configuration."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ? OR argument_expr LIKE ?",
               "%session%", "%session%")
        .order_by("file, line")
    )

    for file, line, callee, config in rows:
        if not config:
            continue

        config_lower = config.lower()

        # Skip if not a session configuration
        if "session" not in callee.lower() and "session" not in config_lower:
            continue

        issues = []

        # Check for weak secret
        if "secret" in config_lower:
            weak_secrets = ("secret", "keyboard cat", "default", "changeme", "password")
            if any(weak in config_lower for weak in weak_secrets):
                issues.append("weak secret")

        # Check cookie security flags
        if "cookie" in config_lower:
            if "httponly" not in config_lower:
                issues.append("missing httpOnly")
            if "secure" not in config_lower:
                issues.append("missing secure flag")
            if "samesite" not in config_lower:
                issues.append("missing sameSite")

        if issues:
            findings.append(
                StandardFinding(
                    rule_name="express-session-insecure",
                    message=f"Insecure session configuration: {', '.join(issues)}",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet="Session configuration issues",
                    cwe_id="CWE-614",
                )
            )

    return findings


# TODO(quality): Missing detection patterns to add in future:
# - Prototype pollution in req.body (Express < 4.16 or with body-parser)
# - HTTP parameter pollution
# - Path traversal in express.static
# - NoSQL injection in req.query/req.body
# - ReDoS in route patterns
# - Header injection via res.set/res.header
# - SSRF via proxy middleware
# - Trust proxy misconfiguration (req.ip spoofing)


def register_taint_patterns(taint_registry) -> None:
    """Register Express.js-specific taint patterns for taint tracking engine.

    Args:
        taint_registry: The taint pattern registry to register patterns with
    """
    for pattern in USER_INPUT_SOURCES:
        taint_registry.register_source(pattern, "http_request", "javascript")

    for pattern in RESPONSE_SINKS:
        taint_registry.register_sink(pattern, "response", "javascript")

    for pattern in REDIRECT_SINKS:
        taint_registry.register_sink(pattern, "redirect", "javascript")
