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

# Blocking sync operations that should not be in async routes
SYNC_OPERATIONS = frozenset([
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
])

# Debug endpoint patterns that should not be in production
DEBUG_ENDPOINTS = frozenset([
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
])

# FastAPI response classes
FASTAPI_RESPONSE_SINKS = frozenset([
    "JSONResponse",
    "HTMLResponse",
    "PlainTextResponse",
    "StreamingResponse",
    "FileResponse",
    "RedirectResponse",
])

# FastAPI input sources
FASTAPI_INPUT_SOURCES = frozenset([
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
])


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

        # Check if this is a FastAPI project
        fastapi_files = _get_fastapi_files(db)
        if not fastapi_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        # Run all security checks
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

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_fastapi_files(db: RuleDB) -> list[str]:
    """Get files that import FastAPI."""
    rows = db.query(
        Q("refs")
        .select("src")
        .where("value IN (?, ?)", "fastapi", "FastAPI")
    )
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
    """Check for direct database access without dependency injection."""
    findings = []

    # Find files with API endpoints but no Depends usage
    sql, params = Q.raw(
        """
        SELECT DISTINCT file, line, callee_function
        FROM function_call_args
        WHERE EXISTS (
            SELECT 1 FROM api_endpoints e
            WHERE e.file = function_call_args.file
        )
        AND NOT EXISTS (
            SELECT 1 FROM function_call_args f2
            WHERE f2.file = function_call_args.file
            AND f2.callee_function = 'Depends'
        )
        AND (callee_function LIKE '%.query%'
             OR callee_function LIKE '%.execute%'
             OR callee_function LIKE 'db.%'
             OR callee_function LIKE 'session.%')
        ORDER BY file, line
        """,
        [],
    )
    rows = db.execute(sql, params)

    seen = set()
    for file, line, callee in rows:
        key = (file, line, callee)
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="fastapi-no-dependency-injection",
                message=f"Direct database access ({callee}) without dependency injection",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="architecture",
                confidence=Confidence.MEDIUM,
                snippet="Use Depends() for database session management",
                cwe_id="CWE-1061",
            )
        )

    return findings


def _check_missing_cors(db: RuleDB, fastapi_files: list[str]) -> list[StandardFinding]:
    """Check for missing CORS middleware."""
    findings = []

    # Check if CORSMiddleware is imported
    rows = db.query(
        Q("refs")
        .select("value")
        .where("value = ?", "CORSMiddleware")
        .limit(1)
    )
    if list(rows):
        return findings

    # Check if FastAPI app exists
    rows = db.query(
        Q("function_call_args")
        .select("callee_function")
        .where("callee_function = ?", "FastAPI")
        .limit(1)
    )
    if not list(rows):
        return findings

    # No CORS middleware found
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
        # Check if there's error handling nearby
        error_rows = db.query(
            Q("cfg_blocks")
            .select("id")
            .where("file = ? AND block_type IN (?, ?, ?) AND start_line BETWEEN ? AND ?",
                   file, "try", "except", "finally", line - 20, line + 20)
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
        # Check if file has authentication-related calls
        auth_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND (callee_function LIKE ? OR callee_function LIKE ? OR callee_function LIKE ? OR callee_function LIKE ?)",
                   file, "%auth%", "%verify%", "%current_user%", "%token%")
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

    # Check for exact matches and pattern matches
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

    # Check FastAPI constructor for timeout
    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "argument_expr")
        .where("callee_function = ?", "FastAPI")
    )

    has_timeout = any("timeout" in (arg_expr or "") for _, arg_expr in rows)
    if has_timeout:
        return findings

    # Check for timeout middleware
    rows = db.query(
        Q("refs")
        .select("value")
        .where("value IN (?, ?)", "slowapi", "timeout_middleware")
        .limit(1)
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


# TODO(quality): Missing detection patterns to add in future:
# - Pydantic model without extra="forbid" (mass assignment)
# - Insecure deserialization (pickle, yaml.unsafe_load)
# - SSRF via user-controlled URLs in httpx/requests
# - JWT vulnerabilities (weak algorithm, no expiry check)
# - Missing rate limiting on auth endpoints
# - Response validation disabled (response_model_exclude_unset)
# - Security headers missing (helmet equivalent for FastAPI)


def register_taint_patterns(taint_registry) -> None:
    """Register FastAPI-specific taint patterns for taint tracking engine.

    Args:
        taint_registry: The taint pattern registry to register patterns with
    """
    for pattern in FASTAPI_RESPONSE_SINKS:
        taint_registry.register_sink(pattern, "response", "python")

    for pattern in FASTAPI_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "python")
