"""
Node/JavaScript/TypeScript-specific schema definitions.

This module contains table schemas specific to Node.js, React, Vue, and TypeScript:
- Framework-specific patterns (React hooks, Vue composition API)
- TypeScript type annotations
- API endpoints and middleware
- Package management and build analysis
- Validation frameworks (Zod, Joi, Yup)

Design Philosophy:
- Node/JS/TS-only tables
- Framework-agnostic core with framework-specific extensions
- Complements core schema with JavaScript ecosystem patterns
"""

from .utils import Column, ForeignKey, TableSchema

# ============================================================================
# NODE/JAVASCRIPT SYMBOL TABLES
# ============================================================================

CLASS_PROPERTIES = TableSchema(
    name="class_properties",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("property_name", "TEXT", nullable=False),
        Column("property_type", "TEXT", nullable=True),  # TypeScript type annotation
        Column("is_optional", "BOOLEAN", default="0"),    # ? modifier
        Column("is_readonly", "BOOLEAN", default="0"),    # readonly keyword
        Column("access_modifier", "TEXT", nullable=True), # "private", "protected", "public"
        Column("has_declare", "BOOLEAN", default="0"),    # declare keyword (TypeScript)
        Column("initializer", "TEXT", nullable=True),     # Default value if present
    ],
    primary_key=["file", "class_name", "property_name", "line"],
    indexes=[
        ("idx_class_properties_file", ["file"]),
        ("idx_class_properties_class", ["class_name"]),
        ("idx_class_properties_name", ["property_name"]),
    ]
)

# ENV_VAR_USAGE moved to security_schema.py (cross-language security pattern)

# ============================================================================
# ORM & API TABLES - Moved to frameworks_schema.py
# (ORM_RELATIONSHIPS, API_ENDPOINTS, API_ENDPOINT_CONTROLS moved out)
# ============================================================================

# ============================================================================
# REACT TABLES
# ============================================================================

REACT_COMPONENTS = TableSchema(
    name="react_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("has_jsx", "BOOLEAN", default="0"),
        # hooks_used REMOVED - see react_component_hooks junction table
        Column("props_type", "TEXT"),
    ],
    indexes=[
        ("idx_react_components_file", ["file"]),
        ("idx_react_components_name", ["name"]),
    ]
)

# Junction table for normalized React component hooks
# Replaces JSON TEXT column react_components.hooks_used with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
REACT_COMPONENT_HOOKS = TableSchema(
    name="react_component_hooks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("component_file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),  # 1 row per hook used
    ],
    indexes=[
        ("idx_react_comp_hooks_component", ["component_file", "component_name"]),  # FK composite lookup
        ("idx_react_comp_hooks_hook", ["hook_name"]),  # Fast search by hook name
        ("idx_react_comp_hooks_file", ["component_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["component_file", "component_name"],
            foreign_table="react_components",
            foreign_columns=["file", "name"]
        )
    ]
)

REACT_HOOKS = TableSchema(
    name="react_hooks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),
        Column("dependency_array", "TEXT"),
        # dependency_vars REMOVED - see react_hook_dependencies junction table
        Column("callback_body", "TEXT"),
        Column("has_cleanup", "BOOLEAN", default="0"),
        Column("cleanup_type", "TEXT"),
    ],
    indexes=[
        ("idx_react_hooks_file", ["file"]),
        ("idx_react_hooks_component", ["component_name"]),
        ("idx_react_hooks_name", ["hook_name"]),
    ]
)

# Junction table for normalized React hook dependency variables
# Replaces JSON TEXT column react_hooks.dependency_vars with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
REACT_HOOK_DEPENDENCIES = TableSchema(
    name="react_hook_dependencies",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("hook_file", "TEXT", nullable=False),
        Column("hook_line", "INTEGER", nullable=False),
        Column("hook_component", "TEXT", nullable=False),
        Column("dependency_name", "TEXT", nullable=False),  # 1 row per dependency variable
    ],
    indexes=[
        ("idx_react_hook_deps_hook", ["hook_file", "hook_line", "hook_component"]),  # FK composite lookup
        ("idx_react_hook_deps_name", ["dependency_name"]),  # Fast search by variable name
        ("idx_react_hook_deps_file", ["hook_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["hook_file", "hook_line", "hook_component"],
            foreign_table="react_hooks",
            foreign_columns=["file", "line", "component_name"]
        )
    ]
)

