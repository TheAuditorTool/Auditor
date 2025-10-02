"""SQL-based WebSocket security analyzer.

This module detects WebSocket security issues by querying the indexed database
instead of traversing AST structures.
"""

import sqlite3
from typing import List, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


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
    
    # WebSocket connection patterns
    connection_patterns = [
        'WebSocket', 'WebSocketServer', 'ws.Server', 'io.Server',
        'socketio.Server', 'websocket.serve', 'websockets.serve',
        'on("connection")', 'on("connect")', 'onconnection', 'onconnect'
    ]
    
    # Authentication patterns
    auth_patterns = [
        'auth', 'authenticate', 'verify', 'token', 'jwt', 'session',
        'passport', 'check_permission', 'validate_user', 'authorize'
    ]
    
    # Find WebSocket server creation and connection handlers
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({})
        ORDER BY f.file, f.line
    """.format(' OR '.join([f"f.callee_function LIKE '%{pattern}%'" for pattern in connection_patterns])))
    
    websocket_handlers = cursor.fetchall()
    
    for file, line, func, args in websocket_handlers:
        # Check if authentication is performed nearby (within ±30 lines)
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line BETWEEN ? AND ?
              AND ({})
        """.format(' OR '.join([f"f2.callee_function LIKE '%{auth}%'" for auth in auth_patterns])),
        (file, line - 30, line + 30))
        
        has_auth = cursor.fetchone()[0] > 0
        
        # Also check for auth-related variables
        if not has_auth:
            cursor.execute("""
                SELECT COUNT(*)
                FROM symbols s
                WHERE s.path = ?
                  AND s.line BETWEEN ? AND ?
                  AND ({})
            """.format(' OR '.join([f"s.name LIKE '%{auth}%'" for auth in auth_patterns])),
            (file, line - 30, line + 30))
            
            has_auth = cursor.fetchone()[0] > 0
        
        if not has_auth:
            findings.append(StandardFinding(
                rule_name='websocket-no-auth-handshake',
                message='WebSocket connection handler without authentication',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
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
        # Check for auth in function body
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line BETWEEN ? AND ?
              AND ({})
        """.format(' OR '.join([f"f.callee_function LIKE '%{auth}%'" for auth in auth_patterns])),
        (file, line, line + 50))
        
        has_auth = cursor.fetchone()[0] > 0
        
        if not has_auth and ('connect' in name.lower() or 'handshake' in name.lower()):
            findings.append(StandardFinding(
                rule_name='websocket-no-auth-handshake',
                message=f'WebSocket handler {name} lacks authentication',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'def {name}(...)',
                cwe_id='CWE-862'
            ))
    
    return findings


def _find_websocket_no_validation(cursor) -> List[StandardFinding]:
    """Find WebSocket message handlers without validation."""
    findings = []
    
    # Message handling patterns
    message_patterns = [
        'on("message")', 'onmessage', 'on_message', 'message_handler',
        'recv', 'receive', 'on("data")', 'ondata', 'handle_message'
    ]
    
    # Validation patterns
    validation_patterns = [
        'validate', 'verify', 'check', 'schema', 'sanitize', 'clean',
        'joi', 'yup', 'zod', 'jsonschema', 'parse', 'assert'
    ]
    
    # Find message handlers
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({})
    """.format(' OR '.join([f"f.callee_function LIKE '%{pattern}%'" for pattern in message_patterns])))
    
    message_handlers = cursor.fetchall()
    
    for file, line, func, args in message_handlers:
        # Check for validation nearby
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line BETWEEN ? AND ?
              AND ({})
        """.format(' OR '.join([f"f2.callee_function LIKE '%{val}%'" for val in validation_patterns])),
        (file, line, line + 20))
        
        has_validation = cursor.fetchone()[0] > 0
        
        if not has_validation:
            findings.append(StandardFinding(
                rule_name='websocket-no-message-validation',
                message='WebSocket message handler without input validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
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
        # Check for validation in function
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line BETWEEN ? AND ?
              AND ({})
        """.format(' OR '.join([f"f.callee_function LIKE '%{val}%'" for val in validation_patterns])),
        (file, line, line + 30))
        
        has_validation = cursor.fetchone()[0] > 0
        
        if not has_validation:
            findings.append(StandardFinding(
                rule_name='websocket-no-message-validation',
                message=f'WebSocket handler {name} lacks message validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=f'def {name}(...)',
                cwe_id='CWE-20'
            ))
    
    return findings


