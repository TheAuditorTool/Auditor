"""
GraphQL schema definitions - GraphQL schema, types, fields, and resolver mappings.

This module contains table schemas for GraphQL analysis:
- Schema files and fingerprints (SDL and code-first)
- Type definitions, fields, and arguments
- Resolver mappings from GraphQL fields to backend symbols
- Execution graph edges for taint and security analysis
- Findings cache for FCE integration

Design Philosophy:
- Language-agnostic GraphQL patterns (JavaScript, TypeScript, Python)
- Bridges GraphQL schema layer to backend implementation
- Enables deterministic taint flows and auth verification
- Integrates with existing symbols table via resolver_symbol_id foreign keys

These tables are populated by:
- GraphQL extractor (.graphql/.gql/.graphqls SDL parsing)
- JavaScript extractor (Apollo, NestJS, TypeGraphQL resolver detection)
- Python extractor (Graphene, Ariadne, Strawberry resolver detection)
- GraphQL build command (execution graph construction)
"""

from typing import Dict
from .utils import Column, TableSchema, ForeignKey


# ============================================================================
# GRAPHQL SCHEMA TRACKING - Schema files and fingerprints
# ============================================================================

GRAPHQL_SCHEMAS = TableSchema(
    name="graphql_schemas",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("schema_hash", "TEXT", nullable=False),
        Column("language", "TEXT", nullable=False),  # 'sdl' or 'code-first'
        Column("last_modified", "INTEGER", nullable=True),  # Unix timestamp
    ],
    indexes=[
        ("idx_graphql_schemas_hash", ["schema_hash"]),
        ("idx_graphql_schemas_language", ["language"]),
    ]
)


# ============================================================================
# GRAPHQL TYPE SYSTEM - Types, interfaces, inputs, enums
# ============================================================================

