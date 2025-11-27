"""
Framework-focused schema definitions - Cross-language framework patterns.

This module contains table schemas for web framework patterns:
- ORM relationships (SQLAlchemy, Django, Sequelize, TypeORM, Diesel)
- API routing (Flask, FastAPI, Django, Express, NestJS)
- ORM query patterns (cross-language ORM analysis)

Design Philosophy:
- Language-agnostic framework patterns (Python, Node, future Rust)
- Used by framework-specific security rules
- Focused on ORM and API routing vulnerabilities

These tables are populated by multiple extractors:
- ORM_RELATIONSHIPS: Python extractor (SQLAlchemy/Django), Node extractor (Sequelize/TypeORM)
- API_ENDPOINTS/CONTROLS: Python extractor (Flask/FastAPI/Django), Node extractor (Express/NestJS)
- ORM_QUERIES: Python extractor, Node extractor
- PRISMA_MODELS: Node extractor (Prisma)
"""

from .utils import Column, ForeignKey, TableSchema

ORM_RELATIONSHIPS = TableSchema(
    name="orm_relationships",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("source_model", "TEXT", nullable=False),
        Column("target_model", "TEXT", nullable=False),
        Column("relationship_type", "TEXT", nullable=False),
        Column("foreign_key", "TEXT", nullable=True),
        Column("cascade_delete", "BOOLEAN", default="0"),
        Column("as_name", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "source_model", "target_model"],
    indexes=[
        ("idx_orm_relationships_file", ["file"]),
        ("idx_orm_relationships_source", ["source_model"]),
        ("idx_orm_relationships_target", ["target_model"]),
        ("idx_orm_relationships_type", ["relationship_type"]),
    ],
)

ORM_QUERIES = TableSchema(
    name="orm_queries",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("query_type", "TEXT", nullable=False),
        Column("includes", "TEXT"),
        Column("has_limit", "BOOLEAN", default="0"),
        Column("has_transaction", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_orm_queries_file", ["file"]),
        ("idx_orm_queries_type", ["query_type"]),
    ],
)

PRISMA_MODELS = TableSchema(
    name="prisma_models",
    columns=[
        Column("model_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),
        Column("is_indexed", "BOOLEAN", default="0"),
        Column("is_unique", "BOOLEAN", default="0"),
        Column("is_relation", "BOOLEAN", default="0"),
    ],
    primary_key=["model_name", "field_name"],
    indexes=[
        ("idx_prisma_models_indexed", ["is_indexed"]),
    ],
)


API_ENDPOINTS = TableSchema(
    name="api_endpoints",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER"),
        Column("method", "TEXT", nullable=False),
        Column("pattern", "TEXT", nullable=False),
        Column("path", "TEXT"),
        Column("full_path", "TEXT"),
        Column("has_auth", "BOOLEAN", default="0"),
        Column("handler_function", "TEXT"),
    ],
    indexes=[
        ("idx_api_endpoints_file", ["file"]),
    ],
)


API_ENDPOINT_CONTROLS = TableSchema(
    name="api_endpoint_controls",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("endpoint_file", "TEXT", nullable=False),
        Column("endpoint_line", "INTEGER", nullable=False),
        Column("control_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_api_endpoint_controls_endpoint", ["endpoint_file", "endpoint_line"]),
        ("idx_api_endpoint_controls_control", ["control_name"]),
        ("idx_api_endpoint_controls_file", ["endpoint_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["endpoint_file", "endpoint_line"],
            foreign_table="api_endpoints",
            foreign_columns=["file", "line"],
        )
    ],
)


ROUTER_MOUNTS = TableSchema(
    name="router_mounts",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("mount_path_expr", "TEXT", nullable=False),
        Column("router_variable", "TEXT", nullable=False),
        Column("is_literal", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_router_mounts_file", ["file"]),
        ("idx_router_mounts_router_var", ["router_variable"]),
    ],
)


FRAMEWORKS_TABLES: dict[str, TableSchema] = {
    "orm_relationships": ORM_RELATIONSHIPS,
    "orm_queries": ORM_QUERIES,
    "prisma_models": PRISMA_MODELS,
    "api_endpoints": API_ENDPOINTS,
    "api_endpoint_controls": API_ENDPOINT_CONTROLS,
    "router_mounts": ROUTER_MOUNTS,
}
