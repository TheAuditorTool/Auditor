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
# PYTHON TABLES REGISTRY
# ============================================================================

PYTHON_TABLES: Dict[str, TableSchema] = {
    # Basic Python (Phase 1)
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,
    "python_routes": PYTHON_ROUTES,
    "python_blueprints": PYTHON_BLUEPRINTS,
    "python_validators": PYTHON_VALIDATORS,

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
}
