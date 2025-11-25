"""
Python-specific schema definitions.

This module contains table schemas specific to Python frameworks and patterns:
- ORM models (SQLAlchemy, Django)
- HTTP routes (Flask, FastAPI, Django)
- Validation patterns (Pydantic)
- Decorators

Design Philosophy:
- Python-only tables
- Framework-specific extractions
- Complements core schema with language-specific patterns

CONSOLIDATION NOTE (2025-11-25):
This file was reduced from 149 tables to 8 tables. 141 orphan tables
(tables with zero consumers - no SELECT queries in rules, commands,
taint, or context code) were deleted. See openspec change
'consolidate-python-orphan-tables' for full rationale and verification.
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
# PYTHON TABLES REGISTRY (8 tables with verified consumers)
# ============================================================================

PYTHON_TABLES: Dict[str, TableSchema] = {
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
}
