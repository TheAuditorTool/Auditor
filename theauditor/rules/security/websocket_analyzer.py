"""WebSocket security analyzer for detecting common WebSocket vulnerabilities.

Detects WebSocket security issues in both Python and JavaScript/TypeScript code.
Replaces regex patterns from security.yml with proper AST analysis.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Set


def find_websocket_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find WebSocket security issues in Python or JavaScript/TypeScript code.
    
    Detects:
    1. websocket-no-auth-handshake - WebSocket without authentication
    2. websocket-no-message-validation - Unvalidated message handling
    3. websocket-no-rate-limiting - Missing rate limiting
    4. websocket-broadcast-sensitive-data - Broadcasting sensitive data
    
    Args:
        tree: Python AST or ESLint/tree-sitter AST from ast_parser.py
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checking function
    
    Returns:
        List of findings with details about WebSocket security issues
    """
    findings = []
    
    # Determine tree type and analyze accordingly
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        if tree_type == "python_ast":
            actual_tree = tree.get("tree")
            if actual_tree:
                return _analyze_python_websocket(actual_tree, file_path)
        elif tree_type == "eslint_ast":
            return _analyze_javascript_websocket(tree, file_path)
        elif tree_type == "tree_sitter":
            return _analyze_tree_sitter_websocket(tree, file_path)
    elif isinstance(tree, ast.AST):
        # Direct Python AST
        return _analyze_python_websocket(tree, file_path)
    
    return findings


def _analyze_python_websocket(tree: ast.AST, file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze Python AST for WebSocket security issues."""
    analyzer = PythonWebSocketAnalyzer(file_path)
    analyzer.visit(tree)
    return analyzer.findings


class PythonWebSocketAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting WebSocket issues in Python."""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or "unknown"
        self.findings = []
        self.has_auth_check = False
        self.has_validation = False
        self.has_rate_limit = False
        self.in_websocket_handler = False
        self.websocket_libraries = ['websocket', 'websockets', 'socketio', 'ws']
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track WebSocket handler functions."""
        # Check if this is a WebSocket handler
        if any(ws in node.name.lower() for ws in ['websocket', 'ws', 'socket', 'connect', 'message']):
            old_handler = self.in_websocket_handler
            old_auth = self.has_auth_check
            old_validation = self.has_validation
            
            self.in_websocket_handler = True
            self.has_auth_check = self._check_for_auth(node)
            self.has_validation = self._check_for_validation(node)
            
            self.generic_visit(node)
            
            # Pattern 1: websocket-no-auth-handshake
            if self.in_websocket_handler and not self.has_auth_check:
                if 'connect' in node.name.lower() or 'handshake' in node.name.lower():
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'websocket_no_auth_handshake',
                        'function': node.name,
                        'severity': 'CRITICAL',
                        'confidence': 0.85,
                        'message': 'WebSocket connection handler without authentication',
                        'hint': 'Add authentication verification before accepting WebSocket connections'
                    })
            
            self.in_websocket_handler = old_handler
            self.has_auth_check = old_auth
            self.has_validation = old_validation
        else:
            self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Handle async WebSocket handlers."""
        # Same logic as FunctionDef
        self.visit_FunctionDef(node)
    
    def visit_Call(self, node: ast.Call):
        """Check for WebSocket operations."""
        call_name = self._get_call_name(node)
        
        # Check for WebSocket message handling
        if any(ws in call_name.lower() for ws in ['on_message', 'onmessage', 'recv', 'receive']):
            # Pattern 2: websocket-no-message-validation
            if not self._has_validation_nearby(node):
                self.findings.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'type': 'websocket_no_message_validation',
                    'method': call_name,
                    'severity': 'HIGH',
                    'confidence': 0.80,
                    'message': 'WebSocket message handler without validation',
                    'hint': 'Validate all incoming WebSocket messages before processing'
                })
        
        # Check for broadcasting
        if any(broadcast in call_name.lower() for broadcast in ['broadcast', 'emit', 'send_all', 'publish']):
            # Pattern 4: websocket-broadcast-sensitive-data
            if self._contains_sensitive_data(node):
                self.findings.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'type': 'websocket_broadcast_sensitive_data',
                    'method': call_name,
                    'severity': 'CRITICAL',
                    'confidence': 0.70,
                    'message': 'Broadcasting potentially sensitive data via WebSocket',
                    'hint': 'Filter sensitive data before broadcasting to all clients'
                })
        
        # Check for rate limiting
        if 'message' in call_name.lower() and not self.has_rate_limit:
            # Pattern 3: websocket-no-rate-limiting
            self.findings.append({
                'line': node.lineno,
                'column': node.col_offset,
                'type': 'websocket_no_rate_limiting',
                'severity': 'HIGH',
                'confidence': 0.75,
                'message': 'WebSocket message handler without rate limiting',
                'hint': 'Implement rate limiting to prevent abuse'
            })
        
        self.generic_visit(node)
    
    def _check_for_auth(self, node: ast.AST) -> bool:
        """Check if function contains authentication checks."""
        auth_keywords = ['auth', 'token', 'verify', 'authenticate', 'check_permission', 'jwt', 'session']
        
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if any(auth in child.id.lower() for auth in auth_keywords):
                    return True
            elif isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if any(auth in call_name.lower() for auth in auth_keywords):
                    return True
        
        return False
    
    def _check_for_validation(self, node: ast.AST) -> bool:
        """Check if function contains validation."""
        validation_keywords = ['validate', 'verify', 'check', 'schema', 'sanitize', 'clean']
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if any(val in call_name.lower() for val in validation_keywords):
                    return True
        
        return False
    
    def _has_validation_nearby(self, node: ast.AST) -> bool:
        """Check if there's validation near this node."""
        # Simplified check - in production would need control flow analysis
        return self.has_validation
    
    def _contains_sensitive_data(self, node: ast.Call) -> bool:
        """Check if call arguments contain sensitive data."""
        sensitive_keywords = ['password', 'secret', 'token', 'key', 'auth', 'session', 
                            'email', 'ssn', 'credit', 'private', 'personal']
        
        for arg in node.args:
            arg_str = ast.unparse(arg) if hasattr(ast, 'unparse') else ""
            if any(sens in arg_str.lower() for sens in sensitive_keywords):
                return True
        
        return False
    
    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return '.'.join(reversed(parts))
        return ''


