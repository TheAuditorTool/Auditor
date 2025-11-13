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

    def __init__(self, db_manager, counts: Dict[str, int]):
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
        }

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

    # Flask Framework (Phase 3.1) storage methods

    def _store_python_flask_apps(self, file_path: str, python_flask_apps: List, jsx_pass: bool):
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

    def _store_python_flask_extensions(self, file_path: str, python_flask_extensions: List, jsx_pass: bool):
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

    def _store_python_flask_hooks(self, file_path: str, python_flask_hooks: List, jsx_pass: bool):
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

    def _store_python_flask_error_handlers(self, file_path: str, python_flask_error_handlers: List, jsx_pass: bool):
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

    def _store_python_flask_websockets(self, file_path: str, python_flask_websockets: List, jsx_pass: bool):
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

    def _store_python_flask_cli_commands(self, file_path: str, python_flask_cli_commands: List, jsx_pass: bool):
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

    def _store_python_flask_cors(self, file_path: str, python_flask_cors: List, jsx_pass: bool):
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

    def _store_python_flask_rate_limits(self, file_path: str, python_flask_rate_limits: List, jsx_pass: bool):
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

    def _store_python_flask_cache(self, file_path: str, python_flask_cache: List, jsx_pass: bool):
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

    def _store_python_unittest_test_cases(self, file_path: str, python_unittest_test_cases: List, jsx_pass: bool):
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

    def _store_python_assertion_patterns(self, file_path: str, python_assertion_patterns: List, jsx_pass: bool):
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

    def _store_python_pytest_plugin_hooks(self, file_path: str, python_pytest_plugin_hooks: List, jsx_pass: bool):
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

    def _store_python_hypothesis_strategies(self, file_path: str, python_hypothesis_strategies: List, jsx_pass: bool):
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

    def _store_python_auth_decorators(self, file_path: str, python_auth_decorators: List, jsx_pass: bool):
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

    def _store_python_password_hashing(self, file_path: str, python_password_hashing: List, jsx_pass: bool):
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

    def _store_python_jwt_operations(self, file_path: str, python_jwt_operations: List, jsx_pass: bool):
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

    def _store_python_sql_injection(self, file_path: str, python_sql_injection: List, jsx_pass: bool):
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

    def _store_python_command_injection(self, file_path: str, python_command_injection: List, jsx_pass: bool):
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

    def _store_python_path_traversal(self, file_path: str, python_path_traversal: List, jsx_pass: bool):
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

    def _store_python_dangerous_eval(self, file_path: str, python_dangerous_eval: List, jsx_pass: bool):
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

    def _store_python_crypto_operations(self, file_path: str, python_crypto_operations: List, jsx_pass: bool):
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

    def _store_python_django_signals(self, file_path: str, python_django_signals: List, jsx_pass: bool):
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

    def _store_python_django_receivers(self, file_path: str, python_django_receivers: List, jsx_pass: bool):
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

    def _store_python_django_managers(self, file_path: str, python_django_managers: List, jsx_pass: bool):
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

    def _store_python_django_querysets(self, file_path: str, python_django_querysets: List, jsx_pass: bool):
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

    def _store_python_instance_mutations(self, file_path: str, python_instance_mutations: List, jsx_pass: bool):
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