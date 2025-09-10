"""PII Data Flow Analyzer

Detects PII (Personally Identifiable Information) exposure patterns in Python and JavaScript/TypeScript code.
"""

import ast
from typing import Any, Dict, List, Optional, Set
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

PII_FIELD_PATTERNS = {
    'ssn', 'social_security', 'socialsecurity', 'sin',
    'email', 'email_address', 'emailaddress', 'mail',
    'phone', 'phone_number', 'phonenumber', 'mobile', 'cell',
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'credit_card', 'creditcard', 'cc_number', 'card_number', 'cardnumber',
    'dob', 'date_of_birth', 'dateofbirth', 'birthdate', 'birthday',
    'address', 'street', 'zipcode', 'postal_code', 'postalcode',
    'passport', 'drivers_license', 'driverslicense', 'license_number',
    'bank_account', 'bankaccount', 'account_number', 'accountnumber',
    'routing_number', 'routingnumber', 'iban', 'swift',
    'tax_id', 'taxid', 'ein', 'national_id', 'nationalid',
    'ip_address', 'ipaddress', 'mac_address', 'macaddress',
    'username', 'user_name', 'login', 'userid', 'user_id',
    'first_name', 'firstname', 'last_name', 'lastname', 'full_name', 'fullname',
    'maiden_name', 'maidenname', 'nickname',
    'salary', 'income', 'wage', 'compensation',
    'medical_record', 'medicalrecord', 'health_record', 'diagnosis',
    'biometric', 'fingerprint', 'retina', 'face_id', 'faceid'
}

LOGGING_FUNCTIONS = {
    'python': {
        'print', 'logger.debug', 'logger.info', 'logger.warning', 'logger.error',
        'logging.debug', 'logging.info', 'logging.warning', 'logging.error',
        'log.debug', 'log.info', 'log.warning', 'log.error',
        'console.log', 'console.debug', 'console.info', 'console.warn', 'console.error'
    },
    'javascript': {
        'console.log', 'console.debug', 'console.info', 'console.warn', 'console.error',
        'console.trace', 'console.dir', 'console.table',
        'logger.debug', 'logger.info', 'logger.warn', 'logger.error',
        'log.debug', 'log.info', 'log.warn', 'log.error',
        'winston.debug', 'winston.info', 'winston.warn', 'winston.error',
        'bunyan.debug', 'bunyan.info', 'bunyan.warn', 'bunyan.error',
        'pino.debug', 'pino.info', 'pino.warn', 'pino.error'
    }
}

ERROR_RESPONSE_PATTERNS = {
    'python': {
        'Response', 'HttpResponse', 'JsonResponse', 'render',
        'make_response', 'jsonify', 'send_error', 'abort'
    },
    'javascript': {
        'res.send', 'res.json', 'res.status', 'res.render',
        'response.send', 'response.json', 'response.status',
        'ctx.body', 'ctx.response', 'reply.send', 'reply.code'
    }
}

