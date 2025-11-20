"""SQL-based WebSocket security analyzer.

This module detects WebSocket security issues by querying the indexed database
instead of traversing AST structures.
"""
from __future__ import annotations


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


def find_websocket_issues(context: StandardRuleContext) -> list[StandardFinding]:
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


def _find_websocket_no_auth(cursor) -> list[StandardFinding]:
    """Find WebSocket connections without authentication."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
        ORDER BY file, line
    """)

    # Filter for WebSocket connection patterns in Python
    websocket_handlers = []
    for row in cursor.fetchall():
        file, line, func, args = row
        # Check if function matches any connection pattern
        if any(pattern in func for pattern in CONNECTION_PATTERNS):
            websocket_handlers.append((file, line, func, args))

    for file, line, func, args in websocket_handlers:
        # Check if authentication is performed nearby (within ±30 lines)
        cursor.execute("""
            SELECT callee_function, line
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
        """, (file,))

        # Filter in Python for auth patterns and line proximity
        nearby_auth = []
        for callee, func_line in cursor.fetchall():
            if line - 30 <= func_line <= line + 30:
                if any(auth in callee for auth in AUTH_PATTERNS):
                    nearby_auth.append((callee, func_line))

        has_auth = len(nearby_auth) > 0

        # Also check for auth-related variables
        if not has_auth:
            cursor.execute("""
                SELECT name, line
                FROM symbols
                WHERE path = ?
                  AND name IS NOT NULL
            """, (file,))

            # Filter in Python for auth patterns and line proximity
            nearby_sym = []
            for name, sym_line in cursor.fetchall():
                if line - 30 <= sym_line <= line + 30:
                    if any(auth in name for auth in AUTH_PATTERNS):
                        nearby_sym.append((name, sym_line))

            has_auth = len(nearby_sym) > 0

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
        SELECT path AS file, line, name
        FROM symbols
        WHERE type = 'function'
          AND name IS NOT NULL
    """)

    # Filter in Python for WebSocket handler name patterns
    handler_patterns = ['websocket', 'ws_handler', 'socket_handler', 'on_connect']
    python_handlers = []
    for row in cursor.fetchall():
        file, line, name = row
        name_lower = name.lower()
        if any(pattern in name_lower for pattern in handler_patterns):
            python_handlers.append((file, line, name))

    for file, line, name in python_handlers:
        # Check for auth in function body
        cursor.execute("""
            SELECT callee_function, line
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
        """, (file,))

        # Filter in Python for auth patterns and line range
        auth_in_body = []
        for callee, func_line in cursor.fetchall():
            if line <= func_line <= line + 50:
                if any(auth in callee for auth in AUTH_PATTERNS):
                    auth_in_body.append((callee, func_line))

        has_auth = len(auth_in_body) > 0

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


def _find_websocket_no_validation(cursor) -> list[StandardFinding]:
    """Find WebSocket message handlers without validation."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
    """)

    # Filter for message handler patterns in Python
    message_handlers = []
    for row in cursor.fetchall():
        file, line, func, args = row
        if any(pattern in func for pattern in MESSAGE_PATTERNS):
            message_handlers.append((file, line, func, args))

    for file, line, func, args in message_handlers:
        # Check for validation nearby
        cursor.execute("""
            SELECT callee_function, line
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
        """, (file,))

        # Filter in Python for validation patterns and line range
        validation_nearby = []
        for callee, func_line in cursor.fetchall():
            if line <= func_line <= line + 20:
                if any(val in callee for val in VALIDATION_PATTERNS):
                    validation_nearby.append((callee, func_line))

        has_validation = len(validation_nearby) > 0

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
        SELECT path AS file, line, name
        FROM symbols
        WHERE type = 'function'
          AND name IS NOT NULL
    """)

    # Filter in Python for message handler patterns
    msg_handler_patterns = ['message', 'recv', 'receive', 'on_data']
    python_message_handlers = []
    for row in cursor.fetchall():
        file, line, name = row
        name_lower = name.lower()
        if any(pattern in name_lower for pattern in msg_handler_patterns):
            python_message_handlers.append((file, line, name))

    for file, line, name in python_message_handlers:
        # Check for validation in function
        cursor.execute("""
            SELECT callee_function, line
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
        """, (file,))

        # Filter in Python for validation patterns and line range
        py_validation_nearby = []
        for callee, func_line in cursor.fetchall():
            if line <= func_line <= line + 30:
                if any(val in callee for val in VALIDATION_PATTERNS):
                    py_validation_nearby.append((callee, func_line))

        has_validation = len(py_validation_nearby) > 0

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


