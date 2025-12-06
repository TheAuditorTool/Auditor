"""Python-specific schema definitions."""

from .utils import Column, ForeignKey, TableSchema

PYTHON_ORM_MODELS = TableSchema(
    name="python_orm_models",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("table_name", "TEXT"),
        Column("orm_type", "TEXT", nullable=False, default="'sqlalchemy'"),
    ],
    primary_key=["file", "model_name"],
    indexes=[
        ("idx_python_orm_models_file", ["file"]),
        ("idx_python_orm_models_type", ["orm_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_ORM_FIELDS = TableSchema(
    name="python_orm_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT"),
        Column("is_primary_key", "BOOLEAN", default="0"),
        Column("is_foreign_key", "BOOLEAN", default="0"),
        Column("foreign_key_target", "TEXT"),
    ],
    primary_key=["file", "model_name", "field_name"],
    indexes=[
        ("idx_python_orm_fields_file", ["file"]),
        ("idx_python_orm_fields_model", ["model_name"]),
        ("idx_python_orm_fields_foreign", ["is_foreign_key"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
        ForeignKey(
            local_columns=["file", "model_name"],
            foreign_table="python_orm_models",
            foreign_columns=["file", "model_name"],
        ),
    ],
)

PYTHON_ROUTES = TableSchema(
    name="python_routes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER"),
        Column("framework", "TEXT", nullable=False),
        Column("method", "TEXT"),
        Column("pattern", "TEXT"),
        Column("handler_function", "TEXT"),
        Column("has_auth", "BOOLEAN", default="0"),
        Column("dependencies", "TEXT"),
        Column("blueprint", "TEXT"),
    ],
    indexes=[
        ("idx_python_routes_file", ["file"]),
        ("idx_python_routes_framework", ["framework"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_VALIDATORS = TableSchema(
    name="python_validators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("field_name", "TEXT"),
        Column("validator_method", "TEXT", nullable=False),
        Column("validator_type", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_validators_file", ["file"]),
        ("idx_python_validators_model", ["model_name"]),
        ("idx_python_validators_type", ["validator_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_PACKAGE_CONFIGS = TableSchema(
    name="python_package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("file_type", "TEXT", nullable=False),
        Column("project_name", "TEXT"),
        Column("project_version", "TEXT"),
        Column("indexed_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["file_path"],
    indexes=[
        ("idx_python_package_configs_file", ["file_path"]),
        ("idx_python_package_configs_type", ["file_type"]),
        ("idx_python_package_configs_project", ["project_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_PACKAGE_DEPENDENCIES = TableSchema(
    name="python_package_dependencies",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("version_spec", "TEXT"),
        Column("is_dev", "INTEGER", default="0"),
        Column("group_name", "TEXT"),
        Column("extras", "TEXT"),
        Column("git_url", "TEXT"),
    ],
    primary_key=["file_path", "name", "group_name"],
    indexes=[
        ("idx_python_package_deps_file", ["file_path"]),
        ("idx_python_package_deps_name", ["name"]),
        ("idx_python_package_deps_dev", ["is_dev"]),
        ("idx_python_package_deps_group", ["group_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_BUILD_REQUIRES = TableSchema(
    name="python_build_requires",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("version_spec", "TEXT"),
    ],
    primary_key=["file_path", "name"],
    indexes=[
        ("idx_python_build_requires_file", ["file_path"]),
        ("idx_python_build_requires_name", ["name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_DECORATORS = TableSchema(
    name="python_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_type", "TEXT", nullable=False),
        Column("target_type", "TEXT", nullable=False),
        Column("target_name", "TEXT", nullable=False),
        Column("is_async", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "decorator_name", "target_name"],
    indexes=[
        ("idx_python_decorators_file", ["file"]),
        ("idx_python_decorators_type", ["decorator_type"]),
        ("idx_python_decorators_target", ["target_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_DJANGO_VIEWS = TableSchema(
    name="python_django_views",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("view_class_name", "TEXT", nullable=False),
        Column("view_type", "TEXT", nullable=False),
        Column("base_view_class", "TEXT"),
        Column("model_name", "TEXT"),
        Column("template_name", "TEXT"),
        Column("has_permission_check", "BOOLEAN", default="0"),
        Column("http_method_names", "TEXT"),
        Column("has_get_queryset_override", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "view_class_name"],
    indexes=[
        ("idx_python_django_views_file", ["file"]),
        ("idx_python_django_views_type", ["view_type"]),
        ("idx_python_django_views_model", ["model_name"]),
        ("idx_python_django_views_no_perm", ["has_permission_check"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_DJANGO_MIDDLEWARE = TableSchema(
    name="python_django_middleware",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("middleware_class_name", "TEXT", nullable=False),
        Column("has_process_request", "BOOLEAN", default="0"),
        Column("has_process_response", "BOOLEAN", default="0"),
        Column("has_process_exception", "BOOLEAN", default="0"),
        Column("has_process_view", "BOOLEAN", default="0"),
        Column("has_process_template_response", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "middleware_class_name"],
    indexes=[
        ("idx_python_django_middleware_file", ["file"]),
        ("idx_python_django_middleware_request", ["has_process_request"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_LOOPS = TableSchema(
    name="python_loops",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("loop_kind", "TEXT", nullable=False),
        Column("loop_type", "TEXT"),
        Column("has_else", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        Column("target_count", "INTEGER"),
        Column("in_function", "TEXT"),
        Column("is_infinite", "INTEGER", default="0"),
        Column("estimated_complexity", "TEXT"),
        Column("has_growing_operation", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_loops_file", ["file"]),
        ("idx_python_loops_kind", ["loop_kind"]),
        ("idx_python_loops_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_BRANCHES = TableSchema(
    name="python_branches",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("branch_kind", "TEXT", nullable=False),
        Column("branch_type", "TEXT"),
        Column("has_else", "INTEGER", default="0"),
        Column("has_elif", "INTEGER", default="0"),
        Column("chain_length", "INTEGER"),
        Column("has_complex_condition", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        Column("case_count", "INTEGER", default="0"),
        Column("has_guards", "INTEGER", default="0"),
        Column("has_wildcard", "INTEGER", default="0"),
        Column("pattern_types", "TEXT"),
        Column("exception_types", "TEXT"),
        Column("handling_strategy", "TEXT"),
        Column("variable_name", "TEXT"),
        Column("exception_type", "TEXT"),
        Column("is_re_raise", "INTEGER", default="0"),
        Column("from_exception", "TEXT"),
        Column("message", "TEXT"),
        Column("condition", "TEXT"),
        Column("has_cleanup", "INTEGER", default="0"),
        Column("cleanup_calls", "TEXT"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_branches_file", ["file"]),
        ("idx_python_branches_kind", ["branch_kind"]),
        ("idx_python_branches_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_FUNCTIONS_ADVANCED = TableSchema(
    name="python_functions_advanced",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_kind", "TEXT", nullable=False),
        Column("function_type", "TEXT"),
        Column("name", "TEXT"),
        Column("function_name", "TEXT"),
        Column("yield_count", "INTEGER", default="0"),
        Column("has_send", "INTEGER", default="0"),
        Column("has_yield_from", "INTEGER", default="0"),
        Column("is_infinite", "INTEGER", default="0"),
        Column("await_count", "INTEGER", default="0"),
        Column("has_async_for", "INTEGER", default="0"),
        Column("has_async_with", "INTEGER", default="0"),
        Column("parameter_count", "INTEGER"),
        Column("parameters", "TEXT"),
        Column("body", "TEXT"),
        Column("captures_closure", "INTEGER", default="0"),
        Column("captured_vars", "TEXT"),
        Column("used_in", "TEXT"),
        Column("as_name", "TEXT"),
        Column("context_expr", "TEXT"),
        Column("is_async", "INTEGER", default="0"),
        Column("iter_expr", "TEXT"),
        Column("target_var", "TEXT"),
        Column("base_case_line", "INTEGER"),
        Column("calls_function", "TEXT"),
        Column("recursion_type", "TEXT"),
        Column("cache_size", "INTEGER"),
        Column("memoization_type", "TEXT"),
        Column("is_recursive", "INTEGER", default="0"),
        Column("has_memoization", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_functions_advanced_file", ["file"]),
        ("idx_python_functions_advanced_kind", ["function_kind"]),
        ("idx_python_functions_advanced_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_IO_OPERATIONS = TableSchema(
    name="python_io_operations",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("io_kind", "TEXT", nullable=False),
        Column("io_type", "TEXT"),
        Column("operation", "TEXT"),
        Column("target", "TEXT"),
        Column("is_static", "INTEGER", default="0"),
        Column("flow_type", "TEXT"),
        Column("function_name", "TEXT"),
        Column("parameter_name", "TEXT"),
        Column("return_expr", "TEXT"),
        Column("is_async", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_io_operations_file", ["file"]),
        ("idx_python_io_operations_kind", ["io_kind"]),
        ("idx_python_io_operations_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_STATE_MUTATIONS = TableSchema(
    name="python_state_mutations",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("mutation_kind", "TEXT", nullable=False),
        Column("mutation_type", "TEXT"),
        Column("target", "TEXT"),
        Column("operator", "TEXT"),
        Column("target_type", "TEXT"),
        Column("operation", "TEXT"),
        Column("is_init", "INTEGER", default="0"),
        Column("is_dunder_method", "INTEGER", default="0"),
        Column("is_property_setter", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_state_mutations_file", ["file"]),
        ("idx_python_state_mutations_kind", ["mutation_kind"]),
        ("idx_python_state_mutations_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_CLASS_FEATURES = TableSchema(
    name="python_class_features",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("feature_kind", "TEXT", nullable=False),
        Column("feature_type", "TEXT"),
        Column("class_name", "TEXT"),
        Column("name", "TEXT"),
        Column("in_class", "TEXT"),
        Column("metaclass_name", "TEXT"),
        Column("is_definition", "INTEGER", default="0"),
        Column("field_count", "INTEGER"),
        Column("frozen", "INTEGER", default="0"),
        Column("enum_name", "TEXT"),
        Column("enum_type", "TEXT"),
        Column("member_count", "INTEGER"),
        Column("slot_count", "INTEGER"),
        Column("abstract_method_count", "INTEGER"),
        Column("method_name", "TEXT"),
        Column("method_type", "TEXT"),
        Column("category", "TEXT"),
        Column("visibility", "TEXT"),
        Column("is_name_mangled", "INTEGER", default="0"),
        Column("decorator", "TEXT"),
        Column("decorator_type", "TEXT"),
        Column("has_arguments", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_class_features_file", ["file"]),
        ("idx_python_class_features_kind", ["feature_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_PROTOCOLS = TableSchema(
    name="python_protocols",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("protocol_kind", "TEXT", nullable=False),
        Column("protocol_type", "TEXT"),
        Column("class_name", "TEXT"),
        Column("in_function", "TEXT"),
        Column("has_iter", "INTEGER", default="0"),
        Column("has_next", "INTEGER", default="0"),
        Column("is_generator", "INTEGER", default="0"),
        Column("raises_stopiteration", "INTEGER", default="0"),
        Column("has_contains", "INTEGER", default="0"),
        Column("has_getitem", "INTEGER", default="0"),
        Column("has_setitem", "INTEGER", default="0"),
        Column("has_delitem", "INTEGER", default="0"),
        Column("has_len", "INTEGER", default="0"),
        Column("is_mapping", "INTEGER", default="0"),
        Column("is_sequence", "INTEGER", default="0"),
        Column("has_args", "INTEGER", default="0"),
        Column("has_kwargs", "INTEGER", default="0"),
        Column("param_count", "INTEGER"),
        Column("has_getstate", "INTEGER", default="0"),
        Column("has_setstate", "INTEGER", default="0"),
        Column("has_reduce", "INTEGER", default="0"),
        Column("has_reduce_ex", "INTEGER", default="0"),
        Column("context_expr", "TEXT"),
        Column("resource_type", "TEXT"),
        Column("variable_name", "TEXT"),
        Column("is_async", "INTEGER", default="0"),
        Column("has_copy", "INTEGER", default="0"),
        Column("has_deepcopy", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_protocols_file", ["file"]),
        ("idx_python_protocols_kind", ["protocol_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_DESCRIPTORS = TableSchema(
    name="python_descriptors",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("descriptor_kind", "TEXT", nullable=False),
        Column("descriptor_type", "TEXT"),
        Column("name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("in_class", "TEXT"),
        Column("has_get", "INTEGER", default="0"),
        Column("has_set", "INTEGER", default="0"),
        Column("has_delete", "INTEGER", default="0"),
        Column("is_data_descriptor", "INTEGER", default="0"),
        Column("property_name", "TEXT"),
        Column("access_type", "TEXT"),
        Column("has_computation", "INTEGER", default="0"),
        Column("has_validation", "INTEGER", default="0"),
        Column("method_name", "TEXT"),
        Column("is_functools", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_descriptors_file", ["file"]),
        ("idx_python_descriptors_kind", ["descriptor_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_TYPE_DEFINITIONS = TableSchema(
    name="python_type_definitions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("type_kind", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("type_param_count", "INTEGER"),
        Column("type_param_1", "TEXT"),
        Column("type_param_2", "TEXT"),
        Column("type_param_3", "TEXT"),
        Column("type_param_4", "TEXT"),
        Column("type_param_5", "TEXT"),
        Column("is_runtime_checkable", "INTEGER", default="0"),
        Column("methods", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_type_definitions_file", ["file"]),
        ("idx_python_type_definitions_kind", ["type_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_LITERALS = TableSchema(
    name="python_literals",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("literal_kind", "TEXT", nullable=False),
        Column("literal_type", "TEXT"),
        Column("name", "TEXT"),
        Column("literal_value_1", "TEXT"),
        Column("literal_value_2", "TEXT"),
        Column("literal_value_3", "TEXT"),
        Column("literal_value_4", "TEXT"),
        Column("literal_value_5", "TEXT"),
        Column("function_name", "TEXT"),
        Column("overload_count", "INTEGER"),
        Column("variants", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_literals_file", ["file"]),
        ("idx_python_literals_kind", ["literal_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_SECURITY_FINDINGS = TableSchema(
    name="python_security_findings",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("finding_kind", "TEXT", nullable=False),
        Column("finding_type", "TEXT"),
        Column("function_name", "TEXT"),
        Column("decorator_name", "TEXT"),
        Column("permissions", "TEXT"),
        Column("is_vulnerable", "INTEGER", default="0"),
        Column("shell_true", "INTEGER", default="0"),
        Column("is_constant_input", "INTEGER", default="0"),
        Column("is_critical", "INTEGER", default="0"),
        Column("has_concatenation", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_security_findings_file", ["file"]),
        ("idx_python_security_findings_kind", ["finding_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_TEST_CASES = TableSchema(
    name="python_test_cases",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("test_kind", "TEXT", nullable=False),
        Column("test_type", "TEXT"),
        Column("name", "TEXT"),
        Column("function_name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("assertion_type", "TEXT"),
        Column("test_expr", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_test_cases_file", ["file"]),
        ("idx_python_test_cases_kind", ["test_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_TEST_FIXTURES = TableSchema(
    name="python_test_fixtures",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("fixture_kind", "TEXT", nullable=False),
        Column("fixture_type", "TEXT"),
        Column("name", "TEXT"),
        Column("scope", "TEXT"),
        Column("autouse", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_test_fixtures_file", ["file"]),
        ("idx_python_test_fixtures_kind", ["fixture_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_FRAMEWORK_CONFIG = TableSchema(
    name="python_framework_config",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("config_kind", "TEXT", nullable=False),
        Column("config_type", "TEXT"),
        Column("framework", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("endpoint", "TEXT"),
        Column("cache_type", "TEXT"),
        Column("timeout", "INTEGER"),
        Column("class_name", "TEXT"),
        Column("model_name", "TEXT"),
        Column("function_name", "TEXT"),
        Column("target_name", "TEXT"),
        Column("base_class", "TEXT"),
        Column("has_process_request", "INTEGER", default="0"),
        Column("has_process_response", "INTEGER", default="0"),
        Column("has_process_exception", "INTEGER", default="0"),
        Column("has_process_view", "INTEGER", default="0"),
        Column("has_process_template_response", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_framework_config_file", ["file"]),
        ("idx_python_framework_config_framework", ["framework"]),
        ("idx_python_framework_config_kind", ["config_kind"]),
        ("idx_python_framework_config_class", ["class_name"]),
        ("idx_python_framework_config_model", ["model_name"]),
        ("idx_python_framework_config_function", ["function_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_VALIDATION_SCHEMAS = TableSchema(
    name="python_validation_schemas",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("schema_kind", "TEXT", nullable=False),
        Column("schema_type", "TEXT"),
        Column("framework", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("field_type", "TEXT"),
        Column("required", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_validation_schemas_file", ["file"]),
        ("idx_python_validation_schemas_framework", ["framework"]),
        ("idx_python_validation_schemas_kind", ["schema_kind"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_OPERATORS = TableSchema(
    name="python_operators",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operator_kind", "TEXT", nullable=False),
        Column("operator_type", "TEXT"),
        Column("operator", "TEXT"),
        Column("in_function", "TEXT"),
        Column("container_type", "TEXT"),
        Column("chain_length", "INTEGER"),
        Column("operators", "TEXT"),
        Column("has_complex_condition", "INTEGER", default="0"),
        Column("variable", "TEXT"),
        Column("used_in", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_operators_file", ["file"]),
        ("idx_python_operators_kind", ["operator_kind"]),
        ("idx_python_operators_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_COLLECTIONS = TableSchema(
    name="python_collections",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("collection_kind", "TEXT", nullable=False),
        Column("collection_type", "TEXT"),
        Column("operation", "TEXT"),
        Column("method", "TEXT"),
        Column("in_function", "TEXT"),
        Column("has_default", "INTEGER", default="0"),
        Column("mutates_in_place", "INTEGER", default="0"),
        Column("builtin", "TEXT"),
        Column("has_key", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_collections_file", ["file"]),
        ("idx_python_collections_kind", ["collection_kind"]),
        ("idx_python_collections_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_STDLIB_USAGE = TableSchema(
    name="python_stdlib_usage",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("stdlib_kind", "TEXT", nullable=False),
        Column("module", "TEXT"),
        Column("usage_type", "TEXT"),
        Column("function_name", "TEXT"),
        Column("pattern", "TEXT"),
        Column("in_function", "TEXT"),
        Column("operation", "TEXT"),
        Column("has_flags", "INTEGER", default="0"),
        Column("direction", "TEXT"),
        Column("path_type", "TEXT"),
        Column("log_level", "TEXT"),
        Column("threading_type", "TEXT"),
        Column("is_decorator", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_stdlib_usage_file", ["file"]),
        ("idx_python_stdlib_usage_kind", ["stdlib_kind"]),
        ("idx_python_stdlib_usage_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_IMPORTS_ADVANCED = TableSchema(
    name="python_imports_advanced",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("import_kind", "TEXT", nullable=False),
        Column("import_type", "TEXT"),
        Column("module", "TEXT"),
        Column("name", "TEXT"),
        Column("alias", "TEXT"),
        Column("is_relative", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
        Column("has_alias", "INTEGER", default="0"),
        Column("imported_names", "TEXT"),
        Column("is_wildcard", "INTEGER", default="0"),
        Column("relative_level", "INTEGER"),
        Column("attribute", "TEXT"),
        Column("is_default", "INTEGER", default="0"),
        Column("export_type", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_imports_advanced_file", ["file"]),
        ("idx_python_imports_advanced_kind", ["import_kind"]),
        ("idx_python_imports_advanced_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_EXPRESSIONS = TableSchema(
    name="python_expressions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("expression_kind", "TEXT", nullable=False),
        Column("expression_type", "TEXT"),
        Column("in_function", "TEXT"),
        Column("target", "TEXT"),
        Column("has_start", "INTEGER", default="0"),
        Column("has_stop", "INTEGER", default="0"),
        Column("has_step", "INTEGER", default="0"),
        Column("is_assignment", "INTEGER", default="0"),
        Column("element_count", "INTEGER"),
        Column("operation", "TEXT"),
        Column("has_rest", "INTEGER", default="0"),
        Column("target_count", "INTEGER"),
        Column("unpack_type", "TEXT"),
        Column("pattern", "TEXT"),
        Column("uses_is", "INTEGER", default="0"),
        Column("format_type", "TEXT"),
        Column("has_expressions", "INTEGER", default="0"),
        Column("var_count", "INTEGER"),
        Column("context", "TEXT"),
        Column("has_globals", "INTEGER", default="0"),
        Column("has_locals", "INTEGER", default="0"),
        Column("generator_function", "TEXT"),
        Column("yield_expr", "TEXT"),
        Column("yield_type", "TEXT"),
        Column("in_loop", "INTEGER", default="0"),
        Column("condition", "TEXT"),
        Column("awaited_expr", "TEXT"),
        Column("containing_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_expressions_file", ["file"]),
        ("idx_python_expressions_kind", ["expression_kind"]),
        ("idx_python_expressions_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_COMPREHENSIONS = TableSchema(
    name="python_comprehensions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("comp_kind", "TEXT", nullable=False),
        Column("comp_type", "TEXT"),
        Column("iteration_var", "TEXT"),
        Column("iteration_source", "TEXT"),
        Column("result_expr", "TEXT"),
        Column("filter_expr", "TEXT"),
        Column("has_filter", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pcomp_file", ["file"]),
        ("idx_pcomp_kind", ["comp_kind"]),
        ("idx_pcomp_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

PYTHON_CONTROL_STATEMENTS = TableSchema(
    name="python_control_statements",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("statement_kind", "TEXT", nullable=False),
        Column("statement_type", "TEXT"),
        Column("loop_type", "TEXT"),
        Column("condition_type", "TEXT"),
        Column("has_message", "INTEGER", default="0"),
        Column("target_count", "INTEGER"),
        Column("target_type", "TEXT"),
        Column("context_count", "INTEGER"),
        Column("has_alias", "INTEGER", default="0"),
        Column("is_async", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pcs_file", ["file"]),
        ("idx_pcs_kind", ["statement_kind"]),
        ("idx_pcs_function", ["in_function"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_PROTOCOL_METHODS = TableSchema(
    name="python_protocol_methods",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("protocol_id", "INTEGER", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("method_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_ppm_file", ["file"]),
        ("idx_ppm_protocol", ["protocol_id"]),
        ("idx_ppm_method", ["method_name"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["protocol_id"],
            foreign_table="python_protocols",
            foreign_columns=["id"],
        ),
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_TYPEDDICT_FIELDS = TableSchema(
    name="python_typeddict_fields",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("typeddict_id", "INTEGER", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT"),
        Column("required", "INTEGER", default="1"),
        Column("field_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_ptf_file", ["file"]),
        ("idx_ptf_typeddict", ["typeddict_id"]),
        ("idx_ptf_field", ["field_name"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["typeddict_id"],
            foreign_table="python_type_definitions",
            foreign_columns=["id"],
        ),
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_FIXTURE_PARAMS = TableSchema(
    name="python_fixture_params",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("fixture_id", "INTEGER", nullable=False),
        Column("param_name", "TEXT"),
        Column("param_value", "TEXT"),
        Column("param_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pfp_file", ["file"]),
        ("idx_pfp_fixture", ["fixture_id"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["fixture_id"],
            foreign_table="python_test_fixtures",
            foreign_columns=["id"],
        ),
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_FRAMEWORK_METHODS = TableSchema(
    name="python_framework_methods",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("config_id", "INTEGER", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("method_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pfm_file", ["file"]),
        ("idx_pfm_config", ["config_id"]),
        ("idx_pfm_method", ["method_name"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["config_id"],
            foreign_table="python_framework_config",
            foreign_columns=["id"],
        ),
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_SCHEMA_VALIDATORS = TableSchema(
    name="python_schema_validators",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("schema_id", "INTEGER", nullable=False),
        Column("validator_name", "TEXT", nullable=False),
        Column("validator_type", "TEXT"),
        Column("validator_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_psv_file", ["file"]),
        ("idx_psv_schema", ["schema_id"]),
        ("idx_psv_validator", ["validator_name"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["schema_id"],
            foreign_table="python_validation_schemas",
            foreign_columns=["id"],
        ),
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PYTHON_TABLES: dict[str, TableSchema] = {
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,
    "python_routes": PYTHON_ROUTES,
    "python_validators": PYTHON_VALIDATORS,
    "python_package_configs": PYTHON_PACKAGE_CONFIGS,
    "python_package_dependencies": PYTHON_PACKAGE_DEPENDENCIES,
    "python_build_requires": PYTHON_BUILD_REQUIRES,
    "python_decorators": PYTHON_DECORATORS,
    "python_django_views": PYTHON_DJANGO_VIEWS,
    "python_django_middleware": PYTHON_DJANGO_MIDDLEWARE,
    "python_loops": PYTHON_LOOPS,
    "python_branches": PYTHON_BRANCHES,
    "python_functions_advanced": PYTHON_FUNCTIONS_ADVANCED,
    "python_io_operations": PYTHON_IO_OPERATIONS,
    "python_state_mutations": PYTHON_STATE_MUTATIONS,
    "python_class_features": PYTHON_CLASS_FEATURES,
    "python_protocols": PYTHON_PROTOCOLS,
    "python_descriptors": PYTHON_DESCRIPTORS,
    "python_type_definitions": PYTHON_TYPE_DEFINITIONS,
    "python_literals": PYTHON_LITERALS,
    "python_security_findings": PYTHON_SECURITY_FINDINGS,
    "python_test_cases": PYTHON_TEST_CASES,
    "python_test_fixtures": PYTHON_TEST_FIXTURES,
    "python_framework_config": PYTHON_FRAMEWORK_CONFIG,
    "python_validation_schemas": PYTHON_VALIDATION_SCHEMAS,
    "python_operators": PYTHON_OPERATORS,
    "python_collections": PYTHON_COLLECTIONS,
    "python_stdlib_usage": PYTHON_STDLIB_USAGE,
    "python_imports_advanced": PYTHON_IMPORTS_ADVANCED,
    "python_expressions": PYTHON_EXPRESSIONS,
    "python_comprehensions": PYTHON_COMPREHENSIONS,
    "python_control_statements": PYTHON_CONTROL_STATEMENTS,
    "python_protocol_methods": PYTHON_PROTOCOL_METHODS,
    "python_typeddict_fields": PYTHON_TYPEDDICT_FIELDS,
    "python_fixture_params": PYTHON_FIXTURE_PARAMS,
    "python_framework_methods": PYTHON_FRAMEWORK_METHODS,
    "python_schema_validators": PYTHON_SCHEMA_VALIDATORS,
}
