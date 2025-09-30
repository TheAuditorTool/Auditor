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
        jsx_mode = file_info.get('jsx_mode')
        result = {
            'imports': [],
            'resolved_imports': {},
            'routes': [],
            'symbols': [],
            'assignments': [],
            'function_calls': [],
            'returns': [],
            'orm_queries': [],
            'react_components': [],
            'react_hooks': [],
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
                return_expr = ret.get('return_expr', '')
                has_jsx = False
                if (jsx_mode or '').lower() == 'preserved':
                    snippet = return_expr or ''
                    has_jsx = '<' in snippet and '>' in snippet
                result['returns'].append({
                    'line': ret.get('line', 0),
                    'function_name': ret.get('function_name', 'global'),
                    'return_expr': return_expr,
                    'return_vars': ret.get('return_vars', []),
                    'has_jsx': has_jsx,
                })
            
            # Extract ORM queries
            result['orm_queries'] = self._extract_orm_queries(tree, content)
        
        # Extract SQL queries embedded in JavaScript code
        result['sql_queries'] = self.extract_sql_queries(content)

        if (jsx_mode or '').lower() == 'preserved':
            self._detect_react_metadata(file_info, content, result)

        return result

    def _detect_react_metadata(self, file_info: Dict[str, Any], content: str, result: Dict[str, Any]) -> None:
        """Populate React component and hook metadata for preserved JSX pass."""
        imported_modules = {mod for _, mod in result.get('imports', [])}
        has_react_import = any(mod.startswith('react') for mod in imported_modules)
        if not has_react_import:
            return
        component_patterns = [
            (re.compile(r'export\s+default\s+function\s+(?P<name>[A-Z][A-Za-z0-9_]*)'), 'default'),
            (re.compile(r'export\s+function\s+(?P<name>[A-Z][A-Za-z0-9_]*)'), 'named'),
            (re.compile(r'export\s+const\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(?[^\n=]*=>'), 'named'),
        ]

        discovered = {}
        for pattern, export_type in component_patterns:
            for match in pattern.finditer(content):
                name = match.group('name')
                if not name or name in discovered:
                    continue
                snippet_start = match.start()
                snippet = content[snippet_start: snippet_start + 600]
                if '<' not in snippet or '>' not in snippet:
                    continue
                line = content[:snippet_start].count('\n') + 1
                discovered[name] = {
                    'data': {
                        'name': name,
                        'line': line,
                        'col': 0,
                        'export': export_type,
                        'hook_calls': 0,
                    },
                    'start': snippet_start,
                }

        if not discovered:
            return

        hook_regex = re.compile(r'(?:React\.)?(use[A-Z][A-Za-z0-9_]*)\s*\(')
        for name, payload in discovered.items():
            component = payload['data']
            snippet_start = payload['start']
            snippet = content[snippet_start: snippet_start + 600]
            hooks = []
            for hook_match in hook_regex.finditer(snippet):
                hook_name = hook_match.group(1)
                absolute_index = snippet_start + hook_match.start()
                hook_line = content[:absolute_index].count('\n') + 1
                hooks.append({'name': hook_name, 'component': name, 'line': hook_line, 'col': 0})

            component['hook_calls'] = len(hooks)
            result['react_hooks'].extend(hooks)

            has_existing_jsx_return = any(
                ret.get('function_name') == name and ret.get('has_jsx')
                for ret in result.get('returns', [])
            )
            if not has_existing_jsx_return:
                result.setdefault('returns', []).append({
                    'line': component['line'],
                    'function_name': name,
                    'return_expr': '<jsx>',
                    'return_vars': [],
                    'has_jsx': True,
                })

        result['react_components'].extend([payload['data'] for payload in discovered.values()])

    @staticmethod
    def _detect_export_type(component_name: str, content: str) -> str:
        """Heuristically determine how a component is exported."""
        if re.search(rf'export\s+default\s+function\s+{component_name}\b', content):
            return 'default'
        if re.search(rf'export\s+(?:const|function|class)\s+{component_name}\b', content):
            return 'named'
        if re.search(rf'export\s*\{{[^}}]*\b{component_name}\b', content):
            return 'named'
        return 'local'

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

            raw_parts = [segment.strip() for segment in middleware_str.split(',')]
            middleware: List[str] = []
            candidates = raw_parts[:-1] if len(raw_parts) > 1 else []
            ignore_tokens = {'req', 'res', 'next', 'async', 'function', 'err'}

            for candidate in candidates:
                token = candidate
                if '=>' in token:
                    continue
                token = token.replace('async', '').strip()
                token = token.split('(')[0].strip()
                token = re.sub(r'[^A-Za-z0-9_.$]', '', token)
                if not token or token in ignore_tokens:
                    continue
                middleware.append(token)

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