def _analyze_javascript_websocket(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript ESLint AST for WebSocket security issues."""
    findings = []
    
    ast = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not ast or not isinstance(ast, dict):
        return findings
    
    # Track state
    has_auth_check = False
    has_validation = False
    has_rate_limit = False
    in_websocket_context = False
    
    def traverse_ast(node: Dict[str, Any], parent: Dict[str, Any] = None):
        nonlocal has_auth_check, has_validation, has_rate_limit, in_websocket_context
        
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Check for WebSocket server creation
        if node_type == "NewExpression":
            callee = node.get("callee", {})
            if _is_websocket_server(callee):
                in_websocket_context = True
                
                # Check the entire scope for auth
                if not _contains_auth_check(node, content):
                    # Pattern 1: websocket-no-auth-handshake
                    loc = node.get("loc", {}).get("start", {})
                    findings.append({
                        'line': loc.get("line", 0),
                        'column': loc.get("column", 0),
                        'type': 'websocket_no_auth_handshake',
                        'severity': 'CRITICAL',
                        'confidence': 0.85,
                        'message': 'WebSocket server without authentication',
                        'hint': 'Add authentication verification in connection handler'
                    })
        
        # Check for event handlers (on('connection'), on('message'), etc.)
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            
            # Check for .on() method calls
            if callee.get("type") == "MemberExpression":
                prop = callee.get("property", {})
                if prop.get("name") == "on":
                    args = node.get("arguments", [])
                    if args and args[0].get("type") == "Literal":
                        event_name = args[0].get("value", "")
                        
                        # Connection handler
                        if event_name == "connection":
                            # Check for auth in handler
                            if len(args) > 1:
                                handler = args[1]
                                if not _contains_auth_check(handler, content):
                                    loc = node.get("loc", {}).get("start", {})
                                    findings.append({
                                        'line': loc.get("line", 0),
                                        'column': loc.get("column", 0),
                                        'type': 'websocket_no_auth_handshake',
                                        'severity': 'CRITICAL',
                                        'confidence': 0.85,
                                        'message': 'WebSocket connection handler without authentication',
                                        'hint': 'Verify authentication token in connection handler'
                                    })
                        
                        # Message handler
                        elif event_name in ["message", "data"]:
                            if len(args) > 1:
                                handler = args[1]
                                
                                # Pattern 2: websocket-no-message-validation
                                if not _contains_validation(handler, content):
                                    loc = node.get("loc", {}).get("start", {})
                                    findings.append({
                                        'line': loc.get("line", 0),
                                        'column': loc.get("column", 0),
                                        'type': 'websocket_no_message_validation',
                                        'severity': 'HIGH',
                                        'confidence': 0.80,
                                        'message': 'WebSocket message handler without validation',
                                        'hint': 'Validate all incoming messages before processing'
                                    })
                                
                                # Pattern 3: websocket-no-rate-limiting
                                if not _contains_rate_limit(handler, content):
                                    loc = node.get("loc", {}).get("start", {})
                                    findings.append({
                                        'line': loc.get("line", 0),
                                        'column': loc.get("column", 0),
                                        'type': 'websocket_no_rate_limiting',
                                        'severity': 'HIGH',
                                        'confidence': 0.75,
                                        'message': 'WebSocket message handler without rate limiting',
                                        'hint': 'Implement rate limiting to prevent abuse'
                                    })
            
            # Check for broadcasting
            call_text = _extract_call_text(callee, content)
            if any(broadcast in call_text.lower() for broadcast in ['broadcast', 'emit', 'send', 'clients.foreach']):
                # Pattern 4: websocket-broadcast-sensitive-data
                if _contains_sensitive_data_js(node, content):
                    loc = node.get("loc", {}).get("start", {})
                    findings.append({
                        'line': loc.get("line", 0),
                        'column': loc.get("column", 0),
                        'type': 'websocket_broadcast_sensitive_data',
                        'method': call_text,
                        'severity': 'CRITICAL',
                        'confidence': 0.70,
                        'message': 'Broadcasting potentially sensitive data',
                        'hint': 'Filter sensitive data before broadcasting'
                    })
        
        # Recursively traverse
        for key, value in node.items():
            if key in ["type", "loc", "range", "raw", "value"]:
                continue
            
            if isinstance(value, dict):
                traverse_ast(value, node)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        traverse_ast(item, node)
    
    # Start traversal
    if ast.get("type") == "Program":
        traverse_ast(ast)
    
    return findings


def _is_websocket_server(callee: Dict[str, Any]) -> bool:
    """Check if this is a WebSocket server creation."""
    if callee.get("type") == "MemberExpression":
        obj = callee.get("object", {})
        prop = callee.get("property", {})
        
        if obj.get("name") in ["WebSocket", "ws", "io"] and prop.get("name") == "Server":
            return True
    elif callee.get("type") == "Identifier":
        name = callee.get("name", "")
        if name in ["WebSocketServer", "Server", "SocketIOServer"]:
            return True
    
    return False


def _contains_auth_check(node: Dict[str, Any], content: str) -> bool:
    """Check if node contains authentication checks."""
    auth_keywords = ['auth', 'token', 'verify', 'authenticate', 'jwt', 'passport', 'session', 'authorization']
    
    # Extract text from node range if available
    node_text = _extract_node_text(node, content).lower()
    
    return any(auth in node_text for auth in auth_keywords)


def _contains_validation(node: Dict[str, Any], content: str) -> bool:
    """Check if node contains validation."""
    validation_keywords = ['validate', 'verify', 'check', 'schema', 'sanitize', 'clean', 'joi', 'yup', 'zod']
    
    node_text = _extract_node_text(node, content).lower()
    
    return any(val in node_text for val in validation_keywords)


def _contains_rate_limit(node: Dict[str, Any], content: str) -> bool:
    """Check if node contains rate limiting."""
    rate_keywords = ['rate', 'limit', 'throttle', 'quota', 'flood', 'spam', 'cooldown', 'bucket']
    
    node_text = _extract_node_text(node, content).lower()
    
    return any(rate in node_text for rate in rate_keywords)


def _contains_sensitive_data_js(node: Dict[str, Any], content: str) -> bool:
    """Check if call contains sensitive data."""
    sensitive_keywords = ['password', 'secret', 'token', 'key', 'auth', 'session',
                         'email', 'ssn', 'credit', 'private', 'personal', 'confidential']
    
    node_text = _extract_node_text(node, content).lower()
    
    return any(sens in node_text for sens in sensitive_keywords)


def _extract_call_text(callee: Dict[str, Any], content: str) -> str:
    """Extract call text from ESLint AST node."""
    if callee.get("type") == "Identifier":
        return callee.get("name", "")
    elif callee.get("type") == "MemberExpression":
        parts = []
        current = callee
        
        while current and isinstance(current, dict):
            if current.get("type") == "MemberExpression":
                prop = current.get("property", {})
                if prop.get("type") == "Identifier":
                    parts.append(prop.get("name", ""))
                current = current.get("object", {})
            elif current.get("type") == "Identifier":
                parts.append(current.get("name", ""))
                break
            else:
                break
        
        return '.'.join(reversed(parts))
    
    return ""


def _extract_node_text(node: Dict[str, Any], content: str) -> str:
    """Extract text from node using range if available."""
    if not node or not content:
        return ""
    
    range_info = node.get("range")
    if range_info and isinstance(range_info, list) and len(range_info) == 2:
        start, end = range_info
        if 0 <= start < end <= len(content):
            return content[start:end]
    
    return ""


def _analyze_tree_sitter_websocket(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze tree-sitter AST (simplified implementation)."""
    # Would need tree-sitter specific implementation
    # For now, return empty list
    return []