"""Input validation security analyzer for detecting validation and deserialization issues.

Detects input validation issues in both Python and JavaScript/TypeScript code.
Replaces regex patterns from security_compliance.yml with proper AST analysis.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Set


def find_input_validation_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find input validation and deserialization security issues.
    
    Detects:
    1. missing-input-validation - Request data used without validation
    2. unsafe-deserialization - eval/parse of user-controlled data
    3. missing-csrf-protection - State-changing routes without CSRF
    
    Args:
        tree: Python AST or ESLint/tree-sitter AST from ast_parser.py
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checking function
    
    Returns:
        List of findings with details about input validation issues
    """
    findings = []
    
    # Determine tree type and analyze accordingly
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        if tree_type == "python_ast":
            actual_tree = tree.get("tree")
            if actual_tree:
                return _analyze_python_validation(actual_tree, file_path)
        elif tree_type == "eslint_ast":
            return _analyze_javascript_validation(tree, file_path)
        elif tree_type == "tree_sitter":
            return _analyze_tree_sitter_validation(tree, file_path)
    elif isinstance(tree, ast.AST):
        # Direct Python AST
        return _analyze_python_validation(tree, file_path)
    
    return findings


def _analyze_python_validation(tree: ast.AST, file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze Python AST for input validation issues."""
    analyzer = PythonValidationAnalyzer(file_path)
    analyzer.visit(tree)
    return analyzer.findings


class PythonValidationAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting input validation issues in Python."""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or "unknown"
        self.findings = []
        self.request_vars = set()  # Track variables from request
        self.validated_vars = set()  # Track validated variables
        self.in_route_handler = False
        self.current_function = None
        self.has_csrf_protection = False
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track function context and route handlers."""
        old_function = self.current_function
        old_route = self.in_route_handler
        old_csrf = self.has_csrf_protection
        
        self.current_function = node.name
        
        # Check if this is a route handler (has route decorator)
        for decorator in node.decorator_list:
            if self._is_route_decorator(decorator):
                self.in_route_handler = True
                
                # Check for CSRF protection in decorators
                self.has_csrf_protection = self._check_csrf_decorators(node.decorator_list)
                
                # Check if it's a state-changing operation
                if self._is_state_changing_route(decorator):
                    # Pattern 3: missing-csrf-protection
                    if not self.has_csrf_protection:
                        self.findings.append({
                            'line': node.lineno,
                            'column': node.col_offset,
                            'type': 'missing_csrf_protection',
                            'function': node.name,
                            'severity': 'HIGH',
                            'confidence': 0.70,
                            'message': 'State-changing route without CSRF protection',
                            'hint': 'Add CSRF protection decorator or middleware'
                        })
                break
        
        # Check function body
        self.generic_visit(node)
        
        self.current_function = old_function
        self.in_route_handler = old_route
        self.has_csrf_protection = old_csrf
    
    def visit_Assign(self, node: ast.Assign):
        """Track assignments from request data."""
        # Check if assigning from request
        if isinstance(node.value, ast.Attribute):
            if self._is_request_source(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.request_vars.add(target.id)
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Check for dangerous operations and validation."""
        call_name = self._get_call_name(node)
        
        # Check for validation functions
        validation_functions = ['validate', 'verify', 'check', 'sanitize', 'clean', 'schema']
        if any(val in call_name.lower() for val in validation_functions):
            # Track what's being validated
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    self.validated_vars.add(arg.id)
        
        # Pattern 2: unsafe-deserialization
        dangerous_functions = ['eval', 'exec', 'compile', '__import__', 'pickle.loads', 'yaml.load', 'json.loads']
        if any(danger in call_name.lower() for danger in dangerous_functions):
            # Check if using user input
            for arg in node.args:
                if self._contains_user_input(arg):
                    severity = 'CRITICAL' if 'eval' in call_name.lower() or 'exec' in call_name.lower() else 'HIGH'
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'unsafe_deserialization',
                        'function': call_name,
                        'severity': severity,
                        'confidence': 0.85,
                        'message': f'Unsafe deserialization using {call_name} with user input',
                        'hint': 'Use safe alternatives like json.loads() or yaml.safe_load()'
                    })
        
        # Pattern 1: missing-input-validation
        # Check for database operations with unvalidated request data
        db_operations = ['create', 'update', 'save', 'insert', 'query', 'execute', 'filter', 'find']
        if any(db_op in call_name.lower() for db_op in db_operations):
            # Check if using request data without validation
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    if arg.id in self.request_vars and arg.id not in self.validated_vars:
                        self.findings.append({
                            'line': node.lineno,
                            'column': node.col_offset,
                            'type': 'missing_input_validation',
                            'variable': arg.id,
                            'operation': call_name,
                            'severity': 'HIGH',
                            'confidence': 0.75,
                            'message': f'Using unvalidated request data in {call_name}',
                            'hint': 'Validate all user input before database operations'
                        })
        
        self.generic_visit(node)
    
    def _is_route_decorator(self, decorator: ast.AST) -> bool:
        """Check if decorator is a route decorator."""
        route_patterns = ['route', 'get', 'post', 'put', 'delete', 'patch', 'api']
        
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute):
                return any(pattern in func.attr.lower() for pattern in route_patterns)
            elif isinstance(func, ast.Name):
                return any(pattern in func.id.lower() for pattern in route_patterns)
        elif isinstance(decorator, ast.Attribute):
            return any(pattern in decorator.attr.lower() for pattern in route_patterns)
        elif isinstance(decorator, ast.Name):
            return any(pattern in decorator.id.lower() for pattern in route_patterns)
        
        return False
    
    def _is_state_changing_route(self, decorator: ast.AST) -> bool:
        """Check if route is state-changing (POST, PUT, DELETE, PATCH)."""
        state_changing = ['post', 'put', 'delete', 'patch']
        
        # Check decorator for HTTP method
        decorator_str = ast.unparse(decorator) if hasattr(ast, 'unparse') else ""
        return any(method in decorator_str.lower() for method in state_changing)
    
    def _check_csrf_decorators(self, decorators: List[ast.AST]) -> bool:
        """Check if any decorator provides CSRF protection."""
        csrf_patterns = ['csrf', 'csrf_protect', 'csrf_exempt', 'verify_csrf', 'check_csrf']
        
        for decorator in decorators:
            decorator_str = ast.unparse(decorator) if hasattr(ast, 'unparse') else ""
            if any(csrf in decorator_str.lower() for csrf in csrf_patterns):
                # csrf_exempt means NO protection
                if 'exempt' not in decorator_str.lower():
                    return True
        
        return False
    
    def _is_request_source(self, node: ast.AST) -> bool:
        """Check if node represents request data source."""
        request_sources = ['request', 'req', 'params', 'query', 'body', 'form', 'args', 'json', 'data']
        
        if isinstance(node, ast.Attribute):
            # Check for patterns like request.form, request.json
            if isinstance(node.value, ast.Name):
                return node.value.id.lower() in request_sources
        
        return False
    
    def _contains_user_input(self, node: ast.AST) -> bool:
        """Check if node contains user input."""
        if isinstance(node, ast.Name):
            return node.id in self.request_vars
        elif isinstance(node, ast.Attribute):
            return self._is_request_source(node)
        
        # Check recursively for complex expressions
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if child.id in self.request_vars:
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


