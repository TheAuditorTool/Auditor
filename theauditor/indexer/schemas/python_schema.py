"""
Python-specific schema definitions.

This module contains table schemas specific to Python frameworks and patterns:
- ORM models (SQLAlchemy, Django)
- HTTP routes (Flask, FastAPI, Django)
- Validation patterns (Pydantic)

Design Philosophy:
- Python-only tables
- Framework-specific extractions
- Complements core schema with language-specific patterns
"""

from typing import Dict
from .utils import Column, TableSchema


# ============================================================================
# PYTHON-SPECIFIC TABLES
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

PYTHON_BLUEPRINTS = TableSchema(
    name="python_blueprints",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER"),
        Column("blueprint_name", "TEXT", nullable=False),
        Column("url_prefix", "TEXT"),
        Column("subdomain", "TEXT"),
    ],
    primary_key=["file", "blueprint_name"],
    indexes=[
        ("idx_python_blueprints_file", ["file"]),
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

# Phase 2.2: Advanced Python patterns (decorators, async, testing, types)

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

PYTHON_CONTEXT_MANAGERS = TableSchema(
    name="python_context_managers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("context_type", "TEXT", nullable=False),
        Column("context_expr", "TEXT"),
        Column("as_name", "TEXT"),
        Column("is_async", "BOOLEAN", default="0"),
        Column("is_custom", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_context_managers_file", ["file"]),
        ("idx_python_context_managers_type", ["context_type"]),
        ("idx_python_context_managers_line", ["file", "line"]),
    ]
)

PYTHON_ASYNC_FUNCTIONS = TableSchema(
    name="python_async_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("has_await", "BOOLEAN", default="0"),
        Column("await_count", "INTEGER", default="0"),
        Column("has_async_with", "BOOLEAN", default="0"),
        Column("has_async_for", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_async_functions_file", ["file"]),
        ("idx_python_async_functions_name", ["function_name"]),
    ]
)

PYTHON_AWAIT_EXPRESSIONS = TableSchema(
    name="python_await_expressions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("await_expr", "TEXT", nullable=False),
        Column("containing_function", "TEXT"),
    ],
    indexes=[
        ("idx_python_await_expressions_file", ["file"]),
        ("idx_python_await_expressions_function", ["containing_function"]),
    ]
)

PYTHON_ASYNC_GENERATORS = TableSchema(
    name="python_async_generators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("generator_type", "TEXT", nullable=False),
        Column("target_vars", "TEXT"),
        Column("iterable_expr", "TEXT"),
        Column("function_name", "TEXT"),
    ],
    indexes=[
        ("idx_python_async_generators_file", ["file"]),
        ("idx_python_async_generators_type", ["generator_type"]),
    ]
)

PYTHON_PYTEST_FIXTURES = TableSchema(
    name="python_pytest_fixtures",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("fixture_name", "TEXT", nullable=False),
        Column("scope", "TEXT", default="'function'"),
        Column("has_autouse", "BOOLEAN", default="0"),
        Column("has_params", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "fixture_name"],
    indexes=[
        ("idx_python_pytest_fixtures_file", ["file"]),
        ("idx_python_pytest_fixtures_name", ["fixture_name"]),
        ("idx_python_pytest_fixtures_scope", ["scope"]),
    ]
)

PYTHON_PYTEST_PARAMETRIZE = TableSchema(
    name="python_pytest_parametrize",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("test_function", "TEXT", nullable=False),
        Column("parameter_names", "TEXT", nullable=False),
        Column("argvalues_count", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_python_pytest_parametrize_file", ["file"]),
        ("idx_python_pytest_parametrize_function", ["test_function"]),
    ]
)

PYTHON_PYTEST_MARKERS = TableSchema(
    name="python_pytest_markers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("test_function", "TEXT", nullable=False),
        Column("marker_name", "TEXT", nullable=False),
        Column("marker_args", "TEXT"),
    ],
    indexes=[
        ("idx_python_pytest_markers_file", ["file"]),
        ("idx_python_pytest_markers_name", ["marker_name"]),
    ]
)

PYTHON_MOCK_PATTERNS = TableSchema(
    name="python_mock_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("mock_type", "TEXT", nullable=False),
        Column("target", "TEXT"),
        Column("in_function", "TEXT"),
        Column("is_decorator", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_mock_patterns_file", ["file"]),
        ("idx_python_mock_patterns_type", ["mock_type"]),
    ]
)

# Phase 3.2: Testing Ecosystem Additions
PYTHON_UNITTEST_TEST_CASES = TableSchema(
    name="python_unittest_test_cases",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("test_class_name", "TEXT", nullable=False),
        Column("test_method_count", "INTEGER", default="0"),
        Column("has_setup", "BOOLEAN", default="0"),
        Column("has_teardown", "BOOLEAN", default="0"),
        Column("has_setupclass", "BOOLEAN", default="0"),
        Column("has_teardownclass", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "test_class_name"],
    indexes=[
        ("idx_python_unittest_test_cases_file", ["file"]),
        ("idx_python_unittest_test_cases_name", ["test_class_name"]),
    ]
)

PYTHON_ASSERTION_PATTERNS = TableSchema(
    name="python_assertion_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("assertion_type", "TEXT", nullable=False),
        Column("test_expr", "TEXT"),
        Column("assertion_method", "TEXT"),
    ],
    indexes=[
        ("idx_python_assertion_patterns_file", ["file"]),
        ("idx_python_assertion_patterns_function", ["function_name"]),
        ("idx_python_assertion_patterns_type", ["assertion_type"]),
    ]
)

PYTHON_PYTEST_PLUGIN_HOOKS = TableSchema(
    name="python_pytest_plugin_hooks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("hook_name", "TEXT", nullable=False),
        Column("param_count", "INTEGER", default="0"),
    ],
    primary_key=["file", "line", "hook_name"],
    indexes=[
        ("idx_python_pytest_plugin_hooks_file", ["file"]),
        ("idx_python_pytest_plugin_hooks_name", ["hook_name"]),
    ]
)

PYTHON_HYPOTHESIS_STRATEGIES = TableSchema(
    name="python_hypothesis_strategies",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("test_name", "TEXT", nullable=False),
        Column("strategy_count", "INTEGER", default="0"),
        Column("strategies", "TEXT"),
    ],
    primary_key=["file", "line", "test_name"],
    indexes=[
        ("idx_python_hypothesis_strategies_file", ["file"]),
        ("idx_python_hypothesis_strategies_test", ["test_name"]),
    ]
)

# Phase 3.3: Security Patterns (OWASP Top 10)
PYTHON_AUTH_DECORATORS = TableSchema(
    name="python_auth_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("permissions", "TEXT"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_auth_decorators_file", ["file"]),
        ("idx_python_auth_decorators_decorator", ["decorator_name"]),
    ]
)

PYTHON_PASSWORD_HASHING = TableSchema(
    name="python_password_hashing",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("hash_library", "TEXT"),
        Column("hash_method", "TEXT"),
        Column("is_weak", "BOOLEAN", default="0"),
        Column("has_hardcoded_value", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_password_hashing_file", ["file"]),
        ("idx_python_password_hashing_weak", ["is_weak"]),
        ("idx_python_password_hashing_hardcoded", ["has_hardcoded_value"]),
    ]
)

PYTHON_JWT_OPERATIONS = TableSchema(
    name="python_jwt_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),
        Column("algorithm", "TEXT"),
        Column("verify", "BOOLEAN"),
        Column("is_insecure", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_jwt_operations_file", ["file"]),
        ("idx_python_jwt_operations_insecure", ["is_insecure"]),
    ]
)

PYTHON_SQL_INJECTION = TableSchema(
    name="python_sql_injection",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("db_method", "TEXT", nullable=False),
        Column("interpolation_type", "TEXT"),
        Column("is_vulnerable", "BOOLEAN", default="1"),
    ],
    indexes=[
        ("idx_python_sql_injection_file", ["file"]),
        ("idx_python_sql_injection_vulnerable", ["is_vulnerable"]),
    ]
)

PYTHON_COMMAND_INJECTION = TableSchema(
    name="python_command_injection",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function", "TEXT", nullable=False),
        Column("shell_true", "BOOLEAN", default="0"),
        Column("is_vulnerable", "BOOLEAN", default="1"),
    ],
    indexes=[
        ("idx_python_command_injection_file", ["file"]),
        ("idx_python_command_injection_vulnerable", ["is_vulnerable"]),
    ]
)

PYTHON_PATH_TRAVERSAL = TableSchema(
    name="python_path_traversal",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function", "TEXT", nullable=False),
        Column("has_concatenation", "BOOLEAN", default="0"),
        Column("is_vulnerable", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_path_traversal_file", ["file"]),
        ("idx_python_path_traversal_vulnerable", ["is_vulnerable"]),
    ]
)

PYTHON_DANGEROUS_EVAL = TableSchema(
    name="python_dangerous_eval",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function", "TEXT", nullable=False),
        Column("is_constant_input", "BOOLEAN", default="0"),
        Column("is_critical", "BOOLEAN", default="1"),
    ],
    indexes=[
        ("idx_python_dangerous_eval_file", ["file"]),
        ("idx_python_dangerous_eval_critical", ["is_critical"]),
    ]
)

PYTHON_CRYPTO_OPERATIONS = TableSchema(
    name="python_crypto_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("algorithm", "TEXT"),
        Column("mode", "TEXT"),
        Column("is_weak", "BOOLEAN", default="0"),
        Column("has_hardcoded_key", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_crypto_operations_file", ["file"]),
        ("idx_python_crypto_operations_weak", ["is_weak"]),
        ("idx_python_crypto_operations_hardcoded", ["has_hardcoded_key"]),
    ]
)

# ============================================================================
# PHASE 3.4: DJANGO ADVANCED PATTERNS
# ============================================================================

