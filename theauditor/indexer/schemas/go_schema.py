"""Go-specific schema definitions."""

from .utils import Column, TableSchema

GO_PACKAGES = TableSchema(
    name="go_packages",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("import_path", "TEXT"),
    ],
    primary_key=["file"],
    indexes=[
        ("idx_go_packages_name", ["name"]),
    ],
)

GO_IMPORTS = TableSchema(
    name="go_imports",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("path", "TEXT", nullable=False),
        Column("alias", "TEXT"),
        Column("is_dot_import", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_go_imports_file", ["file"]),
        ("idx_go_imports_path", ["path"]),
    ],
)

GO_STRUCTS = TableSchema(
    name="go_structs",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("doc_comment", "TEXT"),
    ],
    primary_key=["file", "name"],
    indexes=[
        ("idx_go_structs_file", ["file"]),
        ("idx_go_structs_name", ["name"]),
    ],
)

GO_STRUCT_FIELDS = TableSchema(
    name="go_struct_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("struct_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),
        Column("tag", "TEXT"),
        Column("is_embedded", "BOOLEAN", default="0"),
        Column("is_exported", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "struct_name", "field_name"],
    indexes=[
        ("idx_go_struct_fields_struct", ["struct_name"]),
    ],
)

GO_INTERFACES = TableSchema(
    name="go_interfaces",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("doc_comment", "TEXT"),
    ],
    primary_key=["file", "name"],
    indexes=[
        ("idx_go_interfaces_file", ["file"]),
        ("idx_go_interfaces_name", ["name"]),
    ],
)

GO_INTERFACE_METHODS = TableSchema(
    name="go_interface_methods",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("interface_name", "TEXT", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("signature", "TEXT", nullable=False),
    ],
    primary_key=["file", "interface_name", "method_name"],
    indexes=[
        ("idx_go_interface_methods_interface", ["interface_name"]),
    ],
)

GO_FUNCTIONS = TableSchema(
    name="go_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("signature", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("is_async", "BOOLEAN", default="0"),
        Column("doc_comment", "TEXT"),
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_go_functions_file", ["file"]),
        ("idx_go_functions_name", ["name"]),
    ],
)

GO_METHODS = TableSchema(
    name="go_methods",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("receiver_type", "TEXT", nullable=False),
        Column("receiver_name", "TEXT"),
        Column("is_pointer_receiver", "BOOLEAN", default="0"),
        Column("name", "TEXT", nullable=False),
        Column("signature", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "receiver_type", "name"],
    indexes=[
        ("idx_go_methods_file", ["file"]),
        ("idx_go_methods_receiver", ["receiver_type"]),
        ("idx_go_methods_name", ["name"]),
    ],
)

GO_FUNC_PARAMS = TableSchema(
    name="go_func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("func_name", "TEXT", nullable=False),
        Column("func_line", "INTEGER", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT"),
        Column("param_type", "TEXT", nullable=False),
        Column("is_variadic", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "func_name", "func_line", "param_index"],
    indexes=[
        ("idx_go_func_params_func", ["func_name"]),
    ],
)

GO_FUNC_RETURNS = TableSchema(
    name="go_func_returns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("func_name", "TEXT", nullable=False),
        Column("func_line", "INTEGER", nullable=False),
        Column("return_index", "INTEGER", nullable=False),
        Column("return_name", "TEXT"),
        Column("return_type", "TEXT", nullable=False),
    ],
    primary_key=["file", "func_name", "func_line", "return_index"],
    indexes=[
        ("idx_go_func_returns_func", ["func_name"]),
    ],
)

GO_GOROUTINES = TableSchema(
    name="go_goroutines",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("containing_func", "TEXT"),
        Column("spawned_expr", "TEXT", nullable=False),
        Column("is_anonymous", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_go_goroutines_file", ["file"]),
        ("idx_go_goroutines_func", ["containing_func"]),
    ],
)

GO_CHANNELS = TableSchema(
    name="go_channels",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("element_type", "TEXT"),
        Column("direction", "TEXT"),
        Column("buffer_size", "INTEGER"),
    ],
    indexes=[
        ("idx_go_channels_file", ["file"]),
        ("idx_go_channels_name", ["name"]),
    ],
)

GO_CHANNEL_OPS = TableSchema(
    name="go_channel_ops",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("channel_name", "TEXT"),
        Column("operation", "TEXT", nullable=False),
        Column("containing_func", "TEXT"),
    ],
    indexes=[
        ("idx_go_channel_ops_file", ["file"]),
        ("idx_go_channel_ops_channel", ["channel_name"]),
    ],
)

GO_DEFER_STATEMENTS = TableSchema(
    name="go_defer_statements",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("containing_func", "TEXT"),
        Column("deferred_expr", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_go_defer_file", ["file"]),
        ("idx_go_defer_func", ["containing_func"]),
    ],
)

