"""
Python-specific schema definitions.

This module contains table schemas specific to Python frameworks and patterns:
- ORM models (SQLAlchemy, Django)
- HTTP routes (Flask, FastAPI, Django)
- Validation patterns (Pydantic)
- Decorators
- Control flow (loops, branches, exceptions)
- Security findings (injections, crypto, auth)
- Testing (fixtures, test cases)
- Framework configs (Flask, Django, Celery)

Design Philosophy:
- Python-only tables
- Framework-specific extractions
- Complements core schema with language-specific patterns
- Domain-grouped consolidated tables with discriminator columns

TABLE HISTORY:
- 2025-11-25: Reduced from 149 to 8 tables (consolidate-python-orphan-tables)
- 2025-11-25: Added 20 consolidated tables (wire-extractors-to-consolidated-schema)
- Current: 28 tables (8 original + 20 consolidated)
"""

from typing import Dict
from .utils import Column, TableSchema


# ============================================================================
# PYTHON-SPECIFIC TABLES (8 tables with verified consumers)
# ============================================================================

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
    ]
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
    ]
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
    ]
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
    ]
)

PYTHON_PACKAGE_CONFIGS = TableSchema(
    name="python_package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("file_type", "TEXT", nullable=False),  # 'pyproject' | 'requirements'
        Column("project_name", "TEXT"),
        Column("project_version", "TEXT"),
        Column("dependencies", "TEXT"),  # JSON array of dependency dicts
        Column("optional_dependencies", "TEXT"),  # JSON object {group: [deps]}
        Column("build_system", "TEXT"),  # JSON object with build-backend info
        Column("indexed_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["file_path"],
    indexes=[
        ("idx_python_package_configs_file", ["file_path"]),
        ("idx_python_package_configs_type", ["file_type"]),
        ("idx_python_package_configs_project", ["project_name"]),
    ]
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
    ]
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
    ]
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
    ]
)


# ============================================================================
# CONSOLIDATED PYTHON TABLES (20 new tables - Phase 2 Wire Extractors)
# ============================================================================

# -----------------------------------------------------------------------------
# GROUP 1: Control & Data Flow (5 tables)
# -----------------------------------------------------------------------------

PYTHON_LOOPS = TableSchema(
    name="python_loops",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("loop_type", "TEXT", nullable=False),  # 'for_loop', 'while_loop', 'async_for_loop'
        Column("target", "TEXT"),              # loop variable
        Column("iterator", "TEXT"),            # iterable expression
        Column("has_else", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        Column("body_line_count", "INTEGER"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_loops_file", ["file"]),
        ("idx_python_loops_type", ["loop_type"]),
    ]
)

PYTHON_BRANCHES = TableSchema(
    name="python_branches",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("branch_type", "TEXT", nullable=False),  # 'if', 'match', 'try', 'except', 'finally', 'raise'
        Column("condition", "TEXT"),
        Column("has_else", "INTEGER", default="0"),
        Column("elif_count", "INTEGER", default="0"),
        Column("case_count", "INTEGER", default="0"),
        Column("exception_type", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_branches_file", ["file"]),
        ("idx_python_branches_type", ["branch_type"]),
    ]
)

PYTHON_FUNCTIONS_ADVANCED = TableSchema(
    name="python_functions_advanced",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_type", "TEXT", nullable=False),  # 'async', 'async_generator', 'generator', 'lambda', 'context_manager'
        Column("name", "TEXT"),
        Column("is_method", "INTEGER", default="0"),
        Column("yield_count", "INTEGER", default="0"),
        Column("await_count", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_functions_advanced_file", ["file"]),
        ("idx_python_functions_advanced_type", ["function_type"]),
    ]
)

PYTHON_IO_OPERATIONS = TableSchema(
    name="python_io_operations",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("io_type", "TEXT", nullable=False),  # 'file', 'network', 'database', 'process', 'param_flow', 'closure', 'nonlocal', 'conditional'
        Column("operation", "TEXT"),         # 'read', 'write', 'open', 'close', etc.
        Column("target", "TEXT"),
        Column("is_taint_source", "INTEGER", default="0"),
        Column("is_taint_sink", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_io_operations_file", ["file"]),
        ("idx_python_io_operations_type", ["io_type"]),
    ]
)

PYTHON_STATE_MUTATIONS = TableSchema(
    name="python_state_mutations",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("mutation_type", "TEXT", nullable=False),  # 'instance', 'class', 'global', 'argument', 'augmented'
        Column("target", "TEXT"),
        Column("operator", "TEXT"),
        Column("value_expr", "TEXT"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_state_mutations_file", ["file"]),
        ("idx_python_state_mutations_type", ["mutation_type"]),
    ]
)

# -----------------------------------------------------------------------------
# GROUP 2: Object-Oriented & Types (5 tables)
# -----------------------------------------------------------------------------

PYTHON_CLASS_FEATURES = TableSchema(
    name="python_class_features",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("feature_type", "TEXT", nullable=False),  # 'metaclass', 'slots', 'abstract', 'dataclass', 'enum', 'inheritance', 'dunder', 'visibility', 'method_type'
        Column("class_name", "TEXT"),
        Column("name", "TEXT"),
        Column("details", "TEXT"),  # JSON for feature-specific data
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_class_features_file", ["file"]),
        ("idx_python_class_features_type", ["feature_type"]),
    ]
)

