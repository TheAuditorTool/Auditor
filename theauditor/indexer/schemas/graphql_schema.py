"""GraphQL schema definitions - GraphQL schema, types, fields, and resolver mappings."""

from .utils import Column, ForeignKey, TableSchema

GRAPHQL_SCHEMAS = TableSchema(
    name="graphql_schemas",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("schema_hash", "TEXT", nullable=False),
        Column("language", "TEXT", nullable=False),
        Column("last_modified", "INTEGER", nullable=True),
    ],
    indexes=[
        ("idx_graphql_schemas_hash", ["schema_hash"]),
        ("idx_graphql_schemas_language", ["language"]),
    ],
)


GRAPHQL_TYPES = TableSchema(
    name="graphql_types",
    columns=[
        Column("type_id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("schema_path", "TEXT", nullable=False),
        Column("type_name", "TEXT", nullable=False),
        Column("kind", "TEXT", nullable=False),
        Column("implements", "TEXT", nullable=True),
        Column("description", "TEXT", nullable=True),
        Column("line", "INTEGER", nullable=True),
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
            foreign_columns=["file_path"],
        )
    ],
)


GRAPHQL_FIELDS = TableSchema(
    name="graphql_fields",
    columns=[
        Column("field_id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("type_id", "INTEGER", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("return_type", "TEXT", nullable=False),
        Column("is_list", "BOOLEAN", default="0"),
        Column("is_nullable", "BOOLEAN", default="1"),
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
            local_columns=["type_id"], foreign_table="graphql_types", foreign_columns=["type_id"]
        )
    ],
)


GRAPHQL_FIELD_ARGS = TableSchema(
    name="graphql_field_args",
    columns=[
        Column("field_id", "INTEGER", nullable=False),
        Column("arg_name", "TEXT", nullable=False),
        Column("arg_type", "TEXT", nullable=False),
        Column("has_default", "BOOLEAN", default="0"),
        Column("default_value", "TEXT", nullable=True),
        Column("is_nullable", "BOOLEAN", default="1"),
    ],
    primary_key=["field_id", "arg_name"],
    indexes=[
        ("idx_graphql_field_args_field", ["field_id"]),
        ("idx_graphql_field_args_type", ["arg_type"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["field_id"], foreign_table="graphql_fields", foreign_columns=["field_id"]
        )
    ],
)


GRAPHQL_FIELD_DIRECTIVES = TableSchema(
    name="graphql_field_directives",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("field_id", "INTEGER", nullable=False),
        Column("directive_name", "TEXT", nullable=False),
        Column("arguments_json", "TEXT"),
    ],
    indexes=[
        ("idx_graphql_field_directives_field", ["field_id"]),
        ("idx_graphql_field_directives_name", ["directive_name"]),
    ],
    unique_constraints=[["field_id", "directive_name"]],
    foreign_keys=[
        ForeignKey(
            local_columns=["field_id"],
            foreign_table="graphql_fields",
            foreign_columns=["field_id"],
        )
    ],
)

GRAPHQL_ARG_DIRECTIVES = TableSchema(
    name="graphql_arg_directives",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("field_id", "INTEGER", nullable=False),
        Column("arg_name", "TEXT", nullable=False),
        Column("directive_name", "TEXT", nullable=False),
        Column("arguments_json", "TEXT"),
    ],
    indexes=[
        ("idx_graphql_arg_directives_fk", ["field_id", "arg_name"]),
        ("idx_graphql_arg_directives_name", ["directive_name"]),
    ],
    unique_constraints=[["field_id", "arg_name", "directive_name"]],
    foreign_keys=[
        ForeignKey(
            local_columns=["field_id", "arg_name"],
            foreign_table="graphql_field_args",
            foreign_columns=["field_id", "arg_name"],
        )
    ],
)


GRAPHQL_RESOLVER_MAPPINGS = TableSchema(
    name="graphql_resolver_mappings",
    columns=[
        Column("field_id", "INTEGER", nullable=False),
        Column("resolver_symbol_id", "INTEGER", nullable=False),
        Column("resolver_path", "TEXT", nullable=False),
        Column("resolver_line", "INTEGER", nullable=False),
        Column("resolver_language", "TEXT", nullable=False),
        Column("resolver_export", "TEXT", nullable=True),
        Column("binding_style", "TEXT", nullable=False),
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
            local_columns=["field_id"], foreign_table="graphql_fields", foreign_columns=["field_id"]
        )
    ],
)


GRAPHQL_RESOLVER_PARAMS = TableSchema(
    name="graphql_resolver_params",
    columns=[
        Column("resolver_symbol_id", "INTEGER", nullable=False),
        Column("arg_name", "TEXT", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("is_kwargs", "BOOLEAN", default="0"),
        Column("is_list_input", "BOOLEAN", default="0"),
    ],
    primary_key=["resolver_symbol_id", "arg_name"],
    indexes=[
        ("idx_graphql_resolver_params_symbol", ["resolver_symbol_id"]),
        ("idx_graphql_resolver_params_arg", ["arg_name"]),
        ("idx_graphql_resolver_params_param", ["param_name"]),
    ],
)


GRAPHQL_EXECUTION_EDGES = TableSchema(
    name="graphql_execution_edges",
    columns=[
        Column("from_field_id", "INTEGER", nullable=False),
        Column("to_symbol_id", "INTEGER", nullable=False),
        Column("edge_kind", "TEXT", nullable=False),
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
            foreign_columns=["field_id"],
        )
    ],
)


GRAPHQL_FINDINGS_CACHE = TableSchema(
    name="graphql_findings_cache",
    columns=[
        Column("finding_id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("field_id", "INTEGER", nullable=True),
        Column("resolver_symbol_id", "INTEGER", nullable=True),
        Column("rule", "TEXT", nullable=False),
        Column("severity", "TEXT", nullable=False),
        Column("description", "TEXT"),
        Column("message", "TEXT"),
        Column("confidence", "TEXT", default="'medium'"),
        Column("provenance", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_graphql_findings_cache_field", ["field_id"]),
        ("idx_graphql_findings_cache_symbol", ["resolver_symbol_id"]),
        ("idx_graphql_findings_cache_rule", ["rule"]),
        ("idx_graphql_findings_cache_severity", ["severity"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["field_id"], foreign_table="graphql_fields", foreign_columns=["field_id"]
        )
    ],
)


GRAPHQL_TABLES: dict[str, TableSchema] = {
    "graphql_schemas": GRAPHQL_SCHEMAS,
    "graphql_types": GRAPHQL_TYPES,
    "graphql_fields": GRAPHQL_FIELDS,
    "graphql_field_directives": GRAPHQL_FIELD_DIRECTIVES,
    "graphql_field_args": GRAPHQL_FIELD_ARGS,
    "graphql_arg_directives": GRAPHQL_ARG_DIRECTIVES,
    "graphql_resolver_mappings": GRAPHQL_RESOLVER_MAPPINGS,
    "graphql_resolver_params": GRAPHQL_RESOLVER_PARAMS,
    "graphql_execution_edges": GRAPHQL_EXECUTION_EDGES,
    "graphql_findings_cache": GRAPHQL_FINDINGS_CACHE,
}