class PythonPIIAnalyzer(ast.NodeVisitor):
    """Analyzes Python AST for PII exposure patterns."""
    
    def __init__(self, file_path: str = None):
        self.issues = []
        self.file_path = file_path or "unknown"
        self.pii_variables = set()
        self.in_try_block = False
        self.current_function = None
        
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
        
    def visit_Assign(self, node: ast.Assign) -> None:
        """Track PII variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id.lower()
                if any(pii in var_name for pii in PII_FIELD_PATTERNS):
                    self.pii_variables.add(target.id)
        self.generic_visit(node)
        
    def visit_Call(self, node: ast.Call) -> None:
        """Check for PII in logging and error responses."""
        func_name = self._get_call_name(node.func)
        
        # Check logging functions
        if self._is_logging_call(func_name):
            self._check_pii_in_call_args(node, func_name, "PII logged")
            
        # Check error response functions
        if self._is_error_response(func_name):
            self._check_pii_in_call_args(node, func_name, "PII in error response")
            
        # Check URL construction
        if func_name in {'urlencode', 'urllib.parse.urlencode', 'build_url', 'make_url'}:
            self._check_pii_in_call_args(node, func_name, "PII in URL parameters")
            
        # Check database operations without encryption
        if func_name in {'execute', 'executemany', 'insert', 'update', 'save', 'create'}:
            self._check_unencrypted_pii_storage(node, func_name)
            
        self.generic_visit(node)
        
    def visit_Try(self, node: ast.Try) -> None:
        """Track try blocks for exception handling."""
        old_in_try = self.in_try_block
        self.in_try_block = True
        
        for handler in node.handlers:
            self._check_exception_handler(handler)
            
        self.generic_visit(node)
        self.in_try_block = old_in_try
        
    def _get_call_name(self, node: Any) -> str:
        """Extract the full call name from a Call node's func."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._get_call_name(node.value)
            if base:
                return f"{base}.{node.attr}"
            return node.attr
        return ""
        
    def _is_logging_call(self, func_name: str) -> bool:
        """Check if function is a logging call."""
        return any(
            func_name == log_func or func_name.endswith(f".{log_func}")
            for log_func in LOGGING_FUNCTIONS['python']
        )
        
    def _is_error_response(self, func_name: str) -> bool:
        """Check if function returns an error response."""
        return any(
            func_name == resp_func or func_name.endswith(f".{resp_func}")
            for resp_func in ERROR_RESPONSE_PATTERNS['python']
        )
        
    def _check_pii_in_call_args(self, node: ast.Call, func_name: str, issue_type: str) -> None:
        """Check if PII is passed to a function call."""
        for arg in node.args:
            pii_fields = self._find_pii_in_node(arg)
            if pii_fields:
                self.issues.append({
                    'type': issue_type,
                    'file': self.file_path,
                    'line': node.lineno,
                    'column': node.col_offset,
                    'function': self.current_function or '<module>',
                    'code': func_name,
                    'pii_fields': list(pii_fields),
                    'severity': 'high'
                })
                
    def _find_pii_in_node(self, node: Any) -> Set[str]:
        """Find PII fields referenced in a node."""
        pii_found = set()
        
        if isinstance(node, ast.Name):
            if node.id in self.pii_variables:
                pii_found.add(node.id)
            elif any(pii in node.id.lower() for pii in PII_FIELD_PATTERNS):
                pii_found.add(node.id)
                
        elif isinstance(node, ast.Attribute):
            attr_name = node.attr.lower()
            if any(pii in attr_name for pii in PII_FIELD_PATTERNS):
                pii_found.add(node.attr)
                
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant):
                    key_str = str(key.value).lower()
                    if any(pii in key_str for pii in PII_FIELD_PATTERNS):
                        pii_found.add(str(key.value))
                        
        elif isinstance(node, ast.JoinedStr):  # f-strings
            for value in node.values:
                if isinstance(value, ast.FormattedValue):
                    pii_found.update(self._find_pii_in_node(value.value))
                    
        return pii_found
        
    def _check_unencrypted_pii_storage(self, node: ast.Call, func_name: str) -> None:
        """Check for unencrypted PII in database operations."""
        # Look for PII fields in arguments
        for arg in node.args:
            pii_fields = self._find_pii_in_node(arg)
            if pii_fields:
                # Check if there's any encryption nearby
                if not self._has_encryption_nearby(node):
                    self.issues.append({
                        'type': 'Unencrypted PII storage',
                        'file': self.file_path,
                        'line': node.lineno,
                        'column': node.col_offset,
                        'function': self.current_function or '<module>',
                        'code': func_name,
                        'pii_fields': list(pii_fields),
                        'severity': 'critical'
                    })
                    
    def _has_encryption_nearby(self, node: ast.Call) -> bool:
        """Check if encryption functions are used nearby."""
        # Simple heuristic: check for encryption-related calls in same function
        # This would need more sophisticated analysis in production
        return False
        
    def _check_exception_handler(self, handler: ast.ExceptHandler) -> None:
        """Check exception handlers for PII exposure."""
        for node in ast.walk(handler):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node.func)
                if self._is_logging_call(func_name) or self._is_error_response(func_name):
                    # Check if exception details are being logged
                    for arg in node.args:
                        if isinstance(arg, ast.Name) and arg.id in {'e', 'ex', 'exc', 'exception', 'error'}:
                            self.issues.append({
                                'type': 'PII in exception handling',
                                'file': self.file_path,
                                'line': node.lineno,
                                'column': node.col_offset,
                                'function': self.current_function or '<module>',
                                'code': func_name,
                                'severity': 'medium',
                                'note': 'Exception details may contain PII'
                            })


