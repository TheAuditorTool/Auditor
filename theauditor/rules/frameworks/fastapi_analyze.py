"""FastAPI Framework Security Analyzer.

Detects security misconfigurations and vulnerabilities in FastAPI applications:
- Sync operations in async routes (blocking event loop)
- Missing dependency injection for database access
- Missing CORS/timeout configuration
- Unauthenticated WebSocket endpoints
- Debug endpoints exposed in production
- Path traversal in file upload handlers
- Missing exception handlers (info leakage)
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
    name="fastapi_security",
    category="frameworks",
    target_extensions=[".py"],
    exclude_patterns=["test/", "tests/", "spec.", "__tests__/", "migrations/", ".venv/"],
    execution_scope="database",
    primary_table="api_endpoints",
)


SYNC_OPERATIONS = frozenset(
    [
        "time.sleep",
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "requests.patch",
        "requests.head",
        "requests.options",
        "urllib.request.urlopen",
        "urllib.urlopen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_output",
    ]
)


DEBUG_ENDPOINTS = frozenset(
    [
        "/debug",
        "/test",
        "/_debug",
        "/_test",
        "/health/full",
        "/metrics/internal",
        "/admin/debug",
        "/dev",
        "/_dev",
        "/testing",
        "/__debug__",
        "/internal",
    ]
)


FASTAPI_RESPONSE_SINKS = frozenset(
    [
        "JSONResponse",
        "HTMLResponse",
        "PlainTextResponse",
        "StreamingResponse",
        "FileResponse",
        "RedirectResponse",
    ]
)


FASTAPI_INPUT_SOURCES = frozenset(
    [
        "Request",
        "Body",
        "Query",
        "Path",
        "Form",
        "File",
        "Header",
        "Cookie",
        "Depends",
        "UploadFile",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect FastAPI security vulnerabilities using indexed data.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        fastapi_files = _get_fastapi_files(db)
        if not fastapi_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_check_sync_in_async(db))
        findings.extend(_check_no_dependency_injection(db))
        findings.extend(_check_missing_cors(db, fastapi_files))
        findings.extend(_check_blocking_file_ops(db))
        findings.extend(_check_raw_sql_in_routes(db))
        findings.extend(_check_background_task_errors(db))
        findings.extend(_check_websocket_auth(db))
        findings.extend(_check_debug_endpoints(db))
        findings.extend(_check_path_traversal(db))
        findings.extend(_check_missing_timeout(db, fastapi_files))
        findings.extend(_check_missing_exception_handlers(db))
        findings.extend(_check_pydantic_mass_assignment(db))
        findings.extend(_check_insecure_deserialization(db))
        findings.extend(_check_ssrf(db))
        findings.extend(_check_jwt_vulnerabilities(db))
        findings.extend(_check_missing_rate_limiting(db, fastapi_files))
        findings.extend(_check_missing_security_headers(db, fastapi_files))
        findings.extend(_check_missing_csrf(db, fastapi_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_fastapi_files(db: RuleDB) -> list[str]:
    """Get files that import FastAPI."""
    rows = db.query(Q("refs").select("src").where("value IN (?, ?)", "fastapi", "FastAPI"))
    return list({row[0] for row in rows})


def _check_sync_in_async(db: RuleDB) -> list[StandardFinding]:
    """Check for blocking sync operations in routes."""
    findings = []

    sync_ops_list = list(SYNC_OPERATIONS)
    placeholders = ",".join("?" * len(sync_ops_list))

    sql, params = Q.raw(
        f"""
        SELECT DISTINCT file, line, callee_function
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

    for file, line, sync_op in rows:
        findings.append(
            StandardFinding(
                rule_name="fastapi-sync-in-async",
                message=f"Blocking operation {sync_op} in route handler may block event loop",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="performance",
                confidence=Confidence.MEDIUM,
                snippet=f"Use async alternative for {sync_op}",
                cwe_id="CWE-400",
            )
        )

    return findings


