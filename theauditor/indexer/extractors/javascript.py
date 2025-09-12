"""JavaScript/TypeScript file extractor.

Handles extraction of JavaScript and TypeScript specific elements including:
- ES6/CommonJS imports and requires
- Express/Fastify routes with middleware
- ORM queries (Sequelize, Prisma, TypeORM)
- Property accesses for taint analysis
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor
from ..config import (
    SEQUELIZE_METHODS, PRISMA_METHODS, 
    TYPEORM_REPOSITORY_METHODS, TYPEORM_QB_METHODS
)


class JavaScriptExtractor(BaseExtractor):
    """Extractor for JavaScript and TypeScript files."""
    
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a JavaScript/TypeScript file.
        
        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree
            
        Returns:
            Dictionary containing all extracted data
        """
        result = {
            'imports': [],
            'resolved_imports': {},
            'routes': [],
            'symbols': [],
            'assignments': [],
            'function_calls': [],
            'returns': [],
            'orm_queries': [],
            'cfg': []  # Control flow graph data
        }
        
        # Extract imports using regex patterns
        result['imports'] = self.extract_imports(content, file_info['ext'])
        
        # Resolve imports if we have js_semantic_parser
        if tree and tree.get('success'):
            try:
                from theauditor.js_semantic_parser import JSSemanticParser
                js_parser = JSSemanticParser(project_root=str(self.root_path))
                result['resolved_imports'] = js_parser.resolve_imports(
                    tree, file_info['path']
                )
            except Exception:
                # Resolution failed, keep unresolved imports
                pass
        
        # Extract routes
        if tree:
            result['routes'] = self._extract_routes_ast(tree, content)
        else:
            result['routes'] = [(method, path, []) 
                               for method, path in self.extract_routes(content)]
        
        # Extract symbols from AST if available
        if tree and self.ast_parser:
            # Functions
            functions = self.ast_parser.extract_functions(tree)
            for func in functions:
                line = func.get('line', 0)
                # Validate line numbers are reasonable
                if line < 1 or line > 100000:
                    continue  # Skip invalid symbols
                
                result['symbols'].append({
                    'name': func.get('name', ''),
                    'type': 'function',
                    'line': line,
                    'col': func.get('col', 0)
                })
            
            # Classes
            classes = self.ast_parser.extract_classes(tree)
            for cls in classes:
                line = cls.get('line', 0)
                # Validate line numbers are reasonable
                if line < 1 or line > 100000:
                    continue  # Skip invalid symbols
                
                result['symbols'].append({
                    'name': cls.get('name', ''),
                    'type': 'class',
                    'line': line,
                    'col': cls.get('col', 0)
                })
            
            # Calls and other symbols
            symbols = self.ast_parser.extract_calls(tree)
            for symbol in symbols:
                line = symbol.get('line', 0)
                # Validate line numbers are reasonable
                if line < 1 or line > 100000:
                    continue  # Skip invalid symbols
                
                result['symbols'].append({
                    'name': symbol.get('name', ''),
                    'type': symbol.get('type', 'call'),
                    'line': line,
                    'col': symbol.get('col', symbol.get('column', 0))
                })
            
            # CRITICAL: Extract property accesses for taint analysis
            # This is needed to find patterns like req.body, req.query, etc.
            properties = self.ast_parser.extract_properties(tree)
            for prop in properties:
                line = prop.get('line', 0)
                # Validate line numbers are reasonable
                if line < 1 or line > 100000:
                    continue  # Skip invalid symbols
                
                result['symbols'].append({
                    'name': prop.get('name', ''),
                    'type': 'property',
                    'line': line,
                    'col': prop.get('col', prop.get('column', 0))
                })
            
            # Extract data flow information
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
            
            # Extract ORM queries
            result['orm_queries'] = self._extract_orm_queries(tree, content)
            
            # Extract control flow graph data
            result['cfg'] = self._extract_control_flow(tree, file_info['path'])
        
        # Extract SQL queries embedded in JavaScript code
        result['sql_queries'] = self.extract_sql_queries(content)
        
        return result
    
    def _extract_routes_ast(self, tree: Dict[str, Any], content: str) -> List[tuple]:
        """Extract Express/Fastify routes with middleware.
        
        Args:
            tree: Parsed AST tree
            content: File content for fallback extraction
            
        Returns:
            List of (method, pattern, controls) tuples
        """
        routes = []
        
        # Enhanced regex to capture middleware
        # Pattern: router.METHOD('/path', [middleware1, middleware2,] handler)
        pattern = re.compile(
            r'(?:app|router)\.(get|post|put|patch|delete|all)\s*\(\s*[\'\"\`]([^\'\"\`]+)[\'\"\`]\s*,\s*([^)]+)\)',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(content):
            method = match.group(1).upper()
            path = match.group(2)
            middleware_str = match.group(3)
            
            # Extract middleware function names
            middleware = []
            # Look for function names before the final handler
            middleware_pattern = re.compile(r'(\w+)(?:\s*,|\s*\))')
            for m in middleware_pattern.finditer(middleware_str):
                name = m.group(1)
                # Filter out common non-middleware terms
                if name not in ['req', 'res', 'next', 'async', 'function', 'err']:
                    middleware.append(name)
            
            # Remove the last item as it's likely the handler, not middleware
            if len(middleware) > 1:
                middleware = middleware[:-1]
            
            routes.append((method, path, middleware))
        
        # If no routes found with enhanced regex, fallback to basic extraction
        if not routes:
            routes = [(method, path, []) 
                     for method, path in self.extract_routes(content)]
        
        return routes
    
    def _extract_orm_queries(self, tree: Dict[str, Any], content: str) -> List[Dict]:
        """Extract ORM query calls from JavaScript/TypeScript code.
        
        Args:
            tree: AST tree from ast_parser
            content: File content for line extraction
            
        Returns:
            List of ORM query dictionaries
        """
        queries = []
        
        if not tree or not self.ast_parser:
            return queries
        
        # Handle wrapped tree format
        if not isinstance(tree, dict) or tree.get("type") != "tree_sitter":
            return queries
        
        try:
            # Extract all function calls from the tree
            calls = self.ast_parser.extract_calls(tree)
            lines = content.split('\n')
            
            # All ORM methods to check
            all_orm_methods = (
                SEQUELIZE_METHODS | PRISMA_METHODS | 
                TYPEORM_REPOSITORY_METHODS | TYPEORM_QB_METHODS
            )
            
            # Process each call
            for call in calls:
                method_name = call.get('name', '')
                
                # Check for ORM method patterns
                if '.' in method_name:
                    parts = method_name.split('.')
                    method = parts[-1]
                    
                    if method in all_orm_methods:
                        line_num = call.get('line', 0)
                        
                        # Determine ORM type and extract context
                        orm_type = self._determine_orm_type(method, parts)
                        
                        # Try to extract options from context
                        has_include = False
                        has_limit = False
                        has_transaction = False
                        includes_json = None
                        
                        if 0 < line_num <= len(lines):
                            # Get context for multi-line calls
                            start_line = max(0, line_num - 1)
                            end_line = min(len(lines), line_num + 10)
                            context = '\n'.join(lines[start_line:end_line])
                            
                            # Check for includes/relations (eager loading)
                            if 'include:' in context or 'include :' in context or 'relations:' in context:
                                has_include = True
                                # Check for death query pattern in Sequelize
                                if 'all: true' in context and 'nested: true' in context:
                                    includes_json = json.dumps({"all": True, "nested": True})
                                else:
                                    # Try to extract include/relations specification
                                    include_match = re.search(
                                        r'(?:include|relations):\s*(\[.*?\]|\{.*?\})', 
                                        context, re.DOTALL
                                    )
                                    if include_match:
                                        includes_json = json.dumps({"raw": include_match.group(1)[:200]})
                            
                            # Check for limit/take
                            if 'limit:' in context or 'limit :' in context or 'take:' in context:
                                has_limit = True
                            
                            # Check for transaction
                            if 'transaction:' in context or '.$transaction' in context:
                                has_transaction = True
                        
                        # Format query type with model name for Prisma
                        if orm_type == 'prisma' and len(parts) >= 3:
                            query_type = f'{parts[-2]}.{method}'  # model.method
                        else:
                            query_type = method
                        
                        queries.append({
                            'line': line_num,
                            'query_type': query_type,
                            'includes': includes_json,
                            'has_limit': has_limit,
                            'has_transaction': has_transaction
                        })
        
        except Exception:
            # Silently fail ORM extraction
            pass
        
        return queries
    
    def _determine_orm_type(self, method: str, parts: List[str]) -> str:
        """Determine which ORM is being used based on method and call pattern.
        
        Args:
            method: The method name
            parts: The split call parts (e.g., ['prisma', 'user', 'findMany'])
            
        Returns:
            ORM type string: 'sequelize', 'prisma', 'typeorm', or 'unknown'
        """
        if method in SEQUELIZE_METHODS:
            return 'sequelize'
        elif method in PRISMA_METHODS:
            # Prisma typically uses prisma.modelName.method pattern
            if len(parts) >= 3 and parts[-3] in ['prisma', 'db', 'client']:
                return 'prisma'
        elif method in TYPEORM_REPOSITORY_METHODS:
            return 'typeorm_repository'
        elif method in TYPEORM_QB_METHODS:
            return 'typeorm_qb'
        return 'unknown'
    
    def _extract_control_flow(self, tree: Dict[str, Any], file_path: str) -> List[Dict[str, Any]]:
        """Extract control flow graph from JavaScript/TypeScript AST.
        
        Args:
            tree: Parsed AST tree
            file_path: Path to the file
            
        Returns:
            List of CFG data for each function
        """
        cfg_data = []
        
        # Check if we have a valid tree (handle both tree_sitter and semantic_ast)
        if not tree:
            return cfg_data
        
        # For semantic_ast, success is nested at tree['tree']['success']
        if tree.get('type') == 'semantic_ast':
            if not tree.get('tree', {}).get('success'):
                return cfg_data
        else:
            # For tree_sitter format, check at root
            if not tree.get('success'):
                return cfg_data
        
        # Extract function AST nodes directly for CFG building
        # (Success already validated above, now extract functions)
        from theauditor.ast_extractors.typescript_impl import extract_typescript_function_nodes
        # Get complete function nodes with bodies
        function_nodes = extract_typescript_function_nodes(tree, None)
        for func in function_nodes:
            function_cfg = self._build_function_cfg_js(func, file_path)
            if function_cfg:
                cfg_data.append(function_cfg)
        
        # Extract classes and their methods
        classes = self.ast_parser.extract_classes(tree)
        for cls in classes:
            # Classes don't have methods extracted separately in our parser
            # but we can still create CFG for class methods if needed
            pass
        
        return cfg_data
    
    def _build_function_cfg_js(self, func_node: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Build control flow graph for a single JavaScript/TypeScript function.
        
        Args:
            func_node: Complete AST node for the function
            file_path: Path to the file
            
        Returns:
            CFG data dictionary
        """
        # Extract function name from AST node
        func_name = 'anonymous'
        name_node = func_node.get('name')
        if isinstance(name_node, dict):
            func_name = name_node.get('text', 'anonymous')
        elif isinstance(name_node, str):
            func_name = name_node
        # For arrow functions and anonymous functions, may not have a name
        
        blocks = []
        edges = []
        block_id_counter = [0]
        
        def get_next_block_id():
            block_id_counter[0] += 1
            return block_id_counter[0]
        
        # Entry block
        entry_block_id = get_next_block_id()
        start_line = func_node.get('line', 1)
        # Don't extract 'end' - it's character position not line number
        # Exit blocks are synthetic and don't need real end line
        
        blocks.append({
            'id': entry_block_id,
            'type': 'entry',
            'start_line': start_line,
            'end_line': start_line,
            'statements': []
        })
        
        # Analyze function body for control flow structures
        # This is simplified - a full implementation would parse the body
        current_block_id = entry_block_id
        
        # Extract body from AST node - it's in the children as a Block node
        body = ''
        for child in func_node.get('children', []):
            if isinstance(child, dict) and child.get('kind') == 'Block':
                body = child.get('text', '')
                break
        if body:
            # Detect if statements
            if_count = body.count('if (') + body.count('if(')
            for _ in range(if_count):
                # Create condition block
                condition_id = get_next_block_id()
                blocks.append({
                    'id': condition_id,
                    'type': 'condition',
                    'start_line': start_line,
                    'end_line': start_line,
                    'condition': 'if_condition',
                    'statements': [{'type': 'if', 'line': start_line}]
                })
                edges.append({'source': current_block_id, 'target': condition_id, 'type': 'normal'})
                
                # Then and else branches
                then_id = get_next_block_id()
                blocks.append({
                    'id': then_id,
                    'type': 'basic',
                    'start_line': start_line,
                    'end_line': start_line,
                    'statements': []
                })
                edges.append({'source': condition_id, 'target': then_id, 'type': 'true'})
                
                # Merge block
                merge_id = get_next_block_id()
                blocks.append({
                    'id': merge_id,
                    'type': 'merge',
                    'start_line': start_line,
                    'end_line': start_line,
                    'statements': []
                })
                edges.append({'source': condition_id, 'target': merge_id, 'type': 'false'})
                edges.append({'source': then_id, 'target': merge_id, 'type': 'normal'})
                
                current_block_id = merge_id
            
            # Detect loops
            loop_count = body.count('for (') + body.count('for(') + body.count('while (') + body.count('while(')
            for _ in range(loop_count):
                # Loop condition block
                loop_id = get_next_block_id()
                blocks.append({
                    'id': loop_id,
                    'type': 'loop_condition',
                    'start_line': start_line,
                    'end_line': start_line,
                    'condition': 'loop_condition',
                    'statements': [{'type': 'loop', 'line': start_line}]
                })
                edges.append({'source': current_block_id, 'target': loop_id, 'type': 'normal'})
                
                # Loop body
                body_id = get_next_block_id()
                blocks.append({
                    'id': body_id,
                    'type': 'loop_body',
                    'start_line': start_line,
                    'end_line': start_line,
                    'statements': []
                })
                edges.append({'source': loop_id, 'target': body_id, 'type': 'true'})
                edges.append({'source': body_id, 'target': loop_id, 'type': 'back_edge'})
                
                # Exit block
                exit_id = get_next_block_id()
                blocks.append({
                    'id': exit_id,
                    'type': 'merge',
                    'start_line': start_line,
                    'end_line': start_line,
                    'statements': []
                })
                edges.append({'source': loop_id, 'target': exit_id, 'type': 'false'})
                
                current_block_id = exit_id
            
            # Detect try-catch blocks
            try_count = body.count('try {') + body.count('try{')
            for _ in range(try_count):
                # Try block
                try_id = get_next_block_id()
                blocks.append({
                    'id': try_id,
                    'type': 'try',
                    'start_line': start_line,
                    'end_line': start_line,
                    'statements': [{'type': 'try', 'line': start_line}]
                })
                edges.append({'source': current_block_id, 'target': try_id, 'type': 'normal'})
                
                # Catch block
                catch_id = get_next_block_id()
                blocks.append({
                    'id': catch_id,
                    'type': 'except',
                    'start_line': start_line,
                    'end_line': start_line,
                    'statements': [{'type': 'catch', 'line': start_line}]
                })
                edges.append({'source': try_id, 'target': catch_id, 'type': 'exception'})
                
                # Merge after try-catch
                merge_id = get_next_block_id()
                blocks.append({
                    'id': merge_id,
                    'type': 'merge',
                    'start_line': start_line,
                    'end_line': start_line,
                    'statements': []
                })
                edges.append({'source': try_id, 'target': merge_id, 'type': 'normal'})
                edges.append({'source': catch_id, 'target': merge_id, 'type': 'normal'})
                
                current_block_id = merge_id
        
        # Exit block
        if current_block_id:
            exit_block_id = get_next_block_id()
            blocks.append({
                'id': exit_block_id,
                'type': 'exit',
                'start_line': start_line,  # Exit block is synthetic - use function start
                'end_line': start_line,    # Doesn't correspond to real code lines
                'statements': []
            })
            edges.append({'source': current_block_id, 'target': exit_block_id, 'type': 'normal'})
        
        return {
            'function_name': func_name,
            'file': file_path,
            'blocks': blocks,
            'edges': edges
        }