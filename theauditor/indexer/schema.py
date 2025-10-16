"""
Database schema definitions - Single Source of Truth.

This module defines ALL table schemas used by TheAuditor.
Any module that reads/writes database MUST import schemas from here.

Design Philosophy:
- Indexer creates tables from these schemas
- Taint analyzer queries using these schemas
- Pattern rules query using these schemas
- Memory cache pre-loads using these schemas
- NO MORE HARDCODED COLUMN NAMES

Usage:
    from theauditor.indexer.schema import TABLES, build_query

    # Build a query dynamically:
    query = build_query('variable_usage', ['file', 'line', 'variable_name'])
    # Returns: "SELECT file, line, variable_name FROM variable_usage"

    # Validate database matches schema:
    mismatches = validate_all_tables(cursor)
    if mismatches:
        print(f"Schema errors: {mismatches}")

Schema Contract:
- This is the SINGLE source of truth for ALL database schemas
- Changes here propagate to ALL consumers automatically
- Schema validation runs at indexing time and analysis time
- Breaking changes detected at runtime, not production
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import sqlite3


@dataclass
class Column:
    """Represents a database column with type and constraints."""
    name: str
    type: str
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False
    check: Optional[str] = None

    def to_sql(self) -> str:
        """Generate SQL column definition."""
        parts = [self.name, self.type]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        if self.primary_key:
            parts.append("PRIMARY KEY")
        if self.check:
            parts.append(f"CHECK({self.check})")
        return " ".join(parts)


@dataclass
class TableSchema:
    """Represents a complete table schema.

    Design Pattern - Foreign Key Constraints:
        FOREIGN KEY constraints are intentionally omitted from TableSchema definitions.
        This design choice keeps the schema focused on table-level structure (columns,
        types, indexes, constraints) and decouples it from relational integrity, which
        is managed and enforced at the database.py layer where CREATE TABLE statements
        are defined. This simplifies schema validation and code generation by avoiding
        circular dependencies between table definitions.

        Foreign keys are defined exclusively in database.py CREATE TABLE statements
        and are not validated by the schema contract system.

    Attributes:
        name: Table name
        columns: List of column definitions
        indexes: List of (index_name, [column_names]) tuples
        primary_key: Composite primary key column list (for multi-column PKs)
        unique_constraints: List of UNIQUE constraint column lists
    """
    name: str
    columns: List[Column]
    indexes: List[Tuple[str, List[str]]] = field(default_factory=list)
    primary_key: Optional[List[str]] = None  # Composite primary keys
    unique_constraints: List[List[str]] = field(default_factory=list)  # UNIQUE constraints

    def column_names(self) -> List[str]:
        """Get list of column names in definition order."""
        return [col.name for col in self.columns]

    def create_table_sql(self) -> str:
        """Generate CREATE TABLE statement."""
        col_defs = [col.to_sql() for col in self.columns]

        # Add composite primary key if defined
        if self.primary_key:
            pk_cols = ", ".join(self.primary_key)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")

        # Add unique constraints if defined
        for unique_cols in self.unique_constraints:
            unique_str = ", ".join(unique_cols)
            col_defs.append(f"UNIQUE({unique_str})")

        return f"CREATE TABLE IF NOT EXISTS {self.name} (\n    " + ",\n    ".join(col_defs) + "\n)"

    def create_indexes_sql(self) -> List[str]:
        """Generate CREATE INDEX statements."""
        stmts = []
        for idx_name, idx_cols in self.indexes:
            cols_str = ", ".join(idx_cols)
            stmts.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {self.name} ({cols_str})")
        return stmts

    def validate_against_db(self, cursor: sqlite3.Cursor) -> Tuple[bool, List[str]]:
        """
        Validate that actual database table matches this schema.

        Returns:
            (is_valid, [error_messages])
        """
        errors = []

        # Check table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (self.name,)
        )
        if not cursor.fetchone():
            errors.append(f"Table {self.name} does not exist")
            return False, errors

        # Get actual columns
        cursor.execute(f"PRAGMA table_info({self.name})")
        actual_cols = {row[1]: row[2] for row in cursor.fetchall()}  # {name: type}

        # Validate columns (only check required columns, allow extra for migrations)
        for col in self.columns:
            if col.name not in actual_cols:
                errors.append(f"Column {self.name}.{col.name} missing in database")
            elif actual_cols[col.name].upper() != col.type.upper():
                errors.append(
                    f"Column {self.name}.{col.name} type mismatch: "
                    f"expected {col.type}, got {actual_cols[col.name]}"
                )

        # Validate UNIQUE constraints if defined in schema
        if self.unique_constraints:
            # Get the CREATE TABLE SQL from sqlite_master
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (self.name,)
            )
            result = cursor.fetchone()
            if result:
                create_sql = result[0] or ""
                # Check each expected UNIQUE constraint exists in the SQL
                for unique_cols in self.unique_constraints:
                    unique_str = ", ".join(unique_cols)
                    # Match both "UNIQUE(col1, col2)" and "UNIQUE (col1, col2)" formats
                    if f"UNIQUE({unique_str})" not in create_sql and f"UNIQUE ({unique_str})" not in create_sql:
                        errors.append(
                            f"UNIQUE constraint on ({unique_str}) missing in database table {self.name}"
                        )

        return len(errors) == 0, errors


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
    indexes=[]
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
        # Migrations (added via ALTER TABLE)
        Column("type_annotation", "TEXT"),
        Column("is_typed", "BOOLEAN", default="0"),
    ],
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
# API & ROUTING TABLES
# ============================================================================

API_ENDPOINTS = TableSchema(
    name="api_endpoints",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER"),
        Column("method", "TEXT", nullable=False),
        Column("pattern", "TEXT", nullable=False),
        Column("path", "TEXT"),
        Column("controls", "TEXT"),
        Column("has_auth", "BOOLEAN", default="0"),
        Column("handler_function", "TEXT"),
    ],
    indexes=[
        ("idx_api_endpoints_file", ["file"]),
    ]
)

# ============================================================================
# SQL & DATABASE TABLES
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
        Column("tables", "TEXT"),
        Column("extraction_source", "TEXT", nullable=False, default="'code_execute'"),
    ],
    indexes=[
        ("idx_sql_queries_file", ["file_path"]),
        ("idx_sql_queries_command", ["command"]),
    ]
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
    ]
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
    ]
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
    ]
)

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
        Column("source_vars", "TEXT"),
        Column("in_function", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_assignments_file", ["file"]),
        ("idx_assignments_function", ["in_function"]),
        ("idx_assignments_target", ["target_var"]),
    ]
)

ASSIGNMENTS_JSX = TableSchema(
    name="assignments_jsx",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_var", "TEXT", nullable=False),
        Column("source_expr", "TEXT", nullable=False),
        Column("source_vars", "TEXT"),
        Column("in_function", "TEXT", nullable=False),
        Column("jsx_mode", "TEXT", nullable=False, default="'preserved'"),
        Column("extraction_pass", "INTEGER", default="1"),
    ],
    primary_key=["file", "line", "target_var", "jsx_mode"],
    indexes=[
        ("idx_jsx_assignments_file", ["file"]),
        ("idx_jsx_assignments_function", ["in_function"]),
    ]
)

FUNCTION_CALL_ARGS = TableSchema(
    name="function_call_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("caller_function", "TEXT", nullable=False),
        Column("callee_function", "TEXT", nullable=False, check="callee_function != ''"),
        Column("argument_index", "INTEGER", nullable=False),
        Column("argument_expr", "TEXT", nullable=False),
        Column("param_name", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_function_call_args_file", ["file"]),
        ("idx_function_call_args_caller", ["caller_function"]),
        ("idx_function_call_args_callee", ["callee_function"]),
        ("idx_function_call_args_file_line", ["file", "line"]),
    ]
)

FUNCTION_CALL_ARGS_JSX = TableSchema(
    name="function_call_args_jsx",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("caller_function", "TEXT", nullable=False),
        Column("callee_function", "TEXT", nullable=False),
        Column("argument_index", "INTEGER", nullable=False),
        Column("argument_expr", "TEXT", nullable=False),
        Column("param_name", "TEXT", nullable=False),
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
        Column("return_vars", "TEXT"),
        # React-specific columns (added via ALTER TABLE)
        Column("has_jsx", "BOOLEAN", default="0"),
        Column("returns_component", "BOOLEAN", default="0"),
        Column("cleanup_operations", "TEXT"),
    ],
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
        Column("return_vars", "TEXT"),
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

# ============================================================================
# REACT TABLES
# ============================================================================

REACT_COMPONENTS = TableSchema(
    name="react_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("has_jsx", "BOOLEAN", default="0"),
        Column("hooks_used", "TEXT"),
        Column("props_type", "TEXT"),
    ],
    indexes=[
        ("idx_react_components_file", ["file"]),
        ("idx_react_components_name", ["name"]),
    ]
)

REACT_HOOKS = TableSchema(
    name="react_hooks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),
        Column("dependency_array", "TEXT"),
        Column("dependency_vars", "TEXT"),
        Column("callback_body", "TEXT"),
        Column("has_cleanup", "BOOLEAN", default="0"),
        Column("cleanup_type", "TEXT"),
    ],
    indexes=[
        ("idx_react_hooks_file", ["file"]),
        ("idx_react_hooks_component", ["component_name"]),
        ("idx_react_hooks_name", ["hook_name"]),
    ]
)

# ============================================================================
# VUE TABLES
# ============================================================================

VUE_COMPONENTS = TableSchema(
    name="vue_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("start_line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("has_template", "BOOLEAN", default="0"),
        Column("has_style", "BOOLEAN", default="0"),
        Column("composition_api_used", "BOOLEAN", default="0"),
        Column("props_definition", "TEXT"),
        Column("emits_definition", "TEXT"),
        Column("setup_return", "TEXT"),
    ],
    indexes=[
        ("idx_vue_components_file", ["file"]),
        ("idx_vue_components_name", ["name"]),
        ("idx_vue_components_type", ["type"]),
    ]
)

VUE_HOOKS = TableSchema(
    name="vue_hooks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),
        Column("hook_type", "TEXT", nullable=False),
        Column("dependencies", "TEXT"),
        Column("return_value", "TEXT"),
        Column("is_async", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_vue_hooks_file", ["file"]),
        ("idx_vue_hooks_component", ["component_name"]),
        ("idx_vue_hooks_type", ["hook_type"]),
    ]
)

VUE_DIRECTIVES = TableSchema(
    name="vue_directives",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("directive_name", "TEXT", nullable=False),
        Column("expression", "TEXT"),
        Column("in_component", "TEXT"),
        Column("has_key", "BOOLEAN", default="0"),
        Column("modifiers", "TEXT"),
    ],
    indexes=[
        ("idx_vue_directives_file", ["file"]),
        ("idx_vue_directives_name", ["directive_name"]),
    ]
)

VUE_PROVIDE_INJECT = TableSchema(
    name="vue_provide_inject",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("operation_type", "TEXT", nullable=False),
        Column("key_name", "TEXT", nullable=False),
        Column("value_expr", "TEXT"),
        Column("is_reactive", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_vue_provide_inject_file", ["file"]),
    ]
)

# ============================================================================
# TYPESCRIPT TABLES
# ============================================================================

TYPE_ANNOTATIONS = TableSchema(
    name="type_annotations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("column", "INTEGER"),
        Column("symbol_name", "TEXT", nullable=False),
        Column("symbol_kind", "TEXT", nullable=False),
        Column("type_annotation", "TEXT"),
        Column("is_any", "BOOLEAN", default="0"),
        Column("is_unknown", "BOOLEAN", default="0"),
        Column("is_generic", "BOOLEAN", default="0"),
        Column("has_type_params", "BOOLEAN", default="0"),
        Column("type_params", "TEXT"),
        Column("return_type", "TEXT"),
        Column("extends_type", "TEXT"),
    ],
    primary_key=["file", "line", "column", "symbol_name"],
    indexes=[
        ("idx_type_annotations_file", ["file"]),
        ("idx_type_annotations_any", ["file", "is_any"]),
        ("idx_type_annotations_unknown", ["file", "is_unknown"]),
        ("idx_type_annotations_generic", ["file", "is_generic"]),
    ]
)

# ============================================================================
# DOCKER & INFRASTRUCTURE TABLES
# ============================================================================

DOCKER_IMAGES = TableSchema(
    name="docker_images",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("base_image", "TEXT"),
        Column("exposed_ports", "TEXT"),
        Column("env_vars", "TEXT"),
        Column("build_args", "TEXT"),
        Column("user", "TEXT"),
        Column("has_healthcheck", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_docker_images_base", ["base_image"]),
    ]
)

COMPOSE_SERVICES = TableSchema(
    name="compose_services",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("service_name", "TEXT", nullable=False),
        Column("image", "TEXT"),
        Column("ports", "TEXT"),
        Column("volumes", "TEXT"),
        Column("environment", "TEXT"),
        Column("is_privileged", "BOOLEAN", default="0"),
        Column("network_mode", "TEXT"),
        # Security fields (added via ALTER TABLE)
        Column("user", "TEXT"),
        Column("cap_add", "TEXT"),
        Column("cap_drop", "TEXT"),
        Column("security_opt", "TEXT"),
        Column("restart", "TEXT"),
        Column("command", "TEXT"),
        Column("entrypoint", "TEXT"),
        Column("depends_on", "TEXT"),
        Column("healthcheck", "TEXT"),
    ],
    primary_key=["file_path", "service_name"],
    indexes=[
        ("idx_compose_services_file", ["file_path"]),
        ("idx_compose_services_privileged", ["is_privileged"]),
    ]
)

NGINX_CONFIGS = TableSchema(
    name="nginx_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("block_type", "TEXT", nullable=False),
        Column("block_context", "TEXT"),
        Column("directives", "TEXT"),
        Column("level", "INTEGER", default="0"),
    ],
    primary_key=["file_path", "block_type", "block_context"],
    indexes=[
        ("idx_nginx_configs_file", ["file_path"]),
        ("idx_nginx_configs_type", ["block_type"]),
    ]
)

# ============================================================================
# BUILD ANALYSIS TABLES
# ============================================================================

PACKAGE_CONFIGS = TableSchema(
    name="package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("package_name", "TEXT"),
        Column("version", "TEXT"),
        Column("dependencies", "TEXT"),
        Column("dev_dependencies", "TEXT"),
        Column("peer_dependencies", "TEXT"),
        Column("scripts", "TEXT"),
        Column("engines", "TEXT"),
        Column("workspaces", "TEXT"),
        Column("private", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_package_configs_file", ["file_path"]),
    ]
)

LOCK_ANALYSIS = TableSchema(
    name="lock_analysis",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("lock_type", "TEXT", nullable=False),
        Column("package_manager_version", "TEXT"),
        Column("total_packages", "INTEGER"),
        Column("duplicate_packages", "TEXT"),
        Column("lock_file_version", "TEXT"),
    ],
    indexes=[
        ("idx_lock_analysis_file", ["file_path"]),
        ("idx_lock_analysis_type", ["lock_type"]),
    ]
)

IMPORT_STYLES = TableSchema(
    name="import_styles",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("package", "TEXT", nullable=False),
        Column("import_style", "TEXT", nullable=False),
        Column("imported_names", "TEXT"),
        Column("alias_name", "TEXT"),
        Column("full_statement", "TEXT"),
    ],
    indexes=[
        ("idx_import_styles_file", ["file"]),
        ("idx_import_styles_package", ["package"]),
        ("idx_import_styles_style", ["import_style"]),
    ]
)

# ============================================================================
# FRAMEWORK DETECTION TABLES
# ============================================================================

FRAMEWORKS = TableSchema(
    name="frameworks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("name", "TEXT", nullable=False),
        Column("version", "TEXT"),
        Column("language", "TEXT", nullable=False),
        Column("path", "TEXT", default="'.'"),
        Column("source", "TEXT"),
        Column("package_manager", "TEXT"),
        Column("is_primary", "BOOLEAN", default="0"),
    ],
    indexes=[],
    unique_constraints=[["name", "language", "path"]]
)

FRAMEWORK_SAFE_SINKS = TableSchema(
    name="framework_safe_sinks",
    columns=[
        Column("framework_id", "INTEGER"),
        Column("sink_pattern", "TEXT", nullable=False),
        Column("sink_type", "TEXT", nullable=False),
        Column("is_safe", "BOOLEAN", default="1"),
        Column("reason", "TEXT"),
    ],
    indexes=[]
)

# ============================================================================
# FINDINGS TABLE (Dual-write pattern for FCE)
# ============================================================================

FINDINGS_CONSOLIDATED = TableSchema(
    name="findings_consolidated",
    columns=[
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
        Column("details_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
    ]
)

# ============================================================================
# SCHEMA REGISTRY - Single source of truth
# ============================================================================

TABLES: Dict[str, TableSchema] = {
    # Core tables
    "files": FILES,
    "config_files": CONFIG_FILES,
    "refs": REFS,

    # Symbol tables
    "symbols": SYMBOLS,
    "symbols_jsx": SYMBOLS_JSX,

    # API & routing
    "api_endpoints": API_ENDPOINTS,

    # SQL & database
    "sql_objects": SQL_OBJECTS,
    "sql_queries": SQL_QUERIES,
    "jwt_patterns": JWT_PATTERNS,
    "orm_queries": ORM_QUERIES,
    "prisma_models": PRISMA_MODELS,

    # Data flow (taint analysis critical)
    "assignments": ASSIGNMENTS,
    "assignments_jsx": ASSIGNMENTS_JSX,
    "function_call_args": FUNCTION_CALL_ARGS,
    "function_call_args_jsx": FUNCTION_CALL_ARGS_JSX,
    "function_returns": FUNCTION_RETURNS,
    "function_returns_jsx": FUNCTION_RETURNS_JSX,
    "variable_usage": VARIABLE_USAGE,
    "object_literals": OBJECT_LITERALS,

    # Control flow graph
    "cfg_blocks": CFG_BLOCKS,
    "cfg_edges": CFG_EDGES,
    "cfg_block_statements": CFG_BLOCK_STATEMENTS,

    # React
    "react_components": REACT_COMPONENTS,
    "react_hooks": REACT_HOOKS,

    # Vue
    "vue_components": VUE_COMPONENTS,
    "vue_hooks": VUE_HOOKS,
    "vue_directives": VUE_DIRECTIVES,
    "vue_provide_inject": VUE_PROVIDE_INJECT,

    # TypeScript
    "type_annotations": TYPE_ANNOTATIONS,

    # Docker & infrastructure
    "docker_images": DOCKER_IMAGES,
    "compose_services": COMPOSE_SERVICES,
    "nginx_configs": NGINX_CONFIGS,

    # Build analysis
    "package_configs": PACKAGE_CONFIGS,
    "lock_analysis": LOCK_ANALYSIS,
    "import_styles": IMPORT_STYLES,

    # Framework detection
    "frameworks": FRAMEWORKS,
    "framework_safe_sinks": FRAMEWORK_SAFE_SINKS,

    # Findings
    "findings_consolidated": FINDINGS_CONSOLIDATED,
}


# ============================================================================
# QUERY BUILDER UTILITIES
# ============================================================================

def build_query(table_name: str, columns: Optional[List[str]] = None,
                where: Optional[str] = None, order_by: Optional[str] = None,
                limit: Optional[int] = None) -> str:
    """
    Build a SELECT query using schema definitions.

    Args:
        table_name: Name of the table
        columns: List of column names to select (None = all columns)
        where: Optional WHERE clause (without 'WHERE' keyword)
        order_by: Optional ORDER BY clause (without 'ORDER BY' keyword)
        limit: Optional LIMIT clause (just the number, e.g., 1, 10, 100)

    Returns:
        Complete SELECT query string

    Example:
        >>> build_query('variable_usage', ['file', 'line', 'variable_name'])
        'SELECT file, line, variable_name FROM variable_usage'

        >>> build_query('sql_queries', where="command != 'UNKNOWN'")
        'SELECT file_path, line_number, query_text, command, tables, extraction_source FROM sql_queries WHERE command != \\'UNKNOWN\\''

        >>> build_query('symbols', ['name', 'line'], where="type = 'function'", order_by="line DESC", limit=1)
        'SELECT name, line FROM symbols WHERE type = \\'function\\' ORDER BY line DESC LIMIT 1'
    """
    if table_name not in TABLES:
        raise ValueError(f"Unknown table: {table_name}. Available tables: {', '.join(sorted(TABLES.keys()))}")

    schema = TABLES[table_name]

    if columns is None:
        columns = schema.column_names()
    else:
        # Validate columns exist
        valid_cols = set(schema.column_names())
        for col in columns:
            if col not in valid_cols:
                raise ValueError(
                    f"Unknown column '{col}' in table '{table_name}'. "
                    f"Valid columns: {', '.join(sorted(valid_cols))}"
                )

    query_parts = [
        "SELECT",
        ", ".join(columns),
        "FROM",
        table_name
    ]

    if where:
        query_parts.extend(["WHERE", where])

    if order_by:
        query_parts.extend(["ORDER BY", order_by])

    if limit is not None:
        query_parts.extend(["LIMIT", str(limit)])

    return " ".join(query_parts)


def validate_all_tables(cursor: sqlite3.Cursor) -> Dict[str, List[str]]:
    """
    Validate all table schemas against actual database.

    Returns:
        Dict of {table_name: [errors]} for tables with mismatches.
        Empty dict means all schemas are valid.
    """
    results = {}
    for table_name, schema in TABLES.items():
        is_valid, errors = schema.validate_against_db(cursor)
        if not is_valid:
            results[table_name] = errors
    return results


def get_table_schema(table_name: str) -> TableSchema:
    """
    Get schema for a specific table.

    Args:
        table_name: Name of the table

    Returns:
        TableSchema object

    Raises:
        ValueError: If table doesn't exist
    """
    if table_name not in TABLES:
        raise ValueError(
            f"Unknown table: {table_name}. "
            f"Available tables: {', '.join(sorted(TABLES.keys()))}"
        )
    return TABLES[table_name]


# ============================================================================
# SELF-TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("TheAuditor Database Schema Contract")
    print("=" * 80)
    print(f"\nTotal tables defined: {len(TABLES)}")
    print("\nTables:")
    for table_name in sorted(TABLES.keys()):
        schema = TABLES[table_name]
        print(f"\n  {table_name}:")
        print(f"    Columns: {len(schema.columns)}")
        for col in schema.columns:
            nullable = "" if col.nullable else " NOT NULL"
            default = f" DEFAULT {col.default}" if col.default else ""
            print(f"      - {col.name}: {col.type}{nullable}{default}")
        if schema.indexes:
            print(f"    Indexes: {len(schema.indexes)}")
            for idx_name, idx_cols in schema.indexes:
                print(f"      - {idx_name} on ({', '.join(idx_cols)})")

    print("\n" + "=" * 80)
    print("Query Builder Examples:")
    print("=" * 80)

    # Test query builder
    query1 = build_query('variable_usage', ['file', 'line', 'variable_name'])
    print(f"\nExample 1:\n  {query1}")

    query2 = build_query('sql_queries', where="command != 'UNKNOWN'", order_by="file_path, line_number")
    print(f"\nExample 2:\n  {query2}")

    query3 = build_query('function_returns')
    print(f"\nExample 3 (all columns):\n  {query3}")

    print("\n" + "=" * 80)
    print("Schema contract module loaded successfully!")
    print("=" * 80)
