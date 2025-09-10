"""Multi-tenant security analyzer for PostgreSQL RLS patterns.

Detects multi-tenant security issues primarily in JavaScript/TypeScript (Sequelize)
but also checks Python code for similar patterns.
Replaces regex patterns from multi_tenant.yml with proper AST analysis.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Set


def find_multi_tenant_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find multi-tenant security issues in Python or JavaScript/TypeScript code.
    
    Detects:
    1. cross-tenant-data-leak - Raw SQL on sensitive tables without tenant filtering
    2. rls-policy-without-using - CREATE POLICY without USING clause (SQL DDL)
    3. missing-rls-context-setting - Transaction without SET LOCAL app.current_facility_id
    4. raw-query-without-transaction - Raw SQL without transaction context
    5. bypass-rls-with-superuser - Using postgres/superuser connection (config issue)
    
    Args:
        tree: Python AST or ESLint/tree-sitter AST from ast_parser.py
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checking function
    
    Returns:
        List of findings with details about multi-tenant security issues
    """
    findings = []
    
    # Determine tree type and analyze accordingly
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        if tree_type == "python_ast":
            actual_tree = tree.get("tree")
            if actual_tree:
                return _analyze_python_multitenant(actual_tree, file_path)
        elif tree_type == "eslint_ast":
            return _analyze_javascript_multitenant(tree, file_path)
        elif tree_type == "tree_sitter":
            return _analyze_tree_sitter_multitenant(tree, file_path)
    elif isinstance(tree, ast.AST):
        # Direct Python AST
        return _analyze_python_multitenant(tree, file_path)
    
    return findings


def _analyze_python_multitenant(tree: ast.AST, file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze Python AST for multi-tenant security issues."""
    analyzer = PythonMultiTenantAnalyzer(file_path)
    analyzer.visit(tree)
    return analyzer.findings


class PythonMultiTenantAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting multi-tenant issues in Python."""
    
    # Sensitive tables that should have tenant filtering
    SENSITIVE_TABLES = [
        'products', 'orders', 'inventory', 'customers', 'users', 
        'locations', 'transfers', 'invoices', 'payments', 'shipments'
    ]
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or "unknown"
        self.findings = []
        self.in_transaction = False
        self.has_set_local = False
        self.current_transaction_node = None
        
    def visit_Call(self, node: ast.Call):
        """Check for database operations and transactions."""
        call_name = self._get_call_name(node)
        
        # Check for transaction starts
        if any(trans in call_name.lower() for trans in ['transaction', 'begin_nested', 'atomic']):
            old_transaction = self.in_transaction
            old_set_local = self.has_set_local
            old_node = self.current_transaction_node
            
            self.in_transaction = True
            self.has_set_local = False
            self.current_transaction_node = node
            
            # Check the transaction body
            self.generic_visit(node)
            
            # Pattern 3: missing-rls-context-setting
            if not self.has_set_local:
                self.findings.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'type': 'missing_rls_context_setting',
                    'severity': 'HIGH',
                    'confidence': 0.75,
                    'message': 'Transaction without SET LOCAL app.current_facility_id',
                    'hint': "Add cursor.execute('SET LOCAL app.current_facility_id = %s', [facility_id])"
                })
            
            self.in_transaction = old_transaction
            self.has_set_local = old_set_local
            self.current_transaction_node = old_node
            return
        
        # Check for SET LOCAL
        if 'execute' in call_name.lower():
            sql_string = self._extract_sql_string(node)
            if sql_string:
                sql_upper = sql_string.upper()
                
                # Check if it's SET LOCAL for RLS context
                if 'SET LOCAL' in sql_upper and 'CURRENT_FACILITY_ID' in sql_upper:
                    self.has_set_local = True
                
                # Check for raw queries on sensitive tables
                self._check_cross_tenant_leak(sql_string, node)
                
                # Check for CREATE POLICY without USING
                self._check_rls_policy(sql_string, node)
                
                # Pattern 4: raw-query-without-transaction
                if not self.in_transaction:
                    if any(table in sql_string.lower() for table in self.SENSITIVE_TABLES):
                        self.findings.append({
                            'line': node.lineno,
                            'column': node.col_offset,
                            'type': 'raw_query_without_transaction',
                            'severity': 'HIGH',
                            'confidence': 0.70,
                            'message': 'Raw SQL query outside transaction context (RLS may not apply)',
                            'hint': 'Execute query within a transaction with proper RLS context'
                        })
        
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign):
        """Check for database configuration assignments."""
        # Pattern 5: bypass-rls-with-superuser
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id.upper()
                if any(db_var in var_name for db_var in ['DB_USER', 'DATABASE_USER', 'POSTGRES_USER']):
                    # Check the value being assigned
                    if isinstance(node.value, ast.Constant):
                        value = str(node.value.value).lower()
                        if value in ['postgres', 'root', 'admin', 'superuser', 'sa']:
                            self.findings.append({
                                'line': node.lineno,
                                'column': node.col_offset,
                                'type': 'bypass_rls_with_superuser',
                                'variable': target.id,
                                'value': value,
                                'severity': 'CRITICAL',
                                'confidence': 0.80,
                                'message': f'Using superuser "{value}" bypasses RLS policies',
                                'hint': 'Use a limited database user with RLS policies applied'
                            })
        
        self.generic_visit(node)
    
    def _check_cross_tenant_leak(self, sql: str, node: ast.AST):
        """Check for cross-tenant data leak patterns."""
        sql_upper = sql.upper()
        
        # Pattern 1: cross-tenant-data-leak
        # Check if query touches sensitive tables
        for table in self.SENSITIVE_TABLES:
            if table.upper() in sql_upper:
                # Check if it has WHERE clause with facility_id or tenant_id
                has_tenant_filter = any(
                    tenant_field in sql_upper 
                    for tenant_field in ['FACILITY_ID', 'TENANT_ID', 'ORGANIZATION_ID']
                )
                
                if not has_tenant_filter and 'WHERE' in sql_upper:
                    # Has WHERE but no tenant filter
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'cross_tenant_data_leak',
                        'table': table,
                        'severity': 'CRITICAL',
                        'confidence': 0.85,
                        'message': f'Query on {table} without tenant filtering',
                        'hint': 'Add facility_id/tenant_id to WHERE clause'
                    })
                elif not has_tenant_filter and 'WHERE' not in sql_upper:
                    # No WHERE clause at all
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'cross_tenant_data_leak',
                        'table': table,
                        'severity': 'CRITICAL',
                        'confidence': 0.90,
                        'message': f'Query on {table} with no WHERE clause (no tenant filtering)',
                        'hint': 'Add WHERE facility_id = ... for tenant isolation'
                    })
                break
    
    def _check_rls_policy(self, sql: str, node: ast.AST):
        """Check for RLS policy issues."""
        sql_upper = sql.upper()
        
        # Pattern 2: rls-policy-without-using
        if 'CREATE POLICY' in sql_upper:
            if 'USING' not in sql_upper:
                self.findings.append({
                    'line': node.lineno,
                    'column': node.col_offset,
                    'type': 'rls_policy_without_using',
                    'severity': 'CRITICAL',
                    'confidence': 0.95,
                    'message': 'CREATE POLICY without USING clause for row filtering',
                    'hint': "Add USING clause: USING (facility_id = current_setting('app.current_facility_id')::uuid)"
                })
    
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