# ============================================================================
# VUE TABLES
# ============================================================================

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
        # NOTE: props_definition, emits_definition, setup_return REMOVED
        # -> vue_component_props, vue_component_emits, vue_component_setup_returns junction tables
    ],
    indexes=[
        ("idx_vue_components_file", ["file"]),
        ("idx_vue_components_name", ["name"]),
        ("idx_vue_components_type", ["type"]),
    ]
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
    ]
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
    ]
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
    ]
)

# ============================================================================
# TYPESCRIPT TABLES
# ============================================================================

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
    ]
)

# PRISMA_MODELS - Moved to frameworks_schema.py

# ============================================================================
# SEQUELIZE ORM TABLES
# ============================================================================

SEQUELIZE_MODELS = TableSchema(
    name="sequelize_models",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("table_name", "TEXT", nullable=True),  # Can be NULL if inferred from model name
        Column("extends_model", "BOOLEAN", default="0"),  # True if explicitly extends Model
    ],
    primary_key=["file", "model_name"],
    indexes=[
        ("idx_sequelize_models_file", ["file"]),
        ("idx_sequelize_models_name", ["model_name"]),
    ]
)

SEQUELIZE_ASSOCIATIONS = TableSchema(
    name="sequelize_associations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("association_type", "TEXT", nullable=False),  # 'hasMany', 'belongsTo', 'hasOne', 'belongsToMany'
        Column("target_model", "TEXT", nullable=False),
        Column("foreign_key", "TEXT", nullable=True),  # Can be NULL if using convention
        Column("through_table", "TEXT", nullable=True),  # Only for belongsToMany
    ],
    primary_key=["file", "model_name", "association_type", "target_model", "line"],
    indexes=[
        ("idx_sequelize_assoc_file", ["file"]),
        ("idx_sequelize_assoc_model", ["model_name"]),
        ("idx_sequelize_assoc_target", ["target_model"]),
        ("idx_sequelize_assoc_type", ["association_type"]),
    ]
)

# ============================================================================
# BULLMQ JOB QUEUES TABLES
# ============================================================================

BULLMQ_QUEUES = TableSchema(
    name="bullmq_queues",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("queue_name", "TEXT", nullable=False),
        Column("redis_config", "TEXT", nullable=True),  # Stringified config
    ],
    primary_key=["file", "queue_name"],
    indexes=[
        ("idx_bullmq_queues_file", ["file"]),
        ("idx_bullmq_queues_name", ["queue_name"]),
    ]
)

BULLMQ_WORKERS = TableSchema(
    name="bullmq_workers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("queue_name", "TEXT", nullable=False),
        Column("worker_function", "TEXT", nullable=True),  # Function name or 'anonymous'
        Column("processor_path", "TEXT", nullable=True),  # File path if imported
    ],
    primary_key=["file", "queue_name", "line"],
    indexes=[
        ("idx_bullmq_workers_file", ["file"]),
        ("idx_bullmq_workers_queue", ["queue_name"]),
    ]
)

# ============================================================================
# ANGULAR FRAMEWORK TABLES
# ============================================================================

ANGULAR_COMPONENTS = TableSchema(
    name="angular_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("selector", "TEXT", nullable=True),  # Can be NULL for abstract components
        Column("template_path", "TEXT", nullable=True),
        # NOTE: style_paths REMOVED -> angular_component_styles junction table
        Column("has_lifecycle_hooks", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "component_name"],
    indexes=[
        ("idx_angular_components_file", ["file"]),
        ("idx_angular_components_name", ["component_name"]),
        ("idx_angular_components_selector", ["selector"]),
    ]
)