PYTHON_DJANGO_SIGNALS = TableSchema(
    name="python_django_signals",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("signal_name", "TEXT", nullable=False),
        Column("signal_type", "TEXT"),  # definition, connection, custom
        Column("providing_args", "TEXT"),  # JSON array
        Column("sender", "TEXT"),  # Optional - for connections
        Column("receiver_function", "TEXT"),  # Optional - for connections
    ],
    primary_key=["file", "line", "signal_name"],
    indexes=[
        ("idx_python_django_signals_file", ["file"]),
        ("idx_python_django_signals_name", ["signal_name"]),
        ("idx_python_django_signals_type", ["signal_type"]),
    ]
)

PYTHON_DJANGO_RECEIVERS = TableSchema(
    name="python_django_receivers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("signals", "TEXT"),  # JSON array of signal names
        Column("sender", "TEXT"),  # Optional
        Column("is_weak", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_django_receivers_file", ["file"]),
        ("idx_python_django_receivers_function", ["function_name"]),
        ("idx_python_django_receivers_weak", ["is_weak"]),
    ]
)

PYTHON_DJANGO_MANAGERS = TableSchema(
    name="python_django_managers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("manager_name", "TEXT", nullable=False),
        Column("base_class", "TEXT"),  # Manager, BaseManager, etc.
        Column("custom_methods", "TEXT"),  # JSON array of method names
        Column("model_assignment", "TEXT"),  # Model.objects = ManagerName()
    ],
    primary_key=["file", "line", "manager_name"],
    indexes=[
        ("idx_python_django_managers_file", ["file"]),
        ("idx_python_django_managers_name", ["manager_name"]),
        ("idx_python_django_managers_base", ["base_class"]),
    ]
)

PYTHON_DJANGO_QUERYSETS = TableSchema(
    name="python_django_querysets",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("queryset_name", "TEXT", nullable=False),
        Column("base_class", "TEXT"),  # QuerySet
        Column("custom_methods", "TEXT"),  # JSON array of method names
        Column("has_as_manager", "BOOLEAN", default="0"),
        Column("method_chain", "TEXT"),  # Optional - for queryset chains
    ],
    primary_key=["file", "line", "queryset_name"],
    indexes=[
        ("idx_python_django_querysets_file", ["file"]),
        ("idx_python_django_querysets_name", ["queryset_name"]),
        ("idx_python_django_querysets_as_manager", ["has_as_manager"]),
    ]
)

PYTHON_PROTOCOLS = TableSchema(
    name="python_protocols",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("protocol_name", "TEXT", nullable=False),
        Column("methods", "TEXT"),
        Column("is_runtime_checkable", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "protocol_name"],
    indexes=[
        ("idx_python_protocols_file", ["file"]),
        ("idx_python_protocols_name", ["protocol_name"]),
    ]
)

PYTHON_GENERICS = TableSchema(
    name="python_generics",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("type_params", "TEXT"),
    ],
    primary_key=["file", "class_name"],
    indexes=[
        ("idx_python_generics_file", ["file"]),
        ("idx_python_generics_name", ["class_name"]),
    ]
)

PYTHON_TYPED_DICTS = TableSchema(
    name="python_typed_dicts",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("typeddict_name", "TEXT", nullable=False),
        Column("fields", "TEXT"),
    ],
    primary_key=["file", "typeddict_name"],
    indexes=[
        ("idx_python_typed_dicts_file", ["file"]),
        ("idx_python_typed_dicts_name", ["typeddict_name"]),
    ]
)

PYTHON_LITERALS = TableSchema(
    name="python_literals",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("usage_context", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("literal_type", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_literals_file", ["file"]),
        ("idx_python_literals_context", ["usage_context"]),
    ]
)

PYTHON_OVERLOADS = TableSchema(
    name="python_overloads",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("overload_count", "INTEGER", nullable=False),
        Column("variants", "TEXT", nullable=False),
    ],
    primary_key=["file", "function_name"],
    indexes=[
        ("idx_python_overloads_file", ["file"]),
        ("idx_python_overloads_name", ["function_name"]),
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

PYTHON_DJANGO_FORMS = TableSchema(
    name="python_django_forms",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("is_model_form", "BOOLEAN", default="0"),
        Column("model_name", "TEXT"),
        Column("field_count", "INTEGER", default="0"),
        Column("has_custom_clean", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "form_class_name"],
    indexes=[
        ("idx_python_django_forms_file", ["file"]),
        ("idx_python_django_forms_model", ["is_model_form"]),
        ("idx_python_django_forms_no_validators", ["has_custom_clean"]),
    ]
)

PYTHON_DJANGO_FORM_FIELDS = TableSchema(
    name="python_django_form_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),
        Column("required", "BOOLEAN", default="1"),
        Column("max_length", "INTEGER"),
        Column("has_custom_validator", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "form_class_name", "field_name"],
    indexes=[
        ("idx_python_django_form_fields_file", ["file"]),
        ("idx_python_django_form_fields_form", ["form_class_name"]),
        ("idx_python_django_form_fields_type", ["field_type"]),
        ("idx_python_django_form_fields_no_length", ["max_length"]),
    ]
)

PYTHON_DJANGO_ADMIN = TableSchema(
    name="python_django_admin",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("admin_class_name", "TEXT", nullable=False),
        Column("model_name", "TEXT"),
        Column("list_display", "TEXT"),
        Column("list_filter", "TEXT"),
        Column("search_fields", "TEXT"),
        Column("readonly_fields", "TEXT"),
        Column("has_custom_actions", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "admin_class_name"],
    indexes=[
        ("idx_python_django_admin_file", ["file"]),
        ("idx_python_django_admin_model", ["model_name"]),
        ("idx_python_django_admin_actions", ["has_custom_actions"]),
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

PYTHON_MARSHMALLOW_SCHEMAS = TableSchema(
    name="python_marshmallow_schemas",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("schema_class_name", "TEXT", nullable=False),
        Column("field_count", "INTEGER", default="0"),
        Column("has_nested_schemas", "BOOLEAN", default="0"),
        Column("has_custom_validators", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "schema_class_name"],
    indexes=[
        ("idx_python_marshmallow_schemas_file", ["file"]),
        ("idx_python_marshmallow_schemas_name", ["schema_class_name"]),
    ]
)

PYTHON_MARSHMALLOW_FIELDS = TableSchema(
    name="python_marshmallow_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("schema_class_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),
        Column("required", "BOOLEAN", default="0"),
        Column("allow_none", "BOOLEAN", default="0"),
        Column("has_validate", "BOOLEAN", default="0"),
        Column("has_custom_validator", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "schema_class_name", "field_name"],
    indexes=[
        ("idx_python_marshmallow_fields_file", ["file"]),
        ("idx_python_marshmallow_fields_schema", ["schema_class_name"]),
        ("idx_python_marshmallow_fields_required", ["required"]),
    ]
)

PYTHON_DRF_SERIALIZERS = TableSchema(
    name="python_drf_serializers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("serializer_class_name", "TEXT", nullable=False),
        Column("field_count", "INTEGER", default="0"),
        Column("is_model_serializer", "BOOLEAN", default="0"),
        Column("has_meta_model", "BOOLEAN", default="0"),
        Column("has_read_only_fields", "BOOLEAN", default="0"),
        Column("has_custom_validators", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "serializer_class_name"],
    indexes=[
        ("idx_python_drf_serializers_file", ["file"]),
        ("idx_python_drf_serializers_name", ["serializer_class_name"]),
        ("idx_python_drf_serializers_model", ["is_model_serializer"]),
    ]
)

PYTHON_DRF_SERIALIZER_FIELDS = TableSchema(
    name="python_drf_serializer_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("serializer_class_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),
        Column("read_only", "BOOLEAN", default="0"),
        Column("write_only", "BOOLEAN", default="0"),
        Column("required", "BOOLEAN", default="0"),
        Column("allow_null", "BOOLEAN", default="0"),
        Column("has_source", "BOOLEAN", default="0"),
        Column("has_custom_validator", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "serializer_class_name", "field_name"],
    indexes=[
        ("idx_python_drf_fields_file", ["file"]),
        ("idx_python_drf_fields_serializer", ["serializer_class_name"]),
        ("idx_python_drf_fields_read_only", ["read_only"]),
        ("idx_python_drf_fields_write_only", ["write_only"]),
    ]
)

PYTHON_WTFORMS_FORMS = TableSchema(
    name="python_wtforms_forms",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("field_count", "INTEGER", default="0"),
        Column("has_custom_validators", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "form_class_name"],
    indexes=[
        ("idx_python_wtforms_forms_file", ["file"]),
        ("idx_python_wtforms_forms_name", ["form_class_name"]),
    ]
)

PYTHON_WTFORMS_FIELDS = TableSchema(
    name="python_wtforms_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),
        Column("has_validators", "BOOLEAN", default="0"),
        Column("has_custom_validator", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "form_class_name", "field_name"],
    indexes=[
        ("idx_python_wtforms_fields_file", ["file"]),
        ("idx_python_wtforms_fields_form", ["form_class_name"]),
        ("idx_python_wtforms_fields_has_validators", ["has_validators"]),
    ]
)

PYTHON_CELERY_TASKS = TableSchema(
    name="python_celery_tasks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("task_name", "TEXT", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("arg_count", "INTEGER", default="0"),
        Column("bind", "BOOLEAN", default="0"),
        Column("serializer", "TEXT", nullable=True),
        Column("max_retries", "INTEGER", nullable=True),
        Column("rate_limit", "TEXT", nullable=True),
        Column("time_limit", "INTEGER", nullable=True),
        Column("queue", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "task_name"],
    indexes=[
        ("idx_python_celery_tasks_file", ["file"]),
        ("idx_python_celery_tasks_name", ["task_name"]),
        ("idx_python_celery_tasks_serializer", ["serializer"]),
        ("idx_python_celery_tasks_queue", ["queue"]),
    ]
)

PYTHON_CELERY_TASK_CALLS = TableSchema(
    name="python_celery_task_calls",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("caller_function", "TEXT", nullable=False),
        Column("task_name", "TEXT", nullable=False),
        Column("invocation_type", "TEXT", nullable=False),
        Column("arg_count", "INTEGER", default="0"),
        Column("has_countdown", "BOOLEAN", default="0"),
        Column("has_eta", "BOOLEAN", default="0"),
        Column("queue_override", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "caller_function", "task_name", "invocation_type"],
    indexes=[
        ("idx_python_celery_task_calls_file", ["file"]),
        ("idx_python_celery_task_calls_task", ["task_name"]),
        ("idx_python_celery_task_calls_type", ["invocation_type"]),
        ("idx_python_celery_task_calls_caller", ["caller_function"]),
    ]
)

PYTHON_CELERY_BEAT_SCHEDULES = TableSchema(
    name="python_celery_beat_schedules",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("schedule_name", "TEXT", nullable=False),
        Column("task_name", "TEXT", nullable=False),
        Column("schedule_type", "TEXT", nullable=False),
        Column("schedule_expression", "TEXT", nullable=True),
        Column("args", "TEXT", nullable=True),
        Column("kwargs", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "schedule_name"],
    indexes=[
        ("idx_python_celery_beat_schedules_file", ["file"]),
        ("idx_python_celery_beat_schedules_task", ["task_name"]),
        ("idx_python_celery_beat_schedules_type", ["schedule_type"]),
    ]
)

PYTHON_GENERATORS = TableSchema(
    name="python_generators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("generator_type", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("yield_count", "INTEGER", default="0"),
        Column("has_yield_from", "BOOLEAN", default="0"),
        Column("has_send", "BOOLEAN", default="0"),
        Column("is_infinite", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "name"],
    indexes=[
        ("idx_python_generators_file", ["file"]),
        ("idx_python_generators_type", ["generator_type"]),
        ("idx_python_generators_infinite", ["is_infinite"]),
    ]
)

# Flask Framework (Phase 3.1)
PYTHON_FLASK_APPS = TableSchema(
    name="python_flask_apps",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("factory_name", "TEXT", nullable=False),
        Column("app_var_name", "TEXT"),
        Column("config_source", "TEXT"),
        Column("registers_blueprints", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "factory_name"],
    indexes=[
        ("idx_python_flask_apps_file", ["file"]),
        ("idx_python_flask_apps_factory", ["factory_name"]),
        ("idx_python_flask_apps_config", ["config_source"]),
    ]
)

PYTHON_FLASK_EXTENSIONS = TableSchema(
    name="python_flask_extensions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("extension_type", "TEXT", nullable=False),
        Column("var_name", "TEXT"),
        Column("app_passed_to_constructor", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "extension_type", "var_name"],
    indexes=[
        ("idx_python_flask_extensions_file", ["file"]),
        ("idx_python_flask_extensions_type", ["extension_type"]),
    ]
)

PYTHON_FLASK_HOOKS = TableSchema(
    name="python_flask_hooks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("hook_type", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("app_var", "TEXT"),
    ],
    primary_key=["file", "line", "hook_type", "function_name"],
    indexes=[
        ("idx_python_flask_hooks_file", ["file"]),
        ("idx_python_flask_hooks_type", ["hook_type"]),
    ]
)

PYTHON_FLASK_ERROR_HANDLERS = TableSchema(
    name="python_flask_error_handlers",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("error_code", "INTEGER"),
        Column("exception_type", "TEXT"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_flask_error_handlers_file", ["file"]),
        ("idx_python_flask_error_handlers_code", ["error_code"]),
        ("idx_python_flask_error_handlers_exception", ["exception_type"]),
    ]
)

PYTHON_FLASK_WEBSOCKETS = TableSchema(
    name="python_flask_websockets",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("event_name", "TEXT"),
        Column("namespace", "TEXT"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_flask_websockets_file", ["file"]),
        ("idx_python_flask_websockets_event", ["event_name"]),
        ("idx_python_flask_websockets_namespace", ["namespace"]),
    ]
)

PYTHON_FLASK_CLI_COMMANDS = TableSchema(
    name="python_flask_cli_commands",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("command_name", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("has_options", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "command_name"],
    indexes=[
        ("idx_python_flask_cli_commands_file", ["file"]),
        ("idx_python_flask_cli_commands_name", ["command_name"]),
    ]
)

PYTHON_FLASK_CORS = TableSchema(
    name="python_flask_cors",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("config_type", "TEXT", nullable=False),
        Column("origins", "TEXT"),
        Column("is_permissive", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "config_type"],
    indexes=[
        ("idx_python_flask_cors_file", ["file"]),
        ("idx_python_flask_cors_type", ["config_type"]),
        ("idx_python_flask_cors_permissive", ["is_permissive"]),
    ]
)

PYTHON_FLASK_RATE_LIMITS = TableSchema(
    name="python_flask_rate_limits",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("limit_string", "TEXT"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_flask_rate_limits_file", ["file"]),
        ("idx_python_flask_rate_limits_function", ["function_name"]),
    ]
)

PYTHON_FLASK_CACHE = TableSchema(
    name="python_flask_cache",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("cache_type", "TEXT", nullable=False),
        Column("timeout", "INTEGER"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_flask_cache_file", ["file"]),
        ("idx_python_flask_cache_type", ["cache_type"]),
    ]
)

# ============================================================================
# CAUSAL LEARNING PATTERNS (Week 1 - Side Effect Detection)
# ============================================================================

PYTHON_INSTANCE_MUTATIONS = TableSchema(
    name="python_instance_mutations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target", "TEXT", nullable=False),  # 'self.counter', 'self.config.debug'
        Column("operation", "TEXT", nullable=False),  # 'assignment' | 'augmented_assignment' | 'method_call'
        Column("in_function", "TEXT", nullable=False),
        Column("is_init", "BOOLEAN", default="0"),  # True if in __init__ (expected mutation)
        Column("is_property_setter", "BOOLEAN", default="0"),  # True if in @property.setter
        Column("is_dunder_method", "BOOLEAN", default="0"),  # True if in __setitem__, __enter__, etc.
    ],
    primary_key=["file", "line", "target"],
    indexes=[
        ("idx_python_instance_mutations_file", ["file"]),
        ("idx_python_instance_mutations_function", ["in_function"]),
        ("idx_python_instance_mutations_side_effects", ["is_init", "is_property_setter", "is_dunder_method"]),
    ]
)

