"""Python-specific database operations.

This module contains add_* methods for PYTHON_TABLES defined in schemas/python_schema.py.
Handles 34 Python-specific tables including ORM models, routes, decorators, async patterns,
testing frameworks (pytest), validation frameworks (Pydantic, Marshmallow, WTForms),
web frameworks (Django, DRF), and task queues (Celery).
"""

import json
from typing import List, Optional


class PythonDatabaseMixin:
    """Mixin providing add_* methods for PYTHON_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    def add_python_orm_model(self, file_path: str, line: int, model_name: str,
                             table_name: Optional[str], orm_type: str = 'sqlalchemy'):
        """Add a Python ORM model definition to the batch."""
        self.generic_batches['python_orm_models'].append((file_path, line, model_name, table_name, orm_type))

    def add_python_orm_field(self, file_path: str, line: int, model_name: str,
                             field_name: str, field_type: Optional[str],
                             is_primary_key: bool = False, is_foreign_key: bool = False,
                             foreign_key_target: Optional[str] = None):
        """Add a Python ORM field definition to the batch."""
        self.generic_batches['python_orm_fields'].append((
            file_path,
            line,
            model_name,
            field_name,
            field_type,
            1 if is_primary_key else 0,
            1 if is_foreign_key else 0,
            foreign_key_target
        ))

    def add_python_route(self, file_path: str, line: int, framework: str, method: str,
                         pattern: str, handler_function: str, has_auth: bool = False,
                         dependencies: Optional[List[str]] = None, blueprint: Optional[str] = None):
        """Add a Python framework route (Flask/FastAPI) to the batch."""
        dependencies_json = json.dumps(dependencies) if dependencies else None
        self.generic_batches['python_routes'].append((
            file_path,
            line,
            framework,
            method,
            pattern,
            handler_function,
            1 if has_auth else 0,
            dependencies_json,
            blueprint
        ))

    def add_python_blueprint(self, file_path: str, line: int, blueprint_name: str,
                             url_prefix: Optional[str], subdomain: Optional[str]):
        """Add a Flask blueprint definition to the batch."""
        self.generic_batches['python_blueprints'].append((
            file_path,
            line,
            blueprint_name,
            url_prefix,
            subdomain
        ))

    def add_python_validator(self, file_path: str, line: int, model_name: str,
                             field_name: Optional[str], validator_method: str,
                             validator_type: str):
        """Add a Pydantic validator definition to the batch."""
        self.generic_batches['python_validators'].append((
            file_path,
            line,
            model_name,
            field_name,
            validator_method,
            validator_type
        ))

    # Phase 2.2: Advanced Python pattern add_* methods

    def add_python_decorator(self, file_path: str, line: int, decorator_name: str,
                            decorator_type: str, target_type: str, target_name: str,
                            is_async: bool):
        """Add a Python decorator usage to the batch."""
        self.generic_batches['python_decorators'].append((
            file_path,
            line,
            decorator_name,
            decorator_type,
            target_type,
            target_name,
            1 if is_async else 0
        ))

    def add_python_instance_mutation(self, file_path: str, line: int, target: str,
                                     operation: str, in_function: str, is_init: bool,
                                     is_property_setter: bool, is_dunder_method: bool):
        """Add Python instance attribute mutation (Causal Learning - Week 1)."""
        self.generic_batches['python_instance_mutations'].append((
            file_path,
            line,
            target,
            operation,
            in_function,
            1 if is_init else 0,
            1 if is_property_setter else 0,
            1 if is_dunder_method else 0
        ))

    def add_python_class_mutation(self, file_path: str, line: int, class_name: str,
                                   attribute: str, operation: str, in_function: str,
                                   is_classmethod: bool):
        """Add Python class attribute mutation (Causal Learning - Week 1)."""
        self.generic_batches['python_class_mutations'].append((
            file_path,
            line,
            class_name,
            attribute,
            operation,
            in_function,
            1 if is_classmethod else 0
        ))

    def add_python_global_mutation(self, file_path: str, line: int, global_name: str,
                                    operation: str, in_function: str):
        """Add Python global variable mutation (Causal Learning - Week 1)."""
        self.generic_batches['python_global_mutations'].append((
            file_path,
            line,
            global_name,
            operation,
            in_function
        ))

    def add_python_argument_mutation(self, file_path: str, line: int, parameter_name: str,
                                      mutation_type: str, mutation_detail: str, in_function: str):
        """Add Python argument mutation (Causal Learning - Week 1)."""
        self.generic_batches['python_argument_mutations'].append((
            file_path,
            line,
            parameter_name,
            mutation_type,
            mutation_detail,
            in_function
        ))

    def add_python_augmented_assignment(self, file_path: str, line: int, target: str,
                                         operator: str, target_type: str, in_function: str):
        """Add Python augmented assignment (Causal Learning - Week 1)."""
        self.generic_batches['python_augmented_assignments'].append((
            file_path,
            line,
            target,
            operator,
            target_type,
            in_function
        ))

    def add_python_context_manager(self, file_path: str, line: int, context_type: str,
                                   context_expr: Optional[str], as_name: Optional[str],
                                   is_async: bool, is_custom: bool):
        """Add a Python context manager usage to the batch."""
        self.generic_batches['python_context_managers'].append((
            file_path,
            line,
            context_type,
            context_expr,
            as_name,
            1 if is_async else 0,
            1 if is_custom else 0
        ))

    def add_python_async_function(self, file_path: str, line: int, function_name: str,
                                  has_await: bool, await_count: int,
                                  has_async_with: bool, has_async_for: bool):
        """Add a Python async function to the batch."""
        self.generic_batches['python_async_functions'].append((
            file_path,
            line,
            function_name,
            1 if has_await else 0,
            await_count,
            1 if has_async_with else 0,
            1 if has_async_for else 0
        ))

    def add_python_await_expression(self, file_path: str, line: int, await_expr: str,
                                    containing_function: Optional[str]):
        """Add a Python await expression to the batch."""
        self.generic_batches['python_await_expressions'].append((
            file_path,
            line,
            await_expr,
            containing_function
        ))

    def add_python_async_generator(self, file_path: str, line: int, generator_type: str,
                                   target_vars: Optional[str], iterable_expr: Optional[str],
                                   function_name: Optional[str]):
        """Add a Python async generator pattern to the batch."""
        self.generic_batches['python_async_generators'].append((
            file_path,
            line,
            generator_type,
            target_vars,
            iterable_expr,
            function_name
        ))

    def add_python_pytest_fixture(self, file_path: str, line: int, fixture_name: str,
                                  scope: str, has_autouse: bool, has_params: bool):
        """Add a pytest fixture to the batch."""
        self.generic_batches['python_pytest_fixtures'].append((
            file_path,
            line,
            fixture_name,
            scope,
            1 if has_autouse else 0,
            1 if has_params else 0
        ))

    def add_python_pytest_parametrize(self, file_path: str, line: int, test_function: str,
                                      parameter_names: str, argvalues_count: int):
        """Add a pytest parametrize decorator to the batch."""
        self.generic_batches['python_pytest_parametrize'].append((
            file_path,
            line,
            test_function,
            parameter_names,
            argvalues_count
        ))

    def add_python_pytest_marker(self, file_path: str, line: int, test_function: str,
                                 marker_name: str, marker_args: Optional[str]):
        """Add a pytest marker to the batch."""
        self.generic_batches['python_pytest_markers'].append((
            file_path,
            line,
            test_function,
            marker_name,
            marker_args
        ))

    def add_python_mock_pattern(self, file_path: str, line: int, mock_type: str,
                                target: Optional[str], in_function: Optional[str],
                                is_decorator: bool):
        """Add a Python mock pattern to the batch."""
        self.generic_batches['python_mock_patterns'].append((
            file_path,
            line,
            mock_type,
            target,
            in_function,
            1 if is_decorator else 0
        ))

    def add_python_protocol(self, file_path: str, line: int, protocol_name: str,
                           methods: str, is_runtime_checkable: bool):
        """Add a Python Protocol class to the batch."""
        self.generic_batches['python_protocols'].append((
            file_path,
            line,
            protocol_name,
            methods,
            1 if is_runtime_checkable else 0
        ))

    def add_python_generic(self, file_path: str, line: int, class_name: str,
                          type_params: Optional[str]):
        """Add a Python Generic class to the batch."""
        self.generic_batches['python_generics'].append((
            file_path,
            line,
            class_name,
            type_params
        ))

    def add_python_typed_dict(self, file_path: str, line: int, typeddict_name: str,
                             fields: str):
        """Add a Python TypedDict to the batch."""
        self.generic_batches['python_typed_dicts'].append((
            file_path,
            line,
            typeddict_name,
            fields
        ))

    def add_python_literal(self, file_path: str, line: int, usage_context: str,
                          name: Optional[str], literal_type: str):
        """Add a Python Literal type usage to the batch."""
        self.generic_batches['python_literals'].append((
            file_path,
            line,
            usage_context,
            name,
            literal_type
        ))

    def add_python_overload(self, file_path: str, function_name: str, overload_count: int,
                           variants: str):
        """Add a Python @overload function to the batch."""
        self.generic_batches['python_overloads'].append((
            file_path,
            function_name,
            overload_count,
            variants
        ))

    def add_python_django_view(self, file_path: str, line: int, view_class_name: str,
                              view_type: str, base_view_class: Optional[str],
                              model_name: Optional[str], template_name: Optional[str],
                              has_permission_check: bool, http_method_names: Optional[str],
                              has_get_queryset_override: bool):
        """Add a Django Class-Based View to the batch."""
        self.generic_batches['python_django_views'].append((
            file_path,
            line,
            view_class_name,
            view_type,
            base_view_class,
            model_name,
            template_name,
            1 if has_permission_check else 0,
            http_method_names,
            1 if has_get_queryset_override else 0
        ))

    def add_python_django_form(self, file_path: str, line: int, form_class_name: str,
                               is_model_form: bool, model_name: Optional[str],
                               field_count: int, has_custom_clean: bool):
        """Add a Django Form or ModelForm to the batch."""
        self.generic_batches['python_django_forms'].append((
            file_path,
            line,
            form_class_name,
            1 if is_model_form else 0,
            model_name,
            field_count,
            1 if has_custom_clean else 0
        ))

    def add_python_django_form_field(self, file_path: str, line: int, form_class_name: str,
                                     field_name: str, field_type: str,
                                     required: bool, max_length: Optional[int],
                                     has_custom_validator: bool):
        """Add a Django form field to the batch."""
        self.generic_batches['python_django_form_fields'].append((
            file_path,
            line,
            form_class_name,
            field_name,
            field_type,
            1 if required else 0,
            max_length,
            1 if has_custom_validator else 0
        ))

    def add_python_django_admin(self, file_path: str, line: int, admin_class_name: str,
                                model_name: Optional[str], list_display: Optional[str],
                                list_filter: Optional[str], search_fields: Optional[str],
                                readonly_fields: Optional[str], has_custom_actions: bool):
        """Add a Django ModelAdmin configuration to the batch."""
        self.generic_batches['python_django_admin'].append((
            file_path,
            line,
            admin_class_name,
            model_name,
            list_display,
            list_filter,
            search_fields,
            readonly_fields,
            1 if has_custom_actions else 0
        ))

    def add_python_django_middleware(self, file_path: str, line: int, middleware_class_name: str,
                                     has_process_request: bool, has_process_response: bool,
                                     has_process_exception: bool, has_process_view: bool,
                                     has_process_template_response: bool):
        """Add a Django middleware configuration to the batch."""
        self.generic_batches['python_django_middleware'].append((
            file_path,
            line,
            middleware_class_name,
            1 if has_process_request else 0,
            1 if has_process_response else 0,
            1 if has_process_exception else 0,
            1 if has_process_view else 0,
            1 if has_process_template_response else 0
        ))

    def add_python_marshmallow_schema(self, file_path: str, line: int, schema_class_name: str,
                                      field_count: int, has_nested_schemas: bool,
                                      has_custom_validators: bool):
        """Add a Marshmallow schema definition to the batch."""
        self.generic_batches['python_marshmallow_schemas'].append((
            file_path,
            line,
            schema_class_name,
            field_count,
            1 if has_nested_schemas else 0,
            1 if has_custom_validators else 0
        ))

    def add_python_marshmallow_field(self, file_path: str, line: int, schema_class_name: str,
                                     field_name: str, field_type: str, required: bool,
                                     allow_none: bool, has_validate: bool, has_custom_validator: bool):
        """Add a Marshmallow field definition to the batch."""
        self.generic_batches['python_marshmallow_fields'].append((
            file_path,
            line,
            schema_class_name,
            field_name,
            field_type,
            1 if required else 0,
            1 if allow_none else 0,
            1 if has_validate else 0,
            1 if has_custom_validator else 0
        ))

    def add_python_drf_serializer(self, file_path: str, line: int, serializer_class_name: str,
                                  field_count: int, is_model_serializer: bool, has_meta_model: bool,
                                  has_read_only_fields: bool, has_custom_validators: bool):
        """Add a Django REST Framework serializer definition to the batch."""
        self.generic_batches['python_drf_serializers'].append((
            file_path,
            line,
            serializer_class_name,
            field_count,
            1 if is_model_serializer else 0,
            1 if has_meta_model else 0,
            1 if has_read_only_fields else 0,
            1 if has_custom_validators else 0
        ))

    def add_python_drf_serializer_field(self, file_path: str, line: int, serializer_class_name: str,
                                        field_name: str, field_type: str, read_only: bool,
                                        write_only: bool, required: bool, allow_null: bool,
                                        has_source: bool, has_custom_validator: bool):
        """Add a Django REST Framework field definition to the batch."""
        self.generic_batches['python_drf_serializer_fields'].append((
            file_path,
            line,
            serializer_class_name,
            field_name,
            field_type,
            1 if read_only else 0,
            1 if write_only else 0,
            1 if required else 0,
            1 if allow_null else 0,
            1 if has_source else 0,
            1 if has_custom_validator else 0
        ))

    def add_python_wtforms_form(self, file_path: str, line: int, form_class_name: str,
                                field_count: int, has_custom_validators: bool):
        """Add a WTForms form definition to the batch."""
        self.generic_batches['python_wtforms_forms'].append((
            file_path,
            line,
            form_class_name,
            field_count,
            1 if has_custom_validators else 0
        ))

    def add_python_wtforms_field(self, file_path: str, line: int, form_class_name: str,
                                 field_name: str, field_type: str, has_validators: bool,
                                 has_custom_validator: bool):
        """Add a WTForms field definition to the batch."""
        self.generic_batches['python_wtforms_fields'].append((
            file_path,
            line,
            form_class_name,
            field_name,
            field_type,
            1 if has_validators else 0,
            1 if has_custom_validator else 0
        ))

    def add_python_celery_task(self, file_path: str, line: int, task_name: str, decorator_name: str,
                               arg_count: int, bind: bool, serializer: str, max_retries: int,
                               rate_limit: str, time_limit: int, queue: str):
        """Add a Celery task definition to the batch."""
        self.generic_batches['python_celery_tasks'].append((
            file_path,
            line,
            task_name,
            decorator_name,
            arg_count,
            1 if bind else 0,
            serializer,  # nullable
            max_retries,  # nullable
            rate_limit,  # nullable
            time_limit,  # nullable
            queue  # nullable
        ))

    def add_python_celery_task_call(self, file_path: str, line: int, caller_function: str, task_name: str,
                                      invocation_type: str, arg_count: int, has_countdown: bool,
                                      has_eta: bool, queue_override: str):
        """Add a Celery task invocation to the batch."""
        self.generic_batches['python_celery_task_calls'].append((
            file_path,
            line,
            caller_function,
            task_name,
            invocation_type,
            arg_count,
            1 if has_countdown else 0,
            1 if has_eta else 0,
            queue_override  # nullable
        ))

    def add_python_celery_beat_schedule(self, file_path: str, line: int, schedule_name: str, task_name: str,
                                         schedule_type: str, schedule_expression: str, args: str, kwargs: str):
        """Add a Celery Beat periodic schedule to the batch."""
        self.generic_batches['python_celery_beat_schedules'].append((
            file_path,
            line,
            schedule_name,
            task_name,
            schedule_type,
            schedule_expression,  # nullable
            args,  # nullable
            kwargs  # nullable
        ))

    def add_python_generator(self, file_path: str, line: int, generator_type: str, name: str,
                             yield_count: int, has_yield_from: bool, has_send: bool, is_infinite: bool):
        """Add a Python generator to the batch."""
        self.generic_batches['python_generators'].append((
            file_path,
            line,
            generator_type,
            name,
            yield_count,
            1 if has_yield_from else 0,
            1 if has_send else 0,
            1 if is_infinite else 0
        ))

    # Phase 3.1: Flask framework add_* methods

    def add_python_flask_app(self, file_path: str, line: int, factory_name: str,
                             app_var_name: str, config_source: str, registers_blueprints: bool):
        """Add a Flask application factory to the batch."""
        self.generic_batches['python_flask_apps'].append((
            file_path,
            line,
            factory_name,
            app_var_name,  # nullable
            config_source,  # nullable
            1 if registers_blueprints else 0
        ))

    def add_python_flask_extension(self, file_path: str, line: int, extension_type: str,
                                    var_name: str, app_passed_to_constructor: bool):
        """Add a Flask extension registration to the batch."""
        self.generic_batches['python_flask_extensions'].append((
            file_path,
            line,
            extension_type,
            var_name,  # nullable
            1 if app_passed_to_constructor else 0
        ))

    def add_python_flask_hook(self, file_path: str, line: int, hook_type: str,
                              function_name: str, app_var: str):
        """Add a Flask request/response hook to the batch."""
        self.generic_batches['python_flask_hooks'].append((
            file_path,
            line,
            hook_type,
            function_name,
            app_var  # nullable
        ))

    def add_python_flask_error_handler(self, file_path: str, line: int, function_name: str,
                                        error_code: int, exception_type: str):
        """Add a Flask error handler to the batch."""
        self.generic_batches['python_flask_error_handlers'].append((
            file_path,
            line,
            function_name,
            error_code,  # nullable
            exception_type  # nullable
        ))

    def add_python_flask_websocket(self, file_path: str, line: int, function_name: str,
                                    event_name: str, namespace: str):
        """Add a Flask-SocketIO WebSocket handler to the batch."""
        self.generic_batches['python_flask_websockets'].append((
            file_path,
            line,
            function_name,
            event_name,  # nullable
            namespace  # nullable
        ))

    def add_python_flask_cli_command(self, file_path: str, line: int, command_name: str,
                                      function_name: str, has_options: bool):
        """Add a Flask CLI command to the batch."""
        self.generic_batches['python_flask_cli_commands'].append((
            file_path,
            line,
            command_name,
            function_name,
            1 if has_options else 0
        ))

    def add_python_flask_cors(self, file_path: str, line: int, config_type: str,
                              origins: str, is_permissive: bool):
        """Add a Flask CORS configuration to the batch."""
        self.generic_batches['python_flask_cors'].append((
            file_path,
            line,
            config_type,
            origins,  # nullable
            1 if is_permissive else 0
        ))

    def add_python_flask_rate_limit(self, file_path: str, line: int, function_name: str,
                                      limit_string: str):
        """Add a Flask rate limit decorator to the batch."""
        self.generic_batches['python_flask_rate_limits'].append((
            file_path,
            line,
            function_name,
            limit_string  # nullable
        ))

    def add_python_flask_cache(self, file_path: str, line: int, function_name: str,
                                cache_type: str, timeout: int):
        """Add a Flask cache decorator to the batch."""
        self.generic_batches['python_flask_cache'].append((
            file_path,
            line,
            function_name,
            cache_type,
            timeout  # nullable
        ))

    # Phase 3.2: Testing Ecosystem add_* methods

    def add_python_unittest_test_case(self, file_path: str, line: int, test_class_name: str,
                                       test_method_count: int, has_setup: bool, has_teardown: bool,
                                       has_setupclass: bool, has_teardownclass: bool):
        """Add a unittest TestCase to the batch."""
        self.generic_batches['python_unittest_test_cases'].append((
            file_path,
            line,
            test_class_name,
            test_method_count,
            1 if has_setup else 0,
            1 if has_teardown else 0,
            1 if has_setupclass else 0,
            1 if has_teardownclass else 0
        ))

    def add_python_assertion_pattern(self, file_path: str, line: int, function_name: str,
                                      assertion_type: str, test_expr: str, assertion_method: str):
        """Add an assertion pattern to the batch."""
        self.generic_batches['python_assertion_patterns'].append((
            file_path,
            line,
            function_name,
            assertion_type,
            test_expr,  # nullable
            assertion_method  # nullable
        ))

    def add_python_pytest_plugin_hook(self, file_path: str, line: int, hook_name: str,
                                       param_count: int):
        """Add a pytest plugin hook to the batch."""
        self.generic_batches['python_pytest_plugin_hooks'].append((
            file_path,
            line,
            hook_name,
            param_count
        ))

    def add_python_hypothesis_strategy(self, file_path: str, line: int, test_name: str,
                                        strategy_count: int, strategies: str):
        """Add a Hypothesis strategy to the batch."""
        self.generic_batches['python_hypothesis_strategies'].append((
            file_path,
            line,
            test_name,
            strategy_count,
            strategies  # nullable
        ))

    # Phase 3.3: Security Patterns add_* methods

    def add_python_auth_decorator(self, file_path: str, line: int, function_name: str,
                                   decorator_name: str, permissions: str):
        """Add an authentication decorator to the batch."""
        self.generic_batches['python_auth_decorators'].append((
            file_path,
            line,
            function_name,
            decorator_name,
            permissions  # nullable
        ))

    def add_python_password_hashing(self, file_path: str, line: int, hash_library: str,
                                     hash_method: str, is_weak: bool, has_hardcoded_value: bool):
        """Add a password hashing pattern to the batch."""
        self.generic_batches['python_password_hashing'].append((
            file_path,
            line,
            hash_library,  # nullable
            hash_method,  # nullable
            1 if is_weak else 0,
            1 if has_hardcoded_value else 0
        ))

    def add_python_jwt_operation(self, file_path: str, line: int, operation: str,
                                  algorithm: str, verify: bool, is_insecure: bool):
        """Add a JWT operation to the batch."""
        self.generic_batches['python_jwt_operations'].append((
            file_path,
            line,
            operation,
            algorithm,  # nullable
            1 if verify else 0 if verify is not None else None,  # nullable boolean
            1 if is_insecure else 0
        ))

    def add_python_sql_injection(self, file_path: str, line: int, db_method: str,
                                  interpolation_type: str, is_vulnerable: bool):
        """Add a SQL injection pattern to the batch."""
        self.generic_batches['python_sql_injection'].append((
            file_path,
            line,
            db_method,
            interpolation_type,  # nullable
            1 if is_vulnerable else 0
        ))

    def add_python_command_injection(self, file_path: str, line: int, function: str,
                                      shell_true: bool, is_vulnerable: bool):
        """Add a command injection pattern to the batch."""
        self.generic_batches['python_command_injection'].append((
            file_path,
            line,
            function,
            1 if shell_true else 0,
            1 if is_vulnerable else 0
        ))

    def add_python_path_traversal(self, file_path: str, line: int, function: str,
                                   has_concatenation: bool, is_vulnerable: bool):
        """Add a path traversal pattern to the batch."""
        self.generic_batches['python_path_traversal'].append((
            file_path,
            line,
            function,
            1 if has_concatenation else 0,
            1 if is_vulnerable else 0
        ))

    def add_python_dangerous_eval(self, file_path: str, line: int, function: str,
                                   is_constant_input: bool, is_critical: bool):
        """Add a dangerous eval/exec pattern to the batch."""
        self.generic_batches['python_dangerous_eval'].append((
            file_path,
            line,
            function,
            1 if is_constant_input else 0,
            1 if is_critical else 0
        ))

    def add_python_crypto_operation(self, file_path: str, line: int, algorithm: str,
                                     mode: str, is_weak: bool, has_hardcoded_key: bool):
        """Add a cryptography operation to the batch."""
        self.generic_batches['python_crypto_operations'].append((
            file_path,
            line,
            algorithm,  # nullable
            mode,  # nullable
            1 if is_weak else 0,
            1 if has_hardcoded_key else 0
        ))

    # ============================================================================
    # PHASE 3.4: DJANGO ADVANCED PATTERNS
    # ============================================================================

    def add_python_django_signal(self, file_path: str, line: int, signal_name: str,
                                  signal_type: str, providing_args: str, sender: str,
                                  receiver_function: str):
        """Add a Django signal definition or connection to the batch."""
        self.generic_batches['python_django_signals'].append((
            file_path,
            line,
            signal_name,
            signal_type,  # nullable
            providing_args,  # nullable
            sender,  # nullable
            receiver_function  # nullable
        ))

    def add_python_django_receiver(self, file_path: str, line: int, function_name: str,
                                    signals: str, sender: str, is_weak: bool):
        """Add a Django @receiver decorator to the batch."""
        self.generic_batches['python_django_receivers'].append((
            file_path,
            line,
            function_name,
            signals,  # nullable
            sender,  # nullable
            1 if is_weak else 0
        ))

    def add_python_django_manager(self, file_path: str, line: int, manager_name: str,
                                   base_class: str, custom_methods: str, model_assignment: str):
        """Add a Django custom manager to the batch."""
        self.generic_batches['python_django_managers'].append((
            file_path,
            line,
            manager_name,
            base_class,  # nullable
            custom_methods,  # nullable
            model_assignment  # nullable
        ))

    def add_python_django_queryset(self, file_path: str, line: int, queryset_name: str,
                                    base_class: str, custom_methods: str, has_as_manager: bool,
                                    method_chain: str):
        """Add a Django QuerySet definition or chain to the batch."""
        self.generic_batches['python_django_querysets'].append((
            file_path,
            line,
            queryset_name,
            base_class,  # nullable
            custom_methods,  # nullable
            1 if has_as_manager else 0,
            method_chain  # nullable
        ))

    # ============================================================================
    # CAUSAL LEARNING: EXCEPTION FLOW PATTERNS (Week 1, Block 1.2)
    # ============================================================================

    def add_python_exception_raise(self, file_path: str, line: int, exception_type: Optional[str],
                                    message: Optional[str], from_exception: Optional[str],
                                    in_function: str, condition: Optional[str], is_re_raise: bool):
        """Add a Python exception raise pattern to the batch."""
        self.generic_batches['python_exception_raises'].append((
            file_path,
            line,
            exception_type,
            message,
            from_exception,
            in_function,
            condition,
            1 if is_re_raise else 0
        ))

    def add_python_exception_catch(self, file_path: str, line: int, exception_types: str,
                                    variable_name: Optional[str], handling_strategy: str,
                                    in_function: str):
        """Add a Python exception catch pattern to the batch."""
        self.generic_batches['python_exception_catches'].append((
            file_path,
            line,
            exception_types,
            variable_name,
            handling_strategy,
            in_function
        ))

    def add_python_finally_block(self, file_path: str, line: int, cleanup_calls: Optional[str],
                                  has_cleanup: bool, in_function: str):
        """Add a Python finally block pattern to the batch."""
        self.generic_batches['python_finally_blocks'].append((
            file_path,
            line,
            cleanup_calls,
            1 if has_cleanup else 0,
            in_function
        ))

    def add_python_context_manager_enhanced(self, file_path: str, line: int, context_expr: str,
                                             variable_name: Optional[str], in_function: str,
                                             is_async: bool, resource_type: Optional[str]):
        """Add a Python context manager enhanced pattern to the batch."""
        self.generic_batches['python_context_managers_enhanced'].append((
            file_path,
            line,
            context_expr,
            variable_name,
            in_function,
            1 if is_async else 0,
            resource_type
        ))

    # ============================================================================
    # CAUSAL LEARNING: DATA FLOW PATTERNS (Week 2, Block 2.1)
    # ============================================================================

    def add_python_io_operation(self, file_path: str, line: int, io_type: str,
                                 operation: str, target: Optional[str],
                                 is_static: bool, in_function: str):
        """Add a Python I/O operation pattern to the batch."""
        self.generic_batches['python_io_operations'].append((
            file_path,
            line,
            io_type,
            operation,
            target,
            1 if is_static else 0,
            in_function
        ))

    def add_python_parameter_return_flow(self, file_path: str, line: int, function_name: str,
                                          parameter_name: str, return_expr: str,
                                          flow_type: str, is_async: bool):
        """Add a Python parameter-to-return flow pattern to the batch."""
        self.generic_batches['python_parameter_return_flow'].append((
            file_path,
            line,
            function_name,
            parameter_name,
            return_expr,
            flow_type,
            1 if is_async else 0
        ))

    def add_python_closure_capture(self, file_path: str, line: int, inner_function: str,
                                    captured_variable: str, outer_function: str, is_lambda: bool):
        """Add a Python closure capture pattern to the batch."""
        self.generic_batches['python_closure_captures'].append((
            file_path,
            line,
            inner_function,
            captured_variable,
            outer_function,
            1 if is_lambda else 0
        ))

    def add_python_nonlocal_access(self, file_path: str, line: int, variable_name: str,
                                    access_type: str, in_function: str):
        """Add a Python nonlocal access pattern to the batch."""
        self.generic_batches['python_nonlocal_access'].append((
            file_path,
            line,
            variable_name,
            access_type,
            in_function
        ))

    def add_python_conditional_call(self, file_path: str, line: int, function_call: str,
                                     condition_expr: Optional[str], condition_type: str,
                                     in_function: str, nesting_level: int):
        """Add a Python conditional call pattern to the batch."""
        self.generic_batches['python_conditional_calls'].append((
            file_path,
            line,
            function_call,
            condition_expr,
            condition_type,
            in_function,
            nesting_level
        ))

    # ============================================================================
    # CAUSAL LEARNING: BEHAVIORAL PATTERNS (Week 3, Block 3.1)
    # ============================================================================

    def add_python_recursion_pattern(self, file_path: str, line: int, function_name: str,
                                      recursion_type: str, calls_function: str,
                                      base_case_line: Optional[int], is_async: bool):
        """Add a Python recursion pattern to the batch."""
        self.generic_batches['python_recursion_patterns'].append((
            file_path,
            line,
            function_name,
            recursion_type,
            calls_function,
            base_case_line,
            1 if is_async else 0
        ))

    def add_python_generator_yield(self, file_path: str, line: int, generator_function: str,
                                    yield_type: str, yield_expr: Optional[str],
                                    condition: Optional[str], in_loop: bool):
        """Add a Python generator yield pattern to the batch."""
        self.generic_batches['python_generator_yields'].append((
            file_path,
            line,
            generator_function,
            yield_type,
            yield_expr,
            condition,
            1 if in_loop else 0
        ))

    def add_python_property_pattern(self, file_path: str, line: int, property_name: str,
                                     access_type: str, in_class: str,
                                     has_computation: bool, has_validation: bool):
        """Add a Python property pattern to the batch."""
        self.generic_batches['python_property_patterns'].append((
            file_path,
            line,
            property_name,
            access_type,
            in_class,
            1 if has_computation else 0,
            1 if has_validation else 0
        ))

    def add_python_dynamic_attribute(self, file_path: str, line: int, method_name: str,
                                      in_class: str, has_delegation: bool, has_validation: bool):
        """Add a Python dynamic attribute pattern to the batch."""
        self.generic_batches['python_dynamic_attributes'].append((
            file_path,
            line,
            method_name,
            in_class,
            1 if has_delegation else 0,
            1 if has_validation else 0
        ))

    # ============================================================================
    # CAUSAL LEARNING: PERFORMANCE INDICATORS (Week 4, Block 4.1)
    # ============================================================================

    def add_python_loop_complexity(self, file_path: str, line: int, loop_type: str,
                                    nesting_level: int, has_growing_operation: bool,
                                    in_function: str, estimated_complexity: str):
        """Add a Python loop complexity pattern to the batch."""
        self.generic_batches['python_loop_complexity'].append((
            file_path,
            line,
            loop_type,
            nesting_level,
            1 if has_growing_operation else 0,
            in_function,
            estimated_complexity
        ))

    def add_python_resource_usage(self, file_path: str, line: int, resource_type: str,
                                   allocation_expr: str, in_function: str, has_cleanup: bool):
        """Add a Python resource usage pattern to the batch."""
        self.generic_batches['python_resource_usage'].append((
            file_path,
            line,
            resource_type,
            allocation_expr,
            in_function,
            1 if has_cleanup else 0
        ))

    def add_python_memoization_pattern(self, file_path: str, line: int, function_name: str,
                                        has_memoization: bool, memoization_type: str,
                                        is_recursive: bool, cache_size: Optional[int]):
        """Add a Python memoization pattern to the batch."""
        self.generic_batches['python_memoization_patterns'].append((
            file_path,
            line,
            function_name,
            1 if has_memoization else 0,
            memoization_type,
            1 if is_recursive else 0,
            cache_size
        ))
