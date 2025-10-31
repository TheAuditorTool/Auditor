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
}
