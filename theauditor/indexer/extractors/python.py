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
            
            # Extract control flow graph for each function
            # Try to get Python AST if available
            if tree and 'tree' in tree:
                # Check if we have a Python AST (from Python files parsed with ast module)
                python_ast = None
                
                # Sometimes the tree is wrapped
                tree_obj = tree.get('tree')
                
                # Try to parse Python code to get AST for CFG
                try:
                    import ast as python_ast_module
                    python_ast = python_ast_module.parse(content)
                    result['cfg'] = self._extract_control_flow(python_ast, file_info['path'])
                except:
                    # Failed to parse as Python AST
                    pass
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
    
    def _extract_control_flow(self, module: ast.Module, file_path: str) -> List[Dict[str, Any]]:
        """Extract control flow graph from Python AST.
        
        Args:
            module: Python AST module
            file_path: Path to the file
            
        Returns:
            List of CFG data for each function
        """
        cfg_data = []
        
        # Find all functions and methods
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_cfg = self._build_function_cfg(node, file_path)
                if function_cfg:
                    cfg_data.append(function_cfg)
        
        return cfg_data
    
    def _build_function_cfg(self, func_node: ast.FunctionDef, file_path: str) -> Dict[str, Any]:
        """Build control flow graph for a single function.
        
        Args:
            func_node: Function AST node
            file_path: Path to the file
            
        Returns:
            CFG data dictionary
        """
        blocks = []
        edges = []
        block_id_counter = [0]  # Use list to allow mutation in nested function
        
        def get_next_block_id():
            block_id_counter[0] += 1
            return block_id_counter[0]
        
        # Entry block
        entry_block_id = get_next_block_id()
        blocks.append({
            'id': entry_block_id,
            'type': 'entry',
            'start_line': func_node.lineno,
            'end_line': func_node.lineno,
            'statements': []
        })
        
        # Process function body
        current_block_id = entry_block_id
        exit_block_id = None
        
        for stmt in func_node.body:
            block_info = self._process_statement(stmt, current_block_id, get_next_block_id)
            
            if block_info:
                new_blocks, new_edges, next_block_id = block_info
                blocks.extend(new_blocks)
                edges.extend(new_edges)
                current_block_id = next_block_id
        
        # Exit block
        if current_block_id:
            exit_block_id = get_next_block_id()
            blocks.append({
                'id': exit_block_id,
                'type': 'exit',
                'start_line': func_node.end_lineno or func_node.lineno,
                'end_line': func_node.end_lineno or func_node.lineno,
                'statements': []
            })
            edges.append({
                'source': current_block_id,
                'target': exit_block_id,
                'type': 'normal'
            })
        
        return {
            'function_name': func_node.name,
            'file': file_path,
            'blocks': blocks,
            'edges': edges
        }
    
    def _process_statement(self, stmt: ast.stmt, current_block_id: int, 
                          get_next_block_id) -> Optional[tuple]:
        """Process a statement and update CFG.
        
        Args:
            stmt: Statement AST node
            current_block_id: Current block ID
            get_next_block_id: Function to get next block ID
            
        Returns:
            Tuple of (new_blocks, new_edges, next_block_id) or None
        """
        blocks = []
        edges = []
        
        if isinstance(stmt, ast.If):
            # Create condition block
            condition_block_id = get_next_block_id()
            blocks.append({
                'id': condition_block_id,
                'type': 'condition',
                'start_line': stmt.lineno,
                'end_line': stmt.lineno,
                'condition': ast.unparse(stmt.test) if hasattr(ast, 'unparse') else 'condition',
                'statements': [{'type': 'if', 'line': stmt.lineno}]
            })
            
            # Connect current to condition
            edges.append({
                'source': current_block_id,
                'target': condition_block_id,
                'type': 'normal'
            })
            
            # Then branch
            then_block_id = get_next_block_id()
            blocks.append({
                'id': then_block_id,
                'type': 'basic',
                'start_line': stmt.body[0].lineno if stmt.body else stmt.lineno,
                'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
                'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.body]
            })
            edges.append({
                'source': condition_block_id,
                'target': then_block_id,
                'type': 'true'
            })
            
            # Else branch (if exists)
            if stmt.orelse:
                else_block_id = get_next_block_id()
                blocks.append({
                    'id': else_block_id,
                    'type': 'basic',
                    'start_line': stmt.orelse[0].lineno if stmt.orelse else stmt.lineno,
                    'end_line': stmt.orelse[-1].end_lineno if stmt.orelse and hasattr(stmt.orelse[-1], 'end_lineno') else stmt.lineno,
                    'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.orelse]
                })
                edges.append({
                    'source': condition_block_id,
                    'target': else_block_id,
                    'type': 'false'
                })
                
                # Merge point
                merge_block_id = get_next_block_id()
                blocks.append({
                    'id': merge_block_id,
                    'type': 'merge',
                    'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                    'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                    'statements': []
                })
                edges.append({'source': then_block_id, 'target': merge_block_id, 'type': 'normal'})
                edges.append({'source': else_block_id, 'target': merge_block_id, 'type': 'normal'})
                
                return blocks, edges, merge_block_id
            else:
                # No else branch - false goes to next block
                next_block_id = get_next_block_id()
                blocks.append({
                    'id': next_block_id,
                    'type': 'merge',
                    'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                    'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                    'statements': []
                })
                edges.append({'source': condition_block_id, 'target': next_block_id, 'type': 'false'})
                edges.append({'source': then_block_id, 'target': next_block_id, 'type': 'normal'})
                
                return blocks, edges, next_block_id
                
        elif isinstance(stmt, (ast.While, ast.For)):
            # Loop condition block
            loop_block_id = get_next_block_id()
            blocks.append({
                'id': loop_block_id,
                'type': 'loop_condition',
                'start_line': stmt.lineno,
                'end_line': stmt.lineno,
                'condition': ast.unparse(stmt.test if isinstance(stmt, ast.While) else stmt.iter) if hasattr(ast, 'unparse') else 'loop',
                'statements': [{'type': 'while' if isinstance(stmt, ast.While) else 'for', 'line': stmt.lineno}]
            })
            edges.append({'source': current_block_id, 'target': loop_block_id, 'type': 'normal'})
            
            # Loop body
            body_block_id = get_next_block_id()
            blocks.append({
                'id': body_block_id,
                'type': 'loop_body',
                'start_line': stmt.body[0].lineno if stmt.body else stmt.lineno,
                'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
                'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.body]
            })
            edges.append({'source': loop_block_id, 'target': body_block_id, 'type': 'true'})
            edges.append({'source': body_block_id, 'target': loop_block_id, 'type': 'back_edge'})
            
            # Exit from loop
            exit_block_id = get_next_block_id()
            blocks.append({
                'id': exit_block_id,
                'type': 'merge',
                'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'statements': []
            })
            edges.append({'source': loop_block_id, 'target': exit_block_id, 'type': 'false'})
            
            return blocks, edges, exit_block_id
            
        elif isinstance(stmt, ast.Return):
            # Return statement - no successors
            return_block_id = get_next_block_id()
            blocks.append({
                'id': return_block_id,
                'type': 'return',
                'start_line': stmt.lineno,
                'end_line': stmt.lineno,
                'statements': [{'type': 'return', 'line': stmt.lineno}]
            })
            edges.append({'source': current_block_id, 'target': return_block_id, 'type': 'normal'})
            
            return blocks, edges, None  # No successor after return
            
        elif isinstance(stmt, ast.Try):
            # Try-except block
            try_block_id = get_next_block_id()
            blocks.append({
                'id': try_block_id,
                'type': 'try',
                'start_line': stmt.lineno,
                'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
                'statements': [{'type': 'try', 'line': stmt.lineno}]
            })
            edges.append({'source': current_block_id, 'target': try_block_id, 'type': 'normal'})
            
            # Exception handlers
            handler_ids = []
            for handler in stmt.handlers:
                handler_block_id = get_next_block_id()
                blocks.append({
                    'id': handler_block_id,
                    'type': 'except',
                    'start_line': handler.lineno,
                    'end_line': handler.body[-1].end_lineno if handler.body and hasattr(handler.body[-1], 'end_lineno') else handler.lineno,
                    'statements': [{'type': 'except', 'line': handler.lineno}]
                })
                edges.append({'source': try_block_id, 'target': handler_block_id, 'type': 'exception'})
                handler_ids.append(handler_block_id)
            
            # Finally block (if exists)
            if stmt.finalbody:
                finally_block_id = get_next_block_id()
                blocks.append({
                    'id': finally_block_id,
                    'type': 'finally',
                    'start_line': stmt.finalbody[0].lineno,
                    'end_line': stmt.finalbody[-1].end_lineno if hasattr(stmt.finalbody[-1], 'end_lineno') else stmt.finalbody[0].lineno,
                    'statements': [{'type': 'finally', 'line': stmt.finalbody[0].lineno}]
                })
                
                # All paths lead to finally
                edges.append({'source': try_block_id, 'target': finally_block_id, 'type': 'normal'})
                for handler_id in handler_ids:
                    edges.append({'source': handler_id, 'target': finally_block_id, 'type': 'normal'})
                
                return blocks, edges, finally_block_id
            else:
                # Merge after exception handling
                merge_block_id = get_next_block_id()
                blocks.append({
                    'id': merge_block_id,
                    'type': 'merge',
                    'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                    'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                    'statements': []
                })
                edges.append({'source': try_block_id, 'target': merge_block_id, 'type': 'normal'})
                for handler_id in handler_ids:
                    edges.append({'source': handler_id, 'target': merge_block_id, 'type': 'normal'})
                
                return blocks, edges, merge_block_id
        
        # Default: basic statement, no branching
        return None