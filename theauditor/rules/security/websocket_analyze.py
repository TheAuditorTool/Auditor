"""SQL-based WebSocket security analyzer.

This module detects WebSocket security issues by querying the indexed database
instead of traversing AST structures.
"""

import sqlite3
from typing import List, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# METADATA (Orchestrator Discovery)
# ============================================================================

METADATA = RuleMetadata(
    name="websocket_security",
    category="security",
    target_extensions=['.py', '.js', '.ts', '.jsx', '.tsx'],
    exclude_patterns=['test/', 'spec.', '__tests__/', 'node_modules/'],
    requires_jsx_pass=False
)

# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozensets)
# ============================================================================

# WebSocket connection patterns
CONNECTION_PATTERNS = frozenset([
    'WebSocket', 'WebSocketServer', 'ws.Server', 'io.Server',
    'socketio.Server', 'websocket.serve', 'websockets.serve',
    'on("connection")', 'on("connect")', 'onconnection', 'onconnect'
])

# Authentication patterns
AUTH_PATTERNS = frozenset([
    'auth', 'authenticate', 'verify', 'token', 'jwt', 'session',
    'passport', 'check_permission', 'validate_user', 'authorize'
])

# Message handling patterns
MESSAGE_PATTERNS = frozenset([
    'on("message")', 'onmessage', 'on_message', 'message_handler',
    'recv', 'receive', 'on("data")', 'ondata', 'handle_message'
])

# Validation patterns
VALIDATION_PATTERNS = frozenset([
    'validate', 'verify', 'check', 'schema', 'sanitize', 'clean',
    'joi', 'yup', 'zod', 'jsonschema', 'parse', 'assert'
])

# Rate limiting patterns
RATE_LIMIT_PATTERNS = frozenset([
    'rate', 'limit', 'throttle', 'quota', 'flood', 'spam',
    'cooldown', 'bucket', 'ratelimit', 'rate_limit'
])

# Broadcast patterns
BROADCAST_PATTERNS = frozenset([
    'broadcast', 'emit', 'send_all', 'publish', 'clients.forEach',
    'wss.clients', 'io.emit', 'socket.broadcast', 'sendToAll'
])

# Sensitive data patterns
SENSITIVE_PATTERNS = frozenset([
    'password', 'secret', 'token', 'key', 'auth', 'session',
    'email', 'ssn', 'credit', 'private', 'personal', 'confidential',
    'api_key', 'access_token', 'refresh_token'
])


def find_websocket_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """
    Detect WebSocket security issues using SQL queries.
    
    This function queries the indexed database to find:
    - WebSocket connections without authentication
    - Unvalidated message handling
    - Missing rate limiting on WebSocket messages
    - Broadcasting sensitive data to all clients
    
    Args:
        context: StandardRuleContext with database path
        
    Returns:
        List of StandardFinding objects
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()
        
        # Pattern 1: WebSocket without authentication handshake
        findings.extend(_find_websocket_no_auth(cursor))
        
        # Pattern 2: WebSocket message handling without validation
        findings.extend(_find_websocket_no_validation(cursor))
        
        # Pattern 3: WebSocket without rate limiting
        findings.extend(_find_websocket_no_rate_limit(cursor))
        
        # Pattern 4: Broadcasting sensitive data
        findings.extend(_find_websocket_broadcast_sensitive(cursor))
        
        # Pattern 5: Plain WebSocket without TLS
        findings.extend(_find_websocket_no_tls(cursor))
        
        conn.close()
        
    except Exception:
        pass  # Return empty findings on error
    
    return findings


def _find_websocket_no_auth(cursor) -> List[StandardFinding]:
    """Find WebSocket connections without authentication."""
    findings = []

    # Build static query with known pattern count - NO dynamic SQL
    conn_placeholders = ' OR '.join(['f.callee_function LIKE ?'] * len(CONNECTION_PATTERNS))
    conn_params = [f'%{p}%' for p in CONNECTION_PATTERNS]

    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({conn_placeholders})
        ORDER BY f.file, f.line
    """, conn_params)
    
    websocket_handlers = cursor.fetchall()

    for file, line, func, args in websocket_handlers:
        # Check if authentication is performed nearby (within ±30 lines)
        # Build static query - NO dynamic SQL
        auth_placeholders = ' OR '.join(['f2.callee_function LIKE ?'] * len(AUTH_PATTERNS))
        auth_params = [file, line - 30, line + 30] + [f'%{auth}%' for auth in AUTH_PATTERNS]

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line BETWEEN ? AND ?
              AND ({auth_placeholders})
        """, auth_params)

        has_auth = cursor.fetchone()[0] > 0

        # Also check for auth-related variables
        if not has_auth:
            auth_sym_placeholders = ' OR '.join(['s.name LIKE ?'] * len(AUTH_PATTERNS))
            auth_sym_params = [file, line - 30, line + 30] + [f'%{auth}%' for auth in AUTH_PATTERNS]

            cursor.execute(f"""
                SELECT COUNT(*)
                FROM symbols s
                WHERE s.path = ?
                  AND s.line BETWEEN ? AND ?
                  AND ({auth_sym_placeholders})
            """, auth_sym_params)

            has_auth = cursor.fetchone()[0] > 0

        if not has_auth:
            findings.append(StandardFinding(
                rule_name='websocket-no-auth-handshake',
                message='WebSocket connection handler without authentication',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}("connection", ...)',
                cwe_id='CWE-862'
            ))
    
    # Check for Python async WebSocket handlers
    cursor.execute("""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.type = 'function'
          AND (s.name LIKE '%websocket%' OR s.name LIKE '%ws_handler%'
               OR s.name LIKE '%socket_handler%' OR s.name LIKE '%on_connect%')
    """)

    python_handlers = cursor.fetchall()

    for file, line, name in python_handlers:
        # Check for auth in function body - static query
        py_auth_placeholders = ' OR '.join(['f.callee_function LIKE ?'] * len(AUTH_PATTERNS))
        py_auth_params = [file, line, line + 50] + [f'%{auth}%' for auth in AUTH_PATTERNS]

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line BETWEEN ? AND ?
              AND ({py_auth_placeholders})
        """, py_auth_params)

        has_auth = cursor.fetchone()[0] > 0

        if not has_auth and ('connect' in name.lower() or 'handshake' in name.lower()):
            findings.append(StandardFinding(
                rule_name='websocket-no-auth-handshake',
                message=f'WebSocket handler {name} lacks authentication',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.MEDIUM,
                snippet=f'def {name}(...)',
                cwe_id='CWE-862'
            ))
    
    return findings