PYTHON_PROTOCOLS = TableSchema(
    name="python_protocols",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("protocol_type", "TEXT", nullable=False),  # 'iterator', 'container', 'callable', 'comparison', 'arithmetic', 'pickle', 'context_manager'
        Column("class_name", "TEXT"),
        Column("implemented_methods", "TEXT"),  # JSON array
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_protocols_file", ["file"]),
        ("idx_python_protocols_type", ["protocol_type"]),
    ]
)

PYTHON_DESCRIPTORS = TableSchema(
    name="python_descriptors",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("descriptor_type", "TEXT", nullable=False),  # 'descriptor', 'property', 'dynamic_attr', 'cached_property', 'attr_access'
        Column("name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("has_getter", "INTEGER", default="0"),
        Column("has_setter", "INTEGER", default="0"),
        Column("has_deleter", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_descriptors_file", ["file"]),
        ("idx_python_descriptors_type", ["descriptor_type"]),
    ]
)

PYTHON_TYPE_DEFINITIONS = TableSchema(
    name="python_type_definitions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("type_kind", "TEXT", nullable=False),  # 'typed_dict', 'generic', 'protocol'
        Column("name", "TEXT"),
        Column("type_params", "TEXT"),  # JSON array of type parameters
        Column("fields", "TEXT"),        # JSON for TypedDict fields
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_type_definitions_file", ["file"]),
        ("idx_python_type_definitions_kind", ["type_kind"]),
    ]
)

PYTHON_LITERALS = TableSchema(
    name="python_literals",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("literal_type", "TEXT", nullable=False),  # 'literal', 'overload'
        Column("name", "TEXT"),
        Column("literal_values", "TEXT"),  # JSON array of literal values (renamed from 'values' - SQL reserved keyword)
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_literals_file", ["file"]),
        ("idx_python_literals_type", ["literal_type"]),
    ]
)

# -----------------------------------------------------------------------------
# GROUP 3: Security & Testing (5 tables)
# -----------------------------------------------------------------------------

PYTHON_SECURITY_FINDINGS = TableSchema(
    name="python_security_findings",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("finding_type", "TEXT", nullable=False),  # 'sql_injection', 'command_injection', 'path_traversal', 'dangerous_eval', 'crypto', 'auth', 'password', 'jwt'
        Column("severity", "TEXT", default="'medium'"),  # 'low', 'medium', 'high', 'critical'
        Column("source_expr", "TEXT"),
        Column("sink_expr", "TEXT"),
        Column("vulnerable_code", "TEXT"),
        Column("cwe_id", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_security_findings_file", ["file"]),
        ("idx_python_security_findings_type", ["finding_type"]),
        ("idx_python_security_findings_severity", ["severity"]),
    ]
)

