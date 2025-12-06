"""Python storage handlers for framework-specific patterns."""

import json

from .base import BaseStorage


class PythonStorage(BaseStorage):
    """Python-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            "python_orm_models": self._store_python_orm_models,
            "python_orm_fields": self._store_python_orm_fields,
            "python_routes": self._store_python_routes,
            "python_validators": self._store_python_validators,
            "python_decorators": self._store_python_decorators,
            "python_django_views": self._store_python_django_views,
            "python_django_middleware": self._store_python_django_middleware,
            "python_loops": self._store_python_loops,
            "python_branches": self._store_python_branches,
            "python_functions_advanced": self._store_python_functions_advanced,
            "python_io_operations": self._store_python_io_operations,
            "python_state_mutations": self._store_python_state_mutations,
            "python_class_features": self._store_python_class_features,
            "python_protocols": self._store_python_protocols,
            "python_descriptors": self._store_python_descriptors,
            "python_type_definitions": self._store_python_type_definitions,
            "python_literals": self._store_python_literals,
            "python_security_findings": self._store_python_security_findings,
            "python_test_cases": self._store_python_test_cases,
            "python_test_fixtures": self._store_python_test_fixtures,
            "python_framework_config": self._store_python_framework_config,
            "python_validation_schemas": self._store_python_validation_schemas,
            "python_operators": self._store_python_operators,
            "python_collections": self._store_python_collections,
            "python_stdlib_usage": self._store_python_stdlib_usage,
            "python_imports_advanced": self._store_python_imports_advanced,
            "python_expressions": self._store_python_expressions,
            "python_comprehensions": self._store_python_comprehensions,
            "python_control_statements": self._store_python_control_statements,
            "python_package_configs": self._store_python_package_configs,
            "python_package_dependencies": self._store_python_package_dependencies,
            "python_build_requires": self._store_python_build_requires,
        }

    def _store_python_orm_models(self, file_path: str, python_orm_models: list, jsx_pass: bool):
        """Store Python ORM models."""
        for model in python_orm_models:
            self.db_manager.add_python_orm_model(
                file_path,
                model.get("line", 0),
                model.get("model_name", ""),
                model.get("table_name"),
                model.get("orm_type", "sqlalchemy"),
            )
            if "python_orm_models" not in self.counts:
                self.counts["python_orm_models"] = 0
            self.counts["python_orm_models"] += 1

    def _store_python_orm_fields(self, file_path: str, python_orm_fields: list, jsx_pass: bool):
        """Store Python ORM fields."""
        for field in python_orm_fields:
            self.db_manager.add_python_orm_field(
                file_path,
                field.get("line", 0),
                field.get("model_name", ""),
                field.get("field_name", ""),
                field.get("field_type"),
                field.get("is_primary_key", False),
                field.get("is_foreign_key", False),
                field.get("foreign_key_target"),
            )
            if "python_orm_fields" not in self.counts:
                self.counts["python_orm_fields"] = 0
            self.counts["python_orm_fields"] += 1

    def _store_python_routes(self, file_path: str, python_routes: list, jsx_pass: bool):
        """Store Python routes."""
        for route in python_routes:
            self.db_manager.add_python_route(
                file_path,
                route.get("line"),
                route.get("framework", ""),
                route.get("method", ""),
                route.get("pattern", ""),
                route.get("handler_function", ""),
                route.get("has_auth", False),
                route.get("dependencies"),
                route.get("blueprint"),
            )
            if "python_routes" not in self.counts:
                self.counts["python_routes"] = 0
            self.counts["python_routes"] += 1

    def _store_python_validators(self, file_path: str, python_validators: list, jsx_pass: bool):
        """Store Python validators."""
        for validator in python_validators:
            self.db_manager.add_python_validator(
                file_path,
                validator.get("line", 0),
                validator.get("model_name", ""),
                validator.get("field_name"),
                validator.get("validator_method", ""),
                validator.get("validator_type", ""),
            )
            if "python_validators" not in self.counts:
                self.counts["python_validators"] = 0
            self.counts["python_validators"] += 1

    def _store_python_decorators(self, file_path: str, python_decorators: list, jsx_pass: bool):
        """Store Python decorators."""
        for decorator in python_decorators:
            self.db_manager.add_python_decorator(
                file_path,
                decorator.get("line", 0),
                decorator.get("decorator_name", ""),
                decorator.get("decorator_type", ""),
                decorator.get("target_type", ""),
                decorator.get("target_name", ""),
                decorator.get("is_async", False),
            )
            if "python_decorators" not in self.counts:
                self.counts["python_decorators"] = 0
            self.counts["python_decorators"] += 1

    def _store_python_django_views(self, file_path: str, python_django_views: list, jsx_pass: bool):
        """Store Python Django views."""
        for django_view in python_django_views:
            self.db_manager.add_python_django_view(
                file_path,
                django_view.get("line", 0),
                django_view.get("view_class_name", ""),
                django_view.get("view_type", ""),
                django_view.get("base_view_class"),
                django_view.get("model_name"),
                django_view.get("template_name"),
                django_view.get("has_permission_check", False),
                django_view.get("http_method_names"),
                django_view.get("has_get_queryset_override", False),
            )
            if "python_django_views" not in self.counts:
                self.counts["python_django_views"] = 0
            self.counts["python_django_views"] += 1

    def _store_python_django_middleware(
        self, file_path: str, python_django_middleware: list, jsx_pass: bool
    ):
        """Store Python Django middleware."""
        for django_middleware in python_django_middleware:
            self.db_manager.add_python_django_middleware(
                file_path,
                django_middleware.get("line", 0),
                django_middleware.get("middleware_class_name", ""),
                django_middleware.get("has_process_request", False),
                django_middleware.get("has_process_response", False),
                django_middleware.get("has_process_exception", False),
                django_middleware.get("has_process_view", False),
                django_middleware.get("has_process_template_response", False),
            )
            if "python_django_middleware" not in self.counts:
                self.counts["python_django_middleware"] = 0
            self.counts["python_django_middleware"] += 1

    def _store_python_loops(self, file_path: str, python_loops: list, jsx_pass: bool):
        """Store Python loops (for/while/async_for/complexity_analysis)."""
        for loop in python_loops:
            self.db_manager.add_python_loop(
                file_path,
                loop.get("line", 0),
                loop.get("loop_kind", ""),
                loop.get("loop_type"),
                loop.get("has_else", False),
                loop.get("nesting_level", 0),
                loop.get("target_count"),
                loop.get("in_function"),
                loop.get("is_infinite", False),
                loop.get("estimated_complexity"),
                loop.get("has_growing_operation", False),
            )
            if "python_loops" not in self.counts:
                self.counts["python_loops"] = 0
            self.counts["python_loops"] += 1

    def _store_python_branches(self, file_path: str, python_branches: list, jsx_pass: bool):
        """Store Python branches (if/match/raise/except/finally)."""
        for branch in python_branches:
            pattern_types = branch.get("pattern_types")
            if isinstance(pattern_types, list):
                pattern_types = json.dumps(pattern_types)
            exception_types = branch.get("exception_types")
            if isinstance(exception_types, list):
                exception_types = json.dumps(exception_types)
            cleanup_calls = branch.get("cleanup_calls")
            if isinstance(cleanup_calls, list):
                cleanup_calls = json.dumps(cleanup_calls)

            self.db_manager.add_python_branch(
                file_path,
                branch.get("line", 0),
                branch.get("branch_kind", ""),
                branch.get("branch_type"),
                branch.get("has_else", False),
                branch.get("has_elif", False),
                branch.get("chain_length"),
                branch.get("has_complex_condition", False),
                branch.get("nesting_level", 0),
                branch.get("case_count", 0),
                branch.get("has_guards", False),
                branch.get("has_wildcard", False),
                pattern_types,
                exception_types,
                branch.get("handling_strategy"),
                branch.get("variable_name"),
                branch.get("exception_type"),
                branch.get("is_re_raise", False),
                branch.get("from_exception"),
                branch.get("message"),
                branch.get("condition"),
                branch.get("has_cleanup", False),
                cleanup_calls,
                branch.get("in_function"),
            )
            if "python_branches" not in self.counts:
                self.counts["python_branches"] = 0
            self.counts["python_branches"] += 1

    def _store_python_functions_advanced(
        self, file_path: str, python_functions_advanced: list, jsx_pass: bool
    ):
        """Store advanced Python function patterns (generator/async/lambda/context_manager/recursive/memoized)."""
        for func in python_functions_advanced:
            parameters = func.get("parameters")
            if isinstance(parameters, list):
                parameters = json.dumps(parameters)
            captured_vars = func.get("captured_vars")
            if isinstance(captured_vars, list):
                captured_vars = json.dumps(captured_vars)

            self.db_manager.add_python_function_advanced(
                file_path,
                func.get("line", 0),
                func.get("function_kind", ""),
                func.get("function_type"),
                func.get("name"),
                func.get("function_name"),
                func.get("yield_count", 0),
                func.get("has_send", False),
                func.get("has_yield_from", False),
                func.get("is_infinite", False),
                func.get("await_count", 0),
                func.get("has_async_for", False),
                func.get("has_async_with", False),
                func.get("parameter_count"),
                parameters,
                func.get("body"),
                func.get("captures_closure", False),
                captured_vars,
                func.get("used_in"),
                func.get("as_name"),
                func.get("context_expr"),
                func.get("is_async", False),
                func.get("iter_expr"),
                func.get("target_var"),
                func.get("base_case_line"),
                func.get("calls_function"),
                func.get("recursion_type"),
                func.get("cache_size"),
                func.get("memoization_type"),
                func.get("is_recursive", False),
                func.get("has_memoization", False),
                func.get("in_function"),
            )
            if "python_functions_advanced" not in self.counts:
                self.counts["python_functions_advanced"] = 0
            self.counts["python_functions_advanced"] += 1

    def _store_python_io_operations(
        self, file_path: str, python_io_operations: list, jsx_pass: bool
    ):
        """Store Python I/O operations (file/network/database/process/param_flow/closure/nonlocal/conditional)."""
        for io_op in python_io_operations:
            self.db_manager.add_python_io_operation(
                file_path,
                io_op.get("line", 0),
                io_op.get("io_kind", ""),
                io_op.get("io_type"),
                io_op.get("operation"),
                io_op.get("target"),
                io_op.get("is_static", False),
                io_op.get("flow_type"),
                io_op.get("function_name"),
                io_op.get("parameter_name"),
                io_op.get("return_expr"),
                io_op.get("is_async", False),
                io_op.get("in_function"),
            )
            if "python_io_operations" not in self.counts:
                self.counts["python_io_operations"] = 0
            self.counts["python_io_operations"] += 1

    def _store_python_state_mutations(
        self, file_path: str, python_state_mutations: list, jsx_pass: bool
    ):
        """Store Python state mutations (instance/class/global/argument/augmented)."""
        for mutation in python_state_mutations:
            self.db_manager.add_python_state_mutation(
                file_path,
                mutation.get("line", 0),
                mutation.get("mutation_kind", ""),
                mutation.get("mutation_type"),
                mutation.get("target"),
                mutation.get("operator"),
                mutation.get("target_type"),
                mutation.get("operation"),
                mutation.get("is_init", False),
                mutation.get("is_dunder_method", False),
                mutation.get("is_property_setter", False),
                mutation.get("in_function"),
            )
            if "python_state_mutations" not in self.counts:
                self.counts["python_state_mutations"] = 0
            self.counts["python_state_mutations"] += 1

    def _store_python_class_features(
        self, file_path: str, python_class_features: list, jsx_pass: bool
    ):
        """Store Python class features (metaclass/slots/abstract/dataclass/enum/etc)."""
        for feature in python_class_features:
            self.db_manager.add_python_class_feature(
                file_path,
                feature.get("line", 0),
                feature.get("feature_kind", ""),
                feature.get("feature_type"),
                feature.get("class_name"),
                feature.get("name"),
                feature.get("in_class"),
                feature.get("metaclass_name"),
                feature.get("is_definition", False),
                feature.get("field_count"),
                feature.get("frozen", False),
                feature.get("enum_name"),
                feature.get("enum_type"),
                feature.get("member_count"),
                feature.get("slot_count"),
                feature.get("abstract_method_count"),
                feature.get("method_name"),
                feature.get("method_type"),
                feature.get("category"),
                feature.get("visibility"),
                feature.get("is_name_mangled", False),
                feature.get("decorator"),
                feature.get("decorator_type"),
                feature.get("has_arguments", False),
            )
            if "python_class_features" not in self.counts:
                self.counts["python_class_features"] = 0
            self.counts["python_class_features"] += 1

    def _store_python_protocols(self, file_path: str, python_protocols: list, jsx_pass: bool):
        """Store Python protocol implementations with junction table for methods."""
        for protocol in python_protocols:
            protocol_id = self.db_manager.add_python_protocol(
                file_path,
                protocol.get("line", 0),
                protocol.get("protocol_kind", ""),
                protocol.get("protocol_type"),
                protocol.get("class_name"),
                protocol.get("in_function"),
                protocol.get("has_iter", False),
                protocol.get("has_next", False),
                protocol.get("is_generator", False),
                protocol.get("raises_stopiteration", False),
                protocol.get("has_contains", False),
                protocol.get("has_getitem", False),
                protocol.get("has_setitem", False),
                protocol.get("has_delitem", False),
                protocol.get("has_len", False),
                protocol.get("is_mapping", False),
                protocol.get("is_sequence", False),
                protocol.get("has_args", False),
                protocol.get("has_kwargs", False),
                protocol.get("param_count"),
                protocol.get("has_getstate", False),
                protocol.get("has_setstate", False),
                protocol.get("has_reduce", False),
                protocol.get("has_reduce_ex", False),
                protocol.get("context_expr"),
                protocol.get("resource_type"),
                protocol.get("variable_name"),
                protocol.get("is_async", False),
                protocol.get("has_copy", False),
                protocol.get("has_deepcopy", False),
            )

            implemented_methods = protocol.get("implemented_methods") or []
            if isinstance(implemented_methods, str):
                try:
                    implemented_methods = json.loads(implemented_methods)
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(
                        f"DATA CORRUPTION: Invalid implemented_methods JSON.\n"
                        f"  File: {file_path}\n"
                        f"  Protocol: {protocol.get('class_name')}\n"
                        f"  Raw data: {repr(implemented_methods)[:200]}\n"
                        f"  Error: {e}"
                    ) from e

            for order, method_name in enumerate(implemented_methods):
                self.db_manager.add_python_protocol_method(
                    file_path, protocol_id, method_name, order
                )
                if "python_protocol_methods" not in self.counts:
                    self.counts["python_protocol_methods"] = 0
                self.counts["python_protocol_methods"] += 1

            if "python_protocols" not in self.counts:
                self.counts["python_protocols"] = 0
            self.counts["python_protocols"] += 1

    def _store_python_descriptors(self, file_path: str, python_descriptors: list, jsx_pass: bool):
        """Store Python descriptors (property/cached_property/dynamic_attr/etc)."""
        for desc in python_descriptors:
            self.db_manager.add_python_descriptor(
                file_path,
                desc.get("line", 0),
                desc.get("descriptor_kind", ""),
                desc.get("descriptor_type"),
                desc.get("name"),
                desc.get("class_name"),
                desc.get("in_class"),
                desc.get("has_get", False) or desc.get("has_getter", False),
                desc.get("has_set", False) or desc.get("has_setter", False),
                desc.get("has_delete", False) or desc.get("has_deleter", False),
                desc.get("is_data_descriptor", False),
                desc.get("property_name"),
                desc.get("access_type"),
                desc.get("has_computation", False),
                desc.get("has_validation", False),
                desc.get("method_name"),
                desc.get("is_functools", False),
            )
            if "python_descriptors" not in self.counts:
                self.counts["python_descriptors"] = 0
            self.counts["python_descriptors"] += 1

    def _store_python_type_definitions(
        self, file_path: str, python_type_definitions: list, jsx_pass: bool
    ):
        """Store Python type definitions with junction table for TypedDict fields."""
        for typedef in python_type_definitions:
            type_params = typedef.get("type_params") or []
            if isinstance(type_params, str):
                try:
                    type_params = json.loads(type_params)
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(
                        f"DATA CORRUPTION: Invalid type_params JSON.\n"
                        f"  File: {file_path}\n"
                        f"  TypeDef: {typedef.get('name')}\n"
                        f"  Raw data: {repr(type_params)[:200]}\n"
                        f"  Error: {e}"
                    ) from e

            type_param_count = len(type_params) if type_params else None
            type_param_1 = type_params[0] if len(type_params) > 0 else None
            type_param_2 = type_params[1] if len(type_params) > 1 else None
            type_param_3 = type_params[2] if len(type_params) > 2 else None
            type_param_4 = type_params[3] if len(type_params) > 3 else None
            type_param_5 = type_params[4] if len(type_params) > 4 else None

            methods = typedef.get("methods")
            if isinstance(methods, list):
                methods = ",".join(str(m) for m in methods)

            typedef_id = self.db_manager.add_python_type_definition(
                file_path,
                typedef.get("line", 0),
                typedef.get("type_kind", ""),
                typedef.get("name") or typedef.get("typeddict_name"),
                type_param_count,
                type_param_1,
                type_param_2,
                type_param_3,
                type_param_4,
                type_param_5,
                typedef.get("is_runtime_checkable", False),
                methods,
            )

            if typedef.get("type_kind") == "typed_dict":
                fields = typedef.get("fields") or []
                if isinstance(fields, str):
                    try:
                        fields = json.loads(fields)
                    except (json.JSONDecodeError, TypeError) as e:
                        raise ValueError(
                            f"DATA CORRUPTION: Invalid TypedDict fields JSON.\n"
                            f"  File: {file_path}\n"
                            f"  TypeDef: {typedef.get('name')}\n"
                            f"  Raw data: {repr(fields)[:200]}\n"
                            f"  Error: {e}"
                        ) from e

                if isinstance(fields, list):
                    for order, field_info in enumerate(fields):
                        if isinstance(field_info, dict):
                            field_name = field_info.get("field_name") or field_info.get("name")
                            field_type = field_info.get("field_type") or field_info.get("type")
                            required = field_info.get("is_required", True) or field_info.get(
                                "required", True
                            )
                        else:
                            continue

                        if field_name:
                            self.db_manager.add_python_typeddict_field(
                                file_path, typedef_id, field_name, field_type, required, order
                            )
                            if "python_typeddict_fields" not in self.counts:
                                self.counts["python_typeddict_fields"] = 0
                            self.counts["python_typeddict_fields"] += 1
                elif isinstance(fields, dict):
                    for order, (field_name, field_info) in enumerate(fields.items()):
                        if isinstance(field_info, dict):
                            field_type = field_info.get("type")
                            required = field_info.get("required", True)
                        else:
                            field_type = field_info
                            required = True

                        self.db_manager.add_python_typeddict_field(
                            file_path, typedef_id, field_name, field_type, required, order
                        )
                        if "python_typeddict_fields" not in self.counts:
                            self.counts["python_typeddict_fields"] = 0
                        self.counts["python_typeddict_fields"] += 1

            if "python_type_definitions" not in self.counts:
                self.counts["python_type_definitions"] = 0
            self.counts["python_type_definitions"] += 1

    def _store_python_literals(self, file_path: str, python_literals: list, jsx_pass: bool):
        """Store Python Literal/Overload types."""
        for lit in python_literals:
            literal_values = lit.get("literal_values") or lit.get("values") or []
            if isinstance(literal_values, str):
                try:
                    literal_values = json.loads(literal_values)
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(
                        f"DATA CORRUPTION: Invalid literal_values JSON.\n"
                        f"  File: {file_path}\n"
                        f"  Literal: {lit.get('name')}\n"
                        f"  Raw data: {repr(literal_values)[:200]}\n"
                        f"  Error: {e}"
                    ) from e

            def to_str(v):
                return str(v) if v is not None else None

            literal_value_1 = to_str(literal_values[0]) if len(literal_values) > 0 else None
            literal_value_2 = to_str(literal_values[1]) if len(literal_values) > 1 else None
            literal_value_3 = to_str(literal_values[2]) if len(literal_values) > 2 else None
            literal_value_4 = to_str(literal_values[3]) if len(literal_values) > 3 else None
            literal_value_5 = to_str(literal_values[4]) if len(literal_values) > 4 else None

            variants = lit.get("variants")
            if isinstance(variants, list):
                variants = ",".join(str(v) for v in variants)

            self.db_manager.add_python_literal(
                file_path,
                lit.get("line", 0),
                lit.get("literal_kind", ""),
                lit.get("literal_type"),
                lit.get("name"),
                literal_value_1,
                literal_value_2,
                literal_value_3,
                literal_value_4,
                literal_value_5,
                lit.get("function_name"),
                lit.get("overload_count"),
                variants,
            )
            if "python_literals" not in self.counts:
                self.counts["python_literals"] = 0
            self.counts["python_literals"] += 1

    def _store_python_security_findings(
        self, file_path: str, python_security_findings: list, jsx_pass: bool
    ):
        """Store Python security findings (sql_injection/command_injection/etc)."""
        for finding in python_security_findings:
            finding_kind = finding.get("finding_kind") or finding.get("finding_type", "unknown")
            self.db_manager.add_python_security_finding(
                file_path,
                finding.get("line", 0),
                finding_kind,
                finding.get("finding_type"),
                finding.get("function_name"),
                finding.get("decorator_name"),
                finding.get("permissions"),
                finding.get("is_vulnerable", False),
                finding.get("shell_true", False),
                finding.get("is_constant_input", False),
                finding.get("is_critical", False),
                finding.get("has_concatenation", False),
            )
            if "python_security_findings" not in self.counts:
                self.counts["python_security_findings"] = 0
            self.counts["python_security_findings"] += 1

    def _store_python_test_cases(self, file_path: str, python_test_cases: list, jsx_pass: bool):
        """Store Python test cases (unittest/pytest/assertion)."""
        for test in python_test_cases:
            test_kind = test.get("test_kind") or test.get("test_type", "unknown")
            self.db_manager.add_python_test_case(
                file_path,
                test.get("line", 0),
                test_kind,
                test.get("test_type"),
                test.get("name"),
                test.get("function_name"),
                test.get("class_name"),
                test.get("assertion_type"),
                test.get("test_expr"),
            )
            if "python_test_cases" not in self.counts:
                self.counts["python_test_cases"] = 0
            self.counts["python_test_cases"] += 1

    def _store_python_test_fixtures(
        self, file_path: str, python_test_fixtures: list, jsx_pass: bool
    ):
        """Store Python test fixtures (fixture/parametrize/marker/mock/etc)."""
        for fixture in python_test_fixtures:
            fixture_kind = fixture.get("fixture_kind") or fixture.get("fixture_type", "unknown")

            fixture_id = self.db_manager.add_python_test_fixture(
                file_path,
                fixture.get("line", 0),
                fixture_kind,
                fixture.get("fixture_type"),
                fixture.get("name"),
                fixture.get("scope"),
                fixture.get("autouse", False),
                fixture.get("in_function"),
            )
            if "python_test_fixtures" not in self.counts:
                self.counts["python_test_fixtures"] = 0
            self.counts["python_test_fixtures"] += 1

            params = fixture.get("params")
            if params and isinstance(params, list):
                for idx, param in enumerate(params):
                    if isinstance(param, dict):
                        param_name = param.get("name")
                        param_value = param.get("value")
                    else:
                        param_name = str(param) if param else None
                        param_value = None
                    self.db_manager.add_python_fixture_param(
                        file_path, fixture_id, param_name, param_value, idx
                    )
                    if "python_fixture_params" not in self.counts:
                        self.counts["python_fixture_params"] = 0
                    self.counts["python_fixture_params"] += 1

    def _store_python_framework_config(
        self, file_path: str, python_framework_config: list, jsx_pass: bool
    ):
        """Store Python framework configurations (flask/celery/django)."""
        for config in python_framework_config:
            config_kind = config.get("config_kind") or config.get("config_type", "unknown")

            class_name = (
                config.get("form_class_name")
                or config.get("admin_class_name")
                or config.get("schema_class_name")
                or config.get("serializer_class_name")
                or config.get("queryset_name")
                or config.get("manager_name")
                or config.get("class_name")
            )

            model_name = config.get("model_name")

            function_name = (
                config.get("function_name")
                or config.get("factory_name")
                or config.get("resolver_name")
                or config.get("receiver_function")
            )

            target_name = (
                config.get("task_name")
                or config.get("signal_name")
                or config.get("schedule_name")
                or config.get("blueprint_name")
                or config.get("event_name")
                or config.get("command_name")
            )

            base_class = config.get("base_class") or config.get("base_view_class")

            config_id = self.db_manager.add_python_framework_config(
                file_path,
                config.get("line", 0),
                config_kind,
                config.get("config_type"),
                config.get("framework", ""),
                config.get("name"),
                config.get("endpoint"),
                config.get("cache_type"),
                config.get("timeout"),
                class_name,
                model_name,
                function_name,
                target_name,
                base_class,
                config.get("has_process_request", False),
                config.get("has_process_response", False),
                config.get("has_process_exception", False),
                config.get("has_process_view", False),
                config.get("has_process_template_response", False),
            )
            if "python_framework_config" not in self.counts:
                self.counts["python_framework_config"] = 0
            self.counts["python_framework_config"] += 1

            methods = config.get("methods")
            if methods:
                if isinstance(methods, str):
                    method_list = [m.strip() for m in methods.split(",") if m.strip()]
                elif isinstance(methods, list):
                    method_list = methods
                else:
                    method_list = []
            else:
                method_list = []
                if config.get("has_process_request"):
                    method_list.append("process_request")
                if config.get("has_process_response"):
                    method_list.append("process_response")
                if config.get("has_process_exception"):
                    method_list.append("process_exception")
                if config.get("has_process_view"):
                    method_list.append("process_view")
                if config.get("has_process_template_response"):
                    method_list.append("process_template_response")

            for idx, method_name in enumerate(method_list):
                self.db_manager.add_python_framework_method(file_path, config_id, method_name, idx)
                if "python_framework_methods" not in self.counts:
                    self.counts["python_framework_methods"] = 0
                self.counts["python_framework_methods"] += 1

    def _store_python_validation_schemas(
        self, file_path: str, python_validation_schemas: list, jsx_pass: bool
    ):
        """Store Python validation schemas (marshmallow/drf/wtforms)."""
        for schema in python_validation_schemas:
            schema_kind = schema.get("schema_kind") or schema.get("schema_type", "unknown")

            schema_id = self.db_manager.add_python_validation_schema(
                file_path,
                schema.get("line", 0),
                schema_kind,
                schema.get("schema_type"),
                schema.get("framework", ""),
                schema.get("name"),
                schema.get("field_type"),
                schema.get("required", False),
            )
            if "python_validation_schemas" not in self.counts:
                self.counts["python_validation_schemas"] = 0
            self.counts["python_validation_schemas"] += 1

            validators = schema.get("validators")
            if validators and isinstance(validators, list):
                for idx, validator in enumerate(validators):
                    if isinstance(validator, dict):
                        validator_name = validator.get("name", str(validator))
                        validator_type = validator.get("type")
                    else:
                        validator_name = str(validator) if validator else None
                        validator_type = None
                    if validator_name:
                        self.db_manager.add_python_schema_validator(
                            file_path, schema_id, validator_name, validator_type, idx
                        )
                        if "python_schema_validators" not in self.counts:
                            self.counts["python_schema_validators"] = 0
                        self.counts["python_schema_validators"] += 1

    def _store_python_operators(self, file_path: str, python_operators: list, jsx_pass: bool):
        """Store Python operators (binary/unary/membership/chained/ternary/walrus/matmul)."""
        for op in python_operators:
            operator_kind = op.get("operator_kind") or op.get("operator_type", "unknown")
            self.db_manager.add_python_operator(
                file_path,
                op.get("line", 0),
                operator_kind,
                op.get("operator_type"),
                op.get("operator"),
                op.get("in_function"),
                op.get("container_type"),
                op.get("chain_length"),
                op.get("operators"),
                op.get("has_complex_condition", False),
                op.get("variable"),
                op.get("used_in"),
            )
            if "python_operators" not in self.counts:
                self.counts["python_operators"] = 0
            self.counts["python_operators"] += 1

    def _store_python_collections(self, file_path: str, python_collections: list, jsx_pass: bool):
        """Store Python collection operations (dict/list/set/string/builtin)."""
        for coll in python_collections:
            collection_kind = coll.get("collection_kind") or coll.get("collection_type", "unknown")
            self.db_manager.add_python_collection(
                file_path,
                coll.get("line", 0),
                collection_kind,
                coll.get("collection_type"),
                coll.get("operation"),
                coll.get("method"),
                coll.get("in_function"),
                coll.get("has_default", False),
                coll.get("mutates_in_place", False),
                coll.get("builtin"),
                coll.get("has_key", False),
            )
            if "python_collections" not in self.counts:
                self.counts["python_collections"] = 0
            self.counts["python_collections"] += 1

    def _store_python_stdlib_usage(self, file_path: str, python_stdlib_usage: list, jsx_pass: bool):
        """Store Python stdlib usage (re/json/datetime/pathlib/logging/threading/etc)."""
        for usage in python_stdlib_usage:
            stdlib_kind = usage.get("stdlib_kind") or usage.get("module", "unknown")
            self.db_manager.add_python_stdlib_usage(
                file_path,
                usage.get("line", 0),
                stdlib_kind,
                usage.get("module"),
                usage.get("usage_type"),
                usage.get("function_name"),
                usage.get("pattern"),
                usage.get("in_function"),
                usage.get("operation"),
                usage.get("has_flags", False),
                usage.get("direction"),
                usage.get("path_type"),
                usage.get("log_level"),
                usage.get("threading_type"),
                usage.get("is_decorator", False),
            )
            if "python_stdlib_usage" not in self.counts:
                self.counts["python_stdlib_usage"] = 0
            self.counts["python_stdlib_usage"] += 1

    def _store_python_imports_advanced(
        self, file_path: str, python_imports_advanced: list, jsx_pass: bool
    ):
        """Store advanced Python import patterns (static/dynamic/namespace/module_attr/export)."""
        for imp in python_imports_advanced:
            import_kind = imp.get("import_kind") or imp.get("import_type", "unknown")
            self.db_manager.add_python_import_advanced(
                file_path,
                imp.get("line", 0),
                import_kind,
                imp.get("import_type"),
                imp.get("module"),
                imp.get("name"),
                imp.get("alias"),
                imp.get("is_relative", False),
                imp.get("in_function"),
                imp.get("has_alias", False),
                imp.get("imported_names"),
                imp.get("is_wildcard", False),
                imp.get("relative_level"),
                imp.get("attribute"),
                imp.get("default", False) or imp.get("is_default", False),
                imp.get("export_type") or imp.get("type"),
            )
            if "python_imports_advanced" not in self.counts:
                self.counts["python_imports_advanced"] = 0
            self.counts["python_imports_advanced"] += 1

    def _store_python_expressions(self, file_path: str, python_expressions: list, jsx_pass: bool):
        """Store Python expression patterns (slice/tuple/unpack/none/truthiness/format/etc)."""
        for expr in python_expressions:
            expression_kind = expr.get("expression_kind") or expr.get("expression_type", "unknown")
            self.db_manager.add_python_expression(
                file_path,
                expr.get("line", 0),
                expression_kind,
                expr.get("expression_type"),
                expr.get("in_function"),
                expr.get("target"),
                expr.get("has_start", False),
                expr.get("has_stop", False),
                expr.get("has_step", False),
                expr.get("is_assignment", False),
                expr.get("element_count"),
                expr.get("operation"),
                expr.get("has_rest", False),
                expr.get("target_count"),
                expr.get("unpack_type"),
                expr.get("pattern"),
                expr.get("uses_is", False),
                expr.get("format_type"),
                expr.get("has_expressions", False),
                expr.get("var_count"),
                expr.get("context"),
                expr.get("has_globals", False),
                expr.get("has_locals", False),
                expr.get("generator_function"),
                expr.get("yield_expr"),
                expr.get("yield_type"),
                expr.get("in_loop", False),
                expr.get("condition"),
                expr.get("awaited_expr"),
                expr.get("containing_function"),
            )
            if "python_expressions" not in self.counts:
                self.counts["python_expressions"] = 0
            self.counts["python_expressions"] += 1

    def _store_python_comprehensions(
        self, file_path: str, python_comprehensions: list, jsx_pass: bool
    ):
        """Store Python comprehensions (list/dict/set/generator)."""
        for comp in python_comprehensions:
            self.db_manager.add_python_comprehension(
                file_path,
                comp.get("line", 0),
                comp.get("comp_kind", ""),
                comp.get("comp_type"),
                comp.get("iteration_var"),
                comp.get("iteration_source"),
                comp.get("result_expr"),
                comp.get("filter_expr"),
                comp.get("has_filter", False),
                comp.get("nesting_level", 0),
                comp.get("in_function"),
            )
            if "python_comprehensions" not in self.counts:
                self.counts["python_comprehensions"] = 0
            self.counts["python_comprehensions"] += 1

    def _store_python_control_statements(
        self, file_path: str, python_control_statements: list, jsx_pass: bool
    ):
        """Store Python control statements (break/continue/pass/assert/del/with)."""
        for stmt in python_control_statements:
            self.db_manager.add_python_control_statement(
                file_path,
                stmt.get("line", 0),
                stmt.get("statement_kind", ""),
                stmt.get("statement_type"),
                stmt.get("loop_type"),
                stmt.get("condition_type"),
                stmt.get("has_message", False),
                stmt.get("target_count"),
                stmt.get("target_type"),
                stmt.get("context_count"),
                stmt.get("has_alias", False),
                stmt.get("is_async", False),
                stmt.get("in_function"),
            )
            if "python_control_statements" not in self.counts:
                self.counts["python_control_statements"] = 0
            self.counts["python_control_statements"] += 1

    def _store_python_package_configs(
        self, file_path: str, python_package_configs: list, jsx_pass: bool
    ):
        """Store Python package configuration records (pyproject.toml/requirements.txt)."""
        for item in python_package_configs:
            self.db_manager.add_python_package_config(
                file_path=item["file_path"],
                file_type=item.get("file_type", "unknown"),
                project_name=item.get("project_name"),
                project_version=item.get("project_version"),
            )
        if "python_package_configs" not in self.counts:
            self.counts["python_package_configs"] = 0
        self.counts["python_package_configs"] += len(python_package_configs)

    def _store_python_package_dependencies(
        self, file_path: str, python_package_dependencies: list, jsx_pass: bool
    ):
        """Store Python package dependency records."""
        for item in python_package_dependencies:
            self.db_manager.add_python_package_dependency(
                file_path=item["file_path"],
                name=item["name"],
                version_spec=item.get("version_spec"),
                is_dev=item.get("is_dev", False),
                group_name=item.get("group_name"),
                extras=item.get("extras"),
                git_url=item.get("git_url"),
            )
        if "python_package_dependencies" not in self.counts:
            self.counts["python_package_dependencies"] = 0
        self.counts["python_package_dependencies"] += len(python_package_dependencies)

    def _store_python_build_requires(
        self, file_path: str, python_build_requires: list, jsx_pass: bool
    ):
        """Store Python build requirement records (build-system.requires)."""
        for item in python_build_requires:
            self.db_manager.add_python_build_requirement(
                file_path=item["file_path"],
                name=item["name"],
                version_spec=item.get("version_spec"),
            )
        if "python_build_requires" not in self.counts:
            self.counts["python_build_requires"] = 0
        self.counts["python_build_requires"] += len(python_build_requires)
