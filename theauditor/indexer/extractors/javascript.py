"""JavaScript/TypeScript extractor.

This extractor:
1. Delegates core extraction to the AST parser
2. Performs framework-specific analysis (React/Vue) on the extracted data
"""

from typing import Dict, Any, List, Optional
import os

from . import BaseExtractor


class JavaScriptExtractor(BaseExtractor):
    """Extractor for JavaScript and TypeScript files."""

    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue']

    def extract(self, file_info: Dict[str, Any], content: str,
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all JavaScript/TypeScript information.

        Args:
            file_info: File metadata dictionary
            content: File content (for fallback patterns only)
            tree: Parsed AST from js_semantic_parser

        Returns:
            Dictionary containing all extracted data for database
        """
        result = {
            'imports': [],
            'resolved_imports': {},  # CRITICAL: Module resolution for taint tracking
            'routes': [],
            'symbols': [],
            'assignments': [],
            'function_calls': [],
            'returns': [],
            'variable_usage': [],
            'cfg': [],
            # Security patterns
            'sql_queries': [],  # CRITICAL: SQL injection detection
            'jwt_patterns': [],  # CRITICAL: JWT secret detection
            'type_annotations': [],  # TypeScript types
            # React/Vue framework-specific
            'react_components': [],
            'react_hooks': [],
            'vue_components': [],
            'vue_hooks': [],
            'vue_directives': [],
            'vue_provide_inject': [],
            # Other extractions
            'orm_queries': [],
            'api_endpoints': []
        }

        # No AST = no extraction
        if not tree or not self.ast_parser:
            return result

        # === CORE EXTRACTION via AST parser ===

        # Extract imports
        imports = self.ast_parser.extract_imports(tree)
        if imports:
            # Convert to expected format for database
            for imp in imports:
                if imp.get('target'):
                    result['imports'].append(('import', imp['target']))

        # Extract symbols (functions, classes, calls)
        functions = self.ast_parser.extract_functions(tree)
        for func in functions:
            result['symbols'].append({
                'name': func.get('name', ''),
                'type': 'function',
                'line': func.get('line', 0),
                'col': func.get('col', 0)
            })

        classes = self.ast_parser.extract_classes(tree)
        for cls in classes:
            result['symbols'].append({
                'name': cls.get('name', ''),
                'type': 'class',
                'line': cls.get('line', 0),
                'col': cls.get('column', 0)
            })

        calls = self.ast_parser.extract_calls(tree)
        for call in calls:
            result['symbols'].append({
                'name': call.get('name', ''),
                'type': call.get('type', 'call'),
                'line': call.get('line', 0),
                'col': call.get('column', 0)
            })

        # Extract assignments for data flow analysis
        assignments = self.ast_parser.extract_assignments(tree)
        if assignments:
            result['assignments'] = assignments
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] JS extractor: Found {len(assignments)} assignments")

        # Extract function calls with arguments for taint analysis
        function_calls = self.ast_parser.extract_function_calls_with_args(tree)
        if function_calls:
            result['function_calls'] = function_calls
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] JS extractor: Found {len(function_calls)} function calls with args")

        # Extract return statements
        returns = self.ast_parser.extract_returns(tree)
        if returns:
            result['returns'] = returns
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] JS extractor: Found {len(returns)} returns")

        # Extract control flow graphs
        cfg = self.ast_parser.extract_cfg(tree)
        if cfg:
            result['cfg'] = cfg

        # Extract routes using BaseExtractor's method (regex-based for now)
        routes = self.extract_routes(content)
        if routes:
            result['routes'] = routes

        # === FRAMEWORK-SPECIFIC ANALYSIS ===
        # Analyze the extracted data to identify React/Vue patterns

        # Detect React components from functions that:
        # 1. Have uppercase names (convention)
        # 2. Return JSX
        # 3. Use hooks
        component_functions = []
        for func in functions:
            name = func.get('name', '')
            if name and name[0:1].isupper():
                # Check if this function returns JSX
                func_returns = [r for r in result.get('returns', [])
                              if r.get('function_name') == name]
                has_jsx = any(r.get('has_jsx') or r.get('returns_component') for r in func_returns)

                # Check for hook usage
                hook_calls = []
                for call in calls:
                    call_name = call.get('name', '')
                    if call_name.startswith('use') and call.get('line', 0) >= func.get('line', 0):
                        # This is a potential hook in this component
                        # More precise would be to check if line is within function bounds
                        hook_calls.append(call_name)

                result['react_components'].append({
                    'name': name,
                    'type': 'function',
                    'start_line': func.get('line', 0),
                    'end_line': func.get('end_line', func.get('line', 0)),
                    'has_jsx': has_jsx,
                    'hooks_used': list(set(hook_calls[:10])),  # Limit to 10 unique hooks
                    'props_type': None
                })
                component_functions.append(name)

        # Detect React class components
        for cls in classes:
            name = cls.get('name', '')
            # Check if it extends React.Component or Component
            # This is simplified - would need to check inheritance properly
            if name and name[0:1].isupper():
                result['react_components'].append({
                    'name': name,
                    'type': 'class',
                    'start_line': cls.get('line', 0),
                    'end_line': cls.get('line', 0),
                    'has_jsx': True,  # Assume class components have JSX
                    'hooks_used': [],  # Class components don't use hooks
                    'props_type': None
                })
                component_functions.append(name)

        # Extract React hooks usage with DETAILED analysis
        for fc in result.get('function_calls', []):
            call_name = fc.get('callee_function', '')
            if call_name.startswith('use'):
                line = fc.get('line', 0)
                component_name = fc.get('caller_function', 'global')

                # Find the actual component if caller is nested function
                for comp in result['react_components']:
                    if comp['start_line'] <= line <= comp.get('end_line', comp['start_line'] + 100):
                        component_name = comp['name']
                        break

                # Analyze hook type and extract details
                hook_type = 'custom'
                dependency_array = None
                dependency_vars = []
                callback_body = None
                has_cleanup = False
                cleanup_type = None

                if call_name in ['useState', 'useEffect', 'useCallback', 'useMemo',
                                'useRef', 'useContext', 'useReducer', 'useLayoutEffect']:
                    hook_type = 'builtin'

                    # For hooks with dependencies, check second argument
                    if call_name in ['useEffect', 'useCallback', 'useMemo', 'useLayoutEffect']:
                        # Look for the same call in function_calls to get arguments
                        matching_calls = [c for c in result.get('function_calls', [])
                                        if c.get('line') == line and
                                        c.get('callee_function') == call_name]

                        if matching_calls:
                            # Get dependency array from second argument (index 1)
                            deps_arg = [c for c in matching_calls if c.get('argument_index') == 1]
                            if deps_arg:
                                dep_expr = deps_arg[0].get('argument_expr', '')
                                if dep_expr.startswith('[') and dep_expr.endswith(']'):
                                    dependency_array = dep_expr
                                    # Extract variables from dependency array
                                    dep_content = dep_expr[1:-1].strip()
                                    if dep_content:
                                        dependency_vars = [v.strip() for v in dep_content.split(',')]

                            # Get callback body from first argument (index 0)
                            callback_arg = [c for c in matching_calls if c.get('argument_index') == 0]
                            if callback_arg:
                                callback_body = callback_arg[0].get('argument_expr', '')[:500]

                                # Check for cleanup in useEffect
                                if call_name in ['useEffect', 'useLayoutEffect']:
                                    if 'return' in callback_body:
                                        has_cleanup = True
                                        if 'clearTimeout' in callback_body or 'clearInterval' in callback_body:
                                            cleanup_type = 'timer_cleanup'
                                        elif 'removeEventListener' in callback_body:
                                            cleanup_type = 'event_cleanup'
                                        elif 'unsubscribe' in callback_body or 'disconnect' in callback_body:
                                            cleanup_type = 'subscription_cleanup'
                                        else:
                                            cleanup_type = 'cleanup_function'

                result['react_hooks'].append({
                    'line': line,
                    'component_name': component_name,
                    'hook_name': call_name,
                    'hook_type': hook_type,
                    'dependency_array': dependency_array,
                    'dependency_vars': dependency_vars,
                    'callback_body': callback_body,
                    'has_cleanup': has_cleanup,
                    'cleanup_type': cleanup_type
                })

        # Detect Vue components and patterns
        for call in calls:
            call_name = call.get('name', '')

            # Vue 3 Composition API
            if call_name == 'defineComponent':
                result['vue_components'].append({
                    'name': file_info.get('path', '').split('/')[-1].split('.')[0],
                    'type': 'composition-api',
                    'start_line': call.get('line', 0),
                    'end_line': call.get('line', 0),
                    'has_template': file_info.get('ext') == '.vue',
                    'has_style': file_info.get('ext') == '.vue',
                    'composition_api_used': True,
                    'props_definition': None,
                    'emits_definition': None,
                    'setup_return': None
                })

            # Vue reactivity hooks
            elif call_name in ['ref', 'reactive', 'computed', 'watch', 'watchEffect']:
                result['vue_hooks'].append({
                    'line': call.get('line', 0),
                    'component_name': 'global',  # Would need component detection
                    'hook_name': call_name,
                    'hook_type': 'reactivity',
                    'dependencies': None,
                    'return_value': None,
                    'is_async': False
                })

            # Vue provide/inject
            elif call_name in ['provide', 'inject']:
                result['vue_provide_inject'].append({
                    'line': call.get('line', 0),
                    'component_name': 'global',
                    'operation_type': call_name,
                    'key_name': 'unknown',
                    'value_expr': None,
                    'is_reactive': False
                })

            # Vue directives (would need template parsing for full support)
            elif call_name.startswith('v-') or call_name in ['directive']:
                result['vue_directives'].append({
                    'line': call.get('line', 0),
                    'directive_name': call_name,
                    'element_type': None,
                    'argument': None,
                    'modifiers': [],
                    'value_expr': None,
                    'is_dynamic': False
                })

        # Detect ORM queries from method calls
        orm_methods = {
            # Sequelize
            'findAll', 'findOne', 'findByPk', 'create', 'update', 'destroy',
            'findOrCreate', 'findAndCountAll', 'bulkCreate', 'upsert',
            # Prisma
            'findMany', 'findUnique', 'findFirst', 'create', 'update', 'delete',
            'createMany', 'updateMany', 'deleteMany', 'upsert',
            # TypeORM
            'find', 'findOne', 'save', 'remove', 'delete', 'insert', 'update',
            'createQueryBuilder', 'getRepository', 'getManager'
        }

        for call in calls:
            method = call.get('name', '').split('.')[-1]
            if method in orm_methods:
                result['orm_queries'].append({
                    'line': call.get('line', 0),
                    'query_type': method,
                    'includes': None,
                    'has_limit': False,
                    'has_transaction': False
                })

        # Detect API endpoints from route definitions
        if routes:
            for method, path, middleware in routes:
                result['api_endpoints'].append({
                    'line': 0,  # Routes are regex-extracted, no line info
                    'http_method': method,
                    'route_path': path,
                    'has_auth': any('auth' in str(m).lower() for m in middleware),
                    'has_validation': any('validat' in str(m).lower() for m in middleware),
                    'middleware_stack': middleware[:5] if middleware else []
                })

        # === CRITICAL SECURITY PATTERN DETECTION ===

        # Extract SQL queries (detect potential SQL injection)
        sql_patterns = self.extract_sql_queries(content)  # Uses BaseExtractor method
        if sql_patterns:
            result['sql_queries'] = sql_patterns

        # Extract JWT patterns (detect hardcoded secrets)
        jwt_patterns = self.extract_jwt_patterns(content)  # Uses BaseExtractor method
        if jwt_patterns:
            result['jwt_patterns'] = jwt_patterns

        # Extract TypeScript type annotations from symbols
        for symbol in result['symbols']:
            if symbol.get('type') == 'function':
                # Check in original functions data for type info
                for func in functions:
                    if func.get('name') == symbol.get('name'):
                        if 'type' in func or 'returnType' in func:
                            result['type_annotations'].append({
                                'line': symbol.get('line', 0),
                                'symbol_name': symbol.get('name'),
                                'annotation_type': 'return',
                                'type_text': func.get('returnType', func.get('type', 'any'))
                            })

        # Build variable usage from assignments and symbols
        # This is CRITICAL for dead code detection and taint analysis
        for assign in result.get('assignments', []):
            result['variable_usage'].append({
                'line': assign.get('line', 0),
                'variable_name': assign.get('target_var', ''),
                'usage_type': 'write',
                'in_component': assign.get('in_function', 'global'),
                'in_hook': '',
                'scope_level': 0 if assign.get('in_function') == 'global' else 1
            })
            # Also track reads from source variables
            for var in assign.get('source_vars', []):
                result['variable_usage'].append({
                    'line': assign.get('line', 0),
                    'variable_name': var,
                    'usage_type': 'read',
                    'in_component': assign.get('in_function', 'global'),
                    'in_hook': '',
                    'scope_level': 0 if assign.get('in_function') == 'global' else 1
                })

        # Track function calls as variable usage (function names are "read")
        for call in result.get('function_calls', []):
            if call.get('callee_function'):
                result['variable_usage'].append({
                    'line': call.get('line', 0),
                    'variable_name': call.get('callee_function'),
                    'usage_type': 'call',
                    'in_component': call.get('caller_function', 'global'),
                    'in_hook': '',
                    'scope_level': 0 if call.get('caller_function') == 'global' else 1
                })

        # Module resolution for imports (CRITICAL for taint tracking across modules)
        # This maps import names to their actual module paths
        for imp_type, imp_path in result.get('imports', []):
            # Extract module name from path
            if imp_path:
                # For now, simple mapping - would need more complex resolution
                module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')
                result['resolved_imports'][module_name] = imp_path

        return result