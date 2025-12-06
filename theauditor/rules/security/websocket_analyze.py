"""WebSocket security analyzer using fidelity layer.

Detects WebSocket security issues:
- Missing authentication on connection handlers (CWE-862)
- Missing input validation on message handlers (CWE-20)
- Missing rate limiting on message handlers (CWE-770)
- Broadcasting sensitive data (CWE-200)
- Missing TLS encryption - ws:// instead of wss:// (CWE-319)
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
    name="websocket_security",
    category="security",
    target_extensions=[".py", ".js", ".ts", ".jsx", ".tsx"],
    exclude_patterns=["test/", "spec.", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="function_call_args",
)


CONNECTION_PATTERNS = frozenset(
    [
        "WebSocket",
        "WebSocketServer",
        "ws.Server",
        "io.Server",
        "socketio.Server",
        "websocket.serve",
        "websockets.serve",
        "onconnection",
        "onconnect",
        "on_connection",
        "on_connect",
        "WebSocketRoute",
        "websocket_route",
        "AsyncWebsocketConsumer",
        "WebsocketConsumer",
        "channels.routing",
        "websocket_endpoint",
        "WebSocketEndpoint",
        "connect",
        "websocket_connect",
        "sio.on",
        "socketio.on",
    ]
)


AUTH_PATTERNS = frozenset(
    [
        "auth",
        "authenticate",
        "verify",
        "token",
        "jwt",
        "session",
        "passport",
        "check_permission",
        "validate_user",
        "authorize",
        "is_authenticated",
        "require_auth",
        "login_required",
    ]
)


MESSAGE_PATTERNS = frozenset(
    [
        "onmessage",
        "on_message",
        "message_handler",
        "recv",
        "receive",
        "ondata",
        "on_data",
        "handle_message",
        "receive_json",
        "receive_text",
        "receive_bytes",
        "websocket_receive",
        "receive_text",
        "receive_bytes",
        "iter_text",
        "iter_bytes",
    ]
)


VALIDATION_PATTERNS = frozenset(
    [
        "validate",
        "verify",
        "check",
        "schema",
        "sanitize",
        "clean",
        "joi",
        "yup",
        "zod",
        "jsonschema",
        "parse",
        "assert",
        "pydantic",
        "marshmallow",
    ]
)


RATE_LIMIT_PATTERNS = frozenset(
    [
        "rate",
        "limit",
        "throttle",
        "quota",
        "flood",
        "spam",
        "cooldown",
        "bucket",
        "ratelimit",
        "rate_limit",
        "slowapi",
        "limiter",
    ]
)


BROADCAST_PATTERNS = frozenset(
    [
        "broadcast",
        "emit",
        "send_all",
        "publish",
        "clients.forEach",
        "wss.clients",
        "io.emit",
        "socket.broadcast",
        "sendToAll",
        "group_send",
        "channel_layer",
    ]
)


SENSITIVE_PATTERNS = frozenset(
    [
        "password",
        "secret",
        "token",
        "key",
        "auth",
        "session",
        "email",
        "ssn",
        "credit",
        "private",
        "personal",
        "confidential",
        "api_key",
        "access_token",
        "refresh_token",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect WebSocket security issues in indexed codebase.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_find_websocket_no_auth(db))
        findings.extend(_find_websocket_no_validation(db))
        findings.extend(_find_websocket_no_rate_limit(db))
        findings.extend(_find_websocket_broadcast_sensitive(db))
        findings.extend(_find_websocket_no_tls(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _find_websocket_no_auth(db: RuleDB) -> list[StandardFinding]:
    """Find WebSocket connections without authentication."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    websocket_handlers: list[tuple[str, int, str, str | None]] = []
    for file, line, func, args in rows:
        if any(pattern in func for pattern in CONNECTION_PATTERNS):
            websocket_handlers.append((file, line, func, args))

    for file, line, func, _args in websocket_handlers:
        nearby_calls = db.query(
            Q("function_call_args")
            .select("callee_function", "line")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
        )

        has_auth = False
        for callee, func_line in nearby_calls:
            if line - 30 <= func_line <= line + 30:
                if any(auth in callee.lower() for auth in AUTH_PATTERNS):
                    has_auth = True
                    break

        if not has_auth:
            nearby_symbols = db.query(
                Q("symbols")
                .select("name", "line")
                .where("path = ?", file)
                .where("name IS NOT NULL")
            )

            for name, sym_line in nearby_symbols:
                if line - 30 <= sym_line <= line + 30:
                    if any(auth in name.lower() for auth in AUTH_PATTERNS):
                        has_auth = True
                        break

        if not has_auth:
            findings.append(
                StandardFinding(
                    rule_name="websocket-no-auth-handshake",
                    message="WebSocket connection handler without authentication",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    snippet=f'{func}("connection", ...)',
                    cwe_id="CWE-862",
                )
            )

    handler_patterns = ["websocket", "ws_handler", "socket_handler", "on_connect"]
    python_handlers = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("type = ?", "function")
        .where("name IS NOT NULL")
    )

    for file, line, name in python_handlers:
        name_lower = name.lower()
        if not any(pattern in name_lower for pattern in handler_patterns):
            continue

        body_calls = db.query(
            Q("function_call_args")
            .select("callee_function", "line")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
        )

        has_auth = False
        for callee, func_line in body_calls:
            if line <= func_line <= line + 50:
                if any(auth in callee.lower() for auth in AUTH_PATTERNS):
                    has_auth = True
                    break

        if not has_auth and ("connect" in name_lower or "handshake" in name_lower):
            findings.append(
                StandardFinding(
                    rule_name="websocket-no-auth-handshake",
                    message=f"WebSocket handler {name} lacks authentication",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    snippet=f"def {name}(...)",
                    cwe_id="CWE-862",
                )
            )

    return findings


