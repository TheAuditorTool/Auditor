"""
Core schema definitions - Used by ALL languages.

This module contains table schemas used across Python, Node, Rust, and all extractors:
- File tracking (files, config_files, refs)
- Symbol definitions (symbols, symbols_jsx)
- Data flow tables (assignments, function_call_args, function_returns)
- Security patterns (sql_queries, jwt_patterns)
- Control flow graphs (cfg_blocks, cfg_edges)
- Findings (findings_consolidated)

Design Philosophy:
- Core tables are language-agnostic
- Used by multiple extractors (Python + Node + Rust)
- Security-critical patterns (SQL, JWT, taint analysis)
"""

from .utils import Column, ForeignKey, TableSchema


# ============================================================================
# CORE TABLES - File tracking and metadata
# ============================================================================

FILES = TableSchema(
    name="files",
    columns=[
        Column("path", "TEXT", nullable=False, primary_key=True),
        Column("sha256", "TEXT", nullable=False),
        Column("ext", "TEXT", nullable=False),
        Column("bytes", "INTEGER", nullable=False),
        Column("loc", "INTEGER", nullable=False),
        Column("file_category", "TEXT", nullable=False, default="'source'"),
    ],
    indexes=[
        ("idx_files_ext", ["ext"])  # Index for fast extension lookups (Python/Node/etc)
    ]
)

