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
import logging
import os
import sys
from pathlib import Path
from .base import BaseStorage

logger = logging.getLogger(__name__)


class CoreStorage(BaseStorage):
    """Core storage handlers for language-agnostic patterns."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        # Register core handlers
        self.handlers = {
            'imports': self._store_imports,
            'routes': self._store_routes,
            'router_mounts': self._store_router_mounts,  # PHASE 6.7
            'express_middleware_chains': self._store_express_middleware_chains,  # PHASE 5
            'sql_objects': self._store_sql_objects,
            'sql_queries': self._store_sql_queries,
            'cdk_constructs': self._store_cdk_constructs,
            'cdk_construct_properties': self._store_cdk_construct_properties,  # Flat array from JS
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

    def _store_imports(self, file_path: str, imports: list, jsx_pass: bool):
        """Store imports/references."""
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] Processing {len(imports)} imports for {file_path}")
        for import_item in imports:
            # Handle dict format (new Python extractors)
            if isinstance(import_item, dict):
                kind = import_item.get('type', 'import')  # 'import' or 'from'
                value = import_item.get('target') or import_item.get('source', '')
                line = import_item.get('line')
            # Handle tuple format (legacy/JS extractors)
            elif len(import_item) == 3:
                kind, value, line = import_item
            else:
                kind, value = import_item
                line = None

            resolved = self._current_extracted.get('resolved_imports', {}).get(value, value)
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG]   Adding ref: {file_path} -> {kind} {resolved} (line {line})")
            self.db_manager.add_ref(file_path, kind, resolved, line)
            self.counts['refs'] += 1

    def _store_routes(self, file_path: str, routes: list, jsx_pass: bool):
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

    def _store_router_mounts(self, file_path: str, router_mounts: list, jsx_pass: bool):
        """Store router mount points (PHASE 6.7 - AST-based route resolution)."""
        for mount in router_mounts:
            if isinstance(mount, dict):
                self.db_manager.add_router_mount(
                    file=mount.get('file', file_path),
                    line=mount.get('line', 0),
                    mount_path_expr=mount.get('mount_path_expr', ''),
                    router_variable=mount.get('router_variable', ''),
                    is_literal=mount.get('is_literal', False)
                )
                if 'router_mounts' not in self.counts:
                    self.counts['router_mounts'] = 0
                self.counts['router_mounts'] += 1

    def _store_express_middleware_chains(self, file_path: str, express_middleware_chains: list, jsx_pass: bool):
        """Store Express middleware chains (PHASE 5).

        Each chain record represents one handler in a route definition's execution order.
        Example: router.post('/', mw1, mw2, controller) creates 3 records.
        """
        for chain in express_middleware_chains:
            if isinstance(chain, dict):
                # Generic batch append - no add method needed, schema-driven
                self.db_manager.generic_batches['express_middleware_chains'].append((
                    file_path,
                    chain.get('route_line'),
                    chain.get('route_path', ''),
                    chain.get('route_method', 'GET'),
                    chain.get('execution_order', 0),
                    chain.get('handler_expr', ''),
                    chain.get('handler_type', 'middleware'),
                    chain.get('handler_file'),  # Future enhancement
                    chain.get('handler_function'),  # Future enhancement
                    chain.get('handler_line')  # Future enhancement
                ))
                if 'express_middleware_chains' not in self.counts:
                    self.counts['express_middleware_chains'] = 0
                self.counts['express_middleware_chains'] += 1

    def _store_sql_objects(self, file_path: str, sql_objects: list, jsx_pass: bool):
        """Store SQL objects."""
        for kind, name in sql_objects:
            self.db_manager.add_sql_object(file_path, kind, name)
            self.counts['sql'] += 1

    def _store_sql_queries(self, file_path: str, sql_queries: list, jsx_pass: bool):
        """Store SQL queries."""
        for query in sql_queries:
            self.db_manager.add_sql_query(
                file_path, query['line'], query['query_text'],
                query['command'], query['tables'],
                query.get('extraction_source', 'code_execute')
            )
            self.counts['sql_queries'] += 1

    def _store_cdk_constructs(self, file_path: str, cdk_constructs: list, jsx_pass: bool):
        """Store CDK constructs (AWS Infrastructure-as-Code)."""
        for construct in cdk_constructs:
            if not isinstance(construct, dict):
                continue
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

    def _store_cdk_construct_properties(self, file_path: str, properties: list, jsx_pass: bool):
        """Store CDK construct properties from flat junction array (JS format).

        JS sends: {construct_line, construct_class, property_name, value_expr, property_line}
        Schema expects: construct_id FK which we reconstruct from file_path + line + class.

        NOTE: construct_name not available in flat format, defaults to 'unnamed'.
        This matches behavior when Python extracts nested properties.
        """
        for prop in properties:
            if not isinstance(prop, dict):
                continue

            # Reconstruct construct_id to match parent record format
            construct_line = prop.get('construct_line', 0)
            construct_class = prop.get('construct_class', '')
            construct_id = f"{file_path}::L{construct_line}::{construct_class}::unnamed"

            self.db_manager.add_cdk_construct_property(
                construct_id=construct_id,
                property_name=prop.get('property_name', ''),
                property_value_expr=prop.get('value_expr', ''),
                line=prop.get('property_line', construct_line)
            )
            self.counts['cdk_construct_properties'] = self.counts.get('cdk_construct_properties', 0) + 1

    def _store_symbols(self, file_path: str, symbols: list, jsx_pass: bool):
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

    def _store_type_annotations(self, file_path: str, type_annotations: list, jsx_pass: bool):
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

    def _store_orm_queries(self, file_path: str, orm_queries: list, jsx_pass: bool):
        """Store ORM queries."""
        for query in orm_queries:
            self.db_manager.add_orm_query(
                file_path, query['line'], query['query_type'],
                query.get('includes'), query.get('has_limit', False),
                query.get('has_transaction', False)
            )
            self.counts['orm'] += 1

    def _store_validation_framework_usage(self, file_path: str, validation_framework_usage: list, jsx_pass: bool):
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

    def _store_assignments(self, file_path: str, assignments: list, jsx_pass: bool):
        """Store data flow information for taint analysis."""
        if assignments:
            logger.info(f"[DEBUG] Found {len(assignments)} assignments in {file_path}")
            if assignments:
                first = assignments[0]
                logger.info(f"[DEBUG] First assignment: line {first.get('line')}, {first.get('target_var')} = {first.get('source_expr', '')[:50]}")

        # CRITICAL: Deduplicate assignments by (file, line, target_var) to avoid UNIQUE constraint violations
        # JavaScript extractors can produce duplicates for complex destructuring patterns
        seen = set()
        deduplicated = []
        for assignment in assignments:
            key = (file_path, assignment['line'], assignment['target_var'])
            if key not in seen:
                seen.add(key)
                deduplicated.append(assignment)
            else:
                logger.debug(f"[DEDUP] Skipping duplicate assignment: {key}")

        if len(deduplicated) < len(assignments):
            logger.info(f"[DEDUP] Removed {len(assignments) - len(deduplicated)} duplicate assignments from {file_path}")

        for assignment in deduplicated:
            if jsx_pass:
                # JSX preserved mode - store to _jsx tables
                self.db_manager.add_assignment_jsx(
                    file_path, assignment['line'], assignment['target_var'],
                    assignment['source_expr'], assignment.get('source_vars', []),
                    assignment['in_function'], assignment.get('property_path'),
                    jsx_mode='preserved', extraction_pass=2
                )
            else:
                # Transform mode - store to main tables
                self.db_manager.add_assignment(
                    file_path, assignment['line'], assignment['target_var'],
                    assignment['source_expr'], assignment.get('source_vars', []),
                    assignment['in_function'], assignment.get('property_path')
                )
                self.counts['assignments'] += 1

    def _store_function_calls(self, file_path: str, function_calls: list, jsx_pass: bool):
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
                    call['argument_expr'], call.get('param_name', ''),
                    jsx_mode='preserved', extraction_pass=2
                )
            else:
                # Transform mode - store to main tables
                # ZERO FALLBACK POLICY: Hard fail on wrong types
                # If these are dicts, the extractor is broken and must be fixed
                callee_file_path = call.get('callee_file_path')
                param_name = call.get('param_name', '')

                # ZERO FALLBACK POLICY: Hard fail on wrong types - no silent skipping
                if isinstance(callee_file_path, dict):
                    raise TypeError(
                        f"EXTRACTION BUG: callee_file_path must be str or None, got dict in {file_path}:{call['line']}. "
                        f"Value: {callee_file_path}. Fix TypeScript extractor (typescript_impl.py)."
                    )

                if isinstance(param_name, dict):
                    raise TypeError(
                        f"EXTRACTION BUG: param_name must be str, got dict in {file_path}:{call['line']}. "
                        f"Callee: {call['callee_function']}. Value: {param_name}. Fix extraction layer."
                    )

                self.db_manager.add_function_call_arg(
                    file_path, call['line'], call['caller_function'],
                    call['callee_function'], call['argument_index'],
                    call['argument_expr'], param_name,
                    callee_file_path=callee_file_path
                )
                self.counts['function_calls'] += 1

    def _store_returns(self, file_path: str, returns: list, jsx_pass: bool):
        """Store return statements."""
        # CRITICAL: Deduplicate function_returns by (file, line, function_name) to avoid UNIQUE constraint violations
        # JavaScript extractors can produce duplicates for complex return patterns
        seen = set()
        deduplicated = []
        for ret in returns:
            key = (file_path, ret['line'], ret['function_name'])
            if key not in seen:
                seen.add(key)
                deduplicated.append(ret)
            else:
                logger.debug(f"[DEDUP] Skipping duplicate function_return: {key}")

        if len(deduplicated) < len(returns):
            logger.info(f"[DEDUP] Removed {len(returns) - len(deduplicated)} duplicate function_returns from {file_path}")

        for ret in deduplicated:
            if jsx_pass:
                # JSX preserved mode - store to _jsx tables
                self.db_manager.add_function_return_jsx(
                    file_path, ret['line'], ret['function_name'],
                    ret['return_expr'], ret.get('return_vars', []),
                    ret.get('has_jsx', False), ret.get('returns_component', False),
                    ret.get('cleanup_operations'),
                    jsx_mode='preserved', extraction_pass=2
                )
            else:
                # Transform mode - store to main tables
                self.db_manager.add_function_return(
                    file_path, ret['line'], ret['function_name'],
                    ret['return_expr'], ret.get('return_vars', [])
                )
                self.counts['returns'] += 1

    def _store_cfg(self, file_path: str, cfg: list, jsx_pass: bool):
        """Store control flow graph data to main or _jsx tables."""
        for function_cfg in cfg:
            if not function_cfg or not isinstance(function_cfg, dict):
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

    def _store_jwt_patterns(self, file_path: str, jwt_patterns: list, jsx_pass: bool):
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

    def _store_react_components(self, file_path: str, react_components: list, jsx_pass: bool):
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

    def _store_class_properties(self, file_path: str, class_properties: list, jsx_pass: bool):
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

    def _store_env_var_usage(self, file_path: str, env_var_usage: list, jsx_pass: bool):
        """Store environment variable usage (process.env.X)."""
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG INDEXER] Found {len(env_var_usage)} env_var_usage for {file_path}")

        # CRITICAL: Deduplicate env_var_usage by (file, line, var_name, access_type) to avoid UNIQUE constraint violations
        # The primary key includes all 4 columns as per security_schema.py
        seen = set()
        deduplicated = []
        for usage in env_var_usage:
            key = (file_path, usage['line'], usage['var_name'], usage['access_type'])
            if key not in seen:
                seen.add(key)
                deduplicated.append(usage)
            else:
                logger.debug(f"[DEDUP] Skipping duplicate env_var_usage: {key}")

        if len(deduplicated) < len(env_var_usage):
            logger.info(f"[DEDUP] Removed {len(env_var_usage) - len(deduplicated)} duplicate env_var_usage entries from {file_path}")

        for usage in deduplicated:
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

    def _store_orm_relationships(self, file_path: str, orm_relationships: list, jsx_pass: bool):
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

    def _store_variable_usage(self, file_path: str, variable_usage: list, jsx_pass: bool):
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

    def _store_object_literals(self, file_path: str, object_literals: list, jsx_pass: bool):
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

    def _store_package_configs(self, file_path: str, package_configs: list, jsx_pass: bool):
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