GRAPHQL_TYPES = TableSchema(
    name="graphql_types",
    columns=[
        Column("type_id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("schema_path", "TEXT", nullable=False),  # FK to graphql_schemas.file_path
        Column("type_name", "TEXT", nullable=False),
        Column("kind", "TEXT", nullable=False),  # 'object', 'interface', 'input', 'enum', 'union', 'scalar'
        Column("implements", "TEXT", nullable=True),  # JSON array of interface names
        Column("description", "TEXT", nullable=True),
        Column("line", "INTEGER", nullable=True),  # Line number in schema file
    ],
    indexes=[
        ("idx_graphql_types_schema", ["schema_path"]),
        ("idx_graphql_types_name", ["type_name"]),
        ("idx_graphql_types_kind", ["kind"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["schema_path"],
            foreign_table="graphql_schemas",
            foreign_columns=["file_path"]
        )
    ]
)


# ============================================================================
# GRAPHQL FIELDS - Field definitions per type
# ============================================================================

GRAPHQL_FIELDS = TableSchema(
    name="graphql_fields",
    columns=[
        Column("field_id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("type_id", "INTEGER", nullable=False),  # FK to graphql_types.type_id
        Column("field_name", "TEXT", nullable=False),
        Column("return_type", "TEXT", nullable=False),  # GraphQL type (e.g., 'User', 'String!', '[Post]')
        Column("is_list", "BOOLEAN", default="0"),
        Column("is_nullable", "BOOLEAN", default="1"),
        Column("directives_json", "TEXT", nullable=True),  # JSON array of directive objects
        Column("line", "INTEGER", nullable=True),
        Column("column", "INTEGER", nullable=True),
    ],
    indexes=[
        ("idx_graphql_fields_type", ["type_id"]),
        ("idx_graphql_fields_name", ["field_name"]),
        ("idx_graphql_fields_return", ["return_type"]),
        ("idx_graphql_fields_list", ["is_list"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["type_id"],
            foreign_table="graphql_types",
            foreign_columns=["type_id"]
        )
    ]
)


# ============================================================================
# GRAPHQL FIELD ARGUMENTS - Argument definitions per field
# ============================================================================

GRAPHQL_FIELD_ARGS = TableSchema(
    name="graphql_field_args",
    columns=[
        Column("field_id", "INTEGER", nullable=False),  # FK to graphql_fields.field_id
        Column("arg_name", "TEXT", nullable=False),
        Column("arg_type", "TEXT", nullable=False),  # GraphQL type (e.g., 'ID!', 'String', '[Int]')
        Column("has_default", "BOOLEAN", default="0"),
        Column("default_value", "TEXT", nullable=True),
        Column("is_nullable", "BOOLEAN", default="1"),
        Column("directives_json", "TEXT", nullable=True),  # JSON array of directive objects
    ],
    primary_key=["field_id", "arg_name"],
    indexes=[
        ("idx_graphql_field_args_field", ["field_id"]),
        ("idx_graphql_field_args_type", ["arg_type"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["field_id"],
            foreign_table="graphql_fields",
            foreign_columns=["field_id"]
        )
    ]
)


# ============================================================================
# GRAPHQL RESOLVER MAPPINGS - Bridge fields to backend symbols
# ============================================================================

GRAPHQL_RESOLVER_MAPPINGS = TableSchema(
    name="graphql_resolver_mappings",
    columns=[
        Column("field_id", "INTEGER", nullable=False),  # FK to graphql_fields.field_id
        Column("resolver_symbol_id", "INTEGER", nullable=False),  # FK to symbols.symbol_id
        Column("resolver_path", "TEXT", nullable=False),
        Column("resolver_line", "INTEGER", nullable=False),
        Column("resolver_language", "TEXT", nullable=False),  # 'javascript', 'typescript', 'python'
        Column("resolver_export", "TEXT", nullable=True),  # Export name for tracing
        Column("binding_style", "TEXT", nullable=False),  # 'apollo-object', 'apollo-class', 'nestjs-decorator', 'graphene-decorator', etc.
    ],
    primary_key=["field_id", "resolver_symbol_id"],
    indexes=[
        ("idx_graphql_resolver_mappings_field", ["field_id"]),
        ("idx_graphql_resolver_mappings_symbol", ["resolver_symbol_id"]),
        ("idx_graphql_resolver_mappings_path", ["resolver_path"]),
        ("idx_graphql_resolver_mappings_style", ["binding_style"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["field_id"],
            foreign_table="graphql_fields",
            foreign_columns=["field_id"]
        )
    ]
)


# ============================================================================
# GRAPHQL RESOLVER PARAMS - Map GraphQL args to function params
# ============================================================================

GRAPHQL_RESOLVER_PARAMS = TableSchema(
    name="graphql_resolver_params",
    columns=[
        Column("resolver_symbol_id", "INTEGER", nullable=False),  # FK to symbols.symbol_id
        Column("arg_name", "TEXT", nullable=False),  # GraphQL argument name
        Column("param_name", "TEXT", nullable=False),  # Function parameter name
        Column("param_index", "INTEGER", nullable=False),  # Parameter position (0-indexed)
        Column("is_kwargs", "BOOLEAN", default="0"),  # Python **kwargs or JS destructured args
        Column("is_list_input", "BOOLEAN", default="0"),  # Parameter expects list input
    ],
    primary_key=["resolver_symbol_id", "arg_name"],
    indexes=[
        ("idx_graphql_resolver_params_symbol", ["resolver_symbol_id"]),
        ("idx_graphql_resolver_params_arg", ["arg_name"]),
        ("idx_graphql_resolver_params_param", ["param_name"]),
    ]
)


# ============================================================================
# GRAPHQL EXECUTION EDGES - Resolver execution graph
# ============================================================================

GRAPHQL_EXECUTION_EDGES = TableSchema(
    name="graphql_execution_edges",
    columns=[
        Column("from_field_id", "INTEGER", nullable=False),  # FK to graphql_fields.field_id
        Column("to_symbol_id", "INTEGER", nullable=False),  # FK to symbols.symbol_id
        Column("edge_kind", "TEXT", nullable=False),  # 'resolver' or 'downstream_call'
    ],
    primary_key=["from_field_id", "to_symbol_id", "edge_kind"],
    indexes=[
        ("idx_graphql_execution_edges_from", ["from_field_id"]),
        ("idx_graphql_execution_edges_to", ["to_symbol_id"]),
        ("idx_graphql_execution_edges_kind", ["edge_kind"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["from_field_id"],
            foreign_table="graphql_fields",
            foreign_columns=["field_id"]
        )
    ]
)


# ============================================================================
# GRAPHQL FINDINGS CACHE - FCE fast path cache
# ============================================================================

GRAPHQL_FINDINGS_CACHE = TableSchema(
    name="graphql_findings_cache",
    columns=[
        Column("finding_id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("field_id", "INTEGER", nullable=True),  # FK to graphql_fields.field_id (nullable for schema-level findings)
        Column("resolver_symbol_id", "INTEGER", nullable=True),  # FK to symbols.symbol_id
        Column("rule", "TEXT", nullable=False),
        Column("severity", "TEXT", nullable=False),  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
        Column("details_json", "TEXT", nullable=False),  # JSON object with finding details
        Column("provenance", "TEXT", nullable=False),  # Source of finding (rule name + version)
    ],
    indexes=[
        ("idx_graphql_findings_cache_field", ["field_id"]),
        ("idx_graphql_findings_cache_symbol", ["resolver_symbol_id"]),
        ("idx_graphql_findings_cache_rule", ["rule"]),
        ("idx_graphql_findings_cache_severity", ["severity"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["field_id"],
            foreign_table="graphql_fields",
            foreign_columns=["field_id"]
        )
    ]
)


# ============================================================================
# GRAPHQL TABLES REGISTRY
# ============================================================================

GRAPHQL_TABLES: dict[str, TableSchema] = {
    "graphql_schemas": GRAPHQL_SCHEMAS,
    "graphql_types": GRAPHQL_TYPES,
    "graphql_fields": GRAPHQL_FIELDS,
    "graphql_field_args": GRAPHQL_FIELD_ARGS,
    "graphql_resolver_mappings": GRAPHQL_RESOLVER_MAPPINGS,
    "graphql_resolver_params": GRAPHQL_RESOLVER_PARAMS,
    "graphql_execution_edges": GRAPHQL_EXECUTION_EDGES,
    "graphql_findings_cache": GRAPHQL_FINDINGS_CACHE,
}