CONFIG_FILES = TableSchema(
    name="config_files",
    columns=[
        Column("path", "TEXT", nullable=False, primary_key=True),
        Column("content", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("context_dir", "TEXT"),
    ],
    indexes=[]
)

REFS = TableSchema(
    name="refs",
    columns=[
        Column("src", "TEXT", nullable=False),
        Column("kind", "TEXT", nullable=False),
        Column("value", "TEXT", nullable=False),
        Column("line", "INTEGER"),
    ],
    indexes=[
        ("idx_refs_src", ["src"]),
    ]
)

# ============================================================================
# SYMBOL TABLES - Code structure and analysis
# ============================================================================

SYMBOLS = TableSchema(
    name="symbols",
    columns=[
        Column("path", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("col", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("type_annotation", "TEXT"),
        Column("parameters", "TEXT"),  # JSON array of parameter names: ['data', '_createdBy']
        Column("is_typed", "BOOLEAN", default="0"),
    ],
    primary_key=["path", "name", "line", "type", "col"],
    indexes=[
        ("idx_symbols_path", ["path"]),
        ("idx_symbols_type", ["type"]),
        ("idx_symbols_name", ["name"]),
    ]
)

SYMBOLS_JSX = TableSchema(
    name="symbols_jsx",
    columns=[
        Column("path", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("col", "INTEGER", nullable=False),
        Column("jsx_mode", "TEXT", nullable=False, default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="1"),
    ],
    primary_key=["path", "name", "line", "jsx_mode"],
    indexes=[
        ("idx_jsx_symbols_path", ["path"]),
        ("idx_jsx_symbols_type", ["type"]),
    ]
)

# ============================================================================
# SQL & DATABASE TABLES
# ============================================================================
# SQL & DATABASE TABLES - Moved to security_schema.py
# (SQL_OBJECTS, SQL_QUERIES, SQL_QUERY_TABLES, JWT_PATTERNS moved out)
# ORM_QUERIES - Moved to frameworks_schema.py
# ============================================================================

# ============================================================================
# DATA FLOW TABLES - Taint analysis critical
# ============================================================================

ASSIGNMENTS = TableSchema(
    name="assignments",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_var", "TEXT", nullable=False),
        Column("source_expr", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
        Column("property_path", "TEXT", nullable=True),  # Full path for destructured assignments (e.g., req.params.id)
    ],
    primary_key=["file", "line", "target_var"],
    indexes=[
        ("idx_assignments_file", ["file"]),
        ("idx_assignments_function", ["in_function"]),
        ("idx_assignments_target", ["target_var"]),
        ("idx_assignments_property_path", ["property_path"]),  # Index for taint analysis queries
    ]
)

ASSIGNMENTS_JSX = TableSchema(
    name="assignments_jsx",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_var", "TEXT", nullable=False),
        Column("source_expr", "TEXT", nullable=False),
        Column("in_function", "TEXT", nullable=False),
        Column("property_path", "TEXT", nullable=True),  # Full path for destructured assignments (e.g., req.params.id)
        Column("jsx_mode", "TEXT", nullable=False, default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="1"),
    ],
    primary_key=["file", "line", "target_var", "jsx_mode"],
    indexes=[
        ("idx_jsx_assignments_file", ["file"]),
        ("idx_jsx_assignments_function", ["in_function"]),
        ("idx_jsx_assignments_property_path", ["property_path"]),  # Index for taint analysis queries
    ]
)

FUNCTION_CALL_ARGS = TableSchema(
    name="function_call_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("caller_function", "TEXT", nullable=False),
        Column("callee_function", "TEXT", nullable=False, check="callee_function != ''"),
        Column("argument_index", "INTEGER", nullable=True),  # NULL for 0-arg calls
        Column("argument_expr", "TEXT", nullable=True),     # NULL for 0-arg calls
        Column("param_name", "TEXT", nullable=True),        # NULL for 0-arg calls
        Column("callee_file_path", "TEXT"),  # Resolved file path for callee function (enables unambiguous cross-file tracking)
    ],
    indexes=[
        ("idx_function_call_args_file", ["file"]),
        ("idx_function_call_args_caller", ["caller_function"]),
        ("idx_function_call_args_callee", ["callee_function"]),
        ("idx_function_call_args_file_line", ["file", "line"]),
        ("idx_function_call_args_callee_file", ["callee_file_path"]),  # Index for cross-file queries
        ("idx_function_call_args_argument_index", ["argument_index"]),  # Index for taint analysis queries by arg position
        ("idx_function_call_args_param_name", ["param_name"]),  # Index for parameter name lookups
    ]
)

FUNCTION_CALL_ARGS_JSX = TableSchema(
    name="function_call_args_jsx",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("caller_function", "TEXT", nullable=False),
        Column("callee_function", "TEXT", nullable=False),
        Column("argument_index", "INTEGER", nullable=True),  # NULL for 0-arg calls
        Column("argument_expr", "TEXT", nullable=True),     # NULL for 0-arg calls
        Column("param_name", "TEXT", nullable=True),        # NULL for 0-arg calls
        Column("jsx_mode", "TEXT", nullable=False, default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="1"),
    ],
    primary_key=["file", "line", "callee_function", "argument_index", "jsx_mode"],
    indexes=[
        ("idx_jsx_calls_file", ["file"]),
        ("idx_jsx_calls_caller", ["caller_function"]),
    ]
)

FUNCTION_RETURNS = TableSchema(
    name="function_returns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("return_expr", "TEXT", nullable=False),
        # React-specific columns (added via ALTER TABLE)
        Column("has_jsx", "BOOLEAN", default="0"),
        Column("returns_component", "BOOLEAN", default="0"),
        Column("cleanup_operations", "TEXT"),
    ],
    primary_key=["file", "line", "function_name"],
    indexes=[
        ("idx_function_returns_file", ["file"]),
        ("idx_function_returns_function", ["function_name"]),
    ]
)

FUNCTION_RETURNS_JSX = TableSchema(
    name="function_returns_jsx",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT"),
        Column("return_expr", "TEXT"),
        Column("has_jsx", "BOOLEAN", default="0"),
        Column("returns_component", "BOOLEAN", default="0"),
        Column("cleanup_operations", "TEXT"),
        Column("jsx_mode", "TEXT", nullable=False, default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="1"),
    ],
    primary_key=["file", "line", "extraction_pass"],
    indexes=[
        ("idx_jsx_returns_file", ["file"]),
        ("idx_jsx_returns_function", ["function_name"]),
    ]
)

# Junction tables for normalized many-to-many relationships
# Replaces JSON TEXT columns source_vars and return_vars with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies

