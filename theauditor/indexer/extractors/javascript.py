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

        # Extract imports - check both direct tree and nested tree structure
        # TypeScript semantic parser returns imports directly in the tree
        actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
        imports_data = actual_tree.get("imports", [])

        if imports_data:
            # Convert to expected format for database
            for imp in imports_data:
                module = imp.get('module')
                if module:
                    # Use the kind (import/require) as the type
                    kind = imp.get('kind', 'import')
                    result['imports'].append((kind, module))

            # NEW: Extract import styles for bundle analysis
            result['import_styles'] = self._analyze_import_styles(imports_data, file_info['path'])

        # Extract symbols (functions, classes, calls, properties)
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

        # ============================================================================
        # DATABASE CONTRACT: Symbols Table Schema
        # ============================================================================
        # The symbols table MUST maintain 4 types:
        #   - function: Function/method declarations
        #   - class: Class declarations
        #   - call: Function/method calls (e.g., res.send(), db.query())
        #   - property: Property accesses (e.g., req.body, req.query)
        #
        # CRITICAL: Taint analyzer depends on call/property symbols.
        # Query: SELECT * FROM symbols WHERE type='call' OR type='property'
        #
        # DO NOT remove call/property extraction without:
        #   1. Creating alternative tables (calls, properties)
        #   2. Updating ALL taint analyzer queries
        #   3. Updating memory cache pre-computation
        #   4. Testing on 3+ real-world projects
        #
        # Removing call/property symbols = taint analysis returns 0 results.
        # This is a DATABASE CONTRACT, not a design opinion.
        # ============================================================================

        # Extract call symbols for taint analysis
        calls = self.ast_parser.extract_calls(tree)
        if calls:
            for call in calls:
                result['symbols'].append({
                    'name': call.get('name', ''),
                    'type': 'call',
                    'line': call.get('line', 0),
                    'col': call.get('col', call.get('column', 0))
                })
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] JS extractor: Found {len(calls)} call symbols")

        # Extract property access symbols for taint analysis
        properties = self.ast_parser.extract_properties(tree)
        if properties:
            for prop in properties:
                result['symbols'].append({
                    'name': prop.get('name', ''),
                    'type': 'property',
                    'line': prop.get('line', 0),
                    'col': prop.get('col', prop.get('column', 0))
                })
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] JS extractor: Found {len(properties)} property symbols")

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
            # Convert to 3-tuple format (method, pattern, controls)
            result['routes'] = [(method, path, []) for method, path in routes]

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

                # Check for hook usage - use function_calls, not removed 'calls' variable
                hook_calls = []
                for fc in result.get('function_calls', []):
                    call_name = fc.get('callee_function', '')
                    if call_name.startswith('use') and fc.get('line', 0) >= func.get('line', 0):
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

        # Detect Vue components and patterns - use function_calls, not removed 'calls' variable
        for fc in result.get('function_calls', []):
            call_name = fc.get('callee_function', '')

            # Vue 3 Composition API
            if call_name == 'defineComponent':
                result['vue_components'].append({
                    'name': file_info.get('path', '').split('/')[-1].split('.')[0],
                    'type': 'composition-api',
                    'start_line': fc.get('line', 0),
                    'end_line': fc.get('line', 0),
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
                    'line': fc.get('line', 0),
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
                    'line': fc.get('line', 0),
                    'component_name': 'global',
                    'operation_type': call_name,
                    'key_name': 'unknown',
                    'value_expr': None,
                    'is_reactive': False
                })

            # Vue directives (would need template parsing for full support)
            elif call_name.startswith('v-') or call_name in ['directive']:
                result['vue_directives'].append({
                    'line': fc.get('line', 0),
                    'directive_name': call_name,
                    'element_type': None,
                    'argument': None,
                    'modifiers': [],
                    'value_expr': None,
                    'is_dynamic': False
                })

        # Detect ORM queries with DETAILED analysis
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

        for fc in result.get('function_calls', []):
            method = fc.get('callee_function', '').split('.')[-1]
            if method in orm_methods:
                line = fc.get('line', 0)

                # Analyze arguments for includes/relations, limit, transaction
                includes = None
                has_limit = False
                has_transaction = False

                # Get all arguments for this call
                matching_args = [c for c in result.get('function_calls', [])
                               if c.get('line') == line and
                               c.get('callee_function') == fc.get('callee_function')]

                # Check first argument (usually options object)
                if matching_args:
                    first_arg = [c for c in matching_args if c.get('argument_index') == 0]
                    if first_arg:
                        arg_expr = first_arg[0].get('argument_expr', '')

                        # Check for includes/relations
                        if 'include:' in arg_expr or 'include :' in arg_expr:
                            # Extract include value
                            includes = 'has_includes'
                        elif 'relations:' in arg_expr or 'relations :' in arg_expr:
                            includes = 'has_relations'

                        # Check for limit/take
                        if any(term in arg_expr for term in ['limit:', 'limit :', 'take:', 'take :', 'skip:', 'offset:']):
                            has_limit = True

                        # Check for transaction
                        if 'transaction:' in arg_expr or 'transaction :' in arg_expr:
                            has_transaction = True

                # Check if in transaction block (simplified check)
                caller_func = fc.get('caller_function', '')
                if 'transaction' in caller_func.lower() or 'withTransaction' in caller_func:
                    has_transaction = True

                result['orm_queries'].append({
                    'line': line,
                    'query_type': fc.get('callee_function', method),
                    'includes': includes,
                    'has_limit': has_limit,
                    'has_transaction': has_transaction
                })

        # Detect API endpoints from route definitions
        if result.get('routes'):
            for method, path, middleware in result['routes']:
                result['api_endpoints'].append({
                    'line': 0,  # Routes are regex-extracted, no line info
                    'http_method': method,
                    'route_path': path,
                    'has_auth': any('auth' in str(m).lower() for m in middleware),
                    'has_validation': any('validat' in str(m).lower() for m in middleware),
                    'middleware_stack': middleware[:5] if middleware else []
                })

        # === CRITICAL SECURITY PATTERN DETECTION ===

        # Extract SQL queries from database execution calls using already-extracted function_calls
        # This uses the AST data we already have instead of regex
        result['sql_queries'] = self._extract_sql_from_function_calls(
            result.get('function_calls', []),
            file_info.get('path', '')
        )

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

    def _analyze_import_styles(self, imports: List[Dict], file_path: str) -> List[Dict]:
        """Analyze import statements to determine import style.

        Classifies imports into categories for tree-shaking analysis:
        - namespace: import * as lodash from 'lodash' (prevents tree-shaking)
        - named: import { map, filter } from 'lodash' (allows tree-shaking)
        - default: import lodash from 'lodash' (depends on export structure)
        - side-effect: import 'polyfill' (no tree-shaking, intentional)

        This enables bundle_analyze.py CHECK 3 (inefficient namespace imports).

        Args:
            imports: List of import dictionaries from ast_parser
            file_path: Path to the file being analyzed

        Returns:
            List of import style records for database
        """
        import_styles = []

        for imp in imports:
            target = imp.get('target', '')
            if not target:
                continue

            line = imp.get('line', 0)

            # Determine import style from import structure
            import_style = None
            imported_names = None
            alias_name = None
            full_statement = imp.get('text', '')

            # Check for namespace import: import * as X
            if imp.get('namespace'):
                import_style = 'namespace'
                alias_name = imp.get('namespace')

            # Check for named imports: import { a, b }
            elif imp.get('names'):
                import_style = 'named'
                imported_names = imp.get('names', [])

            # Check for default import: import X
            elif imp.get('default'):
                import_style = 'default'
                alias_name = imp.get('default')

            # Side-effect only: import 'package'
            elif not imp.get('namespace') and not imp.get('names') and not imp.get('default'):
                import_style = 'side-effect'

            # Only add if we could classify the import
            if import_style:
                import_styles.append({
                    'line': line,
                    'package': target,
                    'import_style': import_style,
                    'imported_names': imported_names,
                    'alias_name': alias_name,
                    'full_statement': full_statement[:200] if full_statement else None
                })

        return import_styles

    def _determine_sql_source(self, file_path: str, method_name: str) -> str:
        """Determine extraction source category for SQL query.

        This categorization allows rules to filter intelligently:
        - migration_file: DDL from migration files (LOW priority for SQL injection)
        - orm_query: ORM method calls (MEDIUM priority, usually parameterized)
        - code_execute: Direct database execution (HIGH priority for injection)

        Args:
            file_path: Path to the file being analyzed
            method_name: Database method name (execute, query, findAll, etc.)

        Returns:
            extraction_source category string
        """
        file_path_lower = file_path.lower()

        # Migration files (highest priority check)
        if 'migration' in file_path_lower or 'migrate' in file_path_lower:
            return 'migration_file'

        # Database schema files
        if file_path.endswith('.sql') or 'schema' in file_path_lower:
            return 'migration_file'  # DDL schemas treated as migrations

        # ORM methods (Sequelize, Prisma, TypeORM)
        ORM_METHODS = frozenset([
            'findAll', 'findOne', 'findByPk', 'create', 'update', 'destroy',  # Sequelize
            'findMany', 'findUnique', 'findFirst', 'upsert', 'createMany',    # Prisma
            'find', 'save', 'remove', 'createQueryBuilder', 'getRepository'   # TypeORM
        ])

        if method_name in ORM_METHODS:
            return 'orm_query'

        # Default: direct database execution in code (highest risk)
        return 'code_execute'

    def _extract_sql_from_function_calls(self, function_calls: List[Dict], file_path: str) -> List[Dict]:
        """Extract SQL queries from database execution method calls.

        Uses already-extracted function_calls data to find SQL execution calls
        like db.execute(), connection.query(), pool.raw(), etc.

        This is AST-based extraction (via function_calls) instead of regex,
        eliminating the 97.6% false positive rate.

        Args:
            function_calls: List of function call dictionaries from AST parser
            file_path: Path to the file being analyzed (for source categorization)

        Returns:
            List of SQL query dictionaries with extraction_source tags
        """
        queries = []

        # SQL execution method names
        SQL_METHODS = frozenset([
            'execute', 'query', 'raw', 'exec', 'run',
            'executeSql', 'executeQuery', 'execSQL', 'select',
            'insert', 'update', 'delete', 'query_raw'
        ])

        # Check sqlparse availability
        try:
            import sqlparse
            HAS_SQLPARSE = True
        except ImportError:
            HAS_SQLPARSE = False
            return queries

        for call in function_calls:
            callee = call.get('callee_function', '')

            # Check if method name matches SQL execution pattern
            method_name = callee.split('.')[-1] if '.' in callee else callee

            if method_name not in SQL_METHODS:
                continue

            # Only check first argument (SQL query string)
            if call.get('argument_index') != 0:
                continue

            # Get the argument expression
            arg_expr = call.get('argument_expr', '')
            if not arg_expr:
                continue

            # Check if it looks like SQL (contains SQL keywords)
            if not any(keyword in arg_expr.upper() for keyword in
                      ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER']):
                continue

            # Remove quotes if it's a string literal
            query_text = arg_expr.strip()
            if (query_text.startswith('"') and query_text.endswith('"')) or \
               (query_text.startswith("'") and query_text.endswith("'")):
                query_text = query_text[1:-1]

            # Skip template literals and variables (can't analyze statically)
            if '${' in query_text or query_text.startswith('`'):
                continue

            # Parse SQL to extract metadata
            try:
                parsed = sqlparse.parse(query_text)
                if not parsed:
                    continue

                statement = parsed[0]
                command = statement.get_type()

                # Skip UNKNOWN commands (unparseable)
                if not command or command == 'UNKNOWN':
                    continue

                # Extract table names
                tables = []
                tokens = list(statement.flatten())
                for i, token in enumerate(tokens):
                    if token.ttype is None and token.value.upper() in ['FROM', 'INTO', 'UPDATE', 'TABLE', 'JOIN']:
                        for j in range(i + 1, len(tokens)):
                            next_token = tokens[j]
                            if not next_token.is_whitespace:
                                if next_token.ttype in [None, sqlparse.tokens.Name]:
                                    table_name = next_token.value.strip('"\'`')
                                    if '.' in table_name:
                                        table_name = table_name.split('.')[-1]
                                    if table_name and table_name.upper() not in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                                        tables.append(table_name)
                                break

                # Determine extraction source for intelligent filtering
                extraction_source = self._determine_sql_source(file_path, method_name)

                queries.append({
                    'line': call.get('line', 0),
                    'query_text': query_text[:1000],
                    'command': command,
                    'tables': tables,
                    'extraction_source': extraction_source
                })

            except Exception:
                # Failed to parse - skip
                continue

        return queries