PYTHON_CLASS_MUTATIONS = TableSchema(
    name="python_class_mutations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),  # 'Counter' or 'cls'
        Column("attribute", "TEXT", nullable=False),  # 'instances', 'call_count'
        Column("operation", "TEXT", nullable=False),  # 'assignment' | 'augmented_assignment'
        Column("in_function", "TEXT", nullable=False),
        Column("is_classmethod", "BOOLEAN", default="0"),  # True if in @classmethod
    ],
    primary_key=["file", "line", "class_name", "attribute"],
    indexes=[
        ("idx_python_class_mutations_file", ["file"]),
        ("idx_python_class_mutations_class", ["class_name"]),
        ("idx_python_class_mutations_function", ["in_function"]),
    ]
)

PYTHON_GLOBAL_MUTATIONS = TableSchema(
    name="python_global_mutations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("global_name", "TEXT", nullable=False),  # '_cache', '_global_counter'
        Column("operation", "TEXT", nullable=False),  # 'assignment' | 'augmented_assignment' | 'item_assignment' | 'attr_assignment'
        Column("in_function", "TEXT", nullable=False),
    ],
    primary_key=["file", "line", "global_name"],
    indexes=[
        ("idx_python_global_mutations_file", ["file"]),
        ("idx_python_global_mutations_name", ["global_name"]),
        ("idx_python_global_mutations_function", ["in_function"]),
    ]
)

PYTHON_ARGUMENT_MUTATIONS = TableSchema(
    name="python_argument_mutations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("parameter_name", "TEXT", nullable=False),  # 'items', 'data', 'elements'
        Column("mutation_type", "TEXT", nullable=False),  # 'method_call' | 'item_assignment' | 'attr_assignment' | 'assignment' | 'augmented_assignment'
        Column("mutation_detail", "TEXT", nullable=False),  # Method name or operation type
        Column("in_function", "TEXT", nullable=False),
    ],
    primary_key=["file", "line", "parameter_name"],
    indexes=[
        ("idx_python_argument_mutations_file", ["file"]),
        ("idx_python_argument_mutations_param", ["parameter_name"]),
        ("idx_python_argument_mutations_function", ["in_function"]),
        ("idx_python_argument_mutations_type", ["mutation_type"]),
    ]
)

PYTHON_AUGMENTED_ASSIGNMENTS = TableSchema(
    name="python_augmented_assignments",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target", "TEXT", nullable=False),  # 'self.counter', 'Counter.instances', 'x'
        Column("operator", "TEXT", nullable=False),  # '+=' | '-=' | '*=' | '/=' | '//=' | '%=' | '**=' | '&=' | '|=' | '^=' | '>>=' | '<<='
        Column("target_type", "TEXT", nullable=False),  # 'instance' | 'class' | 'global' | 'local' | 'argument' | 'subscript'
        Column("in_function", "TEXT", nullable=False),
    ],
    primary_key=["file", "line", "target"],
    indexes=[
        ("idx_python_augmented_assignments_file", ["file"]),
        ("idx_python_augmented_assignments_target_type", ["target_type"]),
        ("idx_python_augmented_assignments_operator", ["operator"]),
        ("idx_python_augmented_assignments_function", ["in_function"]),
    ]
)

# ============================================================================
# CAUSAL LEARNING: EXCEPTION FLOW PATTERNS (Week 1, Block 1.2)
# ============================================================================