PYTHON_TEST_CASES = TableSchema(
    name="python_test_cases",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("test_type", "TEXT", nullable=False),  # 'unittest', 'pytest', 'assertion'
        Column("name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("assertion_type", "TEXT"),
        Column("expected_exception", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_test_cases_file", ["file"]),
        ("idx_python_test_cases_type", ["test_type"]),
    ]
)

PYTHON_TEST_FIXTURES = TableSchema(
    name="python_test_fixtures",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("fixture_type", "TEXT", nullable=False),  # 'fixture', 'parametrize', 'marker', 'mock', 'plugin_hook', 'hypothesis'
        Column("name", "TEXT"),
        Column("scope", "TEXT"),           # 'function', 'class', 'module', 'session'
        Column("params", "TEXT"),          # JSON array
        Column("autouse", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_test_fixtures_file", ["file"]),
        ("idx_python_test_fixtures_type", ["fixture_type"]),
    ]
)

PYTHON_FRAMEWORK_CONFIG = TableSchema(
    name="python_framework_config",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),      # 'flask', 'celery', 'django'
        Column("config_type", "TEXT", nullable=False),    # 'app', 'extension', 'hook', 'error_handler', 'task', 'signal', 'admin', 'form', etc.
        Column("name", "TEXT"),
        Column("endpoint", "TEXT"),
        Column("methods", "TEXT"),
        Column("schedule", "TEXT"),
        Column("details", "TEXT"),  # JSON for framework-specific data
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_framework_config_file", ["file"]),
        ("idx_python_framework_config_framework", ["framework"]),
        ("idx_python_framework_config_type", ["config_type"]),
    ]
)

PYTHON_VALIDATION_SCHEMAS = TableSchema(
    name="python_validation_schemas",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),     # 'marshmallow', 'drf', 'wtforms'
        Column("schema_type", "TEXT", nullable=False),   # 'schema', 'field', 'serializer', 'form'
        Column("name", "TEXT"),
        Column("field_type", "TEXT"),
        Column("validators", "TEXT"),  # JSON array
        Column("required", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_validation_schemas_file", ["file"]),
        ("idx_python_validation_schemas_framework", ["framework"]),
    ]
)

# -----------------------------------------------------------------------------
# GROUP 4: Low-Level & Misc (5 tables)
# -----------------------------------------------------------------------------

PYTHON_OPERATORS = TableSchema(
    name="python_operators",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operator_type", "TEXT", nullable=False),  # 'binary', 'unary', 'membership', 'chained', 'ternary', 'walrus', 'matmul'
        Column("operator", "TEXT"),
        Column("left_operand", "TEXT"),
        Column("right_operand", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_operators_file", ["file"]),
        ("idx_python_operators_type", ["operator_type"]),
    ]
)

PYTHON_COLLECTIONS = TableSchema(
    name="python_collections",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("collection_type", "TEXT", nullable=False),  # 'dict', 'list', 'set', 'string', 'builtin', 'itertools', 'functools', 'collections'
        Column("operation", "TEXT"),
        Column("method", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_collections_file", ["file"]),
        ("idx_python_collections_type", ["collection_type"]),
    ]
)

PYTHON_STDLIB_USAGE = TableSchema(
    name="python_stdlib_usage",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("module", "TEXT", nullable=False),         # 're', 'json', 'datetime', 'pathlib', 'logging', 'threading', 'contextlib', 'typing', 'weakref', 'contextvars'
        Column("usage_type", "TEXT", nullable=False),     # 'pattern', 'operation', 'call'
        Column("function_name", "TEXT"),
        Column("pattern", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_stdlib_usage_file", ["file"]),
        ("idx_python_stdlib_usage_module", ["module"]),
    ]
)

