"""Python-specific database operations.

This module contains add_* methods for PYTHON_TABLES defined in schemas/python_schema.py.

Handles 28 Python tables with 28 add_* methods:
- 8 original methods for 8 kept tables (ORM, routes, validators, decorators, Django, package_configs)
- 20 new methods for consolidated tables (loops, branches, security, testing, etc.)

HISTORY:
- 2025-11-25: Purged ~140 zombie methods (1,655 lines deleted)
- 2025-11-25: Added 20 consolidated table methods
- 2025-11-25: Removed dead add_python_blueprint method (table doesn't exist)
"""


import json
from typing import List, Optional


class PythonDatabaseMixin:
    """Mixin providing add_* methods for PYTHON_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    def add_python_orm_model(self, file_path: str, line: int, model_name: str,
                             table_name: str | None, orm_type: str = 'sqlalchemy'):
        """Add a Python ORM model definition to the batch."""
        self.generic_batches['python_orm_models'].append((file_path, line, model_name, table_name, orm_type))

    def add_python_orm_field(self, file_path: str, line: int, model_name: str,
                             field_name: str, field_type: str | None,
                             is_primary_key: bool = False, is_foreign_key: bool = False,
                             foreign_key_target: str | None = None):
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
                         dependencies: list[str] | None = None, blueprint: str | None = None):
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

    def add_python_validator(self, file_path: str, line: int, model_name: str,
                             field_name: str | None, validator_method: str,
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

    def add_python_package_config(self, file_path: str, file_type: str,
                                   project_name: str | None, project_version: str | None,
                                   dependencies: str, optional_dependencies: str,
                                   build_system: str | None):
        """Add a Python package configuration (pyproject.toml/requirements.txt) to the batch.

        Args:
            file_path: Path to the dependency file
            file_type: 'pyproject' or 'requirements'
            project_name: Package name (from pyproject.toml)
            project_version: Package version (from pyproject.toml)
            dependencies: JSON array of dependency dicts
            optional_dependencies: JSON object with optional dependency groups
            build_system: JSON object with build system info
        """
        self.generic_batches['python_package_configs'].append((
            file_path,
            file_type,
            project_name,
            project_version,
            dependencies,
            optional_dependencies,
            build_system
        ))

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

    def add_python_django_view(self, file_path: str, line: int, view_class_name: str,
                              view_type: str, base_view_class: str | None,
                              model_name: str | None, template_name: str | None,
                              has_permission_check: bool, http_method_names: str | None,
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

    # =========================================================================
    # CONSOLIDATED TABLES - Group 1: Control & Data Flow (5 methods)
    # =========================================================================

    def add_python_loop(self, file_path: str, line: int, loop_type: str,
                        target: str | None, iterator: str | None,
                        has_else: bool, nesting_level: int,
                        body_line_count: int | None):
        """Add a Python loop (for/while/async for) to the batch.

        Args:
            loop_type: 'for_loop', 'while_loop', 'async_for_loop'
        """
        self.generic_batches['python_loops'].append((
            file_path,
            line,
            loop_type,
            target,
            iterator,
            1 if has_else else 0,
            nesting_level,
            body_line_count
        ))

    def add_python_branch(self, file_path: str, line: int, branch_type: str,
                          condition: str | None, has_else: bool,
                          elif_count: int, case_count: int,
                          exception_type: str | None):
        """Add a Python branch (if/match/try/except/finally/raise) to the batch.

        Args:
            branch_type: 'if', 'match', 'try', 'except', 'finally', 'raise'
        """
        self.generic_batches['python_branches'].append((
            file_path,
            line,
            branch_type,
            condition,
            1 if has_else else 0,
            elif_count,
            case_count,
            exception_type
        ))

    def add_python_function_advanced(self, file_path: str, line: int, function_type: str,
                                      name: str | None, is_method: bool,
                                      yield_count: int, await_count: int):
        """Add an advanced Python function pattern to the batch.

        Args:
            function_type: 'async', 'async_generator', 'generator', 'lambda', 'context_manager'
        """
        self.generic_batches['python_functions_advanced'].append((
            file_path,
            line,
            function_type,
            name,
            1 if is_method else 0,
            yield_count,
            await_count
        ))

    def add_python_io_operation(self, file_path: str, line: int, io_type: str,
                                 operation: str | None, target: str | None,
                                 is_taint_source: bool, is_taint_sink: bool):
        """Add a Python I/O operation to the batch.

        Args:
            io_type: 'file', 'network', 'database', 'process', 'param_flow', 'closure', 'nonlocal', 'conditional'
        """
        self.generic_batches['python_io_operations'].append((
            file_path,
            line,
            io_type,
            operation,
            target,
            1 if is_taint_source else 0,
            1 if is_taint_sink else 0
        ))

    def add_python_state_mutation(self, file_path: str, line: int, mutation_type: str,
                                   target: str | None, operator: str | None,
                                   value_expr: str | None, in_function: str | None):
        """Add a Python state mutation to the batch.

        Args:
            mutation_type: 'instance', 'class', 'global', 'argument', 'augmented'
        """
        self.generic_batches['python_state_mutations'].append((
            file_path,
            line,
            mutation_type,
            target,
            operator,
            value_expr,
            in_function
        ))

    # =========================================================================
    # CONSOLIDATED TABLES - Group 2: Object-Oriented & Types (5 methods)
    # =========================================================================

    def add_python_class_feature(self, file_path: str, line: int, feature_type: str,
                                  class_name: str | None, name: str | None,
                                  details: dict | None):
        """Add a Python class feature to the batch.

        Args:
            feature_type: 'metaclass', 'slots', 'abstract', 'dataclass', 'enum',
                         'inheritance', 'dunder', 'visibility', 'method_type'
            details: JSON dict with feature-specific data
        """
        details_json = json.dumps(details) if details else None
        self.generic_batches['python_class_features'].append((
            file_path,
            line,
            feature_type,
            class_name,
            name,
            details_json
        ))

    def add_python_protocol(self, file_path: str, line: int, protocol_type: str,
                            class_name: str | None, implemented_methods: list[str] | None):
        """Add a Python protocol implementation to the batch.

        Args:
            protocol_type: 'iterator', 'container', 'callable', 'comparison',
                          'arithmetic', 'pickle', 'context_manager'
            implemented_methods: JSON array of method names
        """
        methods_json = json.dumps(implemented_methods) if implemented_methods else None
        self.generic_batches['python_protocols'].append((
            file_path,
            line,
            protocol_type,
            class_name,
            methods_json
        ))

    def add_python_descriptor(self, file_path: str, line: int, descriptor_type: str,
                               name: str | None, class_name: str | None,
                               has_getter: bool, has_setter: bool, has_deleter: bool):
        """Add a Python descriptor to the batch.

        Args:
            descriptor_type: 'descriptor', 'property', 'dynamic_attr', 'cached_property', 'attr_access'
        """
        self.generic_batches['python_descriptors'].append((
            file_path,
            line,
            descriptor_type,
            name,
            class_name,
            1 if has_getter else 0,
            1 if has_setter else 0,
            1 if has_deleter else 0
        ))

    def add_python_type_definition(self, file_path: str, line: int, type_kind: str,
                                    name: str | None, type_params: list[str] | None,
                                    fields: dict | None):
        """Add a Python type definition to the batch.

        Args:
            type_kind: 'typed_dict', 'generic', 'protocol'
            type_params: JSON array of type parameters
            fields: JSON dict for TypedDict fields
        """
        params_json = json.dumps(type_params) if type_params else None
        fields_json = json.dumps(fields) if fields else None
        self.generic_batches['python_type_definitions'].append((
            file_path,
            line,
            type_kind,
            name,
            params_json,
            fields_json
        ))

    def add_python_literal(self, file_path: str, line: int, literal_type: str,
                           name: str | None, literal_values: list | None):
        """Add a Python Literal/Overload type to the batch.

        Args:
            literal_type: 'literal', 'overload'
            literal_values: JSON array of literal values
        """
        literal_values_json = json.dumps(literal_values) if literal_values else None
        self.generic_batches['python_literals'].append((
            file_path,
            line,
            literal_type,
            name,
            literal_values_json
        ))

    # =========================================================================
    # CONSOLIDATED TABLES - Group 3: Security & Testing (5 methods)
    # =========================================================================

    def add_python_security_finding(self, file_path: str, line: int, finding_type: str,
                                     severity: str, source_expr: str | None,
                                     sink_expr: str | None, vulnerable_code: str | None,
                                     cwe_id: str | None):
        """Add a Python security finding to the batch.

        Args:
            finding_type: 'sql_injection', 'command_injection', 'path_traversal',
                         'dangerous_eval', 'crypto', 'auth', 'password', 'jwt'
            severity: 'low', 'medium', 'high', 'critical'
        """
        self.generic_batches['python_security_findings'].append((
            file_path,
            line,
            finding_type,
            severity,
            source_expr,
            sink_expr,
            vulnerable_code,
            cwe_id
        ))

    def add_python_test_case(self, file_path: str, line: int, test_type: str,
                              name: str | None, class_name: str | None,
                              assertion_type: str | None, expected_exception: str | None):
        """Add a Python test case to the batch.

        Args:
            test_type: 'unittest', 'pytest', 'assertion'
        """
        self.generic_batches['python_test_cases'].append((
            file_path,
            line,
            test_type,
            name,
            class_name,
            assertion_type,
            expected_exception
        ))

    def add_python_test_fixture(self, file_path: str, line: int, fixture_type: str,
                                 name: str | None, scope: str | None,
                                 params: list | None, autouse: bool):
        """Add a Python test fixture to the batch.

        Args:
            fixture_type: 'fixture', 'parametrize', 'marker', 'mock', 'plugin_hook', 'hypothesis'
            scope: 'function', 'class', 'module', 'session'
            params: JSON array of parameters
        """
        params_json = json.dumps(params) if params else None
        self.generic_batches['python_test_fixtures'].append((
            file_path,
            line,
            fixture_type,
            name,
            scope,
            params_json,
            1 if autouse else 0
        ))

    def add_python_framework_config(self, file_path: str, line: int, framework: str,
                                     config_type: str, name: str | None,
                                     endpoint: str | None, methods: str | None,
                                     schedule: str | None, details: dict | None):
        """Add a Python framework configuration to the batch.

        Args:
            framework: 'flask', 'celery', 'django'
            config_type: 'app', 'extension', 'hook', 'error_handler', 'task', 'signal',
                        'admin', 'form', 'websocket', 'cli', 'cors', 'rate_limit', 'cache'
            details: JSON dict for framework-specific data
        """
        details_json = json.dumps(details) if details else None
        self.generic_batches['python_framework_config'].append((
            file_path,
            line,
            framework,
            config_type,
            name,
            endpoint,
            methods,
            schedule,
            details_json
        ))

    def add_python_validation_schema(self, file_path: str, line: int, framework: str,
                                      schema_type: str, name: str | None,
                                      field_type: str | None, validators: list | None,
                                      required: bool):
        """Add a Python validation schema to the batch.

        Args:
            framework: 'marshmallow', 'drf', 'wtforms'
            schema_type: 'schema', 'field', 'serializer', 'form'
            validators: JSON array of validator names
        """
        validators_json = json.dumps(validators) if validators else None
        self.generic_batches['python_validation_schemas'].append((
            file_path,
            line,
            framework,
            schema_type,
            name,
            field_type,
            validators_json,
            1 if required else 0
        ))

    # =========================================================================
    # CONSOLIDATED TABLES - Group 4: Low-Level & Misc (5 methods)
    # =========================================================================

    def add_python_operator(self, file_path: str, line: int, operator_type: str,
                            operator: str | None, left_operand: str | None,
                            right_operand: str | None):
        """Add a Python operator usage to the batch.

        Args:
            operator_type: 'binary', 'unary', 'membership', 'chained', 'ternary', 'walrus', 'matmul'
        """
        self.generic_batches['python_operators'].append((
            file_path,
            line,
            operator_type,
            operator,
            left_operand,
            right_operand
        ))

    def add_python_collection(self, file_path: str, line: int, collection_type: str,
                               operation: str | None, method: str | None):
        """Add a Python collection operation to the batch.

        Args:
            collection_type: 'dict', 'list', 'set', 'string', 'builtin', 'itertools', 'functools', 'collections'
        """
        self.generic_batches['python_collections'].append((
            file_path,
            line,
            collection_type,
            operation,
            method
        ))

    def add_python_stdlib_usage(self, file_path: str, line: int, module: str,
                                 usage_type: str, function_name: str | None,
                                 pattern: str | None):
        """Add a Python stdlib usage to the batch.

        Args:
            module: 're', 'json', 'datetime', 'pathlib', 'logging', 'threading', 'contextlib', 'typing', 'weakref', 'contextvars'
            usage_type: 'pattern', 'operation', 'call'
        """
        self.generic_batches['python_stdlib_usage'].append((
            file_path,
            line,
            module,
            usage_type,
            function_name,
            pattern
        ))

    def add_python_import_advanced(self, file_path: str, line: int, import_type: str,
                                    module: str | None, name: str | None,
                                    alias: str | None, is_relative: bool):
        """Add an advanced Python import pattern to the batch.

        Args:
            import_type: 'static', 'dynamic', 'namespace', 'module_attr'
        """
        self.generic_batches['python_imports_advanced'].append((
            file_path,
            line,
            import_type,
            module,
            name,
            alias,
            1 if is_relative else 0
        ))

    def add_python_expression(self, file_path: str, line: int, expression_type: str,
                               subtype: str | None, expression: str | None,
                               variables: str | None):
        """Add a Python expression pattern to the batch.

        Args:
            expression_type: 'comprehension', 'slice', 'tuple', 'unpack', 'none', 'truthiness',
                            'format', 'ellipsis', 'bytes', 'exec', 'copy', 'recursion', 'yield',
                            'complexity', 'resource', 'memoize', 'await', 'break', 'continue',
                            'pass', 'assert', 'del', 'with', 'class_decorator'
            subtype: For comprehensions - 'list', 'dict', 'set', 'generator'
        """
        self.generic_batches['python_expressions'].append((
            file_path,
            line,
            expression_type,
            subtype,
            expression,
            variables
        ))
