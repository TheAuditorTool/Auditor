"""Rust-specific schema definitions.

Phase 1 Core Tables (7 tables):
- rust_modules: Module declarations
- rust_use_statements: Use/import declarations
- rust_functions: Function definitions
- rust_structs: Struct definitions
- rust_enums: Enum definitions
- rust_traits: Trait definitions
- rust_impl_blocks: Impl block metadata
"""

from .utils import Column, TableSchema

RUST_MODULES = TableSchema(
    name="rust_modules",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("visibility", "TEXT"),
        Column("is_inline", "BOOLEAN", default="0"),
        Column("parent_module", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_modules_name", ["module_name"]),
    ],
)

RUST_USE_STATEMENTS = TableSchema(
    name="rust_use_statements",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("import_path", "TEXT", nullable=False),
        Column("local_name", "TEXT", nullable=False),
        Column("canonical_path", "TEXT"),
        Column("is_glob", "BOOLEAN", default="0"),
        Column("visibility", "TEXT"),
    ],
    primary_key=["file_path", "line", "local_name"],
    indexes=[
        ("idx_rust_use_canonical", ["canonical_path"]),
    ],
)

RUST_FUNCTIONS = TableSchema(
    name="rust_functions",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("name", "TEXT", nullable=False),
        Column("visibility", "TEXT"),
        Column("is_async", "BOOLEAN", default="0"),
        Column("is_unsafe", "BOOLEAN", default="0"),
        Column("is_const", "BOOLEAN", default="0"),
        Column("is_extern", "BOOLEAN", default="0"),
        Column("abi", "TEXT"),
        Column("return_type", "TEXT"),
        Column("params_json", "TEXT"),
        Column("generics", "TEXT"),
        Column("where_clause", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_functions_name", ["name"]),
        ("idx_rust_functions_async", ["is_async"]),
        ("idx_rust_functions_unsafe", ["is_unsafe"]),
    ],
)

RUST_STRUCTS = TableSchema(
    name="rust_structs",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("name", "TEXT", nullable=False),
        Column("visibility", "TEXT"),
        Column("generics", "TEXT"),
        Column("is_tuple_struct", "BOOLEAN", default="0"),
        Column("is_unit_struct", "BOOLEAN", default="0"),
        Column("derives_json", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_structs_name", ["name"]),
    ],
)

RUST_ENUMS = TableSchema(
    name="rust_enums",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("name", "TEXT", nullable=False),
        Column("visibility", "TEXT"),
        Column("generics", "TEXT"),
        Column("derives_json", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_enums_name", ["name"]),
    ],
)

RUST_TRAITS = TableSchema(
    name="rust_traits",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("name", "TEXT", nullable=False),
        Column("visibility", "TEXT"),
        Column("generics", "TEXT"),
        Column("supertraits", "TEXT"),
        Column("is_unsafe", "BOOLEAN", default="0"),
        Column("is_auto", "BOOLEAN", default="0"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_traits_name", ["name"]),
    ],
)

RUST_IMPL_BLOCKS = TableSchema(
    name="rust_impl_blocks",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("target_type_raw", "TEXT", nullable=False),
        Column("target_type_resolved", "TEXT"),
        Column("trait_name", "TEXT"),
        Column("trait_resolved", "TEXT"),
        Column("generics", "TEXT"),
        Column("where_clause", "TEXT"),
        Column("is_unsafe", "BOOLEAN", default="0"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_impl_target_raw", ["target_type_raw"]),
        ("idx_rust_impl_target_resolved", ["target_type_resolved"]),
        ("idx_rust_impl_trait", ["trait_name"]),
    ],
)


RUST_GENERICS = TableSchema(
    name="rust_generics",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("parent_line", "INTEGER", nullable=False),
        Column("parent_type", "TEXT", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("param_kind", "TEXT"),
        Column("bounds", "TEXT"),
        Column("default_value", "TEXT"),
    ],
    primary_key=["file_path", "parent_line", "param_name"],
    indexes=[
        ("idx_rust_generics_parent", ["parent_type"]),
    ],
)

RUST_LIFETIMES = TableSchema(
    name="rust_lifetimes",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("parent_line", "INTEGER", nullable=False),
        Column("lifetime_name", "TEXT", nullable=False),
        Column("is_static", "BOOLEAN", default="0"),
    ],
    primary_key=["file_path", "parent_line", "lifetime_name"],
    indexes=[],
)

RUST_MACROS = TableSchema(
    name="rust_macros",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("macro_type", "TEXT"),
        Column("visibility", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_macros_name", ["name"]),
    ],
)

RUST_MACRO_INVOCATIONS = TableSchema(
    name="rust_macro_invocations",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("macro_name", "TEXT", nullable=False),
        Column("containing_function", "TEXT"),
        Column("args_sample", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_macro_inv_name", ["macro_name"]),
    ],
)

RUST_ATTRIBUTES = TableSchema(
    name="rust_attributes",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("attribute_name", "TEXT", nullable=False),
        Column("args", "TEXT"),
        Column("target_type", "TEXT"),
        Column("target_name", "TEXT"),
        Column("target_line", "INTEGER"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_attrs_name", ["attribute_name"]),
        ("idx_rust_attrs_target", ["target_type", "target_name"]),
    ],
)

RUST_ASYNC_FUNCTIONS = TableSchema(
    name="rust_async_functions",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("return_type", "TEXT"),
        Column("has_await", "BOOLEAN", default="0"),
        Column("await_count", "INTEGER", default="0"),
    ],
    primary_key=["file_path", "line"],
    indexes=[],
)