def _find_websocket_no_validation(db: RuleDB) -> list[StandardFinding]:
    """Find WebSocket message handlers without validation."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
    )

    message_handlers: list[tuple[str, int, str, str | None]] = []
    for file, line, func, args in rows:
        if any(pattern in func for pattern in MESSAGE_PATTERNS):
            message_handlers.append((file, line, func, args))

    for file, line, func, _args in message_handlers:
        nearby_calls = db.query(
            Q("function_call_args")
            .select("callee_function", "line")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
        )

        has_validation = False
        for callee, func_line in nearby_calls:
            if line <= func_line <= line + 20:
                if any(val in callee.lower() for val in VALIDATION_PATTERNS):
                    has_validation = True
                    break

        if not has_validation:
            findings.append(
                StandardFinding(
                    rule_name="websocket-no-message-validation",
                    message="WebSocket message handler without input validation",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.LOW,
                    snippet=f'{func}("message", ...)',
                    cwe_id="CWE-20",
                )
            )

    msg_handler_patterns = ["message", "recv", "receive", "on_data"]
    python_handlers = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("type = ?", "function")
        .where("name IS NOT NULL")
    )

    for file, line, name in python_handlers:
        name_lower = name.lower()
        if not any(pattern in name_lower for pattern in msg_handler_patterns):
            continue

        body_calls = db.query(
            Q("function_call_args")
            .select("callee_function", "line")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
        )

        has_validation = False
        for callee, func_line in body_calls:
            if line <= func_line <= line + 30:
                if any(val in callee.lower() for val in VALIDATION_PATTERNS):
                    has_validation = True
                    break

        if not has_validation:
            findings.append(
                StandardFinding(
                    rule_name="websocket-no-message-validation",
                    message=f"WebSocket handler {name} lacks message validation",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.LOW,
                    snippet=f"def {name}(...)",
                    cwe_id="CWE-20",
                )
            )

    return findings


def _find_websocket_no_rate_limit(db: RuleDB) -> list[StandardFinding]:
    """Find WebSocket handlers without rate limiting."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "callee_function", "line")
        .where("callee_function IS NOT NULL")
    )

    message_keywords = ["message", "recv", "onmessage", "on_message", "receive"]
    ws_file_lines: dict[str, int] = {}

    for file, callee, line in rows:
        callee_lower = callee.lower()
        if any(kw in callee_lower for kw in message_keywords):
            if file not in ws_file_lines or line < ws_file_lines[file]:
                ws_file_lines[file] = line

    for file, first_line in ws_file_lines.items():
        file_calls = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
            .limit(100)
        )

        has_rate_limit = False
        for (callee,) in file_calls:
            if any(rl in callee.lower() for rl in RATE_LIMIT_PATTERNS):
                has_rate_limit = True
                break

        if not has_rate_limit:
            file_symbols = db.query(
                Q("symbols")
                .select("name")
                .where("path = ?", file)
                .where("name IS NOT NULL")
                .limit(100)
            )

            for (name,) in file_symbols:
                if any(rl in name.lower() for rl in RATE_LIMIT_PATTERNS):
                    has_rate_limit = True
                    break

        if not has_rate_limit:
            findings.append(
                StandardFinding(
                    rule_name="websocket-no-rate-limiting",
                    message="WebSocket message handling without rate limiting",
                    file_path=file,
                    line=first_line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.LOW,
                    snippet='on("message", handler)',
                    cwe_id="CWE-770",
                )
            )

    return findings


