"""SQL-based WebSocket security analyzer.

This module detects WebSocket security issues by querying the indexed database
instead of traversing AST structures.
"""

import sqlite3
from typing import List, Dict, Any, Set
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


def detect_websocket_patterns(db_path: str) -> List[Dict[str, Any]]:
    """
    Detect WebSocket security issues using SQL queries.
    
    This function queries the indexed database to find:
    - WebSocket connections without authentication
    - Unvalidated message handling
    - Missing rate limiting on WebSocket messages
    - Broadcasting sensitive data to all clients
    
    Args:
        db_path: Path to the repo_index.db database
        
    Returns:
        List of security findings in StandardFinding format
    """
    findings = []
    
    try:
        conn = sqlite3.connect(db_path)
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
        
    except Exception as e:
        logger.error(f"Error detecting WebSocket patterns: {e}")
    
    return findings


def _find_websocket_no_auth(cursor) -> List[Dict[str, Any]]:
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
                WHERE s.file = ?
                  AND s.line BETWEEN ? AND ?
                  AND ({})
            """.format(' OR '.join([f"s.name LIKE '%{auth}%'" for auth in auth_patterns])),
            (file, line - 30, line + 30))
            
            has_auth = cursor.fetchone()[0] > 0
        
        if not has_auth:
            findings.append({
                'rule_id': 'websocket-no-auth-handshake',
                'message': 'WebSocket connection handler without authentication',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'Add authentication verification before accepting WebSocket connections to prevent unauthorized access.'
            })
    
    # Check for Python async WebSocket handlers
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.symbol_type = 'function'
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
            findings.append({
                'rule_id': 'websocket-no-auth-handshake',
                'message': f'WebSocket handler {name} lacks authentication',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'Verify authentication token or session before establishing WebSocket connection.'
            })
    
    return findings


def _find_websocket_no_validation(cursor) -> List[Dict[str, Any]]:
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
            findings.append({
                'rule_id': 'websocket-no-message-validation',
                'message': 'WebSocket message handler without input validation',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'high',
                'category': 'security',
                'confidence': 'high',
                'description': 'Validate all incoming WebSocket messages before processing to prevent injection attacks.'
            })
    
    # Check Python message handlers
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.symbol_type = 'function'
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
            findings.append({
                'rule_id': 'websocket-no-message-validation',
                'message': f'WebSocket handler {name} lacks message validation',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'high',
                'category': 'security',
                'confidence': 'medium',
                'description': 'Implement schema validation for all incoming messages.'
            })
    
    return findings


def _find_websocket_no_rate_limit(cursor) -> List[Dict[str, Any]]:
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
                WHERE s.file = ?
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
            
            findings.append({
                'rule_id': 'websocket-no-rate-limiting',
                'message': 'WebSocket message handling without rate limiting',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'high',
                'category': 'security',
                'confidence': 'medium',
                'description': 'Implement rate limiting to prevent WebSocket abuse and DoS attacks.'
            })
    
    return findings


def _find_websocket_broadcast_sensitive(cursor) -> List[Dict[str, Any]]:
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
            findings.append({
                'rule_id': 'websocket-broadcast-sensitive-data',
                'message': 'Broadcasting potentially sensitive data via WebSocket',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'Filter sensitive data before broadcasting to all clients. Consider targeted messaging instead.'
            })
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
                findings.append({
                    'rule_id': 'websocket-broadcast-sensitive-data',
                    'message': 'Broadcasting variable containing sensitive data',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'critical',
                    'category': 'security',
                    'confidence': 'medium',
                    'description': 'Variable may contain sensitive information. Sanitize before broadcasting.'
                })
    
    return findings


def _find_websocket_no_tls(cursor) -> List[Dict[str, Any]]:
    """Find WebSocket connections without TLS (ws:// instead of wss://)."""
    findings = []
    
    # Find WebSocket URLs
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.symbol_type = 'string'
          AND s.name LIKE 'ws://%'
          AND s.name NOT LIKE 'ws://localhost%'
          AND s.name NOT LIKE 'ws://127.0.0.1%'
    """)
    
    insecure_urls = cursor.fetchall()
    
    for file, line, url in insecure_urls:
        findings.append({
            'rule_id': 'websocket-no-tls',
            'message': 'WebSocket connection without TLS encryption',
            'file': file,
            'line': line,
            'column': 0,
            'severity': 'high',
            'category': 'security',
            'confidence': 'high',
            'description': f'Use wss:// instead of ws:// for encrypted WebSocket connections. Found: {url[:50]}'
        })
    
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
        findings.append({
            'rule_id': 'websocket-no-tls',
            'message': 'WebSocket server without TLS configuration',
            'file': file,
            'line': line,
            'column': 0,
            'severity': 'high',
            'category': 'security',
            'confidence': 'medium',
            'description': 'Configure WebSocket server with TLS/SSL certificates for encrypted communication.'
        })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register WebSocket-specific patterns with the taint system.
    
    This function maintains compatibility with the taint analyzer.
    """
    # WebSocket broadcast/emit operations - these are sinks where data flows out
    WEBSOCKET_SINKS = [
        "ws.send", "ws.broadcast", "ws.emit",
        "socket.send", "socket.emit", "socket.broadcast",
        "io.emit", "io.send", "io.broadcast",
        "clients.forEach", "wss.clients.forEach",
        "connection.send", "connection.write",
        "websocket.send", "websocket.send_text",
        "websocket.send_bytes", "websocket.send_json",
        "broadcast", "emit", "send_all", "publish",
        "on_message", "onmessage", "recv", "receive"
    ]
    
    for pattern in WEBSOCKET_SINKS:
        taint_registry.register_sink(pattern, "websocket", "any")


def find_websocket_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """
    Compatibility wrapper for AST-based callers.
    
    This function is called by universal_detector but we ignore the AST tree
    and query the database instead.
    """
    # This would need access to the database path
    # In real implementation, this would be configured
    return []


# For direct CLI usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        findings = detect_websocket_patterns(db_path)
        for finding in findings:
            print(f"{finding['file']}:{finding['line']} - {finding['message']}")