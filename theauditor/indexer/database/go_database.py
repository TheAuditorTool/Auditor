"""Go-specific database operations."""


class GoDatabaseMixin:
    """Mixin providing add_* methods for GO_TABLES."""

    def add_go_package(
        self,
        file_path: str,
        line: int,
        name: str,
        import_path: str | None = None,
    ):
        """Add a Go package declaration to the batch."""
        self.generic_batches["go_packages"].append((file_path, line, name, import_path))

    def add_go_import(
        self,
        file_path: str,
        line: int,
        path: str,
        alias: str | None = None,
        is_dot_import: bool = False,
    ):
        """Add a Go import to the batch."""
        self.generic_batches["go_imports"].append(
            (file_path, line, path, alias, 1 if is_dot_import else 0)
        )

    def add_go_struct(
        self,
        file_path: str,
        line: int,
        name: str,
        is_exported: bool = False,
        doc_comment: str | None = None,
    ):
        """Add a Go struct definition to the batch."""
        self.generic_batches["go_structs"].append(
            (file_path, line, name, 1 if is_exported else 0, doc_comment)
        )

    def add_go_struct_field(
        self,
        file_path: str,
        struct_name: str,
        field_name: str,
        field_type: str,
        tag: str | None = None,
        is_embedded: bool = False,
        is_exported: bool = False,
    ):
        """Add a Go struct field to the batch."""
        self.generic_batches["go_struct_fields"].append(
            (
                file_path,
                struct_name,
                field_name,
                field_type,
                tag,
                1 if is_embedded else 0,
                1 if is_exported else 0,
            )
        )

    def add_go_interface(
        self,
        file_path: str,
        line: int,
        name: str,
        is_exported: bool = False,
        doc_comment: str | None = None,
    ):
        """Add a Go interface definition to the batch."""
        self.generic_batches["go_interfaces"].append(
            (file_path, line, name, 1 if is_exported else 0, doc_comment)
        )

    def add_go_interface_method(
        self,
        file_path: str,
        interface_name: str,
        method_name: str,
        signature: str,
    ):
        """Add a Go interface method to the batch."""
        self.generic_batches["go_interface_methods"].append(
            (file_path, interface_name, method_name, signature)
        )

    def add_go_function(
        self,
        file_path: str,
        line: int,
        name: str,
        signature: str | None = None,
        is_exported: bool = False,
        is_async: bool = False,
        doc_comment: str | None = None,
    ):
        """Add a Go function definition to the batch."""
        self.generic_batches["go_functions"].append(
            (
                file_path,
                line,
                name,
                signature,
                1 if is_exported else 0,
                1 if is_async else 0,
                doc_comment,
            )
        )

    def add_go_method(
        self,
        file_path: str,
        line: int,
        receiver_type: str,
        receiver_name: str | None,
        is_pointer_receiver: bool,
        name: str,
        signature: str | None = None,
        is_exported: bool = False,
    ):
        """Add a Go method (function with receiver) to the batch."""
        self.generic_batches["go_methods"].append(
            (
                file_path,
                line,
                receiver_type,
                receiver_name,
                1 if is_pointer_receiver else 0,
                name,
                signature,
                1 if is_exported else 0,
            )
        )

    def add_go_func_param(
        self,
        file_path: str,
        func_name: str,
        func_line: int,
        param_index: int,
        param_name: str | None,
        param_type: str,
        is_variadic: bool = False,
    ):
        """Add a Go function parameter to the batch."""
        self.generic_batches["go_func_params"].append(
            (
                file_path,
                func_name,
                func_line,
                param_index,
                param_name,
                param_type,
                1 if is_variadic else 0,
            )
        )

    def add_go_func_return(
        self,
        file_path: str,
        func_name: str,
        func_line: int,
        return_index: int,
        return_name: str | None,
        return_type: str,
    ):
        """Add a Go function return type to the batch."""
        self.generic_batches["go_func_returns"].append(
            (file_path, func_name, func_line, return_index, return_name, return_type)
        )

    def add_go_goroutine(
        self,
        file_path: str,
        line: int,
        containing_func: str | None,
        spawned_expr: str,
        is_anonymous: bool = False,
    ):
        """Add a Go goroutine spawn to the batch."""
        self.generic_batches["go_goroutines"].append(
            (file_path, line, containing_func, spawned_expr, 1 if is_anonymous else 0)
        )

    def add_go_channel(
        self,
        file_path: str,
        line: int,
        name: str,
        element_type: str | None = None,
        direction: str | None = None,
        buffer_size: int | None = None,
    ):
        """Add a Go channel declaration to the batch."""
        self.generic_batches["go_channels"].append(
            (file_path, line, name, element_type, direction, buffer_size)
        )

    def add_go_channel_op(
        self,
        file_path: str,
        line: int,
        channel_name: str | None,
        operation: str,
        containing_func: str | None = None,
    ):
        """Add a Go channel operation (send/receive) to the batch."""
        self.generic_batches["go_channel_ops"].append(
            (file_path, line, channel_name, operation, containing_func)
        )

    def add_go_defer_statement(
        self,
        file_path: str,
        line: int,
        containing_func: str | None,
        deferred_expr: str,
    ):
        """Add a Go defer statement to the batch."""
        self.generic_batches["go_defer_statements"].append(
            (file_path, line, containing_func, deferred_expr)
        )

    def add_go_error_return(
        self,
        file_path: str,
        line: int,
        func_name: str,
        returns_error: bool = True,
    ):
        """Add a Go function error return tracking to the batch."""
        self.generic_batches["go_error_returns"].append(
            (file_path, line, func_name, 1 if returns_error else 0)
        )

    def add_go_type_assertion(
        self,
        file_path: str,
        line: int,
        expr: str,
        asserted_type: str,
        is_type_switch: bool = False,
        containing_func: str | None = None,
    ):
        """Add a Go type assertion to the batch."""
        self.generic_batches["go_type_assertions"].append(
            (
                file_path,
                line,
                expr,
                asserted_type,
                1 if is_type_switch else 0,
                containing_func,
            )
        )

    def add_go_route(
        self,
        file_path: str,
        line: int,
        framework: str,
        method: str | None = None,
        path: str | None = None,
        handler_func: str | None = None,
    ):
        """Add a Go HTTP route to the batch."""
        self.generic_batches["go_routes"].append(
            (file_path, line, framework, method, path, handler_func)
        )

    def add_go_constant(
        self,
        file_path: str,
        line: int,
        name: str,
        value: str | None = None,
        const_type: str | None = None,
        is_exported: bool = False,
    ):
        """Add a Go constant to the batch."""
        self.generic_batches["go_constants"].append(
            (file_path, line, name, value, const_type, 1 if is_exported else 0)
        )

    def add_go_variable(
        self,
        file_path: str,
        line: int,
        name: str,
        var_type: str | None = None,
        initial_value: str | None = None,
        is_exported: bool = False,
        is_package_level: bool = False,
        containing_func: str | None = None,
    ):
        """Add a Go variable to the batch."""
        self.generic_batches["go_variables"].append(
            (
                file_path,
                line,
                name,
                var_type,
                initial_value,
                1 if is_exported else 0,
                1 if is_package_level else 0,
                containing_func,
            )
        )

    def add_go_type_param(
        self,
        file_path: str,
        line: int,
        parent_name: str,
        parent_kind: str,
        param_index: int,
        param_name: str,
        type_constraint: str | None = None,
    ):
        """Add a Go type parameter (generics) to the batch."""
        self.generic_batches["go_type_params"].append(
            (file_path, line, parent_name, parent_kind, param_index, param_name, type_constraint)
        )

    def add_go_captured_var(
        self,
        file_path: str,
        line: int,
        goroutine_id: int,
        var_name: str,
        var_type: str | None = None,
        is_loop_var: bool = False,
    ):
        """Add a Go captured variable in goroutine to the batch."""
        self.generic_batches["go_captured_vars"].append(
            (file_path, line, goroutine_id, var_name, var_type, 1 if is_loop_var else 0)
        )

    def add_go_middleware(
        self,
        file_path: str,
        line: int,
        framework: str,
        router_var: str | None,
        middleware_func: str,
        is_global: bool = False,
    ):
        """Add a Go middleware registration to the batch."""
        self.generic_batches["go_middleware"].append(
            (file_path, line, framework, router_var, middleware_func, 1 if is_global else 0)
        )

    def add_go_module_config(
        self,
        file_path: str,
        module_path: str,
        go_version: str | None,
    ) -> None:
        """Add a Go module config to the batch."""
        self.generic_batches["go_module_configs"].append((file_path, module_path, go_version))

    def add_go_module_dependency(
        self,
        file_path: str,
        module_path: str,
        version: str,
        is_indirect: bool,
    ) -> None:
        """Add a Go module dependency to the batch."""
        self.generic_batches["go_module_dependencies"].append(
            (file_path, module_path, version, 1 if is_indirect else 0)
        )
