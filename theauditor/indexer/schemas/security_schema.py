"""Security-focused schema definitions - Cross-language security patterns."""

from .utils import Column, ForeignKey, TableSchema

ENV_VAR_USAGE = TableSchema(
    name="env_var_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("var_name", "TEXT", nullable=False),
        Column("access_type", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=True),
        Column("property_access", "TEXT", nullable=True),
    ],
    primary_key=[
        "file",
        "line",
        "var_name",
        "access_type",
    ],  # Include access_type: same var can have multiple access types per line
    indexes=[
        ("idx_env_var_usage_file", ["file"]),
        ("idx_env_var_usage_name", ["var_name"]),
        ("idx_env_var_usage_type", ["access_type"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


SQL_OBJECTS = TableSchema(
    name="sql_objects",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("kind", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_sql_file", ["file"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file"], foreign_table="files", foreign_columns=["path"]),
    ],
)

SQL_QUERIES = TableSchema(
    name="sql_queries",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line_number", "INTEGER", nullable=False),
        Column("query_text", "TEXT", nullable=False),
        Column("command", "TEXT", nullable=False, check="command != 'UNKNOWN'"),
        Column("extraction_source", "TEXT", nullable=False, default="'code_execute'"),
    ],
    primary_key=["file_path", "line_number"],
    indexes=[
        ("idx_sql_queries_file", ["file_path"]),
        ("idx_sql_queries_command", ["command"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)


SQL_QUERY_TABLES = TableSchema(
    name="sql_query_tables",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("query_file", "TEXT", nullable=False),
        Column("query_line", "INTEGER", nullable=False),
        Column("table_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_sql_query_tables_query", ["query_file", "query_line"]),
        ("idx_sql_query_tables_table", ["table_name"]),
        ("idx_sql_query_tables_file", ["query_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["query_file", "query_line"],
            foreign_table="sql_queries",
            foreign_columns=["file_path", "line_number"],
        ),
        ForeignKey(local_columns=["query_file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


JWT_PATTERNS = TableSchema(
    name="jwt_patterns",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line_number", "INTEGER", nullable=False),
        Column("pattern_type", "TEXT", nullable=False),
        Column("pattern_text", "TEXT"),
        Column("secret_source", "TEXT"),
        Column("algorithm", "TEXT"),
    ],
    indexes=[
        ("idx_jwt_file", ["file_path"]),
        ("idx_jwt_type", ["pattern_type"]),
        ("idx_jwt_secret_source", ["secret_source"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["file_path"], foreign_table="files", foreign_columns=["path"]),
    ],
)


TAINT_FLOWS = TableSchema(
    name="taint_flows",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("source_file", "TEXT", nullable=False),
        Column("source_line", "INTEGER", nullable=False),
        Column("source_pattern", "TEXT", nullable=False),
        Column("sink_file", "TEXT", nullable=False),
        Column("sink_line", "INTEGER", nullable=False),
        Column("sink_pattern", "TEXT", nullable=False),
        Column("vulnerability_type", "TEXT", nullable=False),
        Column("path_length", "INTEGER", nullable=False),
        Column("hops", "INTEGER", nullable=False),
        Column("path_json", "TEXT", nullable=False),
        Column("flow_sensitive", "INTEGER", nullable=False, default="1"),
    ],
    indexes=[
        ("idx_taint_flows_source", ["source_file", "source_line"]),
        ("idx_taint_flows_sink", ["sink_file", "sink_line"]),
        ("idx_taint_flows_type", ["vulnerability_type"]),
        ("idx_taint_flows_length", ["path_length"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["source_file"], foreign_table="files", foreign_columns=["path"]),
        ForeignKey(local_columns=["sink_file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


RESOLVED_FLOW_AUDIT = TableSchema(
    name="resolved_flow_audit",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("source_file", "TEXT", nullable=False),
        Column("source_line", "INTEGER", nullable=False),
        Column("source_pattern", "TEXT", nullable=False),
        Column("sink_file", "TEXT", nullable=False),
        Column("sink_line", "INTEGER", nullable=False),
        Column("sink_pattern", "TEXT", nullable=False),
        Column("vulnerability_type", "TEXT", nullable=False),
        Column("path_length", "INTEGER", nullable=False),
        Column("hops", "INTEGER", nullable=False),
        Column("path_json", "TEXT", nullable=False),
        Column("flow_sensitive", "INTEGER", nullable=False, default="1"),
        Column(
            "status",
            "TEXT",
            nullable=False,
            check="status IN ('VULNERABLE', 'SANITIZED', 'REACHABLE')",
        ),
        Column("sanitizer_file", "TEXT", nullable=True),
        Column("sanitizer_line", "INTEGER", nullable=True),
        Column("sanitizer_method", "TEXT", nullable=True),
        Column(
            "engine",
            "TEXT",
            nullable=False,
            default="'IFDS'",
            check="engine IN ('FlowResolver', 'IFDS')",
        ),
    ],
    indexes=[
        ("idx_resolved_flow_source", ["source_file", "source_line"]),
        ("idx_resolved_flow_sink", ["sink_file", "sink_line"]),
        ("idx_resolved_flow_type", ["vulnerability_type"]),
        ("idx_resolved_flow_length", ["path_length"]),
        ("idx_resolved_flow_status", ["status"]),
        ("idx_resolved_flow_sanitizer", ["sanitizer_file", "sanitizer_line"]),
        ("idx_resolved_flow_sanitizer_method", ["sanitizer_method"]),
        ("idx_resolved_flow_engine", ["engine"]),
    ],
    foreign_keys=[
        ForeignKey(local_columns=["source_file"], foreign_table="files", foreign_columns=["path"]),
        ForeignKey(local_columns=["sink_file"], foreign_table="files", foreign_columns=["path"]),
    ],
)


SECURITY_TABLES: dict[str, TableSchema] = {
    "env_var_usage": ENV_VAR_USAGE,
    "sql_objects": SQL_OBJECTS,
    "sql_queries": SQL_QUERIES,
    "sql_query_tables": SQL_QUERY_TABLES,
    "jwt_patterns": JWT_PATTERNS,
    "taint_flows": TAINT_FLOWS,
    "resolved_flow_audit": RESOLVED_FLOW_AUDIT,
}
