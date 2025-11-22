"""Python storage handlers for framework-specific patterns.

This module contains handlers for Python frameworks and patterns:
- ORM: sqlalchemy, django models, fields
- HTTP: flask routes, django views, fastapi endpoints
- Validation: pydantic, marshmallow, django forms, wtforms, drf
- Testing: unittest, pytest, hypothesis, mocking
- Async: celery tasks, async/await, generators
- Security: auth decorators, password hashing, JWT, injection patterns
- Type System: protocols, generics, typed dicts, overloads
- Django: signals, receivers, managers, querysets, middleware, admin
- Flask: apps, extensions, hooks, websockets, cors, cache, CLI commands

Handler Count: 59
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
            # ORM and Data Models (4)
            'python_orm_models': self._store_python_orm_models,
            'python_orm_fields': self._store_python_orm_fields,
            'python_routes': self._store_python_routes,
            'python_blueprints': self._store_python_blueprints,

            # Django Framework (11)
            'python_django_views': self._store_python_django_views,
            'python_django_forms': self._store_python_django_forms,
            'python_django_form_fields': self._store_python_django_form_fields,
            'python_django_admin': self._store_python_django_admin,
            'python_django_middleware': self._store_python_django_middleware,
            'python_django_signals': self._store_python_django_signals,
            'python_django_receivers': self._store_python_django_receivers,
            'python_django_managers': self._store_python_django_managers,
            'python_django_querysets': self._store_python_django_querysets,

            # Validation Frameworks (6)
            'python_marshmallow_schemas': self._store_python_marshmallow_schemas,
            'python_marshmallow_fields': self._store_python_marshmallow_fields,
            'python_drf_serializers': self._store_python_drf_serializers,
            'python_drf_serializer_fields': self._store_python_drf_serializer_fields,
            'python_wtforms_forms': self._store_python_wtforms_forms,
            'python_wtforms_fields': self._store_python_wtforms_fields,

            # Celery and Background Tasks (4)
            'python_celery_tasks': self._store_python_celery_tasks,
            'python_celery_task_calls': self._store_python_celery_task_calls,
            'python_celery_beat_schedules': self._store_python_celery_beat_schedules,
            'python_generators': self._store_python_generators,

            # Flask Framework (9)
            'python_flask_apps': self._store_python_flask_apps,
            'python_flask_extensions': self._store_python_flask_extensions,
            'python_flask_hooks': self._store_python_flask_hooks,
            'python_flask_error_handlers': self._store_python_flask_error_handlers,
            'python_flask_websockets': self._store_python_flask_websockets,
            'python_flask_cli_commands': self._store_python_flask_cli_commands,
            'python_flask_cors': self._store_python_flask_cors,
            'python_flask_rate_limits': self._store_python_flask_rate_limits,
            'python_flask_cache': self._store_python_flask_cache,

            # Testing Framework (8)
            'python_unittest_test_cases': self._store_python_unittest_test_cases,
            'python_assertion_patterns': self._store_python_assertion_patterns,
            'python_pytest_plugin_hooks': self._store_python_pytest_plugin_hooks,
            'python_hypothesis_strategies': self._store_python_hypothesis_strategies,
            'python_pytest_fixtures': self._store_python_pytest_fixtures,
            'python_pytest_parametrize': self._store_python_pytest_parametrize,
            'python_pytest_markers': self._store_python_pytest_markers,
            'python_mock_patterns': self._store_python_mock_patterns,

            # Security Patterns (8)
            'python_auth_decorators': self._store_python_auth_decorators,
            'python_password_hashing': self._store_python_password_hashing,
            'python_jwt_operations': self._store_python_jwt_operations,
            'python_sql_injection': self._store_python_sql_injection,
            'python_command_injection': self._store_python_command_injection,
            'python_path_traversal': self._store_python_path_traversal,
            'python_dangerous_eval': self._store_python_dangerous_eval,
            'python_crypto_operations': self._store_python_crypto_operations,

            # Type System (5)
            'python_protocols': self._store_python_protocols,
            'python_generics': self._store_python_generics,
            'python_typed_dicts': self._store_python_typed_dicts,
            'python_literals': self._store_python_literals,
            'python_overloads': self._store_python_overloads,

            # Core Python Patterns (5)
            'python_validators': self._store_python_validators,
            'python_decorators': self._store_python_decorators,
            'python_context_managers': self._store_python_context_managers,
            'python_async_functions': self._store_python_async_functions,
            'python_await_expressions': self._store_python_await_expressions,
            'python_async_generators': self._store_python_async_generators,

            # Causal Learning Patterns (Week 1 - State Mutations)
            'python_instance_mutations': self._store_python_instance_mutations,
            'python_class_mutations': self._store_python_class_mutations,
            'python_global_mutations': self._store_python_global_mutations,
            'python_argument_mutations': self._store_python_argument_mutations,
            'python_augmented_assignments': self._store_python_augmented_assignments,

            # Causal Learning - Week 1: Exception Flow (4)
            'python_exception_raises': self._store_python_exception_raises,
            'python_exception_catches': self._store_python_exception_catches,
            'python_finally_blocks': self._store_python_finally_blocks,
            'python_context_managers_enhanced': self._store_python_context_managers_enhanced,

            # Causal Learning - Week 2: Data Flow (4)
            'python_io_operations': self._store_python_io_operations,
            'python_parameter_return_flow': self._store_python_parameter_return_flow,
            'python_closure_captures': self._store_python_closure_captures,
            'python_nonlocal_access': self._store_python_nonlocal_access,
            'python_conditional_calls': self._store_python_conditional_calls,

            # Causal Learning - Week 3: Behavioral (4)
            'python_recursion_patterns': self._store_python_recursion_patterns,
            'python_generator_yields': self._store_python_generator_yields,
            'python_property_patterns': self._store_python_property_patterns,
            'python_dynamic_attributes': self._store_python_dynamic_attributes,

            # Causal Learning - Week 4: Performance (3)
            'python_loop_complexity': self._store_python_loop_complexity,
            'python_resource_usage': self._store_python_resource_usage,
            'python_memoization_patterns': self._store_python_memoization_patterns,

            # Python Coverage V2 - Week 1: Fundamentals (8)
            'python_comprehensions': self._store_python_comprehensions,
            'python_lambda_functions': self._store_python_lambda_functions,
            'python_slice_operations': self._store_python_slice_operations,
            'python_tuple_operations': self._store_python_tuple_operations,
            'python_unpacking_patterns': self._store_python_unpacking_patterns,
            'python_none_patterns': self._store_python_none_patterns,
            'python_truthiness_patterns': self._store_python_truthiness_patterns,
            'python_string_formatting': self._store_python_string_formatting,

            # Python Coverage V2 - Week 2: Operators (6)
            'python_operators': self._store_python_operators,
            'python_membership_tests': self._store_python_membership_tests,
            'python_chained_comparisons': self._store_python_chained_comparisons,
            'python_ternary_expressions': self._store_python_ternary_expressions,
            'python_walrus_operators': self._store_python_walrus_operators,
            'python_matrix_multiplication': self._store_python_matrix_multiplication,

            # Python Coverage V2 - Week 3: Collections (8)
            'python_dict_operations': self._store_python_dict_operations,
            'python_list_mutations': self._store_python_list_mutations,
            'python_set_operations': self._store_python_set_operations,
            'python_string_methods': self._store_python_string_methods,
            'python_builtin_usage': self._store_python_builtin_usage,
            'python_itertools_usage': self._store_python_itertools_usage,
            'python_functools_usage': self._store_python_functools_usage,
            'python_collections_usage': self._store_python_collections_usage,

            # Python Coverage V2 - Week 4: Class Features (10)
            'python_metaclasses': self._store_python_metaclasses,
            'python_descriptors': self._store_python_descriptors,
            'python_dataclasses': self._store_python_dataclasses,
            'python_enums': self._store_python_enums,
            'python_slots': self._store_python_slots,
            'python_abstract_classes': self._store_python_abstract_classes,
            'python_method_types': self._store_python_method_types,
            'python_multiple_inheritance': self._store_python_multiple_inheritance,
            'python_dunder_methods': self._store_python_dunder_methods,
            'python_visibility_conventions': self._store_python_visibility_conventions,

            # Python Coverage V2 - Week 4: Stdlib Patterns (8)
            'python_regex_patterns': self._store_python_regex_patterns,
            'python_json_operations': self._store_python_json_operations,
            'python_datetime_operations': self._store_python_datetime_operations,
            'python_path_operations': self._store_python_path_operations,
            'python_logging_patterns': self._store_python_logging_patterns,
            'python_threading_patterns': self._store_python_threading_patterns,
            'python_contextlib_patterns': self._store_python_contextlib_patterns,
            'python_type_checking': self._store_python_type_checking,

            # Python Coverage V2 - Week 5: Control Flow (10)
            'python_for_loops': self._store_python_for_loops,
            'python_while_loops': self._store_python_while_loops,
            'python_async_for_loops': self._store_python_async_for_loops,
            'python_if_statements': self._store_python_if_statements,
            'python_match_statements': self._store_python_match_statements,
            'python_break_continue_pass': self._store_python_break_continue_pass,
            'python_assert_statements': self._store_python_assert_statements,
            'python_del_statements': self._store_python_del_statements,
            'python_import_statements': self._store_python_import_statements,
            'python_with_statements': self._store_python_with_statements,

            # Python Coverage V2 - Week 6: Protocol Patterns (10)
            'python_iterator_protocol': self._store_python_iterator_protocol,
            'python_container_protocol': self._store_python_container_protocol,
            'python_callable_protocol': self._store_python_callable_protocol,
            'python_comparison_protocol': self._store_python_comparison_protocol,
            'python_arithmetic_protocol': self._store_python_arithmetic_protocol,
            'python_pickle_protocol': self._store_python_pickle_protocol,
            'python_weakref_usage': self._store_python_weakref_usage,
            'python_contextvar_usage': self._store_python_contextvar_usage,
            'python_module_attributes': self._store_python_module_attributes,
            'python_class_decorators': self._store_python_class_decorators,

            # Python Coverage V2 - Advanced Patterns (8)
            'python_namespace_packages': self._store_python_namespace_packages,
            'python_cached_property': self._store_python_cached_property,
            'python_descriptor_protocol': self._store_python_descriptor_protocol,
            'python_attribute_access_protocol': self._store_python_attribute_access_protocol,
            'python_copy_protocol': self._store_python_copy_protocol,
            'python_ellipsis_usage': self._store_python_ellipsis_usage,
            'python_bytes_operations': self._store_python_bytes_operations,
            'python_exec_eval_compile': self._store_python_exec_eval_compile,
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

    def _store_python_blueprints(self, file_path: str, python_blueprints: list, jsx_pass: bool):
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

    def _store_python_django_forms(self, file_path: str, python_django_forms: list, jsx_pass: bool):
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

    def _store_python_django_form_fields(self, file_path: str, python_django_form_fields: list, jsx_pass: bool):
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

    def _store_python_django_admin(self, file_path: str, python_django_admin: list, jsx_pass: bool):
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

    def _store_python_marshmallow_schemas(self, file_path: str, python_marshmallow_schemas: list, jsx_pass: bool):
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

    def _store_python_marshmallow_fields(self, file_path: str, python_marshmallow_fields: list, jsx_pass: bool):
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

    def _store_python_drf_serializers(self, file_path: str, python_drf_serializers: list, jsx_pass: bool):
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

    def _store_python_drf_serializer_fields(self, file_path: str, python_drf_serializer_fields: list, jsx_pass: bool):
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

    def _store_python_wtforms_forms(self, file_path: str, python_wtforms_forms: list, jsx_pass: bool):
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

    def _store_python_wtforms_fields(self, file_path: str, python_wtforms_fields: list, jsx_pass: bool):
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

    def _store_python_celery_tasks(self, file_path: str, python_celery_tasks: list, jsx_pass: bool):
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

    def _store_python_celery_task_calls(self, file_path: str, python_celery_task_calls: list, jsx_pass: bool):
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

    def _store_python_celery_beat_schedules(self, file_path: str, python_celery_beat_schedules: list, jsx_pass: bool):
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

    def _store_python_generators(self, file_path: str, python_generators: list, jsx_pass: bool):
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

    # Flask Framework (Phase 3.1) storage methods

    def _store_python_flask_apps(self, file_path: str, python_flask_apps: list, jsx_pass: bool):
        """Store Flask application factories."""
        for app in python_flask_apps:
            self.db_manager.add_python_flask_app(
                file_path,
                app.get('line', 0),
                app.get('factory_name', ''),
                app.get('app_var_name'),
                app.get('config_source'),
                app.get('registers_blueprints', False)
            )
            if 'python_flask_apps' not in self.counts:
                self.counts['python_flask_apps'] = 0
            self.counts['python_flask_apps'] += 1

    def _store_python_flask_extensions(self, file_path: str, python_flask_extensions: list, jsx_pass: bool):
        """Store Flask extension registrations."""
        for extension in python_flask_extensions:
            self.db_manager.add_python_flask_extension(
                file_path,
                extension.get('line', 0),
                extension.get('extension_type', ''),
                extension.get('var_name'),
                extension.get('app_passed_to_constructor', False)
            )
            if 'python_flask_extensions' not in self.counts:
                self.counts['python_flask_extensions'] = 0
            self.counts['python_flask_extensions'] += 1

    def _store_python_flask_hooks(self, file_path: str, python_flask_hooks: list, jsx_pass: bool):
        """Store Flask request/response hooks."""
        for hook in python_flask_hooks:
            self.db_manager.add_python_flask_hook(
                file_path,
                hook.get('line', 0),
                hook.get('hook_type', ''),
                hook.get('function_name', ''),
                hook.get('app_var')
            )
            if 'python_flask_hooks' not in self.counts:
                self.counts['python_flask_hooks'] = 0
            self.counts['python_flask_hooks'] += 1

    def _store_python_flask_error_handlers(self, file_path: str, python_flask_error_handlers: list, jsx_pass: bool):
        """Store Flask error handlers."""
        for handler in python_flask_error_handlers:
            self.db_manager.add_python_flask_error_handler(
                file_path,
                handler.get('line', 0),
                handler.get('function_name', ''),
                handler.get('error_code'),
                handler.get('exception_type')
            )
            if 'python_flask_error_handlers' not in self.counts:
                self.counts['python_flask_error_handlers'] = 0
            self.counts['python_flask_error_handlers'] += 1

    def _store_python_flask_websockets(self, file_path: str, python_flask_websockets: list, jsx_pass: bool):
        """Store Flask-SocketIO WebSocket handlers."""
        for websocket in python_flask_websockets:
            self.db_manager.add_python_flask_websocket(
                file_path,
                websocket.get('line', 0),
                websocket.get('function_name', ''),
                websocket.get('event_name'),
                websocket.get('namespace')
            )
            if 'python_flask_websockets' not in self.counts:
                self.counts['python_flask_websockets'] = 0
            self.counts['python_flask_websockets'] += 1

    def _store_python_flask_cli_commands(self, file_path: str, python_flask_cli_commands: list, jsx_pass: bool):
        """Store Flask CLI commands."""
        for command in python_flask_cli_commands:
            self.db_manager.add_python_flask_cli_command(
                file_path,
                command.get('line', 0),
                command.get('command_name', ''),
                command.get('function_name', ''),
                command.get('has_options', False)
            )
            if 'python_flask_cli_commands' not in self.counts:
                self.counts['python_flask_cli_commands'] = 0
            self.counts['python_flask_cli_commands'] += 1

    def _store_python_flask_cors(self, file_path: str, python_flask_cors: list, jsx_pass: bool):
        """Store Flask CORS configurations."""
        for cors in python_flask_cors:
            self.db_manager.add_python_flask_cors(
                file_path,
                cors.get('line', 0),
                cors.get('config_type', ''),
                cors.get('origins'),
                cors.get('is_permissive', False)
            )
            if 'python_flask_cors' not in self.counts:
                self.counts['python_flask_cors'] = 0
            self.counts['python_flask_cors'] += 1

    def _store_python_flask_rate_limits(self, file_path: str, python_flask_rate_limits: list, jsx_pass: bool):
        """Store Flask rate limiting decorators."""
        for limit in python_flask_rate_limits:
            self.db_manager.add_python_flask_rate_limit(
                file_path,
                limit.get('line', 0),
                limit.get('function_name', ''),
                limit.get('limit_string')
            )
            if 'python_flask_rate_limits' not in self.counts:
                self.counts['python_flask_rate_limits'] = 0
            self.counts['python_flask_rate_limits'] += 1

    def _store_python_flask_cache(self, file_path: str, python_flask_cache: list, jsx_pass: bool):
        """Store Flask caching decorators."""
        for cache in python_flask_cache:
            self.db_manager.add_python_flask_cache(
                file_path,
                cache.get('line', 0),
                cache.get('function_name', ''),
                cache.get('cache_type', ''),
                cache.get('timeout')
            )
            if 'python_flask_cache' not in self.counts:
                self.counts['python_flask_cache'] = 0
            self.counts['python_flask_cache'] += 1

    # Testing Ecosystem (Phase 3.2) storage methods

    def _store_python_unittest_test_cases(self, file_path: str, python_unittest_test_cases: list, jsx_pass: bool):
        """Store unittest TestCase classes."""
        for test_case in python_unittest_test_cases:
            self.db_manager.add_python_unittest_test_case(
                file_path,
                test_case.get('line', 0),
                test_case.get('test_class_name', ''),
                test_case.get('test_method_count', 0),
                test_case.get('has_setup', False),
                test_case.get('has_teardown', False),
                test_case.get('has_setupclass', False),
                test_case.get('has_teardownclass', False)
            )
            if 'python_unittest_test_cases' not in self.counts:
                self.counts['python_unittest_test_cases'] = 0
            self.counts['python_unittest_test_cases'] += 1

    def _store_python_assertion_patterns(self, file_path: str, python_assertion_patterns: list, jsx_pass: bool):
        """Store assertion patterns."""
        for assertion in python_assertion_patterns:
            self.db_manager.add_python_assertion_pattern(
                file_path,
                assertion.get('line', 0),
                assertion.get('function_name', ''),
                assertion.get('assertion_type', ''),
                assertion.get('test_expr'),
                assertion.get('assertion_method')
            )
            if 'python_assertion_patterns' not in self.counts:
                self.counts['python_assertion_patterns'] = 0
            self.counts['python_assertion_patterns'] += 1

    def _store_python_pytest_plugin_hooks(self, file_path: str, python_pytest_plugin_hooks: list, jsx_pass: bool):
        """Store pytest plugin hooks."""
        for hook in python_pytest_plugin_hooks:
            self.db_manager.add_python_pytest_plugin_hook(
                file_path,
                hook.get('line', 0),
                hook.get('hook_name', ''),
                hook.get('param_count', 0)
            )
            if 'python_pytest_plugin_hooks' not in self.counts:
                self.counts['python_pytest_plugin_hooks'] = 0
            self.counts['python_pytest_plugin_hooks'] += 1

    def _store_python_hypothesis_strategies(self, file_path: str, python_hypothesis_strategies: list, jsx_pass: bool):
        """Store Hypothesis strategies."""
        for strategy in python_hypothesis_strategies:
            self.db_manager.add_python_hypothesis_strategy(
                file_path,
                strategy.get('line', 0),
                strategy.get('test_name', ''),
                strategy.get('strategy_count', 0),
                strategy.get('strategies')
            )
            if 'python_hypothesis_strategies' not in self.counts:
                self.counts['python_hypothesis_strategies'] = 0
            self.counts['python_hypothesis_strategies'] += 1

    # Security Patterns (Phase 3.3) storage methods

    def _store_python_auth_decorators(self, file_path: str, python_auth_decorators: list, jsx_pass: bool):
        """Store authentication decorators."""
        for auth in python_auth_decorators:
            self.db_manager.add_python_auth_decorator(
                file_path,
                auth.get('line', 0),
                auth.get('function_name', ''),
                auth.get('decorator_name', ''),
                auth.get('permissions')
            )
            if 'python_auth_decorators' not in self.counts:
                self.counts['python_auth_decorators'] = 0
            self.counts['python_auth_decorators'] += 1

    def _store_python_password_hashing(self, file_path: str, python_password_hashing: list, jsx_pass: bool):
        """Store password hashing patterns."""
        for hash_pattern in python_password_hashing:
            self.db_manager.add_python_password_hashing(
                file_path,
                hash_pattern.get('line', 0),
                hash_pattern.get('hash_library'),
                hash_pattern.get('hash_method'),
                hash_pattern.get('is_weak', False),
                hash_pattern.get('has_hardcoded_value', False)
            )
            if 'python_password_hashing' not in self.counts:
                self.counts['python_password_hashing'] = 0
            self.counts['python_password_hashing'] += 1

    def _store_python_jwt_operations(self, file_path: str, python_jwt_operations: list, jsx_pass: bool):
        """Store JWT operations."""
        for jwt_op in python_jwt_operations:
            self.db_manager.add_python_jwt_operation(
                file_path,
                jwt_op.get('line', 0),
                jwt_op.get('operation', ''),
                jwt_op.get('algorithm'),
                jwt_op.get('verify'),
                jwt_op.get('is_insecure', False)
            )
            if 'python_jwt_operations' not in self.counts:
                self.counts['python_jwt_operations'] = 0
            self.counts['python_jwt_operations'] += 1

    def _store_python_sql_injection(self, file_path: str, python_sql_injection: list, jsx_pass: bool):
        """Store SQL injection patterns."""
        for sql_pattern in python_sql_injection:
            self.db_manager.add_python_sql_injection(
                file_path,
                sql_pattern.get('line', 0),
                sql_pattern.get('db_method', ''),
                sql_pattern.get('interpolation_type'),
                sql_pattern.get('is_vulnerable', True)
            )
            if 'python_sql_injection' not in self.counts:
                self.counts['python_sql_injection'] = 0
            self.counts['python_sql_injection'] += 1

    def _store_python_command_injection(self, file_path: str, python_command_injection: list, jsx_pass: bool):
        """Store command injection patterns."""
        for cmd_pattern in python_command_injection:
            self.db_manager.add_python_command_injection(
                file_path,
                cmd_pattern.get('line', 0),
                cmd_pattern.get('function', ''),
                cmd_pattern.get('shell_true', False),
                cmd_pattern.get('is_vulnerable', True)
            )
            if 'python_command_injection' not in self.counts:
                self.counts['python_command_injection'] = 0
            self.counts['python_command_injection'] += 1

    def _store_python_path_traversal(self, file_path: str, python_path_traversal: list, jsx_pass: bool):
        """Store path traversal patterns."""
        for path_pattern in python_path_traversal:
            self.db_manager.add_python_path_traversal(
                file_path,
                path_pattern.get('line', 0),
                path_pattern.get('function', ''),
                path_pattern.get('has_concatenation', False),
                path_pattern.get('is_vulnerable', False)
            )
            if 'python_path_traversal' not in self.counts:
                self.counts['python_path_traversal'] = 0
            self.counts['python_path_traversal'] += 1

    def _store_python_dangerous_eval(self, file_path: str, python_dangerous_eval: list, jsx_pass: bool):
        """Store dangerous eval/exec patterns."""
        for eval_pattern in python_dangerous_eval:
            self.db_manager.add_python_dangerous_eval(
                file_path,
                eval_pattern.get('line', 0),
                eval_pattern.get('function', ''),
                eval_pattern.get('is_constant_input', False),
                eval_pattern.get('is_critical', True)
            )
            if 'python_dangerous_eval' not in self.counts:
                self.counts['python_dangerous_eval'] = 0
            self.counts['python_dangerous_eval'] += 1

    def _store_python_crypto_operations(self, file_path: str, python_crypto_operations: list, jsx_pass: bool):
        """Store cryptography operations."""
        for crypto_op in python_crypto_operations:
            self.db_manager.add_python_crypto_operation(
                file_path,
                crypto_op.get('line', 0),
                crypto_op.get('algorithm'),
                crypto_op.get('mode'),
                crypto_op.get('is_weak', False),
                crypto_op.get('has_hardcoded_key', False)
            )
            if 'python_crypto_operations' not in self.counts:
                self.counts['python_crypto_operations'] = 0
            self.counts['python_crypto_operations'] += 1

    # ============================================================================
    # PHASE 3.4: DJANGO ADVANCED STORAGE METHODS
    # ============================================================================

    def _store_python_django_signals(self, file_path: str, python_django_signals: list, jsx_pass: bool):
        """Store Django signal definitions and connections."""
        for signal in python_django_signals:
            self.db_manager.add_python_django_signal(
                file_path,
                signal.get('line', 0),
                signal.get('signal_name', 'unknown'),
                signal.get('signal_type'),
                signal.get('providing_args', '[]'),
                signal.get('sender'),
                signal.get('receiver_function')
            )
            if 'python_django_signals' not in self.counts:
                self.counts['python_django_signals'] = 0
            self.counts['python_django_signals'] += 1

    def _store_python_django_receivers(self, file_path: str, python_django_receivers: list, jsx_pass: bool):
        """Store Django @receiver decorators."""
        for receiver in python_django_receivers:
            self.db_manager.add_python_django_receiver(
                file_path,
                receiver.get('line', 0),
                receiver.get('function_name', 'unknown'),
                receiver.get('signals', '[]'),
                receiver.get('sender'),
                receiver.get('is_weak', False)
            )
            if 'python_django_receivers' not in self.counts:
                self.counts['python_django_receivers'] = 0
            self.counts['python_django_receivers'] += 1

    def _store_python_django_managers(self, file_path: str, python_django_managers: list, jsx_pass: bool):
        """Store Django custom managers."""
        for manager in python_django_managers:
            self.db_manager.add_python_django_manager(
                file_path,
                manager.get('line', 0),
                manager.get('manager_name', 'unknown'),
                manager.get('base_class'),
                manager.get('custom_methods', '[]'),
                manager.get('model_assignment')
            )
            if 'python_django_managers' not in self.counts:
                self.counts['python_django_managers'] = 0
            self.counts['python_django_managers'] += 1

    def _store_python_django_querysets(self, file_path: str, python_django_querysets: list, jsx_pass: bool):
        """Store Django QuerySet definitions and chains."""
        for queryset in python_django_querysets:
            self.db_manager.add_python_django_queryset(
                file_path,
                queryset.get('line', 0),
                queryset.get('queryset_name', 'unknown'),
                queryset.get('base_class'),
                queryset.get('custom_methods', '[]'),
                queryset.get('has_as_manager', False),
                queryset.get('method_chain')
            )
            if 'python_django_querysets' not in self.counts:
                self.counts['python_django_querysets'] = 0
            self.counts['python_django_querysets'] += 1

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

    def _store_python_context_managers(self, file_path: str, python_context_managers: list, jsx_pass: bool):
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

    def _store_python_async_functions(self, file_path: str, python_async_functions: list, jsx_pass: bool):
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

    def _store_python_await_expressions(self, file_path: str, python_await_expressions: list, jsx_pass: bool):
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

    def _store_python_async_generators(self, file_path: str, python_async_generators: list, jsx_pass: bool):
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

    def _store_python_instance_mutations(self, file_path: str, python_instance_mutations: list, jsx_pass: bool):
        """Store Python instance attribute mutations (Causal Learning - Week 1)."""
        for mutation in python_instance_mutations:
            self.db_manager.add_python_instance_mutation(
                file_path,
                mutation.get('line', 0),
                mutation.get('target', ''),
                mutation.get('operation', ''),
                mutation.get('in_function', 'global'),
                mutation.get('is_init', False),
                mutation.get('is_property_setter', False),
                mutation.get('is_dunder_method', False)
            )
            if 'python_instance_mutations' not in self.counts:
                self.counts['python_instance_mutations'] = 0
            self.counts['python_instance_mutations'] += 1

    def _store_python_class_mutations(self, file_path: str, python_class_mutations: list, jsx_pass: bool):
        """Store Python class attribute mutations (Causal Learning - Week 1)."""
        for mutation in python_class_mutations:
            self.db_manager.add_python_class_mutation(
                file_path,
                mutation.get('line', 0),
                mutation.get('class_name', ''),
                mutation.get('attribute', ''),
                mutation.get('operation', ''),
                mutation.get('in_function', 'global'),
                mutation.get('is_classmethod', False)
            )
            if 'python_class_mutations' not in self.counts:
                self.counts['python_class_mutations'] = 0
            self.counts['python_class_mutations'] += 1

    def _store_python_global_mutations(self, file_path: str, python_global_mutations: list, jsx_pass: bool):
        """Store Python global variable mutations (Causal Learning - Week 1)."""
        for mutation in python_global_mutations:
            self.db_manager.add_python_global_mutation(
                file_path,
                mutation.get('line', 0),
                mutation.get('global_name', ''),
                mutation.get('operation', ''),
                mutation.get('in_function', 'global')
            )
            if 'python_global_mutations' not in self.counts:
                self.counts['python_global_mutations'] = 0
            self.counts['python_global_mutations'] += 1

    def _store_python_argument_mutations(self, file_path: str, python_argument_mutations: list, jsx_pass: bool):
        """Store Python argument mutations (Causal Learning - Week 1)."""
        for mutation in python_argument_mutations:
            self.db_manager.add_python_argument_mutation(
                file_path,
                mutation.get('line', 0),
                mutation.get('parameter_name', ''),
                mutation.get('mutation_type', ''),
                mutation.get('mutation_detail', ''),
                mutation.get('in_function', 'global')
            )
            if 'python_argument_mutations' not in self.counts:
                self.counts['python_argument_mutations'] = 0
            self.counts['python_argument_mutations'] += 1

    def _store_python_augmented_assignments(self, file_path: str, python_augmented_assignments: list, jsx_pass: bool):
        """Store Python augmented assignments (Causal Learning - Week 1)."""
        for assignment in python_augmented_assignments:
            self.db_manager.add_python_augmented_assignment(
                file_path,
                assignment.get('line', 0),
                assignment.get('target', ''),
                assignment.get('operator', ''),
                assignment.get('target_type', ''),
                assignment.get('in_function', 'global')
            )
            if 'python_augmented_assignments' not in self.counts:
                self.counts['python_augmented_assignments'] = 0
            self.counts['python_augmented_assignments'] += 1

    def _store_python_pytest_fixtures(self, file_path: str, python_pytest_fixtures: list, jsx_pass: bool):
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

    def _store_python_pytest_parametrize(self, file_path: str, python_pytest_parametrize: list, jsx_pass: bool):
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

    def _store_python_pytest_markers(self, file_path: str, python_pytest_markers: list, jsx_pass: bool):
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

    def _store_python_mock_patterns(self, file_path: str, python_mock_patterns: list, jsx_pass: bool):
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

    def _store_python_protocols(self, file_path: str, python_protocols: list, jsx_pass: bool):
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

    # ========================================================================
    # Causal Learning Storage Handlers (Week 1-4: 15 new handlers)
    # ========================================================================

    def _store_python_exception_raises(self, file_path: str, python_exception_raises: list, jsx_pass: bool):
        """Store exception raise patterns (Week 1 Exception Flow)."""
        for item in python_exception_raises:
            self.db_manager.add_python_exception_raise(
                file_path,
                item.get('line', 0),
                item.get('exception_type'),
                item.get('message'),
                item.get('from_exception'),
                item.get('in_function', 'global'),
                item.get('condition'),
                item.get('is_re_raise', False)
            )
            if 'python_exception_raises' not in self.counts:
                self.counts['python_exception_raises'] = 0
            self.counts['python_exception_raises'] += 1

    def _store_python_exception_catches(self, file_path: str, python_exception_catches: list, jsx_pass: bool):
        """Store exception catch patterns (Week 1 Exception Flow)."""
        for item in python_exception_catches:
            self.db_manager.add_python_exception_catch(
                file_path,
                item.get('line', 0),
                item.get('exception_types', ''),
                item.get('variable_name'),
                item.get('handling_strategy', ''),
                item.get('in_function', 'global')
            )
            if 'python_exception_catches' not in self.counts:
                self.counts['python_exception_catches'] = 0
            self.counts['python_exception_catches'] += 1

    def _store_python_finally_blocks(self, file_path: str, python_finally_blocks: list, jsx_pass: bool):
        """Store finally block patterns (Week 1 Exception Flow)."""
        for item in python_finally_blocks:
            self.db_manager.add_python_finally_block(
                file_path,
                item.get('line', 0),
                item.get('cleanup_calls'),
                item.get('has_cleanup', False),
                item.get('in_function', 'global')
            )
            if 'python_finally_blocks' not in self.counts:
                self.counts['python_finally_blocks'] = 0
            self.counts['python_finally_blocks'] += 1

    def _store_python_context_managers_enhanced(self, file_path: str, python_context_managers_enhanced: list, jsx_pass: bool):
        """Store enhanced context manager patterns (Week 1 Exception Flow)."""
        for item in python_context_managers_enhanced:
            self.db_manager.add_python_context_manager_enhanced(
                file_path,
                item.get('line', 0),
                item.get('context_expr', ''),
                item.get('variable_name'),
                item.get('in_function', 'global'),
                item.get('is_async', False),
                item.get('resource_type')
            )
            if 'python_context_managers_enhanced' not in self.counts:
                self.counts['python_context_managers_enhanced'] = 0
            self.counts['python_context_managers_enhanced'] += 1

    def _store_python_io_operations(self, file_path: str, python_io_operations: list, jsx_pass: bool):
        """Store I/O operation patterns (Week 2 Data Flow)."""
        for item in python_io_operations:
            self.db_manager.add_python_io_operation(
                file_path,
                item.get('line', 0),
                item.get('io_type', ''),
                item.get('operation', ''),
                item.get('target'),
                item.get('is_static', False),
                item.get('in_function', 'global')
            )
            if 'python_io_operations' not in self.counts:
                self.counts['python_io_operations'] = 0
            self.counts['python_io_operations'] += 1

    def _store_python_parameter_return_flow(self, file_path: str, python_parameter_return_flow: list, jsx_pass: bool):
        """Store parameter return flow patterns (Week 2 Data Flow)."""
        for item in python_parameter_return_flow:
            self.db_manager.add_python_parameter_return_flow(
                file_path,
                item.get('line', 0),
                item.get('function_name', ''),
                item.get('parameter_name', ''),
                item.get('return_expr', ''),
                item.get('flow_type', ''),
                item.get('is_async', False)
            )
            if 'python_parameter_return_flow' not in self.counts:
                self.counts['python_parameter_return_flow'] = 0
            self.counts['python_parameter_return_flow'] += 1

    def _store_python_closure_captures(self, file_path: str, python_closure_captures: list, jsx_pass: bool):
        """Store closure capture patterns (Week 2 Data Flow)."""
        for item in python_closure_captures:
            self.db_manager.add_python_closure_capture(
                file_path,
                item.get('line', 0),
                item.get('inner_function', ''),
                item.get('captured_variable', ''),
                item.get('outer_function', ''),
                item.get('is_lambda', False)
            )
            if 'python_closure_captures' not in self.counts:
                self.counts['python_closure_captures'] = 0
            self.counts['python_closure_captures'] += 1

    def _store_python_nonlocal_access(self, file_path: str, python_nonlocal_access: list, jsx_pass: bool):
        """Store nonlocal access patterns (Week 2 Data Flow)."""
        for item in python_nonlocal_access:
            self.db_manager.add_python_nonlocal_access(
                file_path,
                item.get('line', 0),
                item.get('variable_name', ''),
                item.get('access_type', ''),
                item.get('in_function', 'global')
            )
            if 'python_nonlocal_access' not in self.counts:
                self.counts['python_nonlocal_access'] = 0
            self.counts['python_nonlocal_access'] += 1

    def _store_python_conditional_calls(self, file_path: str, python_conditional_calls: list, jsx_pass: bool):
        """Store conditional call patterns (Week 2 Data Flow)."""
        for item in python_conditional_calls:
            self.db_manager.add_python_conditional_call(
                file_path,
                item.get('line', 0),
                item.get('function_call', ''),
                item.get('condition_expr'),
                item.get('condition_type', ''),
                item.get('in_function', 'global'),
                item.get('nesting_level', 1)
            )
            if 'python_conditional_calls' not in self.counts:
                self.counts['python_conditional_calls'] = 0
            self.counts['python_conditional_calls'] += 1

    def _store_python_recursion_patterns(self, file_path: str, python_recursion_patterns: list, jsx_pass: bool):
        """Store recursion patterns (Week 3 Behavioral)."""
        for item in python_recursion_patterns:
            self.db_manager.add_python_recursion_pattern(
                file_path,
                item.get('line', 0),
                item.get('function_name', ''),
                item.get('recursion_type', ''),
                item.get('calls_function', ''),
                item.get('base_case_line'),
                item.get('is_async', False)
            )
            if 'python_recursion_patterns' not in self.counts:
                self.counts['python_recursion_patterns'] = 0
            self.counts['python_recursion_patterns'] += 1

    def _store_python_generator_yields(self, file_path: str, python_generator_yields: list, jsx_pass: bool):
        """Store generator yield patterns (Week 3 Behavioral)."""
        for item in python_generator_yields:
            self.db_manager.add_python_generator_yield(
                file_path,
                item.get('line', 0),
                item.get('generator_function', ''),
                item.get('yield_type', ''),
                item.get('yield_expr'),
                item.get('condition'),
                item.get('in_loop', False)
            )
            if 'python_generator_yields' not in self.counts:
                self.counts['python_generator_yields'] = 0
            self.counts['python_generator_yields'] += 1

    def _store_python_property_patterns(self, file_path: str, python_property_patterns: list, jsx_pass: bool):
        """Store property patterns (Week 3 Behavioral)."""
        for item in python_property_patterns:
            self.db_manager.add_python_property_pattern(
                file_path,
                item.get('line', 0),
                item.get('property_name', ''),
                item.get('access_type', ''),
                item.get('in_class', ''),
                item.get('has_computation', False),
                item.get('has_validation', False)
            )
            if 'python_property_patterns' not in self.counts:
                self.counts['python_property_patterns'] = 0
            self.counts['python_property_patterns'] += 1

    def _store_python_dynamic_attributes(self, file_path: str, python_dynamic_attributes: list, jsx_pass: bool):
        """Store dynamic attribute patterns (Week 3 Behavioral)."""
        for item in python_dynamic_attributes:
            self.db_manager.add_python_dynamic_attribute(
                file_path,
                item.get('line', 0),
                item.get('method_name', ''),
                item.get('in_class', ''),
                item.get('has_delegation', False),
                item.get('has_validation', False)
            )
            if 'python_dynamic_attributes' not in self.counts:
                self.counts['python_dynamic_attributes'] = 0
            self.counts['python_dynamic_attributes'] += 1

    def _store_python_loop_complexity(self, file_path: str, python_loop_complexity: list, jsx_pass: bool):
        """Store loop complexity patterns (Week 4 Performance)."""
        for item in python_loop_complexity:
            self.db_manager.add_python_loop_complexity(
                file_path,
                item.get('line', 0),
                item.get('loop_type', ''),
                item.get('nesting_level', 1),
                item.get('has_growing_operation', False),
                item.get('in_function', 'global'),
                item.get('estimated_complexity', '')
            )
            if 'python_loop_complexity' not in self.counts:
                self.counts['python_loop_complexity'] = 0
            self.counts['python_loop_complexity'] += 1

    def _store_python_resource_usage(self, file_path: str, python_resource_usage: list, jsx_pass: bool):
        """Store resource usage patterns (Week 4 Performance)."""
        for item in python_resource_usage:
            self.db_manager.add_python_resource_usage(
                file_path,
                item.get('line', 0),
                item.get('resource_type', ''),
                item.get('allocation_expr', ''),
                item.get('in_function', 'global'),
                item.get('has_cleanup', False)
            )
            if 'python_resource_usage' not in self.counts:
                self.counts['python_resource_usage'] = 0
            self.counts['python_resource_usage'] += 1

    def _store_python_memoization_patterns(self, file_path: str, python_memoization_patterns: list, jsx_pass: bool):
        """Store memoization patterns (Week 4 Performance)."""
        for item in python_memoization_patterns:
            self.db_manager.add_python_memoization_pattern(
                file_path,
                item.get('line', 0),
                item.get('function_name', ''),
                item.get('has_memoization', False),
                item.get('memoization_type', ''),
                item.get('is_recursive', False),
                item.get('cache_size')
            )
            if 'python_memoization_patterns' not in self.counts:
                self.counts['python_memoization_patterns'] = 0
            self.counts['python_memoization_patterns'] += 1

    def _store_python_generics(self, file_path: str, python_generics: list, jsx_pass: bool):
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

    def _store_python_typed_dicts(self, file_path: str, python_typed_dicts: list, jsx_pass: bool):
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

    def _store_python_literals(self, file_path: str, python_literals: list, jsx_pass: bool):
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

    def _store_python_overloads(self, file_path: str, python_overloads: list, jsx_pass: bool):
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

    # ================================================================
    # Python Coverage V2 Storage Handlers (40 handlers)
    # ================================================================

    def _store_python_comprehensions(self, file_path: str, python_comprehensions: list, jsx_pass: bool):
        """Store python comprehensions."""
        for item in python_comprehensions:
            self.db_manager.add_python_comprehension(
                file_path,
                item.get('line', 0),
                item.get('comp_type', ''),
                item.get('result_expr', ''),
                item.get('iteration_var', ''),
                item.get('iteration_source', ''),
                item.get('has_filter', False),
                item.get('filter_expr', ''),
                item.get('nesting_level', ''),
                item.get('in_function', ''),
            )
            if 'python_comprehensions' not in self.counts:
                self.counts['python_comprehensions'] = 0
            self.counts['python_comprehensions'] += 1

    def _store_python_lambda_functions(self, file_path: str, python_lambda_functions: list, jsx_pass: bool):
        """Store python lambda functions."""
        for item in python_lambda_functions:
            self.db_manager.add_python_lambda_function(
                file_path,
                item.get('line', 0),
                item.get('parameter_count', ''),
                item.get('body', ''),
                item.get('captures_closure', False),
                item.get('used_in', ''),
                item.get('in_function', ''),
            )
            if 'python_lambda_functions' not in self.counts:
                self.counts['python_lambda_functions'] = 0
            self.counts['python_lambda_functions'] += 1

    def _store_python_slice_operations(self, file_path: str, python_slice_operations: list, jsx_pass: bool):
        """Store python slice operations."""
        for item in python_slice_operations:
            self.db_manager.add_python_slice_operation(
                file_path,
                item.get('line', 0),
                item.get('target', ''),
                item.get('has_start', False),
                item.get('has_stop', False),
                item.get('has_step', False),
                item.get('is_assignment', False),
                item.get('in_function', ''),
            )
            if 'python_slice_operations' not in self.counts:
                self.counts['python_slice_operations'] = 0
            self.counts['python_slice_operations'] += 1

    def _store_python_tuple_operations(self, file_path: str, python_tuple_operations: list, jsx_pass: bool):
        """Store python tuple operations."""
        for item in python_tuple_operations:
            self.db_manager.add_python_tuple_operation(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('element_count', ''),
                item.get('in_function', ''),
            )
            if 'python_tuple_operations' not in self.counts:
                self.counts['python_tuple_operations'] = 0
            self.counts['python_tuple_operations'] += 1

    def _store_python_unpacking_patterns(self, file_path: str, python_unpacking_patterns: list, jsx_pass: bool):
        """Store python unpacking patterns."""
        for item in python_unpacking_patterns:
            self.db_manager.add_python_unpacking_pattern(
                file_path,
                item.get('line', 0),
                item.get('unpack_type', ''),
                item.get('target_count', ''),
                item.get('has_rest', False),
                item.get('in_function', ''),
            )
            if 'python_unpacking_patterns' not in self.counts:
                self.counts['python_unpacking_patterns'] = 0
            self.counts['python_unpacking_patterns'] += 1

    def _store_python_none_patterns(self, file_path: str, python_none_patterns: list, jsx_pass: bool):
        """Store python none patterns."""
        for item in python_none_patterns:
            self.db_manager.add_python_none_pattern(
                file_path,
                item.get('line', 0),
                item.get('pattern', ''),
                item.get('uses_is', False),
                item.get('in_function', ''),
            )
            if 'python_none_patterns' not in self.counts:
                self.counts['python_none_patterns'] = 0
            self.counts['python_none_patterns'] += 1

    def _store_python_truthiness_patterns(self, file_path: str, python_truthiness_patterns: list, jsx_pass: bool):
        """Store python truthiness patterns."""
        for item in python_truthiness_patterns:
            self.db_manager.add_python_truthiness_pattern(
                file_path,
                item.get('line', 0),
                item.get('pattern', ''),
                item.get('expression', ''),
                item.get('in_function', ''),
            )
            if 'python_truthiness_patterns' not in self.counts:
                self.counts['python_truthiness_patterns'] = 0
            self.counts['python_truthiness_patterns'] += 1

    def _store_python_string_formatting(self, file_path: str, python_string_formatting: list, jsx_pass: bool):
        """Store python string formatting."""
        for item in python_string_formatting:
            self.db_manager.add_python_string_formatting(
                file_path,
                item.get('line', 0),
                item.get('format_type', ''),
                item.get('has_expressions', False),
                item.get('var_count', ''),
                item.get('in_function', ''),
            )
            if 'python_string_formatting' not in self.counts:
                self.counts['python_string_formatting'] = 0
            self.counts['python_string_formatting'] += 1

    def _store_python_operators(self, file_path: str, python_operators: list, jsx_pass: bool):
        """Store python operators."""
        for item in python_operators:
            self.db_manager.add_python_operator(
                file_path,
                item.get('line', 0),
                item.get('operator_type', ''),
                item.get('operator', ''),
                item.get('in_function', ''),
            )
            if 'python_operators' not in self.counts:
                self.counts['python_operators'] = 0
            self.counts['python_operators'] += 1

    def _store_python_membership_tests(self, file_path: str, python_membership_tests: list, jsx_pass: bool):
        """Store python membership tests."""
        for item in python_membership_tests:
            self.db_manager.add_python_membership_test(
                file_path,
                item.get('line', 0),
                item.get('operator', ''),
                item.get('container_type', ''),
                item.get('in_function', ''),
            )
            if 'python_membership_tests' not in self.counts:
                self.counts['python_membership_tests'] = 0
            self.counts['python_membership_tests'] += 1

    def _store_python_chained_comparisons(self, file_path: str, python_chained_comparisons: list, jsx_pass: bool):
        """Store python chained comparisons."""
        for item in python_chained_comparisons:
            self.db_manager.add_python_chained_comparison(
                file_path,
                item.get('line', 0),
                item.get('chain_length', 0),
                item.get('operators', ''),
                item.get('in_function', ''),
            )
            if 'python_chained_comparisons' not in self.counts:
                self.counts['python_chained_comparisons'] = 0
            self.counts['python_chained_comparisons'] += 1

    def _store_python_ternary_expressions(self, file_path: str, python_ternary_expressions: list, jsx_pass: bool):
        """Store python ternary expressions."""
        for item in python_ternary_expressions:
            self.db_manager.add_python_ternary_expression(
                file_path,
                item.get('line', 0),
                item.get('has_complex_condition', False),
                item.get('in_function', ''),
            )
            if 'python_ternary_expressions' not in self.counts:
                self.counts['python_ternary_expressions'] = 0
            self.counts['python_ternary_expressions'] += 1

    def _store_python_walrus_operators(self, file_path: str, python_walrus_operators: list, jsx_pass: bool):
        """Store python walrus operators."""
        for item in python_walrus_operators:
            self.db_manager.add_python_walrus_operator(
                file_path,
                item.get('line', 0),
                item.get('variable', ''),
                item.get('used_in', ''),
                item.get('in_function', ''),
            )
            if 'python_walrus_operators' not in self.counts:
                self.counts['python_walrus_operators'] = 0
            self.counts['python_walrus_operators'] += 1

    def _store_python_matrix_multiplication(self, file_path: str, python_matrix_multiplication: list, jsx_pass: bool):
        """Store python matrix multiplication."""
        for item in python_matrix_multiplication:
            self.db_manager.add_python_matrix_multiplication(
                file_path,
                item.get('line', 0),
                item.get('in_function', ''),
            )
            if 'python_matrix_multiplication' not in self.counts:
                self.counts['python_matrix_multiplication'] = 0
            self.counts['python_matrix_multiplication'] += 1

    def _store_python_dict_operations(self, file_path: str, python_dict_operations: list, jsx_pass: bool):
        """Store python dict operations."""
        for item in python_dict_operations:
            self.db_manager.add_python_dict_operation(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('has_default', False),
                item.get('in_function', ''),
            )
            if 'python_dict_operations' not in self.counts:
                self.counts['python_dict_operations'] = 0
            self.counts['python_dict_operations'] += 1

    def _store_python_list_mutations(self, file_path: str, python_list_mutations: list, jsx_pass: bool):
        """Store python list mutations."""
        for item in python_list_mutations:
            self.db_manager.add_python_list_mutation(
                file_path,
                item.get('line', 0),
                item.get('method', ''),
                item.get('mutates_in_place', False),
                item.get('in_function', ''),
            )
            if 'python_list_mutations' not in self.counts:
                self.counts['python_list_mutations'] = 0
            self.counts['python_list_mutations'] += 1

    def _store_python_set_operations(self, file_path: str, python_set_operations: list, jsx_pass: bool):
        """Store python set operations."""
        for item in python_set_operations:
            self.db_manager.add_python_set_operation(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('in_function', ''),
            )
            if 'python_set_operations' not in self.counts:
                self.counts['python_set_operations'] = 0
            self.counts['python_set_operations'] += 1

    def _store_python_string_methods(self, file_path: str, python_string_methods: list, jsx_pass: bool):
        """Store python string methods."""
        for item in python_string_methods:
            self.db_manager.add_python_string_method(
                file_path,
                item.get('line', 0),
                item.get('method', ''),
                item.get('in_function', ''),
            )
            if 'python_string_methods' not in self.counts:
                self.counts['python_string_methods'] = 0
            self.counts['python_string_methods'] += 1

    def _store_python_builtin_usage(self, file_path: str, python_builtin_usage: list, jsx_pass: bool):
        """Store python builtin usage."""
        for item in python_builtin_usage:
            self.db_manager.add_python_builtin_usage(
                file_path,
                item.get('line', 0),
                item.get('builtin', ''),
                item.get('has_key', False),
                item.get('in_function', ''),
            )
            if 'python_builtin_usage' not in self.counts:
                self.counts['python_builtin_usage'] = 0
            self.counts['python_builtin_usage'] += 1

    def _store_python_itertools_usage(self, file_path: str, python_itertools_usage: list, jsx_pass: bool):
        """Store python itertools usage."""
        for item in python_itertools_usage:
            self.db_manager.add_python_itertools_usage(
                file_path,
                item.get('line', 0),
                item.get('function', ''),
                item.get('is_infinite', False),
                item.get('in_function', ''),
            )
            if 'python_itertools_usage' not in self.counts:
                self.counts['python_itertools_usage'] = 0
            self.counts['python_itertools_usage'] += 1

    def _store_python_functools_usage(self, file_path: str, python_functools_usage: list, jsx_pass: bool):
        """Store python functools usage."""
        for item in python_functools_usage:
            self.db_manager.add_python_functools_usage(
                file_path,
                item.get('line', 0),
                item.get('function', ''),
                item.get('is_decorator', False),
                item.get('in_function', ''),
            )
            if 'python_functools_usage' not in self.counts:
                self.counts['python_functools_usage'] = 0
            self.counts['python_functools_usage'] += 1

    def _store_python_collections_usage(self, file_path: str, python_collections_usage: list, jsx_pass: bool):
        """Store python collections usage."""
        for item in python_collections_usage:
            self.db_manager.add_python_collections_usage(
                file_path,
                item.get('line', 0),
                item.get('collection_type', ''),
                item.get('default_factory', ''),
                item.get('in_function', ''),
            )
            if 'python_collections_usage' not in self.counts:
                self.counts['python_collections_usage'] = 0
            self.counts['python_collections_usage'] += 1

    def _store_python_metaclasses(self, file_path: str, python_metaclasses: list, jsx_pass: bool):
        """Store python metaclasses."""
        for item in python_metaclasses:
            self.db_manager.add_python_metaclasse(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('metaclass_name', ''),
                item.get('is_definition', False),
            )
            if 'python_metaclasses' not in self.counts:
                self.counts['python_metaclasses'] = 0
            self.counts['python_metaclasses'] += 1

    def _store_python_descriptors(self, file_path: str, python_descriptors: list, jsx_pass: bool):
        """Store python descriptors."""
        for item in python_descriptors:
            self.db_manager.add_python_descriptor(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('has_get', False),
                item.get('has_set', False),
                item.get('has_delete', False),
                item.get('descriptor_type', ''),
            )
            if 'python_descriptors' not in self.counts:
                self.counts['python_descriptors'] = 0
            self.counts['python_descriptors'] += 1

    def _store_python_dataclasses(self, file_path: str, python_dataclasses: list, jsx_pass: bool):
        """Store python dataclasses."""
        for item in python_dataclasses:
            self.db_manager.add_python_dataclasse(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('frozen', False),
                item.get('field_count', ''),
            )
            if 'python_dataclasses' not in self.counts:
                self.counts['python_dataclasses'] = 0
            self.counts['python_dataclasses'] += 1

    def _store_python_enums(self, file_path: str, python_enums: list, jsx_pass: bool):
        """Store python enums."""
        for item in python_enums:
            self.db_manager.add_python_enum(
                file_path,
                item.get('line', 0),
                item.get('enum_name', ''),
                item.get('enum_type', ''),
                item.get('member_count', ''),
            )
            if 'python_enums' not in self.counts:
                self.counts['python_enums'] = 0
            self.counts['python_enums'] += 1

    def _store_python_slots(self, file_path: str, python_slots: list, jsx_pass: bool):
        """Store python slots."""
        for item in python_slots:
            self.db_manager.add_python_slot(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('slot_count', ''),
            )
            if 'python_slots' not in self.counts:
                self.counts['python_slots'] = 0
            self.counts['python_slots'] += 1

    def _store_python_abstract_classes(self, file_path: str, python_abstract_classes: list, jsx_pass: bool):
        """Store python abstract classes."""
        for item in python_abstract_classes:
            self.db_manager.add_python_abstract_classe(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('abstract_method_count', ''),
            )
            if 'python_abstract_classes' not in self.counts:
                self.counts['python_abstract_classes'] = 0
            self.counts['python_abstract_classes'] += 1

    def _store_python_method_types(self, file_path: str, python_method_types: list, jsx_pass: bool):
        """Store python method types."""
        for item in python_method_types:
            self.db_manager.add_python_method_type(
                file_path,
                item.get('line', 0),
                item.get('method_name', ''),
                item.get('method_type', ''),
                item.get('in_class', ''),
            )
            if 'python_method_types' not in self.counts:
                self.counts['python_method_types'] = 0
            self.counts['python_method_types'] += 1

    def _store_python_multiple_inheritance(self, file_path: str, python_multiple_inheritance: list, jsx_pass: bool):
        """Store python multiple inheritance."""
        for item in python_multiple_inheritance:
            self.db_manager.add_python_multiple_inheritance(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('base_count', 0),
                item.get('base_classes', ''),
            )
            if 'python_multiple_inheritance' not in self.counts:
                self.counts['python_multiple_inheritance'] = 0
            self.counts['python_multiple_inheritance'] += 1

    def _store_python_dunder_methods(self, file_path: str, python_dunder_methods: list, jsx_pass: bool):
        """Store python dunder methods."""
        for item in python_dunder_methods:
            self.db_manager.add_python_dunder_method(
                file_path,
                item.get('line', 0),
                item.get('method_name', ''),
                item.get('category', ''),
                item.get('in_class', ''),
            )
            if 'python_dunder_methods' not in self.counts:
                self.counts['python_dunder_methods'] = 0
            self.counts['python_dunder_methods'] += 1

    def _store_python_visibility_conventions(self, file_path: str, python_visibility_conventions: list, jsx_pass: bool):
        """Store python visibility conventions."""
        for item in python_visibility_conventions:
            self.db_manager.add_python_visibility_convention(
                file_path,
                item.get('line', 0),
                item.get('name', ''),
                item.get('visibility', ''),
                item.get('is_name_mangled', False),
                item.get('in_class', ''),
            )
            if 'python_visibility_conventions' not in self.counts:
                self.counts['python_visibility_conventions'] = 0
            self.counts['python_visibility_conventions'] += 1

    def _store_python_regex_patterns(self, file_path: str, python_regex_patterns: list, jsx_pass: bool):
        """Store python regex patterns."""
        for item in python_regex_patterns:
            self.db_manager.add_python_regex_pattern(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('has_flags', False),
                item.get('in_function', ''),
            )
            if 'python_regex_patterns' not in self.counts:
                self.counts['python_regex_patterns'] = 0
            self.counts['python_regex_patterns'] += 1

    def _store_python_json_operations(self, file_path: str, python_json_operations: list, jsx_pass: bool):
        """Store python json operations."""
        for item in python_json_operations:
            self.db_manager.add_python_json_operation(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('direction', ''),
                item.get('in_function', ''),
            )
            if 'python_json_operations' not in self.counts:
                self.counts['python_json_operations'] = 0
            self.counts['python_json_operations'] += 1

    def _store_python_datetime_operations(self, file_path: str, python_datetime_operations: list, jsx_pass: bool):
        """Store python datetime operations."""
        for item in python_datetime_operations:
            self.db_manager.add_python_datetime_operation(
                file_path,
                item.get('line', 0),
                item.get('datetime_type', ''),
                item.get('in_function', ''),
            )
            if 'python_datetime_operations' not in self.counts:
                self.counts['python_datetime_operations'] = 0
            self.counts['python_datetime_operations'] += 1

    def _store_python_path_operations(self, file_path: str, python_path_operations: list, jsx_pass: bool):
        """Store python path operations."""
        for item in python_path_operations:
            self.db_manager.add_python_path_operation(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('path_type', ''),
                item.get('in_function', ''),
            )
            if 'python_path_operations' not in self.counts:
                self.counts['python_path_operations'] = 0
            self.counts['python_path_operations'] += 1

    def _store_python_logging_patterns(self, file_path: str, python_logging_patterns: list, jsx_pass: bool):
        """Store python logging patterns."""
        for item in python_logging_patterns:
            self.db_manager.add_python_logging_pattern(
                file_path,
                item.get('line', 0),
                item.get('log_level', ''),
                item.get('in_function', ''),
            )
            if 'python_logging_patterns' not in self.counts:
                self.counts['python_logging_patterns'] = 0
            self.counts['python_logging_patterns'] += 1

    def _store_python_threading_patterns(self, file_path: str, python_threading_patterns: list, jsx_pass: bool):
        """Store python threading patterns."""
        for item in python_threading_patterns:
            self.db_manager.add_python_threading_pattern(
                file_path,
                item.get('line', 0),
                item.get('threading_type', ''),
                item.get('in_function', ''),
            )
            if 'python_threading_patterns' not in self.counts:
                self.counts['python_threading_patterns'] = 0
            self.counts['python_threading_patterns'] += 1

    def _store_python_contextlib_patterns(self, file_path: str, python_contextlib_patterns: list, jsx_pass: bool):
        """Store python contextlib patterns."""
        for item in python_contextlib_patterns:
            self.db_manager.add_python_contextlib_pattern(
                file_path,
                item.get('line', 0),
                item.get('pattern', ''),
                item.get('is_decorator', False),
                item.get('in_function', ''),
            )
            if 'python_contextlib_patterns' not in self.counts:
                self.counts['python_contextlib_patterns'] = 0
            self.counts['python_contextlib_patterns'] += 1

    def _store_python_type_checking(self, file_path: str, python_type_checking: list, jsx_pass: bool):
        """Store python type checking."""
        for item in python_type_checking:
            self.db_manager.add_python_type_checking(
                file_path,
                item.get('line', 0),
                item.get('check_type', ''),
                item.get('in_function', ''),
            )
            if 'python_type_checking' not in self.counts:
                self.counts['python_type_checking'] = 0
            self.counts['python_type_checking'] += 1

    # Python Coverage V2 - Week 5: Control Flow (10)

    def _store_python_for_loops(self, file_path: str, python_for_loops: list, jsx_pass: bool):
        """Store python for loops."""
        for item in python_for_loops:
            self.db_manager.add_python_for_loop(
                file_path,
                item.get('line', 0),
                item.get('loop_type', ''),
                item.get('has_else', False),
                item.get('nesting_level', 0),
                item.get('target_count', 0),
                item.get('in_function', ''),
            )
            if 'python_for_loops' not in self.counts:
                self.counts['python_for_loops'] = 0
            self.counts['python_for_loops'] += 1

    def _store_python_while_loops(self, file_path: str, python_while_loops: list, jsx_pass: bool):
        """Store python while loops."""
        for item in python_while_loops:
            self.db_manager.add_python_while_loop(
                file_path,
                item.get('line', 0),
                item.get('has_else', False),
                item.get('is_infinite', False),
                item.get('nesting_level', 0),
                item.get('in_function', ''),
            )
            if 'python_while_loops' not in self.counts:
                self.counts['python_while_loops'] = 0
            self.counts['python_while_loops'] += 1

    def _store_python_async_for_loops(self, file_path: str, python_async_for_loops: list, jsx_pass: bool):
        """Store python async for loops."""
        for item in python_async_for_loops:
            self.db_manager.add_python_async_for_loop(
                file_path,
                item.get('line', 0),
                item.get('has_else', False),
                item.get('target_count', 0),
                item.get('in_function', ''),
            )
            if 'python_async_for_loops' not in self.counts:
                self.counts['python_async_for_loops'] = 0
            self.counts['python_async_for_loops'] += 1

    def _store_python_if_statements(self, file_path: str, python_if_statements: list, jsx_pass: bool):
        """Store python if statements."""
        for item in python_if_statements:
            self.db_manager.add_python_if_statement(
                file_path,
                item.get('line', 0),
                item.get('has_elif', False),
                item.get('has_else', False),
                item.get('chain_length', 0),
                item.get('nesting_level', 0),
                item.get('has_complex_condition', False),
                item.get('in_function', ''),
            )
            if 'python_if_statements' not in self.counts:
                self.counts['python_if_statements'] = 0
            self.counts['python_if_statements'] += 1

    def _store_python_match_statements(self, file_path: str, python_match_statements: list, jsx_pass: bool):
        """Store python match statements."""
        for item in python_match_statements:
            self.db_manager.add_python_match_statement(
                file_path,
                item.get('line', 0),
                item.get('case_count', 0),
                item.get('has_wildcard', False),
                item.get('has_guards', False),
                item.get('pattern_types', ''),
                item.get('in_function', ''),
            )
            if 'python_match_statements' not in self.counts:
                self.counts['python_match_statements'] = 0
            self.counts['python_match_statements'] += 1

    def _store_python_break_continue_pass(self, file_path: str, python_break_continue_pass: list, jsx_pass: bool):
        """Store python break/continue/pass statements."""
        for item in python_break_continue_pass:
            self.db_manager.add_python_break_continue_pass(
                file_path,
                item.get('line', 0),
                item.get('statement_type', ''),
                item.get('loop_type', ''),
                item.get('in_function', ''),
            )
            if 'python_break_continue_pass' not in self.counts:
                self.counts['python_break_continue_pass'] = 0
            self.counts['python_break_continue_pass'] += 1

    def _store_python_assert_statements(self, file_path: str, python_assert_statements: list, jsx_pass: bool):
        """Store python assert statements."""
        for item in python_assert_statements:
            self.db_manager.add_python_assert_statement(
                file_path,
                item.get('line', 0),
                item.get('has_message', False),
                item.get('condition_type', ''),
                item.get('in_function', ''),
            )
            if 'python_assert_statements' not in self.counts:
                self.counts['python_assert_statements'] = 0
            self.counts['python_assert_statements'] += 1

    def _store_python_del_statements(self, file_path: str, python_del_statements: list, jsx_pass: bool):
        """Store python del statements."""
        for item in python_del_statements:
            self.db_manager.add_python_del_statement(
                file_path,
                item.get('line', 0),
                item.get('target_type', ''),
                item.get('target_count', 0),
                item.get('in_function', ''),
            )
            if 'python_del_statements' not in self.counts:
                self.counts['python_del_statements'] = 0
            self.counts['python_del_statements'] += 1

    def _store_python_import_statements(self, file_path: str, python_import_statements: list, jsx_pass: bool):
        """Store python import statements."""
        for item in python_import_statements:
            self.db_manager.add_python_import_statement(
                file_path,
                item.get('line', 0),
                item.get('import_type', ''),
                item.get('module', ''),
                item.get('has_alias', False),
                item.get('is_wildcard', False),
                item.get('relative_level', 0),
                item.get('imported_names', ''),
                item.get('in_function', ''),
            )
            if 'python_import_statements' not in self.counts:
                self.counts['python_import_statements'] = 0
            self.counts['python_import_statements'] += 1

    def _store_python_with_statements(self, file_path: str, python_with_statements: list, jsx_pass: bool):
        """Store python with statements."""
        for item in python_with_statements:
            self.db_manager.add_python_with_statement(
                file_path,
                item.get('line', 0),
                item.get('is_async', False),
                item.get('context_count', 0),
                item.get('has_alias', False),
                item.get('in_function', ''),
            )
            if 'python_with_statements' not in self.counts:
                self.counts['python_with_statements'] = 0
            self.counts['python_with_statements'] += 1

    # Python Coverage V2 - Week 6: Protocol Patterns (10)

    def _store_python_iterator_protocol(self, file_path: str, python_iterator_protocol: list, jsx_pass: bool):
        """Store python iterator protocol."""
        for item in python_iterator_protocol:
            self.db_manager.add_python_iterator_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('has_iter', False),
                item.get('has_next', False),
                item.get('raises_stopiteration', False),
                item.get('is_generator', False),
            )
            if 'python_iterator_protocol' not in self.counts:
                self.counts['python_iterator_protocol'] = 0
            self.counts['python_iterator_protocol'] += 1

    def _store_python_container_protocol(self, file_path: str, python_container_protocol: list, jsx_pass: bool):
        """Store python container protocol."""
        for item in python_container_protocol:
            self.db_manager.add_python_container_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('has_len', False),
                item.get('has_getitem', False),
                item.get('has_setitem', False),
                item.get('has_delitem', False),
                item.get('has_contains', False),
                item.get('is_sequence', False),
                item.get('is_mapping', False),
            )
            if 'python_container_protocol' not in self.counts:
                self.counts['python_container_protocol'] = 0
            self.counts['python_container_protocol'] += 1

    def _store_python_callable_protocol(self, file_path: str, python_callable_protocol: list, jsx_pass: bool):
        """Store python callable protocol."""
        for item in python_callable_protocol:
            self.db_manager.add_python_callable_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('param_count', 0),
                item.get('has_args', False),
                item.get('has_kwargs', False),
            )
            if 'python_callable_protocol' not in self.counts:
                self.counts['python_callable_protocol'] = 0
            self.counts['python_callable_protocol'] += 1

    def _store_python_comparison_protocol(self, file_path: str, python_comparison_protocol: list, jsx_pass: bool):
        """Store python comparison protocol."""
        for item in python_comparison_protocol:
            self.db_manager.add_python_comparison_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('methods', ''),
                item.get('is_total_ordering', False),
                item.get('has_all_rich', False),
            )
            if 'python_comparison_protocol' not in self.counts:
                self.counts['python_comparison_protocol'] = 0
            self.counts['python_comparison_protocol'] += 1

    def _store_python_arithmetic_protocol(self, file_path: str, python_arithmetic_protocol: list, jsx_pass: bool):
        """Store python arithmetic protocol."""
        for item in python_arithmetic_protocol:
            self.db_manager.add_python_arithmetic_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('methods', ''),
                item.get('has_reflected', False),
                item.get('has_inplace', False),
            )
            if 'python_arithmetic_protocol' not in self.counts:
                self.counts['python_arithmetic_protocol'] = 0
            self.counts['python_arithmetic_protocol'] += 1

    def _store_python_pickle_protocol(self, file_path: str, python_pickle_protocol: list, jsx_pass: bool):
        """Store python pickle protocol."""
        for item in python_pickle_protocol:
            self.db_manager.add_python_pickle_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('has_getstate', False),
                item.get('has_setstate', False),
                item.get('has_reduce', False),
                item.get('has_reduce_ex', False),
            )
            if 'python_pickle_protocol' not in self.counts:
                self.counts['python_pickle_protocol'] = 0
            self.counts['python_pickle_protocol'] += 1

    def _store_python_weakref_usage(self, file_path: str, python_weakref_usage: list, jsx_pass: bool):
        """Store python weakref usage."""
        for item in python_weakref_usage:
            self.db_manager.add_python_weakref_usage(
                file_path,
                item.get('line', 0),
                item.get('usage_type', ''),
                item.get('in_function', ''),
            )
            if 'python_weakref_usage' not in self.counts:
                self.counts['python_weakref_usage'] = 0
            self.counts['python_weakref_usage'] += 1

    def _store_python_contextvar_usage(self, file_path: str, python_contextvar_usage: list, jsx_pass: bool):
        """Store python contextvar usage."""
        for item in python_contextvar_usage:
            self.db_manager.add_python_contextvar_usage(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('in_function', ''),
            )
            if 'python_contextvar_usage' not in self.counts:
                self.counts['python_contextvar_usage'] = 0
            self.counts['python_contextvar_usage'] += 1

    def _store_python_module_attributes(self, file_path: str, python_module_attributes: list, jsx_pass: bool):
        """Store python module attributes."""
        for item in python_module_attributes:
            self.db_manager.add_python_module_attribute(
                file_path,
                item.get('line', 0),
                item.get('attribute', ''),
                item.get('usage_type', ''),
                item.get('in_function', ''),
            )
            if 'python_module_attributes' not in self.counts:
                self.counts['python_module_attributes'] = 0
            self.counts['python_module_attributes'] += 1

    def _store_python_class_decorators(self, file_path: str, python_class_decorators: list, jsx_pass: bool):
        """Store python class decorators."""
        for item in python_class_decorators:
            self.db_manager.add_python_class_decorator(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('decorator', ''),
                item.get('decorator_type', ''),
                item.get('has_arguments', False),
            )
            if 'python_class_decorators' not in self.counts:
                self.counts['python_class_decorators'] = 0
            self.counts['python_class_decorators'] += 1

    # Python Coverage V2 - Advanced Patterns (8)

    def _store_python_namespace_packages(self, file_path: str, python_namespace_packages: list, jsx_pass: bool):
        """Store python namespace packages."""
        for item in python_namespace_packages:
            self.db_manager.add_python_namespace_package(
                file_path,
                item.get('line', 0),
                item.get('pattern', ''),
                item.get('in_function', ''),
            )
            if 'python_namespace_packages' not in self.counts:
                self.counts['python_namespace_packages'] = 0
            self.counts['python_namespace_packages'] += 1

    def _store_python_cached_property(self, file_path: str, python_cached_property: list, jsx_pass: bool):
        """Store python cached property."""
        for item in python_cached_property:
            self.db_manager.add_python_cached_property(
                file_path,
                item.get('line', 0),
                item.get('method_name', ''),
                item.get('in_class', ''),
                item.get('is_functools', False),
            )
            if 'python_cached_property' not in self.counts:
                self.counts['python_cached_property'] = 0
            self.counts['python_cached_property'] += 1

    def _store_python_descriptor_protocol(self, file_path: str, python_descriptor_protocol: list, jsx_pass: bool):
        """Store python descriptor protocol."""
        for item in python_descriptor_protocol:
            self.db_manager.add_python_descriptor_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('has_get', False),
                item.get('has_set', False),
                item.get('has_delete', False),
                item.get('is_data_descriptor', False),
            )
            if 'python_descriptor_protocol' not in self.counts:
                self.counts['python_descriptor_protocol'] = 0
            self.counts['python_descriptor_protocol'] += 1

    def _store_python_attribute_access_protocol(self, file_path: str, python_attribute_access_protocol: list, jsx_pass: bool):
        """Store python attribute access protocol."""
        for item in python_attribute_access_protocol:
            self.db_manager.add_python_attribute_access_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('has_getattr', False),
                item.get('has_setattr', False),
                item.get('has_delattr', False),
                item.get('has_getattribute', False),
            )
            if 'python_attribute_access_protocol' not in self.counts:
                self.counts['python_attribute_access_protocol'] = 0
            self.counts['python_attribute_access_protocol'] += 1

    def _store_python_copy_protocol(self, file_path: str, python_copy_protocol: list, jsx_pass: bool):
        """Store python copy protocol."""
        for item in python_copy_protocol:
            self.db_manager.add_python_copy_protocol(
                file_path,
                item.get('line', 0),
                item.get('class_name', ''),
                item.get('has_copy', False),
                item.get('has_deepcopy', False),
            )
            if 'python_copy_protocol' not in self.counts:
                self.counts['python_copy_protocol'] = 0
            self.counts['python_copy_protocol'] += 1

    def _store_python_ellipsis_usage(self, file_path: str, python_ellipsis_usage: list, jsx_pass: bool):
        """Store python ellipsis usage."""
        for item in python_ellipsis_usage:
            self.db_manager.add_python_ellipsis_usage(
                file_path,
                item.get('line', 0),
                item.get('context', ''),
                item.get('in_function', ''),
            )
            if 'python_ellipsis_usage' not in self.counts:
                self.counts['python_ellipsis_usage'] = 0
            self.counts['python_ellipsis_usage'] += 1

    def _store_python_bytes_operations(self, file_path: str, python_bytes_operations: list, jsx_pass: bool):
        """Store python bytes operations."""
        for item in python_bytes_operations:
            self.db_manager.add_python_bytes_operation(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('in_function', ''),
            )
            if 'python_bytes_operations' not in self.counts:
                self.counts['python_bytes_operations'] = 0
            self.counts['python_bytes_operations'] += 1

    def _store_python_exec_eval_compile(self, file_path: str, python_exec_eval_compile: list, jsx_pass: bool):
        """Store python exec/eval/compile usage."""
        for item in python_exec_eval_compile:
            self.db_manager.add_python_exec_eval_compile(
                file_path,
                item.get('line', 0),
                item.get('operation', ''),
                item.get('has_globals', False),
                item.get('has_locals', False),
                item.get('in_function', ''),
            )
            if 'python_exec_eval_compile' not in self.counts:
                self.counts['python_exec_eval_compile'] = 0
            self.counts['python_exec_eval_compile'] += 1

