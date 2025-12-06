"""Python-specific database operations."""

import json


class PythonDatabaseMixin:
    """Mixin providing add_* methods for PYTHON_TABLES."""

    def add_python_orm_model(
        self,
        file_path: str,
        line: int,
        model_name: str,
        table_name: str | None,
        orm_type: str = "sqlalchemy",
    ):
        """Add a Python ORM model definition to the batch."""
        self.generic_batches["python_orm_models"].append(
            (file_path, line, model_name, table_name, orm_type)
        )

    def add_python_orm_field(
        self,
        file_path: str,
        line: int,
        model_name: str,
        field_name: str,
        field_type: str | None,
        is_primary_key: bool = False,
        is_foreign_key: bool = False,
        foreign_key_target: str | None = None,
    ):
        """Add a Python ORM field definition to the batch."""
        self.generic_batches["python_orm_fields"].append(
            (
                file_path,
                line,
                model_name,
                field_name,
                field_type,
                1 if is_primary_key else 0,
                1 if is_foreign_key else 0,
                foreign_key_target,
            )
        )

    def add_python_route(
        self,
        file_path: str,
        line: int,
        framework: str,
        method: str,
        pattern: str,
        handler_function: str,
        has_auth: bool = False,
        dependencies: list[str] | None = None,
        blueprint: str | None = None,
    ):
        """Add a Python framework route (Flask/FastAPI) to the batch."""
        dependencies_json = json.dumps(dependencies) if dependencies else None
        self.generic_batches["python_routes"].append(
            (
                file_path,
                line,
                framework,
                method,
                pattern,
                handler_function,
                1 if has_auth else 0,
                dependencies_json,
                blueprint,
            )
        )

    def add_python_validator(
        self,
        file_path: str,
        line: int,
        model_name: str,
        field_name: str | None,
        validator_method: str,
        validator_type: str,
    ):
        """Add a Pydantic validator definition to the batch."""
        self.generic_batches["python_validators"].append(
            (file_path, line, model_name, field_name, validator_method, validator_type)
        )

    def add_python_package_config(
        self,
        file_path: str,
        file_type: str,
        project_name: str | None,
        project_version: str | None,
    ):
        """Add a Python package configuration (pyproject.toml/requirements.txt) to the batch."""
        self.generic_batches["python_package_configs"].append(
            (
                file_path,
                file_type,
                project_name,
                project_version,
            )
        )

    def add_python_package_dependency(
        self,
        file_path: str,
        name: str,
        version_spec: str | None,
        is_dev: bool = False,
        group_name: str | None = None,
        extras: str | None = None,
        git_url: str | None = None,
    ):
        """Add a Python package dependency to the junction table."""
        self.generic_batches["python_package_dependencies"].append(
            (
                file_path,
                name,
                version_spec,
                1 if is_dev else 0,
                group_name,
                extras,
                git_url,
            )
        )

    def add_python_build_requirement(
        self,
        file_path: str,
        name: str,
        version_spec: str | None,
    ):
        """Add a Python build requirement (build-system.requires) to the batch."""
        self.generic_batches["python_build_requires"].append(
            (
                file_path,
                name,
                version_spec,
            )
        )

    def add_python_decorator(
        self,
        file_path: str,
        line: int,
        decorator_name: str,
        decorator_type: str,
        target_type: str,
        target_name: str,
        is_async: bool,
    ):
        """Add a Python decorator usage to the batch."""
        self.generic_batches["python_decorators"].append(
            (
                file_path,
                line,
                decorator_name,
                decorator_type,
                target_type,
                target_name,
                1 if is_async else 0,
            )
        )

    def add_python_django_view(
        self,
        file_path: str,
        line: int,
        view_class_name: str,
        view_type: str,
        base_view_class: str | None,
        model_name: str | None,
        template_name: str | None,
        has_permission_check: bool,
        http_method_names: str | None,
        has_get_queryset_override: bool,
    ):
        """Add a Django Class-Based View to the batch."""
        self.generic_batches["python_django_views"].append(
            (
                file_path,
                line,
                view_class_name,
                view_type,
                base_view_class,
                model_name,
                template_name,
                1 if has_permission_check else 0,
                http_method_names,
                1 if has_get_queryset_override else 0,
            )
        )

    def add_python_django_middleware(
        self,
        file_path: str,
        line: int,
        middleware_class_name: str,
        has_process_request: bool,
        has_process_response: bool,
        has_process_exception: bool,
        has_process_view: bool,
        has_process_template_response: bool,
    ):
        """Add a Django middleware configuration to the batch."""
        self.generic_batches["python_django_middleware"].append(
            (
                file_path,
                line,
                middleware_class_name,
                1 if has_process_request else 0,
                1 if has_process_response else 0,
                1 if has_process_exception else 0,
                1 if has_process_view else 0,
                1 if has_process_template_response else 0,
            )
        )

    def add_python_loop(
        self,
        file_path: str,
        line: int,
        loop_kind: str,
        loop_type: str | None,
        has_else: bool,
        nesting_level: int,
        target_count: int | None,
        in_function: str | None,
        is_infinite: bool,
        estimated_complexity: str | None,
        has_growing_operation: bool,
    ):
        """Add a Python loop (for/while/async for/complexity) to the batch."""
        self.generic_batches["python_loops"].append(
            (
                file_path,
                line,
                loop_kind,
                loop_type,
                1 if has_else else 0,
                nesting_level,
                target_count,
                in_function,
                1 if is_infinite else 0,
                estimated_complexity,
                1 if has_growing_operation else 0,
            )
        )

    def add_python_branch(
        self,
        file_path: str,
        line: int,
        branch_kind: str,
        branch_type: str | None,
        has_else: bool,
        has_elif: bool,
        chain_length: int | None,
        has_complex_condition: bool,
        nesting_level: int,
        case_count: int,
        has_guards: bool,
        has_wildcard: bool,
        pattern_types: str | None,
        exception_types: str | None,
        handling_strategy: str | None,
        variable_name: str | None,
        exception_type: str | None,
        is_re_raise: bool,
        from_exception: str | None,
        message: str | None,
        condition: str | None,
        has_cleanup: bool,
        cleanup_calls: str | None,
        in_function: str | None,
    ):
        """Add a Python branch (if/match/raise/except/finally) to the batch."""
        self.generic_batches["python_branches"].append(
            (
                file_path,
                line,
                branch_kind,
                branch_type,
                1 if has_else else 0,
                1 if has_elif else 0,
                chain_length,
                1 if has_complex_condition else 0,
                nesting_level,
                case_count,
                1 if has_guards else 0,
                1 if has_wildcard else 0,
                pattern_types,
                exception_types,
                handling_strategy,
                variable_name,
                exception_type,
                1 if is_re_raise else 0,
                from_exception,
                message,
                condition,
                1 if has_cleanup else 0,
                cleanup_calls,
                in_function,
            )
        )

    def add_python_function_advanced(
        self,
        file_path: str,
        line: int,
        function_kind: str,
        function_type: str | None,
        name: str | None,
        function_name: str | None,
        yield_count: int,
        has_send: bool,
        has_yield_from: bool,
        is_infinite: bool,
        await_count: int,
        has_async_for: bool,
        has_async_with: bool,
        parameter_count: int | None,
        parameters: str | None,
        body: str | None,
        captures_closure: bool,
        captured_vars: str | None,
        used_in: str | None,
        as_name: str | None,
        context_expr: str | None,
        is_async: bool,
        iter_expr: str | None,
        target_var: str | None,
        base_case_line: int | None,
        calls_function: str | None,
        recursion_type: str | None,
        cache_size: int | None,
        memoization_type: str | None,
        is_recursive: bool,
        has_memoization: bool,
        in_function: str | None,
    ):
        """Add an advanced Python function pattern to the batch."""
        self.generic_batches["python_functions_advanced"].append(
            (
                file_path,
                line,
                function_kind,
                function_type,
                name,
                function_name,
                yield_count,
                1 if has_send else 0,
                1 if has_yield_from else 0,
                1 if is_infinite else 0,
                await_count,
                1 if has_async_for else 0,
                1 if has_async_with else 0,
                parameter_count,
                parameters,
                body,
                1 if captures_closure else 0,
                captured_vars,
                used_in,
                as_name,
                context_expr,
                1 if is_async else 0,
                iter_expr,
                target_var,
                base_case_line,
                calls_function,
                recursion_type,
                cache_size,
                memoization_type,
                1 if is_recursive else 0,
                1 if has_memoization else 0,
                in_function,
            )
        )

    def add_python_io_operation(
        self,
        file_path: str,
        line: int,
        io_kind: str,
        io_type: str | None,
        operation: str | None,
        target: str | None,
        is_static: bool,
        flow_type: str | None,
        function_name: str | None,
        parameter_name: str | None,
        return_expr: str | None,
        is_async: bool,
        in_function: str | None,
    ):
        """Add a Python I/O operation to the batch."""
        self.generic_batches["python_io_operations"].append(
            (
                file_path,
                line,
                io_kind,
                io_type,
                operation,
                target,
                1 if is_static else 0,
                flow_type,
                function_name,
                parameter_name,
                return_expr,
                1 if is_async else 0,
                in_function,
            )
        )

    def add_python_state_mutation(
        self,
        file_path: str,
        line: int,
        mutation_kind: str,
        mutation_type: str | None,
        target: str | None,
        operator: str | None,
        target_type: str | None,
        operation: str | None,
        is_init: bool,
        is_dunder_method: bool,
        is_property_setter: bool,
        in_function: str | None,
    ):
        """Add a Python state mutation to the batch."""
        self.generic_batches["python_state_mutations"].append(
            (
                file_path,
                line,
                mutation_kind,
                mutation_type,
                target,
                operator,
                target_type,
                operation,
                1 if is_init else 0,
                1 if is_dunder_method else 0,
                1 if is_property_setter else 0,
                in_function,
            )
        )

    def add_python_class_feature(
        self,
        file_path: str,
        line: int,
        feature_kind: str,
        feature_type: str | None,
        class_name: str | None,
        name: str | None,
        in_class: str | None,
        metaclass_name: str | None,
        is_definition: bool,
        field_count: int | None,
        frozen: bool,
        enum_name: str | None,
        enum_type: str | None,
        member_count: int | None,
        slot_count: int | None,
        abstract_method_count: int | None,
        method_name: str | None,
        method_type: str | None,
        category: str | None,
        visibility: str | None,
        is_name_mangled: bool,
        decorator: str | None,
        decorator_type: str | None,
        has_arguments: bool,
    ):
        """Add a Python class feature to the batch."""
        self.generic_batches["python_class_features"].append(
            (
                file_path,
                line,
                feature_kind,
                feature_type,
                class_name,
                name,
                in_class,
                metaclass_name,
                1 if is_definition else 0,
                field_count,
                1 if frozen else 0,
                enum_name,
                enum_type,
                member_count,
                slot_count,
                abstract_method_count,
                method_name,
                method_type,
                category,
                visibility,
                1 if is_name_mangled else 0,
                decorator,
                decorator_type,
                1 if has_arguments else 0,
            )
        )

    def add_python_protocol(
        self,
        file_path: str,
        line: int,
        protocol_kind: str,
        protocol_type: str | None,
        class_name: str | None,
        in_function: str | None,
        has_iter: bool,
        has_next: bool,
        is_generator: bool,
        raises_stopiteration: bool,
        has_contains: bool,
        has_getitem: bool,
        has_setitem: bool,
        has_delitem: bool,
        has_len: bool,
        is_mapping: bool,
        is_sequence: bool,
        has_args: bool,
        has_kwargs: bool,
        param_count: int | None,
        has_getstate: bool,
        has_setstate: bool,
        has_reduce: bool,
        has_reduce_ex: bool,
        context_expr: str | None,
        resource_type: str | None,
        variable_name: str | None,
        is_async: bool,
        has_copy: bool,
        has_deepcopy: bool,
    ) -> int:
        """Add a Python protocol - returns temp ID for junction table FK.

        Uses batch+temp_id pattern: queues for later flush, returns negative temp ID.
        base_database.py maps temp IDs to real IDs during flush_batch().
        """
        batch = self.generic_batches["python_protocols"]
        temp_id = -(len(batch) + 1)
        batch.append(
            (
                file_path,
                line,
                protocol_kind,
                protocol_type,
                class_name,
                in_function,
                1 if has_iter else 0,
                1 if has_next else 0,
                1 if is_generator else 0,
                1 if raises_stopiteration else 0,
                1 if has_contains else 0,
                1 if has_getitem else 0,
                1 if has_setitem else 0,
                1 if has_delitem else 0,
                1 if has_len else 0,
                1 if is_mapping else 0,
                1 if is_sequence else 0,
                1 if has_args else 0,
                1 if has_kwargs else 0,
                param_count,
                1 if has_getstate else 0,
                1 if has_setstate else 0,
                1 if has_reduce else 0,
                1 if has_reduce_ex else 0,
                context_expr,
                resource_type,
                variable_name,
                1 if is_async else 0,
                1 if has_copy else 0,
                1 if has_deepcopy else 0,
                temp_id,
            )
        )
        return temp_id

    def add_python_protocol_method(
        self, file_path: str, protocol_id: int, method_name: str, method_order: int = 0
    ):
        """Add a method to the python_protocol_methods junction table."""
        self.generic_batches["python_protocol_methods"].append(
            (file_path, protocol_id, method_name, method_order)
        )

    def add_python_descriptor(
        self,
        file_path: str,
        line: int,
        descriptor_kind: str,
        descriptor_type: str | None,
        name: str | None,
        class_name: str | None,
        in_class: str | None,
        has_get: bool,
        has_set: bool,
        has_delete: bool,
        is_data_descriptor: bool,
        property_name: str | None,
        access_type: str | None,
        has_computation: bool,
        has_validation: bool,
        method_name: str | None,
        is_functools: bool,
    ):
        """Add a Python descriptor to the batch."""
        self.generic_batches["python_descriptors"].append(
            (
                file_path,
                line,
                descriptor_kind,
                descriptor_type,
                name,
                class_name,
                in_class,
                1 if has_get else 0,
                1 if has_set else 0,
                1 if has_delete else 0,
                1 if is_data_descriptor else 0,
                property_name,
                access_type,
                1 if has_computation else 0,
                1 if has_validation else 0,
                method_name,
                1 if is_functools else 0,
            )
        )

    def add_python_type_definition(
        self,
        file_path: str,
        line: int,
        type_kind: str,
        name: str | None,
        type_param_count: int | None,
        type_param_1: str | None,
        type_param_2: str | None,
        type_param_3: str | None,
        type_param_4: str | None,
        type_param_5: str | None,
        is_runtime_checkable: bool,
        methods: str | None,
    ) -> int:
        """Add a Python type definition - returns temp ID for junction table FK.

        Uses batch+temp_id pattern: queues for later flush, returns negative temp ID.
        base_database.py maps temp IDs to real IDs during flush_batch().
        """
        batch = self.generic_batches["python_type_definitions"]
        temp_id = -(len(batch) + 1)
        batch.append(
            (
                file_path,
                line,
                type_kind,
                name,
                type_param_count,
                type_param_1,
                type_param_2,
                type_param_3,
                type_param_4,
                type_param_5,
                1 if is_runtime_checkable else 0,
                methods,
                temp_id,
            )
        )
        return temp_id

    def add_python_typeddict_field(
        self,
        file_path: str,
        typeddict_id: int,
        field_name: str,
        field_type: str | None,
        required: bool = True,
        field_order: int = 0,
    ):
        """Add a field to the python_typeddict_fields junction table."""
        self.generic_batches["python_typeddict_fields"].append(
            (file_path, typeddict_id, field_name, field_type, 1 if required else 0, field_order)
        )

    def add_python_literal(
        self,
        file_path: str,
        line: int,
        literal_kind: str,
        literal_type: str | None,
        name: str | None,
        literal_value_1: str | None,
        literal_value_2: str | None,
        literal_value_3: str | None,
        literal_value_4: str | None,
        literal_value_5: str | None,
        function_name: str | None,
        overload_count: int | None,
        variants: str | None,
    ):
        """Add a Python Literal/Overload type to the batch."""
        self.generic_batches["python_literals"].append(
            (
                file_path,
                line,
                literal_kind,
                literal_type,
                name,
                literal_value_1,
                literal_value_2,
                literal_value_3,
                literal_value_4,
                literal_value_5,
                function_name,
                overload_count,
                variants,
            )
        )

    def add_python_security_finding(
        self,
        file_path: str,
        line: int,
        finding_kind: str,
        finding_type: str | None,
        function_name: str | None,
        decorator_name: str | None,
        permissions: str | None,
        is_vulnerable: bool,
        shell_true: bool,
        is_constant_input: bool,
        is_critical: bool,
        has_concatenation: bool,
    ):
        """Add a Python security finding to the batch."""
        self.generic_batches["python_security_findings"].append(
            (
                file_path,
                line,
                finding_kind,
                finding_type,
                function_name,
                decorator_name,
                permissions,
                1 if is_vulnerable else 0,
                1 if shell_true else 0,
                1 if is_constant_input else 0,
                1 if is_critical else 0,
                1 if has_concatenation else 0,
            )
        )

    def add_python_test_case(
        self,
        file_path: str,
        line: int,
        test_kind: str,
        test_type: str | None,
        name: str | None,
        function_name: str | None,
        class_name: str | None,
        assertion_type: str | None,
        test_expr: str | None,
    ):
        """Add a Python test case to the batch."""
        self.generic_batches["python_test_cases"].append(
            (
                file_path,
                line,
                test_kind,
                test_type,
                name,
                function_name,
                class_name,
                assertion_type,
                test_expr,
            )
        )

    def add_python_test_fixture(
        self,
        file_path: str,
        line: int,
        fixture_kind: str,
        fixture_type: str | None,
        name: str | None,
        scope: str | None,
        autouse: bool,
        in_function: str | None,
    ) -> int:
        """Add a Python test fixture - returns temp ID for junction table FK.

        Uses batch+temp_id pattern: queues for later flush, returns negative temp ID.
        base_database.py maps temp IDs to real IDs during flush_batch().
        """
        batch = self.generic_batches["python_test_fixtures"]
        temp_id = -(len(batch) + 1)
        batch.append(
            (
                file_path,
                line,
                fixture_kind,
                fixture_type,
                name,
                scope,
                1 if autouse else 0,
                in_function,
                temp_id,
            )
        )
        return temp_id

    def add_python_fixture_param(
        self,
        file_path: str,
        fixture_id: int,
        param_name: str | None,
        param_value: str | None,
        param_order: int = 0,
    ):
        """Add a parameter to the python_fixture_params junction table."""
        self.generic_batches["python_fixture_params"].append(
            (file_path, fixture_id, param_name, param_value, param_order)
        )

    def add_python_framework_config(
        self,
        file_path: str,
        line: int,
        config_kind: str,
        config_type: str | None,
        framework: str,
        name: str | None,
        endpoint: str | None,
        cache_type: str | None,
        timeout: int | None,
        class_name: str | None,
        model_name: str | None,
        function_name: str | None,
        target_name: str | None,
        base_class: str | None,
        has_process_request: bool,
        has_process_response: bool,
        has_process_exception: bool,
        has_process_view: bool,
        has_process_template_response: bool,
    ) -> int:
        """Add a Python framework configuration - returns temp ID for junction table FK.

        Uses batch+temp_id pattern: queues for later flush, returns negative temp ID.
        base_database.py maps temp IDs to real IDs during flush_batch().
        """
        batch = self.generic_batches["python_framework_config"]
        temp_id = -(len(batch) + 1)
        batch.append(
            (
                file_path,
                line,
                config_kind,
                config_type,
                framework,
                name,
                endpoint,
                cache_type,
                timeout,
                class_name,
                model_name,
                function_name,
                target_name,
                base_class,
                1 if has_process_request else 0,
                1 if has_process_response else 0,
                1 if has_process_exception else 0,
                1 if has_process_view else 0,
                1 if has_process_template_response else 0,
                temp_id,
            )
        )
        return temp_id

    def add_python_framework_method(
        self, file_path: str, config_id: int, method_name: str, method_order: int = 0
    ):
        """Add a method to the python_framework_methods junction table."""
        self.generic_batches["python_framework_methods"].append(
            (file_path, config_id, method_name, method_order)
        )

    def add_python_validation_schema(
        self,
        file_path: str,
        line: int,
        schema_kind: str,
        schema_type: str | None,
        framework: str,
        name: str | None,
        field_type: str | None,
        required: bool,
    ) -> int:
        """Add a Python validation schema - returns temp ID for junction table FK.

        Uses batch+temp_id pattern: queues for later flush, returns negative temp ID.
        base_database.py maps temp IDs to real IDs during flush_batch().
        """
        batch = self.generic_batches["python_validation_schemas"]
        temp_id = -(len(batch) + 1)
        batch.append(
            (
                file_path,
                line,
                schema_kind,
                schema_type,
                framework,
                name,
                field_type,
                1 if required else 0,
                temp_id,
            )
        )
        return temp_id

    def add_python_schema_validator(
        self,
        file_path: str,
        schema_id: int,
        validator_name: str,
        validator_type: str | None,
        validator_order: int = 0,
    ):
        """Add a validator to the python_schema_validators junction table."""
        self.generic_batches["python_schema_validators"].append(
            (file_path, schema_id, validator_name, validator_type, validator_order)
        )

    def add_python_operator(
        self,
        file_path: str,
        line: int,
        operator_kind: str,
        operator_type: str | None,
        operator: str | None,
        in_function: str | None,
        container_type: str | None,
        chain_length: int | None,
        operators: str | None,
        has_complex_condition: bool,
        variable: str | None,
        used_in: str | None,
    ):
        """Add a Python operator usage to the batch."""
        self.generic_batches["python_operators"].append(
            (
                file_path,
                line,
                operator_kind,
                operator_type,
                operator,
                in_function,
                container_type,
                chain_length,
                operators,
                1 if has_complex_condition else 0,
                variable,
                used_in,
            )
        )

    def add_python_collection(
        self,
        file_path: str,
        line: int,
        collection_kind: str,
        collection_type: str | None,
        operation: str | None,
        method: str | None,
        in_function: str | None,
        has_default: bool,
        mutates_in_place: bool,
        builtin: str | None,
        has_key: bool,
    ):
        """Add a Python collection operation to the batch."""
        self.generic_batches["python_collections"].append(
            (
                file_path,
                line,
                collection_kind,
                collection_type,
                operation,
                method,
                in_function,
                1 if has_default else 0,
                1 if mutates_in_place else 0,
                builtin,
                1 if has_key else 0,
            )
        )

    def add_python_stdlib_usage(
        self,
        file_path: str,
        line: int,
        stdlib_kind: str,
        module: str | None,
        usage_type: str | None,
        function_name: str | None,
        pattern: str | None,
        in_function: str | None,
        operation: str | None,
        has_flags: bool,
        direction: str | None,
        path_type: str | None,
        log_level: str | None,
        threading_type: str | None,
        is_decorator: bool,
    ):
        """Add a Python stdlib usage to the batch."""
        self.generic_batches["python_stdlib_usage"].append(
            (
                file_path,
                line,
                stdlib_kind,
                module,
                usage_type,
                function_name,
                pattern,
                in_function,
                operation,
                1 if has_flags else 0,
                direction,
                path_type,
                log_level,
                threading_type,
                1 if is_decorator else 0,
            )
        )

    def add_python_import_advanced(
        self,
        file_path: str,
        line: int,
        import_kind: str,
        import_type: str | None,
        module: str | None,
        name: str | None,
        alias: str | None,
        is_relative: bool,
        in_function: str | None,
        has_alias: bool,
        imported_names: str | None,
        is_wildcard: bool,
        relative_level: int | None,
        attribute: str | None,
        is_default: bool,
        export_type: str | None,
    ):
        """Add an advanced Python import pattern to the batch."""
        self.generic_batches["python_imports_advanced"].append(
            (
                file_path,
                line,
                import_kind,
                import_type,
                module,
                name,
                alias,
                1 if is_relative else 0,
                in_function,
                1 if has_alias else 0,
                imported_names,
                1 if is_wildcard else 0,
                relative_level,
                attribute,
                1 if is_default else 0,
                export_type,
            )
        )

    def add_python_expression(
        self,
        file_path: str,
        line: int,
        expression_kind: str,
        expression_type: str | None,
        in_function: str | None,
        target: str | None,
        has_start: bool,
        has_stop: bool,
        has_step: bool,
        is_assignment: bool,
        element_count: int | None,
        operation: str | None,
        has_rest: bool,
        target_count: int | None,
        unpack_type: str | None,
        pattern: str | None,
        uses_is: bool,
        format_type: str | None,
        has_expressions: bool,
        var_count: int | None,
        context: str | None,
        has_globals: bool,
        has_locals: bool,
        generator_function: str | None,
        yield_expr: str | None,
        yield_type: str | None,
        in_loop: bool,
        condition: str | None,
        awaited_expr: str | None,
        containing_function: str | None,
    ):
        """Add a Python expression pattern to the batch."""
        self.generic_batches["python_expressions"].append(
            (
                file_path,
                line,
                expression_kind,
                expression_type,
                in_function,
                target,
                1 if has_start else 0,
                1 if has_stop else 0,
                1 if has_step else 0,
                1 if is_assignment else 0,
                element_count,
                operation,
                1 if has_rest else 0,
                target_count,
                unpack_type,
                pattern,
                1 if uses_is else 0,
                format_type,
                1 if has_expressions else 0,
                var_count,
                context,
                1 if has_globals else 0,
                1 if has_locals else 0,
                generator_function,
                yield_expr,
                yield_type,
                1 if in_loop else 0,
                condition,
                awaited_expr,
                containing_function,
            )
        )

    def add_python_comprehension(
        self,
        file_path: str,
        line: int,
        comp_kind: str,
        comp_type: str | None,
        iteration_var: str | None,
        iteration_source: str | None,
        result_expr: str | None,
        filter_expr: str | None,
        has_filter: bool,
        nesting_level: int,
        in_function: str | None,
    ):
        """Add a Python comprehension to the batch."""
        self.generic_batches["python_comprehensions"].append(
            (
                file_path,
                line,
                comp_kind,
                comp_type,
                iteration_var,
                iteration_source,
                result_expr,
                filter_expr,
                1 if has_filter else 0,
                nesting_level,
                in_function,
            )
        )

    def add_python_control_statement(
        self,
        file_path: str,
        line: int,
        statement_kind: str,
        statement_type: str | None,
        loop_type: str | None,
        condition_type: str | None,
        has_message: bool,
        target_count: int | None,
        target_type: str | None,
        context_count: int | None,
        has_alias: bool,
        is_async: bool,
        in_function: str | None,
    ):
        """Add a Python control statement to the batch."""
        self.generic_batches["python_control_statements"].append(
            (
                file_path,
                line,
                statement_kind,
                statement_type,
                loop_type,
                condition_type,
                1 if has_message else 0,
                target_count,
                target_type,
                context_count,
                1 if has_alias else 0,
                1 if is_async else 0,
                in_function,
            )
        )