def _find_websocket_broadcast_sensitive(db: RuleDB) -> list[StandardFinding]:
    """Find broadcasting of sensitive data via WebSocket."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
    )

    broadcasts: list[tuple[str, int, str, str | None]] = []
    for file, line, func, args in rows:
        if any(bc in func for bc in BROADCAST_PATTERNS):
            broadcasts.append((file, line, func, args))

    for file, line, func, args in broadcasts:
        if not args:
            continue

        args_lower = args.lower()
        contains_sensitive = any(sens in args_lower for sens in SENSITIVE_PATTERNS)

        if contains_sensitive:
            findings.append(
                StandardFinding(
                    rule_name="websocket-broadcast-sensitive-data",
                    message="Broadcasting potentially sensitive data via WebSocket",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}(sensitive_data)",
                    cwe_id="CWE-200",
                )
            )
        else:
            potential_vars = [
                word
                for word in args.replace("(", " ").replace(")", " ").replace(",", " ").split()
                if word.isidentifier()
            ]

            if potential_vars:
                assignments = db.query(
                    Q("assignments")
                    .select("target_var", "source_expr")
                    .where("file = ?", file)
                    .where("line < ?", line)
                    .where("target_var IS NOT NULL")
                    .where("source_expr IS NOT NULL")
                )

                sensitive_found = False
                for var, expr in assignments:
                    if var in potential_vars:
                        expr_lower = expr.lower()
                        if any(sens in expr_lower for sens in SENSITIVE_PATTERNS):
                            sensitive_found = True
                            break

                if sensitive_found:
                    findings.append(
                        StandardFinding(
                            rule_name="websocket-broadcast-sensitive-data",
                            message="Broadcasting variable containing sensitive data",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="security",
                            confidence=Confidence.MEDIUM,
                            snippet=f"{func}(variable)",
                            cwe_id="CWE-200",
                        )
                    )

    return findings


def _find_websocket_no_tls(db: RuleDB) -> list[StandardFinding]:
    """Find WebSocket connections without TLS (ws:// instead of wss://)."""
    findings: list[StandardFinding] = []

    assignments = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
    )

    for file, line, var, expr in assignments:
        if not expr:
            continue

        if "ws://" not in expr or "wss://" in expr:
            continue

        if "ws://localhost" in expr or "ws://127.0.0.1" in expr:
            continue

        findings.append(
            StandardFinding(
                rule_name="websocket-no-tls",
                message="WebSocket connection without TLS encryption",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.HIGH,
                snippet=f"{var} = {expr[:50]}..." if len(expr) > 50 else f"{var} = {expr}",
                cwe_id="CWE-319",
            )
        )

    server_calls = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
    )

    for file, line, func, args in server_calls:
        if "WebSocketServer" not in func and "ws.Server" not in func:
            continue

        if args is None or "https" not in args and "tls" not in args and "ssl" not in args:
            findings.append(
                StandardFinding(
                    rule_name="websocket-no-tls",
                    message="WebSocket server without TLS configuration",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}(...)",
                    cwe_id="CWE-319",
                )
            )

    return findings