PYTHON_EXCEPTION_RAISES = TableSchema(
    name="python_exception_raises",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("exception_type", "TEXT"),  # 'ValueError' or None for bare raise
        Column("message", "TEXT"),  # Static message if extractable
        Column("from_exception", "TEXT"),  # Exception chaining (raise X from Y)
        Column("in_function", "TEXT", nullable=False),
        Column("condition", "TEXT"),  # Conditional raises (if x < 0: raise ...)
        Column("is_re_raise", "BOOLEAN", default="0"),  # True for bare 'raise'
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_python_exception_raises_file", ["file"]),
        ("idx_python_exception_raises_type", ["exception_type"]),
        ("idx_python_exception_raises_function", ["in_function"]),
        ("idx_python_exception_raises_re_raise", ["is_re_raise"]),
    ]
)

PYTHON_EXCEPTION_CATCHES = TableSchema(
    name="python_exception_catches",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("exception_types", "TEXT", nullable=False),  # Comma-separated for multiple types
        Column("variable_name", "TEXT"),  # 'e' in 'as e'
        Column("handling_strategy", "TEXT", nullable=False),  # 'return_none' | 're_raise' | 'log_and_continue' | etc.
        Column("in_function", "TEXT", nullable=False),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_python_exception_catches_file", ["file"]),
        ("idx_python_exception_catches_types", ["exception_types"]),
        ("idx_python_exception_catches_strategy", ["handling_strategy"]),
        ("idx_python_exception_catches_function", ["in_function"]),
    ]
)

PYTHON_FINALLY_BLOCKS = TableSchema(
    name="python_finally_blocks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("cleanup_calls", "TEXT"),  # Comma-separated function names called in finally
        Column("has_cleanup", "BOOLEAN", default="0"),  # True if contains cleanup logic
        Column("in_function", "TEXT", nullable=False),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_python_finally_blocks_file", ["file"]),
        ("idx_python_finally_blocks_function", ["in_function"]),
        ("idx_python_finally_blocks_has_cleanup", ["has_cleanup"]),
    ]
)

PYTHON_CONTEXT_MANAGERS_ENHANCED = TableSchema(
    name="python_context_managers_enhanced",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("context_expr", "TEXT", nullable=False),  # 'open(file)' or 'lock'
        Column("variable_name", "TEXT"),  # 'f' in 'as f'
        Column("in_function", "TEXT", nullable=False),
        Column("is_async", "BOOLEAN", default="0"),
        Column("resource_type", "TEXT"),  # 'file' | 'lock' | 'database' | 'network' | None
    ],
    primary_key=["file", "line", "context_expr"],
    indexes=[
        ("idx_python_context_managers_enhanced_file", ["file"]),
        ("idx_python_context_managers_enhanced_function", ["in_function"]),
        ("idx_python_context_managers_enhanced_resource", ["resource_type"]),
        ("idx_python_context_managers_enhanced_async", ["is_async"]),
    ]
)

# ============================================================================
# CAUSAL LEARNING: DATA FLOW PATTERNS (Week 2, Block 2.1)
# ============================================================================

PYTHON_IO_OPERATIONS = TableSchema(
    name="python_io_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("io_type", "TEXT", nullable=False),  # 'FILE_WRITE' | 'FILE_READ' | 'DB_COMMIT' | 'DB_QUERY' | 'NETWORK' | 'PROCESS' | 'ENV_MODIFY'
        Column("operation", "TEXT", nullable=False),  # 'open' | 'requests.post' | 'subprocess.run' | etc.
        Column("target", "TEXT"),  # Filename, URL, command, etc. (if static)
        Column("is_static", "BOOLEAN", default="0"),  # True if target is statically known
        Column("in_function", "TEXT", nullable=False),
    ],
    primary_key=["file", "line", "io_type", "operation"],
    indexes=[
        ("idx_python_io_operations_file", ["file"]),
        ("idx_python_io_operations_type", ["io_type"]),
        ("idx_python_io_operations_function", ["in_function"]),
        ("idx_python_io_operations_static", ["is_static"]),
    ]
)

PYTHON_PARAMETER_RETURN_FLOW = TableSchema(
    name="python_parameter_return_flow",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("parameter_name", "TEXT", nullable=False),  # Parameter referenced in return
        Column("return_expr", "TEXT", nullable=False),  # Full return expression
        Column("flow_type", "TEXT", nullable=False),  # 'direct' | 'transformed' | 'conditional' | 'other'
        Column("is_async", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "function_name", "parameter_name"],
    indexes=[
        ("idx_python_parameter_return_flow_file", ["file"]),
        ("idx_python_parameter_return_flow_function", ["function_name"]),
        ("idx_python_parameter_return_flow_type", ["flow_type"]),
    ]
)

PYTHON_CLOSURE_CAPTURES = TableSchema(
    name="python_closure_captures",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("inner_function", "TEXT", nullable=False),  # Nested function name
        Column("captured_variable", "TEXT", nullable=False),  # Variable from outer scope
        Column("outer_function", "TEXT", nullable=False),  # Enclosing function name
        Column("is_lambda", "BOOLEAN", default="0"),  # True if inner function is lambda
    ],
    primary_key=["file", "line", "inner_function", "captured_variable"],
    indexes=[
        ("idx_python_closure_captures_file", ["file"]),
        ("idx_python_closure_captures_inner", ["inner_function"]),
        ("idx_python_closure_captures_outer", ["outer_function"]),
        ("idx_python_closure_captures_variable", ["captured_variable"]),
    ]
)

PYTHON_NONLOCAL_ACCESS = TableSchema(
    name="python_nonlocal_access",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("variable_name", "TEXT", nullable=False),  # Nonlocal variable name
        Column("access_type", "TEXT", nullable=False),  # 'read' | 'write'
        Column("in_function", "TEXT", nullable=False),  # Function containing nonlocal declaration
    ],
    primary_key=["file", "line", "variable_name", "access_type"],
    indexes=[
        ("idx_python_nonlocal_access_file", ["file"]),
        ("idx_python_nonlocal_access_variable", ["variable_name"]),
        ("idx_python_nonlocal_access_type", ["access_type"]),
        ("idx_python_nonlocal_access_function", ["in_function"]),
    ]
)

PYTHON_CONDITIONAL_CALLS = TableSchema(
    name="python_conditional_calls",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_call", "TEXT", nullable=False),  # Function being called conditionally
        Column("condition_expr", "TEXT"),  # Condition expression (if extractable)
        Column("condition_type", "TEXT", nullable=False),  # 'if' | 'elif' | 'else' | 'guard' | 'exception'
        Column("in_function", "TEXT", nullable=False),  # Containing function
        Column("nesting_level", "INTEGER", nullable=False),  # Depth of conditional nesting
    ],
    primary_key=["file", "line", "function_call"],
    indexes=[
        ("idx_python_conditional_calls_file", ["file"]),
        ("idx_python_conditional_calls_function", ["function_call"]),
        ("idx_python_conditional_calls_type", ["condition_type"]),
        ("idx_python_conditional_calls_containing", ["in_function"]),
        ("idx_python_conditional_calls_nesting", ["nesting_level"]),
    ]
)

# ============================================================================
# CAUSAL LEARNING: BEHAVIORAL PATTERNS (Week 3, Block 3.1)
# ============================================================================

PYTHON_RECURSION_PATTERNS = TableSchema(
    name="python_recursion_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("recursion_type", "TEXT", nullable=False),  # 'direct' | 'tail' | 'mutual'
        Column("calls_function", "TEXT", nullable=False),  # Function being called
        Column("base_case_line", "INTEGER"),  # Line number of base case condition
        Column("is_async", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "function_name", "calls_function"],
    indexes=[
        ("idx_python_recursion_patterns_file", ["file"]),
        ("idx_python_recursion_patterns_function", ["function_name"]),
        ("idx_python_recursion_patterns_type", ["recursion_type"]),
    ]
)

PYTHON_GENERATOR_YIELDS = TableSchema(
    name="python_generator_yields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("generator_function", "TEXT", nullable=False),
        Column("yield_type", "TEXT", nullable=False),  # 'yield' | 'yield_from'
        Column("yield_expr", "TEXT"),  # Expression being yielded
        Column("condition", "TEXT"),  # Condition if inside if statement
        Column("in_loop", "BOOLEAN", default="0"),  # True if yield is inside a loop
    ],
    primary_key=["file", "line", "generator_function"],
    indexes=[
        ("idx_python_generator_yields_file", ["file"]),
        ("idx_python_generator_yields_function", ["generator_function"]),
        ("idx_python_generator_yields_type", ["yield_type"]),
        ("idx_python_generator_yields_in_loop", ["in_loop"]),
    ]
)

PYTHON_PROPERTY_PATTERNS = TableSchema(
    name="python_property_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("property_name", "TEXT", nullable=False),
        Column("access_type", "TEXT", nullable=False),  # 'getter' | 'setter' | 'deleter'
        Column("in_class", "TEXT", nullable=False),  # Class name containing property
        Column("has_computation", "BOOLEAN", default="0"),  # True if getter has computation
        Column("has_validation", "BOOLEAN", default="0"),  # True if setter has validation
    ],
    primary_key=["file", "line", "property_name", "access_type"],
    indexes=[
        ("idx_python_property_patterns_file", ["file"]),
        ("idx_python_property_patterns_property", ["property_name"]),
        ("idx_python_property_patterns_class", ["in_class"]),
        ("idx_python_property_patterns_type", ["access_type"]),
    ]
)

PYTHON_DYNAMIC_ATTRIBUTES = TableSchema(
    name="python_dynamic_attributes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method_name", "TEXT", nullable=False),  # '__getattr__' | '__setattr__' | '__getattribute__' | '__delattr__'
        Column("in_class", "TEXT", nullable=False),  # Class name containing method
        Column("has_delegation", "BOOLEAN", default="0"),  # True if method delegates to another object
        Column("has_validation", "BOOLEAN", default="0"),  # True if method validates
    ],
    primary_key=["file", "line", "method_name", "in_class"],
    indexes=[
        ("idx_python_dynamic_attributes_file", ["file"]),
        ("idx_python_dynamic_attributes_method", ["method_name"]),
        ("idx_python_dynamic_attributes_class", ["in_class"]),
    ]
)