def _check_no_dependency_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for direct database access without dependency injection.

    Improved to:
    1. Support SessionDep (SQLModel pattern) alongside Depends
    2. Check per-function granularity, not just file-level
    """
    findings = []

    sql, params = Q.raw(
        """
        SELECT DISTINCT file, line, callee_function, caller_function
        FROM function_call_args
        WHERE EXISTS (
            SELECT 1 FROM api_endpoints e
            WHERE e.file = function_call_args.file
        )
        AND (callee_function LIKE '%.query%'
             OR callee_function LIKE '%.execute%'
             OR callee_function LIKE 'db.%'
             OR callee_function LIKE 'session.%')
        ORDER BY file, line
        """,
        [],
    )
    db_access_rows = list(db.execute(sql, params))

    di_sql, di_params = Q.raw(
        """
        SELECT DISTINCT file, caller_function, callee_function
        FROM function_call_args
        WHERE callee_function IN ('Depends', 'SessionDep')
           OR argument_expr LIKE '%SessionDep%'
           OR argument_expr LIKE '%Depends%'
        """,
        [],
    )
    di_rows = list(db.execute(di_sql, di_params))

    di_functions = set()
    di_files = set()
    for file, caller, _callee in di_rows:
        if caller:
            di_functions.add((file, caller))
        di_files.add(file)

    seen = set()
    for file, line, callee, caller in db_access_rows:
        key = (file, line, callee)
        if key in seen:
            continue
        seen.add(key)

        if caller and (file, caller) in di_functions:
            continue

        if not caller and file in di_files:
            continue

        findings.append(
            StandardFinding(
                rule_name="fastapi-no-dependency-injection",
                message=f"Direct database access ({callee}) without dependency injection",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="architecture",
                confidence=Confidence.MEDIUM,
                snippet="Use Depends() or SessionDep for database session management",
                cwe_id="CWE-1061",
            )
        )

    return findings


def _check_missing_cors(db: RuleDB, fastapi_files: list[str]) -> list[StandardFinding]:
    """Check for missing CORS middleware."""
    findings = []

    rows = db.query(Q("refs").select("value").where("value = ?", "CORSMiddleware").limit(1))
    if list(rows):
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("callee_function")
        .where("callee_function = ?", "FastAPI")
        .limit(1)
    )
    if not list(rows):
        return findings

    if fastapi_files:
        findings.append(
            StandardFinding(
                rule_name="fastapi-missing-cors",
                message="FastAPI application without CORS middleware configuration",
                file_path=fastapi_files[0],
                line=1,
                severity=Severity.MEDIUM,
                category="security",
                confidence=Confidence.MEDIUM,
                snippet="Add CORSMiddleware to handle cross-origin requests",
                cwe_id="CWE-346",
            )
        )

    return findings


def _check_blocking_file_ops(db: RuleDB) -> list[StandardFinding]:
    """Check for blocking file I/O in routes without aiofiles."""
    findings = []

    sql, params = Q.raw(
        """
        SELECT DISTINCT file, line, callee_function
        FROM function_call_args
        WHERE callee_function = 'open'
        AND EXISTS (
            SELECT 1 FROM api_endpoints e
            WHERE e.file = function_call_args.file
        )
        AND NOT EXISTS (
            SELECT 1 FROM refs r
            WHERE r.src = function_call_args.file AND r.value = 'aiofiles'
        )
        ORDER BY file, line
        """,
        [],
    )
    rows = db.execute(sql, params)

    for file, line, _ in rows:
        findings.append(
            StandardFinding(
                rule_name="fastapi-blocking-file-io",
                message="Blocking file I/O without aiofiles may block event loop",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="performance",
                confidence=Confidence.LOW,
                snippet="Use aiofiles for async file operations",
                cwe_id="CWE-400",
            )
        )

    return findings


def _check_raw_sql_in_routes(db: RuleDB) -> list[StandardFinding]:
    """Check for raw SQL queries in route handlers."""
    findings = []

    sql_commands = ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE"]
    placeholders = ",".join("?" * len(sql_commands))

    sql, params = Q.raw(
        f"""
        SELECT DISTINCT file_path, line_number, command
        FROM sql_queries
        WHERE command IN ({placeholders})
        AND EXISTS (
            SELECT 1 FROM api_endpoints e
            WHERE e.file = sql_queries.file_path
        )
        ORDER BY file_path, line_number
        """,
        sql_commands,
    )
    rows = db.execute(sql, params)

    for file, line, sql_command in rows:
        findings.append(
            StandardFinding(
                rule_name="fastapi-raw-sql-in-route",
                message=f"Raw SQL {sql_command} in route handler - use ORM or repository pattern",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="architecture",
                confidence=Confidence.HIGH,
                snippet="Move SQL to repository layer with parameterized queries",
                cwe_id="CWE-1061",
            )
        )

    return findings


def _check_background_task_errors(db: RuleDB) -> list[StandardFinding]:
    """Check for background tasks without error handling."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "caller_function")
        .where("callee_function IN (?, ?)", "BackgroundTasks.add_task", "add_task")
        .order_by("file, line")
    )

    for file, line, _func in rows:
        error_rows = db.query(
            Q("cfg_blocks")
            .select("id")
            .where(
                "file = ? AND block_type IN (?, ?, ?) AND start_line BETWEEN ? AND ?",
                file,
                "try",
                "except",
                "finally",
                line - 20,
                line + 20,
            )
            .limit(1)
        )

        if not list(error_rows):
            findings.append(
                StandardFinding(
                    rule_name="fastapi-background-task-no-error-handling",
                    message="Background task without exception handling - failures will be silent",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="error-handling",
                    confidence=Confidence.MEDIUM,
                    snippet="Wrap background task in try/except with logging",
                    cwe_id="CWE-248",
                )
            )

    return findings