def _find_websocket_no_rate_limit(cursor) -> List[StandardFinding]:
    """Find WebSocket handlers without rate limiting."""
    findings = []
    
    # Rate limiting patterns
    rate_limit_patterns = [
        'rate', 'limit', 'throttle', 'quota', 'flood', 'spam',
        'cooldown', 'bucket', 'ratelimit', 'rate_limit'
    ]
    
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
        # Check if file has any rate limiting
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f
            WHERE f.file = ?
              AND ({})
        """.format(' OR '.join([f"f.callee_function LIKE '%{rl}%'" for rl in rate_limit_patterns])),
        (file,))
        
        has_rate_limit = cursor.fetchone()[0] > 0
        
        # Also check for rate limiting variables/imports
        if not has_rate_limit:
            cursor.execute("""
                SELECT COUNT(*)
                FROM symbols s
                WHERE s.path = ?
                  AND ({})
            """.format(' OR '.join([f"s.name LIKE '%{rl}%'" for rl in rate_limit_patterns])),
            (file,))
            
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
                snippet='on("message", handler)',
                cwe_id='CWE-770'
            ))
    
    return findings


def _find_websocket_broadcast_sensitive(cursor) -> List[StandardFinding]:
    """Find broadcasting of sensitive data via WebSocket."""
    findings = []
    
    # Broadcast patterns
    broadcast_patterns = [
        'broadcast', 'emit', 'send_all', 'publish', 'clients.forEach',
        'wss.clients', 'io.emit', 'socket.broadcast', 'sendToAll'
    ]
    
    # Sensitive data patterns
    sensitive_patterns = [
        'password', 'secret', 'token', 'key', 'auth', 'session',
        'email', 'ssn', 'credit', 'private', 'personal', 'confidential',
        'api_key', 'access_token', 'refresh_token'
    ]
    
    # Find broadcast operations
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({})
    """.format(' OR '.join([f"f.callee_function LIKE '%{bc}%'" for bc in broadcast_patterns])))
    
    broadcasts = cursor.fetchall()
    
    for file, line, func, args in broadcasts:
        if not args:
            continue
            
        # Check if arguments contain sensitive data
        args_lower = args.lower() if args else ""
        contains_sensitive = any(sens in args_lower for sens in sensitive_patterns)
        
        if contains_sensitive:
            findings.append(StandardFinding(
                rule_name='websocket-broadcast-sensitive-data',
                message='Broadcasting potentially sensitive data via WebSocket',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{func}(sensitive_data)',
                cwe_id='CWE-200'
            ))
        else:
            # Check if broadcasting variables that might contain sensitive data
            cursor.execute("""
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
                  AND ({})
            """.format(' OR '.join([f"a.source_expr LIKE '%{sens}%'" for sens in sensitive_patterns])),
            (file, line, file, line))
            
            sensitive_vars = cursor.fetchall()
            
            if sensitive_vars:
                findings.append(StandardFinding(
                    rule_name='websocket-broadcast-sensitive-data',
                    message='Broadcasting variable containing sensitive data',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'{func}(variable)',
                    cwe_id='CWE-200'
                ))
    
    return findings


def _find_websocket_no_tls(cursor) -> List[StandardFinding]:
    """Find WebSocket connections without TLS (ws:// instead of wss://)."""
    findings = []
    
    # Find WebSocket URLs
    cursor.execute("""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.type = 'string'
          AND s.name LIKE 'ws://%'
          AND s.name NOT LIKE 'ws://localhost%'
          AND s.name NOT LIKE 'ws://127.0.0.1%'
    """)
    
    insecure_urls = cursor.fetchall()
    
    for file, line, url in insecure_urls:
        findings.append(StandardFinding(
            rule_name='websocket-no-tls',
            message='WebSocket connection without TLS encryption',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{url[:50]}...' if len(url) > 50 else url,
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
            snippet=f'{func}(...)',
            cwe_id='CWE-319'
        ))
    
    return findings