# ============================================================================
# CAUSAL LEARNING: PERFORMANCE INDICATORS (Week 4, Block 4.1)
# ============================================================================

PYTHON_LOOP_COMPLEXITY = TableSchema(
    name="python_loop_complexity",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("loop_type", "TEXT", nullable=False),  # 'for' | 'while' | 'comprehension'
        Column("nesting_level", "INTEGER", nullable=False),  # 1, 2, 3, 4+
        Column("has_growing_operation", "BOOLEAN", default="0"),  # True if contains append/extend/+=
        Column("in_function", "TEXT", nullable=False),
        Column("estimated_complexity", "TEXT", nullable=False),  # 'O(n)' | 'O(n^2)' | 'O(n^3)' | etc.
    ],
    primary_key=["file", "line", "loop_type"],
    indexes=[
        ("idx_python_loop_complexity_file", ["file"]),
        ("idx_python_loop_complexity_function", ["in_function"]),
        ("idx_python_loop_complexity_nesting", ["nesting_level"]),
        ("idx_python_loop_complexity_complexity", ["estimated_complexity"]),
    ]
)

PYTHON_RESOURCE_USAGE = TableSchema(
    name="python_resource_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("resource_type", "TEXT", nullable=False),  # 'large_list' | 'large_dict' | 'file_handle' | 'db_connection' | 'string_concat'
        Column("allocation_expr", "TEXT", nullable=False),  # Expression that allocates resource
        Column("in_function", "TEXT", nullable=False),
        Column("has_cleanup", "BOOLEAN", default="0"),  # True if resource cleanup is present
    ],
    primary_key=["file", "line", "resource_type"],
    indexes=[
        ("idx_python_resource_usage_file", ["file"]),
        ("idx_python_resource_usage_type", ["resource_type"]),
        ("idx_python_resource_usage_function", ["in_function"]),
    ]
)

PYTHON_MEMOIZATION_PATTERNS = TableSchema(
    name="python_memoization_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("has_memoization", "BOOLEAN", default="0"),  # True if memoization present
        Column("memoization_type", "TEXT", nullable=False),  # 'lru_cache' | 'cache' | 'manual' | 'none'
        Column("is_recursive", "BOOLEAN", default="0"),  # True if function is recursive
        Column("cache_size", "INTEGER"),  # LRU cache size if specified
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_python_memoization_patterns_file", ["file"]),
        ("idx_python_memoization_patterns_function", ["function_name"]),
        ("idx_python_memoization_patterns_has_memo", ["has_memoization"]),
        ("idx_python_memoization_patterns_recursive", ["is_recursive"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: FUNDAMENTAL PATTERNS (Week 1)
# ============================================================================

PYTHON_COMPREHENSIONS = TableSchema(
    name="python_comprehensions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("comp_type", "TEXT", nullable=False),  # 'list' | 'dict' | 'set' | 'generator'
        Column("result_expr", "TEXT"),  # Expression being collected (e.g., 'x * 2')
        Column("iteration_var", "TEXT"),  # Iteration variable (e.g., 'x' or 'x, y')
        Column("iteration_source", "TEXT"),  # Source being iterated (e.g., 'range(10)')
        Column("has_filter", "BOOLEAN", default="0"),  # True if has 'if' condition
        Column("filter_expr", "TEXT"),  # Filter condition if present
        Column("nesting_level", "INTEGER", default="1"),  # 1 for simple, 2+ for nested
        Column("in_function", "TEXT", nullable=False),  # Containing function
    ],
    indexes=[
        ("idx_python_comp_file", ["file"]),
        ("idx_python_comp_type", ["comp_type"]),
        ("idx_python_comp_nesting", ["nesting_level"]),
        ("idx_python_comp_filter", ["has_filter"]),
    ]
)

PYTHON_LAMBDA_FUNCTIONS = TableSchema(
    name="python_lambda_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("parameter_count", "INTEGER", default="0"),  # Number of parameters
        Column("body", "TEXT"),  # Lambda body expression as text
        Column("captures_closure", "BOOLEAN", default="0"),  # True if captures outer vars
        Column("used_in", "TEXT"),  # 'map' | 'filter' | 'sorted_key' | 'assignment' | 'argument'
        Column("in_function", "TEXT", nullable=False),  # Containing function
    ],
    indexes=[
        ("idx_python_lambda_file", ["file"]),
        ("idx_python_lambda_captures", ["captures_closure"]),
        ("idx_python_lambda_usage", ["used_in"]),
    ]
)

PYTHON_SLICE_OPERATIONS = TableSchema(
    name="python_slice_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target", "TEXT"),  # Variable being sliced
        Column("has_start", "BOOLEAN", default="0"),  # True if start index present
        Column("has_stop", "BOOLEAN", default="0"),  # True if stop index present
        Column("has_step", "BOOLEAN", default="0"),  # True if step present
        Column("is_assignment", "BOOLEAN", default="0"),  # True if slice assignment
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_slice_file", ["file"]),
        ("idx_python_slice_assignment", ["is_assignment"]),
    ]
)

PYTHON_TUPLE_OPERATIONS = TableSchema(
    name="python_tuple_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),  # 'pack' | 'unpack' | 'literal'
        Column("element_count", "INTEGER", default="0"),  # Number of elements
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_tuple_file", ["file"]),
        ("idx_python_tuple_operation", ["operation"]),
    ]
)

PYTHON_UNPACKING_PATTERNS = TableSchema(
    name="python_unpacking_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("unpack_type", "TEXT", nullable=False),  # 'tuple' | 'list' | 'extended' | 'nested'
        Column("target_count", "INTEGER", default="0"),  # Number of target variables
        Column("has_rest", "BOOLEAN", default="0"),  # True if has *rest pattern
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_unpack_file", ["file"]),
        ("idx_python_unpack_type", ["unpack_type"]),
        ("idx_python_unpack_rest", ["has_rest"]),
    ]
)

PYTHON_NONE_PATTERNS = TableSchema(
    name="python_none_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("pattern", "TEXT", nullable=False),  # 'is_none_check' | 'none_assignment' | 'none_default' | 'none_return'
        Column("uses_is", "BOOLEAN", default="0"),  # True if uses 'is None' (correct)
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_none_file", ["file"]),
        ("idx_python_none_pattern", ["pattern"]),
        ("idx_python_none_uses_is", ["uses_is"]),
    ]
)

PYTHON_TRUTHINESS_PATTERNS = TableSchema(
    name="python_truthiness_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("pattern", "TEXT", nullable=False),  # 'implicit_bool' | 'explicit_bool' | 'short_circuit'
        Column("expression", "TEXT"),  # Expression being tested
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_truth_file", ["file"]),
        ("idx_python_truth_pattern", ["pattern"]),
    ]
)

PYTHON_STRING_FORMATTING = TableSchema(
    name="python_string_formatting",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("format_type", "TEXT", nullable=False),  # 'f_string' | 'percent' | 'format_method' | 'template'
        Column("has_expressions", "BOOLEAN", default="0"),  # True if has expressions (f"{x + 1}")
        Column("var_count", "INTEGER", default="0"),  # Number of interpolated variables
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_format_file", ["file"]),
        ("idx_python_format_type", ["format_type"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: OPERATORS (Week 2)
# ============================================================================

PYTHON_OPERATORS = TableSchema(
    name="python_operators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operator_type", "TEXT", nullable=False),  # 'arithmetic' | 'comparison' | 'logical' | 'bitwise' | 'unary'
        Column("operator", "TEXT", nullable=False),  # Symbol: +, -, *, ==, and, etc.
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_operators_file", ["file"]),
        ("idx_python_operators_type", ["operator_type"]),
    ]
)

PYTHON_MEMBERSHIP_TESTS = TableSchema(
    name="python_membership_tests",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operator", "TEXT", nullable=False),  # 'in' | 'not in'
        Column("container_type", "TEXT"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_membership_file", ["file"]),
    ]
)

PYTHON_CHAINED_COMPARISONS = TableSchema(
    name="python_chained_comparisons",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("chain_length", "INTEGER", nullable=False),
        Column("operators", "TEXT"),  # Comma-separated
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_chained_file", ["file"]),
    ]
)

PYTHON_TERNARY_EXPRESSIONS = TableSchema(
    name="python_ternary_expressions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("has_complex_condition", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_ternary_file", ["file"]),
    ]
)

PYTHON_WALRUS_OPERATORS = TableSchema(
    name="python_walrus_operators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("variable", "TEXT", nullable=False),
        Column("used_in", "TEXT", nullable=False),  # 'if' | 'while' | 'comprehension' | 'expression'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_walrus_file", ["file"]),
    ]
)

PYTHON_MATRIX_MULTIPLICATION = TableSchema(
    name="python_matrix_multiplication",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_matmul_file", ["file"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: COLLECTIONS (Week 3)
# ============================================================================

PYTHON_DICT_OPERATIONS = TableSchema(
    name="python_dict_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),
        Column("has_default", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_dict_ops_file", ["file"]),
        ("idx_python_dict_ops_operation", ["operation"]),
    ]
)

PYTHON_LIST_MUTATIONS = TableSchema(
    name="python_list_mutations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method", "TEXT", nullable=False),
        Column("mutates_in_place", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_list_mut_file", ["file"]),
        ("idx_python_list_mut_method", ["method"]),
    ]
)

PYTHON_SET_OPERATIONS = TableSchema(
    name="python_set_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_set_ops_file", ["file"]),
    ]
)

PYTHON_STRING_METHODS = TableSchema(
    name="python_string_methods",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_str_methods_file", ["file"]),
        ("idx_python_str_methods_method", ["method"]),
    ]
)

