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


USER_INPUT_SOURCES = frozenset(
    [
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
    ]
)


RESPONSE_SINKS = frozenset(
    [
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
    ]
)


REDIRECT_SINKS = frozenset(
    [
        "res.redirect",
        "response.redirect",
        "res.location",
    ]
)


SYNC_OPERATIONS = frozenset(
    [
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
        "crypto.pbkdf2Sync",
        "crypto.scryptSync",
        "crypto.randomFillSync",
        "crypto.generateKeyPairSync",
        "crypto.generateKeySync",
        "bcrypt.hashSync",
        "bcrypt.compareSync",
        "bcryptjs.hashSync",
        "bcryptjs.compareSync",
    ]
)


RATE_LIMIT_LIBS = frozenset(
    [
        "express-rate-limit",
        "rate-limiter-flexible",
        "express-slow-down",
        "express-brute",
        "rate-limiter",
    ]
)


SANITIZATION_FUNCS = frozenset(
    [
        "sanitize",
        "escape",
        "encode",
        "DOMPurify",
        "xss",
        "validator",
        "clean",
        "strip",
    ]
)


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

        express_files = _get_express_files(db)
        if not express_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        imports = _get_imports(db)
        endpoints = _get_api_endpoints(db)

        findings.extend(_check_missing_helmet(db, express_files, imports))
        findings.extend(_check_missing_error_handler(db, endpoints))
        findings.extend(_check_sync_operations(db))
        findings.extend(_check_xss_vulnerabilities(db))
        findings.extend(_check_open_redirect(db))
        findings.extend(_check_missing_rate_limiting(db, imports, endpoints))
        findings.extend(_check_body_parser_limits(db))
        findings.extend(_check_db_in_routes(db, endpoints))
        findings.extend(_check_cors_wildcard(db))
        findings.extend(_check_missing_csrf(db, imports, endpoints))
        findings.extend(_check_session_security(db))
        findings.extend(_check_prototype_pollution(db))
        findings.extend(_check_nosql_injection(db))
        findings.extend(_check_path_traversal(db))
        findings.extend(_check_header_injection(db))
        findings.extend(_check_ssrf(db))
        findings.extend(_check_trust_proxy(db, express_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_express_files(db: RuleDB) -> list[str]:
    """Get files that import Express."""
    rows = db.query(Q("refs").select("src").where("value = ?", "express"))
    return [row[0] for row in rows]


def _get_imports(db: RuleDB) -> dict[str, set[str]]:
    """Get all imports grouped by file."""
    rows = db.query(Q("refs").select("src", "value").where("kind = ?", "import"))
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

    has_helmet = any("helmet" in file_imports for file_imports in imports.values())
    if has_helmet:
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "argument_expr")
        .where("callee_function LIKE ? OR argument_expr LIKE ?", "%helmet%", "%helmet%")
        .limit(1)
    )
    if list(rows):
        return findings

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

        rows = db.query(
            Q("cfg_blocks")
            .select("block_type")
            .where(
                "file = ? AND function_name = ? AND block_type IN (?, ?, ?)",
                endpoint["file"],
                handler,
                "try",
                "except",
                "catch",
            )
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

    sync_ops_list = list(SYNC_OPERATIONS)[:10]
    placeholders = ",".join("?" * len(sync_ops_list))

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

    response_methods = ("res.send", "res.json", "res.write", "res.render")
    placeholders = ",".join("?" * len(response_methods))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *response_methods)
        .order_by("file, line")
    )

    for file, line, _method, arg_expr in rows:
        if not arg_expr:
            continue

        input_source = None
        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                input_source = source
                break

        if not input_source:
            continue

        sanitization_funcs = ("sanitize", "escape", "encode", "DOMPurify", "xss")
        sanitization_placeholders = ",".join("?" * len(sanitization_funcs))

        sanitize_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where(
                f"file = ? AND line BETWEEN ? AND ? AND callee_function IN ({sanitization_placeholders})",
                file,
                line - 5,
                line + 5,
                *sanitization_funcs,
            )
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
    findings = []

    redirect_methods = tuple(REDIRECT_SINKS)
    placeholders = ",".join("?" * len(redirect_methods))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *redirect_methods)
        .order_by("file, line")
    )

    for file, line, _method, arg_expr in rows:
        if not arg_expr:
            continue

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
    db: RuleDB, imports: dict[str, set[str]], endpoints: list[dict]
) -> list[StandardFinding]:
    """Check for missing rate limiting on API endpoints.

    Improved to verify rate limiter is actually applied via app.use(), not just imported.
    """
    findings = []

    api_routes = [ep for ep in endpoints if "/api" in ep.get("pattern", "")]
    if not api_routes:
        return findings

    has_rate_limit_import = any(
        any(lib in file_imports for lib in RATE_LIMIT_LIBS) for file_imports in imports.values()
    )

    if not has_rate_limit_import:
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

    rate_limit_patterns = ("limiter", "rateLimit", "rateLimiter", "slowDown", "brute")
    applied = False

    for pattern in rate_limit_patterns:
        rows = db.query(
            Q("function_call_args")
            .select("callee_function", "argument_expr")
            .where("callee_function LIKE ? AND argument_expr LIKE ?", "%use%", f"%{pattern}%")
            .limit(1)
        )
        if list(rows):
            applied = True
            break

    if not applied:
        rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where(
                "callee_function LIKE ? OR callee_function LIKE ?", "%rateLimit%", "%rateLimiter%"
            )
            .limit(1)
        )
        if list(rows):
            applied = True

    if not applied:
        findings.append(
            StandardFinding(
                rule_name="express-rate-limit-not-applied",
                message="Rate limiter imported but not applied via app.use()",
                file_path=api_routes[0]["file"],
                line=api_routes[0]["line"],
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.MEDIUM,
                snippet="Call app.use(limiter) to apply rate limiting",
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
        .where(
            "callee_function IN (?, ?, ?, ?)",
            "bodyParser.json",
            "bodyParser.urlencoded",
            "json",
            "urlencoded",
        )
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
        "query",
        "find",
        "findOne",
        "findById",
        "create",
        "update",
        "updateOne",
        "updateMany",
        "delete",
        "deleteOne",
        "deleteMany",
        "save",
        "exec",
    )
    placeholders = ",".join("?" * len(db_methods))

    for route_file in route_files:
        rows = db.query(
            Q("function_call_args")
            .select("line", "callee_function", "caller_function")
            .where(f"file = ? AND callee_function IN ({placeholders})", route_file, *db_methods)
            .order_by("line")
        )

        for line, db_method, caller in rows:
            caller_lower = (caller or "").lower()

            if any(
                pattern in caller_lower for pattern in ("service", "repository", "model", "dao")
            ):
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

    modifying_endpoints = [
        ep for ep in endpoints if ep.get("method", "").upper() in ("POST", "PUT", "DELETE", "PATCH")
    ]

    if not modifying_endpoints:
        return findings

    has_csrf = any(
        "csurf" in file_imports or "csrf" in file_imports for file_imports in imports.values()
    )

    if has_csrf:
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "argument_expr")
        .where("callee_function IN (?, ?) OR argument_expr LIKE ?", "csurf", "csrf", "%csrf%")
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
        .where("callee_function LIKE ? OR argument_expr LIKE ?", "%session%", "%session%")
        .order_by("file, line")
    )

    for file, line, callee, config in rows:
        if not config:
            continue

        config_lower = config.lower()

        if "session" not in callee.lower() and "session" not in config_lower:
            continue

        issues = []

        if "secret" in config_lower:
            weak_secrets = ("secret", "keyboard cat", "default", "changeme", "password")
            if any(weak in config_lower for weak in weak_secrets):
                issues.append("weak secret")

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