ANGULAR_SERVICES = TableSchema(
    name="angular_services",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("service_name", "TEXT", nullable=False),
        Column("is_injectable", "BOOLEAN", default="1"),  # Always true for services
        Column("provided_in", "TEXT", nullable=True),  # 'root', 'any', or module name
    ],
    primary_key=["file", "service_name"],
    indexes=[
        ("idx_angular_services_file", ["file"]),
        ("idx_angular_services_name", ["service_name"]),
    ]
)

ANGULAR_MODULES = TableSchema(
    name="angular_modules",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        # NOTE: declarations, imports, providers, exports REMOVED
        # -> angular_module_declarations, angular_module_imports,
        #    angular_module_providers, angular_module_exports junction tables
    ],
    primary_key=["file", "module_name"],
    indexes=[
        ("idx_angular_modules_file", ["file"]),
        ("idx_angular_modules_name", ["module_name"]),
    ]
)

ANGULAR_GUARDS = TableSchema(
    name="angular_guards",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("guard_name", "TEXT", nullable=False),
        Column("guard_type", "TEXT", nullable=False),  # 'CanActivate', 'CanDeactivate', 'CanLoad', 'Resolve'
        Column("implements_interface", "TEXT", nullable=True),  # Interface name
    ],
    primary_key=["file", "guard_name"],
    indexes=[
        ("idx_angular_guards_file", ["file"]),
        ("idx_angular_guards_name", ["guard_name"]),
        ("idx_angular_guards_type", ["guard_type"]),
    ]
)

DI_INJECTIONS = TableSchema(
    name="di_injections",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_class", "TEXT", nullable=False),  # Component/service that injects
        Column("injected_service", "TEXT", nullable=False),  # Service being injected
        Column("injection_type", "TEXT", nullable=False),  # 'constructor' or 'property'
    ],
    indexes=[
        ("idx_di_injections_file", ["file"]),
        ("idx_di_injections_target", ["target_class"]),
        ("idx_di_injections_service", ["injected_service"]),
    ]
)

# ============================================================================
# BUILD ANALYSIS TABLES
# ============================================================================

PACKAGE_CONFIGS = TableSchema(
    name="package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("package_name", "TEXT"),
        Column("version", "TEXT"),
        Column("dependencies", "TEXT"),
        Column("dev_dependencies", "TEXT"),
        Column("peer_dependencies", "TEXT"),
        Column("scripts", "TEXT"),
        Column("engines", "TEXT"),
        Column("workspaces", "TEXT"),
        Column("private", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_package_configs_file", ["file_path"]),
    ]
)

DEPENDENCY_VERSIONS = TableSchema(
    name="dependency_versions",
    columns=[
        Column("manager", "TEXT", nullable=False),  # npm, py, docker
        Column("package_name", "TEXT", nullable=False),
        Column("locked_version", "TEXT", nullable=False),
        Column("latest_version", "TEXT"),
        Column("delta", "TEXT"),  # major, minor, patch, equal
        Column("is_outdated", "BOOLEAN", nullable=False, default="0"),
        Column("last_checked", "TEXT", nullable=False),
        Column("error", "TEXT"),
    ],
    indexes=[
        ("idx_dependency_versions_pk", ["manager", "package_name", "locked_version"]),
        ("idx_dependency_versions_outdated", ["is_outdated"]),
    ]
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
    ]
)

IMPORT_STYLES = TableSchema(
    name="import_styles",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("package", "TEXT", nullable=False),
        Column("import_style", "TEXT", nullable=False),
        # imported_names REMOVED - see import_style_names junction table
        Column("alias_name", "TEXT"),
        Column("full_statement", "TEXT"),
    ],
    indexes=[
        ("idx_import_styles_file", ["file"]),
        ("idx_import_styles_package", ["package"]),
        ("idx_import_styles_style", ["import_style"]),
    ]
)

