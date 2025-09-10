"""SQL safety analyzer for detecting dangerous SQL patterns.

Detects SQL safety issues in both Python and JavaScript/TypeScript code.
Replaces regex patterns from db_issues.yml with proper AST + SQL analysis.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Set, Tuple


def find_sql_safety_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find SQL safety issues in Python or JavaScript/TypeScript code.
    
    Detects:
    1. sql-string-concat - SQL with string concatenation (covered by sql_injection_analyzer)
    2. transaction-not-rolled-back - Transaction without rollback in error path
    3. missing-db-index-hint - Queries on commonly unindexed fields (heuristic)
    4. unbounded-query - SELECT without LIMIT
    5. nested-transaction - Nested transactions (deadlock risk)
    6. missing-where-clause-update - UPDATE without WHERE
    7. missing-where-clause-delete - DELETE without WHERE
    8. select-star-query - SELECT * usage
    
    Args:
        tree: Python AST or ESLint/tree-sitter AST from ast_parser.py
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checking function
    
    Returns:
        List of findings with details about SQL safety issues
    """
    findings = []
    
    # Determine tree type and analyze accordingly
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        if tree_type == "python_ast":
            actual_tree = tree.get("tree")
            if actual_tree:
                return _analyze_python_sql(actual_tree, file_path)
        elif tree_type == "eslint_ast":
            return _analyze_javascript_sql(tree, file_path)
        elif tree_type == "tree_sitter":
            # Simplified for tree-sitter
            return _analyze_tree_sitter_sql(tree, file_path)
    elif isinstance(tree, ast.AST):
        # Direct Python AST
        return _analyze_python_sql(tree, file_path)
    
    return findings