PYTHON_IMPORTS_ADVANCED = TableSchema(
    name="python_imports_advanced",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("import_type", "TEXT", nullable=False),  # 'static', 'dynamic', 'namespace', 'module_attr'
        Column("module", "TEXT"),
        Column("name", "TEXT"),
        Column("alias", "TEXT"),
        Column("is_relative", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_imports_advanced_file", ["file"]),
        ("idx_python_imports_advanced_type", ["import_type"]),
    ]
)

PYTHON_EXPRESSIONS = TableSchema(
    name="python_expressions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("expression_type", "TEXT", nullable=False),  # 'comprehension', 'slice', 'tuple', 'unpack', 'none', 'truthiness', 'format', 'ellipsis', 'bytes', 'exec', 'copy', 'recursion', 'yield', 'complexity', 'resource', 'memoize', 'await', 'break', 'continue', 'pass', 'assert', 'del', 'with', 'class_decorator'
        Column("subtype", "TEXT"),                   # For comprehensions: 'list', 'dict', 'set', 'generator'
        Column("expression", "TEXT"),
        Column("variables", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_expressions_file", ["file"]),
        ("idx_python_expressions_type", ["expression_type"]),
    ]
)


# ============================================================================
# PYTHON TABLES REGISTRY (28 tables: 8 original + 20 consolidated)
# ============================================================================

PYTHON_TABLES: Dict[str, TableSchema] = {
    # =========================================================================
    # ORIGINAL TABLES (8 with verified consumers)
    # =========================================================================

    # ORM tables - consumers: overfetch.py, discovery.py, schema_cache_adapter.py
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,

    # Routes - consumers: boundary_analyzer.py, deadcode_graph.py, query.py
    "python_routes": PYTHON_ROUTES,

    # Validators - consumers: discovery.py (via SchemaMemoryCache)
    "python_validators": PYTHON_VALIDATORS,

    # Package configs - consumers: deps.py, blueprint.py
    "python_package_configs": PYTHON_PACKAGE_CONFIGS,

    # Decorators - consumers: interceptors.py, deadcode_graph.py, query.py
    "python_decorators": PYTHON_DECORATORS,

    # Django - consumers: interceptors.py
    "python_django_views": PYTHON_DJANGO_VIEWS,
    "python_django_middleware": PYTHON_DJANGO_MIDDLEWARE,

    # =========================================================================
    # CONSOLIDATED TABLES (20 new - Phase 2 Wire Extractors)
    # =========================================================================

    # Group 1: Control & Data Flow
    "python_loops": PYTHON_LOOPS,
    "python_branches": PYTHON_BRANCHES,
    "python_functions_advanced": PYTHON_FUNCTIONS_ADVANCED,
    "python_io_operations": PYTHON_IO_OPERATIONS,
    "python_state_mutations": PYTHON_STATE_MUTATIONS,

    # Group 2: Object-Oriented & Types
    "python_class_features": PYTHON_CLASS_FEATURES,
    "python_protocols": PYTHON_PROTOCOLS,
    "python_descriptors": PYTHON_DESCRIPTORS,
    "python_type_definitions": PYTHON_TYPE_DEFINITIONS,
    "python_literals": PYTHON_LITERALS,

    # Group 3: Security & Testing
    "python_security_findings": PYTHON_SECURITY_FINDINGS,
    "python_test_cases": PYTHON_TEST_CASES,
    "python_test_fixtures": PYTHON_TEST_FIXTURES,
    "python_framework_config": PYTHON_FRAMEWORK_CONFIG,
    "python_validation_schemas": PYTHON_VALIDATION_SCHEMAS,

    # Group 4: Low-Level & Misc
    "python_operators": PYTHON_OPERATORS,
    "python_collections": PYTHON_COLLECTIONS,
    "python_stdlib_usage": PYTHON_STDLIB_USAGE,
    "python_imports_advanced": PYTHON_IMPORTS_ADVANCED,
    "python_expressions": PYTHON_EXPRESSIONS,
}
