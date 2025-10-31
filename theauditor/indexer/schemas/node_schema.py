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

from typing import Dict
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
        Column("props_definition", "TEXT"),
        Column("emits_definition", "TEXT"),
        Column("setup_return", "TEXT"),
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
# NODE TABLES REGISTRY
# ============================================================================

NODE_TABLES: Dict[str, TableSchema] = {
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
    "vue_hooks": VUE_HOOKS,
    "vue_directives": VUE_DIRECTIVES,
    "vue_provide_inject": VUE_PROVIDE_INJECT,

    # TypeScript
    "type_annotations": TYPE_ANNOTATIONS,

    # Build analysis
    "package_configs": PACKAGE_CONFIGS,
    "lock_analysis": LOCK_ANALYSIS,
    "import_styles": IMPORT_STYLES,
    "import_style_names": IMPORT_STYLE_NAMES,

    # Framework detection
    "frameworks": FRAMEWORKS,
    "framework_safe_sinks": FRAMEWORK_SAFE_SINKS,
    "validation_framework_usage": VALIDATION_FRAMEWORK_USAGE,
}
