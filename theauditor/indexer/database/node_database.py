"""Node.js/TypeScript/React/Vue database operations."""

import json


class NodeDatabaseMixin:
    """Mixin providing add_* methods for NODE_TABLES."""

    def add_class_property(
        self,
        file: str,
        line: int,
        class_name: str,
        property_name: str,
        property_type: str | None = None,
        is_optional: bool = False,
        is_readonly: bool = False,
        access_modifier: str | None = None,
        has_declare: bool = False,
        initializer: str | None = None,
    ):
        """Add a class property declaration record to the batch."""
        self.generic_batches["class_properties"].append(
            (
                file,
                line,
                class_name,
                property_name,
                property_type,
                1 if is_optional else 0,
                1 if is_readonly else 0,
                access_modifier,
                1 if has_declare else 0,
                initializer,
            )
        )

    def add_type_annotation(
        self,
        file_path: str,
        line: int,
        column: int,
        symbol_name: str,
        symbol_kind: str,
        type_annotation: str = None,
        is_any: bool = False,
        is_unknown: bool = False,
        is_generic: bool = False,
        has_type_params: bool = False,
        type_params: str = None,
        return_type: str = None,
        extends_type: str = None,
    ):
        """Add a TypeScript type annotation record to the batch."""
        self.generic_batches["type_annotations"].append(
            (
                file_path,
                line,
                column,
                symbol_name,
                symbol_kind,
                type_annotation,
                is_any,
                is_unknown,
                is_generic,
                has_type_params,
                type_params,
                return_type,
                extends_type,
            )
        )

    def add_react_component(
        self,
        file_path: str,
        name: str,
        component_type: str,
        start_line: int,
        end_line: int,
        has_jsx: bool,
        hooks_used: list[str] | None = None,
        props_type: str | None = None,
    ):
        """Add a React component to the batch."""

        self.generic_batches["react_components"].append(
            (file_path, name, component_type, start_line, end_line, has_jsx, props_type)
        )

        if hooks_used:
            for hook_name in hooks_used:
                if not hook_name:
                    continue
                self.generic_batches["react_component_hooks"].append((file_path, name, hook_name))

    def add_react_hook(
        self,
        file_path: str,
        line: int,
        component_name: str,
        hook_name: str,
        dependency_array: list[str] | None = None,
        dependency_vars: list[str] | None = None,
        callback_body: str | None = None,
        has_cleanup: bool = False,
        cleanup_type: str | None = None,
    ):
        """Add a React hook usage to the batch."""

        deps_array_json = json.dumps(dependency_array) if dependency_array is not None else None

        self.generic_batches["react_hooks"].append(
            (
                file_path,
                line,
                component_name,
                hook_name,
                deps_array_json,
                callback_body,
                has_cleanup,
                cleanup_type,
            )
        )

        if dependency_vars:
            for dep_var in dependency_vars:
                if not dep_var:
                    continue
                self.generic_batches["react_hook_dependencies"].append(
                    (file_path, line, component_name, dep_var)
                )

    def add_vue_component(
        self,
        file_path: str,
        name: str,
        component_type: str,
        start_line: int,
        end_line: int,
        has_template: bool = False,
        has_style: bool = False,
        composition_api_used: bool = False,
    ):
        """Add a Vue component PARENT RECORD ONLY to the batch."""
        self.generic_batches["vue_components"].append(
            (
                file_path,
                name,
                component_type,
                start_line,
                end_line,
                1 if has_template else 0,
                1 if has_style else 0,
                1 if composition_api_used else 0,
            )
        )

    def add_vue_hook(
        self,
        file_path: str,
        line: int,
        component_name: str,
        hook_name: str,
        hook_type: str,
        dependencies: list[str] | None = None,
        return_value: str | None = None,
        is_async: bool = False,
    ):
        """Add a Vue hook/reactivity usage to the batch."""
        deps_json = json.dumps(dependencies) if dependencies else None
        self.generic_batches["vue_hooks"].append(
            (
                file_path,
                line,
                component_name,
                hook_name,
                hook_type,
                deps_json,
                return_value,
                is_async,
            )
        )

    def add_vue_directive(
        self,
        file_path: str,
        line: int,
        directive_name: str,
        expression: str,
        in_component: str,
        has_key: bool = False,
        modifiers: list[str] | None = None,
    ):
        """Add a Vue directive usage to the batch."""
        modifiers_json = json.dumps(modifiers) if modifiers else None
        self.generic_batches["vue_directives"].append(
            (file_path, line, directive_name, expression, in_component, has_key, modifiers_json)
        )

    def add_vue_provide_inject(
        self,
        file_path: str,
        line: int,
        component_name: str,
        operation_type: str,
        key_name: str,
        value_expr: str | None = None,
        is_reactive: bool = False,
    ):
        """Add a Vue provide/inject operation to the batch."""
        self.generic_batches["vue_provide_inject"].append(
            (file_path, line, component_name, operation_type, key_name, value_expr, is_reactive)
        )

    def add_vue_component_prop(
        self,
        file: str,
        component_name: str,
        prop_name: str,
        prop_type: str | None = None,
        is_required: bool = False,
        default_value: str | None = None,
    ):
        """Add a Vue component prop to the batch."""
        self.generic_batches["vue_component_props"].append(
            (file, component_name, prop_name, prop_type, 1 if is_required else 0, default_value)
        )

    def add_vue_component_emit(
        self, file: str, component_name: str, emit_name: str, payload_type: str | None = None
    ):
        """Add a Vue component emit to the batch."""
        self.generic_batches["vue_component_emits"].append(
            (file, component_name, emit_name, payload_type)
        )

    def add_vue_component_setup_return(
        self, file: str, component_name: str, return_name: str, return_type: str | None = None
    ):
        """Add a Vue component setup return to the batch."""
        self.generic_batches["vue_component_setup_returns"].append(
            (file, component_name, return_name, return_type)
        )

    def add_sequelize_model(
        self,
        file: str,
        line: int,
        model_name: str,
        table_name: str | None = None,
        extends_model: bool = False,
    ):
        """Add a Sequelize model to the batch."""
        self.generic_batches["sequelize_models"].append(
            (file, line, model_name, table_name, 1 if extends_model else 0)
        )

    def add_sequelize_association(
        self,
        file: str,
        line: int,
        model_name: str,
        association_type: str,
        target_model: str,
        foreign_key: str | None = None,
        through_table: str | None = None,
    ):
        """Add a Sequelize association to the batch."""
        self.generic_batches["sequelize_associations"].append(
            (file, line, model_name, association_type, target_model, foreign_key, through_table)
        )

    def add_bullmq_queue(
        self, file: str, line: int, queue_name: str, redis_config: str | None = None
    ):
        """Add a BullMQ queue to the batch."""
        self.generic_batches["bullmq_queues"].append((file, line, queue_name, redis_config))

    def add_bullmq_worker(
        self,
        file: str,
        line: int,
        queue_name: str,
        worker_function: str | None = None,
        processor_path: str | None = None,
    ):
        """Add a BullMQ worker to the batch."""
        self.generic_batches["bullmq_workers"].append(
            (file, line, queue_name, worker_function, processor_path)
        )

    def add_angular_component(
        self,
        file: str,
        line: int,
        component_name: str,
        selector: str | None = None,
        template_path: str | None = None,
        style_paths: list | str | None = None,
        has_lifecycle_hooks: bool = False,
    ):
        """Add an Angular component to the batch."""

        self.generic_batches["angular_components"].append(
            (file, line, component_name, selector, template_path, 1 if has_lifecycle_hooks else 0)
        )

        if style_paths:
            paths_list = style_paths

            if isinstance(style_paths, str):
                try:
                    paths_list = json.loads(style_paths)
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(
                        f"DATA CORRUPTION: Invalid style_paths JSON.\n"
                        f"  File: {file}\n"
                        f"  Component: {component_name}\n"
                        f"  Raw data: {repr(style_paths)[:200]}\n"
                        f"  Error: {e}"
                    ) from e
            if isinstance(paths_list, list):
                for style_path in paths_list:
                    if style_path:
                        self.generic_batches["angular_component_styles"].append(
                            (file, component_name, style_path)
                        )

    def add_angular_service(
        self,
        file: str,
        line: int,
        service_name: str,
        is_injectable: bool = True,
        provided_in: str | None = None,
    ):
        """Add an Angular service to the batch."""
        self.generic_batches["angular_services"].append(
            (file, line, service_name, 1 if is_injectable else 0, provided_in)
        )

    def add_angular_module(self, file: str, line: int, module_name: str):
        """Add an Angular module PARENT RECORD ONLY to the batch."""
        self.generic_batches["angular_modules"].append((file, line, module_name))

    def add_angular_guard(
        self,
        file: str,
        line: int,
        guard_name: str,
        guard_type: str,
        implements_interface: str | None = None,
    ):
        """Add an Angular guard to the batch."""
        self.generic_batches["angular_guards"].append(
            (file, line, guard_name, guard_type, implements_interface)
        )

    def add_angular_component_style(self, file: str, component_name: str, style_path: str):
        """Add an Angular component style path to the batch."""
        self.generic_batches["angular_component_styles"].append((file, component_name, style_path))

    def add_angular_module_declaration(
        self,
        file: str,
        module_name: str,
        declaration_name: str,
        declaration_type: str | None = None,
    ):
        """Add an Angular module declaration to the batch."""
        self.generic_batches["angular_module_declarations"].append(
            (file, module_name, declaration_name, declaration_type)
        )

    def add_angular_module_import(self, file: str, module_name: str, imported_module: str):
        """Add an Angular module import to the batch."""
        self.generic_batches["angular_module_imports"].append((file, module_name, imported_module))

    def add_angular_module_provider(
        self, file: str, module_name: str, provider_name: str, provider_type: str | None = None
    ):
        """Add an Angular module provider to the batch."""
        self.generic_batches["angular_module_providers"].append(
            (file, module_name, provider_name, provider_type)
        )

    def add_angular_module_export(self, file: str, module_name: str, exported_name: str):
        """Add an Angular module export to the batch."""
        self.generic_batches["angular_module_exports"].append((file, module_name, exported_name))

    def add_di_injection(
        self,
        file: str,
        line: int,
        target_class: str,
        injected_service: str,
        injection_type: str = "constructor",
    ):
        """Add a DI injection to the batch."""
        self.generic_batches["di_injections"].append(
            (file, line, target_class, injected_service, injection_type)
        )

    def add_package_config(
        self,
        file_path: str,
        package_name: str,
        version: str,
        is_private: bool = False,
    ):
        """Add a package.json configuration to the batch."""
        self.generic_batches["package_configs"].append(
            (file_path, package_name, version, is_private)
        )

    def add_lock_analysis(
        self,
        file_path: str,
        lock_type: str,
        package_manager_version: str | None,
        total_packages: int,
        duplicate_packages: dict | None,
        lock_file_version: str | None,
    ):
        """Add a lock file analysis result to the batch."""
        duplicates_json = json.dumps(duplicate_packages) if duplicate_packages else None

        self.generic_batches["lock_analysis"].append(
            (
                file_path,
                lock_type,
                package_manager_version,
                total_packages,
                duplicates_json,
                lock_file_version,
            )
        )

    def add_import_style(
        self,
        file_path: str,
        line: int,
        package: str,
        import_style: str,
        imported_names: list[str] | None = None,
        alias_name: str | None = None,
        full_statement: str | None = None,
        resolved_path: str | None = None,
    ):
        """Add an import style record to the batch."""

        self.generic_batches["import_styles"].append(
            (file_path, line, package, import_style, alias_name, full_statement, resolved_path)
        )

        if imported_names:
            for imported_name in imported_names:
                if not imported_name:
                    continue
                self.generic_batches["import_style_names"].append((file_path, line, imported_name))

    def add_import_style_name(self, file_path: str, line: int, imported_name: str):
        """Add an import style name record directly to the batch."""
        if imported_name:
            self.generic_batches["import_style_names"].append((file_path, line, imported_name))

    def add_react_component_hook_flat(
        self, component_file: str, component_name: str, hook_name: str
    ):
        """Add a react component hook from flat junction array."""
        if hook_name:
            self.generic_batches["react_component_hooks"].append(
                (component_file, component_name, hook_name)
            )

    def add_react_hook_dependency_flat(
        self, hook_file: str, hook_line: int, hook_component: str, dependency_name: str
    ):
        """Add a react hook dependency from flat junction array."""
        if dependency_name:
            self.generic_batches["react_hook_dependencies"].append(
                (hook_file, hook_line, hook_component, dependency_name)
            )

    def add_frontend_api_call(
        self,
        file: str,
        line: int,
        method: str,
        url_literal: str,
        body_variable: str | None = None,
        function_name: str | None = None,
    ):
        """Add a frontend API call record to the batch."""
        self.generic_batches["frontend_api_calls"].append(
            (file, line, method, url_literal, body_variable, function_name)
        )

    def add_framework(self, name, version, language, path, source, is_primary=False):
        """Add framework to batch."""

        if not name:
            return
        self.generic_batches["frameworks"].append(
            (name, version, language, path, source, is_primary)
        )
        if len(self.generic_batches["frameworks"]) >= self.batch_size:
            self.flush_batch()

    def add_framework_safe_sink(self, framework_id, pattern, sink_type, is_safe, reason):
        """Add framework safe sink to batch."""
        self.generic_batches["framework_safe_sinks"].append(
            (framework_id, pattern, sink_type, is_safe, reason)
        )
        if len(self.generic_batches["framework_safe_sinks"]) >= self.batch_size:
            self.flush_batch()

    def add_framework_taint_pattern(
        self, framework_id: int, pattern: str, pattern_type: str, category: str | None = None
    ):
        """Add framework taint pattern (source/sink) to batch."""
        self.generic_batches["framework_taint_patterns"].append(
            (framework_id, pattern, pattern_type, category)
        )
        if len(self.generic_batches["framework_taint_patterns"]) >= self.batch_size:
            self.flush_batch()

    def get_framework_id(self, name, language):
        """Get framework ID from database."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM frameworks WHERE name = ? AND language = ?", (name, language)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def add_func_param(
        self,
        file: str,
        function_line: int,
        function_name: str,
        param_index: int,
        param_name: str,
        param_type: str | None = None,
    ):
        """Add a function parameter to the batch."""
        self.generic_batches["func_params"].append(
            (file, function_line, function_name, param_index, param_name, param_type)
        )

    def add_func_decorator(
        self,
        file: str,
        function_line: int,
        function_name: str,
        decorator_index: int,
        decorator_name: str,
        decorator_line: int | None = None,
    ):
        """Add a function decorator to the batch."""
        self.generic_batches["func_decorators"].append(
            (file, function_line, function_name, decorator_index, decorator_name, decorator_line)
        )

    def add_func_decorator_arg(
        self,
        file: str,
        function_line: int,
        function_name: str,
        decorator_index: int,
        arg_index: int,
        arg_value: str | None = None,
    ):
        """Add a function decorator argument to the batch."""
        self.generic_batches["func_decorator_args"].append(
            (file, function_line, function_name, decorator_index, arg_index, arg_value)
        )

    def add_func_param_decorator(
        self,
        file: str,
        function_line: int,
        function_name: str,
        param_index: int,
        decorator_name: str,
        decorator_args: str | None = None,
    ):
        """Add a function parameter decorator to the batch (NestJS @Body, @Param, etc)."""
        self.generic_batches["func_param_decorators"].append(
            (file, function_line, function_name, param_index, decorator_name, decorator_args)
        )

    def add_class_decorator(
        self,
        file: str,
        class_line: int,
        class_name: str,
        decorator_index: int,
        decorator_name: str,
        decorator_line: int | None = None,
    ):
        """Add a class decorator to the batch."""
        self.generic_batches["class_decorators"].append(
            (file, class_line, class_name, decorator_index, decorator_name, decorator_line)
        )

    def add_class_decorator_arg(
        self,
        file: str,
        class_line: int,
        class_name: str,
        decorator_index: int,
        arg_index: int,
        arg_value: str | None = None,
    ):
        """Add a class decorator argument to the batch."""
        self.generic_batches["class_decorator_args"].append(
            (file, class_line, class_name, decorator_index, arg_index, arg_value)
        )

    def add_assignment_source_var(
        self, file: str, line: int, target_var: str, source_var: str, var_index: int
    ):
        """Add an assignment source variable to the batch."""
        self.generic_batches["assignment_source_vars"].append(
            (file, line, target_var, source_var, var_index)
        )

    def add_return_source_var(
        self, file: str, line: int, function_name: str, source_var: str, var_index: int
    ):
        """Add a return source variable to the batch."""
        self.generic_batches["return_source_vars"].append(
            (file, line, function_name, source_var, var_index)
        )

    def add_import_specifier(
        self,
        file: str,
        import_line: int,
        specifier_name: str,
        original_name: str | None = None,
        is_default: bool = False,
        is_namespace: bool = False,
        is_named: bool = True,
    ):
        """Add an import specifier to the batch."""
        self.generic_batches["import_specifiers"].append(
            (
                file,
                import_line,
                specifier_name,
                original_name,
                1 if is_default else 0,
                1 if is_namespace else 0,
                1 if is_named else 0,
            )
        )

    def add_sequelize_model_field(
        self,
        file: str,
        model_name: str,
        field_name: str,
        data_type: str,
        is_primary_key: bool = False,
        is_nullable: bool = True,
        is_unique: bool = False,
        default_value: str | None = None,
    ):
        """Add a Sequelize model field to the batch."""
        self.generic_batches["sequelize_model_fields"].append(
            (
                file,
                model_name,
                field_name,
                data_type,
                1 if is_primary_key else 0,
                1 if is_nullable else 0,
                1 if is_unique else 0,
                default_value,
            )
        )

    def add_package_dependency(
        self,
        file_path: str,
        name: str,
        version_spec: str | None,
        is_dev: bool = False,
        is_peer: bool = False,
    ):
        """Add a package dependency to the batch."""
        self.generic_batches["package_dependencies"].append(
            (file_path, name, version_spec, 1 if is_dev else 0, 1 if is_peer else 0)
        )

    def add_package_script(
        self,
        file_path: str,
        script_name: str,
        script_command: str,
    ):
        """Add a package script to the batch."""
        self.generic_batches["package_scripts"].append((file_path, script_name, script_command))

    def add_package_engine(
        self,
        file_path: str,
        engine_name: str,
        version_spec: str | None,
    ):
        """Add a package engine requirement to the batch."""
        self.generic_batches["package_engines"].append((file_path, engine_name, version_spec))

    def add_package_workspace(
        self,
        file_path: str,
        workspace_path: str,
    ):
        """Add a package workspace to the batch."""
        self.generic_batches["package_workspaces"].append((file_path, workspace_path))