RUST_AWAIT_POINTS = TableSchema(
    name="rust_await_points",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("containing_function", "TEXT"),
        Column("awaited_expression", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_await_function", ["containing_function"]),
    ],
)

RUST_UNSAFE_BLOCKS = TableSchema(
    name="rust_unsafe_blocks",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line_start", "INTEGER", nullable=False),
        Column("line_end", "INTEGER"),
        Column("containing_function", "TEXT"),
        Column("reason", "TEXT"),
        Column("safety_comment", "TEXT"),
        Column("has_safety_comment", "BOOLEAN", default="0"),
        Column("operations_json", "TEXT"),
    ],
    primary_key=["file_path", "line_start"],
    indexes=[
        ("idx_rust_unsafe_function", ["containing_function"]),
        ("idx_rust_unsafe_no_comment", ["has_safety_comment"]),
    ],
)

RUST_UNSAFE_TRAITS = TableSchema(
    name="rust_unsafe_traits",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("trait_name", "TEXT", nullable=False),
        Column("impl_type", "TEXT"),
    ],
    primary_key=["file_path", "line"],
    indexes=[],
)

RUST_STRUCT_FIELDS = TableSchema(
    name="rust_struct_fields",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("struct_line", "INTEGER", nullable=False),
        Column("field_index", "INTEGER", nullable=False),
        Column("field_name", "TEXT"),
        Column("field_type", "TEXT", nullable=False),
        Column("visibility", "TEXT"),
        Column("is_pub", "BOOLEAN", default="0"),
    ],
    primary_key=["file_path", "struct_line", "field_index"],
    indexes=[],
)

RUST_ENUM_VARIANTS = TableSchema(
    name="rust_enum_variants",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("enum_line", "INTEGER", nullable=False),
        Column("variant_index", "INTEGER", nullable=False),
        Column("variant_name", "TEXT", nullable=False),
        Column("variant_kind", "TEXT"),
        Column("fields_json", "TEXT"),
        Column("discriminant", "TEXT"),
    ],
    primary_key=["file_path", "enum_line", "variant_index"],
    indexes=[],
)

RUST_TRAIT_METHODS = TableSchema(
    name="rust_trait_methods",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("trait_line", "INTEGER", nullable=False),
        Column("method_line", "INTEGER", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("return_type", "TEXT"),
        Column("params_json", "TEXT"),
        Column("has_default", "BOOLEAN", default="0"),
        Column("is_async", "BOOLEAN", default="0"),
    ],
    primary_key=["file_path", "trait_line", "method_line"],
    indexes=[],
)

RUST_EXTERN_FUNCTIONS = TableSchema(
    name="rust_extern_functions",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("abi", "TEXT", default="'C'"),
        Column("return_type", "TEXT"),
        Column("params_json", "TEXT"),
        Column("is_variadic", "BOOLEAN", default="0"),
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_extern_name", ["name"]),
    ],
)

RUST_EXTERN_BLOCKS = TableSchema(
    name="rust_extern_blocks",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("abi", "TEXT", default="'C'"),
    ],
    primary_key=["file_path", "line"],
    indexes=[],
)


CARGO_PACKAGE_CONFIGS = TableSchema(
    name="cargo_package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("package_name", "TEXT"),
        Column("package_version", "TEXT"),
        Column("edition", "TEXT"),
    ],
    primary_key=["file_path"],
    indexes=[
        ("idx_cargo_pkg_name", ["package_name"]),
    ],
)

CARGO_DEPENDENCIES = TableSchema(
    name="cargo_dependencies",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("version_spec", "TEXT"),
        Column("is_dev", "BOOLEAN", default="0"),
        Column("features", "TEXT"),
    ],
    indexes=[
        ("idx_cargo_deps_file", ["file_path"]),
        ("idx_cargo_deps_name", ["name"]),
    ],
)


RUST_TABLES: dict[str, TableSchema] = {
    "rust_modules": RUST_MODULES,
    "rust_use_statements": RUST_USE_STATEMENTS,
    "rust_functions": RUST_FUNCTIONS,
    "rust_structs": RUST_STRUCTS,
    "rust_enums": RUST_ENUMS,
    "rust_traits": RUST_TRAITS,
    "rust_impl_blocks": RUST_IMPL_BLOCKS,
    "rust_generics": RUST_GENERICS,
    "rust_lifetimes": RUST_LIFETIMES,
    "rust_macros": RUST_MACROS,
    "rust_macro_invocations": RUST_MACRO_INVOCATIONS,
    "rust_attributes": RUST_ATTRIBUTES,
    "rust_async_functions": RUST_ASYNC_FUNCTIONS,
    "rust_await_points": RUST_AWAIT_POINTS,
    "rust_unsafe_blocks": RUST_UNSAFE_BLOCKS,
    "rust_unsafe_traits": RUST_UNSAFE_TRAITS,
    "rust_struct_fields": RUST_STRUCT_FIELDS,
    "rust_enum_variants": RUST_ENUM_VARIANTS,
    "rust_trait_methods": RUST_TRAIT_METHODS,
    "rust_extern_functions": RUST_EXTERN_FUNCTIONS,
    "rust_extern_blocks": RUST_EXTERN_BLOCKS,
    "cargo_package_configs": CARGO_PACKAGE_CONFIGS,
    "cargo_dependencies": CARGO_DEPENDENCIES,
}
