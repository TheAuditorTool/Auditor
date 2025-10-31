"""Data storage operations for the indexer.

This module contains the DataStorer class that handles all database storage
operations extracted from IndexerOrchestrator._store_extracted_data().

The God Method (1,169 lines) has been split into 66 focused handler methods.
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class DataStorer:
    """Handles all database storage operations via handler dispatch pattern.

    ARCHITECTURE:
    - Single entry point: store(file_path, extracted, jsx_pass)
    - Handler map: data_type -> handler method
    - Each handler: 10-40 lines, focused, testable

    CRITICAL: Assumes db_manager and counts are provided by orchestrator.
    DO NOT instantiate directly - only used by IndexerOrchestrator.
    """

    def __init__(self, db_manager, counts: Dict[str, int]):
        """Initialize DataStorer with database manager and counts dict.

        Args:
            db_manager: DatabaseManager instance from orchestrator
            counts: Shared counts dictionary for statistics tracking
        """
        self.db_manager = db_manager
        self.counts = counts

        # Handler registry - maps data_type to handler method
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
            'python_orm_models': self._store_python_orm_models,
            'python_orm_fields': self._store_python_orm_fields,
            'python_routes': self._store_python_routes,
            'python_blueprints': self._store_python_blueprints,
            'python_django_views': self._store_python_django_views,
            'python_django_forms': self._store_python_django_forms,
            'python_django_form_fields': self._store_python_django_form_fields,
            'python_django_admin': self._store_python_django_admin,
            'python_django_middleware': self._store_python_django_middleware,
            'python_marshmallow_schemas': self._store_python_marshmallow_schemas,
            'python_marshmallow_fields': self._store_python_marshmallow_fields,
            'python_drf_serializers': self._store_python_drf_serializers,
            'python_drf_serializer_fields': self._store_python_drf_serializer_fields,
            'python_wtforms_forms': self._store_python_wtforms_forms,
            'python_wtforms_fields': self._store_python_wtforms_fields,
            'python_celery_tasks': self._store_python_celery_tasks,
            'python_celery_task_calls': self._store_python_celery_task_calls,
            'python_celery_beat_schedules': self._store_python_celery_beat_schedules,
            'python_generators': self._store_python_generators,
            'python_validators': self._store_python_validators,
            'python_decorators': self._store_python_decorators,
            'python_context_managers': self._store_python_context_managers,
            'python_async_functions': self._store_python_async_functions,
            'python_await_expressions': self._store_python_await_expressions,
            'python_async_generators': self._store_python_async_generators,
            'python_pytest_fixtures': self._store_python_pytest_fixtures,
            'python_pytest_parametrize': self._store_python_pytest_parametrize,
            'python_pytest_markers': self._store_python_pytest_markers,
            'python_mock_patterns': self._store_python_mock_patterns,
            'python_protocols': self._store_python_protocols,
            'python_generics': self._store_python_generics,
            'python_typed_dicts': self._store_python_typed_dicts,
            'python_literals': self._store_python_literals,
            'python_overloads': self._store_python_overloads,
            'react_hooks': self._store_react_hooks,
            'vue_components': self._store_vue_components,
            'vue_hooks': self._store_vue_hooks,
            'vue_directives': self._store_vue_directives,
            'vue_provide_inject': self._store_vue_provide_inject,
            'variable_usage': self._store_variable_usage,
            'object_literals': self._store_object_literals,
            'package_configs': self._store_package_configs,
            'lock_analysis': self._store_lock_analysis,
            'import_styles': self._store_import_styles,
            'terraform_file': self._store_terraform_file,
            'terraform_resources': self._store_terraform_resources,
            'terraform_variables': self._store_terraform_variables,
            'terraform_variable_values': self._store_terraform_variable_values,
            'terraform_outputs': self._store_terraform_outputs,
        }

    def store(self, file_path: str, extracted: Dict[str, Any], jsx_pass: bool = False):
        """Single entry point for all storage operations.

        Args:
            file_path: Path to source file
            extracted: Dictionary of extracted data from extractor
            jsx_pass: True if this is JSX preserved mode pass
        """
        # Store extracted for handlers that need cross-cutting data (e.g., resolved_imports)
        self._current_extracted = extracted

        # JSX pass ONLY processes these 5 data types (to avoid duplicates)
        # cfg is included so handler can explicitly skip it
        jsx_only_types = {'symbols', 'assignments', 'function_calls', 'returns', 'cfg'}

        for data_type, data in extracted.items():
            # Skip non-JSX data types during JSX pass to prevent duplicates
            if jsx_pass and data_type not in jsx_only_types:
                continue

            handler = self.handlers.get(data_type)
            if handler:
                handler(file_path, data, jsx_pass)
            else:
                # Unknown data type - log but don't crash
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] No handler for data type: {data_type}")

    # ========================================================================
    # HANDLER METHODS - Migrated from __init__.py _store_extracted_data()
    # ========================================================================

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
                self.db_manager.add_function_call_arg(
                    file_path, call['line'], call['caller_function'],
                    call['callee_function'], call['argument_index'],
                    call['argument_expr'], call['param_name'],
                    callee_file_path=call.get('callee_file_path')
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

    def _store_python_orm_models(self, file_path: str, python_orm_models: List, jsx_pass: bool):
        """Store Python ORM models."""
        for model in python_orm_models:
            self.db_manager.add_python_orm_model(
                file_path,
                model.get('line', 0),
                model.get('model_name', ''),
                model.get('table_name'),
                model.get('orm_type', 'sqlalchemy')
            )
            if 'python_orm_models' not in self.counts:
                self.counts['python_orm_models'] = 0
            self.counts['python_orm_models'] += 1

    def _store_python_orm_fields(self, file_path: str, python_orm_fields: List, jsx_pass: bool):
        """Store Python ORM fields."""
        for field in python_orm_fields:
            self.db_manager.add_python_orm_field(
                file_path,
                field.get('line', 0),
                field.get('model_name', ''),
                field.get('field_name', ''),
                field.get('field_type'),
                field.get('is_primary_key', False),
                field.get('is_foreign_key', False),
                field.get('foreign_key_target')
            )
            if 'python_orm_fields' not in self.counts:
                self.counts['python_orm_fields'] = 0
            self.counts['python_orm_fields'] += 1

    def _store_python_routes(self, file_path: str, python_routes: List, jsx_pass: bool):
        """Store Python routes."""
        for route in python_routes:
            self.db_manager.add_python_route(
                file_path,
                route.get('line'),
                route.get('framework', ''),
                route.get('method', ''),
                route.get('pattern', ''),
                route.get('handler_function', ''),
                route.get('has_auth', False),
                route.get('dependencies'),
                route.get('blueprint')
            )
            if 'python_routes' not in self.counts:
                self.counts['python_routes'] = 0
            self.counts['python_routes'] += 1

    def _store_python_blueprints(self, file_path: str, python_blueprints: List, jsx_pass: bool):
        """Store Python blueprints."""
        for blueprint in python_blueprints:
            self.db_manager.add_python_blueprint(
                file_path,
                blueprint.get('line'),
                blueprint.get('blueprint_name', ''),
                blueprint.get('url_prefix'),
                blueprint.get('subdomain')
            )
            if 'python_blueprints' not in self.counts:
                self.counts['python_blueprints'] = 0
            self.counts['python_blueprints'] += 1

    def _store_python_django_views(self, file_path: str, python_django_views: List, jsx_pass: bool):
        """Store Python Django views."""
        for django_view in python_django_views:
            self.db_manager.add_python_django_view(
                file_path,
                django_view.get('line', 0),
                django_view.get('view_class_name', ''),
                django_view.get('view_type', ''),
                django_view.get('base_view_class'),
                django_view.get('model_name'),
                django_view.get('template_name'),
                django_view.get('has_permission_check', False),
                django_view.get('http_method_names'),
                django_view.get('has_get_queryset_override', False)
            )
            if 'python_django_views' not in self.counts:
                self.counts['python_django_views'] = 0
            self.counts['python_django_views'] += 1

    def _store_python_django_forms(self, file_path: str, python_django_forms: List, jsx_pass: bool):
        """Store Python Django forms."""
        for django_form in python_django_forms:
            self.db_manager.add_python_django_form(
                file_path,
                django_form.get('line', 0),
                django_form.get('form_class_name', ''),
                django_form.get('is_model_form', False),
                django_form.get('model_name'),
                django_form.get('field_count', 0),
                django_form.get('has_custom_clean', False)
            )
            if 'python_django_forms' not in self.counts:
                self.counts['python_django_forms'] = 0
            self.counts['python_django_forms'] += 1

    def _store_python_django_form_fields(self, file_path: str, python_django_form_fields: List, jsx_pass: bool):
        """Store Python Django form fields."""
        for form_field in python_django_form_fields:
            self.db_manager.add_python_django_form_field(
                file_path,
                form_field.get('line', 0),
                form_field.get('form_class_name', ''),
                form_field.get('field_name', ''),
                form_field.get('field_type', ''),
                form_field.get('required', True),
                form_field.get('max_length'),
                form_field.get('has_custom_validator', False)
            )
            if 'python_django_form_fields' not in self.counts:
                self.counts['python_django_form_fields'] = 0
            self.counts['python_django_form_fields'] += 1

    def _store_python_django_admin(self, file_path: str, python_django_admin: List, jsx_pass: bool):
        """Store Python Django admin."""
        for django_admin in python_django_admin:
            self.db_manager.add_python_django_admin(
                file_path,
                django_admin.get('line', 0),
                django_admin.get('admin_class_name', ''),
                django_admin.get('model_name'),
                django_admin.get('list_display'),
                django_admin.get('list_filter'),
                django_admin.get('search_fields'),
                django_admin.get('readonly_fields'),
                django_admin.get('has_custom_actions', False)
            )
            if 'python_django_admin' not in self.counts:
                self.counts['python_django_admin'] = 0
            self.counts['python_django_admin'] += 1

    def _store_python_django_middleware(self, file_path: str, python_django_middleware: List, jsx_pass: bool):
        """Store Python Django middleware."""
        for django_middleware in python_django_middleware:
            self.db_manager.add_python_django_middleware(
                file_path,
                django_middleware.get('line', 0),
                django_middleware.get('middleware_class_name', ''),
                django_middleware.get('has_process_request', False),
                django_middleware.get('has_process_response', False),
                django_middleware.get('has_process_exception', False),
                django_middleware.get('has_process_view', False),
                django_middleware.get('has_process_template_response', False)
            )
            if 'python_django_middleware' not in self.counts:
                self.counts['python_django_middleware'] = 0
            self.counts['python_django_middleware'] += 1

    def _store_python_marshmallow_schemas(self, file_path: str, python_marshmallow_schemas: List, jsx_pass: bool):
        """Store Python Marshmallow schemas."""
        for marshmallow_schema in python_marshmallow_schemas:
            self.db_manager.add_python_marshmallow_schema(
                file_path,
                marshmallow_schema.get('line', 0),
                marshmallow_schema.get('schema_class_name', ''),
                marshmallow_schema.get('field_count', 0),
                marshmallow_schema.get('has_nested_schemas', False),
                marshmallow_schema.get('has_custom_validators', False)
            )
            if 'python_marshmallow_schemas' not in self.counts:
                self.counts['python_marshmallow_schemas'] = 0
            self.counts['python_marshmallow_schemas'] += 1

    def _store_python_marshmallow_fields(self, file_path: str, python_marshmallow_fields: List, jsx_pass: bool):
        """Store Python Marshmallow fields."""
        for marshmallow_field in python_marshmallow_fields:
            self.db_manager.add_python_marshmallow_field(
                file_path,
                marshmallow_field.get('line', 0),
                marshmallow_field.get('schema_class_name', ''),
                marshmallow_field.get('field_name', ''),
                marshmallow_field.get('field_type', ''),
                marshmallow_field.get('required', False),
                marshmallow_field.get('allow_none', False),
                marshmallow_field.get('has_validate', False),
                marshmallow_field.get('has_custom_validator', False)
            )
            if 'python_marshmallow_fields' not in self.counts:
                self.counts['python_marshmallow_fields'] = 0
            self.counts['python_marshmallow_fields'] += 1

    def _store_python_drf_serializers(self, file_path: str, python_drf_serializers: List, jsx_pass: bool):
        """Store Python DRF serializers."""
        for drf_serializer in python_drf_serializers:
            self.db_manager.add_python_drf_serializer(
                file_path,
                drf_serializer.get('line', 0),
                drf_serializer.get('serializer_class_name', ''),
                drf_serializer.get('field_count', 0),
                drf_serializer.get('is_model_serializer', False),
                drf_serializer.get('has_meta_model', False),
                drf_serializer.get('has_read_only_fields', False),
                drf_serializer.get('has_custom_validators', False)
            )
            if 'python_drf_serializers' not in self.counts:
                self.counts['python_drf_serializers'] = 0
            self.counts['python_drf_serializers'] += 1

    def _store_python_drf_serializer_fields(self, file_path: str, python_drf_serializer_fields: List, jsx_pass: bool):
        """Store Python DRF serializer fields."""
        for drf_field in python_drf_serializer_fields:
            self.db_manager.add_python_drf_serializer_field(
                file_path,
                drf_field.get('line', 0),
                drf_field.get('serializer_class_name', ''),
                drf_field.get('field_name', ''),
                drf_field.get('field_type', ''),
                drf_field.get('read_only', False),
                drf_field.get('write_only', False),
                drf_field.get('required', False),
                drf_field.get('allow_null', False),
                drf_field.get('has_source', False),
                drf_field.get('has_custom_validator', False)
            )
            if 'python_drf_serializer_fields' not in self.counts:
                self.counts['python_drf_serializer_fields'] = 0
            self.counts['python_drf_serializer_fields'] += 1

    def _store_python_wtforms_forms(self, file_path: str, python_wtforms_forms: List, jsx_pass: bool):
        """Store Python WTForms forms."""
        for wtforms_form in python_wtforms_forms:
            self.db_manager.add_python_wtforms_form(
                file_path,
                wtforms_form.get('line', 0),
                wtforms_form.get('form_class_name', ''),
                wtforms_form.get('field_count', 0),
                wtforms_form.get('has_custom_validators', False)
            )
            if 'python_wtforms_forms' not in self.counts:
                self.counts['python_wtforms_forms'] = 0
            self.counts['python_wtforms_forms'] += 1

    def _store_python_wtforms_fields(self, file_path: str, python_wtforms_fields: List, jsx_pass: bool):
        """Store Python WTForms fields."""
        for wtforms_field in python_wtforms_fields:
            self.db_manager.add_python_wtforms_field(
                file_path,
                wtforms_field.get('line', 0),
                wtforms_field.get('form_class_name', ''),
                wtforms_field.get('field_name', ''),
                wtforms_field.get('field_type', ''),
                wtforms_field.get('has_validators', False),
                wtforms_field.get('has_custom_validator', False)
            )
            if 'python_wtforms_fields' not in self.counts:
                self.counts['python_wtforms_fields'] = 0
            self.counts['python_wtforms_fields'] += 1

    def _store_python_celery_tasks(self, file_path: str, python_celery_tasks: List, jsx_pass: bool):
        """Store Python Celery tasks."""
        for celery_task in python_celery_tasks:
            self.db_manager.add_python_celery_task(
                file_path,
                celery_task.get('line', 0),
                celery_task.get('task_name', ''),
                celery_task.get('decorator_name', 'task'),
                celery_task.get('arg_count', 0),
                celery_task.get('bind', False),
                celery_task.get('serializer'),
                celery_task.get('max_retries'),
                celery_task.get('rate_limit'),
                celery_task.get('time_limit'),
                celery_task.get('queue')
            )
            if 'python_celery_tasks' not in self.counts:
                self.counts['python_celery_tasks'] = 0
            self.counts['python_celery_tasks'] += 1

    def _store_python_celery_task_calls(self, file_path: str, python_celery_task_calls: List, jsx_pass: bool):
        """Store Python Celery task calls."""
        for task_call in python_celery_task_calls:
            self.db_manager.add_python_celery_task_call(
                file_path,
                task_call.get('line', 0),
                task_call.get('caller_function', '<module>'),
                task_call.get('task_name', ''),
                task_call.get('invocation_type', 'delay'),
                task_call.get('arg_count', 0),
                task_call.get('has_countdown', False),
                task_call.get('has_eta', False),
                task_call.get('queue_override')
            )
            if 'python_celery_task_calls' not in self.counts:
                self.counts['python_celery_task_calls'] = 0
            self.counts['python_celery_task_calls'] += 1

    def _store_python_celery_beat_schedules(self, file_path: str, python_celery_beat_schedules: List, jsx_pass: bool):
        """Store Python Celery beat schedules."""
        for beat_schedule in python_celery_beat_schedules:
            self.db_manager.add_python_celery_beat_schedule(
                file_path,
                beat_schedule.get('line', 0),
                beat_schedule.get('schedule_name', ''),
                beat_schedule.get('task_name', ''),
                beat_schedule.get('schedule_type', 'unknown'),
                beat_schedule.get('schedule_expression'),
                beat_schedule.get('args'),
                beat_schedule.get('kwargs')
            )
            if 'python_celery_beat_schedules' not in self.counts:
                self.counts['python_celery_beat_schedules'] = 0
            self.counts['python_celery_beat_schedules'] += 1

    def _store_python_generators(self, file_path: str, python_generators: List, jsx_pass: bool):
        """Store Python generators."""
        for generator in python_generators:
            self.db_manager.add_python_generator(
                file_path,
                generator.get('line', 0),
                generator.get('generator_type', 'function'),
                generator.get('name', ''),
                generator.get('yield_count', 0),
                generator.get('has_yield_from', False),
                generator.get('has_send', False),
                generator.get('is_infinite', False)
            )
            if 'python_generators' not in self.counts:
                self.counts['python_generators'] = 0
            self.counts['python_generators'] += 1

    def _store_python_validators(self, file_path: str, python_validators: List, jsx_pass: bool):
        """Store Python validators."""
        for validator in python_validators:
            self.db_manager.add_python_validator(
                file_path,
                validator.get('line', 0),
                validator.get('model_name', ''),
                validator.get('field_name'),
                validator.get('validator_method', ''),
                validator.get('validator_type', '')
            )
            if 'python_validators' not in self.counts:
                self.counts['python_validators'] = 0
            self.counts['python_validators'] += 1

    def _store_python_decorators(self, file_path: str, python_decorators: List, jsx_pass: bool):
        """Store Python decorators."""
        for decorator in python_decorators:
            self.db_manager.add_python_decorator(
                file_path,
                decorator.get('line', 0),
                decorator.get('decorator_name', ''),
                decorator.get('decorator_type', ''),
                decorator.get('target_type', ''),
                decorator.get('target_name', ''),
                decorator.get('is_async', False)
            )
            if 'python_decorators' not in self.counts:
                self.counts['python_decorators'] = 0
            self.counts['python_decorators'] += 1

    def _store_python_context_managers(self, file_path: str, python_context_managers: List, jsx_pass: bool):
        """Store Python context managers."""
        for ctx_mgr in python_context_managers:
            self.db_manager.add_python_context_manager(
                file_path,
                ctx_mgr.get('line', 0),
                ctx_mgr.get('context_type', ''),
                ctx_mgr.get('context_expr'),
                ctx_mgr.get('as_name'),
                ctx_mgr.get('is_async', False),
                ctx_mgr.get('is_custom', False)
            )
            if 'python_context_managers' not in self.counts:
                self.counts['python_context_managers'] = 0
            self.counts['python_context_managers'] += 1

    def _store_python_async_functions(self, file_path: str, python_async_functions: List, jsx_pass: bool):
        """Store Python async functions."""
        for async_func in python_async_functions:
            self.db_manager.add_python_async_function(
                file_path,
                async_func.get('line', 0),
                async_func.get('function_name', ''),
                async_func.get('has_await', False),
                async_func.get('await_count', 0),
                async_func.get('has_async_with', False),
                async_func.get('has_async_for', False)
            )
            if 'python_async_functions' not in self.counts:
                self.counts['python_async_functions'] = 0
            self.counts['python_async_functions'] += 1

    def _store_python_await_expressions(self, file_path: str, python_await_expressions: List, jsx_pass: bool):
        """Store Python await expressions."""
        for await_expr in python_await_expressions:
            self.db_manager.add_python_await_expression(
                file_path,
                await_expr.get('line', 0),
                await_expr.get('await_expr', ''),
                await_expr.get('containing_function')
            )
            if 'python_await_expressions' not in self.counts:
                self.counts['python_await_expressions'] = 0
            self.counts['python_await_expressions'] += 1

    def _store_python_async_generators(self, file_path: str, python_async_generators: List, jsx_pass: bool):
        """Store Python async generators."""
        for async_gen in python_async_generators:
            target_vars = async_gen.get('target_vars')
            if isinstance(target_vars, list):
                target_vars = json.dumps(target_vars)

            self.db_manager.add_python_async_generator(
                file_path,
                async_gen.get('line', 0),
                async_gen.get('generator_type', ''),
                target_vars,
                async_gen.get('iterable_expr'),
                async_gen.get('function_name')
            )
            if 'python_async_generators' not in self.counts:
                self.counts['python_async_generators'] = 0
            self.counts['python_async_generators'] += 1

    def _store_python_pytest_fixtures(self, file_path: str, python_pytest_fixtures: List, jsx_pass: bool):
        """Store Python pytest fixtures."""
        for fixture in python_pytest_fixtures:
            self.db_manager.add_python_pytest_fixture(
                file_path,
                fixture.get('line', 0),
                fixture.get('fixture_name', ''),
                fixture.get('scope', 'function'),
                fixture.get('has_autouse', False),
                fixture.get('has_params', False)
            )
            if 'python_pytest_fixtures' not in self.counts:
                self.counts['python_pytest_fixtures'] = 0
            self.counts['python_pytest_fixtures'] += 1

    def _store_python_pytest_parametrize(self, file_path: str, python_pytest_parametrize: List, jsx_pass: bool):
        """Store Python pytest parametrize."""
        for parametrize in python_pytest_parametrize:
            param_names = parametrize.get('parameter_names', [])
            if isinstance(param_names, list):
                param_names = json.dumps(param_names)

            self.db_manager.add_python_pytest_parametrize(
                file_path,
                parametrize.get('line', 0),
                parametrize.get('test_function', ''),
                param_names,
                parametrize.get('argvalues_count', 0)
            )
            if 'python_pytest_parametrize' not in self.counts:
                self.counts['python_pytest_parametrize'] = 0
            self.counts['python_pytest_parametrize'] += 1

    def _store_python_pytest_markers(self, file_path: str, python_pytest_markers: List, jsx_pass: bool):
        """Store Python pytest markers."""
        for marker in python_pytest_markers:
            marker_args = marker.get('marker_args', [])
            if isinstance(marker_args, list):
                marker_args = json.dumps(marker_args)

            self.db_manager.add_python_pytest_marker(
                file_path,
                marker.get('line', 0),
                marker.get('test_function', ''),
                marker.get('marker_name', ''),
                marker_args
            )
            if 'python_pytest_markers' not in self.counts:
                self.counts['python_pytest_markers'] = 0
            self.counts['python_pytest_markers'] += 1

    def _store_python_mock_patterns(self, file_path: str, python_mock_patterns: List, jsx_pass: bool):
        """Store Python mock patterns."""
        for mock in python_mock_patterns:
            self.db_manager.add_python_mock_pattern(
                file_path,
                mock.get('line', 0),
                mock.get('mock_type', ''),
                mock.get('target'),
                mock.get('in_function'),
                mock.get('is_decorator', False)
            )
            if 'python_mock_patterns' not in self.counts:
                self.counts['python_mock_patterns'] = 0
            self.counts['python_mock_patterns'] += 1

    def _store_python_protocols(self, file_path: str, python_protocols: List, jsx_pass: bool):
        """Store Python protocols."""
        for protocol in python_protocols:
            methods = protocol.get('methods', [])
            if isinstance(methods, list):
                methods = json.dumps(methods)

            self.db_manager.add_python_protocol(
                file_path,
                protocol.get('line', 0),
                protocol.get('protocol_name', ''),
                methods,
                protocol.get('is_runtime_checkable', False)
            )
            if 'python_protocols' not in self.counts:
                self.counts['python_protocols'] = 0
            self.counts['python_protocols'] += 1

    def _store_python_generics(self, file_path: str, python_generics: List, jsx_pass: bool):
        """Store Python generics."""
        for generic in python_generics:
            type_params = generic.get('type_params', [])
            if isinstance(type_params, list):
                type_params = json.dumps(type_params)

            self.db_manager.add_python_generic(
                file_path,
                generic.get('line', 0),
                generic.get('class_name', ''),
                type_params
            )
            if 'python_generics' not in self.counts:
                self.counts['python_generics'] = 0
            self.counts['python_generics'] += 1

    def _store_python_typed_dicts(self, file_path: str, python_typed_dicts: List, jsx_pass: bool):
        """Store Python typed dicts."""
        for typed_dict in python_typed_dicts:
            fields = typed_dict.get('fields', [])
            if isinstance(fields, list):
                fields = json.dumps(fields)

            self.db_manager.add_python_typed_dict(
                file_path,
                typed_dict.get('line', 0),
                typed_dict.get('typeddict_name', ''),
                fields
            )
            if 'python_typed_dicts' not in self.counts:
                self.counts['python_typed_dicts'] = 0
            self.counts['python_typed_dicts'] += 1

    def _store_python_literals(self, file_path: str, python_literals: List, jsx_pass: bool):
        """Store Python literals."""
        for literal in python_literals:
            name = literal.get('parameter_name') or literal.get('function_name') or literal.get('variable_name')

            self.db_manager.add_python_literal(
                file_path,
                literal.get('line', 0),
                literal.get('usage_context', ''),
                name,
                literal.get('literal_type', '')
            )
            if 'python_literals' not in self.counts:
                self.counts['python_literals'] = 0
            self.counts['python_literals'] += 1

    def _store_python_overloads(self, file_path: str, python_overloads: List, jsx_pass: bool):
        """Store Python overloads."""
        for overload in python_overloads:
            variants = overload.get('variants', [])
            if isinstance(variants, list):
                variants = json.dumps(variants)

            self.db_manager.add_python_overload(
                file_path,
                overload.get('function_name', ''),
                overload.get('overload_count', 0),
                variants
            )
            if 'python_overloads' not in self.counts:
                self.counts['python_overloads'] = 0
            self.counts['python_overloads'] += 1

    def _store_react_hooks(self, file_path: str, react_hooks: List, jsx_pass: bool):
        """Store React hooks."""
        for hook in react_hooks:
            self.db_manager.add_react_hook(
                file_path,
                hook['line'],
                hook['component_name'],
                hook['hook_name'],
                hook.get('dependency_array'),
                hook.get('dependency_vars'),
                hook.get('callback_body'),
                hook.get('has_cleanup', False),
                hook.get('cleanup_type')
            )
            self.counts['react_hooks'] += 1

    def _store_vue_components(self, file_path: str, vue_components: List, jsx_pass: bool):
        """Store Vue-specific data."""
        for component in vue_components:
            self.db_manager.add_vue_component(
                file_path,
                component['name'],
                component['type'],
                component['start_line'],
                component['end_line'],
                component.get('has_template', False),
                component.get('has_style', False),
                component.get('composition_api_used', False),
                component.get('props_definition'),
                component.get('emits_definition'),
                component.get('setup_return')
            )
            if 'vue_components' not in self.counts:
                self.counts['vue_components'] = 0
            self.counts['vue_components'] += 1

    def _store_vue_hooks(self, file_path: str, vue_hooks: List, jsx_pass: bool):
        """Store Vue hooks."""
        for hook in vue_hooks:
            self.db_manager.add_vue_hook(
                file_path,
                hook['line'],
                hook['component_name'],
                hook['hook_name'],
                hook.get('hook_type', 'unknown'),
                hook.get('dependencies'),
                hook.get('return_value'),
                hook.get('is_async', False)
            )
            if 'vue_hooks' not in self.counts:
                self.counts['vue_hooks'] = 0
            self.counts['vue_hooks'] += 1

    def _store_vue_directives(self, file_path: str, vue_directives: List, jsx_pass: bool):
        """Store Vue directives."""
        for directive in vue_directives:
            self.db_manager.add_vue_directive(
                file_path,
                directive['line'],
                directive['directive_name'],
                directive.get('value_expr', ''),
                directive.get('in_component', 'global'),
                directive.get('is_dynamic', False),
                directive.get('modifiers')
            )
            if 'vue_directives' not in self.counts:
                self.counts['vue_directives'] = 0
            self.counts['vue_directives'] += 1

    def _store_vue_provide_inject(self, file_path: str, vue_provide_inject: List, jsx_pass: bool):
        """Store Vue provide/inject."""
        for pi in vue_provide_inject:
            self.db_manager.add_vue_provide_inject(
                file_path,
                pi['line'],
                pi['component_name'],
                pi.get('operation_type', 'unknown'),
                pi.get('key_name', ''),
                pi.get('value_expr'),
                pi.get('is_reactive', False)
            )

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

    def _store_lock_analysis(self, file_path: str, lock_analysis: List, jsx_pass: bool):
        """Store lock analysis."""
        for lock in lock_analysis:
            self.db_manager.add_lock_analysis(
                lock['file_path'],
                lock['lock_type'],
                lock.get('package_manager_version'),
                lock['total_packages'],
                lock.get('duplicate_packages'),
                lock.get('lock_file_version')
            )
            if 'lock_analysis' not in self.counts:
                self.counts['lock_analysis'] = 0
            self.counts['lock_analysis'] += 1

    def _store_import_styles(self, file_path: str, import_styles: List, jsx_pass: bool):
        """Store import styles."""
        for import_style in import_styles:
            self.db_manager.add_import_style(
                file_path,
                import_style['line'],
                import_style['package'],
                import_style['import_style'],
                import_style.get('imported_names'),
                import_style.get('alias_name'),
                import_style.get('full_statement')
            )
            if 'import_styles' not in self.counts:
                self.counts['import_styles'] = 0
            self.counts['import_styles'] += 1

    def _store_terraform_file(self, file_path: str, terraform_file: Dict, jsx_pass: bool):
        """Store Terraform infrastructure definitions."""
        self.db_manager.add_terraform_file(
            file_path=terraform_file['file_path'],
            module_name=terraform_file.get('module_name'),
            stack_name=terraform_file.get('stack_name'),
            backend_type=terraform_file.get('backend_type'),
            providers_json=terraform_file.get('providers_json'),
            is_module=terraform_file.get('is_module', False),
            module_source=terraform_file.get('module_source')
        )
        if 'terraform_files' not in self.counts:
            self.counts['terraform_files'] = 0
        self.counts['terraform_files'] += 1

    def _store_terraform_resources(self, file_path: str, terraform_resources: List, jsx_pass: bool):
        """Store Terraform resources."""
        for resource in terraform_resources:
            self.db_manager.add_terraform_resource(
                resource_id=resource['resource_id'],
                file_path=resource['file_path'],
                resource_type=resource['resource_type'],
                resource_name=resource['resource_name'],
                module_path=resource.get('module_path'),
                properties_json=json.dumps(resource.get('properties', {})),
                depends_on_json=json.dumps(resource.get('depends_on', [])),
                sensitive_flags_json=json.dumps(resource.get('sensitive_properties', [])),
                has_public_exposure=resource.get('has_public_exposure', False),
                line=resource.get('line')
            )
            if 'terraform_resources' not in self.counts:
                self.counts['terraform_resources'] = 0
            self.counts['terraform_resources'] += 1

    def _store_terraform_variables(self, file_path: str, terraform_variables: List, jsx_pass: bool):
        """Store Terraform variables."""
        for variable in terraform_variables:
            self.db_manager.add_terraform_variable(
                variable_id=variable['variable_id'],
                file_path=variable['file_path'],
                variable_name=variable['variable_name'],
                variable_type=variable.get('variable_type'),
                default_json=json.dumps(variable.get('default')) if variable.get('default') is not None else None,
                is_sensitive=variable.get('is_sensitive', False),
                description=variable.get('description', ''),
                source_file=variable.get('source_file'),
                line=variable.get('line')
            )
            if 'terraform_variables' not in self.counts:
                self.counts['terraform_variables'] = 0
            self.counts['terraform_variables'] += 1

    def _store_terraform_variable_values(self, file_path: str, terraform_variable_values: List, jsx_pass: bool):
        """Store Terraform variable values."""
        for value in terraform_variable_values:
            raw_value = value.get('variable_value')
            value_json = value.get('variable_value_json')
            if value_json is None and raw_value is not None:
                try:
                    value_json = json.dumps(raw_value)
                except TypeError:
                    value_json = json.dumps(str(raw_value))

            self.db_manager.add_terraform_variable_value(
                file_path=value['file_path'],
                variable_name=value['variable_name'],
                variable_value_json=value_json,
                line=value.get('line'),
                is_sensitive_context=value.get('is_sensitive_context', False)
            )
            if 'terraform_variable_values' not in self.counts:
                self.counts['terraform_variable_values'] = 0
            self.counts['terraform_variable_values'] += 1

    def _store_terraform_outputs(self, file_path: str, terraform_outputs: List, jsx_pass: bool):
        """Store Terraform outputs."""
        for output in terraform_outputs:
            self.db_manager.add_terraform_output(
                output_id=output['output_id'],
                file_path=output['file_path'],
                output_name=output['output_name'],
                value_json=json.dumps(output.get('value')) if output.get('value') is not None else None,
                is_sensitive=output.get('is_sensitive', False),
                description=output.get('description', ''),
                line=output.get('line')
            )
            if 'terraform_outputs' not in self.counts:
                self.counts['terraform_outputs'] = 0
            self.counts['terraform_outputs'] += 1