def _analyze_javascript_multitenant(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript ESLint AST for multi-tenant security issues."""
    findings = []
    
    ast = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not ast or not isinstance(ast, dict):
        return findings
    
    # Sensitive tables that need tenant filtering
    SENSITIVE_TABLES = [
        'products', 'orders', 'inventory', 'customers', 'users',
        'locations', 'transfers', 'invoices', 'payments', 'shipments'
    ]
    
    # Track state
    in_transaction = False
    has_set_local = False
    
    def traverse_ast(node: Dict[str, Any], parent: Dict[str, Any] = None):
        nonlocal in_transaction, has_set_local
        
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Check for Sequelize operations
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            call_text = _extract_call_text(callee, content)
            
            # Check for sequelize.transaction()
            if 'sequelize.transaction' in call_text.lower():
                old_transaction = in_transaction
                old_set_local = has_set_local
                
                in_transaction = True
                has_set_local = False
                
                # Check the transaction callback
                args = node.get("arguments", [])
                for arg in args:
                    if arg.get("type") in ["ArrowFunctionExpression", "FunctionExpression"]:
                        body = arg.get("body", {})
                        
                        # Check if SET LOCAL is called in transaction
                        if not _contains_set_local(body, content):
                            # Pattern 3: missing-rls-context-setting
                            loc = node.get("loc", {}).get("start", {})
                            findings.append({
                                'line': loc.get("line", 0),
                                'column': loc.get("column", 0),
                                'type': 'missing_rls_context_setting',
                                'severity': 'HIGH',
                                'confidence': 0.75,
                                'message': 'Sequelize transaction without SET LOCAL app.current_facility_id',
                                'hint': "Add: await sequelize.query('SET LOCAL app.current_facility_id = :id', {transaction: t})"
                            })
                        
                        # Continue checking the body
                        traverse_ast(body, node)
                
                in_transaction = old_transaction
                has_set_local = old_set_local
                return
            
            # Check for sequelize.query()
            if 'sequelize.query' in call_text.lower() or '.query' in call_text.lower():
                # Extract SQL string
                sql_string = _extract_sql_from_call(node, content)
                
                if sql_string:
                    sql_upper = sql_string.upper()
                    
                    # Check if it's SET LOCAL
                    if 'SET LOCAL' in sql_upper and 'CURRENT_FACILITY_ID' in sql_upper:
                        has_set_local = True
                    
                    # Pattern 1: cross-tenant-data-leak
                    for table in SENSITIVE_TABLES:
                        if table.upper() in sql_upper:
                            # Check for tenant filtering
                            has_tenant_filter = any(
                                field in sql_upper
                                for field in ['FACILITY_ID', 'TENANT_ID', 'ORGANIZATION_ID']
                            )
                            
                            if not has_tenant_filter:
                                loc = node.get("loc", {}).get("start", {})
                                findings.append({
                                    'line': loc.get("line", 0),
                                    'column': loc.get("column", 0),
                                    'type': 'cross_tenant_data_leak',
                                    'table': table,
                                    'severity': 'CRITICAL',
                                    'confidence': 0.85,
                                    'message': f'Sequelize query on {table} without tenant filtering',
                                    'hint': 'Add facility_id to WHERE clause or use ORM with RLS'
                                })
                            break
                    
                    # Pattern 2: rls-policy-without-using
                    if 'CREATE POLICY' in sql_upper and 'USING' not in sql_upper:
                        loc = node.get("loc", {}).get("start", {})
                        findings.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'type': 'rls_policy_without_using',
                            'severity': 'CRITICAL',
                            'confidence': 0.95,
                            'message': 'CREATE POLICY without USING clause',
                            'hint': "Add USING (facility_id = current_setting('app.current_facility_id')::uuid)"
                        })
                    
                    # Pattern 4: raw-query-without-transaction
                    if not in_transaction:
                        # Check if transaction is passed as option
                        has_transaction_option = False
                        args = node.get("arguments", [])
                        if len(args) > 1:
                            options_arg = args[1]
                            if options_arg.get("type") == "ObjectExpression":
                                properties = options_arg.get("properties", [])
                                for prop in properties:
                                    key = prop.get("key", {})
                                    if key.get("name") == "transaction":
                                        has_transaction_option = True
                                        break
                        
                        if not has_transaction_option:
                            # Check if query touches sensitive tables
                            if any(table.upper() in sql_upper for table in SENSITIVE_TABLES):
                                loc = node.get("loc", {}).get("start", {})
                                findings.append({
                                    'line': loc.get("line", 0),
                                    'column': loc.get("column", 0),
                                    'type': 'raw_query_without_transaction',
                                    'severity': 'HIGH',
                                    'confidence': 0.70,
                                    'message': 'Raw Sequelize query without transaction context',
                                    'hint': 'Pass transaction option: {transaction: t}'
                                })
        
        # Check for configuration assignments (Pattern 5)
        if node_type == "AssignmentExpression":
            left = node.get("left", {})
            right = node.get("right", {})
            
            # Check for DB_USER type assignments
            if left.get("type") == "MemberExpression":
                prop = left.get("property", {})
                if prop.get("type") == "Identifier":
                    prop_name = prop.get("name", "").upper()
                    if any(db_var in prop_name for db_var in ['DB_USER', 'DATABASE_USER', 'POSTGRES_USER']):
                        # Check the value
                        if right.get("type") == "Literal":
                            value = str(right.get("value", "")).lower()
                            if value in ['postgres', 'root', 'admin', 'superuser', 'sa']:
                                loc = node.get("loc", {}).get("start", {})
                                findings.append({
                                    'line': loc.get("line", 0),
                                    'column': loc.get("column", 0),
                                    'type': 'bypass_rls_with_superuser',
                                    'variable': prop.get("name"),
                                    'value': value,
                                    'severity': 'CRITICAL',
                                    'confidence': 0.80,
                                    'message': f'Using superuser "{value}" bypasses RLS',
                                    'hint': 'Use limited database user with RLS policies'
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
        
        # Handle template literal
        elif first_arg.get("type") == "TemplateLiteral":
            # Try to reconstruct the SQL (simplified - won't handle expressions)
            quasis = first_arg.get("quasis", [])
            if quasis:
                parts = []
                for quasi in quasis:
                    cooked = quasi.get("value", {}).get("cooked", "")
                    parts.append(cooked)
                return ' '.join(parts)
    
    return None


def _contains_set_local(node: Dict[str, Any], content: str) -> bool:
    """Check if node contains SET LOCAL app.current_facility_id."""
    if not isinstance(node, dict):
        return False
    
    # Check if this is a query call with SET LOCAL
    if node.get("type") == "CallExpression":
        call_text = _extract_call_text(node.get("callee", {}), content)
        if 'query' in call_text.lower():
            sql = _extract_sql_from_call(node, content)
            if sql:
                sql_upper = sql.upper()
                if 'SET LOCAL' in sql_upper and 'CURRENT_FACILITY_ID' in sql_upper:
                    return True
    
    # Recurse through children
    for key, value in node.items():
        if key in ["type", "loc", "range"]:
            continue
        
        if isinstance(value, dict):
            if _contains_set_local(value, content):
                return True
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if _contains_set_local(item, content):
                        return True
    
    return False


def _analyze_tree_sitter_multitenant(tree_wrapper: Dict[str, Any], file_path: str = None) -> List[Dict[str, Any]]:
    """Analyze tree-sitter AST (simplified implementation)."""
    # Would need tree-sitter specific implementation
    # For now, return empty list
    return []