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
from typing import Dict, Any, List, Optional, Tuple

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

            # Extract control flow graph data using centralized AST infrastructure
            result['cfg'] = self.ast_parser.extract_cfg(tree) if self.ast_parser else []
        
        # Extract SQL queries embedded in JavaScript code
        result['sql_queries'] = self.extract_sql_queries(content)

        # Extract JWT patterns with metadata
        result['jwt_patterns'] = self.extract_jwt_patterns(content)

        # Extract React-specific data if this is a React file
        if self._is_react_file(file_info, content):
            result['react_components'] = self._extract_react_components(tree, content)
            result['react_hooks'] = self._extract_react_hooks(tree, content)

        # CRITICAL FIX: Extract variable usage for ALL JavaScript files, not just React
        # This is essential for complete taint analysis and dead code detection
        result['variable_usage'] = self._extract_comprehensive_variable_usage(tree, content)

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

    def _is_react_file(self, file_info: Dict[str, Any], content: str) -> bool:
        """Check if this is a React file based on extension and content."""
        # Check file extension
        if file_info['ext'] in ['.jsx', '.tsx']:
            return True

        # Check for React imports or usage
        if 'react' in content.lower() or 'React' in content:
            return True

        # Check for component patterns
        if any(pattern in content for pattern in ['useState', 'useEffect', 'Component', 'render()']):
            return True

        return False

    def _extract_react_components(self, tree: Dict[str, Any], content: str) -> List[Dict]:
        """Extract React component definitions."""
        components = []

        if not tree or not self.ast_parser:
            return components

        try:
            # Get all functions from the tree
            functions = self.ast_parser.extract_functions(tree)

            for func in functions:
                # Check if it's likely a React component
                name = func.get('name', '')
                if not name:
                    continue

                # React components typically start with capital letter
                is_component = name[0].isupper() if name else False

                # Check for hooks usage
                hooks_used = self._get_hooks_used(func, tree, content)
                if hooks_used:
                    is_component = True

                # Check for JSX return (simplified check)
                has_jsx = self._has_jsx_return(func, content)
                if has_jsx:
                    is_component = True

                if is_component:
                    components.append({
                        'name': name,
                        'type': func.get('type', 'function'),
                        'start_line': func.get('line', 0),
                        'end_line': func.get('end_line', func.get('line', 0) + 10),
                        'has_jsx': has_jsx,
                        'hooks_used': hooks_used,
                        'props_type': None  # TODO: Extract TypeScript/PropTypes
                    })
        except Exception:
            # Silently fail component extraction
            pass

        return components

    def _extract_react_hooks(self, tree: Dict[str, Any], content: str) -> List[Dict]:
        """Extract React hooks with full metadata."""
        hooks = []

        if not tree or not self.ast_parser:
            return hooks

        try:
            # Get all function calls
            calls = self.ast_parser.extract_function_calls_with_args(tree)

            for call in calls:
                callee = call.get('callee_function', '')

                # Check if it's a React hook (starts with 'use')
                if callee.startswith('use'):
                    hook_data = {
                        'line': call.get('line', 0),
                        'component_name': call.get('caller_function', 'global'),
                        'hook_name': callee,
                        'dependency_array': None,
                        'dependency_vars': [],
                        'callback_body': None,
                        'has_cleanup': False,
                        'cleanup_type': None
                    }

                    # Special handling for hooks with dependency arrays
                    if callee in ['useEffect', 'useCallback', 'useMemo']:
                        arg_expr = call.get('argument_expr', '')

                        # Parse dependency array
                        deps = self._parse_dependency_array(arg_expr)
                        hook_data['dependency_array'] = deps

                        # Extract variables referenced in callback
                        hook_data['dependency_vars'] = self._extract_callback_vars(arg_expr)

                        # Store first 500 chars of callback
                        if arg_expr:
                            hook_data['callback_body'] = arg_expr[:500]

                        # Check for cleanup in useEffect
                        if callee == 'useEffect':
                            has_cleanup, cleanup_type = self._check_cleanup(arg_expr)
                            hook_data['has_cleanup'] = has_cleanup
                            hook_data['cleanup_type'] = cleanup_type

                    hooks.append(hook_data)
        except Exception:
            # Silently fail hook extraction
            pass

        return hooks

    def _extract_variable_usage(self, tree: Dict[str, Any], content: str) -> List[Dict]:
        """Track variable usage for dependency analysis."""
        usage = []

        if not tree or not self.ast_parser:
            return usage

        try:
            # Extract all symbols
            symbols = self.ast_parser.extract_calls(tree)

            # Also extract property accesses
            if hasattr(self.ast_parser, 'extract_properties'):
                properties = self.ast_parser.extract_properties(tree)
                symbols.extend(properties)

            # Track variable usage
            for symbol in symbols:
                # Focus on common React variables
                name = symbol.get('name', '')
                if any(var in name for var in ['props', 'state', 'setState', 'dispatch', 'ref']):
                    usage.append({
                        'line': symbol.get('line', 0),
                        'variable_name': name,
                        'usage_type': 'read',  # Simplified for now
                        'in_component': '',  # TODO: Track component context
                        'in_hook': '',  # TODO: Track hook context
                        'scope_level': 1  # Default to component level
                    })
        except Exception:
            # Silently fail variable tracking
            pass

        return usage

    def _extract_comprehensive_variable_usage(self, tree: Dict[str, Any], content: str) -> List[Dict]:
        """Extract ALL variable usage for complete data flow analysis.

        This is critical for taint analysis, dead code detection, and
        understanding the complete data flow in JavaScript/TypeScript code.

        Args:
            tree: Parsed AST tree
            content: File content

        Returns:
            List of all variable usage records with read/write operations
        """
        usage = []

        if not tree or not self.ast_parser:
            return usage

        try:
            # Import scope builder for accurate function context
            from theauditor.ast_extractors.typescript_impl import build_scope_map

            # Build scope map for accurate function context
            # Handle different tree structures
            ast_root = None
            if tree.get("type") == "semantic_ast" and tree.get("tree"):
                ast_root = tree["tree"].get("ast", {})
            elif tree.get("type") == "tree_sitter":
                # Tree-sitter doesn't have nested structure
                ast_root = tree.get("tree", {})
            else:
                ast_root = tree.get("ast", {})

            scope_map = {}
            if ast_root:
                scope_map = build_scope_map(ast_root)

            # 1. Extract all WRITE operations from assignments
            assignments = self.ast_parser.extract_assignments(tree)
            for assign in assignments:
                line = assign.get('line', 0)
                if line > 0:  # Valid line number
                    usage.append({
                        'line': line,
                        'variable_name': assign.get('target_var', ''),
                        'usage_type': 'write',
                        'in_component': scope_map.get(line, assign.get('in_function', 'global')),
                        'in_hook': '',  # Could be enhanced to detect if in hook
                        'scope_level': 0 if scope_map.get(line, 'global') == 'global' else 1
                    })

            # 2. Extract all READ operations from symbols and properties
            symbols = self.ast_parser.extract_calls(tree) or []
            properties = []
            if hasattr(self.ast_parser, 'extract_properties'):
                properties = self.ast_parser.extract_properties(tree) or []

            # Combine all symbol references
            all_refs = symbols + properties

            for ref in all_refs:
                name = ref.get('name', '')
                line = ref.get('line', 0)
                ref_type = ref.get('type', '')

                # Skip empty names or invalid lines
                if not name or line < 1:
                    continue

                # Skip pure function calls (they're not variable usage)
                # But keep property accesses like req.body (they ARE variable usage)
                if ref_type == 'call' and '.' not in name:
                    continue

                # This is a variable reference (read operation)
                usage.append({
                    'line': line,
                    'variable_name': name,
                    'usage_type': 'read',
                    'in_component': scope_map.get(line, 'global'),
                    'in_hook': '',
                    'scope_level': 0 if scope_map.get(line, 'global') == 'global' else 1
                })

            # 3. Extract variable usage from function parameters
            # These are implicit reads when the function is called
            function_params = self.ast_parser._extract_function_parameters(tree) if hasattr(self.ast_parser, '_extract_function_parameters') else {}
            for func_name, params in function_params.items():
                # Find the function's line number
                functions = self.ast_parser.extract_functions(tree) or []
                for func in functions:
                    if func.get('name') == func_name:
                        func_line = func.get('line', 0)
                        # Add each parameter as a variable usage
                        for param in params:
                            if param and func_line > 0:
                                usage.append({
                                    'line': func_line,
                                    'variable_name': param,
                                    'usage_type': 'param',  # Special type for parameters
                                    'in_component': func_name,
                                    'in_hook': '',
                                    'scope_level': 1  # Function scope
                                })
                        break

            # 4. Deduplicate while preserving order
            # Use a set to track seen (line, var, type) combinations
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
                print(f"[DEBUG] Error in comprehensive variable extraction: {e}", file=sys.stderr)
            return usage

    def _parse_dependency_array(self, expr: str) -> Optional[List[str]]:
        """Parse dependency array from hook arguments."""
        import re

        if not expr:
            return None

        # Look for the last array in the expression (the deps)
        # Pattern: ..., [deps]) or ..., [])
        match = re.search(r',\s*\[([^\]]*)\]\s*\)?\s*$', expr)
        if match:
            deps_str = match.group(1).strip()
            if not deps_str:  # Empty array
                return []

            # Split on commas, handling nested structures
            deps = []
            current = ''
            depth = 0

            for char in deps_str:
                if char in '({[':
                    depth += 1
                elif char in ')}]':
                    depth -= 1
                elif char == ',' and depth == 0:
                    if current.strip():
                        deps.append(current.strip())
                    current = ''
                    continue
                current += char

            if current.strip():
                deps.append(current.strip())

            return deps

        return None

    def _extract_callback_vars(self, expr: str) -> List[str]:
        """Extract variables referenced in a callback function."""
        vars_found = []

        if not expr:
            return vars_found

        # Look for common React patterns
        import re

        # Find state/props references
        for match in re.finditer(r'\b(props|state|setState|dispatch)\b\.?\w*', expr):
            vars_found.append(match.group(0))

        # Find variable names (simplified)
        for match in re.finditer(r'\b([a-zA-Z_]\w*)\b', expr):
            var = match.group(1)
            # Filter out keywords and common functions
            if var not in ['function', 'return', 'if', 'else', 'for', 'while', 'const', 'let', 'var',
                          'true', 'false', 'null', 'undefined', 'async', 'await', 'new', 'this']:
                if var not in vars_found:
                    vars_found.append(var)

        return vars_found[:20]  # Limit to 20 variables

    def _check_cleanup(self, expr: str) -> Tuple[bool, Optional[str]]:
        """Check if useEffect has cleanup and what type."""
        if not expr:
            return False, None

        # Check for return statement
        if 'return' in expr:
            # Check for common cleanup patterns
            if 'clearInterval' in expr or 'clearTimeout' in expr:
                return True, 'timer_cleanup'
            if 'removeEventListener' in expr:
                return True, 'event_cleanup'
            if 'unsubscribe' in expr:
                return True, 'subscription_cleanup'
            if 'abort' in expr or 'AbortController' in expr:
                return True, 'abort_controller'
            if 'return ()' in expr or 'return function' in expr:
                return True, 'cleanup_function'

        return False, None

    def _has_jsx_return(self, func: Dict, content: str) -> bool:
        """Check if function returns JSX."""
        # Simplified check - look for JSX patterns near the function
        func_line = func.get('line', 0)
        if func_line > 0 and func_line <= len(content.split('\n')):
            # Get function context (next 20 lines)
            lines = content.split('\n')
            func_context = '\n'.join(lines[func_line-1:func_line+19])

            # Look for JSX patterns
            if any(pattern in func_context for pattern in ['<div', '<span', '<button', '<Component', '<Fragment', 'return (']):
                return True

        return False

    def _get_hooks_used(self, func: Dict, tree: Dict, content: str) -> List[str]:
        """Get list of hooks used in a function."""
        hooks = []

        # Get function context
        func_line = func.get('line', 0)
        end_line = func.get('end_line', func_line + 20)

        if func_line > 0 and func_line <= len(content.split('\n')):
            lines = content.split('\n')
            func_context = '\n'.join(lines[func_line-1:end_line])

            # Find hook calls
            import re
            for match in re.finditer(r'\buse[A-Z]\w*\b', func_context):
                hook = match.group(0)
                if hook not in hooks:
                    hooks.append(hook)

        return hooks