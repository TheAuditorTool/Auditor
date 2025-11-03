"""Core storage handlers for language-agnostic patterns.

This module contains handlers for code patterns that apply across all languages:
- File tracking: imports, refs
- Code structure: symbols, type_annotations, class_properties
- Data flow: assignments, function_calls, returns
- Security: sql_objects, sql_queries, jwt_patterns
- Control flow: cfg blocks/edges/statements
- Analysis: variable_usage, object_literals, orm_queries, orm_relationships
- Infrastructure: cdk_constructs, routes
- Validation: validation_framework_usage
- Build: package_configs

Handler Count: 21
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
from .base import BaseStorage

logger = logging.getLogger(__name__)


class CoreStorage(BaseStorage):
    """Core storage handlers for language-agnostic patterns."""

    def __init__(self, db_manager, counts: Dict[str, int]):
        super().__init__(db_manager, counts)

        # Register core handlers
        self.handlers = {
            'imports': self._store_imports,
            'routes': self._store_routes,
            'sql_objects': self._store_sql_objects,
            'sql_queries': self._store_sql_queries,
            'cdk_constructs': self._store_cdk_constructs,
            'symbols': self._store_symbols,
            'type_annotations': self._store_type_annotations,
            'orm_queries': self._store_orm_queries,
            'validation_framework_usage': self._store_validation_framework_usage,
            'assignments': self._store_assignments,
            'function_calls': self._store_function_calls,
            'returns': self._store_returns,
            'cfg': self._store_cfg,
            'jwt_patterns': self._store_jwt_patterns,
            'react_components': self._store_react_components,
            'class_properties': self._store_class_properties,
            'env_var_usage': self._store_env_var_usage,
            'orm_relationships': self._store_orm_relationships,
            'variable_usage': self._store_variable_usage,
            'object_literals': self._store_object_literals,
            'package_configs': self._store_package_configs,
        }

    def _store_imports(self, file_path: str, imports: List, jsx_pass: bool):
        """Store imports/references."""
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] Processing {len(imports)} imports for {file_path}")
        for import_tuple in imports:
            if len(import_tuple) == 3:
                kind, value, line = import_tuple
            else:
                kind, value = import_tuple
                line = None

            resolved = self._current_extracted.get('resolved_imports', {}).get(value, value)
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG]   Adding ref: {file_path} -> {kind} {resolved} (line {line})")
            self.db_manager.add_ref(file_path, kind, resolved, line)
            self.counts['refs'] += 1

    def _store_routes(self, file_path: str, routes: List, jsx_pass: bool):
        """Store routes (api_endpoints with all 8 fields)."""
        for route in routes:
            if isinstance(route, dict):
                self.db_manager.add_endpoint(
                    file_path=file_path,
                    method=route.get('method', 'GET'),
                    pattern=route.get('pattern', ''),
                    controls=route.get('controls', []),
                    line=route.get('line'),
                    path=route.get('path'),
                    has_auth=route.get('has_auth', False),
                    handler_function=route.get('handler_function')
                )
            else:
                method, pattern, controls = route
                self.db_manager.add_endpoint(file_path, method, pattern, controls)
            self.counts['routes'] += 1

    def _store_sql_objects(self, file_path: str, sql_objects: List, jsx_pass: bool):
        """Store SQL objects."""
        for kind, name in sql_objects:
            self.db_manager.add_sql_object(file_path, kind, name)
            self.counts['sql'] += 1

    def _store_sql_queries(self, file_path: str, sql_queries: List, jsx_pass: bool):
        """Store SQL queries."""
        for query in sql_queries:
            self.db_manager.add_sql_query(
                file_path, query['line'], query['query_text'],
                query['command'], query['tables'],
                query.get('extraction_source', 'code_execute')
            )
            self.counts['sql_queries'] += 1

    def _store_cdk_constructs(self, file_path: str, cdk_constructs: List, jsx_pass: bool):
        """Store CDK constructs (AWS Infrastructure-as-Code)."""
        for construct in cdk_constructs:
            line = construct.get('line', 0)
            cdk_class = construct.get('cdk_class', '')
            construct_name = construct.get('construct_name')

            construct_id = f"{file_path}::L{line}::{cdk_class}::{construct_name or 'unnamed'}"

            if os.environ.get('THEAUDITOR_CDK_DEBUG') == '1':
                print(f"[CDK-INDEX] Generating construct_id: {construct_id}")
                print(f"[CDK-INDEX]   file_path={file_path}, line={line}, cdk_class={cdk_class}, construct_name={construct_name}")

            self.db_manager.add_cdk_construct(
                file_path=file_path,
                line=line,
                cdk_class=cdk_class,
                construct_name=construct_name,
                construct_id=construct_id
            )

            for prop in construct.get('properties', []):
                self.db_manager.add_cdk_construct_property(
                    construct_id=construct_id,
                    property_name=prop.get('name', ''),
                    property_value_expr=prop.get('value_expr', ''),
                    line=prop.get('line', line)
                )

            if 'cdk_constructs' not in self.counts:
                self.counts['cdk_constructs'] = 0
            self.counts['cdk_constructs'] += 1

    def _store_symbols(self, file_path: str, symbols: List, jsx_pass: bool):
        """Store symbols."""
        for symbol in symbols:
            if jsx_pass:
                # JSX preserved mode - store to _jsx tables
                self.db_manager.add_symbol_jsx(
                    file_path, symbol['name'], symbol['type'],
                    symbol['line'], symbol['col'],
                    jsx_mode='preserved', extraction_pass=2
                )
            else:
                # Transform mode - store to main tables
                parameters_json = None
                if 'parameters' in symbol and symbol['parameters']:
                    parameters_json = json.dumps(symbol['parameters'])

                self.db_manager.add_symbol(
                    file_path, symbol['name'], symbol['type'],
                    symbol['line'], symbol['col'], symbol.get('end_line'),
                    symbol.get('type_annotation'),
                    parameters_json
                )
                self.counts['symbols'] += 1

    def _store_type_annotations(self, file_path: str, type_annotations: List, jsx_pass: bool):
        """Store TypeScript type annotations."""
        for annotation in type_annotations:
            self.db_manager.add_type_annotation(
                file_path,
                annotation.get('line', 0),
                annotation.get('column', 0),
                annotation.get('symbol_name', ''),
                annotation.get('annotation_type', annotation.get('symbol_kind', 'unknown')),
                annotation.get('type_annotation', annotation.get('type_text', '')),
                annotation.get('is_any', False),
                annotation.get('is_unknown', False),
                annotation.get('is_generic', False),
                annotation.get('has_type_params', False),
                annotation.get('type_params'),
                annotation.get('return_type'),
                annotation.get('extends_type')
            )

            language = (annotation.get('language') or '').lower()
            if not language:
                ext = Path(file_path).suffix.lower()
                if ext in {'.ts', '.tsx', '.js', '.jsx'}:
                    language = 'typescript'
                elif ext == '.py':
                    language = 'python'
                elif ext == '.rs':
                    language = 'rust'

            if language in {'typescript', 'javascript'}:
                self.counts['type_annotations_typescript'] += 1
            elif language == 'python':
                self.counts['type_annotations_python'] += 1
            elif language == 'rust':
                self.counts['type_annotations_rust'] += 1

            self.counts['type_annotations'] += 1

    def _store_orm_queries(self, file_path: str, orm_queries: List, jsx_pass: bool):
        """Store ORM queries."""
        for query in orm_queries:
            self.db_manager.add_orm_query(
                file_path, query['line'], query['query_type'],
                query.get('includes'), query.get('has_limit', False),
                query.get('has_transaction', False)
            )
            self.counts['orm'] += 1

    def _store_validation_framework_usage(self, file_path: str, validation_framework_usage: List, jsx_pass: bool):
        """Store validation framework usage (for taint analysis sanitizer detection)."""
        if os.environ.get("THEAUDITOR_VALIDATION_DEBUG") and file_path.endswith('validate.ts'):
            print(f"[PY-DEBUG] Extracted keys for {file_path}: {list(self._current_extracted.keys())}", file=sys.stderr)
            print(f"[PY-DEBUG] validation_framework_usage has {len(validation_framework_usage)} items", file=sys.stderr)

        for usage in validation_framework_usage:
            self.db_manager.generic_batches['validation_framework_usage'].append((
                file_path,
                usage['line'],
                usage['framework'],
                usage['method'],
                usage.get('variable_name'),
                1 if usage.get('is_validator', True) else 0,
                usage.get('argument_expr', '')
            ))
        if len(self.db_manager.generic_batches['validation_framework_usage']) >= self.db_manager.batch_size:
            self.db_manager.flush_generic_batch('validation_framework_usage')

    def _store_assignments(self, file_path: str, assignments: List, jsx_pass: bool):
        """Store data flow information for taint analysis."""
        if assignments:
            logger.info(f"[DEBUG] Found {len(assignments)} assignments in {file_path}")
            if assignments:
                first = assignments[0]
                logger.info(f"[DEBUG] First assignment: line {first.get('line')}, {first.get('target_var')} = {first.get('source_expr', '')[:50]}")
        for assignment in assignments:
            if jsx_pass:
                # JSX preserved mode - store to _jsx tables
                self.db_manager.add_assignment_jsx(
                    file_path, assignment['line'], assignment['target_var'],
                    assignment['source_expr'], assignment['source_vars'],
                    assignment['in_function'], assignment.get('property_path'),
                    jsx_mode='preserved', extraction_pass=2
                )
            else:
                # Transform mode - store to main tables
                self.db_manager.add_assignment(
                    file_path, assignment['line'], assignment['target_var'],
                    assignment['source_expr'], assignment['source_vars'],
                    assignment['in_function'], assignment.get('property_path')
                )
                self.counts['assignments'] += 1

    def _store_function_calls(self, file_path: str, function_calls: List, jsx_pass: bool):
        """Store function calls."""
        for call in function_calls:
            callee = call['callee_function']

            # JWT Categorization Enhancement (only for transform mode)
            if not jsx_pass and ('jwt' in callee.lower() or 'jsonwebtoken' in callee.lower()):
                if '.sign' in callee:
                    if call.get('argument_index') == 1:
                        arg_expr = call.get('argument_expr', '')
                        if 'process.env' in arg_expr:
                            call['callee_function'] = 'JWT_SIGN_ENV'
                        elif '"' in arg_expr or "'" in arg_expr:
                            call['callee_function'] = 'JWT_SIGN_HARDCODED'
                        else:
                            call['callee_function'] = 'JWT_SIGN_VAR'
                    else:
                        call['callee_function'] = f'JWT_SIGN#{call["callee_function"]}'
                elif '.verify' in callee:
                    call['callee_function'] = f'JWT_VERIFY#{callee}'
                elif '.decode' in callee:
                    call['callee_function'] = f'JWT_DECODE#{callee}'

            if jsx_pass:
                # JSX preserved mode - store to _jsx tables
                self.db_manager.add_function_call_arg_jsx(
                    file_path, call['line'], call['caller_function'],
                    call['callee_function'], call['argument_index'],
                    call['argument_expr'], call['param_name'],
                    jsx_mode='preserved', extraction_pass=2
                )
            else:
                # Transform mode - store to main tables
                # ZERO FALLBACK POLICY: Hard fail on wrong types
                # If these are dicts, the extractor is broken and must be fixed
                callee_file_path = call.get('callee_file_path')
                param_name = call.get('param_name', '')

                # Validate types - fail loudly if extractor produced wrong data
                if isinstance(callee_file_path, dict):
                    logger.error(
                        f"[EXTRACTOR BUG] callee_file_path is dict (expected str or None) in {file_path}:{call['line']}\n"
                        f"  Value: {callee_file_path}\n"
                        f"  This indicates bug in TypeScript extractor (typescript_impl.py:518-524)\n"
                        f"  SKIPPING this function call to prevent database corruption."
                    )
                    continue  # Skip this call - don't store corrupted data

                if isinstance(param_name, dict):
                    logger.error(
                        f"[EXTRACTOR BUG] param_name is dict (expected str) in {file_path}:{call['line']}\n"
                        f"  Value: {param_name}\n"
                        f"  Callee: {call['callee_function']}\n"
                        f"  This indicates bug in extraction layer producing dict instead of string.\n"
                        f"  SKIPPING this function call to prevent database corruption."
                    )
                    continue  # Skip this call - don't store corrupted data

                self.db_manager.add_function_call_arg(
                    file_path, call['line'], call['caller_function'],
                    call['callee_function'], call['argument_index'],
                    call['argument_expr'], param_name,
                    callee_file_path=callee_file_path
                )
                self.counts['function_calls'] += 1

    def _store_returns(self, file_path: str, returns: List, jsx_pass: bool):
        """Store return statements."""
        for ret in returns:
            if jsx_pass:
                # JSX preserved mode - store to _jsx tables
                self.db_manager.add_function_return_jsx(
                    file_path, ret['line'], ret['function_name'],
                    ret['return_expr'], ret['return_vars'],
                    ret.get('has_jsx', False), ret.get('returns_component', False),
                    ret.get('cleanup_operations'),
                    jsx_mode='preserved', extraction_pass=2
                )
            else:
                # Transform mode - store to main tables
                self.db_manager.add_function_return(
                    file_path, ret['line'], ret['function_name'],
                    ret['return_expr'], ret['return_vars']
                )
                self.counts['returns'] += 1

    def _store_cfg(self, file_path: str, cfg: List, jsx_pass: bool):
        """Store control flow graph data to main or _jsx tables."""
        for function_cfg in cfg:
            if not function_cfg:
                continue

            block_id_map = {}

            for block in function_cfg.get('blocks', []):
                temp_id = block['id']

                if jsx_pass:
                    real_id = self.db_manager.add_cfg_block_jsx(
                        file_path,
                        function_cfg['function_name'],
                        block['type'],
                        block['start_line'],
                        block['end_line'],
                        block.get('condition')
                    )
                else:
                    real_id = self.db_manager.add_cfg_block(
                        file_path,
                        function_cfg['function_name'],
                        block['type'],
                        block['start_line'],
                        block['end_line'],
                        block.get('condition')
                    )

                block_id_map[temp_id] = real_id
                self.counts['cfg_blocks'] += 1

                for stmt in block.get('statements', []):
                    if jsx_pass:
                        self.db_manager.add_cfg_statement_jsx(
                            real_id,
                            stmt['type'],
                            stmt['line'],
                            stmt.get('text')
                        )
                    else:
                        self.db_manager.add_cfg_statement(
                            real_id,
                            stmt['type'],
                            stmt['line'],
                            stmt.get('text')
                        )
                    self.counts['cfg_statements'] += 1

            for edge in function_cfg.get('edges', []):
                source_id = block_id_map.get(edge['source'], edge['source'])
                target_id = block_id_map.get(edge['target'], edge['target'])

                if jsx_pass:
                    self.db_manager.add_cfg_edge_jsx(
                        file_path,
                        function_cfg['function_name'],
                        source_id,
                        target_id,
                        edge['type']
                    )
                else:
                    self.db_manager.add_cfg_edge(
                        file_path,
                        function_cfg['function_name'],
                        source_id,
                        target_id,
                        edge['type']
                    )
                self.counts['cfg_edges'] += 1

            if 'cfg_functions' not in self.counts:
                self.counts['cfg_functions'] = 0
            self.counts['cfg_functions'] += 1

    def _store_jwt_patterns(self, file_path: str, jwt_patterns: List, jsx_pass: bool):
        """Store dedicated JWT patterns."""
        for pattern in jwt_patterns:
            self.db_manager.add_jwt_pattern(
                file_path=file_path,
                line_number=pattern['line'],
                pattern_type=pattern['type'],
                pattern_text=pattern.get('full_match', ''),
                secret_source=pattern.get('secret_type', 'unknown'),
                algorithm=pattern.get('algorithm')
            )
            self.counts['jwt'] = self.counts.get('jwt', 0) + 1

    def _store_react_components(self, file_path: str, react_components: List, jsx_pass: bool):
        """Store React-specific data."""
        for component in react_components:
            self.db_manager.add_react_component(
                file_path,
                component['name'],
                component['type'],
                component['start_line'],
                component['end_line'],
                component['has_jsx'],
                component.get('hooks_used'),
                component.get('props_type')
            )
            self.counts['react_components'] += 1

    def _store_class_properties(self, file_path: str, class_properties: List, jsx_pass: bool):
        """Store class property declarations (TypeScript/JavaScript ES2022+)."""
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG INDEXER] Found {len(class_properties)} class_properties for {file_path}")
        for prop in class_properties:
            if os.environ.get("THEAUDITOR_DEBUG") and len(class_properties) > 0:
                print(f"[DEBUG INDEXER]   Adding {prop['class_name']}.{prop['property_name']} at line {prop['line']}")
            self.db_manager.add_class_property(
                file_path,
                prop['line'],
                prop['class_name'],
                prop['property_name'],
                prop.get('property_type'),
                prop.get('is_optional', False),
                prop.get('is_readonly', False),
                prop.get('access_modifier'),
                prop.get('has_declare', False),
                prop.get('initializer')
            )
            if 'class_properties' not in self.counts:
                self.counts['class_properties'] = 0
            self.counts['class_properties'] += 1

    def _store_env_var_usage(self, file_path: str, env_var_usage: List, jsx_pass: bool):
        """Store environment variable usage (process.env.X)."""
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG INDEXER] Found {len(env_var_usage)} env_var_usage for {file_path}")
        for usage in env_var_usage:
            self.db_manager.add_env_var_usage(
                file_path,
                usage['line'],
                usage['var_name'],
                usage['access_type'],
                usage.get('in_function'),
                usage.get('property_access')
            )
            if 'env_var_usage' not in self.counts:
                self.counts['env_var_usage'] = 0
            self.counts['env_var_usage'] += 1

    def _store_orm_relationships(self, file_path: str, orm_relationships: List, jsx_pass: bool):
        """Store ORM relationship declarations (hasMany, belongsTo, etc.)."""
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG INDEXER] Found {len(orm_relationships)} orm_relationships for {file_path}")
        for rel in orm_relationships:
            self.db_manager.add_orm_relationship(
                file_path,
                rel['line'],
                rel['source_model'],
                rel['target_model'],
                rel['relationship_type'],
                rel.get('foreign_key'),
                rel.get('cascade_delete', False),
                rel.get('as_name')
            )
            if 'orm_relationships' not in self.counts:
                self.counts['orm_relationships'] = 0
            self.counts['orm_relationships'] += 1

    def _store_variable_usage(self, file_path: str, variable_usage: List, jsx_pass: bool):
        """Store variable usage."""
        for var in variable_usage:
            self.db_manager.add_variable_usage(
                file_path,
                var['line'],
                var['variable_name'],
                var['usage_type'],
                var.get('in_component'),
                var.get('in_hook'),
                var.get('scope_level', 0)
            )
            self.counts['variable_usage'] += 1

    def _store_object_literals(self, file_path: str, object_literals: List, jsx_pass: bool):
        """Store object literal storage (PHASE 3)."""
        for obj_lit in object_literals:
            self.db_manager.add_object_literal(
                file_path,
                obj_lit['line'],
                obj_lit['variable_name'],
                obj_lit['property_name'],
                obj_lit['property_value'],
                obj_lit['property_type'],
                obj_lit.get('nested_level', 0),
                obj_lit.get('in_function', '')
            )
            self.counts['object_literals'] += 1

    def _store_package_configs(self, file_path: str, package_configs: List, jsx_pass: bool):
        """Store build analysis data."""
        for pkg_config in package_configs:
            self.db_manager.add_package_config(
                pkg_config['file_path'],
                pkg_config['package_name'],
                pkg_config['version'],
                pkg_config.get('dependencies'),
                pkg_config.get('dev_dependencies'),
                pkg_config.get('peer_dependencies'),
                pkg_config.get('scripts'),
                pkg_config.get('engines'),
                pkg_config.get('workspaces'),
                pkg_config.get('is_private', False)
            )
            self.counts['package_configs'] += 1