"""Python storage handlers for framework-specific patterns.

This module contains handlers for Python frameworks and patterns:
- ORM: sqlalchemy, django models, fields
- HTTP: flask routes, django views
- Validation: pydantic validators
- Decorators: general Python decorators
- Django: views, middleware
- Consolidated tables: loops, branches, security, testing, etc.

HISTORY:
- 2025-11-25: Reduced from 148 handlers to 7 (consolidate-python-orphan-tables)
- 2025-11-25: Added 20 handlers for consolidated tables (wire-extractors-to-consolidated-schema)

Note: python_package_configs is stored via generic_batches in python_database.py,
not here - that's why we have 7 original handlers for 8 Python tables.

Handler Count: 27 (7 original + 20 consolidated)
"""


import json
import os
import sys
from typing import List, Dict, Any
from .base import BaseStorage


class PythonStorage(BaseStorage):
    """Python-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            # ===== ORIGINAL 7 HANDLERS =====
            # ORM - consumers: overfetch.py, discovery.py, schema_cache_adapter.py
            'python_orm_models': self._store_python_orm_models,
            'python_orm_fields': self._store_python_orm_fields,

            # Routes - consumers: boundary_analyzer.py, deadcode_graph.py, query.py
            'python_routes': self._store_python_routes,

            # Validators - consumers: discovery.py (via SchemaMemoryCache)
            'python_validators': self._store_python_validators,

            # Decorators - consumers: interceptors.py, deadcode_graph.py, query.py
            'python_decorators': self._store_python_decorators,

            # Django - consumers: interceptors.py
            'python_django_views': self._store_python_django_views,
            'python_django_middleware': self._store_python_django_middleware,

            # ===== CONSOLIDATED TABLES - 20 HANDLERS =====
            # Group 1: Control & Data Flow
            'python_loops': self._store_python_loops,
            'python_branches': self._store_python_branches,
            'python_functions_advanced': self._store_python_functions_advanced,
            'python_io_operations': self._store_python_io_operations,
            'python_state_mutations': self._store_python_state_mutations,

            # Group 2: Object-Oriented & Types
            'python_class_features': self._store_python_class_features,
            'python_protocols': self._store_python_protocols,
            'python_descriptors': self._store_python_descriptors,
            'python_type_definitions': self._store_python_type_definitions,
            'python_literals': self._store_python_literals,

            # Group 3: Security & Testing
            'python_security_findings': self._store_python_security_findings,
            'python_test_cases': self._store_python_test_cases,
            'python_test_fixtures': self._store_python_test_fixtures,
            'python_framework_config': self._store_python_framework_config,
            'python_validation_schemas': self._store_python_validation_schemas,

            # Group 4: Low-Level & Misc
            'python_operators': self._store_python_operators,
            'python_collections': self._store_python_collections,
            'python_stdlib_usage': self._store_python_stdlib_usage,
            'python_imports_advanced': self._store_python_imports_advanced,
            'python_expressions': self._store_python_expressions,
        }

    def _store_python_orm_models(self, file_path: str, python_orm_models: list, jsx_pass: bool):
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

    def _store_python_orm_fields(self, file_path: str, python_orm_fields: list, jsx_pass: bool):
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

    def _store_python_routes(self, file_path: str, python_routes: list, jsx_pass: bool):
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

    def _store_python_validators(self, file_path: str, python_validators: list, jsx_pass: bool):
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

    def _store_python_decorators(self, file_path: str, python_decorators: list, jsx_pass: bool):
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

    def _store_python_django_views(self, file_path: str, python_django_views: list, jsx_pass: bool):
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

    def _store_python_django_middleware(self, file_path: str, python_django_middleware: list, jsx_pass: bool):
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

    # =========================================================================
    # CONSOLIDATED TABLES - Group 1: Control & Data Flow (5 handlers)
    # =========================================================================

    def _store_python_loops(self, file_path: str, python_loops: list, jsx_pass: bool):
        """Store Python loops (for/while/async for)."""
        for loop in python_loops:
            self.db_manager.add_python_loop(
                file_path,
                loop.get('line', 0),
                loop.get('loop_type', ''),
                loop.get('target'),
                loop.get('iterator'),
                loop.get('has_else', False),
                loop.get('nesting_level', 0),
                loop.get('body_line_count')
            )
            if 'python_loops' not in self.counts:
                self.counts['python_loops'] = 0
            self.counts['python_loops'] += 1

    def _store_python_branches(self, file_path: str, python_branches: list, jsx_pass: bool):
        """Store Python branches (if/match/try/except/finally/raise)."""
        for branch in python_branches:
            self.db_manager.add_python_branch(
                file_path,
                branch.get('line', 0),
                branch.get('branch_type', ''),
                branch.get('condition'),
                branch.get('has_else', False),
                branch.get('elif_count', 0),
                branch.get('case_count', 0),
                branch.get('exception_type')
            )
            if 'python_branches' not in self.counts:
                self.counts['python_branches'] = 0
            self.counts['python_branches'] += 1

    def _store_python_functions_advanced(self, file_path: str, python_functions_advanced: list, jsx_pass: bool):
        """Store advanced Python function patterns (async/generator/lambda/context_manager)."""
        for func in python_functions_advanced:
            self.db_manager.add_python_function_advanced(
                file_path,
                func.get('line', 0),
                func.get('function_type', ''),
                func.get('name'),
                func.get('is_method', False),
                func.get('yield_count', 0),
                func.get('await_count', 0)
            )
            if 'python_functions_advanced' not in self.counts:
                self.counts['python_functions_advanced'] = 0
            self.counts['python_functions_advanced'] += 1

    def _store_python_io_operations(self, file_path: str, python_io_operations: list, jsx_pass: bool):
        """Store Python I/O operations (file/network/database/process)."""
        for io_op in python_io_operations:
            self.db_manager.add_python_io_operation(
                file_path,
                io_op.get('line', 0),
                io_op.get('io_type', ''),
                io_op.get('operation'),
                io_op.get('target'),
                io_op.get('is_taint_source', False),
                io_op.get('is_taint_sink', False)
            )
            if 'python_io_operations' not in self.counts:
                self.counts['python_io_operations'] = 0
            self.counts['python_io_operations'] += 1

    def _store_python_state_mutations(self, file_path: str, python_state_mutations: list, jsx_pass: bool):
        """Store Python state mutations (instance/class/global/argument/augmented)."""
        for mutation in python_state_mutations:
            self.db_manager.add_python_state_mutation(
                file_path,
                mutation.get('line', 0),
                mutation.get('mutation_type', ''),
                mutation.get('target'),
                mutation.get('operator'),
                mutation.get('value_expr'),
                mutation.get('in_function')
            )
            if 'python_state_mutations' not in self.counts:
                self.counts['python_state_mutations'] = 0
            self.counts['python_state_mutations'] += 1

    # =========================================================================
    # CONSOLIDATED TABLES - Group 2: Object-Oriented & Types (5 handlers)
    # =========================================================================

    def _store_python_class_features(self, file_path: str, python_class_features: list, jsx_pass: bool):
        """Store Python class features (metaclass/slots/abstract/dataclass/enum/etc)."""
        for feature in python_class_features:
            self.db_manager.add_python_class_feature(
                file_path,
                feature.get('line', 0),
                feature.get('feature_type', ''),
                feature.get('class_name'),
                feature.get('name'),
                feature.get('details')  # db_manager handles json.dumps
            )
            if 'python_class_features' not in self.counts:
                self.counts['python_class_features'] = 0
            self.counts['python_class_features'] += 1

    def _store_python_protocols(self, file_path: str, python_protocols: list, jsx_pass: bool):
        """Store Python protocol implementations (iterator/container/callable/etc)."""
        for protocol in python_protocols:
            self.db_manager.add_python_protocol(
                file_path,
                protocol.get('line', 0),
                protocol.get('protocol_type', ''),
                protocol.get('class_name'),
                protocol.get('implemented_methods')  # db_manager handles json.dumps
            )
            if 'python_protocols' not in self.counts:
                self.counts['python_protocols'] = 0
            self.counts['python_protocols'] += 1

    def _store_python_descriptors(self, file_path: str, python_descriptors: list, jsx_pass: bool):
        """Store Python descriptors (property/cached_property/dynamic_attr/etc)."""
        for desc in python_descriptors:
            self.db_manager.add_python_descriptor(
                file_path,
                desc.get('line', 0),
                desc.get('descriptor_type', ''),
                desc.get('name'),
                desc.get('class_name'),
                desc.get('has_getter', False),
                desc.get('has_setter', False),
                desc.get('has_deleter', False)
            )
            if 'python_descriptors' not in self.counts:
                self.counts['python_descriptors'] = 0
            self.counts['python_descriptors'] += 1

    def _store_python_type_definitions(self, file_path: str, python_type_definitions: list, jsx_pass: bool):
        """Store Python type definitions (typed_dict/generic/protocol)."""
        for typedef in python_type_definitions:
            self.db_manager.add_python_type_definition(
                file_path,
                typedef.get('line', 0),
                typedef.get('type_kind', ''),
                typedef.get('name'),
                typedef.get('type_params'),  # db_manager handles json.dumps
                typedef.get('fields')  # db_manager handles json.dumps
            )
            if 'python_type_definitions' not in self.counts:
                self.counts['python_type_definitions'] = 0
            self.counts['python_type_definitions'] += 1

    def _store_python_literals(self, file_path: str, python_literals: list, jsx_pass: bool):
        """Store Python Literal/Overload types."""
        for lit in python_literals:
            self.db_manager.add_python_literal(
                file_path,
                lit.get('line', 0),
                lit.get('literal_type', ''),
                lit.get('name'),
                # Extractor outputs 'values', DB column is 'literal_values' (SQL reserved keyword)
                lit.get('literal_values') or lit.get('values')
            )
            if 'python_literals' not in self.counts:
                self.counts['python_literals'] = 0
            self.counts['python_literals'] += 1

    # =========================================================================
    # CONSOLIDATED TABLES - Group 3: Security & Testing (5 handlers)
    # =========================================================================

    def _store_python_security_findings(self, file_path: str, python_security_findings: list, jsx_pass: bool):
        """Store Python security findings (sql_injection/command_injection/etc)."""
        for finding in python_security_findings:
            self.db_manager.add_python_security_finding(
                file_path,
                finding.get('line', 0),
                finding.get('finding_type', ''),
                finding.get('severity', 'medium'),
                finding.get('source_expr'),
                finding.get('sink_expr'),
                finding.get('vulnerable_code'),
                finding.get('cwe_id')
            )
            if 'python_security_findings' not in self.counts:
                self.counts['python_security_findings'] = 0
            self.counts['python_security_findings'] += 1

    def _store_python_test_cases(self, file_path: str, python_test_cases: list, jsx_pass: bool):
        """Store Python test cases (unittest/pytest/assertion)."""
        for test in python_test_cases:
            self.db_manager.add_python_test_case(
                file_path,
                test.get('line', 0),
                test.get('test_type', ''),
                test.get('name'),
                test.get('class_name'),
                test.get('assertion_type'),
                test.get('expected_exception')
            )
            if 'python_test_cases' not in self.counts:
                self.counts['python_test_cases'] = 0
            self.counts['python_test_cases'] += 1

    def _store_python_test_fixtures(self, file_path: str, python_test_fixtures: list, jsx_pass: bool):
        """Store Python test fixtures (fixture/parametrize/marker/mock/etc)."""
        for fixture in python_test_fixtures:
            self.db_manager.add_python_test_fixture(
                file_path,
                fixture.get('line', 0),
                fixture.get('fixture_type', ''),
                fixture.get('name'),
                fixture.get('scope'),
                fixture.get('params'),  # db_manager handles json.dumps
                fixture.get('autouse', False)
            )
            if 'python_test_fixtures' not in self.counts:
                self.counts['python_test_fixtures'] = 0
            self.counts['python_test_fixtures'] += 1

    def _store_python_framework_config(self, file_path: str, python_framework_config: list, jsx_pass: bool):
        """Store Python framework configurations (flask/celery/django)."""
        for config in python_framework_config:
            self.db_manager.add_python_framework_config(
                file_path,
                config.get('line', 0),
                config.get('framework', ''),
                config.get('config_type', ''),
                config.get('name'),
                config.get('endpoint'),
                config.get('methods'),
                config.get('schedule'),
                config.get('details')  # db_manager handles json.dumps
            )
            if 'python_framework_config' not in self.counts:
                self.counts['python_framework_config'] = 0
            self.counts['python_framework_config'] += 1

    def _store_python_validation_schemas(self, file_path: str, python_validation_schemas: list, jsx_pass: bool):
        """Store Python validation schemas (marshmallow/drf/wtforms)."""
        for schema in python_validation_schemas:
            self.db_manager.add_python_validation_schema(
                file_path,
                schema.get('line', 0),
                schema.get('framework', ''),
                schema.get('schema_type', ''),
                schema.get('name'),
                schema.get('field_type'),
                schema.get('validators'),  # db_manager handles json.dumps
                schema.get('required', False)
            )
            if 'python_validation_schemas' not in self.counts:
                self.counts['python_validation_schemas'] = 0
            self.counts['python_validation_schemas'] += 1

    # =========================================================================
    # CONSOLIDATED TABLES - Group 4: Low-Level & Misc (5 handlers)
    # =========================================================================

    def _store_python_operators(self, file_path: str, python_operators: list, jsx_pass: bool):
        """Store Python operators (binary/unary/membership/chained/ternary/walrus/matmul)."""
        for op in python_operators:
            self.db_manager.add_python_operator(
                file_path,
                op.get('line', 0),
                op.get('operator_type', ''),
                op.get('operator'),
                op.get('left_operand'),
                op.get('right_operand')
            )
            if 'python_operators' not in self.counts:
                self.counts['python_operators'] = 0
            self.counts['python_operators'] += 1

    def _store_python_collections(self, file_path: str, python_collections: list, jsx_pass: bool):
        """Store Python collection operations (dict/list/set/string/builtin/itertools/functools/collections)."""
        for coll in python_collections:
            self.db_manager.add_python_collection(
                file_path,
                coll.get('line', 0),
                coll.get('collection_type', ''),
                coll.get('operation'),
                coll.get('method')
            )
            if 'python_collections' not in self.counts:
                self.counts['python_collections'] = 0
            self.counts['python_collections'] += 1

    def _store_python_stdlib_usage(self, file_path: str, python_stdlib_usage: list, jsx_pass: bool):
        """Store Python stdlib usage (re/json/datetime/pathlib/logging/threading/etc)."""
        for usage in python_stdlib_usage:
            self.db_manager.add_python_stdlib_usage(
                file_path,
                usage.get('line', 0),
                usage.get('module', ''),
                usage.get('usage_type', ''),
                usage.get('function_name'),
                usage.get('pattern')
            )
            if 'python_stdlib_usage' not in self.counts:
                self.counts['python_stdlib_usage'] = 0
            self.counts['python_stdlib_usage'] += 1

    def _store_python_imports_advanced(self, file_path: str, python_imports_advanced: list, jsx_pass: bool):
        """Store advanced Python import patterns (static/dynamic/namespace/module_attr)."""
        for imp in python_imports_advanced:
            self.db_manager.add_python_import_advanced(
                file_path,
                imp.get('line', 0),
                imp.get('import_type', ''),
                imp.get('module'),
                imp.get('name'),
                imp.get('alias'),
                imp.get('is_relative', False)
            )
            if 'python_imports_advanced' not in self.counts:
                self.counts['python_imports_advanced'] = 0
            self.counts['python_imports_advanced'] += 1

    def _store_python_expressions(self, file_path: str, python_expressions: list, jsx_pass: bool):
        """Store Python expression patterns (comprehension/slice/tuple/unpack/format/etc)."""
        for expr in python_expressions:
            self.db_manager.add_python_expression(
                file_path,
                expr.get('line', 0),
                expr.get('expression_type', ''),
                expr.get('subtype'),
                expr.get('expression'),
                expr.get('variables')
            )
            if 'python_expressions' not in self.counts:
                self.counts['python_expressions'] = 0
            self.counts['python_expressions'] += 1
