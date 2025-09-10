"""General Logic Analyzer

Detects common programming mistakes and best practice violations in Python and JavaScript/TypeScript code.
Combines business logic issues and resource management patterns.
"""

import ast
from typing import Any, Dict, List, Optional
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


class PythonLogicAnalyzer(ast.NodeVisitor):
    """Analyzes Python AST for common logic and resource management issues."""
    
    def __init__(self, file_path: str = None):
        self.issues = []
        self.file_path = file_path or "unknown"
        self.open_resources = {}  # Track opened resources
        self.in_finally = False
        self.in_with = False
        self.current_function = None
        
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
        
    def visit_With(self, node: ast.With) -> None:
        """Track context manager usage."""
        old_with = self.in_with
        self.in_with = True
        self.generic_visit(node)
        self.in_with = old_with
        
    def visit_Try(self, node: ast.Try) -> None:
        """Track try/finally blocks."""
        # Visit try body
        for stmt in node.body:
            self.visit(stmt)
            
        # Check finally block
        if node.finalbody:
            old_finally = self.in_finally
            self.in_finally = True
            for stmt in node.finalbody:
                self.visit(stmt)
            self.in_finally = old_finally
            
        # Visit handlers
        for handler in node.handlers:
            self.visit(handler)
            
    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Check for business logic issues in binary operations."""
        # Check for float arithmetic with money-related variables
        if isinstance(node.op, (ast.Mult, ast.Div, ast.Add, ast.Sub)):
            left_str = self._get_node_str(node.left)
            right_str = self._get_node_str(node.right)
            
            # Money float arithmetic
            money_terms = ['price', 'cost', 'amount', 'total', 'balance', 'payment', 'fee', 'money']
            if any(term in left_str.lower() or term in right_str.lower() for term in money_terms):
                if self._involves_float(node):
                    self.issues.append({
                        'type': 'money-float-arithmetic',
                        'file': self.file_path,
                        'line': node.lineno,
                        'column': node.col_offset,
                        'function': self.current_function or '<module>',
                        'severity': 'critical',
                        'description': 'Using float/double for money calculations - precision loss risk'
                    })
                    
            # Percentage calculation error
            if isinstance(node.op, ast.Mult):
                if self._is_percentage_calc_error(node):
                    self.issues.append({
                        'type': 'percentage-calc-error',
                        'file': self.file_path,
                        'line': node.lineno,
                        'column': node.col_offset,
                        'function': self.current_function or '<module>',
                        'severity': 'high',
                        'description': 'Potential percentage calculation error (missing parentheses)'
                    })
                    
            # Division by zero risk
            if isinstance(node.op, ast.Div):
                divisor_str = self._get_node_str(node.right)
                risky_terms = ['count', 'length', 'size', 'total', 'sum', 'num']
                if any(term in divisor_str.lower() for term in risky_terms):
                    if not self._has_zero_check_nearby(node):
                        self.issues.append({
                            'type': 'divide-by-zero-risk',
                            'file': self.file_path,
                            'line': node.lineno,
                            'column': node.col_offset,
                            'function': self.current_function or '<module>',
                            'severity': 'medium',
                            'description': 'Division without zero check'
                        })
                        
        self.generic_visit(node)
        
    def visit_Call(self, node: ast.Call) -> None:
        """Check for various call-related issues."""
        func_name = self._get_call_name(node.func)
        
        # Timezone-naive datetime
        if func_name in ['datetime.now', 'datetime.today']:
            if not self._has_timezone_arg(node):
                self.issues.append({
                    'type': 'timezone-naive-datetime',
                    'file': self.file_path,
                    'line': node.lineno,
                    'column': node.col_offset,
                    'function': self.current_function or '<module>',
                    'severity': 'medium',
                    'description': 'Using naive datetime without timezone awareness'
                })
                
        # Email regex validation
        if 're.match' in func_name or 're.search' in func_name or 're.compile' in func_name:
            for arg in node.args:
                if self._contains_email_pattern(arg):
                    self.issues.append({
                        'type': 'email-regex-validation',
                        'file': self.file_path,
                        'line': node.lineno,
                        'column': node.col_offset,
                        'function': self.current_function or '<module>',
                        'severity': 'low',
                        'description': 'Using regex for email validation (use proper library instead)'
                    })
                    
        # Resource management - file/connection/socket opening
        if func_name == 'open' and not self.in_with:
            self._track_resource(node, 'file')
            
        if 'connect' in func_name.lower() or 'socket' in func_name.lower():
            self._track_resource(node, 'connection')
            
        if 'transaction' in func_name.lower() and 'begin' in func_name.lower():
            self._track_resource(node, 'transaction')
            
        # Check for resource cleanup
        if 'close' in func_name or 'disconnect' in func_name or 'commit' in func_name or 'rollback' in func_name:
            self._mark_resource_closed(node)
            
        self.generic_visit(node)
        
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
        
    def _get_node_str(self, node: Any) -> str:
        """Get string representation of a node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return ""
        
    def _involves_float(self, node: ast.BinOp) -> bool:
        """Check if operation involves float."""
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                func_name = self._get_call_name(n.func)
                if 'float' in func_name.lower():
                    return True
            elif isinstance(n, ast.Constant):
                if isinstance(n.value, float):
                    return True
        return False
        
    def _is_percentage_calc_error(self, node: ast.BinOp) -> bool:
        """Check for percentage calculation without proper parentheses."""
        # Looking for patterns like: value / 100 * something or something * value / 100
        # Without parentheses around the percentage part
        if isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Div):
            if self._is_hundred(node.left.right):
                return True
        return False
        
    def _is_hundred(self, node: Any) -> bool:
        """Check if node is the constant 100."""
        return isinstance(node, ast.Constant) and node.value == 100
        
    def _has_zero_check_nearby(self, node: ast.BinOp) -> bool:
        """Check if there's a zero check nearby (simplified)."""
        # This is a simplified check - in production would need more context
        return False
        
    def _has_timezone_arg(self, node: ast.Call) -> bool:
        """Check if datetime call has timezone argument."""
        for keyword in node.keywords:
            if keyword.arg in ['tz', 'tzinfo']:
                return True
        return False
        
    def _contains_email_pattern(self, node: Any) -> bool:
        """Check if node contains email regex pattern."""
        if isinstance(node, ast.Constant):
            pattern = str(node.value)
            return '@' in pattern and ('\\@' in pattern or r'\@' in pattern)
        return False
        
    def _track_resource(self, node: ast.Call, resource_type: str) -> None:
        """Track opened resources."""
        if not self.in_finally and not self.in_with:
            self.open_resources[node.lineno] = {
                'type': resource_type,
                'function': self.current_function,
                'closed': False
            }
            
            # Report if not in proper context
            self.issues.append({
                'type': f'{resource_type}-no-close-finally',
                'file': self.file_path,
                'line': node.lineno,
                'column': node.col_offset,
                'function': self.current_function or '<module>',
                'severity': 'high',
                'description': f'{resource_type.capitalize()} opened without close in finally/with block'
            })
            
    def _mark_resource_closed(self, node: ast.Call) -> None:
        """Mark resources as closed."""
        # Simplified - would need more sophisticated tracking in production
        pass


