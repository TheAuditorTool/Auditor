"""Python file extractor.

Handles extraction of Python-specific elements including:
- Python imports (import/from statements)
- Flask/FastAPI route decorators with middleware
- AST-based symbol extraction
"""

import ast
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor


class PythonExtractor(BaseExtractor):
    """Extractor for Python files."""
    
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.py', '.pyx']
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a Python file.
        
        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree
            
        Returns:
            Dictionary containing all extracted data
        """
        result = {
            'imports': [],
            'routes': [],
            'symbols': [],
            'assignments': [],
            'function_calls': [],
            'returns': [],
            'variable_usage': [],  # CRITICAL: Track all variable usage for complete analysis
            'cfg': []  # Control flow graph data
        }
        
        # Extract imports using regex patterns (for all types)
        result['imports'] = self.extract_imports(content, file_info['ext'])
        
        # If we have an AST tree, extract Python-specific information
        if tree and isinstance(tree, dict):
            # Extract routes with decorators using AST
            result['routes'] = self._extract_routes_ast(tree, file_info['path'])
            
            # Extract symbols from AST parser results
            if self.ast_parser:
                # Functions
                functions = self.ast_parser.extract_functions(tree)
                for func in functions:
                    result['symbols'].append({
                        'name': func.get('name', ''),
                        'type': 'function',
                        'line': func.get('line', 0),
                        'end_line': func.get('end_line', func.get('line', 0)),  # Use end_line if available
                        'col': func.get('col', 0)
                    })
                
                # Classes
                classes = self.ast_parser.extract_classes(tree)
                for cls in classes:
                    result['symbols'].append({
                        'name': cls.get('name', ''),
                        'type': 'class',
                        'line': cls.get('line', 0),
                        'col': cls.get('col', 0)
                    })
                
                # Calls and other symbols
                symbols = self.ast_parser.extract_calls(tree)
                for symbol in symbols:
                    result['symbols'].append({
                        'name': symbol.get('name', ''),
                        'type': symbol.get('type', 'call'),
                        'line': symbol.get('line', 0),
                        'col': symbol.get('col', symbol.get('column', 0))
                    })
                
                # Extract data flow information for taint analysis
                assignments = self.ast_parser.extract_assignments(tree)
                for assignment in assignments:
                    result['assignments'].append({
                        'line': assignment.get('line', 0),
                        'target_var': assignment.get('target_var', ''),
                        'source_expr': assignment.get('source_expr', ''),
                        'source_vars': assignment.get('source_vars', []),
                        'in_function': assignment.get('in_function', 'global')
                    })
                
                # Extract function calls with arguments
                calls_with_args = self.ast_parser.extract_function_calls_with_args(tree)
                for call in calls_with_args:
                    result['function_calls'].append({
                        'line': call.get('line', 0),
                        'caller_function': call.get('caller_function', 'global'),
                        'callee_function': call.get('callee_function', ''),
                        'argument_index': call.get('argument_index', 0),
                        'argument_expr': call.get('argument_expr', ''),
                        'param_name': call.get('param_name', '')
                    })
                
                # Extract return statements
                return_statements = self.ast_parser.extract_returns(tree)
                for ret in return_statements:
                    result['returns'].append({
                        'line': ret.get('line', 0),
                        'function_name': ret.get('function_name', 'global'),
                        'return_expr': ret.get('return_expr', ''),
                        'return_vars': ret.get('return_vars', [])
                    })
            
            # Extract control flow graph using centralized AST infrastructure
            if tree and self.ast_parser:
                result['cfg'] = self.ast_parser.extract_cfg(tree)
        else:
            # Fallback to regex extraction for routes if no AST
            result['routes'] = [(method, path, []) 
                               for method, path in self.extract_routes(content)]
        
        # Extract SQL queries embedded in Python code
        result['sql_queries'] = self.extract_sql_queries(content)

        # Extract JWT patterns (Python also uses JWT libraries like PyJWT)
        result['jwt_patterns'] = self.extract_jwt_patterns(content)

        # CRITICAL FIX: Extract variable usage for ALL Python files
        # This is essential for complete taint analysis and dead code detection
        if tree and self.ast_parser:
            result['variable_usage'] = self._extract_variable_usage(tree, content)

        return result
    
    def _extract_routes_ast(self, tree: Dict[str, Any], file_path: str) -> List[tuple]:
        """Extract Flask/FastAPI routes using Python AST.
        
        Args:
            tree: Parsed AST tree
            file_path: Path to file being analyzed
            
        Returns:
            List of (method, pattern, controls) tuples
        """
        routes = []
        
        # Check if we have a Python AST tree
        if not isinstance(tree.get("tree"), ast.Module):
            return routes
        
        # Walk the AST to find decorated functions
        for node in ast.walk(tree["tree"]):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = []
                route_info = None
                
                # Extract all decorator names
                for decorator in node.decorator_list:
                    dec_name = None
                    if isinstance(decorator, ast.Name):
                        dec_name = decorator.id
                    elif isinstance(decorator, ast.Attribute):
                        dec_name = decorator.attr
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            # Handle @app.route('/path') or @router.get('/path')
                            method_name = decorator.func.attr
                            if method_name in ['route', 'get', 'post', 'put', 'patch', 'delete']:
                                # Extract path from first argument
                                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                    path = decorator.args[0].value
                                    # Determine HTTP method
                                    if method_name == 'route':
                                        # Check for methods argument
                                        method = 'GET'  # Default
                                        for keyword in decorator.keywords:
                                            if keyword.arg == 'methods':
                                                if isinstance(keyword.value, ast.List):
                                                    if keyword.value.elts:
                                                        if isinstance(keyword.value.elts[0], ast.Constant):
                                                            method = keyword.value.elts[0].value.upper()
                                    else:
                                        method = method_name.upper()
                                    route_info = (method, path)
                            dec_name = method_name
                        elif isinstance(decorator.func, ast.Name):
                            dec_name = decorator.func.id
                    
                    # Collect non-route decorators as potential middleware/controls
                    if dec_name and dec_name not in ['route', 'get', 'post', 'put', 'patch', 'delete']:
                        decorators.append(dec_name)
                
                # If we found a route, add it with its security decorators
                if route_info:
                    routes.append((route_info[0], route_info[1], decorators))

        return routes

    def _extract_variable_usage(self, tree: Dict[str, Any], content: str) -> List[Dict]:
        """Extract ALL variable usage for complete data flow analysis.

        This is critical for taint analysis, dead code detection, and
        understanding the complete data flow in Python code.

        Args:
            tree: Parsed AST tree dictionary
            content: File content

        Returns:
            List of all variable usage records with read/write/delete operations
        """
        usage = []
        actual_tree = tree.get("tree")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            return usage

        try:
            # Build function ranges for accurate scope mapping
            function_ranges = {}
            class_ranges = {}

            # First pass: Map all functions and classes
            for node in ast.walk(actual_tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                        function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
                elif isinstance(node, ast.ClassDef):
                    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                        class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

            # Helper to determine scope for a line number
            def get_scope(line_no):
                # Check if in a function
                for fname, (start, end) in function_ranges.items():
                    if start <= line_no <= end:
                        # Check if this function is inside a class
                        for cname, (cstart, cend) in class_ranges.items():
                            if cstart <= start <= cend:
                                return f"{cname}.{fname}"
                        return fname

                # Check if in a class (but not in a method)
                for cname, (start, end) in class_ranges.items():
                    if start <= line_no <= end:
                        return cname

                return "global"

            # Second pass: Extract all variable usage
            for node in ast.walk(actual_tree):
                if isinstance(node, ast.Name) and hasattr(node, 'lineno'):
                    # Determine usage type based on context
                    usage_type = "read"
                    if isinstance(node.ctx, ast.Store):
                        usage_type = "write"
                    elif isinstance(node.ctx, ast.Del):
                        usage_type = "delete"
                    elif isinstance(node.ctx, ast.AugStore):
                        usage_type = "augmented_write"  # +=, -=, etc.
                    elif isinstance(node.ctx, ast.Param):
                        usage_type = "param"  # Function parameter

                    scope = get_scope(node.lineno)

                    usage.append({
                        'line': node.lineno,
                        'variable_name': node.id,
                        'usage_type': usage_type,
                        'in_component': scope,  # In Python, this is the function/class name
                        'in_hook': '',  # Python doesn't have hooks
                        'scope_level': 0 if scope == "global" else (2 if "." in scope else 1)
                    })

                # Also track attribute access (e.g., self.var, obj.attr)
                elif isinstance(node, ast.Attribute) and hasattr(node, 'lineno'):
                    # Build the full attribute chain
                    attr_chain = []
                    current = node
                    while isinstance(current, ast.Attribute):
                        attr_chain.append(current.attr)
                        current = current.value

                    # Add the base
                    if isinstance(current, ast.Name):
                        attr_chain.append(current.id)

                    # Reverse to get correct order
                    full_name = ".".join(reversed(attr_chain))

                    # Determine usage type
                    usage_type = "read"
                    if isinstance(node.ctx, ast.Store):
                        usage_type = "write"
                    elif isinstance(node.ctx, ast.Del):
                        usage_type = "delete"

                    scope = get_scope(node.lineno)

                    usage.append({
                        'line': node.lineno,
                        'variable_name': full_name,
                        'usage_type': usage_type,
                        'in_component': scope,
                        'in_hook': '',
                        'scope_level': 0 if scope == "global" else (2 if "." in scope else 1)
                    })

                # Track function/method calls as variable usage (the function name is "read")
                elif isinstance(node, ast.Call) and hasattr(node, 'lineno'):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        # Build the call chain
                        attr_chain = []
                        current = node.func
                        while isinstance(current, ast.Attribute):
                            attr_chain.append(current.attr)
                            current = current.value
                        if isinstance(current, ast.Name):
                            attr_chain.append(current.id)
                        func_name = ".".join(reversed(attr_chain))

                    if func_name:
                        scope = get_scope(node.lineno)
                        usage.append({
                            'line': node.lineno,
                            'variable_name': func_name,
                            'usage_type': 'call',  # Special type for function calls
                            'in_component': scope,
                            'in_hook': '',
                            'scope_level': 0 if scope == "global" else (2 if "." in scope else 1)
                        })

            # Deduplicate while preserving order
            seen = set()
            deduped_usage = []
            for use in usage:
                key = (use['line'], use['variable_name'], use['usage_type'])
                if key not in seen:
                    seen.add(key)
                    deduped_usage.append(use)

            return deduped_usage

        except Exception as e:
            # Log error but don't fail the extraction
            import os
            if os.environ.get("THEAUDITOR_DEBUG"):
                import sys
                print(f"[DEBUG] Error in Python variable extraction: {e}", file=sys.stderr)
            return usage