def _analyze_javascript_validation(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript ESLint AST for input validation issues."""
    findings = []
    
    ast = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not ast or not isinstance(ast, dict):
        return findings
    
    # Track state
    request_vars = set()
    validated_vars = set()
    has_csrf_middleware = False
    
    def traverse_ast(node: Dict[str, Any], parent: Dict[str, Any] = None):
        nonlocal request_vars, validated_vars, has_csrf_middleware
        
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Track variables from request
        if node_type == "VariableDeclarator":
            var_id = node.get("id", {})
            var_init = node.get("init", {})
            
            if var_id.get("type") == "Identifier":
                var_name = var_id.get("name")
                
                # Check if initialized from request
                init_text = _extract_node_text(var_init, content)
                if any(source in init_text for source in ['req.body', 'req.query', 'req.params', 'request.body']):
                    request_vars.add(var_name)
        
        # Check for route definitions
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            call_text = _extract_call_text(callee, content)
            
            # Check for route handlers
            if any(method in call_text.lower() for method in ['app.post', 'app.put', 'app.delete', 'app.patch',
                                                              'router.post', 'router.put', 'router.delete', 'router.patch']):
                # Pattern 3: missing-csrf-protection
                args = node.get("arguments", [])
                has_csrf = False
                
                # Check middleware arguments for CSRF
                for arg in args:
                    arg_text = _extract_node_text(arg, content).lower()
                    if any(csrf in arg_text for csrf in ['csrf', 'csurf', 'csrfprotection']):
                        has_csrf = True
                        break
                
                if not has_csrf:
                    loc = node.get("loc", {}).get("start", {})
                    findings.append({
                        'line': loc.get("line", 0),
                        'column': loc.get("column", 0),
                        'type': 'missing_csrf_protection',
                        'route': call_text,
                        'severity': 'HIGH',
                        'confidence': 0.65,
                        'message': 'State-changing route without CSRF protection',
                        'hint': 'Add CSRF middleware: csrfProtection'
                    })
            
            # Check for validation
            if any(val in call_text.lower() for val in ['validate', 'sanitize', 'clean', 'schema.validate', 'joi.validate']):
                # Track validated variables
                args = node.get("arguments", [])
                for arg in args:
                    if arg.get("type") == "Identifier":
                        validated_vars.add(arg.get("name"))
            
            # Pattern 2: unsafe-deserialization
            dangerous_calls = ['eval', 'Function', 'JSON.parse', 'deserialize']
            if any(danger in call_text for danger in dangerous_calls):
                # Check if using user input
                args = node.get("arguments", [])
                for arg in args:
                    arg_text = _extract_node_text(arg, content)
                    if any(req in arg_text for req in ['req.', 'request.', 'params', 'query', 'body']):
                        loc = node.get("loc", {}).get("start", {})
                        findings.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'type': 'unsafe_deserialization',
                            'function': call_text,
                            'severity': 'CRITICAL' if 'eval' in call_text else 'HIGH',
                            'confidence': 0.80,
                            'message': f'Unsafe deserialization using {call_text} with user input',
                            'hint': 'Use JSON.parse() with try/catch or validation'
                        })
            
            # Pattern 1: missing-input-validation
            # Check for database operations
            db_operations = ['create', 'update', 'save', 'insert', 'findOneAndUpdate', 'query', 'exec']
            if any(db_op in call_text.lower() for db_op in db_operations):
                # Check if using request.body directly
                args = node.get("arguments", [])
                for arg in args:
                    arg_text = _extract_node_text(arg, content)
                    
                    # Direct use of req.body
                    if 'req.body' in arg_text or 'request.body' in arg_text:
                        # Check if there's validation nearby
                        if not any(val in content[max(0, node.get("range", [0])[0]-500):node.get("range", [0])[0]] 
                                  for val in ['validate', 'sanitize', 'schema']):
                            loc = node.get("loc", {}).get("start", {})
                            findings.append({
                                'line': loc.get("line", 0),
                                'column': loc.get("column", 0),
                                'type': 'missing_input_validation',
                                'operation': call_text,
                                'severity': 'HIGH',
                                'confidence': 0.70,
                                'message': f'Using unvalidated request data in {call_text}',
                                'hint': 'Validate request.body before database operations'
                            })
                    
                    # Check for unvalidated variables
                    elif arg.get("type") == "Identifier":
                        var_name = arg.get("name")
                        if var_name in request_vars and var_name not in validated_vars:
                            loc = node.get("loc", {}).get("start", {})
                            findings.append({
                                'line': loc.get("line", 0),
                                'column': loc.get("column", 0),
                                'type': 'missing_input_validation',
                                'variable': var_name,
                                'operation': call_text,
                                'severity': 'HIGH',
                                'confidence': 0.75,
                                'message': f'Using unvalidated variable {var_name} in {call_text}',
                                'hint': 'Validate all user input before database operations'
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
    
    # Fallback to reconstructing from node type
    if node.get("type") == "Identifier":
        return node.get("name", "")
    elif node.get("type") == "Literal":
        return str(node.get("value", ""))
    elif node.get("type") == "MemberExpression":
        return _extract_call_text(node, content)
    
    return ""


def _analyze_tree_sitter_validation(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze tree-sitter AST (simplified implementation)."""
    # Would need tree-sitter specific implementation
    # For now, return empty list
    return []