"""Rust-specific database operations."""


class RustDatabaseMixin:
    """Mixin providing add_* methods for RUST_TABLES."""

    def add_rust_module(
        self,
        file_path: str,
        module_name: str,
        line: int,
        visibility: str | None,
        is_inline: bool,
        parent_module: str | None,
    ) -> None:
        """Add a Rust module declaration to the batch."""
        self.generic_batches["rust_modules"].append(
            (
                file_path,
                module_name,
                line,
                visibility,
                1 if is_inline else 0,
                parent_module,
            )
        )

    def add_rust_use_statement(
        self,
        file_path: str,
        line: int,
        import_path: str,
        local_name: str | None,
        canonical_path: str | None,
        is_glob: bool,
        visibility: str | None,
    ) -> None:
        """Add a Rust use declaration to the batch."""
        self.generic_batches["rust_use_statements"].append(
            (
                file_path,
                line,
                import_path,
                local_name,
                canonical_path,
                1 if is_glob else 0,
                visibility,
            )
        )

    def add_rust_function(
        self,
        file_path: str,
        line: int,
        end_line: int | None,
        name: str,
        visibility: str | None,
        is_async: bool,
        is_unsafe: bool,
        is_const: bool,
        is_extern: bool,
        abi: str | None,
        return_type: str | None,
        params_json: str | None,
        generics: str | None,
        where_clause: str | None,
    ) -> None:
        """Add a Rust function definition to the batch."""
        self.generic_batches["rust_functions"].append(
            (
                file_path,
                line,
                end_line,
                name,
                visibility,
                1 if is_async else 0,
                1 if is_unsafe else 0,
                1 if is_const else 0,
                1 if is_extern else 0,
                abi,
                return_type,
                params_json,
                generics,
                where_clause,
            )
        )

    def add_rust_struct(
        self,
        file_path: str,
        line: int,
        end_line: int | None,
        name: str,
        visibility: str | None,
        generics: str | None,
        is_tuple_struct: bool,
        is_unit_struct: bool,
        derives_json: str | None,
    ) -> None:
        """Add a Rust struct definition to the batch."""
        self.generic_batches["rust_structs"].append(
            (
                file_path,
                line,
                end_line,
                name,
                visibility,
                generics,
                1 if is_tuple_struct else 0,
                1 if is_unit_struct else 0,
                derives_json,
            )
        )

    def add_rust_enum(
        self,
        file_path: str,
        line: int,
        end_line: int | None,
        name: str,
        visibility: str | None,
        generics: str | None,
        derives_json: str | None,
    ) -> None:
        """Add a Rust enum definition to the batch."""
        self.generic_batches["rust_enums"].append(
            (
                file_path,
                line,
                end_line,
                name,
                visibility,
                generics,
                derives_json,
            )
        )

    def add_rust_trait(
        self,
        file_path: str,
        line: int,
        end_line: int | None,
        name: str,
        visibility: str | None,
        generics: str | None,
        supertraits: str | None,
        is_unsafe: bool,
        is_auto: bool,
    ) -> None:
        """Add a Rust trait definition to the batch."""
        self.generic_batches["rust_traits"].append(
            (
                file_path,
                line,
                end_line,
                name,
                visibility,
                generics,
                supertraits,
                1 if is_unsafe else 0,
                1 if is_auto else 0,
            )
        )

    def add_rust_impl_block(
        self,
        file_path: str,
        line: int,
        end_line: int | None,
        target_type_raw: str,
        target_type_resolved: str | None,
        trait_name: str | None,
        trait_resolved: str | None,
        generics: str | None,
        where_clause: str | None,
        is_unsafe: bool,
    ) -> None:
        """Add a Rust impl block to the batch."""
        self.generic_batches["rust_impl_blocks"].append(
            (
                file_path,
                line,
                end_line,
                target_type_raw,
                target_type_resolved,
                trait_name,
                trait_resolved,
                generics,
                where_clause,
                1 if is_unsafe else 0,
            )
        )

    def add_rust_generic(
        self,
        file_path: str,
        parent_line: int,
        parent_type: str,
        param_name: str,
        param_kind: str | None,
        bounds: str | None,
        default_value: str | None,
    ) -> None:
        """Add a Rust generic parameter to the batch."""
        self.generic_batches["rust_generics"].append(
            (file_path, parent_line, parent_type, param_name, param_kind, bounds, default_value)
        )

    def add_rust_lifetime(
        self,
        file_path: str,
        parent_line: int,
        lifetime_name: str,
        is_static: bool,
    ) -> None:
        """Add a Rust lifetime parameter to the batch."""
        self.generic_batches["rust_lifetimes"].append(
            (file_path, parent_line, lifetime_name, 1 if is_static else 0)
        )

    def add_rust_macro(
        self,
        file_path: str,
        line: int,
        name: str,
        macro_type: str | None,
        visibility: str | None,
    ) -> None:
        """Add a Rust macro definition to the batch."""
        self.generic_batches["rust_macros"].append((file_path, line, name, macro_type, visibility))

    def add_rust_macro_invocation(
        self,
        file_path: str,
        line: int,
        macro_name: str,
        containing_function: str | None,
        args_sample: str | None,
    ) -> None:
        """Add a Rust macro invocation to the batch."""
        self.generic_batches["rust_macro_invocations"].append(
            (file_path, line, macro_name, containing_function, args_sample)
        )

    def add_rust_attribute(
        self,
        file_path: str,
        line: int,
        attribute_name: str,
        args: str | None,
        target_type: str | None,
        target_name: str | None,
        target_line: int | None,
    ) -> None:
        """Add a Rust attribute item to the batch."""
        self.generic_batches["rust_attributes"].append(
            (file_path, line, attribute_name, args, target_type, target_name, target_line)
        )

    def add_rust_async_function(
        self,
        file_path: str,
        line: int,
        function_name: str,
        return_type: str | None,
        has_await: bool,
        await_count: int,
    ) -> None:
        """Add a Rust async function to the batch."""
        self.generic_batches["rust_async_functions"].append(
            (file_path, line, function_name, return_type, 1 if has_await else 0, await_count)
        )

    def add_rust_await_point(
        self,
        file_path: str,
        line: int,
        containing_function: str | None,
        awaited_expression: str | None,
    ) -> None:
        """Add a Rust await point to the batch."""
        self.generic_batches["rust_await_points"].append(
            (file_path, line, containing_function, awaited_expression)
        )

    def add_rust_unsafe_block(
        self,
        file_path: str,
        line_start: int,
        line_end: int | None,
        containing_function: str | None,
        reason: str | None,
        safety_comment: str | None,
        has_safety_comment: bool,
        operations_json: str | None,
    ) -> None:
        """Add a Rust unsafe block to the batch."""
        self.generic_batches["rust_unsafe_blocks"].append(
            (
                file_path,
                line_start,
                line_end,
                containing_function,
                reason,
                safety_comment,
                1 if has_safety_comment else 0,
                operations_json,
            )
        )

    def add_rust_unsafe_trait(
        self,
        file_path: str,
        line: int,
        trait_name: str,
        impl_type: str | None,
    ) -> None:
        """Add a Rust unsafe trait implementation to the batch."""
        self.generic_batches["rust_unsafe_traits"].append((file_path, line, trait_name, impl_type))

    def add_rust_struct_field(
        self,
        file_path: str,
        struct_line: int,
        field_index: int,
        field_name: str | None,
        field_type: str,
        visibility: str | None,
        is_pub: bool,
    ) -> None:
        """Add a Rust struct field to the batch."""
        self.generic_batches["rust_struct_fields"].append(
            (
                file_path,
                struct_line,
                field_index,
                field_name,
                field_type,
                visibility,
                1 if is_pub else 0,
            )
        )

    def add_rust_enum_variant(
        self,
        file_path: str,
        enum_line: int,
        variant_index: int,
        variant_name: str,
        variant_kind: str | None,
        fields_json: str | None,
        discriminant: str | None,
    ) -> None:
        """Add a Rust enum variant to the batch."""
        self.generic_batches["rust_enum_variants"].append(
            (
                file_path,
                enum_line,
                variant_index,
                variant_name,
                variant_kind,
                fields_json,
                discriminant,
            )
        )

    def add_rust_trait_method(
        self,
        file_path: str,
        trait_line: int,
        method_line: int,
        method_name: str,
        return_type: str | None,
        params_json: str | None,
        has_default: bool,
        is_async: bool,
    ) -> None:
        """Add a Rust trait method to the batch."""
        self.generic_batches["rust_trait_methods"].append(
            (
                file_path,
                trait_line,
                method_line,
                method_name,
                return_type,
                params_json,
                1 if has_default else 0,
                1 if is_async else 0,
            )
        )

    def add_rust_extern_function(
        self,
        file_path: str,
        line: int,
        name: str,
        abi: str,
        return_type: str | None,
        params_json: str | None,
        is_variadic: bool,
    ) -> None:
        """Add a Rust extern function to the batch."""
        self.generic_batches["rust_extern_functions"].append(
            (file_path, line, name, abi, return_type, params_json, 1 if is_variadic else 0)
        )

    def add_rust_extern_block(
        self,
        file_path: str,
        line: int,
        end_line: int | None,
        abi: str,
    ) -> None:
        """Add a Rust extern block to the batch."""
        self.generic_batches["rust_extern_blocks"].append((file_path, line, end_line, abi))

    def add_cargo_package_config(
        self,
        file_path: str,
        package_name: str | None,
        package_version: str | None,
        edition: str | None,
    ) -> None:
        """Add a Cargo package config to the batch."""
        self.generic_batches["cargo_package_configs"].append(
            (file_path, package_name, package_version, edition)
        )

    def add_cargo_dependency(
        self,
        file_path: str,
        name: str,
        version_spec: str | None,
        is_dev: bool,
        features: str | None,
    ) -> None:
        """Add a Cargo dependency to the batch."""
        self.generic_batches["cargo_dependencies"].append(
            (file_path, name, version_spec, 1 if is_dev else 0, features)
        )