def _check_websocket_auth(db: RuleDB) -> list[StandardFinding]:
    """Check for WebSocket endpoints without authentication."""
    findings = []

    rows = db.query(
        Q("api_endpoints")
        .select("file", "pattern")
        .where("pattern LIKE ? OR pattern LIKE ?", "%websocket%", "%ws%")
    )

    for file, pattern in rows:
        auth_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where(
                "file = ? AND (callee_function LIKE ? OR callee_function LIKE ? OR callee_function LIKE ? OR callee_function LIKE ?)",
                file,
                "%auth%",
                "%verify%",
                "%current_user%",
                "%token%",
            )
            .limit(1)
        )

        if not list(auth_rows):
            findings.append(
                StandardFinding(
                    rule_name="fastapi-websocket-no-auth",
                    message=f"WebSocket endpoint {pattern} without authentication",
                    file_path=file,
                    line=1,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    snippet="Add authentication check to WebSocket handler",
                    cwe_id="CWE-306",
                )
            )

    return findings


def _check_debug_endpoints(db: RuleDB) -> list[StandardFinding]:
    """Check for debug endpoints exposed in production."""
    findings = []

    debug_list = list(DEBUG_ENDPOINTS)

    for debug_pattern in debug_list:
        rows = db.query(
            Q("api_endpoints")
            .select("file", "pattern", "method")
            .where("pattern = ? OR pattern LIKE ?", debug_pattern, f"%{debug_pattern}%")
        )

        for file, pattern, _method in rows:
            findings.append(
                StandardFinding(
                    rule_name="fastapi-debug-endpoint-exposed",
                    message=f"Debug endpoint {pattern} exposed - should not be in production",
                    file_path=file,
                    line=1,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet="Remove or protect debug endpoints in production",
                    cwe_id="CWE-489",
                )
            )

    return findings


def _check_path_traversal(db: RuleDB) -> list[StandardFinding]:
    """Check for path traversal risks in file upload handlers."""
    findings = []

    form_funcs = ["Form", "File", "UploadFile"]
    file_funcs = ["open", "Path", "os.path.join"]
    form_placeholders = ",".join("?" * len(form_funcs))
    file_placeholders = ",".join("?" * len(file_funcs))

    sql, params = Q.raw(
        f"""
        SELECT DISTINCT file, line
        FROM function_call_args
        WHERE callee_function IN ({form_placeholders})
        AND EXISTS (
            SELECT 1 FROM function_call_args f2
            WHERE f2.file = function_call_args.file
            AND f2.callee_function IN ({file_placeholders})
            AND f2.line > function_call_args.line
            AND f2.line < function_call_args.line + 20
        )
        ORDER BY file, line
        """,
        form_funcs + file_funcs,
    )
    rows = db.execute(sql, params)

    for file, line in rows:
        findings.append(
            StandardFinding(
                rule_name="fastapi-path-traversal-risk",
                message="Form/file data used in file operations - validate and sanitize paths",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="injection",
                confidence=Confidence.MEDIUM,
                snippet="Use secure_filename() and validate upload paths",
                cwe_id="CWE-22",
            )
        )

    return findings