def _check_prototype_pollution(db: RuleDB) -> list[StandardFinding]:
    """Check for prototype pollution vulnerabilities via object merge/extend."""
    findings = []

    merge_funcs = (
        "Object.assign",
        "_.merge",
        "_.extend",
        "_.defaultsDeep",
        "merge",
        "extend",
        "deepMerge",
        "deepExtend",
        "$.extend",
    )
    placeholders = ",".join("?" * len(merge_funcs))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *merge_funcs)
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        if any(source in arg_expr for source in USER_INPUT_SOURCES):
            findings.append(
                StandardFinding(
                    rule_name="express-prototype-pollution",
                    message=f"Prototype pollution risk - {callee} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                    cwe_id="CWE-1321",
                )
            )

    return findings


def _check_nosql_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for NoSQL injection vulnerabilities in MongoDB queries."""
    findings = []

    mongo_methods = (
        "find",
        "findOne",
        "findById",
        "findOneAndUpdate",
        "findOneAndDelete",
        "updateOne",
        "updateMany",
        "deleteOne",
        "deleteMany",
        "aggregate",
        "where",
        "elemMatch",
    )
    placeholders = ",".join("?" * len(mongo_methods))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            f"callee_function IN ({placeholders}) OR callee_function LIKE ?",
            *mongo_methods,
            "%.find%",
        )
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                if "$" in arg_expr or "where" in callee.lower():
                    findings.append(
                        StandardFinding(
                            rule_name="express-nosql-injection",
                            message=f"NoSQL injection risk - {source} in MongoDB query",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="injection",
                            confidence=Confidence.HIGH,
                            snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                            cwe_id="CWE-943",
                        )
                    )
                else:
                    findings.append(
                        StandardFinding(
                            rule_name="express-nosql-injection-risk",
                            message=f"Potential NoSQL injection - {source} in query without sanitization",
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category="injection",
                            confidence=Confidence.MEDIUM,
                            snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                            cwe_id="CWE-943",
                        )
                    )
                break

    return findings


def _check_path_traversal(db: RuleDB) -> list[StandardFinding]:
    """Check for path traversal in express.static and file operations."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            "callee_function IN (?, ?, ?, ?, ?)",
            "express.static",
            "res.sendFile",
            "res.download",
            "path.join",
            "path.resolve",
        )
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""
        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                findings.append(
                    StandardFinding(
                        rule_name="express-path-traversal",
                        message=f"Path traversal risk - {source} in {callee}",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=Confidence.HIGH,
                        snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                        cwe_id="CWE-22",
                    )
                )
                break

    return findings