# Junction table for normalized import statement names
# Replaces JSON TEXT column import_styles.imported_names with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
IMPORT_STYLE_NAMES = TableSchema(
    name="import_style_names",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("import_file", "TEXT", nullable=False),
        Column("import_line", "INTEGER", nullable=False),
        Column("imported_name", "TEXT", nullable=False),  # 1 row per imported name
    ],
    indexes=[
        ("idx_import_style_names_import", ["import_file", "import_line"]),  # FK composite lookup
        ("idx_import_style_names_name", ["imported_name"]),  # Fast search by imported name
        ("idx_import_style_names_file", ["import_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["import_file", "import_line"],
            foreign_table="import_styles",
            foreign_columns=["file", "line"]
        )
    ]
)

# ============================================================================
# FRAMEWORK DETECTION TABLES
# ============================================================================

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
    unique_constraints=[["name", "language", "path"]]
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
    indexes=[]
)

VALIDATION_FRAMEWORK_USAGE = TableSchema(
    name="validation_framework_usage",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),  # 'zod', 'joi', 'yup'
        Column("method", "TEXT", nullable=False),  # 'parse', 'parseAsync', 'validate'
        Column("variable_name", "TEXT"),  # 'schema', 'userSchema' or NULL for direct calls
        Column("is_validator", "BOOLEAN", default="1"),  # True for validators, False for schema builders
        Column("argument_expr", "TEXT"),  # Expression being validated (e.g., 'req.body')
    ],
    indexes=[
        ("idx_validation_framework_file_line", ["file_path", "line"]),
        ("idx_validation_framework_method", ["framework", "method"]),
        ("idx_validation_is_validator", ["is_validator"]),
    ]
)

# ============================================================================
# EXPRESS FRAMEWORK TABLES
# ============================================================================

EXPRESS_MIDDLEWARE_CHAINS = TableSchema(
    name="express_middleware_chains",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("file", "TEXT", nullable=False),  # Route file (e.g., account.routes.ts)
        Column("route_line", "INTEGER", nullable=False),  # Line where router.METHOD called
        Column("route_path", "TEXT", nullable=False),  # Endpoint path (e.g., "/account")
        Column("route_method", "TEXT", nullable=False),  # HTTP method (GET, POST, etc.)
        Column("execution_order", "INTEGER", nullable=False),  # 1, 2, 3... (order in argument list)
        Column("handler_expr", "TEXT", nullable=False),  # Function expression (e.g., "validateBody(...)")
        Column("handler_type", "TEXT", nullable=False),  # 'middleware' or 'controller'
        Column("handler_file", "TEXT"),  # Resolved file (if possible) - FUTURE ENHANCEMENT
        Column("handler_function", "TEXT"),  # Resolved function name - FUTURE ENHANCEMENT
        Column("handler_line", "INTEGER"),  # Resolved line number - FUTURE ENHANCEMENT
    ],
    indexes=[
        ("idx_express_middleware_chains_file", ["file"]),
        ("idx_express_middleware_chains_route", ["route_line"]),
        ("idx_express_middleware_chains_path", ["route_path"]),
        ("idx_express_middleware_chains_method", ["route_method"]),
        ("idx_express_middleware_chains_handler_type", ["handler_type"]),
    ]
)

# ============================================================================
# FRONTEND API CALLS - Cross-boundary flow tracking (frontend -> backend)
# ============================================================================

FRONTEND_API_CALLS = TableSchema(
    name="frontend_api_calls",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method", "TEXT", nullable=False),  # GET, POST, PUT, DELETE, PATCH
        Column("url_literal", "TEXT", nullable=False),  # Static API path (e.g., '/api/users')
        Column("body_variable", "TEXT"),  # Variable name sent as body (e.g., 'userData')
        Column("function_name", "TEXT"),  # Function containing the API call
    ],
    indexes=[
        ("idx_frontend_api_calls_file", ["file"]),
        ("idx_frontend_api_calls_url", ["url_literal"]),
        ("idx_frontend_api_calls_method", ["method"]),
    ]
)

# ============================================================================
# VUE JUNCTION TABLES (JSON blob normalization)
# ============================================================================