PYTHON_BUILTIN_USAGE = TableSchema(
    name="python_builtin_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("builtin", "TEXT", nullable=False),
        Column("has_key", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_builtin_file", ["file"]),
        ("idx_python_builtin_name", ["builtin"]),
    ]
)

PYTHON_ITERTOOLS_USAGE = TableSchema(
    name="python_itertools_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function", "TEXT", nullable=False),
        Column("is_infinite", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_itertools_file", ["file"]),
    ]
)

PYTHON_FUNCTOOLS_USAGE = TableSchema(
    name="python_functools_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function", "TEXT", nullable=False),
        Column("is_decorator", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_functools_file", ["file"]),
    ]
)

PYTHON_COLLECTIONS_USAGE = TableSchema(
    name="python_collections_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("collection_type", "TEXT", nullable=False),
        Column("default_factory", "TEXT"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_collections_file", ["file"]),
        ("idx_python_collections_type", ["collection_type"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: ADVANCED CLASS FEATURES (Week 4)
# ============================================================================

PYTHON_METACLASSES = TableSchema(
    name="python_metaclasses",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("metaclass_name", "TEXT", nullable=False),
        Column("is_definition", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_metaclass_file", ["file"]),
    ]
)

PYTHON_DESCRIPTORS = TableSchema(
    name="python_descriptors",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("has_get", "BOOLEAN", default="0"),
        Column("has_set", "BOOLEAN", default="0"),
        Column("has_delete", "BOOLEAN", default="0"),
        Column("descriptor_type", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_descriptor_file", ["file"]),
    ]
)

PYTHON_DATACLASSES = TableSchema(
    name="python_dataclasses",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("frozen", "BOOLEAN", default="0"),
        Column("field_count", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_python_dataclass_file", ["file"]),
    ]
)

PYTHON_ENUMS = TableSchema(
    name="python_enums",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("enum_name", "TEXT", nullable=False),
        Column("enum_type", "TEXT", nullable=False),
        Column("member_count", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_python_enum_file", ["file"]),
    ]
)

PYTHON_SLOTS = TableSchema(
    name="python_slots",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("slot_count", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_python_slots_file", ["file"]),
    ]
)

PYTHON_ABSTRACT_CLASSES = TableSchema(
    name="python_abstract_classes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("abstract_method_count", "INTEGER", default="0"),
    ],
    indexes=[
        ("idx_python_abstract_file", ["file"]),
    ]
)

PYTHON_METHOD_TYPES = TableSchema(
    name="python_method_types",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("method_type", "TEXT", nullable=False),
        Column("in_class", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_method_types_file", ["file"]),
        ("idx_python_method_types_type", ["method_type"]),
    ]
)

PYTHON_MULTIPLE_INHERITANCE = TableSchema(
    name="python_multiple_inheritance",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("base_count", "INTEGER", nullable=False),
        Column("base_classes", "TEXT"),
    ],
    indexes=[
        ("idx_python_multi_inherit_file", ["file"]),
    ]
)

PYTHON_DUNDER_METHODS = TableSchema(
    name="python_dunder_methods",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("category", "TEXT", nullable=False),
        Column("in_class", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_dunder_file", ["file"]),
        ("idx_python_dunder_category", ["category"]),
    ]
)

PYTHON_VISIBILITY_CONVENTIONS = TableSchema(
    name="python_visibility_conventions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("visibility", "TEXT", nullable=False),
        Column("is_name_mangled", "BOOLEAN", default="0"),
        Column("in_class", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_visibility_file", ["file"]),
        ("idx_python_visibility_type", ["visibility"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: STDLIB PATTERNS (Week 4)
# ============================================================================

PYTHON_REGEX_PATTERNS = TableSchema(
    name="python_regex_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),
        Column("has_flags", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_regex_file", ["file"]),
    ]
)

PYTHON_JSON_OPERATIONS = TableSchema(
    name="python_json_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),
        Column("direction", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_json_file", ["file"]),
    ]
)

PYTHON_DATETIME_OPERATIONS = TableSchema(
    name="python_datetime_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("datetime_type", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_datetime_file", ["file"]),
    ]
)

PYTHON_PATH_OPERATIONS = TableSchema(
    name="python_path_operations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),
        Column("path_type", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_path_file", ["file"]),
    ]
)

PYTHON_LOGGING_PATTERNS = TableSchema(
    name="python_logging_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("log_level", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_logging_file", ["file"]),
        ("idx_python_logging_level", ["log_level"]),
    ]
)

PYTHON_THREADING_PATTERNS = TableSchema(
    name="python_threading_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("threading_type", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_threading_file", ["file"]),
    ]
)

PYTHON_CONTEXTLIB_PATTERNS = TableSchema(
    name="python_contextlib_patterns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("pattern", "TEXT", nullable=False),
        Column("is_decorator", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_contextlib_file", ["file"]),
    ]
)

PYTHON_TYPE_CHECKING = TableSchema(
    name="python_type_checking",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("check_type", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_type_check_file", ["file"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: CONTROL FLOW PATTERNS (Week 5)
# ============================================================================

PYTHON_FOR_LOOPS = TableSchema(
    name="python_for_loops",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("loop_type", "TEXT", nullable=False),  # 'enumerate' | 'zip' | 'range' | 'items' | 'values' | 'keys' | 'plain'
        Column("has_else", "BOOLEAN", default="0"),
        Column("nesting_level", "INTEGER", nullable=False),
        Column("target_count", "INTEGER", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_for_loops_file", ["file"]),
        ("idx_python_for_loops_type", ["loop_type"]),
        ("idx_python_for_loops_file_line", ["file", "line"]),
    ]
)

PYTHON_WHILE_LOOPS = TableSchema(
    name="python_while_loops",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("has_else", "BOOLEAN", default="0"),
        Column("is_infinite", "BOOLEAN", default="0"),
        Column("nesting_level", "INTEGER", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_while_loops_file", ["file"]),
        ("idx_python_while_loops_infinite", ["is_infinite"]),
        ("idx_python_while_loops_file_line", ["file", "line"]),
    ]
)

PYTHON_ASYNC_FOR_LOOPS = TableSchema(
    name="python_async_for_loops",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("has_else", "BOOLEAN", default="0"),
        Column("target_count", "INTEGER", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_async_for_file", ["file"]),
        ("idx_python_async_for_file_line", ["file", "line"]),
    ]
)

PYTHON_IF_STATEMENTS = TableSchema(
    name="python_if_statements",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("has_elif", "BOOLEAN", default="0"),
        Column("has_else", "BOOLEAN", default="0"),
        Column("chain_length", "INTEGER", nullable=False),
        Column("nesting_level", "INTEGER", nullable=False),
        Column("has_complex_condition", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_if_file", ["file"]),
        ("idx_python_if_complex", ["has_complex_condition"]),
        ("idx_python_if_file_line", ["file", "line"]),
    ]
)

PYTHON_MATCH_STATEMENTS = TableSchema(
    name="python_match_statements",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("case_count", "INTEGER", nullable=False),
        Column("has_wildcard", "BOOLEAN", default="0"),
        Column("has_guards", "BOOLEAN", default="0"),
        Column("pattern_types", "TEXT", nullable=False),  # Comma-separated
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_match_file", ["file"]),
        ("idx_python_match_file_line", ["file", "line"]),
    ]
)

PYTHON_BREAK_CONTINUE_PASS = TableSchema(
    name="python_break_continue_pass",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("statement_type", "TEXT", nullable=False),  # 'break' | 'continue' | 'pass'
        Column("loop_type", "TEXT", nullable=False),  # 'for' | 'while' | 'none'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_flow_control_file", ["file"]),
        ("idx_python_flow_control_type", ["statement_type"]),
        ("idx_python_flow_control_file_line", ["file", "line"]),
    ]
)

PYTHON_ASSERT_STATEMENTS = TableSchema(
    name="python_assert_statements",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("has_message", "BOOLEAN", default="0"),
        Column("condition_type", "TEXT", nullable=False),  # 'comparison' | 'isinstance' | 'callable' | 'simple'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_assert_file", ["file"]),
        ("idx_python_assert_file_line", ["file", "line"]),
    ]
)

PYTHON_DEL_STATEMENTS = TableSchema(
    name="python_del_statements",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_type", "TEXT", nullable=False),  # 'name' | 'subscript' | 'attribute'
        Column("target_count", "INTEGER", nullable=False),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_del_file", ["file"]),
        ("idx_python_del_type", ["target_type"]),
        ("idx_python_del_file_line", ["file", "line"]),
    ]
)

PYTHON_IMPORT_STATEMENTS = TableSchema(
    name="python_import_statements",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("import_type", "TEXT", nullable=False),  # 'import' | 'from' | 'relative'
        Column("module", "TEXT", nullable=False),
        Column("has_alias", "BOOLEAN", default="0"),
        Column("is_wildcard", "BOOLEAN", default="0"),
        Column("relative_level", "INTEGER", default="0"),
        Column("imported_names", "TEXT", nullable=False),  # Comma-separated
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_import_file", ["file"]),
        ("idx_python_import_module", ["module"]),
        ("idx_python_import_type", ["import_type"]),
        ("idx_python_import_file_line", ["file", "line"]),
    ]
)