def _find_websocket_no_rate_limit(cursor) -> list[StandardFinding]:
    """Find WebSocket handlers without rate limiting."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT DISTINCT file, callee_function
        FROM function_call_args
        WHERE callee_function IS NOT NULL
    """)

    # Find files with WebSocket message handlers
    message_keywords = ['message', 'recv', 'on("message")', 'onmessage']
    ws_files = set()
    for file, callee in cursor.fetchall():
        callee_lower = callee.lower()
        if any(kw in callee_lower for kw in message_keywords):
            ws_files.add(file)

    for file in ws_files:
        # Check if file has any rate limiting
        cursor.execute("""
            SELECT callee_function
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
            LIMIT 100
        """, (file,))

        # Filter in Python for rate limit patterns
        has_rate_limit = False
        for (callee,) in cursor.fetchall():
            if any(rl in callee for rl in RATE_LIMIT_PATTERNS):
                has_rate_limit = True
                break

        # Also check for rate limiting variables/imports
        if not has_rate_limit:
            cursor.execute("""
                SELECT name
                FROM symbols
                WHERE path = ?
                  AND name IS NOT NULL
                LIMIT 100
            """, (file,))

            # Filter in Python for rate limit patterns
            for (name,) in cursor.fetchall():
                if any(rl in name for rl in RATE_LIMIT_PATTERNS):
                    has_rate_limit = True
                    break

        if not has_rate_limit:
            # Get first message handler location
            cursor.execute("""
                SELECT line
                FROM function_call_args
                WHERE file = ?
                  AND callee_function IS NOT NULL
            """, (file,))

            # Filter in Python for message handlers and get min line
            all_lines = []
            for (func_line,) in cursor.fetchall():
                # Re-fetch callee to check
                cursor.execute("SELECT callee_function FROM function_call_args WHERE file = ? AND line = ? LIMIT 1", (file, func_line))
                callee_row = cursor.fetchone()
                if callee_row:
                    callee = callee_row[0]
                    callee_lower = callee.lower()
                    if 'message' in callee_lower or 'recv' in callee_lower:
                        all_lines.append(func_line)

            line = min(all_lines) if all_lines else 0

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


def _find_websocket_broadcast_sensitive(cursor) -> list[StandardFinding]:
    """Find broadcasting of sensitive data via WebSocket."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
    """)

    # Filter for broadcast patterns in Python
    broadcasts = []
    for row in cursor.fetchall():
        file, line, func, args = row
        if any(bc in func for bc in BROADCAST_PATTERNS):
            broadcasts.append((file, line, func, args))

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
            # Check if broadcasting variables that might contain sensitive data
            # First, extract variable names from broadcast arguments
            broadcast_vars = []
            if args:
                # Simple extraction of potential variable names (alphanumeric tokens)
                import re
                potential_vars = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', args)
                broadcast_vars = potential_vars

            if broadcast_vars:
                # Check if these variables are assigned from sensitive sources
                cursor.execute("""
                    SELECT target_var, source_expr
                    FROM assignments
                    WHERE file = ?
                      AND line < ?
                      AND target_var IS NOT NULL
                      AND source_expr IS NOT NULL
                """, (file, line))

                # Filter in Python for sensitive patterns
                sensitive_vars = []
                for var, expr in cursor.fetchall():
                    if var in broadcast_vars:
                        expr_lower = expr.lower()
                        if any(sens in expr_lower for sens in SENSITIVE_PATTERNS):
                            sensitive_vars.append((var, expr))

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


def _find_websocket_no_tls(cursor) -> list[StandardFinding]:
    """Find WebSocket connections without TLS (ws:// instead of wss://)."""
    findings = []

    # Find WebSocket URLs in assignments (where URL strings are stored)
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
    """)

    # Filter in Python for ws:// URLs that are not localhost
    insecure_urls = []
    for file, line, var, expr in cursor.fetchall():
        if not expr:
            continue
        # Check for ws:// (but not wss://)
        if 'ws://' not in expr or 'wss://' in expr:
            continue
        # Exclude localhost and 127.0.0.1
        if 'ws://localhost' in expr or 'ws://127.0.0.1' in expr:
            continue
        insecure_urls.append((file, line, var, expr))

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
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
    """)

    # Filter in Python for WebSocket server patterns without TLS
    unencrypted_servers = []
    for file, line, func, args in cursor.fetchall():
        # Check if function is WebSocket server
        if not ('WebSocketServer' in func or 'ws.Server' in func):
            continue
        # Check if args are NULL or missing TLS indicators
        if args is None:
            unencrypted_servers.append((file, line, func, args))
        else:
            # Check if args do NOT contain TLS/SSL/HTTPS
            if 'https' not in args and 'tls' not in args and 'ssl' not in args:
                unencrypted_servers.append((file, line, func, args))

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