def analyze_javascript_logic(tree: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript ESLint AST for logic and resource issues."""
    issues = []
    file_path = file_path or "unknown"
    open_resources = {}
    
    def walk_tree(node: Dict[str, Any], parent_func: str = None, in_finally: bool = False) -> None:
        """Walk the AST tree looking for logic issues."""
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
                
        # Check binary operations
        if node_type == 'BinaryExpression':
            operator = node.get('operator')
            left = node.get('left', {})
            right = node.get('right', {})
            
            # Money float arithmetic
            if operator in ['+', '-', '*', '/']:
                left_str = get_node_text(left)
                right_str = get_node_text(right)
                money_terms = ['price', 'cost', 'amount', 'total', 'balance', 'payment', 'fee', 'money']
                
                if any(term in left_str.lower() or term in right_str.lower() for term in money_terms):
                    if involves_float(node):
                        issues.append({
                            'type': 'money-float-arithmetic',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'severity': 'critical',
                            'description': 'Using float/double for money calculations - precision loss risk'
                        })
                        
            # Division by zero risk
            if operator == '/':
                divisor_str = get_node_text(right)
                risky_terms = ['count', 'length', 'size', 'total', 'sum', 'num']
                if any(term in divisor_str.lower() for term in risky_terms):
                    issues.append({
                        'type': 'divide-by-zero-risk',
                        'file': file_path,
                        'line': node.get('loc', {}).get('start', {}).get('line'),
                        'column': node.get('loc', {}).get('start', {}).get('column'),
                        'function': current_func or '<module>',
                        'severity': 'medium',
                        'description': 'Division without zero check'
                    })
                    
        # Check function calls
        if node_type == 'CallExpression':
            callee = node.get('callee', {})
            
            # New Date() without timezone
            if callee.get('type') == 'NewExpression':
                if callee.get('callee', {}).get('name') == 'Date':
                    if not has_timezone_context(node):
                        issues.append({
                            'type': 'timezone-naive-datetime',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'severity': 'medium',
                            'description': 'Using naive datetime without timezone awareness'
                        })
                        
            # Date.now() without UTC context
            if callee.get('type') == 'MemberExpression':
                obj = callee.get('object', {})
                prop = callee.get('property', {})
                
                if obj.get('name') == 'Date' and prop.get('name') == 'now':
                    issues.append({
                        'type': 'timezone-naive-datetime',
                        'file': file_path,
                        'line': node.get('loc', {}).get('start', {}).get('line'),
                        'column': node.get('loc', {}).get('start', {}).get('column'),
                        'function': current_func or '<module>',
                        'severity': 'medium',
                        'description': 'Using naive datetime without timezone awareness'
                    })
                    
                # Resource management
                call_name = f"{obj.get('name', '')}.{prop.get('name', '')}"
                
                # File/stream operations
                if 'createReadStream' in call_name or 'createWriteStream' in call_name:
                    if not in_finally:
                        issues.append({
                            'type': 'stream-no-close',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'severity': 'high',
                            'description': 'Stream created without cleanup in finally block'
                        })
                        
                # Socket operations
                if 'socket' in call_name.lower() or 'createSocket' in call_name:
                    if not in_finally:
                        issues.append({
                            'type': 'socket-no-close',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'severity': 'high',
                            'description': 'Socket opened without proper cleanup'
                        })
                        
                # Database connections
                if 'connect' in call_name.lower() or 'createConnection' in call_name:
                    if not in_finally:
                        issues.append({
                            'type': 'connection-no-close',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'severity': 'high',
                            'description': 'Database/network connection without explicit close'
                        })
                        
        # Check try/finally blocks
        if node_type == 'TryStatement':
            # Process try block
            if node.get('block'):
                walk_tree(node['block'], current_func, False)
                
            # Process finally block
            if node.get('finalizer'):
                walk_tree(node['finalizer'], current_func, True)
                
            # Process handler
            if node.get('handler'):
                walk_tree(node['handler'], current_func, False)
                
            return  # Don't process children again
            
        # Email regex validation
        if node_type == 'CallExpression':
            callee_str = get_node_text(node.get('callee', {}))
            if 'RegExp' in callee_str or '.test' in callee_str or '.match' in callee_str:
                for arg in node.get('arguments', []):
                    if contains_email_pattern(arg):
                        issues.append({
                            'type': 'email-regex-validation',
                            'file': file_path,
                            'line': node.get('loc', {}).get('start', {}).get('line'),
                            'column': node.get('loc', {}).get('start', {}).get('column'),
                            'function': current_func or '<module>',
                            'severity': 'low',
                            'description': 'Using regex for email validation (use proper library instead)'
                        })
                        
        # Recursively process child nodes
        for key in node:
            if key in {'type', 'loc', 'range', 'raw', 'value'}:
                continue
                
            child = node[key]
            if isinstance(child, dict):
                walk_tree(child, current_func, in_finally)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        walk_tree(item, current_func, in_finally)
                        
    def get_node_text(node: Dict[str, Any]) -> str:
        """Get text representation of a node."""
        if not isinstance(node, dict):
            return str(node)
            
        if node.get('type') == 'Identifier':
            return node.get('name', '')
        elif node.get('type') == 'MemberExpression':
            return node.get('property', {}).get('name', '')
        elif node.get('type') == 'Literal':
            return str(node.get('value', ''))
        return ''
        
    def involves_float(node: Dict[str, Any]) -> bool:
        """Check if operation involves float."""
        for key in node:
            if key in {'type', 'loc', 'range'}:
                continue
                
            child = node[key]
            if isinstance(child, dict):
                if child.get('type') == 'CallExpression':
                    callee = child.get('callee', {})
                    if callee.get('name') == 'parseFloat':
                        return True
                    if callee.get('type') == 'MemberExpression':
                        if callee.get('property', {}).get('name') == 'parseFloat':
                            return True
                if involves_float(child):
                    return True
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict) and involves_float(item):
                        return True
        return False
        
    def has_timezone_context(node: Dict[str, Any]) -> bool:
        """Check if datetime operation has timezone context."""
        # Simplified check - would need more context in production
        return False
        
    def contains_email_pattern(node: Dict[str, Any]) -> bool:
        """Check if node contains email regex pattern."""
        if node.get('type') == 'Literal':
            value = str(node.get('value', ''))
            return '@' in value and ('\\@' in value or r'\@' in value)
        return False
        
    # Start walking from root
    walk_tree(tree)
    return issues


def find_logic_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find common logic and resource management issues in Python or JavaScript/TypeScript code.
    
    Detects:
    Business Logic Issues:
    1. money-float-arithmetic - Using float/double for money calculations
    2. percentage-calc-error - Missing parentheses in percentage calculations
    3. timezone-naive-datetime - Using datetime without timezone awareness
    4. email-regex-validation - Using regex for email validation
    5. divide-by-zero-risk - Division without zero check
    
    Resource Management Issues:
    6. file-no-close-finally - File opened without close in finally/with block
    7. connection-no-close - Database/network connection without explicit close
    8. transaction-no-end - Transaction begin without commit/rollback
    9. socket-no-close - Socket opened without proper cleanup
    10. stream-no-close - Stream created without cleanup
    
    Args:
        tree: AST tree (Python ast or ESLint/tree-sitter format)
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checker instance
        
    Returns:
        List of logic and resource issues found
    """
    try:
        # Check if it's a Python AST
        if hasattr(tree, '_fields'):
            analyzer = PythonLogicAnalyzer(file_path)
            analyzer.visit(tree)
            return analyzer.issues
            
        # Check if it's JavaScript/TypeScript ESLint AST
        elif isinstance(tree, dict) and 'type' in tree:
            if tree.get('type') == 'Program':
                return analyze_javascript_logic(tree, file_path)
                
        # Tree-sitter format
        elif hasattr(tree, 'root_node'):
            # Convert tree-sitter to dict for analysis
            # This would need proper tree-sitter traversal in production
            logger.warning(f"Tree-sitter AST not fully supported for logic analysis in {file_path}")
            return []
            
        return []
        
    except Exception as e:
        logger.error(f"Error analyzing logic issues in {file_path}: {e}")
        return []