PYTHON_WITH_STATEMENTS = TableSchema(
    name="python_with_statements",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("is_async", "BOOLEAN", default="0"),
        Column("context_count", "INTEGER", nullable=False),
        Column("has_alias", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_with_file", ["file"]),
        ("idx_python_with_async", ["is_async"]),
        ("idx_python_with_file_line", ["file", "line"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: PROTOCOL PATTERNS (Week 6)
# ============================================================================

PYTHON_ITERATOR_PROTOCOL = TableSchema(
    name="python_iterator_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("has_iter", "BOOLEAN", default="0"),
        Column("has_next", "BOOLEAN", default="0"),
        Column("raises_stopiteration", "BOOLEAN", default="0"),
        Column("is_generator", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_iterator_file", ["file"]),
        ("idx_python_iterator_class", ["class_name"]),
        ("idx_python_iterator_file_line", ["file", "line"]),
    ]
)

PYTHON_CONTAINER_PROTOCOL = TableSchema(
    name="python_container_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("has_len", "BOOLEAN", default="0"),
        Column("has_getitem", "BOOLEAN", default="0"),
        Column("has_setitem", "BOOLEAN", default="0"),
        Column("has_delitem", "BOOLEAN", default="0"),
        Column("has_contains", "BOOLEAN", default="0"),
        Column("is_sequence", "BOOLEAN", default="0"),
        Column("is_mapping", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_container_file", ["file"]),
        ("idx_python_container_class", ["class_name"]),
        ("idx_python_container_file_line", ["file", "line"]),
    ]
)

PYTHON_CALLABLE_PROTOCOL = TableSchema(
    name="python_callable_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("param_count", "INTEGER", nullable=False),
        Column("has_args", "BOOLEAN", default="0"),
        Column("has_kwargs", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_callable_file", ["file"]),
        ("idx_python_callable_class", ["class_name"]),
        ("idx_python_callable_file_line", ["file", "line"]),
    ]
)

PYTHON_COMPARISON_PROTOCOL = TableSchema(
    name="python_comparison_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("methods", "TEXT", nullable=False),  # Comma-separated
        Column("is_total_ordering", "BOOLEAN", default="0"),
        Column("has_all_rich", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_comparison_file", ["file"]),
        ("idx_python_comparison_class", ["class_name"]),
        ("idx_python_comparison_file_line", ["file", "line"]),
    ]
)

PYTHON_ARITHMETIC_PROTOCOL = TableSchema(
    name="python_arithmetic_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("methods", "TEXT", nullable=False),  # Comma-separated
        Column("has_reflected", "BOOLEAN", default="0"),
        Column("has_inplace", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_arithmetic_file", ["file"]),
        ("idx_python_arithmetic_class", ["class_name"]),
        ("idx_python_arithmetic_file_line", ["file", "line"]),
    ]
)

PYTHON_PICKLE_PROTOCOL = TableSchema(
    name="python_pickle_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("has_getstate", "BOOLEAN", default="0"),
        Column("has_setstate", "BOOLEAN", default="0"),
        Column("has_reduce", "BOOLEAN", default="0"),
        Column("has_reduce_ex", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_pickle_file", ["file"]),
        ("idx_python_pickle_class", ["class_name"]),
        ("idx_python_pickle_file_line", ["file", "line"]),
    ]
)

PYTHON_WEAKREF_USAGE = TableSchema(
    name="python_weakref_usage",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("usage_type", "TEXT", nullable=False),  # 'ref' | 'proxy' | 'WeakValueDictionary' | 'WeakKeyDictionary'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_weakref_file", ["file"]),
        ("idx_python_weakref_type", ["usage_type"]),
        ("idx_python_weakref_file_line", ["file", "line"]),
    ]
)

PYTHON_CONTEXTVAR_USAGE = TableSchema(
    name="python_contextvar_usage",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),  # 'ContextVar' | 'get' | 'set' | 'Token'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_contextvar_file", ["file"]),
        ("idx_python_contextvar_op", ["operation"]),
        ("idx_python_contextvar_file_line", ["file", "line"]),
    ]
)

PYTHON_MODULE_ATTRIBUTES = TableSchema(
    name="python_module_attributes",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("attribute", "TEXT", nullable=False),  # '__name__' | '__file__' | '__doc__' | '__all__'
        Column("usage_type", "TEXT", nullable=False),  # 'read' | 'write' | 'check'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_module_attr_file", ["file"]),
        ("idx_python_module_attr_name", ["attribute"]),
        ("idx_python_module_attr_file_line", ["file", "line"]),
    ]
)

PYTHON_CLASS_DECORATORS = TableSchema(
    name="python_class_decorators",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("decorator", "TEXT", nullable=False),
        Column("decorator_type", "TEXT", nullable=False),  # 'dataclass' | 'total_ordering' | 'custom'
        Column("has_arguments", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_class_dec_file", ["file"]),
        ("idx_python_class_dec_type", ["decorator_type"]),
        ("idx_python_class_dec_file_line", ["file", "line"]),
    ]
)

# ============================================================================
# PYTHON COVERAGE V2: ADVANCED PATTERNS
# ============================================================================

PYTHON_NAMESPACE_PACKAGES = TableSchema(
    name="python_namespace_packages",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("pattern", "TEXT", nullable=False),  # 'extend_path' | 'path_manipulation'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_namespace_file", ["file"]),
        ("idx_python_namespace_pattern", ["pattern"]),
    ]
)

PYTHON_CACHED_PROPERTY = TableSchema(
    name="python_cached_property",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("in_class", "TEXT", nullable=False),
        Column("is_functools", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_cached_prop_file", ["file"]),
        ("idx_python_cached_prop_class", ["in_class"]),
    ]
)

PYTHON_DESCRIPTOR_PROTOCOL = TableSchema(
    name="python_descriptor_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("has_get", "BOOLEAN", default="0"),
        Column("has_set", "BOOLEAN", default="0"),
        Column("has_delete", "BOOLEAN", default="0"),
        Column("is_data_descriptor", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_descriptor_file", ["file"]),
        ("idx_python_descriptor_class", ["class_name"]),
    ]
)

PYTHON_ATTRIBUTE_ACCESS_PROTOCOL = TableSchema(
    name="python_attribute_access_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("has_getattr", "BOOLEAN", default="0"),
        Column("has_setattr", "BOOLEAN", default="0"),
        Column("has_delattr", "BOOLEAN", default="0"),
        Column("has_getattribute", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_attr_access_file", ["file"]),
        ("idx_python_attr_access_class", ["class_name"]),
    ]
)

PYTHON_COPY_PROTOCOL = TableSchema(
    name="python_copy_protocol",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("has_copy", "BOOLEAN", default="0"),
        Column("has_deepcopy", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_python_copy_file", ["file"]),
        ("idx_python_copy_class", ["class_name"]),
    ]
)

PYTHON_ELLIPSIS_USAGE = TableSchema(
    name="python_ellipsis_usage",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("context", "TEXT", nullable=False),  # 'type_hint' | 'slice' | 'expression' | 'pass_placeholder'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_ellipsis_file", ["file"]),
        ("idx_python_ellipsis_context", ["context"]),
    ]
)

PYTHON_BYTES_OPERATIONS = TableSchema(
    name="python_bytes_operations",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),  # 'bytes' | 'bytearray' | 'encode' | 'decode' | 'literal'
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_bytes_file", ["file"]),
        ("idx_python_bytes_operation", ["operation"]),
    ]
)

PYTHON_EXEC_EVAL_COMPILE = TableSchema(
    name="python_exec_eval_compile",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operation", "TEXT", nullable=False),  # 'exec' | 'eval' | 'compile'
        Column("has_globals", "BOOLEAN", default="0"),
        Column("has_locals", "BOOLEAN", default="0"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_exec_file", ["file"]),
        ("idx_python_exec_operation", ["operation"]),
    ]
)

# ============================================================================
# PYTHON TABLES REGISTRY
# ============================================================================