def _find_websocket_no_validation(cursor) -> List[StandardFinding]:
    """Find WebSocket message handlers without validation."""
    findings = []

    # Find message handlers - static query
    msg_placeholders = ' OR '.join(['f.callee_function LIKE ?'] * len(MESSAGE_PATTERNS))
    msg_params = [f'%{p}%' for p in MESSAGE_PATTERNS]

    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({msg_placeholders})
    """, msg_params)

    message_handlers = cursor.fetchall()

    for file, line, func, args in message_handlers:
        # Check for validation nearby - static query
        val_placeholders = ' OR '.join(['f2.callee_function LIKE ?'] * len(VALIDATION_PATTERNS))
        val_params = [file, line, line + 20] + [f'%{val}%' for val in VALIDATION_PATTERNS]

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line BETWEEN ? AND ?
              AND ({val_placeholders})
        """, val_params)

        has_validation = cursor.fetchone()[0] > 0

        if not has_validation:
            findings.append(StandardFinding(
                rule_name='websocket-no-message-validation',
                message='WebSocket message handler without input validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.LOW,
                snippet=f'{func}("message", ...)',
                cwe_id='CWE-20'
            ))
    
    # Check Python message handlers
    cursor.execute("""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.type = 'function'
          AND (s.name LIKE '%message%' OR s.name LIKE '%recv%'
               OR s.name LIKE '%receive%' OR s.name LIKE '%on_data%')
    """)

    python_message_handlers = cursor.fetchall()

    for file, line, name in python_message_handlers:
        # Check for validation in function - static query
        py_val_placeholders = ' OR '.join(['f.callee_function LIKE ?'] * len(VALIDATION_PATTERNS))
        py_val_params = [file, line, line + 30] + [f'%{val}%' for val in VALIDATION_PATTERNS]

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line BETWEEN ? AND ?
              AND ({py_val_placeholders})
        """, py_val_params)

        has_validation = cursor.fetchone()[0] > 0

        if not has_validation:
            findings.append(StandardFinding(
                rule_name='websocket-no-message-validation',
                message=f'WebSocket handler {name} lacks message validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.LOW,
                snippet=f'def {name}(...)',
                cwe_id='CWE-20'
            ))
    
    return findings


def _find_websocket_no_rate_limit(cursor) -> List[StandardFinding]:
    """Find WebSocket handlers without rate limiting."""
    findings = []

    # Find all WebSocket message handlers
    cursor.execute("""
        SELECT DISTINCT f.file
        FROM function_call_args f
        WHERE f.callee_function LIKE '%message%'
           OR f.callee_function LIKE '%recv%'
           OR f.callee_function LIKE '%on("message")%'
           OR f.callee_function LIKE '%onmessage%'
    """)

    ws_files = cursor.fetchall()

    for (file,) in ws_files:
        # Check if file has any rate limiting - static query
        rl_placeholders = ' OR '.join(['f.callee_function LIKE ?'] * len(RATE_LIMIT_PATTERNS))
        rl_params = [file] + [f'%{rl}%' for rl in RATE_LIMIT_PATTERNS]

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM function_call_args f
            WHERE f.file = ?
              AND ({rl_placeholders})
        """, rl_params)

        has_rate_limit = cursor.fetchone()[0] > 0

        # Also check for rate limiting variables/imports - static query
        if not has_rate_limit:
            rl_sym_placeholders = ' OR '.join(['s.name LIKE ?'] * len(RATE_LIMIT_PATTERNS))
            rl_sym_params = [file] + [f'%{rl}%' for rl in RATE_LIMIT_PATTERNS]

            cursor.execute(f"""
                SELECT COUNT(*)
                FROM symbols s
                WHERE s.path = ?
                  AND ({rl_sym_placeholders})
            """, rl_sym_params)

            has_rate_limit = cursor.fetchone()[0] > 0

        if not has_rate_limit:
            # Get first message handler location
            cursor.execute("""
                SELECT MIN(f.line)
                FROM function_call_args f
                WHERE f.file = ?
                  AND (f.callee_function LIKE '%message%' OR f.callee_function LIKE '%recv%')
            """, (file,))

            line = cursor.fetchone()[0] or 0

            findings.append(StandardFinding(
                rule_name='websocket-no-rate-limiting',
                message='WebSocket message handling without rate limiting',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.LOW,
                snippet='on("message", handler)',
                cwe_id='CWE-770'
            ))
    
    return findings