def _check_missing_timeout(db: RuleDB, fastapi_files: list[str]) -> list[StandardFinding]:
    """Check for missing request timeout configuration."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "argument_expr")
        .where("callee_function = ?", "FastAPI")
    )

    has_timeout = any("timeout" in (arg_expr or "") for _, arg_expr in rows)
    if has_timeout:
        return findings

    rows = db.query(
        Q("refs").select("value").where("value IN (?, ?)", "slowapi", "timeout_middleware").limit(1)
    )

    if not list(rows) and fastapi_files:
        findings.append(
            StandardFinding(
                rule_name="fastapi-missing-timeout",
                message="FastAPI application without request timeout configuration",
                file_path=fastapi_files[0],
                line=1,
                severity=Severity.MEDIUM,
                category="availability",
                confidence=Confidence.MEDIUM,
                snippet="Add timeout middleware or configure request timeouts",
                cwe_id="CWE-400",
            )
        )

    return findings


def _check_missing_exception_handlers(db: RuleDB) -> list[StandardFinding]:
    """Check for routes without exception handlers."""
    findings = []

    exception_funcs = ["HTTPException", "exception_handler", "add_exception_handler"]
    exception_placeholders = ",".join("?" * len(exception_funcs))

    sql, params = Q.raw(
        f"""
        SELECT DISTINCT file
        FROM api_endpoints
        WHERE NOT EXISTS (
            SELECT 1 FROM function_call_args f
            WHERE f.file = api_endpoints.file
            AND f.callee_function IN ({exception_placeholders})
        )
        LIMIT 5
        """,
        exception_funcs,
    )
    rows = db.execute(sql, params)

    for (file,) in rows:
        findings.append(
            StandardFinding(
                rule_name="fastapi-no-exception-handler",
                message="API routes without exception handlers - may leak error details",
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category="error-handling",
                confidence=Confidence.LOW,
                snippet="Add exception handlers to prevent info leakage",
                cwe_id="CWE-209",
            )
        )

    return findings


def _check_pydantic_mass_assignment(db: RuleDB) -> list[StandardFinding]:
    """Check for Pydantic models without extra='forbid' allowing mass assignment.

    Supports both Pydantic v1 (class Config) and v2 (model_config = ConfigDict).
    """
    findings = []

    rows = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("type = ? AND name LIKE ?", "class", "%Model%")
        .order_by("path, line")
    )

    for file, line, class_name in rows:
        base_rows = db.query(
            Q("refs")
            .select("value")
            .where("src = ? AND value IN (?, ?, ?)", file, "BaseModel", "pydantic", "Pydantic")
            .limit(1)
        )
        if not list(base_rows):
            continue

        has_extra_forbid = False

        config_rows = db.query(
            Q("symbols")
            .select("name")
            .where(
                "path = ? AND line BETWEEN ? AND ? AND name = ?", file, line, line + 30, "Config"
            )
            .limit(1)
        )
        if list(config_rows):
            extra_rows = db.query(
                Q("assignments")
                .select("source_expr")
                .where(
                    "file = ? AND line BETWEEN ? AND ? AND target_var = ?",
                    file,
                    line,
                    line + 30,
                    "extra",
                )
                .limit(1)
            )
            for (source_expr,) in extra_rows:
                if source_expr and "forbid" in source_expr.lower():
                    has_extra_forbid = True
                    break

        if not has_extra_forbid:
            model_config_rows = db.query(
                Q("assignments")
                .select("source_expr")
                .where(
                    "file = ? AND line BETWEEN ? AND ? AND target_var = ?",
                    file,
                    line,
                    line + 30,
                    "model_config",
                )
                .limit(1)
            )
            for (source_expr,) in model_config_rows:
                if source_expr and "forbid" in source_expr.lower():
                    has_extra_forbid = True
                    break

        if not has_extra_forbid:
            findings.append(
                StandardFinding(
                    rule_name="fastapi-pydantic-mass-assignment",
                    message=f"Pydantic model {class_name} without extra='forbid' - mass assignment risk",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="security",
                    confidence=Confidence.LOW,
                    snippet="Add model_config = ConfigDict(extra='forbid') or class Config with extra='forbid'",
                    cwe_id="CWE-915",
                )
            )

    return findings


def _check_insecure_deserialization(db: RuleDB) -> list[StandardFinding]:
    """Check for insecure deserialization vulnerabilities."""
    findings = []

    dangerous_funcs = (
        "pickle.loads",
        "pickle.load",
        "cPickle.loads",
        "cPickle.load",
        "yaml.load",
        "yaml.unsafe_load",
        "marshal.loads",
        "marshal.load",
        "shelve.open",
    )
    placeholders = ",".join("?" * len(dangerous_funcs))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *dangerous_funcs)
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        user_input_patterns = ("request", "Body", "Query", "Path", "Form", "File", "Header")
        has_user_input = any(pattern in arg_expr for pattern in user_input_patterns)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="fastapi-insecure-deserialization",
                    message=f"Insecure deserialization via {callee} with user input - RCE risk",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                    cwe_id="CWE-502",
                )
            )
        elif "yaml.load" in callee and "Loader" not in arg_expr:
            findings.append(
                StandardFinding(
                    rule_name="fastapi-unsafe-yaml-load",
                    message="yaml.load without safe Loader parameter - code execution risk",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet="Use yaml.safe_load() or specify Loader=yaml.SafeLoader",
                    cwe_id="CWE-502",
                )
            )

    return findings


def _check_ssrf(db: RuleDB) -> list[StandardFinding]:
    """Check for Server-Side Request Forgery vulnerabilities."""
    findings = []

    http_funcs = (
        "httpx.get",
        "httpx.post",
        "httpx.put",
        "httpx.delete",
        "httpx.request",
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "aiohttp.ClientSession",
        "urllib.request.urlopen",
    )
    placeholders = ",".join("?" * len(http_funcs))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            f"callee_function IN ({placeholders}) OR callee_function LIKE ?", *http_funcs, "%http%"
        )
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        user_input_patterns = ("request", "Query", "Path", "Body", "Header")
        for pattern in user_input_patterns:
            if pattern in arg_expr:
                findings.append(
                    StandardFinding(
                        rule_name="fastapi-ssrf",
                        message=f"SSRF vulnerability - user input controls URL in {callee}",
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


def _check_jwt_vulnerabilities(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT implementation vulnerabilities."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ? OR callee_function LIKE ?", "%jwt%decode%", "%decode%jwt%")
        .order_by("file, line")
    )

    for file, line, _callee, arg_expr in rows:
        arg_expr = arg_expr or ""
        arg_lower = arg_expr.lower()

        issues = []

        if "algorithms" not in arg_lower and "algorithm" not in arg_lower:
            issues.append("no algorithm specified (algorithm confusion attack)")
        if "none" in arg_lower:
            issues.append("'none' algorithm allowed")

        if "verify=false" in arg_lower or "verify_signature=false" in arg_lower:
            issues.append("signature verification disabled")

        if "options" in arg_lower and "verify_exp" in arg_lower and "false" in arg_lower:
            issues.append("expiry verification disabled")

        if issues:
            findings.append(
                StandardFinding(
                    rule_name="fastapi-jwt-vulnerability",
                    message=f"JWT vulnerability: {', '.join(issues)}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    confidence=Confidence.HIGH,
                    snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                    cwe_id="CWE-347",
                )
            )

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var LIKE ? OR target_var LIKE ?", "%SECRET%", "%JWT%KEY%")
        .order_by("file, line")
    )

    for file, line, var, value in rows:
        value = value or ""

        if ('"' in value or "'" in value) and "environ" not in value and "getenv" not in value:
            clean_value = value.strip("\"'")
            if len(clean_value) < 32:
                findings.append(
                    StandardFinding(
                        rule_name="fastapi-jwt-weak-secret",
                        message=f"Weak/hardcoded JWT secret ({len(clean_value)} chars)",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="authentication",
                        confidence=Confidence.HIGH,
                        snippet=f"{var} = {value[:30]}...",
                        cwe_id="CWE-798",
                    )
                )

    return findings


def _check_missing_rate_limiting(db: RuleDB, fastapi_files: list[str]) -> list[StandardFinding]:
    """Check for missing rate limiting on authentication endpoints."""
    findings = []

    rows = db.query(
        Q("refs")
        .select("value")
        .where("value IN (?, ?, ?)", "slowapi", "fastapi-limiter", "ratelimit")
        .limit(1)
    )
    if list(rows):
        return findings

    rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "pattern", "method")
        .where("pattern LIKE ? OR pattern LIKE ? OR pattern LIKE ?", "%login%", "%auth%", "%token%")
        .order_by("file, line")
    )

    auth_endpoints = list(rows)
    if auth_endpoints and fastapi_files:
        findings.append(
            StandardFinding(
                rule_name="fastapi-missing-rate-limit",
                message="Authentication endpoints without rate limiting - brute force risk",
                file_path=auth_endpoints[0][0],
                line=auth_endpoints[0][1],
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.MEDIUM,
                snippet="Add slowapi or fastapi-limiter for rate limiting",
                cwe_id="CWE-307",
            )
        )

    return findings


def _check_missing_security_headers(db: RuleDB, fastapi_files: list[str]) -> list[StandardFinding]:
    """Check for missing security headers middleware."""
    findings = []

    security_middleware = ("secure-headers", "starlette-secure-headers", "fastapi-security-headers")
    for middleware in security_middleware:
        rows = db.query(Q("refs").select("value").where("value = ?", middleware).limit(1))
        if list(rows):
            return findings

    rows = db.query(
        Q("function_call_args")
        .select("argument_expr")
        .where("callee_function LIKE ? AND argument_expr LIKE ?", "%Middleware%", "%header%")
        .limit(1)
    )
    if list(rows):
        return findings

    if fastapi_files:
        findings.append(
            StandardFinding(
                rule_name="fastapi-missing-security-headers",
                message="FastAPI application without security headers middleware",
                file_path=fastapi_files[0],
                line=1,
                severity=Severity.MEDIUM,
                category="security",
                confidence=Confidence.MEDIUM,
                snippet="Add X-Content-Type-Options, X-Frame-Options, CSP headers",
                cwe_id="CWE-693",
            )
        )

    return findings


def _check_missing_csrf(db: RuleDB, fastapi_files: list[str]) -> list[StandardFinding]:
    """Check for missing CSRF protection on cookie-authenticated endpoints.

    FastAPI has no built-in CSRF protection (unlike Flask/Django).
    Apps using cookie-based authentication need starlette-csrf or fastapi-csrf-protect.
    JWT-only APIs are CSRF-immune and don't need this check.
    """
    findings = []

    if not fastapi_files:
        return findings

    csrf_libs = ("starlette-csrf", "fastapi-csrf-protect", "csrf", "CSRFProtect")
    for lib in csrf_libs:
        rows = db.query(Q("refs").select("value").where("value = ?", lib).limit(1))
        if list(rows):
            return findings

    cookie_auth_indicators = ("cookie", "session", "SESSION_COOKIE", "set_cookie")
    has_cookie_auth = False

    for indicator in cookie_auth_indicators:
        rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where(
                "callee_function LIKE ? OR argument_expr LIKE ?", f"%{indicator}%", f"%{indicator}%"
            )
            .limit(1)
        )
        if list(rows):
            has_cookie_auth = True
            break

    if not has_cookie_auth:
        rows = db.query(
            Q("assignments")
            .select("target_var")
            .where("target_var LIKE ? OR source_expr LIKE ?", "%cookie%", "%cookie%")
            .limit(1)
        )
        if list(rows):
            has_cookie_auth = True

    if has_cookie_auth:
        rows = db.query(
            Q("api_endpoints")
            .select("file", "line", "method", "pattern")
            .where("method IN (?, ?, ?, ?)", "POST", "PUT", "DELETE", "PATCH")
            .limit(1)
        )
        state_changing = list(rows)

        if state_changing:
            findings.append(
                StandardFinding(
                    rule_name="fastapi-missing-csrf",
                    message="Cookie-authenticated FastAPI app without CSRF protection",
                    file_path=state_changing[0][0],
                    line=state_changing[0][1],
                    severity=Severity.HIGH,
                    category="csrf",
                    confidence=Confidence.MEDIUM,
                    snippet="Add starlette-csrf or fastapi-csrf-protect middleware",
                    cwe_id="CWE-352",
                )
            )

    return findings


def register_taint_patterns(taint_registry) -> None:
    """Register FastAPI-specific taint patterns for taint tracking engine.

    Args:
        taint_registry: The taint pattern registry to register patterns with
    """
    for pattern in FASTAPI_RESPONSE_SINKS:
        taint_registry.register_sink(pattern, "response", "python")

    for pattern in FASTAPI_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "python")
