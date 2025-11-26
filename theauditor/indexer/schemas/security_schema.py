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
    primary_key=["file", "line", "var_name", "access_type"],  # Include access_type: same var can have multiple access types per line
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
# TAINT FLOWS - Resolved taint analysis paths (LEGACY - use resolved_flow_audit)
# ============================================================================

TAINT_FLOWS = TableSchema(
    name="taint_flows",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),
        Column("source_file", "TEXT", nullable=False),
        Column("source_line", "INTEGER", nullable=False),
        Column("source_pattern", "TEXT", nullable=False),  # e.g., "req.body"
        Column("sink_file", "TEXT", nullable=False),
        Column("sink_line", "INTEGER", nullable=False),
        Column("sink_pattern", "TEXT", nullable=False),  # e.g., "execute"
        Column("vulnerability_type", "TEXT", nullable=False),  # "sql_injection", "xss", etc.
        Column("path_length", "INTEGER", nullable=False),  # Number of hops
        Column("hops", "INTEGER", nullable=False),  # Same as path_length for compatibility
        Column("path_json", "TEXT", nullable=False),  # JSON array of hop chain
        Column("flow_sensitive", "INTEGER", nullable=False, default="1"),  # Boolean: CFG-aware
    ],
    indexes=[
        ("idx_taint_flows_source", ["source_file", "source_line"]),
        ("idx_taint_flows_sink", ["sink_file", "sink_line"]),
        ("idx_taint_flows_type", ["vulnerability_type"]),
        ("idx_taint_flows_length", ["path_length"]),
    ]
)

# ============================================================================
# RESOLVED FLOW AUDIT - Full taint analysis provenance (ALL paths)
# ============================================================================
# Stores BOTH vulnerable AND sanitized paths with complete metadata.
# This table provides the full audit trail of what the analyzer found,
# enabling downstream consumers (AI, Rules Engine) to learn from both
# positive (sanitized) and negative (vulnerable) examples.
#
# Design rationale (Phase 6):
# - The analyzer finds 10,787 total paths but only 7 are vulnerable
# - The 10,705 sanitized paths are proof that security controls work
# - Discarding them creates a "black box" with no learning signal
# - This table closes the provenance gap
#
# Query examples:
#   -- All paths blocked by specific sanitizer:
#   SELECT * FROM resolved_flow_audit
#   WHERE status = 'SANITIZED' AND sanitizer_file = 'middleware/validate.ts'
#
#   -- Sanitizer effectiveness ranking:
#   SELECT sanitizer_file, sanitizer_line, sanitizer_method, COUNT(*) as blocked_count
#   FROM resolved_flow_audit WHERE status = 'SANITIZED'
#   GROUP BY 1, 2, 3 ORDER BY blocked_count DESC
#
#   -- Only vulnerable paths (same as old taint_flows):
#   SELECT * FROM resolved_flow_audit WHERE status = 'VULNERABLE'

RESOLVED_FLOW_AUDIT = TableSchema(
    name="resolved_flow_audit",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True, autoincrement=True),

        # Source location (where tainted data originates)
        Column("source_file", "TEXT", nullable=False),
        Column("source_line", "INTEGER", nullable=False),
        Column("source_pattern", "TEXT", nullable=False),  # e.g., "req.body.username"

        # Sink location (where tainted data reaches dangerous operation)
        Column("sink_file", "TEXT", nullable=False),
        Column("sink_line", "INTEGER", nullable=False),
        Column("sink_pattern", "TEXT", nullable=False),  # e.g., "User.create"

        # Classification
        Column("vulnerability_type", "TEXT", nullable=False),  # "SQL Injection", "XSS", etc.

        # Path metadata
        Column("path_length", "INTEGER", nullable=False),  # Number of hops
        Column("hops", "INTEGER", nullable=False),  # Same as path_length for compatibility
        Column("path_json", "TEXT", nullable=False),  # JSON array of full hop chain (includes middleware!)
        Column("flow_sensitive", "INTEGER", nullable=False, default="1"),  # Boolean: CFG-aware

        # NEW: Status and sanitizer provenance
        Column("status", "TEXT", nullable=False, check="status IN ('VULNERABLE', 'SANITIZED')"),
        Column("sanitizer_file", "TEXT", nullable=True),  # e.g., "backend/src/middleware/validate.ts"
        Column("sanitizer_line", "INTEGER", nullable=True),  # e.g., 19
        Column("sanitizer_method", "TEXT", nullable=True),  # e.g., "zod.parseAsync"

        # NEW: Engine that discovered this flow (FlowResolver vs IFDS)
        Column("engine", "TEXT", nullable=False, default="'IFDS'", check="engine IN ('FlowResolver', 'IFDS')"),
    ],
    indexes=[
        # Existing indexes from taint_flows (for backward compatibility)
        ("idx_resolved_flow_source", ["source_file", "source_line"]),
        ("idx_resolved_flow_sink", ["sink_file", "sink_line"]),
        ("idx_resolved_flow_type", ["vulnerability_type"]),
        ("idx_resolved_flow_length", ["path_length"]),

        # NEW: Indexes for sanitizer analysis
        ("idx_resolved_flow_status", ["status"]),  # Fast filter for VULNERABLE vs SANITIZED
        ("idx_resolved_flow_sanitizer", ["sanitizer_file", "sanitizer_line"]),  # Sanitizer effectiveness
        ("idx_resolved_flow_sanitizer_method", ["sanitizer_method"]),  # Group by framework (zod, joi, etc.)

        # NEW: Index for engine filtering (FlowResolver vs IFDS)
        ("idx_resolved_flow_engine", ["engine"]),  # Fast filter for forward vs backward flows
    ]
)

# ============================================================================
# SECURITY TABLES REGISTRY
# ============================================================================

SECURITY_TABLES: dict[str, TableSchema] = {
    "env_var_usage": ENV_VAR_USAGE,
    "sql_objects": SQL_OBJECTS,
    "sql_queries": SQL_QUERIES,
    "sql_query_tables": SQL_QUERY_TABLES,
    "jwt_patterns": JWT_PATTERNS,
    "taint_flows": TAINT_FLOWS,  # Legacy table - kept for backward compatibility
    "resolved_flow_audit": RESOLVED_FLOW_AUDIT,  # NEW: Full provenance (vulnerable + sanitized paths)
}