# Junction table for vue_components.props_definition (JSON blob removed)
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
    ]
)

# Junction table for vue_components.emits_definition (JSON blob removed)
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
    ]
)

# Junction table for vue_components.setup_return (JSON blob removed)
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
    ]
)

# ============================================================================
# ANGULAR JUNCTION TABLES (JSON blob normalization)
# ============================================================================

# Junction table for angular_components.style_paths (JSON blob removed)
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
    ]
)

# Junction table for angular_modules.declarations (JSON blob removed)
ANGULAR_MODULE_DECLARATIONS = TableSchema(
    name="angular_module_declarations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("declaration_name", "TEXT", nullable=False),
        Column("declaration_type", "TEXT"),  # component, directive, pipe
    ],
    indexes=[
        ("idx_angular_module_declarations_file", ["file"]),
        ("idx_angular_module_declarations_module", ["module_name"]),
    ]
)

# Junction table for angular_modules.imports (JSON blob removed)
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
    ]
)

# Junction table for angular_modules.providers (JSON blob removed)
ANGULAR_MODULE_PROVIDERS = TableSchema(
    name="angular_module_providers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("provider_name", "TEXT", nullable=False),
        Column("provider_type", "TEXT"),  # class, useValue, useFactory, useExisting
    ],
    indexes=[
        ("idx_angular_module_providers_file", ["file"]),
        ("idx_angular_module_providers_module", ["module_name"]),
    ]
)

# Junction table for angular_modules.exports (JSON blob removed)
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
    ]
)

# ============================================================================
# FUNCTION/CLASS METADATA JUNCTION TABLES
# Normalizes nested arrays from core_language.js extractors
# ============================================================================

# Junction table for function parameters (replaces functions[].parameters nested array)
FUNC_PARAMS = TableSchema(
    name="func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),  # Order matters for call matching
        Column("param_name", "TEXT", nullable=False),
        Column("param_type", "TEXT"),  # TypeScript type annotation
    ],
    indexes=[
        ("idx_func_params_function", ["file", "function_line", "function_name"]),
        ("idx_func_params_name", ["param_name"]),
    ]
)

# Junction table for function decorators (replaces functions[].decorators nested array)
FUNC_DECORATORS = TableSchema(
    name="func_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("decorator_index", "INTEGER", nullable=False),  # Order of decorators
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_line", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_func_decorators_function", ["file", "function_line"]),
        ("idx_func_decorators_name", ["decorator_name"]),
    ]
)

# Junction table for function decorator arguments (replaces decorators[].arguments nested array)
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
    ]
)

# Junction table for function parameter decorators (NestJS @Body, @Param, @Query)
FUNC_PARAM_DECORATORS = TableSchema(
    name="func_param_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_args", "TEXT"),  # Stringified args like "'id'" or "{ transform: parseInt }"
    ],
    indexes=[
        ("idx_func_param_decorators_function", ["file", "function_line", "function_name"]),
        ("idx_func_param_decorators_decorator", ["decorator_name"]),
    ]
)

# Junction table for class decorators (replaces classes[].decorators nested array)
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
    ]
)

# Junction table for class decorator arguments
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
    ]
)

# ============================================================================
# DATA FLOW JUNCTION TABLES
# Normalizes nested arrays from data_flow.js extractors
# ============================================================================

# Junction table for assignment source variables (replaces assignments[].source_vars nested array)
ASSIGNMENT_SOURCE_VARS = TableSchema(
    name="assignment_source_vars",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_var", "TEXT", nullable=False),
        Column("source_var", "TEXT", nullable=False),
        Column("var_index", "INTEGER", nullable=False),  # Order preserves expression structure
    ],
    indexes=[
        ("idx_assignment_source_vars_assignment", ["file", "line", "target_var"]),
        ("idx_assignment_source_vars_source", ["source_var"]),
    ]
)

# Junction table for return source variables (replaces returns[].return_vars nested array)
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
    ]
)