GO_ERROR_RETURNS = TableSchema(
    name="go_error_returns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("func_name", "TEXT", nullable=False),
        Column("returns_error", "BOOLEAN", default="1"),
    ],
    indexes=[
        ("idx_go_error_returns_file", ["file"]),
        ("idx_go_error_returns_func", ["func_name"]),
    ],
)

GO_TYPE_ASSERTIONS = TableSchema(
    name="go_type_assertions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("expr", "TEXT", nullable=False),
        Column("asserted_type", "TEXT", nullable=False),
        Column("is_type_switch", "BOOLEAN", default="0"),
        Column("containing_func", "TEXT"),
    ],
    indexes=[
        ("idx_go_type_assertions_file", ["file"]),
    ],
)

GO_ROUTES = TableSchema(
    name="go_routes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),
        Column("method", "TEXT"),
        Column("path", "TEXT"),
        Column("handler_func", "TEXT"),
    ],
    indexes=[
        ("idx_go_routes_file", ["file"]),
        ("idx_go_routes_framework", ["framework"]),
    ],
)

GO_CONSTANTS = TableSchema(
    name="go_constants",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("value", "TEXT"),
        Column("type", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "name"],
    indexes=[
        ("idx_go_constants_file", ["file"]),
        ("idx_go_constants_name", ["name"]),
    ],
)

GO_VARIABLES = TableSchema(
    name="go_variables",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT"),
        Column("initial_value", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("is_package_level", "BOOLEAN", default="0"),
        Column("containing_func", "TEXT"),
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_go_variables_file", ["file"]),
        ("idx_go_variables_name", ["name"]),
        ("idx_go_variables_package_level", ["is_package_level"]),
        ("idx_go_variables_containing_func", ["containing_func"]),
    ],
)

GO_TYPE_PARAMS = TableSchema(
    name="go_type_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("parent_name", "TEXT", nullable=False),
        Column("parent_kind", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("type_constraint", "TEXT"),
    ],
    primary_key=["file", "parent_name", "param_index"],
    indexes=[
        ("idx_go_type_params_parent", ["parent_name"]),
    ],
)

GO_CAPTURED_VARS = TableSchema(
    name="go_captured_vars",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("goroutine_id", "INTEGER", nullable=False),
        Column("var_name", "TEXT", nullable=False),
        Column("var_type", "TEXT"),
        Column("is_loop_var", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_go_captured_vars_file", ["file"]),
        ("idx_go_captured_vars_goroutine", ["goroutine_id"]),
    ],
)

GO_MIDDLEWARE = TableSchema(
    name="go_middleware",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),
        Column("router_var", "TEXT"),
        Column("middleware_func", "TEXT", nullable=False),
        Column("is_global", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_go_middleware_file", ["file"]),
        ("idx_go_middleware_framework", ["framework"]),
    ],
)


GO_MODULE_CONFIGS = TableSchema(
    name="go_module_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("module_path", "TEXT", nullable=False),
        Column("go_version", "TEXT"),
    ],
    primary_key=["file_path"],
    indexes=[
        ("idx_go_mod_module", ["module_path"]),
    ],
)

GO_MODULE_DEPENDENCIES = TableSchema(
    name="go_module_dependencies",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("module_path", "TEXT", nullable=False),
        Column("version", "TEXT", nullable=False),
        Column("is_indirect", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_go_mod_deps_file", ["file_path"]),
        ("idx_go_mod_deps_module", ["module_path"]),
    ],
)


GO_TABLES = {
    "go_packages": GO_PACKAGES,
    "go_imports": GO_IMPORTS,
    "go_structs": GO_STRUCTS,
    "go_struct_fields": GO_STRUCT_FIELDS,
    "go_interfaces": GO_INTERFACES,
    "go_interface_methods": GO_INTERFACE_METHODS,
    "go_functions": GO_FUNCTIONS,
    "go_methods": GO_METHODS,
    "go_func_params": GO_FUNC_PARAMS,
    "go_func_returns": GO_FUNC_RETURNS,
    "go_goroutines": GO_GOROUTINES,
    "go_channels": GO_CHANNELS,
    "go_channel_ops": GO_CHANNEL_OPS,
    "go_defer_statements": GO_DEFER_STATEMENTS,
    "go_error_returns": GO_ERROR_RETURNS,
    "go_type_assertions": GO_TYPE_ASSERTIONS,
    "go_routes": GO_ROUTES,
    "go_constants": GO_CONSTANTS,
    "go_variables": GO_VARIABLES,
    "go_type_params": GO_TYPE_PARAMS,
    "go_captured_vars": GO_CAPTURED_VARS,
    "go_middleware": GO_MIDDLEWARE,
    "go_module_configs": GO_MODULE_CONFIGS,
    "go_module_dependencies": GO_MODULE_DEPENDENCIES,
}