ASSIGNMENT_SOURCES = TableSchema(
    name="assignment_sources",
    columns=[
        Column("id", "INTEGER", primary_key=True),
        Column("assignment_file", "TEXT", nullable=False),
        Column("assignment_line", "INTEGER", nullable=False),
        Column("assignment_target", "TEXT", nullable=False),
        Column("source_var_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_assignment_sources_assignment", ["assignment_file", "assignment_line", "assignment_target"]),
        ("idx_assignment_sources_var", ["source_var_name"]),
        ("idx_assignment_sources_file", ["assignment_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["assignment_file", "assignment_line", "assignment_target"],
            foreign_table="assignments",
            foreign_columns=["file", "line", "target_var"]
        )
    ]
)

ASSIGNMENT_SOURCES_JSX = TableSchema(
    name="assignment_sources_jsx",
    columns=[
        Column("id", "INTEGER", primary_key=True),
        Column("assignment_file", "TEXT", nullable=False),
        Column("assignment_line", "INTEGER", nullable=False),
        Column("assignment_target", "TEXT", nullable=False),
        Column("jsx_mode", "TEXT", nullable=False),
        Column("source_var_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_assignment_sources_jsx_assignment", ["assignment_file", "assignment_line", "assignment_target", "jsx_mode"]),
        ("idx_assignment_sources_jsx_var", ["source_var_name"]),
        ("idx_assignment_sources_jsx_file", ["assignment_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["assignment_file", "assignment_line", "assignment_target"],
            foreign_table="assignments_jsx",
            foreign_columns=["file", "line", "target_var"]
        )
    ]
)

FUNCTION_RETURN_SOURCES = TableSchema(
    name="function_return_sources",
    columns=[
        Column("id", "INTEGER", primary_key=True),
        Column("return_file", "TEXT", nullable=False),
        Column("return_line", "INTEGER", nullable=False),
        Column("return_function", "TEXT", nullable=False),
        Column("return_var_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_function_return_sources_return", ["return_file", "return_line", "return_function"]),
        ("idx_function_return_sources_var", ["return_var_name"]),
        ("idx_function_return_sources_file", ["return_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["return_file", "return_line", "return_function"],
            foreign_table="function_returns",
            foreign_columns=["file", "line", "function_name"]
        )
    ]
)

FUNCTION_RETURN_SOURCES_JSX = TableSchema(
    name="function_return_sources_jsx",
    columns=[
        Column("id", "INTEGER", primary_key=True),
        Column("return_file", "TEXT", nullable=False),
        Column("return_line", "INTEGER", nullable=False),
        Column("return_function", "TEXT"),
        Column("jsx_mode", "TEXT", nullable=False),
        Column("return_var_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_function_return_sources_jsx_return", ["return_file", "return_line", "jsx_mode"]),
        ("idx_function_return_sources_jsx_var", ["return_var_name"]),
        ("idx_function_return_sources_jsx_file", ["return_file"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["return_file", "return_line"],
            foreign_table="function_returns_jsx",
            foreign_columns=["file", "line"]
        )
    ]
)

VARIABLE_USAGE = TableSchema(
    name="variable_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("variable_name", "TEXT", nullable=False),  # CRITICAL: NOT var_name
        Column("usage_type", "TEXT", nullable=False),
        Column("in_component", "TEXT"),  # CRITICAL: NOT context
        Column("in_hook", "TEXT"),
        Column("scope_level", "INTEGER"),
    ],
    indexes=[
        ("idx_variable_usage_file", ["file"]),
        ("idx_variable_usage_component", ["in_component"]),
        ("idx_variable_usage_var", ["variable_name"]),
    ]
)

OBJECT_LITERALS = TableSchema(
    name="object_literals",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("variable_name", "TEXT"),  # The object variable (e.g., "handlers")
        Column("property_name", "TEXT", nullable=False),  # The property key (e.g., "create")
        Column("property_value", "TEXT", nullable=False),  # The property value (e.g., "handleCreate")
        Column("property_type", "TEXT"),  # 'function_ref', 'literal', 'expression', 'object', 'method_definition', 'shorthand'
        Column("nested_level", "INTEGER", default="0"),  # Depth of nesting (0 = top level)
        Column("in_function", "TEXT")  # Containing function context
    ],
    indexes=[
        ("idx_object_literals_file", ["file"]),
        ("idx_object_literals_var", ["variable_name"]),
        ("idx_object_literals_value", ["property_value"]),
        ("idx_object_literals_type", ["property_type"])
    ]
)

# ============================================================================
# CONTROL FLOW GRAPH TABLES
# ============================================================================

CFG_BLOCKS = TableSchema(
    name="cfg_blocks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("block_type", "TEXT", nullable=False),
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("condition_expr", "TEXT"),
    ],
    indexes=[
        ("idx_cfg_blocks_file", ["file"]),
        ("idx_cfg_blocks_function", ["function_name"]),
    ]
)

CFG_EDGES = TableSchema(
    name="cfg_edges",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("source_block_id", "INTEGER", nullable=False),
        Column("target_block_id", "INTEGER", nullable=False),
        Column("edge_type", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_cfg_edges_file", ["file"]),
        ("idx_cfg_edges_function", ["function_name"]),
        ("idx_cfg_edges_source", ["source_block_id"]),
        ("idx_cfg_edges_target", ["target_block_id"]),
    ]
)

CFG_BLOCK_STATEMENTS = TableSchema(
    name="cfg_block_statements",
    columns=[
        Column("block_id", "INTEGER", nullable=False),
        Column("statement_type", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("statement_text", "TEXT"),
    ],
    indexes=[
        ("idx_cfg_statements_block", ["block_id"]),
    ]
)

# JSX Preserved Mode CFG Tables
CFG_BLOCKS_JSX = TableSchema(
    name="cfg_blocks_jsx",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("block_type", "TEXT", nullable=False),
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("condition_expr", "TEXT"),
        Column("jsx_mode", "TEXT", default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="2"),
    ],
    indexes=[
        ("idx_jsx_cfg_blocks_file", ["file"]),
        ("idx_jsx_cfg_blocks_function", ["function_name"]),
    ]
)

CFG_EDGES_JSX = TableSchema(
    name="cfg_edges_jsx",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("source_block_id", "INTEGER", nullable=False),
        Column("target_block_id", "INTEGER", nullable=False),
        Column("edge_type", "TEXT", nullable=False),
        Column("jsx_mode", "TEXT", default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="2"),
    ],
    indexes=[
        ("idx_jsx_cfg_edges_file", ["file"]),
        ("idx_jsx_cfg_edges_function", ["function_name"]),
        ("idx_jsx_cfg_edges_source", ["source_block_id"]),
        ("idx_jsx_cfg_edges_target", ["target_block_id"]),
    ]
)