def analyze_javascript_pii(tree: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript ESLint AST for PII exposure."""
    issues = []
    file_path = file_path or "unknown"
    pii_variables = set()
    
    def find_pii_fields(node: Dict[str, Any]) -> Set[str]:
        """Find PII fields in a node."""
        pii_found = set()
        
        if node.get('type') == 'Identifier':
            name = node.get('name', '').lower()
            if any(pii in name for pii in PII_FIELD_PATTERNS):
                pii_found.add(node.get('name'))
                
        elif node.get('type') == 'MemberExpression':
            prop = node.get('property', {})
            if prop.get('type') == 'Identifier':
                prop_name = prop.get('name', '').lower()
                if any(pii in prop_name for pii in PII_FIELD_PATTERNS):
                    pii_found.add(prop.get('name'))
                    
        elif node.get('type') == 'ObjectExpression':
            for prop in node.get('properties', []):
                if prop.get('key', {}).get('type') == 'Identifier':
                    key_name = prop.get('key', {}).get('name', '').lower()
                    if any(pii in key_name for pii in PII_FIELD_PATTERNS):
                        pii_found.add(prop.get('key', {}).get('name'))
                        
        elif node.get('type') == 'TemplateLiteral':
            for expr in node.get('expressions', []):
                pii_found.update(find_pii_fields(expr))
                
        return pii_found
    
    def is_logging_call(node: Dict[str, Any]) -> Optional[str]:
        """Check if node is a logging call."""
        if node.get('type') != 'CallExpression':
            return None
            
        callee = node.get('callee', {})
        
        # console.log, console.error, etc.
        if callee.get('type') == 'MemberExpression':
            obj = callee.get('object', {})
            prop = callee.get('property', {})
            
            if obj.get('type') == 'Identifier' and prop.get('type') == 'Identifier':
                call_name = f"{obj.get('name')}.{prop.get('name')}"
                if call_name in LOGGING_FUNCTIONS['javascript']:
                    return call_name
                    
        return None
        
    def is_error_response(node: Dict[str, Any]) -> Optional[str]:
        """Check if node is an error response."""
        if node.get('type') != 'CallExpression':
            return None
            
        callee = node.get('callee', {})
        
        if callee.get('type') == 'MemberExpression':
            obj = callee.get('object', {})
            prop = callee.get('property', {})
            
            if obj.get('type') == 'Identifier' and prop.get('type') == 'Identifier':
                call_name = f"{obj.get('name')}.{prop.get('name')}"
                if call_name in ERROR_RESPONSE_PATTERNS['javascript']:
                    return call_name
                    
        return None
        
    def walk_tree(node: Dict[str, Any], parent_func: str = None) -> None:
        """Walk the AST tree looking for PII exposure."""
        if not isinstance(node, dict):
            return
            
        node_type = node.get('type')
        current_func = parent_func
        
        # Track function context
        if node_type in {'FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'}:
            if node.get('id'):
                current_func = node['id'].get('name', parent_func)
            else:
                current_func = '<anonymous>'
                
        # Track variable declarations with PII
        if node_type == 'VariableDeclarator':
            if node.get('id', {}).get('type') == 'Identifier':
                var_name = node['id'].get('name', '').lower()
                if any(pii in var_name for pii in PII_FIELD_PATTERNS):
                    pii_variables.add(node['id']['name'])
                    
        # Check function calls
        if node_type == 'CallExpression':
            # Check logging
            log_func = is_logging_call(node)
            if log_func:
                for arg in node.get('arguments', []):
                    pii_fields = find_pii_fields(arg)
                    if pii_fields:
                        issues.append({
                            'type': 'PII logged',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'code': log_func,
                            'pii_fields': list(pii_fields),
                            'severity': 'high'
                        })
                        
            # Check error responses
            resp_func = is_error_response(node)
            if resp_func:
                for arg in node.get('arguments', []):
                    pii_fields = find_pii_fields(arg)
                    if pii_fields:
                        issues.append({
                            'type': 'PII in error response',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'code': resp_func,
                            'pii_fields': list(pii_fields),
                            'severity': 'high'
                        })
                        
            # Check URL construction
            callee = node.get('callee', {})
            if callee.get('type') == 'Identifier':
                func_name = callee.get('name')
                if func_name in {'encodeURIComponent', 'encodeURI'}:
                    for arg in node.get('arguments', []):
                        pii_fields = find_pii_fields(arg)
                        if pii_fields:
                            issues.append({
                                'type': 'PII in URL parameters',
                                'file': file_path,
                                'line': node.get('loc', {}).get('start', {}).get('line'),
                                'column': node.get('loc', {}).get('start', {}).get('column'),
                                'function': current_func or '<module>',
                                'code': func_name,
                                'pii_fields': list(pii_fields),
                                'severity': 'medium'
                            })
                            
        # Check catch blocks for PII exposure
        if node_type == 'CatchClause':
            body = node.get('body', {})
            if body.get('type') == 'BlockStatement':
                for stmt in body.get('body', []):
                    walk_tree(stmt, current_func)
                    
        # Recursively process child nodes
        for key in node:
            if key in {'type', 'loc', 'range', 'raw', 'value'}:
                continue
                
            child = node[key]
            if isinstance(child, dict):
                walk_tree(child, current_func)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        walk_tree(item, current_func)
                        
    # Start walking from root
    walk_tree(tree)
    return issues


def find_pii_exposure(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find PII exposure patterns in Python or JavaScript/TypeScript code.
    
    Detects:
    1. PII logged - Sensitive data in log statements
    2. PII in error response - Sensitive data in error messages
    3. PII in URL parameters - Sensitive data in URLs/query strings
    4. Unencrypted PII storage - Sensitive data stored without encryption
    5. PII in exception handling - Sensitive data in exception messages
    
    Args:
        tree: AST tree (Python ast or ESLint/tree-sitter format)
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checker instance
        
    Returns:
        List of PII exposure issues found
    """
    try:
        # Check if it's a Python AST
        if hasattr(tree, '_fields'):
            analyzer = PythonPIIAnalyzer(file_path)
            analyzer.visit(tree)
            return analyzer.issues
            
        # Check if it's JavaScript/TypeScript ESLint AST
        elif isinstance(tree, dict) and 'type' in tree:
            if tree.get('type') == 'Program':
                return analyze_javascript_pii(tree, file_path)
                
        # Tree-sitter format
        elif hasattr(tree, 'root_node'):
            # Convert tree-sitter to dict for analysis
            # This would need proper tree-sitter traversal in production
            logger.warning(f"Tree-sitter AST not fully supported for PII analysis in {file_path}")
            return []
            
        return []
        
    except Exception as e:
        logger.error(f"Error analyzing PII exposure in {file_path}: {e}")
        return []