"""Rust storage handlers for Rust language patterns."""

from .base import BaseStorage


class RustStorage(BaseStorage):
    """Rust-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            "rust_modules": self._store_rust_modules,
            "rust_use_statements": self._store_rust_use_statements,
            "rust_functions": self._store_rust_functions,
            "rust_structs": self._store_rust_structs,
            "rust_enums": self._store_rust_enums,
            "rust_traits": self._store_rust_traits,
            "rust_impl_blocks": self._store_rust_impl_blocks,
            "rust_generics": self._store_rust_generics,
            "rust_lifetimes": self._store_rust_lifetimes,
            "rust_macros": self._store_rust_macros,
            "rust_macro_invocations": self._store_rust_macro_invocations,
            "rust_attributes": self._store_rust_attributes,
            "rust_async_functions": self._store_rust_async_functions,
            "rust_await_points": self._store_rust_await_points,
            "rust_unsafe_blocks": self._store_rust_unsafe_blocks,
            "rust_unsafe_traits": self._store_rust_unsafe_traits,
            "rust_struct_fields": self._store_rust_struct_fields,
            "rust_enum_variants": self._store_rust_enum_variants,
            "rust_trait_methods": self._store_rust_trait_methods,
            "rust_extern_functions": self._store_rust_extern_functions,
            "rust_extern_blocks": self._store_rust_extern_blocks,
            "cargo_package_configs": self._store_cargo_package_configs,
            "cargo_dependencies": self._store_cargo_dependencies,
        }

    def _store_rust_modules(self, file_path: str, rust_modules: list, jsx_pass: bool) -> None:
        """Store Rust module declarations."""
        for mod in rust_modules:
            self.db_manager.add_rust_module(
                mod.get("file_path", file_path),
                mod.get("module_name", ""),
                mod.get("line", 0),
                mod.get("visibility"),
                mod.get("is_inline", False),
                mod.get("parent_module"),
            )
            if "rust_modules" not in self.counts:
                self.counts["rust_modules"] = 0
            self.counts["rust_modules"] += 1

    def _store_rust_use_statements(
        self, file_path: str, rust_use_statements: list, jsx_pass: bool
    ) -> None:
        """Store Rust use declarations."""
        for use_stmt in rust_use_statements:
            self.db_manager.add_rust_use_statement(
                use_stmt.get("file_path", file_path),
                use_stmt.get("line", 0),
                use_stmt.get("import_path", ""),
                use_stmt.get("local_name"),
                use_stmt.get("canonical_path"),
                use_stmt.get("is_glob", False),
                use_stmt.get("visibility"),
            )
            if "rust_use_statements" not in self.counts:
                self.counts["rust_use_statements"] = 0
            self.counts["rust_use_statements"] += 1

    def _store_rust_functions(self, file_path: str, rust_functions: list, jsx_pass: bool) -> None:
        """Store Rust function definitions."""
        for func in rust_functions:
            self.db_manager.add_rust_function(
                func.get("file_path", file_path),
                func.get("line", 0),
                func.get("end_line"),
                func.get("name", ""),
                func.get("visibility"),
                func.get("is_async", False),
                func.get("is_unsafe", False),
                func.get("is_const", False),
                func.get("is_extern", False),
                func.get("abi"),
                func.get("return_type"),
                func.get("params_json"),
                func.get("generics"),
                func.get("where_clause"),
            )
            if "rust_functions" not in self.counts:
                self.counts["rust_functions"] = 0
            self.counts["rust_functions"] += 1

    def _store_rust_structs(self, file_path: str, rust_structs: list, jsx_pass: bool) -> None:
        """Store Rust struct definitions."""
        for struct in rust_structs:
            self.db_manager.add_rust_struct(
                struct.get("file_path", file_path),
                struct.get("line", 0),
                struct.get("end_line"),
                struct.get("name", ""),
                struct.get("visibility"),
                struct.get("generics"),
                struct.get("is_tuple_struct", False),
                struct.get("is_unit_struct", False),
                struct.get("derives_json"),
            )
            if "rust_structs" not in self.counts:
                self.counts["rust_structs"] = 0
            self.counts["rust_structs"] += 1

    def _store_rust_enums(self, file_path: str, rust_enums: list, jsx_pass: bool) -> None:
        """Store Rust enum definitions."""
        for enum in rust_enums:
            self.db_manager.add_rust_enum(
                enum.get("file_path", file_path),
                enum.get("line", 0),
                enum.get("end_line"),
                enum.get("name", ""),
                enum.get("visibility"),
                enum.get("generics"),
                enum.get("derives_json"),
            )
            if "rust_enums" not in self.counts:
                self.counts["rust_enums"] = 0
            self.counts["rust_enums"] += 1

    def _store_rust_traits(self, file_path: str, rust_traits: list, jsx_pass: bool) -> None:
        """Store Rust trait definitions."""
        for trait in rust_traits:
            self.db_manager.add_rust_trait(
                trait.get("file_path", file_path),
                trait.get("line", 0),
                trait.get("end_line"),
                trait.get("name", ""),
                trait.get("visibility"),
                trait.get("generics"),
                trait.get("supertraits"),
                trait.get("is_unsafe", False),
                trait.get("is_auto", False),
            )
            if "rust_traits" not in self.counts:
                self.counts["rust_traits"] = 0
            self.counts["rust_traits"] += 1

    def _store_rust_impl_blocks(
        self, file_path: str, rust_impl_blocks: list, jsx_pass: bool
    ) -> None:
        """Store Rust impl blocks."""
        for impl_block in rust_impl_blocks:
            self.db_manager.add_rust_impl_block(
                impl_block.get("file_path", file_path),
                impl_block.get("line", 0),
                impl_block.get("end_line"),
                impl_block.get("target_type_raw", ""),
                impl_block.get("target_type_resolved"),
                impl_block.get("trait_name"),
                impl_block.get("trait_resolved"),
                impl_block.get("generics"),
                impl_block.get("where_clause"),
                impl_block.get("is_unsafe", False),
            )
            if "rust_impl_blocks" not in self.counts:
                self.counts["rust_impl_blocks"] = 0
            self.counts["rust_impl_blocks"] += 1

    def _store_rust_generics(self, file_path: str, rust_generics: list, jsx_pass: bool) -> None:
        """Store Rust generic parameters."""
        for gen in rust_generics:
            self.db_manager.add_rust_generic(
                gen.get("file_path", file_path),
                gen.get("parent_line", 0),
                gen.get("parent_type", ""),
                gen.get("param_name", ""),
                gen.get("param_kind"),
                gen.get("bounds"),
                gen.get("default_value"),
            )
            if "rust_generics" not in self.counts:
                self.counts["rust_generics"] = 0
            self.counts["rust_generics"] += 1

    def _store_rust_lifetimes(self, file_path: str, rust_lifetimes: list, jsx_pass: bool) -> None:
        """Store Rust lifetime parameters."""
        for lt in rust_lifetimes:
            self.db_manager.add_rust_lifetime(
                lt.get("file_path", file_path),
                lt.get("parent_line", 0),
                lt.get("lifetime_name", ""),
                lt.get("is_static", False),
            )
            if "rust_lifetimes" not in self.counts:
                self.counts["rust_lifetimes"] = 0
            self.counts["rust_lifetimes"] += 1

    def _store_rust_macros(self, file_path: str, rust_macros: list, jsx_pass: bool) -> None:
        """Store Rust macro definitions."""
        for macro in rust_macros:
            self.db_manager.add_rust_macro(
                macro.get("file_path", file_path),
                macro.get("line", 0),
                macro.get("name", ""),
                macro.get("macro_type"),
                macro.get("visibility"),
            )
            if "rust_macros" not in self.counts:
                self.counts["rust_macros"] = 0
            self.counts["rust_macros"] += 1

    def _store_rust_macro_invocations(
        self, file_path: str, rust_macro_invocations: list, jsx_pass: bool
    ) -> None:
        """Store Rust macro invocations."""
        for inv in rust_macro_invocations:
            self.db_manager.add_rust_macro_invocation(
                inv.get("file_path", file_path),
                inv.get("line", 0),
                inv.get("macro_name", ""),
                inv.get("containing_function"),
                inv.get("args_sample"),
            )
            if "rust_macro_invocations" not in self.counts:
                self.counts["rust_macro_invocations"] = 0
            self.counts["rust_macro_invocations"] += 1

    def _store_rust_attributes(self, file_path: str, rust_attributes: list, jsx_pass: bool) -> None:
        """Store Rust attribute items (#[attr] decorators)."""
        for attr in rust_attributes:
            self.db_manager.add_rust_attribute(
                attr.get("file_path", file_path),
                attr.get("line", 0),
                attr.get("attribute_name", ""),
                attr.get("args"),
                attr.get("target_type"),
                attr.get("target_name"),
                attr.get("target_line"),
            )
            if "rust_attributes" not in self.counts:
                self.counts["rust_attributes"] = 0
            self.counts["rust_attributes"] += 1

    def _store_rust_async_functions(
        self, file_path: str, rust_async_functions: list, jsx_pass: bool
    ) -> None:
        """Store Rust async function metadata."""
        for func in rust_async_functions:
            self.db_manager.add_rust_async_function(
                func.get("file_path", file_path),
                func.get("line", 0),
                func.get("function_name", ""),
                func.get("return_type"),
                func.get("has_await", False),
                func.get("await_count", 0),
            )
            if "rust_async_functions" not in self.counts:
                self.counts["rust_async_functions"] = 0
            self.counts["rust_async_functions"] += 1

    def _store_rust_await_points(
        self, file_path: str, rust_await_points: list, jsx_pass: bool
    ) -> None:
        """Store Rust await expression locations."""
        for pt in rust_await_points:
            self.db_manager.add_rust_await_point(
                pt.get("file_path", file_path),
                pt.get("line", 0),
                pt.get("containing_function"),
                pt.get("awaited_expression"),
            )
            if "rust_await_points" not in self.counts:
                self.counts["rust_await_points"] = 0
            self.counts["rust_await_points"] += 1

    def _store_rust_unsafe_blocks(
        self, file_path: str, rust_unsafe_blocks: list, jsx_pass: bool
    ) -> None:
        """Store Rust unsafe block locations."""
        for blk in rust_unsafe_blocks:
            self.db_manager.add_rust_unsafe_block(
                blk.get("file_path", file_path),
                blk.get("line_start", 0),
                blk.get("line_end"),
                blk.get("containing_function"),
                blk.get("reason"),
                blk.get("safety_comment"),
                blk.get("has_safety_comment", False),
                blk.get("operations_json"),
            )
            if "rust_unsafe_blocks" not in self.counts:
                self.counts["rust_unsafe_blocks"] = 0
            self.counts["rust_unsafe_blocks"] += 1

    def _store_rust_unsafe_traits(
        self, file_path: str, rust_unsafe_traits: list, jsx_pass: bool
    ) -> None:
        """Store Rust unsafe trait implementations."""
        for ut in rust_unsafe_traits:
            self.db_manager.add_rust_unsafe_trait(
                ut.get("file_path", file_path),
                ut.get("line", 0),
                ut.get("trait_name", ""),
                ut.get("impl_type"),
            )
            if "rust_unsafe_traits" not in self.counts:
                self.counts["rust_unsafe_traits"] = 0
            self.counts["rust_unsafe_traits"] += 1

    def _store_rust_struct_fields(
        self, file_path: str, rust_struct_fields: list, jsx_pass: bool
    ) -> None:
        """Store Rust struct field definitions."""
        for field in rust_struct_fields:
            self.db_manager.add_rust_struct_field(
                field.get("file_path", file_path),
                field.get("struct_line", 0),
                field.get("field_index", 0),
                field.get("field_name"),
                field.get("field_type", ""),
                field.get("visibility"),
                field.get("is_pub", False),
            )
            if "rust_struct_fields" not in self.counts:
                self.counts["rust_struct_fields"] = 0
            self.counts["rust_struct_fields"] += 1

    def _store_rust_enum_variants(
        self, file_path: str, rust_enum_variants: list, jsx_pass: bool
    ) -> None:
        """Store Rust enum variant definitions."""
        for var in rust_enum_variants:
            self.db_manager.add_rust_enum_variant(
                var.get("file_path", file_path),
                var.get("enum_line", 0),
                var.get("variant_index", 0),
                var.get("variant_name", ""),
                var.get("variant_kind"),
                var.get("fields_json"),
                var.get("discriminant"),
            )
            if "rust_enum_variants" not in self.counts:
                self.counts["rust_enum_variants"] = 0
            self.counts["rust_enum_variants"] += 1

    def _store_rust_trait_methods(
        self, file_path: str, rust_trait_methods: list, jsx_pass: bool
    ) -> None:
        """Store Rust trait method signatures."""
        for meth in rust_trait_methods:
            self.db_manager.add_rust_trait_method(
                meth.get("file_path", file_path),
                meth.get("trait_line", 0),
                meth.get("method_line", 0),
                meth.get("method_name", ""),
                meth.get("return_type"),
                meth.get("params_json"),
                meth.get("has_default", False),
                meth.get("is_async", False),
            )
            if "rust_trait_methods" not in self.counts:
                self.counts["rust_trait_methods"] = 0
            self.counts["rust_trait_methods"] += 1

    def _store_rust_extern_functions(
        self, file_path: str, rust_extern_functions: list, jsx_pass: bool
    ) -> None:
        """Store Rust extern function declarations."""
        for func in rust_extern_functions:
            self.db_manager.add_rust_extern_function(
                func.get("file_path", file_path),
                func.get("line", 0),
                func.get("name", ""),
                func.get("abi", "C"),
                func.get("return_type"),
                func.get("params_json"),
                func.get("is_variadic", False),
            )
            if "rust_extern_functions" not in self.counts:
                self.counts["rust_extern_functions"] = 0
            self.counts["rust_extern_functions"] += 1

    def _store_rust_extern_blocks(
        self, file_path: str, rust_extern_blocks: list, jsx_pass: bool
    ) -> None:
        """Store Rust extern block metadata."""
        for blk in rust_extern_blocks:
            self.db_manager.add_rust_extern_block(
                blk.get("file_path", file_path),
                blk.get("line", 0),
                blk.get("end_line"),
                blk.get("abi", "C"),
            )
            if "rust_extern_blocks" not in self.counts:
                self.counts["rust_extern_blocks"] = 0
            self.counts["rust_extern_blocks"] += 1

    def _store_cargo_package_configs(
        self, file_path: str, cargo_package_configs: list, jsx_pass: bool
    ) -> None:
        """Store Cargo.toml package configurations."""
        for cfg in cargo_package_configs:
            self.db_manager.add_cargo_package_config(
                cfg.get("file_path", file_path),
                cfg.get("package_name"),
                cfg.get("package_version"),
                cfg.get("edition"),
            )
            if "cargo_package_configs" not in self.counts:
                self.counts["cargo_package_configs"] = 0
            self.counts["cargo_package_configs"] += 1

    def _store_cargo_dependencies(
        self, file_path: str, cargo_dependencies: list, jsx_pass: bool
    ) -> None:
        """Store Cargo.toml dependencies."""
        for dep in cargo_dependencies:
            self.db_manager.add_cargo_dependency(
                dep.get("file_path", file_path),
                dep.get("name", ""),
                dep.get("version_spec"),
                dep.get("is_dev", False),
                dep.get("features"),
            )
            if "cargo_dependencies" not in self.counts:
                self.counts["cargo_dependencies"] = 0
            self.counts["cargo_dependencies"] += 1