CFG_BLOCK_STATEMENTS_JSX = TableSchema(
    name="cfg_block_statements_jsx",
    columns=[
        Column("block_id", "INTEGER", nullable=False),
        Column("statement_type", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("statement_text", "TEXT"),
        Column("jsx_mode", "TEXT", default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="2"),
    ],
    indexes=[
        ("idx_jsx_cfg_statements_block", ["block_id"]),
    ]
)

# ============================================================================
# FINDINGS TABLE (Sparse Wide Table pattern - NO JSON blobs)
# ============================================================================
# ARCHITECTURE: Tool-specific metadata stored in typed columns, not JSON.
# - 79% of rows have NULL for tool-specific columns (free storage in SQLite)
# - Enables SQL filtering: WHERE cfg_complexity > 10
# - Eliminates json.loads() overhead in FCE
# - Taint complex data lives in taint_flows table, not here
# ============================================================================

FINDINGS_CONSOLIDATED = TableSchema(
    name="findings_consolidated",
    columns=[
        # === CORE COLUMNS (13) - Unchanged ===
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("column", "INTEGER"),
        Column("rule", "TEXT", nullable=False),
        Column("tool", "TEXT", nullable=False),
        Column("message", "TEXT"),
        Column("severity", "TEXT", nullable=False),
        Column("category", "TEXT"),
        Column("confidence", "REAL"),
        Column("code_snippet", "TEXT"),
        Column("cwe", "TEXT"),
        Column("timestamp", "TEXT", nullable=False),

        # === CFG-ANALYSIS COLUMNS (9) - 66 rows use these ===
        Column("cfg_function", "TEXT"),           # Function name
        Column("cfg_complexity", "INTEGER"),      # Cyclomatic complexity
        Column("cfg_block_count", "INTEGER"),     # Number of basic blocks
        Column("cfg_edge_count", "INTEGER"),      # Number of control flow edges
        Column("cfg_has_loops", "INTEGER"),       # Boolean as 0/1
        Column("cfg_has_recursion", "INTEGER"),   # Boolean as 0/1
        Column("cfg_start_line", "INTEGER"),      # Function start line
        Column("cfg_end_line", "INTEGER"),        # Function end line
        Column("cfg_threshold", "INTEGER"),       # Complexity threshold used

        # === GRAPH-ANALYSIS COLUMNS (7) - 50 rows use these ===
        Column("graph_id", "TEXT"),               # Node identifier
        Column("graph_in_degree", "INTEGER"),     # Incoming connections
        Column("graph_out_degree", "INTEGER"),    # Outgoing connections
        Column("graph_total_connections", "INTEGER"),  # Total connections
        Column("graph_centrality", "REAL"),       # Betweenness centrality
        Column("graph_score", "REAL"),            # Composite hotspot score
        Column("graph_cycle_nodes", "TEXT"),      # Comma-separated node list for cycles

        # === MYPY COLUMNS (3) - 4,397 rows use these ===
        Column("mypy_error_code", "TEXT"),        # e.g., "arg-type", "no-untyped-def"
        Column("mypy_severity_int", "INTEGER"),   # Severity as integer
        Column("mypy_column", "INTEGER"),         # Column number from mypy

        # === TERRAFORM COLUMNS (4) - 7 rows use these ===
        Column("tf_finding_id", "TEXT"),          # Terraform finding ID
        Column("tf_resource_id", "TEXT"),         # Resource identifier
        Column("tf_remediation", "TEXT"),         # Remediation guidance
        Column("tf_graph_context", "TEXT"),       # Graph context (stringified)
    ],
    indexes=[
        # Existing indexes (unchanged)
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
        # Partial indexes for sparse columns (3-tuple: name, columns, WHERE clause)
        ("idx_findings_cfg_complexity", ["cfg_complexity"], "cfg_complexity IS NOT NULL"),
        ("idx_findings_graph_score", ["graph_score"], "graph_score IS NOT NULL"),
        ("idx_findings_mypy_error_code", ["mypy_error_code"], "mypy_error_code IS NOT NULL"),
    ]
)

# ============================================================================
# CORE TABLES REGISTRY
# ============================================================================

CORE_TABLES: dict[str, TableSchema] = {
    # Core tables
    "files": FILES,
    "config_files": CONFIG_FILES,
    "refs": REFS,

    # Symbol tables
    "symbols": SYMBOLS,
    "symbols_jsx": SYMBOLS_JSX,

    # SQL & database (SQL/JWT tables moved to security_schema.py, orm_queries moved to frameworks_schema.py)

    # Data flow (taint analysis critical)
    "assignments": ASSIGNMENTS,
    "assignments_jsx": ASSIGNMENTS_JSX,
    "assignment_sources": ASSIGNMENT_SOURCES,
    "assignment_sources_jsx": ASSIGNMENT_SOURCES_JSX,
    "function_call_args": FUNCTION_CALL_ARGS,
    "function_call_args_jsx": FUNCTION_CALL_ARGS_JSX,
    "function_returns": FUNCTION_RETURNS,
    "function_returns_jsx": FUNCTION_RETURNS_JSX,
    "function_return_sources": FUNCTION_RETURN_SOURCES,
    "function_return_sources_jsx": FUNCTION_RETURN_SOURCES_JSX,
    "variable_usage": VARIABLE_USAGE,
    "object_literals": OBJECT_LITERALS,

    # Control flow graph
    "cfg_blocks": CFG_BLOCKS,
    "cfg_edges": CFG_EDGES,
    "cfg_block_statements": CFG_BLOCK_STATEMENTS,
    "cfg_blocks_jsx": CFG_BLOCKS_JSX,
    "cfg_edges_jsx": CFG_EDGES_JSX,
    "cfg_block_statements_jsx": CFG_BLOCK_STATEMENTS_JSX,

    # Findings
    "findings_consolidated": FINDINGS_CONSOLIDATED,
}


# ============================================================================
