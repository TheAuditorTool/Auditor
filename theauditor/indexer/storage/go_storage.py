"""Go storage handlers for Go-specific patterns."""

from .base import BaseStorage


class GoStorage(BaseStorage):
    """Go-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            "go_packages": self._store_go_packages,
            "go_imports": self._store_go_imports,
            "go_structs": self._store_go_structs,
            "go_struct_fields": self._store_go_struct_fields,
            "go_interfaces": self._store_go_interfaces,
            "go_interface_methods": self._store_go_interface_methods,
            "go_functions": self._store_go_functions,
            "go_methods": self._store_go_methods,
            "go_func_params": self._store_go_func_params,
            "go_func_returns": self._store_go_func_returns,
            "go_goroutines": self._store_go_goroutines,
            "go_channels": self._store_go_channels,
            "go_channel_ops": self._store_go_channel_ops,
            "go_defer_statements": self._store_go_defer_statements,
            "go_error_returns": self._store_go_error_returns,
            "go_type_assertions": self._store_go_type_assertions,
            "go_routes": self._store_go_routes,
            "go_constants": self._store_go_constants,
            "go_variables": self._store_go_variables,
            "go_type_params": self._store_go_type_params,
            "go_captured_vars": self._store_go_captured_vars,
            "go_middleware": self._store_go_middleware,
            "go_module_configs": self._store_go_module_configs,
            "go_module_dependencies": self._store_go_module_dependencies,
        }

    def _store_go_packages(self, file_path: str, go_packages: list, jsx_pass: bool):
        """Store Go package declarations."""
        for pkg in go_packages:
            self.db_manager.add_go_package(
                pkg.get("file_path", file_path),
                pkg.get("line", 0),
                pkg.get("name", ""),
                pkg.get("import_path"),
            )
            if "go_packages" not in self.counts:
                self.counts["go_packages"] = 0
            self.counts["go_packages"] += 1

    def _store_go_imports(self, file_path: str, go_imports: list, jsx_pass: bool):
        """Store Go imports."""
        for imp in go_imports:
            self.db_manager.add_go_import(
                imp.get("file_path", file_path),
                imp.get("line", 0),
                imp.get("path", ""),
                imp.get("alias"),
                imp.get("is_dot_import", False),
            )
            if "go_imports" not in self.counts:
                self.counts["go_imports"] = 0
            self.counts["go_imports"] += 1

    def _store_go_structs(self, file_path: str, go_structs: list, jsx_pass: bool):
        """Store Go struct definitions."""
        for struct in go_structs:
            self.db_manager.add_go_struct(
                struct.get("file_path", file_path),
                struct.get("line", 0),
                struct.get("name", ""),
                struct.get("is_exported", False),
                struct.get("doc_comment"),
            )
            if "go_structs" not in self.counts:
                self.counts["go_structs"] = 0
            self.counts["go_structs"] += 1

    def _store_go_struct_fields(self, file_path: str, go_struct_fields: list, jsx_pass: bool):
        """Store Go struct fields."""
        for field in go_struct_fields:
            self.db_manager.add_go_struct_field(
                field.get("file_path", file_path),
                field.get("struct_name", ""),
                field.get("field_name", ""),
                field.get("field_type", ""),
                field.get("tag"),
                field.get("is_embedded", False),
                field.get("is_exported", False),
            )
            if "go_struct_fields" not in self.counts:
                self.counts["go_struct_fields"] = 0
            self.counts["go_struct_fields"] += 1

    def _store_go_interfaces(self, file_path: str, go_interfaces: list, jsx_pass: bool):
        """Store Go interface definitions."""
        for iface in go_interfaces:
            self.db_manager.add_go_interface(
                iface.get("file_path", file_path),
                iface.get("line", 0),
                iface.get("name", ""),
                iface.get("is_exported", False),
                iface.get("doc_comment"),
            )
            if "go_interfaces" not in self.counts:
                self.counts["go_interfaces"] = 0
            self.counts["go_interfaces"] += 1

    def _store_go_interface_methods(
        self, file_path: str, go_interface_methods: list, jsx_pass: bool
    ):
        """Store Go interface methods."""
        for method in go_interface_methods:
            self.db_manager.add_go_interface_method(
                method.get("file_path", file_path),
                method.get("interface_name", ""),
                method.get("method_name", ""),
                method.get("signature", ""),
            )
            if "go_interface_methods" not in self.counts:
                self.counts["go_interface_methods"] = 0
            self.counts["go_interface_methods"] += 1

    def _store_go_functions(self, file_path: str, go_functions: list, jsx_pass: bool):
        """Store Go function declarations."""
        for func in go_functions:
            self.db_manager.add_go_function(
                func.get("file_path", file_path),
                func.get("line", 0),
                func.get("name", ""),
                func.get("signature"),
                func.get("is_exported", False),
                func.get("is_async", False),
                func.get("doc_comment"),
            )
            if "go_functions" not in self.counts:
                self.counts["go_functions"] = 0
            self.counts["go_functions"] += 1

    def _store_go_methods(self, file_path: str, go_methods: list, jsx_pass: bool):
        """Store Go method declarations."""
        seen = set()
        for method in go_methods:
            method_file = method.get("file_path", file_path)
            receiver_type = method.get("receiver_type", "")
            method_name = method.get("name", "")
            key = (method_file, receiver_type, method_name)
            if key in seen:
                continue
            seen.add(key)

            self.db_manager.add_go_method(
                method_file,
                method.get("line", 0),
                receiver_type,
                method.get("receiver_name"),
                method.get("is_pointer_receiver", False),
                method_name,
                method.get("signature"),
                method.get("is_exported", False),
            )
            if "go_methods" not in self.counts:
                self.counts["go_methods"] = 0
            self.counts["go_methods"] += 1

    def _store_go_func_params(self, file_path: str, go_func_params: list, jsx_pass: bool):
        """Store Go function parameters."""
        for param in go_func_params:
            self.db_manager.add_go_func_param(
                param.get("file_path", file_path),
                param.get("func_name", ""),
                param.get("func_line", 0),
                param.get("param_index", 0),
                param.get("param_name"),
                param.get("param_type", ""),
                param.get("is_variadic", False),
            )
            if "go_func_params" not in self.counts:
                self.counts["go_func_params"] = 0
            self.counts["go_func_params"] += 1

    def _store_go_func_returns(self, file_path: str, go_func_returns: list, jsx_pass: bool):
        """Store Go function return types."""
        for ret in go_func_returns:
            self.db_manager.add_go_func_return(
                ret.get("file_path", file_path),
                ret.get("func_name", ""),
                ret.get("func_line", 0),
                ret.get("return_index", 0),
                ret.get("return_name"),
                ret.get("return_type", ""),
            )
            if "go_func_returns" not in self.counts:
                self.counts["go_func_returns"] = 0
            self.counts["go_func_returns"] += 1

    def _store_go_goroutines(self, file_path: str, go_goroutines: list, jsx_pass: bool):
        """Store Go goroutine spawns."""
        for goroutine in go_goroutines:
            self.db_manager.add_go_goroutine(
                goroutine.get("file_path", file_path),
                goroutine.get("line", 0),
                goroutine.get("containing_func"),
                goroutine.get("spawned_expr", ""),
                goroutine.get("is_anonymous", False),
            )
            if "go_goroutines" not in self.counts:
                self.counts["go_goroutines"] = 0
            self.counts["go_goroutines"] += 1

    def _store_go_channels(self, file_path: str, go_channels: list, jsx_pass: bool):
        """Store Go channel declarations."""
        for channel in go_channels:
            self.db_manager.add_go_channel(
                channel.get("file_path", file_path),
                channel.get("line", 0),
                channel.get("name", ""),
                channel.get("element_type"),
                channel.get("direction"),
                channel.get("buffer_size"),
            )
            if "go_channels" not in self.counts:
                self.counts["go_channels"] = 0
            self.counts["go_channels"] += 1

    def _store_go_channel_ops(self, file_path: str, go_channel_ops: list, jsx_pass: bool):
        """Store Go channel operations."""
        for op in go_channel_ops:
            self.db_manager.add_go_channel_op(
                op.get("file_path", file_path),
                op.get("line", 0),
                op.get("channel_name"),
                op.get("operation", ""),
                op.get("containing_func"),
            )
            if "go_channel_ops" not in self.counts:
                self.counts["go_channel_ops"] = 0
            self.counts["go_channel_ops"] += 1

    def _store_go_defer_statements(self, file_path: str, go_defer_statements: list, jsx_pass: bool):
        """Store Go defer statements."""
        for defer_stmt in go_defer_statements:
            self.db_manager.add_go_defer_statement(
                defer_stmt.get("file_path", file_path),
                defer_stmt.get("line", 0),
                defer_stmt.get("containing_func"),
                defer_stmt.get("deferred_expr", ""),
            )
            if "go_defer_statements" not in self.counts:
                self.counts["go_defer_statements"] = 0
            self.counts["go_defer_statements"] += 1

    def _store_go_error_returns(self, file_path: str, go_error_returns: list, jsx_pass: bool):
        """Store Go error return tracking."""
        for err_ret in go_error_returns:
            self.db_manager.add_go_error_return(
                err_ret.get("file_path", file_path),
                err_ret.get("line", 0),
                err_ret.get("func_name", ""),
                err_ret.get("returns_error", True),
            )
            if "go_error_returns" not in self.counts:
                self.counts["go_error_returns"] = 0
            self.counts["go_error_returns"] += 1

    def _store_go_type_assertions(self, file_path: str, go_type_assertions: list, jsx_pass: bool):
        """Store Go type assertions."""
        for assertion in go_type_assertions:
            self.db_manager.add_go_type_assertion(
                assertion.get("file_path", file_path),
                assertion.get("line", 0),
                assertion.get("expr", ""),
                assertion.get("asserted_type", ""),
                assertion.get("is_type_switch", False),
                assertion.get("containing_func"),
            )
            if "go_type_assertions" not in self.counts:
                self.counts["go_type_assertions"] = 0
            self.counts["go_type_assertions"] += 1

    def _store_go_routes(self, file_path: str, go_routes: list, jsx_pass: bool):
        """Store Go HTTP routes."""
        for route in go_routes:
            self.db_manager.add_go_route(
                route.get("file_path", file_path),
                route.get("line", 0),
                route.get("framework", ""),
                route.get("method"),
                route.get("path"),
                route.get("handler_func"),
            )
            if "go_routes" not in self.counts:
                self.counts["go_routes"] = 0
            self.counts["go_routes"] += 1

    def _store_go_constants(self, file_path: str, go_constants: list, jsx_pass: bool):
        """Store Go constants."""
        for const in go_constants:
            self.db_manager.add_go_constant(
                const.get("file_path", file_path),
                const.get("line", 0),
                const.get("name", ""),
                const.get("value"),
                const.get("type"),
                const.get("is_exported", False),
            )
            if "go_constants" not in self.counts:
                self.counts["go_constants"] = 0
            self.counts["go_constants"] += 1

    def _store_go_variables(self, file_path: str, go_variables: list, jsx_pass: bool):
        """Store Go variables (package-level and local function variables)."""
        for var in go_variables:
            self.db_manager.add_go_variable(
                var.get("file_path", file_path),
                var.get("line", 0),
                var.get("name", ""),
                var.get("type"),
                var.get("initial_value"),
                var.get("is_exported", False),
                var.get("is_package_level", False),
                var.get("containing_func"),
            )
            if "go_variables" not in self.counts:
                self.counts["go_variables"] = 0
            self.counts["go_variables"] += 1

    def _store_go_type_params(self, file_path: str, go_type_params: list, jsx_pass: bool):
        """Store Go type parameters (generics)."""
        for tp in go_type_params:
            self.db_manager.add_go_type_param(
                tp.get("file_path", file_path),
                tp.get("line", 0),
                tp.get("parent_name", ""),
                tp.get("parent_kind", ""),
                tp.get("param_index", 0),
                tp.get("param_name", ""),
                tp.get("constraint"),
            )
            if "go_type_params" not in self.counts:
                self.counts["go_type_params"] = 0
            self.counts["go_type_params"] += 1

    def _store_go_captured_vars(self, file_path: str, go_captured_vars: list, jsx_pass: bool):
        """Store Go captured variables in goroutines."""
        for cv in go_captured_vars:
            self.db_manager.add_go_captured_var(
                cv.get("file_path", file_path),
                cv.get("line", 0),
                cv.get("goroutine_id", 0),
                cv.get("var_name", ""),
                cv.get("var_type"),
                cv.get("is_loop_var", False),
            )
            if "go_captured_vars" not in self.counts:
                self.counts["go_captured_vars"] = 0
            self.counts["go_captured_vars"] += 1

    def _store_go_middleware(self, file_path: str, go_middleware: list, jsx_pass: bool):
        """Store Go middleware registrations."""
        for mw in go_middleware:
            self.db_manager.add_go_middleware(
                mw.get("file_path", file_path),
                mw.get("line", 0),
                mw.get("framework", ""),
                mw.get("router_var"),
                mw.get("middleware_func", ""),
                mw.get("is_global", False),
            )
            if "go_middleware" not in self.counts:
                self.counts["go_middleware"] = 0
            self.counts["go_middleware"] += 1

    def _store_go_module_configs(
        self, file_path: str, go_module_configs: list, jsx_pass: bool
    ) -> None:
        """Store go.mod module configurations."""
        for cfg in go_module_configs:
            self.db_manager.add_go_module_config(
                cfg.get("file_path", file_path),
                cfg.get("module_path", ""),
                cfg.get("go_version"),
            )
            if "go_module_configs" not in self.counts:
                self.counts["go_module_configs"] = 0
            self.counts["go_module_configs"] += 1

    def _store_go_module_dependencies(
        self, file_path: str, go_module_dependencies: list, jsx_pass: bool
    ) -> None:
        """Store go.mod dependencies."""
        for dep in go_module_dependencies:
            self.db_manager.add_go_module_dependency(
                dep.get("file_path", file_path),
                dep.get("module_path", ""),
                dep.get("version", ""),
                dep.get("is_indirect", False),
            )
            if "go_module_dependencies" not in self.counts:
                self.counts["go_module_dependencies"] = 0
            self.counts["go_module_dependencies"] += 1
