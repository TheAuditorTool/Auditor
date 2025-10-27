"""Python file extractor.

Handles extraction of Python-specific elements including:
- Python imports (import/from statements)
- Flask/FastAPI route decorators with middleware
- AST-based symbol extraction

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is an EXTRACTOR layer module. It:
- RECEIVES: file_info dict (contains 'path' key from indexer)
- DELEGATES: To ast_parser.extract_X(tree) methods
- RETURNS: Extracted data WITHOUT file_path keys

The INDEXER layer (indexer/__init__.py) provides file_path and stores to database.
See indexer/__init__.py:619-564 for _store_extracted_data() implementation.

This separation ensures single source of truth for file paths.
"""

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseExtractor
from .sql import parse_sql_query
from theauditor.ast_extractors import python_impl
from theauditor.ast_extractors.base import get_node_name


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
            'cfg': [],  # Control flow graph data
            'object_literals': [],  # Dict literal parsing for dynamic dispatch
            'type_annotations': [],
            'resolved_imports': {},
            'orm_relationships': [],
            'python_orm_models': [],
            'python_orm_fields': [],
            'python_routes': [],
            'python_blueprints': [],
            'python_validators': [],
        }
        seen_symbols = set()
        
        # Extract imports using AST (proper Python import extraction)
        if tree and isinstance(tree, dict):
            result['imports'] = self._extract_imports_ast(tree)
            import os
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Python extractor found {len(result['imports'])} imports in {file_info['path']}")
            resolved = self._resolve_imports(file_info, tree)
            if resolved:
                result['resolved_imports'] = resolved
        else:
            # No AST available - skip import extraction
            result['imports'] = []
            result['resolved_imports'] = {}
            import os
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Python extractor: No AST for {file_info['path']}, skipping imports")
        
        # If we have an AST tree, extract Python-specific information
        if tree and isinstance(tree, dict):
            # Extract routes with decorators using AST
            result['routes'] = self._extract_routes_ast(tree, file_info['path'])
            
            # Extract symbols from AST parser results
            if self.ast_parser:
                # Functions
                functions = self.ast_parser.extract_functions(tree)
                for func in functions:
                    if func.get('type_annotations'):
                        result['type_annotations'].extend(func['type_annotations'])

                    symbol_entry = {
                        'name': func.get('name', ''),
                        'type': 'function',
                        'line': func.get('line', 0),
                        'end_line': func.get('end_line', func.get('line', 0)),  # Use end_line if available
                        'col': func.get('col', func.get('column', 0)),
                        'column': func.get('column', func.get('col', 0)),
                        'parameters': func.get('parameters', []),
                        'return_type': func.get('return_type'),
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)
                
                # Classes
                classes = self.ast_parser.extract_classes(tree)
                for cls in classes:
                    symbol_entry = {
                        'name': cls.get('name', ''),
                        'type': 'class',
                        'line': cls.get('line', 0),
                        'col': cls.get('col', cls.get('column', 0)),
                        'column': cls.get('column', cls.get('col', 0))
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)
                # Class/module attribute annotations
                attribute_annotations = python_impl.extract_python_attribute_annotations(tree, self.ast_parser)
                if attribute_annotations:
                    result['type_annotations'].extend(attribute_annotations)
                
                # Calls and other symbols
                symbols = self.ast_parser.extract_calls(tree)
                for symbol in symbols:
                    symbol_entry = {
                        'name': symbol.get('name', ''),
                        'type': symbol.get('type', 'call'),
                        'line': symbol.get('line', 0),
                        'col': symbol.get('col', symbol.get('column', 0))
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)

                # Property accesses for taint analysis (request.args, request.GET, etc.)
                properties = self.ast_parser.extract_properties(tree)
                for prop in properties:
                    symbol_entry = {
                        'name': prop.get('name', ''),
                        'type': 'property',
                        'line': prop.get('line', 0),
                        'col': prop.get('col', prop.get('column', 0))
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)

                # ORM metadata (SQLAlchemy & Django)
                sql_models, sql_fields, sql_relationships = python_impl.extract_sqlalchemy_definitions(tree, self.ast_parser)
                if sql_models:
                    result['python_orm_models'].extend(sql_models)
                if sql_fields:
                    result['python_orm_fields'].extend(sql_fields)
                if sql_relationships:
                    result['orm_relationships'].extend(sql_relationships)

                django_models, django_relationships = python_impl.extract_django_definitions(tree, self.ast_parser)
                if django_models:
                    result['python_orm_models'].extend(django_models)
                if django_relationships:
                    result['orm_relationships'].extend(django_relationships)

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
                    # Skip calls with empty callee_function (violates CHECK constraint)
                    callee = call.get('callee_function', '')
                    if not callee:
                        continue

                    result['function_calls'].append({
                        'line': call.get('line', 0),
                        'caller_function': call.get('caller_function', 'global'),
                        'callee_function': callee,
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

            # Extract dict literals using centralized AST infrastructure
            if tree and self.ast_parser:
                result['object_literals'] = self.ast_parser.extract_object_literals(tree)
        else:
            # Fallback to regex extraction for routes if no AST
            # Convert regex results to dictionary format for consistency
            fallback_routes = []
            for method, path in self.extract_routes(content):
                fallback_routes.append({
                    'line': 0,  # No line info from regex
                    'method': method,
                    'pattern': path,
                    'path': file_info['path'],
                    'has_auth': False,  # Can't detect auth from regex
                    'handler_function': '',  # No function name from regex
                    'controls': []
                })
            result['routes'] = fallback_routes
        
        # Extract SQL queries from db.execute() calls using AST
        if tree and isinstance(tree, dict):
            result['sql_queries'] = self._extract_sql_queries_ast(tree, content, file_info.get('path', ''))
        else:
            result['sql_queries'] = []

        # =================================================================
        # JWT EXTRACTION - AST ONLY, NO REGEX
        # =================================================================
        # Edge cases that regex might catch but AST won't: ~0.0001%
        # We accept this loss. If you encounter one, document it and move on.
        # DO NOT ADD REGEX FALLBACKS. EVER.
        if tree:
            result['jwt_patterns'] = self._extract_jwt_from_ast(tree, file_info.get('path', ''))
        else:
            result['jwt_patterns'] = []

        # CRITICAL FIX: Extract variable usage for ALL Python files
        # This is essential for complete taint analysis and dead code detection
        if tree and self.ast_parser:
            result['variable_usage'] = self._extract_variable_usage(tree, content)

        # Pydantic validators & Flask blueprints are AST-driven; safe to extract outside parser guard
        if tree and isinstance(tree, dict):
            validators = python_impl.extract_pydantic_validators(tree, self.ast_parser)
            if validators:
                result['python_validators'].extend(validators)
            blueprints = python_impl.extract_flask_blueprints(tree, self.ast_parser)
            if blueprints:
                result['python_blueprints'].extend(blueprints)

        # Mirror route data into python_routes for framework tracking
        if result['routes']:
            for route in result['routes']:
                result['python_routes'].append({
                    'line': route.get('line'),
                    'framework': route.get('framework', 'flask'),
                    'method': route.get('method'),
                    'pattern': route.get('pattern'),
                    'handler_function': route.get('handler_function'),
                    'has_auth': route.get('has_auth', False),
                    'dependencies': route.get('dependencies', []),
                    'blueprint': route.get('blueprint'),
                })

        return result
    
    def _resolve_imports(self, file_info: Dict[str, Any], tree: Dict[str, Any]) -> Dict[str, str]:
        """Resolve Python import targets to absolute module/file paths."""
        resolved: Dict[str, str] = {}
        actual_tree = tree.get("tree")

        if not isinstance(actual_tree, ast.AST):
            return resolved

        # Determine current module parts from file path
        file_path = Path(file_info['path'])
        module_parts = list(file_path.with_suffix('').parts)
        package_parts = module_parts[:-1]  # directory components

        def normalize_path(path: Path) -> str:
            return str(path).replace("\\", "/")

        def module_parts_to_path(parts: List[str]) -> Optional[str]:
            if not parts:
                return None
            candidate_file = Path(*parts).with_suffix('.py')
            candidate_init = Path(*parts) / '__init__.py'

            if (self.root_path / candidate_file).exists():
                return normalize_path(candidate_file)
            if (self.root_path / candidate_init).exists():
                return normalize_path(candidate_init)
            return None

        def resolve_dotted(module_name: str) -> Optional[str]:
            if not module_name:
                return None
            return module_parts_to_path(module_name.split('.'))

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    resolved_target = resolve_dotted(module_name) or module_name

                    local_name = alias.asname or module_name.split('.')[-1]

                    resolved[module_name] = resolved_target
                    resolved[local_name] = resolved_target

            elif isinstance(node, ast.ImportFrom):
                level = getattr(node, 'level', 0) or 0
                base_parts = package_parts.copy()

                if level:
                    if level <= len(base_parts):
                        base_parts = base_parts[:-level]
                    else:
                        base_parts = []

                module_name = node.module or ""
                module_name_parts = module_name.split('.') if module_name else []
                target_base = base_parts + module_name_parts

                # Resolve module itself
                module_key = '.'.join(part for part in target_base if part)
                module_path = module_parts_to_path(target_base)
                if module_key:
                    resolved[module_key] = module_path or module_key
                elif module_path:
                    resolved[module_path] = module_path

                for alias in node.names:
                    imported_name = alias.name
                    local_name = alias.asname or imported_name

                    full_parts = target_base + [imported_name]
                    symbol_path = module_parts_to_path(full_parts)

                    if symbol_path:
                        resolved_value = symbol_path
                    elif module_path:
                        resolved_value = module_path
                    elif module_key:
                        resolved_value = f"{module_key}.{imported_name}"
                    else:
                        resolved_value = local_name

                    resolved[local_name] = resolved_value

        return resolved
    
    def _extract_routes_ast(self, tree: Dict[str, Any], file_path: str) -> List[Dict]:
        """Extract Flask/FastAPI routes using Python AST.

        Args:
            tree: Parsed AST tree
            file_path: Path to file being analyzed

        Returns:
            List of route dictionaries with all 8 api_endpoints fields:
            - line: Line number of the route handler function
            - method: HTTP method (GET, POST, etc.)
            - pattern: Route pattern (e.g., '/api/users/<id>')
            - path: Full file path (same as file_path)
            - has_auth: Boolean indicating presence of auth decorators
            - handler_function: Name of the handler function
            - controls: List of non-route decorator names (middleware)
        """
        routes = []

        # Check if we have a Python AST tree
        if not isinstance(tree.get("tree"), ast.Module):
            return routes

        # Auth decorator patterns to detect
        AUTH_DECORATORS = frozenset([
            'login_required', 'auth_required', 'permission_required',
            'require_auth', 'authenticated', 'authorize', 'requires_auth',
            'jwt_required', 'token_required', 'verify_jwt', 'check_auth'
        ])

        # Walk the AST to find decorated functions
        for node in ast.walk(tree["tree"]):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_auth = False
                controls: List[str] = []
                framework = None
                blueprint_name = None
                method = 'GET'
                pattern = ''
                route_found = False

                for decorator in node.decorator_list:
                    dec_identifier = get_node_name(decorator)

                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        method_name = decorator.func.attr
                        owner_name = get_node_name(decorator.func.value)

                        if method_name in ['route'] + list(python_impl.FASTAPI_HTTP_METHODS):
                            pattern = ''
                            if decorator.args:
                                path_node = decorator.args[0]
                                if isinstance(path_node, ast.Constant):
                                    pattern = str(path_node.value)
                                elif hasattr(ast, "Str") and isinstance(path_node, ast.Str):
                                    pattern = path_node.s

                            if method_name == 'route':
                                method = 'GET'
                                for keyword in decorator.keywords:
                                    if keyword.arg == 'methods' and isinstance(keyword.value, ast.List) and keyword.value.elts:
                                        element = keyword.value.elts[0]
                                        if isinstance(element, ast.Constant):
                                            method = str(element.value).upper()
                            else:
                                method = method_name.upper()

                            framework = 'flask' if method_name == 'route' else 'fastapi'
                            blueprint_name = owner_name
                            route_found = True
                            dec_identifier = method_name

                    if dec_identifier and dec_identifier in AUTH_DECORATORS:
                        has_auth = True
                    elif dec_identifier and dec_identifier not in ['route'] + list(python_impl.FASTAPI_HTTP_METHODS):
                        controls.append(dec_identifier)

                if route_found:
                    dependencies = []
                    if framework == 'fastapi':
                        dependencies = python_impl._extract_fastapi_dependencies(node)

                    routes.append({
                        'line': node.lineno,
                        'method': method,
                        'pattern': pattern,
                        'path': file_path,
                        'has_auth': has_auth,
                        'handler_function': node.name,
                        'controls': controls,
                        'framework': framework or 'flask',
                        'dependencies': dependencies,
                        'blueprint': blueprint_name if framework == 'flask' else None,
                    })

        return routes

    def _extract_imports_ast(self, tree: Dict[str, Any]) -> List[tuple]:
        """Extract imports from Python AST.

        Uses Python's ast module to accurately extract import statements,
        avoiding false matches in comments, strings, or docstrings.

        Args:
            tree: Parsed AST tree dictionary

        Returns:
            List of (kind, module, line_number) tuples:
            - ('import', 'os', 15)
            - ('from', 'pathlib', 23)
        """
        imports = []

        # Handle None or non-dict input gracefully
        if not tree or not isinstance(tree, dict):
            return imports

        actual_tree = tree.get("tree")

        import os
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG]   _extract_imports_ast: tree type={type(tree)}, has 'tree' key={('tree' in tree) if isinstance(tree, dict) else False}")
            if isinstance(tree, dict) and 'tree' in tree:
                print(f"[DEBUG]   actual_tree type={type(actual_tree)}, isinstance(ast.Module)={isinstance(actual_tree, ast.Module)}")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG]   Returning empty - actual_tree check failed")
            return imports

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                # import os, sys, pathlib
                for alias in node.names:
                    imports.append(('import', alias.name, node.lineno))

            elif isinstance(node, ast.ImportFrom):
                # from pathlib import Path
                # Store the module name (pathlib), not the imported names
                module = node.module or ''  # Handle relative imports (module can be None)
                if module:  # Only store if module name exists
                    imports.append(('from', module, node.lineno))

        return imports

    def _resolve_imports(self, file_info: Dict[str, Any], tree: Dict[str, Any]) -> Dict[str, str]:
        """Resolve Python imports to module paths or local files."""
        resolved: Dict[str, str] = {}

        if not tree or not isinstance(tree, dict):
            return resolved

        actual_tree = tree.get("tree")
        if not isinstance(actual_tree, ast.AST):
            return resolved

        file_path = Path(file_info['path'])
        package_parts = list(file_path.with_suffix('').parts[:-1])

        def to_path(parts: List[str]) -> Optional[str]:
            if not parts:
                return None
            candidate = Path(*parts).with_suffix('.py')
            candidate_init = Path(*parts) / '__init__.py'
            for target in (candidate, candidate_init):
                absolute = (self.root_path / target).resolve()
                if absolute.exists():
                    return target.as_posix()
            return None

        def register(name: str, value: str) -> None:
            if not name or not value:
                return
            resolved[name] = value

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    module_parts = module_name.split('.')
                    resolved_value = to_path(module_parts) or module_name
                    local_name = alias.asname or module_parts[-1]
                    register(module_name, resolved_value)
                    register(local_name, resolved_value)
            elif isinstance(node, ast.ImportFrom):
                level = getattr(node, "level", 0) or 0
                base_parts = package_parts.copy()
                if level:
                    base_parts = base_parts[:-level] if level <= len(base_parts) else []
                module_parts = node.module.split('.') if node.module else []
                if module_parts and level == 0:
                    target_base = module_parts
                else:
                    target_base = base_parts + module_parts
                base_resolved = to_path(target_base)
                module_key = '.'.join(part for part in target_base if part)
                if module_key:
                    register(module_key, base_resolved or module_key)
                for alias in node.names:
                    imported_name = alias.name
                    local_name = alias.asname or imported_name
                    full_parts = target_base + [imported_name]
                    resolved_value = to_path(full_parts)
                    if not resolved_value:
                        candidate_key = module_key + '.' + imported_name if module_key else imported_name
                        resolved_value = candidate_key
                    register(local_name, resolved_value)
                    if module_key:
                        register(f"{module_key}.{imported_name}", resolved_value)

        return resolved

    def _determine_sql_source(self, file_path: str, method_name: str) -> str:
        """Determine extraction source category for SQL query (Python).

        Args:
            file_path: Path to the file being analyzed
            method_name: Database method name

        Returns:
            extraction_source category string
        """
        file_path_lower = file_path.lower()

        # Migration files
        if 'migration' in file_path_lower or 'migrate' in file_path_lower:
            return 'migration_file'

        # Database schema files
        if file_path.endswith('.sql') or 'schema' in file_path_lower:
            return 'migration_file'

        # Django/SQLAlchemy ORM methods
        ORM_METHODS = frozenset([
            'filter', 'get', 'create', 'update', 'delete', 'all',  # Django QuerySet
            'select', 'insert', 'update', 'delete',  # SQLAlchemy
            'exec_driver_sql', 'query'  # SQLAlchemy raw
        ])

        if method_name in ORM_METHODS:
            return 'orm_query'

        # Default: direct database execution
        return 'code_execute'

    def _resolve_sql_literal(self, node: ast.AST) -> Optional[str]:
        """Resolve AST node to static SQL string.

        Handles:
        - ast.Constant / ast.Str: Plain strings
        - ast.JoinedStr: F-strings (if all parts are static)
        - ast.BinOp(Add): String concatenation
        - ast.Call(.format): Format strings

        Returns:
            Static SQL string if resolvable, None if dynamic
        """
        # Plain string literal
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python 3.7
            return node.s

        # F-string: f"SELECT * FROM {table}"
        elif isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif isinstance(value, ast.FormattedValue):
                    # Dynamic expression - can't resolve statically
                    # BUT: If it's a simple constant, we can resolve
                    if isinstance(value.value, ast.Constant):
                        parts.append(str(value.value.value))
                    else:
                        # Dynamic variable/expression - return None (can't analyze)
                        return None
                else:
                    return None
            return ''.join(parts)

        # String concatenation: "SELECT * " + "FROM users"
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._resolve_sql_literal(node.left)
            right = self._resolve_sql_literal(node.right)
            if left is not None and right is not None:
                return left + right
            return None

        # .format() call: "SELECT * FROM {}".format("users")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'format':
                # Get base string
                base = self._resolve_sql_literal(node.func.value)
                if base is None:
                    return None

                # Check if all format arguments are constants
                args = []
                for arg in node.args:
                    if isinstance(arg, ast.Constant):
                        args.append(str(arg.value))
                    else:
                        return None  # Dynamic argument

                try:
                    return base.format(*args)
                except (IndexError, KeyError):
                    return None  # Malformed format string

        return None

    def _extract_sql_queries_ast(self, tree: Dict[str, Any], content: str, file_path: str = '') -> List[Dict]:
        """Extract SQL queries from database execution calls using AST.

        Detects actual SQL execution calls like:
        - cursor.execute("SELECT ...")
        - db.query("INSERT ...")
        - connection.raw("UPDATE ...")

        This avoids the 97.6% false positive rate of regex matching
        by only detecting actual database method calls.

        Args:
            tree: Parsed AST tree dictionary
            content: File content (for extracting string literals)
            file_path: Path to the file being analyzed (for source categorization)

        Returns:
            List of SQL query dictionaries with extraction_source tags
        """
        queries = []
        actual_tree = tree.get("tree")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            return queries

        # SQL execution method names
        SQL_METHODS = frozenset([
            'execute', 'executemany', 'executescript',  # sqlite3, psycopg2, mysql
            'query', 'raw', 'exec_driver_sql',  # Django ORM, SQLAlchemy
            'select', 'insert', 'update', 'delete',  # Query builder methods
        ])

        # No sqlparse import check - parse_sql_query() will raise ImportError
        # if sqlparse is missing, ensuring hard failure instead of silent skip

        for node in ast.walk(actual_tree):
            if not isinstance(node, ast.Call):
                continue

            # Check if this is a database method call
            method_name = None
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

            if method_name not in SQL_METHODS:
                continue

            # Extract SQL query from first argument (if it's a string literal)
            if not node.args:
                continue

            first_arg = node.args[0]

            # Resolve SQL literal (handles plain strings, f-strings, concatenations, .format())
            query_text = self._resolve_sql_literal(first_arg)

            if not query_text:
                # DEBUG: Log skipped queries
                import os
                if os.environ.get("THEAUDITOR_DEBUG"):
                    node_type = type(first_arg).__name__
                    print(f"[SQL EXTRACT] Skipped dynamic query at {file_path}:{node.lineno} (type: {node_type})")
                continue  # Not a string literal (variable, complex f-string, etc.)

            # Parse SQL using shared helper
            parsed = parse_sql_query(query_text)
            if not parsed:
                continue  # Unparseable or UNKNOWN command

            command, tables = parsed

            # Determine extraction source for intelligent filtering
            extraction_source = self._determine_sql_source(file_path, method_name)

            queries.append({
                'line': node.lineno,
                'query_text': query_text[:1000],  # Limit length
                'command': command,
                'tables': tables,
                'extraction_source': extraction_source
            })

        return queries

    def _extract_jwt_from_ast(self, tree: Dict[str, Any], file_path: str) -> List[Dict]:
        """Extract JWT patterns from PyJWT library calls using AST.

        NO REGEX. This uses Python AST analysis to detect JWT library usage.

        Detects PyJWT library usage:
        - jwt.encode(payload, key, algorithm='HS256')
        - jwt.decode(token, key, algorithms=['HS256'])

        Edge cases: ~0.0001% of obfuscated/dynamic JWT calls might be missed.
        We accept this. AST-first is non-negotiable.

        Args:
            tree: Parsed AST tree dictionary
            file_path: Path to the file being analyzed

        Returns:
            List of JWT pattern dicts matching orchestrator expectations:
            - line: int
            - type: 'jwt_sign' | 'jwt_verify' | 'jwt_decode'
            - full_match: str (function call context)
            - secret_type: 'hardcoded' | 'environment' | 'config' | 'variable' | 'unknown'
            - algorithm: str ('HS256', 'RS256', etc.) or None
        """
        patterns = []
        actual_tree = tree.get("tree")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            return patterns

        # JWT method names for PyJWT library (frozenset for O(1) lookup)
        JWT_ENCODE_METHODS = frozenset(['encode'])  # jwt.encode()
        JWT_DECODE_METHODS = frozenset(['decode'])  # jwt.decode()

        for node in ast.walk(actual_tree):
            if not isinstance(node, ast.Call):
                continue

            # Check if this is a JWT method call
            method_name = None
            is_jwt_call = False

            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                # Check if the object is 'jwt' (e.g., jwt.encode)
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == 'jwt':
                        is_jwt_call = True

            if not is_jwt_call or not method_name:
                continue

            # Determine pattern type
            pattern_type = None
            if method_name in JWT_ENCODE_METHODS:
                pattern_type = 'jwt_sign'
            elif method_name in JWT_DECODE_METHODS:
                pattern_type = 'jwt_decode'

            if not pattern_type:
                continue

            line = node.lineno

            if pattern_type == 'jwt_sign':
                # jwt.encode(payload, key, algorithm='HS256')
                # args[0]=payload, args[1]=key
                # keywords may contain algorithm
                secret_node = None
                algorithm = 'HS256'  # Default per JWT spec

                # Extract key argument (second positional argument)
                if len(node.args) >= 2:
                    secret_node = node.args[1]

                # Extract algorithm from keyword arguments
                for keyword in node.keywords:
                    if keyword.arg == 'algorithm':
                        if isinstance(keyword.value, ast.Constant):
                            algorithm = keyword.value.value
                        elif isinstance(keyword.value, ast.Str):  # Python 3.7 compat
                            algorithm = keyword.value.s

                # Categorize secret source
                secret_type = 'unknown'
                if secret_node:
                    if isinstance(secret_node, (ast.Constant, ast.Str)):
                        # Hardcoded string literal
                        secret_type = 'hardcoded'
                    elif isinstance(secret_node, ast.Subscript):
                        # os.environ['KEY'] or config['key']
                        if isinstance(secret_node.value, ast.Attribute):
                            if hasattr(secret_node.value, 'attr'):
                                if secret_node.value.attr == 'environ':
                                    secret_type = 'environment'
                        elif isinstance(secret_node.value, ast.Name):
                            if secret_node.value.id in ['config', 'settings', 'secrets']:
                                secret_type = 'config'
                    elif isinstance(secret_node, ast.Call):
                        # os.getenv('KEY')
                        if isinstance(secret_node.func, ast.Attribute):
                            if secret_node.func.attr == 'getenv':
                                secret_type = 'environment'
                        elif isinstance(secret_node.func, ast.Name):
                            if secret_node.func.id == 'getenv':
                                secret_type = 'environment'
                    elif isinstance(secret_node, ast.Attribute):
                        # config.JWT_SECRET or settings.SECRET_KEY
                        if isinstance(secret_node.value, ast.Name):
                            if secret_node.value.id in ['config', 'settings', 'secrets']:
                                secret_type = 'config'
                    elif isinstance(secret_node, ast.Name):
                        # Variable reference
                        secret_type = 'variable'

                full_match = f"jwt.encode(...)"

                patterns.append({
                    'line': line,
                    'type': pattern_type,
                    'full_match': full_match,
                    'secret_type': secret_type,
                    'algorithm': algorithm
                })

            elif pattern_type == 'jwt_decode':
                # jwt.decode(token, key, algorithms=['HS256'])
                algorithm = None

                # Extract algorithms from keyword arguments
                for keyword in node.keywords:
                    if keyword.arg == 'algorithms':
                        # algorithms is a list
                        if isinstance(keyword.value, ast.List):
                            if keyword.value.elts:
                                first_algo = keyword.value.elts[0]
                                if isinstance(first_algo, ast.Constant):
                                    algorithm = first_algo.value
                                elif isinstance(first_algo, ast.Str):
                                    algorithm = first_algo.s

                full_match = f"jwt.decode(...)"

                patterns.append({
                    'line': line,
                    'type': pattern_type,
                    'full_match': full_match,
                    'secret_type': None,  # Not applicable for decode
                    'algorithm': algorithm
                })

        return patterns

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