def _analyze_python_sql(tree: ast.AST, file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze Python AST for SQL safety issues."""
    analyzer = PythonSQLAnalyzer(file_path)
    analyzer.visit(tree)
    return analyzer.findings


class PythonSQLAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting SQL safety issues in Python."""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or "unknown"
        self.findings = []
        self.in_transaction = False
        self.transaction_depth = 0
        self.has_rollback = False
        self.current_try_block = None
        self.sql_strings = []  # Collect SQL strings for analysis
        
    def visit_Call(self, node: ast.Call):
        """Check for database operations."""
        call_name = self._get_call_name(node)
        
        # Check for transaction starts
        if any(trans in call_name.lower() for trans in ['begin', 'start_transaction', 'begin_transaction']):
            self.transaction_depth += 1
            if self.transaction_depth > 1:
                # Pattern 5: nested-transaction
                self.findings.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'type': 'nested_transaction',
                    'severity': 'HIGH',
                    'confidence': 0.85,
                    'message': 'Nested transaction detected - potential deadlock risk',
                    'hint': 'Avoid nested transactions or use savepoints instead'
                })
            self.in_transaction = True
        
        # Check for rollback
        if 'rollback' in call_name.lower():
            self.has_rollback = True
        
        # Check for SQL execution
        if any(exec_func in call_name.lower() for exec_func in ['execute', 'query', 'exec']):
            # Extract SQL string
            sql_string = self._extract_sql_string(node)
            if sql_string:
                self._analyze_sql_string(sql_string, node.lineno, node.col_offset)
        
        self.generic_visit(node)
    
    def visit_Try(self, node: ast.Try):
        """Track try blocks for transaction rollback checking."""
        old_try = self.current_try_block
        old_rollback = self.has_rollback
        
        self.current_try_block = node
        self.has_rollback = False
        
        # Visit the try body
        for stmt in node.body:
            self.visit(stmt)
        
        # Check if this try block has a transaction but no rollback in handlers
        if self.in_transaction:
            has_rollback_in_handlers = False
            
            # Check exception handlers
            for handler in node.handlers:
                for stmt in handler.body:
                    if self._contains_rollback(stmt):
                        has_rollback_in_handlers = True
                        break
            
            # Check finally block
            for stmt in node.finalbody:
                if self._contains_rollback(stmt):
                    has_rollback_in_handlers = True
                    break
            
            if not has_rollback_in_handlers and not self.has_rollback:
                # Pattern 2: transaction-not-rolled-back
                self.findings.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'type': 'transaction_not_rolled_back',
                    'severity': 'HIGH',
                    'confidence': 0.75,
                    'message': 'Transaction without rollback in error path',
                    'hint': 'Add rollback in except or finally block'
                })
        
        self.current_try_block = old_try
        self.has_rollback = old_rollback
    
    def visit_Constant(self, node: ast.Constant):
        """Collect SQL strings for analysis."""
        if isinstance(node.value, str):
            sql_upper = node.value.upper()
            if any(kw in sql_upper for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP']):
                self._analyze_sql_string(node.value, node.lineno, node.col_offset)
        self.generic_visit(node)
    
    def visit_Str(self, node: ast.Str):  # For Python < 3.8
        """Collect SQL strings for analysis."""
        sql_upper = node.s.upper()
        if any(kw in sql_upper for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP']):
            self._analyze_sql_string(node.s, node.lineno, node.col_offset)
        self.generic_visit(node)
    
    def _analyze_sql_string(self, sql: str, line: int, column: int):
        """Analyze a SQL string for safety issues."""
        sql_upper = sql.upper()
        
        # Pattern 4: unbounded-query
        if 'SELECT' in sql_upper and 'FROM' in sql_upper:
            if 'LIMIT' not in sql_upper and 'TOP' not in sql_upper:
                self.findings.append({
                    'line': line,
                    'column': column,
                    'type': 'unbounded_query',
                    'severity': 'MEDIUM',
                    'confidence': 0.80,
                    'message': 'SELECT query without LIMIT clause',
                    'hint': 'Add LIMIT to prevent memory issues with large result sets'
                })
        
        # Pattern 6: missing-where-clause-update
        if re.search(r'\bUPDATE\s+\S+\s+SET\s+', sql_upper):
            if 'WHERE' not in sql_upper:
                self.findings.append({
                    'line': line,
                    'column': column,
                    'type': 'missing_where_clause_update',
                    'severity': 'CRITICAL',
                    'confidence': 0.95,
                    'message': 'UPDATE without WHERE clause will affect ALL rows',
                    'hint': 'Add WHERE clause to target specific rows'
                })
        
        # Pattern 7: missing-where-clause-delete
        if re.search(r'\bDELETE\s+FROM\s+\S+', sql_upper):
            if 'WHERE' not in sql_upper:
                self.findings.append({
                    'line': line,
                    'column': column,
                    'type': 'missing_where_clause_delete',
                    'severity': 'CRITICAL',
                    'confidence': 0.95,
                    'message': 'DELETE without WHERE clause will delete ALL rows',
                    'hint': 'Add WHERE clause to target specific rows'
                })
        
        # Pattern 8: select-star-query
        if re.search(r'SELECT\s+\*\s+FROM', sql_upper):
            self.findings.append({
                'line': line,
                'column': column,
                'type': 'select_star_query',
                'severity': 'LOW',
                'confidence': 0.90,
                'message': 'SELECT * query - specify needed columns',
                'hint': 'List specific columns for better performance and stability'
            })
        
        # Pattern 3: missing-db-index-hint (heuristic)
        common_unindexed = ['EMAIL', 'USERNAME', 'USER_ID', 'CREATED_AT', 'UPDATED_AT', 'STATUS']
        if 'WHERE' in sql_upper:
            for field in common_unindexed:
                if f'WHERE {field}' in sql_upper or f'WHERE {field.lower()}' in sql:
                    self.findings.append({
                        'line': line,
                        'column': column,
                        'type': 'missing_db_index_hint',
                        'severity': 'MEDIUM',
                        'confidence': 0.60,
                        'message': f'Query on potentially unindexed field: {field.lower()}',
                        'hint': f'Consider adding index on {field.lower()} if queries are slow'
                    })
                    break
    
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
    
    def _extract_sql_string(self, node: ast.Call) -> Optional[str]:
        """Try to extract SQL string from a call node."""
        if node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant):
                return first_arg.value if isinstance(first_arg.value, str) else None
            elif isinstance(first_arg, ast.Str):  # Python < 3.8
                return first_arg.s
        return None
    
    def _contains_rollback(self, node: ast.AST) -> bool:
        """Check if a node contains a rollback call."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if 'rollback' in call_name.lower():
                    return True
        return False


def _analyze_javascript_sql(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript ESLint AST for SQL safety issues."""
    findings = []
    
    ast = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not ast or not isinstance(ast, dict):
        return findings
    
    # Track state
    in_transaction = False
    transaction_depth = 0
    has_rollback = False
    
    def traverse_ast(node: Dict[str, Any], parent: Dict[str, Any] = None):
        nonlocal in_transaction, transaction_depth, has_rollback
        
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Check for database calls
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            call_text = _extract_call_text(callee, content)
            
            # Check for transactions
            if any(trans in call_text.lower() for trans in ['begin', 'transaction', 'starttransaction']):
                transaction_depth += 1
                if transaction_depth > 1:
                    # Pattern 5: nested-transaction
                    loc = node.get("loc", {}).get("start", {})
                    findings.append({
                        'line': loc.get("line", 0),
                        'column': loc.get("column", 0),
                        'type': 'nested_transaction',
                        'severity': 'HIGH',
                        'confidence': 0.85,
                        'message': 'Nested transaction detected - potential deadlock risk',
                        'hint': 'Avoid nested transactions or use savepoints'
                    })
                in_transaction = True
            
            # Check for rollback
            if 'rollback' in call_text.lower():
                has_rollback = True
            
            # Check for SQL execution (sequelize.query, db.query, etc.)
            if any(exec_func in call_text.lower() for exec_func in ['.query', '.execute', '.exec', '.raw']):
                # Extract SQL string from arguments
                sql_string = _extract_sql_from_call(node, content)
                if sql_string:
                    _analyze_sql_string_js(sql_string, node, findings)
        
        # Check try/catch blocks for transaction rollback
        if node_type == "TryStatement":
            block = node.get("block", {})
            handler = node.get("handler", {})
            finalizer = node.get("finalizer", {})
            
            # Check if there's a transaction in the try block
            has_transaction_in_try = _contains_pattern(block, ['transaction', 'begin'])
            
            if has_transaction_in_try:
                # Check for rollback in catch or finally
                has_rollback_in_handler = False
                
                if handler:
                    handler_body = handler.get("body", {})
                    if _contains_pattern(handler_body, ['rollback']):
                        has_rollback_in_handler = True
                
                if finalizer and not has_rollback_in_handler:
                    if _contains_pattern(finalizer, ['rollback']):
                        has_rollback_in_handler = True
                
                if not has_rollback_in_handler:
                    # Pattern 2: transaction-not-rolled-back
                    loc = node.get("loc", {}).get("start", {})
                    findings.append({
                        'line': loc.get("line", 0),
                        'column': loc.get("column", 0),
                        'type': 'transaction_not_rolled_back',
                        'severity': 'HIGH',
                        'confidence': 0.75,
                        'message': 'Transaction without rollback in error path',
                        'hint': 'Add rollback in catch or finally block'
                    })
        
        # Check for SQL in string literals
        if node_type in ["Literal", "TemplateLiteral"]:
            sql_string = None
            
            if node_type == "Literal" and isinstance(node.get("value"), str):
                sql_string = node.get("value")
            elif node_type == "TemplateLiteral":
                # Reconstruct template literal (simplified)
                quasis = node.get("quasis", [])
                if quasis:
                    sql_string = quasis[0].get("value", {}).get("cooked", "")
            
            if sql_string:
                sql_upper = sql_string.upper()
                if any(kw in sql_upper for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
                    _analyze_sql_string_js(sql_string, node, findings)
        
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


def _analyze_sql_string_js(sql: str, node: Dict[str, Any], findings: List[Dict[str, Any]]):
    """Analyze SQL string for safety issues in JavaScript context."""
    sql_upper = sql.upper()
    loc = node.get("loc", {}).get("start", {})
    
    # Pattern 4: unbounded-query
    if 'SELECT' in sql_upper and 'FROM' in sql_upper:
        if 'LIMIT' not in sql_upper and 'TOP' not in sql_upper:
            findings.append({
                'line': loc.get("line", 0),
                'column': loc.get("column", 0),
                'type': 'unbounded_query',
                'severity': 'MEDIUM',
                'confidence': 0.80,
                'message': 'SELECT query without LIMIT clause',
                'hint': 'Add LIMIT to prevent memory issues'
            })
    
    # Pattern 6: missing-where-clause-update
    if re.search(r'\bUPDATE\s+\S+\s+SET\s+', sql_upper):
        if 'WHERE' not in sql_upper:
            findings.append({
                'line': loc.get("line", 0),
                'column': loc.get("column", 0),
                'type': 'missing_where_clause_update',
                'severity': 'CRITICAL',
                'confidence': 0.95,
                'message': 'UPDATE without WHERE clause will affect ALL rows',
                'hint': 'Add WHERE clause to target specific rows'
            })
    
    # Pattern 7: missing-where-clause-delete
    if re.search(r'\bDELETE\s+FROM\s+\S+', sql_upper):
        if 'WHERE' not in sql_upper:
            findings.append({
                'line': loc.get("line", 0),
                'column': loc.get("column", 0),
                'type': 'missing_where_clause_delete',
                'severity': 'CRITICAL',
                'confidence': 0.95,
                'message': 'DELETE without WHERE clause will delete ALL rows',
                'hint': 'Add WHERE clause to target specific rows'
            })
    
    # Pattern 8: select-star-query
    if re.search(r'SELECT\s+\*\s+FROM', sql_upper):
        findings.append({
            'line': loc.get("line", 0),
            'column': loc.get("column", 0),
            'type': 'select_star_query',
            'severity': 'LOW',
            'confidence': 0.90,
            'message': 'SELECT * query - specify needed columns',
            'hint': 'List specific columns for better performance'
        })
    
    # Pattern 3: missing-db-index-hint
    common_unindexed = ['EMAIL', 'USERNAME', 'USER_ID', 'CREATED_AT', 'UPDATED_AT', 'STATUS']
    if 'WHERE' in sql_upper:
        for field in common_unindexed:
            if f'WHERE {field}' in sql_upper:
                findings.append({
                    'line': loc.get("line", 0),
                    'column': loc.get("column", 0),
                    'type': 'missing_db_index_hint',
                    'severity': 'MEDIUM',
                    'confidence': 0.60,
                    'message': f'Query on potentially unindexed field: {field.lower()}',
                    'hint': f'Consider adding index on {field.lower()}'
                })
                break


def _extract_call_text(callee: Dict[str, Any], content: str) -> str:
    """Extract call text from ESLint AST node."""
    if callee.get("type") == "Identifier":
        return callee.get("name", "")
    elif callee.get("type") == "MemberExpression":
        obj = callee.get("object", {})
        prop = callee.get("property", {})
        
        obj_name = ""
        if obj.get("type") == "Identifier":
            obj_name = obj.get("name", "")
        
        prop_name = ""
        if prop.get("type") == "Identifier":
            prop_name = prop.get("name", "")
        
        return f"{obj_name}.{prop_name}"
    
    return ""


def _extract_sql_from_call(call_node: Dict[str, Any], content: str) -> Optional[str]:
    """Extract SQL string from a call expression."""
    args = call_node.get("arguments", [])
    
    if args:
        first_arg = args[0]
        
        # Handle string literal
        if first_arg.get("type") == "Literal":
            value = first_arg.get("value")
            if isinstance(value, str):
                return value
        
        # Handle template literal (simplified)
        elif first_arg.get("type") == "TemplateLiteral":
            quasis = first_arg.get("quasis", [])
            if quasis:
                return quasis[0].get("value", {}).get("cooked", "")
    
    return None


def _contains_pattern(node: Dict[str, Any], patterns: List[str]) -> bool:
    """Check if node contains any of the patterns."""
    if not isinstance(node, dict):
        return False
    
    # Check current node
    for key, value in node.items():
        if isinstance(value, str):
            for pattern in patterns:
                if pattern.lower() in value.lower():
                    return True
    
    # Recurse
    for key, value in node.items():
        if isinstance(value, dict):
            if _contains_pattern(value, patterns):
                return True
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if _contains_pattern(item, patterns):
                        return True
    
    return False


def _analyze_tree_sitter_sql(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze tree-sitter AST (simplified implementation)."""
    # Would need tree-sitter specific implementation
    # For now, return empty list
    return []