def _find_websocket_broadcast_sensitive(cursor) -> List[StandardFinding]:
    """Find broadcasting of sensitive data via WebSocket."""
    findings = []

    # Find broadcast operations - static query
    bc_placeholders = ' OR '.join(['f.callee_function LIKE ?'] * len(BROADCAST_PATTERNS))
    bc_params = [f'%{bc}%' for bc in BROADCAST_PATTERNS]

    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({bc_placeholders})
    """, bc_params)
    
    broadcasts = cursor.fetchall()

    for file, line, func, args in broadcasts:
        if not args:
            continue

        # Check if arguments contain sensitive data (simple pattern match)
        args_lower = args.lower() if args else ""
        contains_sensitive = any(sens in args_lower for sens in SENSITIVE_PATTERNS)

        if contains_sensitive:
            findings.append(StandardFinding(
                rule_name='websocket-broadcast-sensitive-data',
                message='Broadcasting potentially sensitive data via WebSocket',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}(sensitive_data)',
                cwe_id='CWE-200'
            ))
        else:
            # Check if broadcasting variables that might contain sensitive data - static query
            sens_placeholders = ' OR '.join(['a.source_expr LIKE ?'] * len(SENSITIVE_PATTERNS))
            sens_params = [file, line, file, line] + [f'%{sens}%' for sens in SENSITIVE_PATTERNS]

            cursor.execute(f"""
                SELECT a.target_var, a.source_expr
                FROM assignments a
                WHERE a.file = ?
                  AND a.line < ?
                  AND a.target_var IN (SELECT DISTINCT
                                         CASE
                                           WHEN instr(f2.argument_expr, a2.target_var) > 0
                                           THEN a2.target_var
                                         END
                                       FROM assignments a2, function_call_args f2
                                       WHERE f2.file = ? AND f2.line = ?)
                  AND ({sens_placeholders})
            """, sens_params)

            sensitive_vars = cursor.fetchall()

            if sensitive_vars:
                findings.append(StandardFinding(
                    rule_name='websocket-broadcast-sensitive-data',
                    message='Broadcasting variable containing sensitive data',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.MEDIUM,
                    snippet=f'{func}(variable)',
                    cwe_id='CWE-200'
                ))
    
    return findings


def _find_websocket_no_tls(cursor) -> List[StandardFinding]:
    """Find WebSocket connections without TLS (ws:// instead of wss://)."""
    findings = []

    # Find WebSocket URLs in assignments (where URL strings are stored)
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr LIKE '%ws://%'
          AND source_expr NOT LIKE '%wss://%'
          AND source_expr NOT LIKE '%ws://localhost%'
          AND source_expr NOT LIKE '%ws://127.0.0.1%'
    """)

    insecure_urls = cursor.fetchall()

    for file, line, var, expr in insecure_urls:
        findings.append(StandardFinding(
            rule_name='websocket-no-tls',
            message='WebSocket connection without TLS encryption',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            confidence=Confidence.HIGH,
            snippet=f'{var} = {expr[:50]}...' if len(expr) > 50 else f'{var} = {expr}',
            cwe_id='CWE-319'
        ))

    # Check for WebSocket server without TLS config
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%WebSocketServer%'
               OR f.callee_function LIKE '%ws.Server%')
          AND (f.argument_expr IS NULL
               OR (f.argument_expr NOT LIKE '%https%'
                   AND f.argument_expr NOT LIKE '%tls%'
                   AND f.argument_expr NOT LIKE '%ssl%'))
    """)

    unencrypted_servers = cursor.fetchall()

    for file, line, func, args in unencrypted_servers:
        findings.append(StandardFinding(
            rule_name='websocket-no-tls',
            message='WebSocket server without TLS configuration',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            confidence=Confidence.HIGH,
            snippet=f'{func}(...)',
            cwe_id='CWE-319'
        ))

    return findings