PYTHON_TABLES: dict[str, TableSchema] = {
    # Basic Python (Phase 1)
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,
    "python_routes": PYTHON_ROUTES,
    "python_blueprints": PYTHON_BLUEPRINTS,
    "python_validators": PYTHON_VALIDATORS,
    "python_package_configs": PYTHON_PACKAGE_CONFIGS,

    # Advanced Python (Phase 2.2)
    "python_decorators": PYTHON_DECORATORS,
    "python_context_managers": PYTHON_CONTEXT_MANAGERS,
    "python_async_functions": PYTHON_ASYNC_FUNCTIONS,
    "python_await_expressions": PYTHON_AWAIT_EXPRESSIONS,
    "python_async_generators": PYTHON_ASYNC_GENERATORS,
    "python_pytest_fixtures": PYTHON_PYTEST_FIXTURES,
    "python_pytest_parametrize": PYTHON_PYTEST_PARAMETRIZE,
    "python_pytest_markers": PYTHON_PYTEST_MARKERS,
    "python_mock_patterns": PYTHON_MOCK_PATTERNS,
    # Phase 3.2: Testing Ecosystem Additions
    "python_unittest_test_cases": PYTHON_UNITTEST_TEST_CASES,
    "python_assertion_patterns": PYTHON_ASSERTION_PATTERNS,
    "python_pytest_plugin_hooks": PYTHON_PYTEST_PLUGIN_HOOKS,
    "python_hypothesis_strategies": PYTHON_HYPOTHESIS_STRATEGIES,
    # Phase 3.3: Security Patterns (OWASP Top 10)
    "python_auth_decorators": PYTHON_AUTH_DECORATORS,
    "python_password_hashing": PYTHON_PASSWORD_HASHING,
    "python_jwt_operations": PYTHON_JWT_OPERATIONS,
    "python_sql_injection": PYTHON_SQL_INJECTION,
    "python_command_injection": PYTHON_COMMAND_INJECTION,
    "python_path_traversal": PYTHON_PATH_TRAVERSAL,
    "python_dangerous_eval": PYTHON_DANGEROUS_EVAL,
    "python_crypto_operations": PYTHON_CRYPTO_OPERATIONS,
    # Phase 3.4: Django Advanced
    "python_django_signals": PYTHON_DJANGO_SIGNALS,
    "python_django_receivers": PYTHON_DJANGO_RECEIVERS,
    "python_django_managers": PYTHON_DJANGO_MANAGERS,
    "python_django_querysets": PYTHON_DJANGO_QUERYSETS,
    "python_protocols": PYTHON_PROTOCOLS,
    "python_generics": PYTHON_GENERICS,
    "python_typed_dicts": PYTHON_TYPED_DICTS,
    "python_literals": PYTHON_LITERALS,
    "python_overloads": PYTHON_OVERLOADS,
    "python_django_views": PYTHON_DJANGO_VIEWS,
    "python_django_forms": PYTHON_DJANGO_FORMS,
    "python_django_form_fields": PYTHON_DJANGO_FORM_FIELDS,
    "python_django_admin": PYTHON_DJANGO_ADMIN,
    "python_django_middleware": PYTHON_DJANGO_MIDDLEWARE,
    "python_marshmallow_schemas": PYTHON_MARSHMALLOW_SCHEMAS,
    "python_marshmallow_fields": PYTHON_MARSHMALLOW_FIELDS,
    "python_drf_serializers": PYTHON_DRF_SERIALIZERS,
    "python_drf_serializer_fields": PYTHON_DRF_SERIALIZER_FIELDS,
    "python_wtforms_forms": PYTHON_WTFORMS_FORMS,
    "python_wtforms_fields": PYTHON_WTFORMS_FIELDS,
    "python_celery_tasks": PYTHON_CELERY_TASKS,
    "python_celery_task_calls": PYTHON_CELERY_TASK_CALLS,
    "python_celery_beat_schedules": PYTHON_CELERY_BEAT_SCHEDULES,
    "python_generators": PYTHON_GENERATORS,

    # Flask Framework (Phase 3.1)
    "python_flask_apps": PYTHON_FLASK_APPS,
    "python_flask_extensions": PYTHON_FLASK_EXTENSIONS,
    "python_flask_hooks": PYTHON_FLASK_HOOKS,
    "python_flask_error_handlers": PYTHON_FLASK_ERROR_HANDLERS,
    "python_flask_websockets": PYTHON_FLASK_WEBSOCKETS,
    "python_flask_cli_commands": PYTHON_FLASK_CLI_COMMANDS,
    "python_flask_cors": PYTHON_FLASK_CORS,
    "python_flask_rate_limits": PYTHON_FLASK_RATE_LIMITS,
    "python_flask_cache": PYTHON_FLASK_CACHE,
    # Causal Learning Patterns (Week 1 - Side Effect Detection)
    "python_instance_mutations": PYTHON_INSTANCE_MUTATIONS,
    "python_class_mutations": PYTHON_CLASS_MUTATIONS,
    "python_global_mutations": PYTHON_GLOBAL_MUTATIONS,
    "python_argument_mutations": PYTHON_ARGUMENT_MUTATIONS,
    "python_augmented_assignments": PYTHON_AUGMENTED_ASSIGNMENTS,
    # Causal Learning Patterns (Week 1 - Exception Flow)
    "python_exception_raises": PYTHON_EXCEPTION_RAISES,
    "python_exception_catches": PYTHON_EXCEPTION_CATCHES,
    "python_finally_blocks": PYTHON_FINALLY_BLOCKS,
    "python_context_managers_enhanced": PYTHON_CONTEXT_MANAGERS_ENHANCED,
    # Causal Learning Patterns (Week 2 - Data Flow)
    "python_io_operations": PYTHON_IO_OPERATIONS,
    "python_parameter_return_flow": PYTHON_PARAMETER_RETURN_FLOW,
    "python_closure_captures": PYTHON_CLOSURE_CAPTURES,
    "python_nonlocal_access": PYTHON_NONLOCAL_ACCESS,
    "python_conditional_calls": PYTHON_CONDITIONAL_CALLS,
    # Causal Learning Patterns (Week 3 - Behavioral)
    "python_recursion_patterns": PYTHON_RECURSION_PATTERNS,
    "python_generator_yields": PYTHON_GENERATOR_YIELDS,
    "python_property_patterns": PYTHON_PROPERTY_PATTERNS,
    "python_dynamic_attributes": PYTHON_DYNAMIC_ATTRIBUTES,
    # Causal Learning Patterns (Week 4 - Performance)
    "python_loop_complexity": PYTHON_LOOP_COMPLEXITY,
    "python_resource_usage": PYTHON_RESOURCE_USAGE,
    "python_memoization_patterns": PYTHON_MEMOIZATION_PATTERNS,
    # Python Coverage V2 (Week 1 - Fundamentals)
    "python_comprehensions": PYTHON_COMPREHENSIONS,
    "python_lambda_functions": PYTHON_LAMBDA_FUNCTIONS,
    "python_slice_operations": PYTHON_SLICE_OPERATIONS,
    "python_tuple_operations": PYTHON_TUPLE_OPERATIONS,
    "python_unpacking_patterns": PYTHON_UNPACKING_PATTERNS,
    "python_none_patterns": PYTHON_NONE_PATTERNS,
    "python_truthiness_patterns": PYTHON_TRUTHINESS_PATTERNS,
    "python_string_formatting": PYTHON_STRING_FORMATTING,
    # Python Coverage V2 (Week 2 - Operators)
    "python_operators": PYTHON_OPERATORS,
    "python_membership_tests": PYTHON_MEMBERSHIP_TESTS,
    "python_chained_comparisons": PYTHON_CHAINED_COMPARISONS,
    "python_ternary_expressions": PYTHON_TERNARY_EXPRESSIONS,
    "python_walrus_operators": PYTHON_WALRUS_OPERATORS,
    "python_matrix_multiplication": PYTHON_MATRIX_MULTIPLICATION,
    # Python Coverage V2 (Week 3 - Collections)
    "python_dict_operations": PYTHON_DICT_OPERATIONS,
    "python_list_mutations": PYTHON_LIST_MUTATIONS,
    "python_set_operations": PYTHON_SET_OPERATIONS,
    "python_string_methods": PYTHON_STRING_METHODS,
    "python_builtin_usage": PYTHON_BUILTIN_USAGE,
    "python_itertools_usage": PYTHON_ITERTOOLS_USAGE,
    "python_functools_usage": PYTHON_FUNCTOOLS_USAGE,
    "python_collections_usage": PYTHON_COLLECTIONS_USAGE,
    # Python Coverage V2 (Week 4 - Advanced Class Features)
    "python_metaclasses": PYTHON_METACLASSES,
    "python_descriptors": PYTHON_DESCRIPTORS,
    "python_dataclasses": PYTHON_DATACLASSES,
    "python_enums": PYTHON_ENUMS,
    "python_slots": PYTHON_SLOTS,
    "python_abstract_classes": PYTHON_ABSTRACT_CLASSES,
    "python_method_types": PYTHON_METHOD_TYPES,
    "python_multiple_inheritance": PYTHON_MULTIPLE_INHERITANCE,
    "python_dunder_methods": PYTHON_DUNDER_METHODS,
    "python_visibility_conventions": PYTHON_VISIBILITY_CONVENTIONS,
    # Python Coverage V2 (Week 4 - Stdlib Patterns)
    "python_regex_patterns": PYTHON_REGEX_PATTERNS,
    "python_json_operations": PYTHON_JSON_OPERATIONS,
    "python_datetime_operations": PYTHON_DATETIME_OPERATIONS,
    "python_path_operations": PYTHON_PATH_OPERATIONS,
    "python_logging_patterns": PYTHON_LOGGING_PATTERNS,
    "python_threading_patterns": PYTHON_THREADING_PATTERNS,
    "python_contextlib_patterns": PYTHON_CONTEXTLIB_PATTERNS,
    "python_type_checking": PYTHON_TYPE_CHECKING,
    # Python Coverage V2 (Week 5 - Control Flow)
    "python_for_loops": PYTHON_FOR_LOOPS,
    "python_while_loops": PYTHON_WHILE_LOOPS,
    "python_async_for_loops": PYTHON_ASYNC_FOR_LOOPS,
    "python_if_statements": PYTHON_IF_STATEMENTS,
    "python_match_statements": PYTHON_MATCH_STATEMENTS,
    "python_break_continue_pass": PYTHON_BREAK_CONTINUE_PASS,
    "python_assert_statements": PYTHON_ASSERT_STATEMENTS,
    "python_del_statements": PYTHON_DEL_STATEMENTS,
    "python_import_statements": PYTHON_IMPORT_STATEMENTS,
    "python_with_statements": PYTHON_WITH_STATEMENTS,
    # Python Coverage V2 (Week 6 - Protocol Patterns)
    "python_iterator_protocol": PYTHON_ITERATOR_PROTOCOL,
    "python_container_protocol": PYTHON_CONTAINER_PROTOCOL,
    "python_callable_protocol": PYTHON_CALLABLE_PROTOCOL,
    "python_comparison_protocol": PYTHON_COMPARISON_PROTOCOL,
    "python_arithmetic_protocol": PYTHON_ARITHMETIC_PROTOCOL,
    "python_pickle_protocol": PYTHON_PICKLE_PROTOCOL,
    "python_weakref_usage": PYTHON_WEAKREF_USAGE,
    "python_contextvar_usage": PYTHON_CONTEXTVAR_USAGE,
    "python_module_attributes": PYTHON_MODULE_ATTRIBUTES,
    "python_class_decorators": PYTHON_CLASS_DECORATORS,
    # Python Coverage V2 (Advanced - Rarely Used Patterns)
    "python_namespace_packages": PYTHON_NAMESPACE_PACKAGES,
    "python_cached_property": PYTHON_CACHED_PROPERTY,
    "python_descriptor_protocol": PYTHON_DESCRIPTOR_PROTOCOL,
    "python_attribute_access_protocol": PYTHON_ATTRIBUTE_ACCESS_PROTOCOL,
    "python_copy_protocol": PYTHON_COPY_PROTOCOL,
    "python_ellipsis_usage": PYTHON_ELLIPSIS_USAGE,
    "python_bytes_operations": PYTHON_BYTES_OPERATIONS,
    "python_exec_eval_compile": PYTHON_EXEC_EVAL_COMPILE,
}