def _check_header_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for HTTP header injection vulnerabilities."""
    findings = []

    header_methods = ("res.set", "res.header", "res.setHeader", "response.set", "response.header")
    placeholders = ",".join("?" * len(header_methods))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *header_methods)
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""
        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                findings.append(
                    StandardFinding(
                        rule_name="express-header-injection",
                        message=f"HTTP header injection - {source} in {callee}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="injection",
                        confidence=Confidence.HIGH,
                        snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                        cwe_id="CWE-113",
                    )
                )
                break

    return findings


def _check_ssrf(db: RuleDB) -> list[StandardFinding]:
    """Check for Server-Side Request Forgery vulnerabilities."""
    findings = []

    http_funcs = (
        "axios",
        "axios.get",
        "axios.post",
        "axios.put",
        "axios.delete",
        "fetch",
        "request",
        "request.get",
        "request.post",
        "http.get",
        "http.request",
        "https.get",
        "https.request",
        "got",
        "got.get",
        "got.post",
        "superagent",
        "needle",
    )
    placeholders = ",".join("?" * len(http_funcs))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *http_funcs)
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""
        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                findings.append(
                    StandardFinding(
                        rule_name="express-ssrf",
                        message=f"SSRF vulnerability - {source} controls URL in {callee}",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=Confidence.HIGH,
                        snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                        cwe_id="CWE-918",
                    )
                )
                break

    return findings


def _check_trust_proxy(db: RuleDB, express_files: list[str]) -> list[StandardFinding]:
    """Check for trust proxy misconfiguration allowing IP spoofing."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ? AND argument_expr LIKE ?", "%set%", "%trust proxy%")
        .order_by("file, line")
    )

    for file, line, _callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        if "true" in arg_expr.lower() or "'*'" in arg_expr or '"*"' in arg_expr:
            findings.append(
                StandardFinding(
                    rule_name="express-trust-proxy-all",
                    message="trust proxy set to true - trusts all proxies, enables IP spoofing",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                    cwe_id="CWE-348",
                )
            )

    ip_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("argument_expr LIKE ?", "%req.ip%")
        .order_by("file, line")
    )

    files_using_req_ip = {row[0] for row in ip_rows}

    for ip_file in files_using_req_ip:
        proxy_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND argument_expr LIKE ?", ip_file, "%trust proxy%")
            .limit(1)
        )
        if not list(proxy_rows):
            findings.append(
                StandardFinding(
                    rule_name="express-req-ip-no-trust-proxy",
                    message="req.ip used without trust proxy configuration - may return wrong IP behind proxy",
                    file_path=ip_file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    snippet="Configure trust proxy if behind reverse proxy",
                    cwe_id="CWE-348",
                )
            )

    return findings


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