# ============================================================================
# IMPORT JUNCTION TABLES
# Normalizes nested arrays from module_framework.js extractors
# ============================================================================

# Junction table for ES6 import specifiers (replaces imports[].specifiers nested array)
IMPORT_SPECIFIERS = TableSchema(
    name="import_specifiers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("import_line", "INTEGER", nullable=False),
        Column("specifier_name", "TEXT", nullable=False),  # Local name used in code
        Column("original_name", "TEXT"),  # For aliased imports: import { foo as bar }
        Column("is_default", "INTEGER", default="0"),
        Column("is_namespace", "INTEGER", default="0"),
        Column("is_named", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_import_specifiers_import", ["file", "import_line"]),
        ("idx_import_specifiers_name", ["specifier_name"]),
    ]
)

# ============================================================================
# ORM JUNCTION TABLES
# Normalizes missing extractions from sequelize_extractors.js
# ============================================================================

# Junction table for Sequelize model field definitions (currently not extracted)
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
    ]
)

# ============================================================================
# NODE TABLES REGISTRY
# ============================================================================

NODE_TABLES: dict[str, TableSchema] = {
    # Node/JS symbol tables
    "class_properties": CLASS_PROPERTIES,
    # env_var_usage moved to SECURITY_TABLES

    # ORM & API tables - Moved to frameworks_schema.py

    # React
    "react_components": REACT_COMPONENTS,
    "react_component_hooks": REACT_COMPONENT_HOOKS,
    "react_hooks": REACT_HOOKS,
    "react_hook_dependencies": REACT_HOOK_DEPENDENCIES,

    # Vue
    "vue_components": VUE_COMPONENTS,
    "vue_component_props": VUE_COMPONENT_PROPS,
    "vue_component_emits": VUE_COMPONENT_EMITS,
    "vue_component_setup_returns": VUE_COMPONENT_SETUP_RETURNS,
    "vue_hooks": VUE_HOOKS,
    "vue_directives": VUE_DIRECTIVES,
    "vue_provide_inject": VUE_PROVIDE_INJECT,

    # TypeScript
    "type_annotations": TYPE_ANNOTATIONS,

    # Build analysis
    "package_configs": PACKAGE_CONFIGS,
    "dependency_versions": DEPENDENCY_VERSIONS,
    "lock_analysis": LOCK_ANALYSIS,
    "import_styles": IMPORT_STYLES,
    "import_style_names": IMPORT_STYLE_NAMES,

    # Framework detection
    "frameworks": FRAMEWORKS,
    "framework_safe_sinks": FRAMEWORK_SAFE_SINKS,
    "validation_framework_usage": VALIDATION_FRAMEWORK_USAGE,

    # Express framework
    "express_middleware_chains": EXPRESS_MIDDLEWARE_CHAINS,

    # Frontend API calls (cross-boundary flow tracking)
    "frontend_api_calls": FRONTEND_API_CALLS,

    # Sequelize ORM
    "sequelize_models": SEQUELIZE_MODELS,
    "sequelize_associations": SEQUELIZE_ASSOCIATIONS,

    # BullMQ Job Queues
    "bullmq_queues": BULLMQ_QUEUES,
    "bullmq_workers": BULLMQ_WORKERS,

    # Angular Framework
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

    # Function/class metadata junction tables
    "func_params": FUNC_PARAMS,
    "func_decorators": FUNC_DECORATORS,
    "func_decorator_args": FUNC_DECORATOR_ARGS,
    "func_param_decorators": FUNC_PARAM_DECORATORS,
    "class_decorators": CLASS_DECORATORS,
    "class_decorator_args": CLASS_DECORATOR_ARGS,

    # Data flow junction tables
    "assignment_source_vars": ASSIGNMENT_SOURCE_VARS,
    "return_source_vars": RETURN_SOURCE_VARS,

    # Import junction tables
    "import_specifiers": IMPORT_SPECIFIERS,

    # ORM junction tables
    "sequelize_model_fields": SEQUELIZE_MODEL_FIELDS,
}
