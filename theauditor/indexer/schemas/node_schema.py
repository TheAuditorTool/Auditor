"""Node/JavaScript/TypeScript-specific schema definitions."""

from .utils import Column, ForeignKey, TableSchema

CLASS_PROPERTIES = TableSchema(
    name="class_properties",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("property_name", "TEXT", nullable=False),
        Column("property_type", "TEXT", nullable=True),
        Column("is_optional", "BOOLEAN", default="0"),
        Column("is_readonly", "BOOLEAN", default="0"),
        Column("access_modifier", "TEXT", nullable=True),
        Column("has_declare", "BOOLEAN", default="0"),
        Column("initializer", "TEXT", nullable=True),
    ],
    primary_key=["file", "class_name", "property_name", "line"],
    indexes=[
        ("idx_class_properties_file", ["file"]),
        ("idx_class_properties_class", ["class_name"]),
        ("idx_class_properties_name", ["property_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


REACT_COMPONENTS = TableSchema(
    name="react_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("has_jsx", "BOOLEAN", default="0"),
        Column("props_type", "TEXT"),
    ],
    primary_key=["file", "name"],
    indexes=[
        ("idx_react_components_file", ["file"]),
        ("idx_react_components_name", ["name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


REACT_COMPONENT_HOOKS = TableSchema(
    name="react_component_hooks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("component_file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_react_comp_hooks_component", ["component_file", "component_name"]),
        ("idx_react_comp_hooks_hook", ["hook_name"]),
        ("idx_react_comp_hooks_file", ["component_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["component_file", "component_name"],
            foreign_table="react_components",
            foreign_columns=["file", "name"],
        ),
        ForeignKey(
            local_columns=["component_file"], foreign_table="files", foreign_columns=["path"]
        ),
    ],
)

REACT_HOOKS = TableSchema(
    name="react_hooks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),
        Column("dependency_array", "TEXT"),
        Column("callback_body", "TEXT"),
        Column("has_cleanup", "BOOLEAN", default="0"),
        Column("cleanup_type", "TEXT"),
    ],
    primary_key=["file", "line", "component_name"],
    indexes=[
        ("idx_react_hooks_file", ["file"]),
        ("idx_react_hooks_component", ["component_name"]),
        ("idx_react_hooks_name", ["hook_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


REACT_HOOK_DEPENDENCIES = TableSchema(
    name="react_hook_dependencies",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("hook_file", "TEXT", nullable=False),
        Column("hook_line", "INTEGER", nullable=False),
        Column("hook_component", "TEXT", nullable=False),
        Column("dependency_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_react_hook_deps_hook", ["hook_file", "hook_line", "hook_component"]),
        ("idx_react_hook_deps_name", ["dependency_name"]),
        ("idx_react_hook_deps_file", ["hook_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["hook_file", "hook_line", "hook_component"],
            foreign_table="react_hooks",
            foreign_columns=["file", "line", "component_name"],
        ),
        ForeignKey(local_columns=["hook_file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


VUE_COMPONENTS = TableSchema(
    name="vue_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("has_template", "BOOLEAN", default="0"),
        Column("has_style", "BOOLEAN", default="0"),
        Column("composition_api_used", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_vue_components_file", ["file"]),
        ("idx_vue_components_name", ["name"]),
        ("idx_vue_components_type", ["type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

VUE_HOOKS = TableSchema(
    name="vue_hooks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),
        Column("hook_type", "TEXT", nullable=False),
        Column("dependencies", "TEXT"),
        Column("return_value", "TEXT"),
        Column("is_async", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_vue_hooks_file", ["file"]),
        ("idx_vue_hooks_component", ["component_name"]),
        ("idx_vue_hooks_type", ["hook_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

VUE_DIRECTIVES = TableSchema(
    name="vue_directives",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("directive_name", "TEXT", nullable=False),
        Column("expression", "TEXT"),
        Column("in_component", "TEXT"),
        Column("has_key", "BOOLEAN", default="0"),
        Column("modifiers", "TEXT"),
    ],
    indexes=[
        ("idx_vue_directives_file", ["file"]),
        ("idx_vue_directives_name", ["directive_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

VUE_PROVIDE_INJECT = TableSchema(
    name="vue_provide_inject",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("operation_type", "TEXT", nullable=False),
        Column("key_name", "TEXT", nullable=False),
        Column("value_expr", "TEXT"),
        Column("is_reactive", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_vue_provide_inject_file", ["file"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


TYPE_ANNOTATIONS = TableSchema(
    name="type_annotations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("column", "INTEGER"),
        Column("symbol_name", "TEXT", nullable=False),
        Column("symbol_kind", "TEXT", nullable=False),
        Column("type_annotation", "TEXT"),
        Column("is_any", "BOOLEAN", default="0"),
        Column("is_unknown", "BOOLEAN", default="0"),
        Column("is_generic", "BOOLEAN", default="0"),
        Column("has_type_params", "BOOLEAN", default="0"),
        Column("type_params", "TEXT"),
        Column("return_type", "TEXT"),
        Column("extends_type", "TEXT"),
    ],
    primary_key=["file", "line", "column", "symbol_name"],
    indexes=[
        ("idx_type_annotations_file", ["file"]),
        ("idx_type_annotations_any", ["file", "is_any"]),
        ("idx_type_annotations_unknown", ["file", "is_unknown"]),
        ("idx_type_annotations_generic", ["file", "is_generic"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


SEQUELIZE_MODELS = TableSchema(
    name="sequelize_models",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("table_name", "TEXT", nullable=True),
        Column("extends_model", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "model_name"],
    indexes=[
        ("idx_sequelize_models_file", ["file"]),
        ("idx_sequelize_models_name", ["model_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

SEQUELIZE_ASSOCIATIONS = TableSchema(
    name="sequelize_associations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("association_type", "TEXT", nullable=False),
        Column("target_model", "TEXT", nullable=False),
        Column("foreign_key", "TEXT", nullable=True),
        Column("through_table", "TEXT", nullable=True),
    ],
    primary_key=["file", "model_name", "association_type", "target_model", "line"],
    indexes=[
        ("idx_sequelize_assoc_file", ["file"]),
        ("idx_sequelize_assoc_model", ["model_name"]),
        ("idx_sequelize_assoc_target", ["target_model"]),
        ("idx_sequelize_assoc_type", ["association_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


BULLMQ_QUEUES = TableSchema(
    name="bullmq_queues",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("queue_name", "TEXT", nullable=False),
        Column("redis_config", "TEXT", nullable=True),
    ],
    primary_key=["file", "queue_name"],
    indexes=[
        ("idx_bullmq_queues_file", ["file"]),
        ("idx_bullmq_queues_name", ["queue_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

BULLMQ_WORKERS = TableSchema(
    name="bullmq_workers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("queue_name", "TEXT", nullable=False),
        Column("worker_function", "TEXT", nullable=True),
        Column("processor_path", "TEXT", nullable=True),
    ],
    primary_key=["file", "queue_name", "line"],
    indexes=[
        ("idx_bullmq_workers_file", ["file"]),
        ("idx_bullmq_workers_queue", ["queue_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


ANGULAR_COMPONENTS = TableSchema(
    name="angular_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("selector", "TEXT", nullable=True),
        Column("template_path", "TEXT", nullable=True),
        Column("has_lifecycle_hooks", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "component_name"],
    indexes=[
        ("idx_angular_components_file", ["file"]),
        ("idx_angular_components_name", ["component_name"]),
        ("idx_angular_components_selector", ["selector"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

ANGULAR_SERVICES = TableSchema(
    name="angular_services",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("service_name", "TEXT", nullable=False),
        Column("is_injectable", "BOOLEAN", default="1"),
        Column("provided_in", "TEXT", nullable=True),
    ],
    primary_key=["file", "service_name"],
    indexes=[
        ("idx_angular_services_file", ["file"]),
        ("idx_angular_services_name", ["service_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

ANGULAR_MODULES = TableSchema(
    name="angular_modules",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("module_name", "TEXT", nullable=False),
    ],
    primary_key=["file", "module_name"],
    indexes=[
        ("idx_angular_modules_file", ["file"]),
        ("idx_angular_modules_name", ["module_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

ANGULAR_GUARDS = TableSchema(
    name="angular_guards",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("guard_name", "TEXT", nullable=False),
        Column("guard_type", "TEXT", nullable=False),
        Column("implements_interface", "TEXT", nullable=True),
    ],
    primary_key=["file", "guard_name"],
    indexes=[
        ("idx_angular_guards_file", ["file"]),
        ("idx_angular_guards_name", ["guard_name"]),
        ("idx_angular_guards_type", ["guard_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

DI_INJECTIONS = TableSchema(
    name="di_injections",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_class", "TEXT", nullable=False),
        Column("injected_service", "TEXT", nullable=False),
        Column("injection_type", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_di_injections_file", ["file"]),
        ("idx_di_injections_target", ["target_class"]),
        ("idx_di_injections_service", ["injected_service"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PACKAGE_CONFIGS = TableSchema(
    name="package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("package_name", "TEXT"),
        Column("version", "TEXT"),
        Column("private", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_package_configs_file", ["file_path"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)


PACKAGE_DEPENDENCIES = TableSchema(
    name="package_dependencies",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("version_spec", "TEXT"),
        Column("is_dev", "BOOLEAN", default="0"),
        Column("is_peer", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_package_dependencies_file_path", ["file_path"]),
        ("idx_package_dependencies_name", ["name"]),
    ],
    unique_constraints=[["file_path", "name", "is_dev", "is_peer"]],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="package_configs",
            foreign_columns=["file_path"],
        )
    ],
)

PACKAGE_SCRIPTS = TableSchema(
    name="package_scripts",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("script_name", "TEXT", nullable=False),
        Column("script_command", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_package_scripts_file_path", ["file_path"]),
    ],
    unique_constraints=[["file_path", "script_name"]],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="package_configs",
            foreign_columns=["file_path"],
        )
    ],
)

PACKAGE_ENGINES = TableSchema(
    name="package_engines",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("engine_name", "TEXT", nullable=False),
        Column("version_spec", "TEXT"),
    ],
    indexes=[
        ("idx_package_engines_file_path", ["file_path"]),
    ],
    unique_constraints=[["file_path", "engine_name"]],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="package_configs",
            foreign_columns=["file_path"],
        )
    ],
)

PACKAGE_WORKSPACES = TableSchema(
    name="package_workspaces",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("workspace_path", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_package_workspaces_file_path", ["file_path"]),
    ],
    unique_constraints=[["file_path", "workspace_path"]],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="package_configs",
            foreign_columns=["file_path"],
        )
    ],
)

DEPENDENCY_VERSIONS = TableSchema(
    name="dependency_versions",
    columns=[
        Column("manager", "TEXT", nullable=False),
        Column("package_name", "TEXT", nullable=False),
        Column("locked_version", "TEXT", nullable=False),
        Column("latest_version", "TEXT"),
        Column("delta", "TEXT"),
        Column("is_outdated", "BOOLEAN", nullable=False, default="0"),
        Column("last_checked", "TEXT", nullable=False),
        Column("error", "TEXT"),
    ],
    indexes=[
        ("idx_dependency_versions_pk", ["manager", "package_name", "locked_version"]),
        ("idx_dependency_versions_outdated", ["is_outdated"]),
    ],
)

LOCK_ANALYSIS = TableSchema(
    name="lock_analysis",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("lock_type", "TEXT", nullable=False),
        Column("package_manager_version", "TEXT"),
        Column("total_packages", "INTEGER"),
        Column("duplicate_packages", "TEXT"),
        Column("lock_file_version", "TEXT"),
    ],
    indexes=[
        ("idx_lock_analysis_file", ["file_path"]),
        ("idx_lock_analysis_type", ["lock_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)

IMPORT_STYLES = TableSchema(
    name="import_styles",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("package", "TEXT", nullable=False),
        Column("import_style", "TEXT", nullable=False),
        Column("alias_name", "TEXT"),
        Column("full_statement", "TEXT"),
        Column("resolved_path", "TEXT"),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_import_styles_file", ["file"]),
        ("idx_import_styles_package", ["package"]),
        ("idx_import_styles_style", ["import_style"]),
        ("idx_import_styles_resolved", ["resolved_path"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


IMPORT_STYLE_NAMES = TableSchema(
    name="import_style_names",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("import_file", "TEXT", nullable=False),
        Column("import_line", "INTEGER", nullable=False),
        Column("imported_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_import_style_names_import", ["import_file", "import_line"]),
        ("idx_import_style_names_name", ["imported_name"]),
        ("idx_import_style_names_file", ["import_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["import_file", "import_line"],
            foreign_table="import_styles",
            foreign_columns=["file", "line"],
        ),
        ForeignKey(local_columns=["import_file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


FRAMEWORKS = TableSchema(
    name="frameworks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("name", "TEXT", nullable=False),
        Column("version", "TEXT"),
        Column("language", "TEXT", nullable=False),
        Column("path", "TEXT", default="'.'"),
        Column("source", "TEXT"),
        Column("package_manager", "TEXT"),
        Column("is_primary", "BOOLEAN", default="0"),
    ],
    indexes=[],
    unique_constraints=[["name", "language", "path"]],
)

FRAMEWORK_SAFE_SINKS = TableSchema(
    name="framework_safe_sinks",
    columns=[
        Column("framework_id", "INTEGER"),
        Column("sink_pattern", "TEXT", nullable=False),
        Column("sink_type", "TEXT", nullable=False),
        Column("is_safe", "BOOLEAN", default="1"),
        Column("reason", "TEXT"),
    ],
    indexes=[],
)

VALIDATION_FRAMEWORK_USAGE = TableSchema(
    name="validation_framework_usage",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),
        Column("method", "TEXT", nullable=False),
        Column("variable_name", "TEXT"),
        Column("is_validator", "BOOLEAN", default="1"),
        Column("argument_expr", "TEXT"),
    ],
    indexes=[
        ("idx_validation_framework_file_line", ["file_path", "line"]),
        ("idx_validation_framework_method", ["framework", "method"]),
        ("idx_validation_is_validator", ["is_validator"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)


EXPRESS_MIDDLEWARE_CHAINS = TableSchema(
    name="express_middleware_chains",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("route_line", "INTEGER", nullable=False),
        Column("route_path", "TEXT", nullable=False),
        Column("route_method", "TEXT", nullable=False),
        Column("execution_order", "INTEGER", nullable=False),
        Column("handler_expr", "TEXT", nullable=False),
        Column("handler_type", "TEXT", nullable=False),
        Column("handler_file", "TEXT"),
        Column("handler_function", "TEXT"),
        Column("handler_line", "INTEGER"),
    ],
    indexes=[
        ("idx_express_middleware_chains_file", ["file"]),
        ("idx_express_middleware_chains_route", ["route_line"]),
        ("idx_express_middleware_chains_path", ["route_path"]),
        ("idx_express_middleware_chains_method", ["route_method"]),
        ("idx_express_middleware_chains_handler_type", ["handler_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


FRONTEND_API_CALLS = TableSchema(
    name="frontend_api_calls",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method", "TEXT", nullable=False),
        Column("url_literal", "TEXT", nullable=False),
        Column("body_variable", "TEXT"),
        Column("function_name", "TEXT"),
    ],
    indexes=[
        ("idx_frontend_api_calls_file", ["file"]),
        ("idx_frontend_api_calls_url", ["url_literal"]),
        ("idx_frontend_api_calls_method", ["method"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


VUE_COMPONENT_PROPS = TableSchema(
    name="vue_component_props",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("prop_name", "TEXT", nullable=False),
        Column("prop_type", "TEXT"),
        Column("is_required", "INTEGER", default="0"),
        Column("default_value", "TEXT"),
    ],
    indexes=[
        ("idx_vue_component_props_file", ["file"]),
        ("idx_vue_component_props_component", ["component_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


VUE_COMPONENT_EMITS = TableSchema(
    name="vue_component_emits",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("emit_name", "TEXT", nullable=False),
        Column("payload_type", "TEXT"),
    ],
    indexes=[
        ("idx_vue_component_emits_file", ["file"]),
        ("idx_vue_component_emits_component", ["component_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


VUE_COMPONENT_SETUP_RETURNS = TableSchema(
    name="vue_component_setup_returns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("return_name", "TEXT", nullable=False),
        Column("return_type", "TEXT"),
    ],
    indexes=[
        ("idx_vue_component_setup_returns_file", ["file"]),
        ("idx_vue_component_setup_returns_component", ["component_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


ANGULAR_COMPONENT_STYLES = TableSchema(
    name="angular_component_styles",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("style_path", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_angular_component_styles_file", ["file"]),
        ("idx_angular_component_styles_component", ["component_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


ANGULAR_MODULE_DECLARATIONS = TableSchema(
    name="angular_module_declarations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("declaration_name", "TEXT", nullable=False),
        Column("declaration_type", "TEXT"),
    ],
    indexes=[
        ("idx_angular_module_declarations_file", ["file"]),
        ("idx_angular_module_declarations_module", ["module_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


ANGULAR_MODULE_IMPORTS = TableSchema(
    name="angular_module_imports",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("imported_module", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_angular_module_imports_file", ["file"]),
        ("idx_angular_module_imports_module", ["module_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


ANGULAR_MODULE_PROVIDERS = TableSchema(
    name="angular_module_providers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("provider_name", "TEXT", nullable=False),
        Column("provider_type", "TEXT"),
    ],
    indexes=[
        ("idx_angular_module_providers_file", ["file"]),
        ("idx_angular_module_providers_module", ["module_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


ANGULAR_MODULE_EXPORTS = TableSchema(
    name="angular_module_exports",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("exported_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_angular_module_exports_file", ["file"]),
        ("idx_angular_module_exports_module", ["module_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


FUNC_PARAMS = TableSchema(
    name="func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("param_type", "TEXT"),
    ],
    indexes=[
        ("idx_func_params_function", ["file", "function_line", "function_name"]),
        ("idx_func_params_name", ["param_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


FUNC_DECORATORS = TableSchema(
    name="func_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_line", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_func_decorators_function", ["file", "function_line"]),
        ("idx_func_decorators_name", ["decorator_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


FUNC_DECORATOR_ARGS = TableSchema(
    name="func_decorator_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("arg_index", "INTEGER", nullable=False),
        Column("arg_value", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_func_decorator_args_decorator", ["file", "function_line", "decorator_index"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


FUNC_PARAM_DECORATORS = TableSchema(
    name="func_param_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_args", "TEXT"),
    ],
    indexes=[
        ("idx_func_param_decorators_function", ["file", "function_line", "function_name"]),
        ("idx_func_param_decorators_decorator", ["decorator_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


CLASS_DECORATORS = TableSchema(
    name="class_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("class_line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_line", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_class_decorators_class", ["file", "class_line"]),
        ("idx_class_decorators_name", ["decorator_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


CLASS_DECORATOR_ARGS = TableSchema(
    name="class_decorator_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("class_line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),
        Column("arg_index", "INTEGER", nullable=False),
        Column("arg_value", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_class_decorator_args_decorator", ["file", "class_line", "decorator_index"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


ASSIGNMENT_SOURCE_VARS = TableSchema(
    name="assignment_source_vars",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_var", "TEXT", nullable=False),
        Column("source_var", "TEXT", nullable=False),
        Column("var_index", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_assignment_source_vars_assignment", ["file", "line", "target_var"]),
        ("idx_assignment_source_vars_source", ["source_var"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


RETURN_SOURCE_VARS = TableSchema(
    name="return_source_vars",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("source_var", "TEXT", nullable=False),
        Column("var_index", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_return_source_vars_return", ["file", "line"]),
        ("idx_return_source_vars_source", ["source_var"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


IMPORT_SPECIFIERS = TableSchema(
    name="import_specifiers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("import_line", "INTEGER", nullable=False),
        Column("specifier_name", "TEXT", nullable=False),
        Column("original_name", "TEXT"),
        Column("is_default", "INTEGER", default="0"),
        Column("is_namespace", "INTEGER", default="0"),
        Column("is_named", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_import_specifiers_import", ["file", "import_line"]),
        ("idx_import_specifiers_name", ["specifier_name"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


SEQUELIZE_MODEL_FIELDS = TableSchema(
    name="sequelize_model_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("data_type", "TEXT", nullable=False),
        Column("is_primary_key", "INTEGER", default="0"),
        Column("is_nullable", "INTEGER", default="1"),
        Column("is_unique", "INTEGER", default="0"),
        Column("default_value", "TEXT"),
    ],
    indexes=[
        ("idx_sequelize_model_fields_model", ["file", "model_name"]),
        ("idx_sequelize_model_fields_type", ["data_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


NODE_TABLES: dict[str, TableSchema] = {
    "class_properties": CLASS_PROPERTIES,
    "react_components": REACT_COMPONENTS,
    "react_component_hooks": REACT_COMPONENT_HOOKS,
    "react_hooks": REACT_HOOKS,
    "react_hook_dependencies": REACT_HOOK_DEPENDENCIES,
    "vue_components": VUE_COMPONENTS,
    "vue_component_props": VUE_COMPONENT_PROPS,
    "vue_component_emits": VUE_COMPONENT_EMITS,
    "vue_component_setup_returns": VUE_COMPONENT_SETUP_RETURNS,
    "vue_hooks": VUE_HOOKS,
    "vue_directives": VUE_DIRECTIVES,
    "vue_provide_inject": VUE_PROVIDE_INJECT,
    "type_annotations": TYPE_ANNOTATIONS,
    "package_configs": PACKAGE_CONFIGS,
    "package_dependencies": PACKAGE_DEPENDENCIES,
    "package_scripts": PACKAGE_SCRIPTS,
    "package_engines": PACKAGE_ENGINES,
    "package_workspaces": PACKAGE_WORKSPACES,
    "dependency_versions": DEPENDENCY_VERSIONS,
    "lock_analysis": LOCK_ANALYSIS,
    "import_styles": IMPORT_STYLES,
    "import_style_names": IMPORT_STYLE_NAMES,
    "frameworks": FRAMEWORKS,
    "framework_safe_sinks": FRAMEWORK_SAFE_SINKS,
    "validation_framework_usage": VALIDATION_FRAMEWORK_USAGE,
    "express_middleware_chains": EXPRESS_MIDDLEWARE_CHAINS,
    "frontend_api_calls": FRONTEND_API_CALLS,
    "sequelize_models": SEQUELIZE_MODELS,
    "sequelize_associations": SEQUELIZE_ASSOCIATIONS,
    "bullmq_queues": BULLMQ_QUEUES,
    "bullmq_workers": BULLMQ_WORKERS,
    "angular_components": ANGULAR_COMPONENTS,
    "angular_component_styles": ANGULAR_COMPONENT_STYLES,
    "angular_services": ANGULAR_SERVICES,
    "angular_modules": ANGULAR_MODULES,
    "angular_module_declarations": ANGULAR_MODULE_DECLARATIONS,
    "angular_module_imports": ANGULAR_MODULE_IMPORTS,
    "angular_module_providers": ANGULAR_MODULE_PROVIDERS,
    "angular_module_exports": ANGULAR_MODULE_EXPORTS,
    "angular_guards": ANGULAR_GUARDS,
    "di_injections": DI_INJECTIONS,
    "func_params": FUNC_PARAMS,
    "func_decorators": FUNC_DECORATORS,
    "func_decorator_args": FUNC_DECORATOR_ARGS,
    "func_param_decorators": FUNC_PARAM_DECORATORS,
    "class_decorators": CLASS_DECORATORS,
    "class_decorator_args": CLASS_DECORATOR_ARGS,
    "assignment_source_vars": ASSIGNMENT_SOURCE_VARS,
    "return_source_vars": RETURN_SOURCE_VARS,
    "import_specifiers": IMPORT_SPECIFIERS,
    "sequelize_model_fields": SEQUELIZE_MODEL_FIELDS,
}
