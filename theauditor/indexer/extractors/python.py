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
            'returns': []
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
        else:
            # Fallback to regex extraction for routes if no AST
            result['routes'] = [(method, path, []) 
                               for method, path in self.extract_routes(content)]
        
        # Extract SQL queries embedded in Python code
        result['sql_queries'] = self.extract_sql_queries(content)
        
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