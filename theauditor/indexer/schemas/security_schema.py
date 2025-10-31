"""
Security-focused schema definitions - Cross-language security patterns.

This module contains table schemas for security analysis patterns:
- Environment variable usage (secrets detection)
- SQL query tracking (SQL injection detection)
- JWT token patterns (authentication security)

Design Philosophy:
- Language-agnostic security patterns (Python, Node, shell scripts)
- Used by security rules and taint analysis
- Focused on vulnerability detection (SQL injection, hardcoded secrets, JWT misuse)

These tables are populated by multiple extractors:
- ENV_VAR_USAGE: Python extractor (process.env), Node extractor (os.environ), shell scripts
- SQL_QUERIES/SQL_QUERY_TABLES: Python extractor, Node extractor, raw SQL files
- JWT_PATTERNS: Python extractor, Node extractor
"""

from typing import Dict
from .utils import Column, TableSchema, ForeignKey


# ============================================================================
# ENVIRONMENT VARIABLE ACCESS - Secrets detection
# ============================================================================

ENV_VAR_USAGE = TableSchema(
    name="env_var_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("var_name", "TEXT", nullable=False),        # "NODE_ENV", "DATABASE_URL"
        Column("access_type", "TEXT", nullable=False),     # "read", "write", "check"
        Column("in_function", "TEXT", nullable=True),      # Function containing this access
        Column("property_access", "TEXT", nullable=True),  # Full expression: "process.env.NODE_ENV"
    ],
    primary_key=["file", "line", "var_name"],
    indexes=[
        ("idx_env_var_usage_file", ["file"]),
        ("idx_env_var_usage_name", ["var_name"]),
        ("idx_env_var_usage_type", ["access_type"]),
    ]
)

# ============================================================================
# SQL QUERY TRACKING - SQL injection detection
# ============================================================================

SQL_OBJECTS = TableSchema(
    name="sql_objects",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("kind", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_sql_file", ["file"]),
    ]
)

SQL_QUERIES = TableSchema(
    name="sql_queries",
    columns=[
        Column("file_path", "TEXT", nullable=False),  # NOTE: file_path not file
        Column("line_number", "INTEGER", nullable=False),  # NOTE: line_number not line
        Column("query_text", "TEXT", nullable=False),
        Column("command", "TEXT", nullable=False, check="command != 'UNKNOWN'"),
        # tables REMOVED - see sql_query_tables junction table
        Column("extraction_source", "TEXT", nullable=False, default="'code_execute'"),
    ],
    indexes=[
        ("idx_sql_queries_file", ["file_path"]),
        ("idx_sql_queries_command", ["command"]),
    ]
)

# Junction table for normalized SQL query table references
# Replaces JSON TEXT column sql_queries.tables with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
SQL_QUERY_TABLES = TableSchema(
    name="sql_query_tables",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("query_file", "TEXT", nullable=False),
        Column("query_line", "INTEGER", nullable=False),
        Column("table_name", "TEXT", nullable=False),  # 1 row per table referenced
    ],
    indexes=[
        ("idx_sql_query_tables_query", ["query_file", "query_line"]),  # FK composite lookup
        ("idx_sql_query_tables_table", ["table_name"]),  # Fast search by table name
        ("idx_sql_query_tables_file", ["query_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["query_file", "query_line"],
            foreign_table="sql_queries",
            foreign_columns=["file_path", "line_number"]
        )
    ]
)

# ============================================================================
# JWT TOKEN PATTERNS - Authentication security
# ============================================================================

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
    ]
)

# ============================================================================
# SECURITY TABLES REGISTRY
# ============================================================================

SECURITY_TABLES: Dict[str, TableSchema] = {
    "env_var_usage": ENV_VAR_USAGE,
    "sql_objects": SQL_OBJECTS,
    "sql_queries": SQL_QUERIES,
    "sql_query_tables": SQL_QUERY_TABLES,
    "jwt_patterns": JWT_PATTERNS,
}
