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
class ForeignKey:
    """Foreign key relationship metadata for JOIN query generation.

    Purpose: Enables build_join_query() to validate and construct JOINs.
    NOT used for CREATE TABLE generation (database.py defines FKs).

    Attributes:
        local_columns: Column names in this table (e.g., ['query_file', 'query_line'])
        foreign_table: Referenced table name (e.g., 'sql_queries')
        foreign_columns: Column names in foreign table (e.g., ['file_path', 'line_number'])

    Example:
        ForeignKey(
            local_columns=['query_file', 'query_line'],
            foreign_table='sql_queries',
            foreign_columns=['file_path', 'line_number']
        )
    """
    local_columns: List[str]
    foreign_table: str
    foreign_columns: List[str]

    def validate(self, local_table: str, all_tables: Dict[str, 'TableSchema']) -> List[str]:
        """Validate foreign key definition against schema.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check foreign table exists
        if self.foreign_table not in all_tables:
            errors.append(f"Foreign table '{self.foreign_table}' does not exist")
            return errors

        local_schema = all_tables[local_table]
        foreign_schema = all_tables[self.foreign_table]

        # Check local columns exist
        local_col_names = set(local_schema.column_names())
        for col in self.local_columns:
            if col not in local_col_names:
                errors.append(f"Local column '{col}' not found in table '{local_table}'")

        # Check foreign columns exist
        foreign_col_names = set(foreign_schema.column_names())
        for col in self.foreign_columns:
            if col not in foreign_col_names:
                errors.append(f"Foreign column '{col}' not found in table '{self.foreign_table}'")

        # Check column count matches
        if len(self.local_columns) != len(self.foreign_columns):
            errors.append(
                f"Column count mismatch: {len(self.local_columns)} local vs "
                f"{len(self.foreign_columns)} foreign"
            )

        return errors


@dataclass
class TableSchema:
    """Represents a complete table schema.

    Design Pattern - Foreign Key Constraints:
        Foreign keys serve TWO purposes in this schema:

        1. JOIN Query Generation (NEW):
           The foreign_keys field provides metadata for build_join_query() to:
           - Validate JOIN conditions reference correct tables/columns
           - Auto-generate proper JOIN ON clauses
           - Enable type-safe relational queries

        2. Database Integrity (UNCHANGED):
           Actual FOREIGN KEY constraints in CREATE TABLE statements are still
           defined exclusively in database.py. This separation maintains backward
           compatibility and avoids circular dependencies during table creation.

        The foreign_keys field is OPTIONAL and backward compatible. Tables without
        foreign keys can still be queried normally with build_query().

    Attributes:
        name: Table name
        columns: List of column definitions
        indexes: List of (index_name, [column_names]) tuples
        primary_key: Composite primary key column list (for multi-column PKs)
        unique_constraints: List of UNIQUE constraint column lists
        foreign_keys: List of ForeignKey definitions (for JOIN generation)
    """
    name: str
    columns: List[Column]
    indexes: List[Tuple[str, List[str]]] = field(default_factory=list)
    primary_key: Optional[List[str]] = None  # Composite primary keys
    unique_constraints: List[List[str]] = field(default_factory=list)  # UNIQUE constraints
    foreign_keys: List[ForeignKey] = field(default_factory=list)  # For JOIN query generation

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

CLASS_PROPERTIES = TableSchema(
    name="class_properties",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("class_name", "TEXT", nullable=False),
        Column("property_name", "TEXT", nullable=False),
        Column("property_type", "TEXT", nullable=True),  # TypeScript type annotation
        Column("is_optional", "BOOLEAN", default="0"),    # ? modifier
        Column("is_readonly", "BOOLEAN", default="0"),    # readonly keyword
        Column("access_modifier", "TEXT", nullable=True), # "private", "protected", "public"
        Column("has_declare", "BOOLEAN", default="0"),    # declare keyword (TypeScript)
        Column("initializer", "TEXT", nullable=True),     # Default value if present
    ],
    primary_key=["file", "class_name", "property_name", "line"],
    indexes=[
        ("idx_class_properties_file", ["file"]),
        ("idx_class_properties_class", ["class_name"]),
        ("idx_class_properties_name", ["property_name"]),
    ]
)

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

ORM_RELATIONSHIPS = TableSchema(
    name="orm_relationships",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("source_model", "TEXT", nullable=False),      # "User"
        Column("target_model", "TEXT", nullable=False),      # "Account"
        Column("relationship_type", "TEXT", nullable=False), # "hasMany", "belongsTo", "hasOne"
        Column("foreign_key", "TEXT", nullable=True),        # "account_id"
        Column("cascade_delete", "BOOLEAN", default="0"),    # CASCADE delete option
        Column("as_name", "TEXT", nullable=True),            # Association alias (e.g., "as: 'owner'")
    ],
    primary_key=["file", "line", "source_model", "target_model"],
    indexes=[
        ("idx_orm_relationships_file", ["file"]),
        ("idx_orm_relationships_source", ["source_model"]),
        ("idx_orm_relationships_target", ["target_model"]),
        ("idx_orm_relationships_type", ["relationship_type"]),
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
        # controls REMOVED - see api_endpoint_controls junction table
        Column("has_auth", "BOOLEAN", default="0"),
        Column("handler_function", "TEXT"),
    ],
    indexes=[
        ("idx_api_endpoints_file", ["file"]),
    ]
)

# Junction table for normalized API endpoint controls/middleware
# Replaces JSON TEXT column api_endpoints.controls with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
API_ENDPOINT_CONTROLS = TableSchema(
    name="api_endpoint_controls",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("endpoint_file", "TEXT", nullable=False),
        Column("endpoint_line", "INTEGER", nullable=False),
        Column("control_name", "TEXT", nullable=False),  # 1 row per middleware/control
    ],
    indexes=[
        ("idx_api_endpoint_controls_endpoint", ["endpoint_file", "endpoint_line"]),  # FK composite lookup
        ("idx_api_endpoint_controls_control", ["control_name"]),  # Fast search by control name
        ("idx_api_endpoint_controls_file", ["endpoint_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["endpoint_file", "endpoint_line"],
            foreign_table="api_endpoints",
            foreign_columns=["file", "line"]
        )
    ]
)

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
        Column("decorator_type", "TEXT", nullable=False),  # property, staticmethod, framework, custom, etc.
        Column("target_type", "TEXT", nullable=False),     # function, class
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
        Column("context_type", "TEXT", nullable=False),  # with, async_with, custom_class
        Column("context_expr", "TEXT"),                  # Expression in with statement
        Column("as_name", "TEXT"),                       # as variable name
        Column("is_async", "BOOLEAN", default="0"),
        Column("is_custom", "BOOLEAN", default="0"),     # Custom __enter__/__exit__ class
    ],
    # No primary key - multiple context managers on same line is valid (with a, b: ...)
    indexes=[
        ("idx_python_context_managers_file", ["file"]),
        ("idx_python_context_managers_type", ["context_type"]),
        ("idx_python_context_managers_line", ["file", "line"]),  # For line lookups
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
        Column("generator_type", "TEXT", nullable=False),  # async_for, async_generator_function
        Column("target_vars", "TEXT"),                      # JSON list for async_for
        Column("iterable_expr", "TEXT"),                    # For async_for
        Column("function_name", "TEXT"),                    # For async_generator_function
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
        Column("scope", "TEXT", default="'function'"),  # function, class, module, session
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
        Column("parameter_names", "TEXT", nullable=False),  # JSON list
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
        Column("marker_args", "TEXT"),  # JSON list
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
        Column("mock_type", "TEXT", nullable=False),  # decorator, patch, Mock, MagicMock, AsyncMock
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
        Column("methods", "TEXT"),  # JSON list of method names
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
        Column("type_params", "TEXT"),  # JSON list of type parameter names
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
        Column("fields", "TEXT"),  # JSON list of field dicts: {field_name, field_type, is_required}
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
        Column("usage_context", "TEXT", nullable=False),  # parameter, return, variable
        Column("name", "TEXT"),                            # parameter_name, function_name, or variable_name
        Column("literal_type", "TEXT", nullable=False),    # Full Literal annotation
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
        Column("variants", "TEXT", nullable=False),  # JSON list of variant dicts: {line, param_types[], return_type}
    ],
    primary_key=["file", "function_name"],
    indexes=[
        ("idx_python_overloads_file", ["file"]),
        ("idx_python_overloads_name", ["function_name"]),
    ]
)

# Django framework-specific patterns
PYTHON_DJANGO_VIEWS = TableSchema(
    name="python_django_views",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("view_class_name", "TEXT", nullable=False),
        Column("view_type", "TEXT", nullable=False),          # list, detail, create, update, delete, form, template, redirect, base
        Column("base_view_class", "TEXT"),                    # ListView, DetailView, CreateView, etc.
        Column("model_name", "TEXT"),                         # Associated model (if any)
        Column("template_name", "TEXT"),                      # Template path
        Column("has_permission_check", "BOOLEAN", default="0"),  # @permission_required, @login_required on dispatch()
        Column("http_method_names", "TEXT"),                  # Comma-separated allowed methods (GET, POST, etc.)
        Column("has_get_queryset_override", "BOOLEAN", default="0"),  # SQL injection surface
    ],
    primary_key=["file", "line", "view_class_name"],
    indexes=[
        ("idx_python_django_views_file", ["file"]),
        ("idx_python_django_views_type", ["view_type"]),
        ("idx_python_django_views_model", ["model_name"]),
        ("idx_python_django_views_no_perm", ["has_permission_check"]),  # Find views without auth
    ]
)

PYTHON_DJANGO_FORMS = TableSchema(
    name="python_django_forms",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("is_model_form", "BOOLEAN", default="0"),
        Column("model_name", "TEXT"),                    # For ModelForm
        Column("field_count", "INTEGER", default="0"),   # Validation surface area
        Column("has_custom_clean", "BOOLEAN", default="0"),  # Custom validation logic
    ],
    primary_key=["file", "line", "form_class_name"],
    indexes=[
        ("idx_python_django_forms_file", ["file"]),
        ("idx_python_django_forms_model", ["is_model_form"]),
        ("idx_python_django_forms_no_validators", ["has_custom_clean"]),  # Forms without validation
    ]
)

PYTHON_DJANGO_FORM_FIELDS = TableSchema(
    name="python_django_form_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),    # CharField, EmailField, IntegerField, etc.
        Column("required", "BOOLEAN", default="1"),      # Default is required
        Column("max_length", "INTEGER"),                 # DoS risk if unbounded
        Column("has_custom_validator", "BOOLEAN", default="0"),  # clean_<field> method exists
    ],
    primary_key=["file", "line", "form_class_name", "field_name"],
    indexes=[
        ("idx_python_django_form_fields_file", ["file"]),
        ("idx_python_django_form_fields_form", ["form_class_name"]),
        ("idx_python_django_form_fields_type", ["field_type"]),
        ("idx_python_django_form_fields_no_length", ["max_length"]),  # Find unbounded fields
    ]
)

PYTHON_DJANGO_ADMIN = TableSchema(
    name="python_django_admin",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("admin_class_name", "TEXT", nullable=False),
        Column("model_name", "TEXT"),                        # Associated model from admin.site.register()
        Column("list_display", "TEXT"),                      # Comma-separated field names shown in list view
        Column("list_filter", "TEXT"),                       # Comma-separated filter fields
        Column("search_fields", "TEXT"),                     # Comma-separated searchable fields
        Column("readonly_fields", "TEXT"),                   # Comma-separated read-only fields
        Column("has_custom_actions", "BOOLEAN", default="0"),  # Custom bulk actions defined
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
        Column("has_process_request", "BOOLEAN", default="0"),       # Pre-view processing
        Column("has_process_response", "BOOLEAN", default="0"),      # Post-view processing
        Column("has_process_exception", "BOOLEAN", default="0"),     # Exception handling
        Column("has_process_view", "BOOLEAN", default="0"),          # View-level processing
        Column("has_process_template_response", "BOOLEAN", default="0"),  # Template processing
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
        Column("field_count", "INTEGER", default="0"),               # Validation surface area
        Column("has_nested_schemas", "BOOLEAN", default="0"),        # ma.Nested references
        Column("has_custom_validators", "BOOLEAN", default="0"),     # @validates decorators
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
        Column("field_type", "TEXT", nullable=False),                # String, Integer, Email, Nested, etc.
        Column("required", "BOOLEAN", default="0"),                  # required=True flag
        Column("allow_none", "BOOLEAN", default="0"),                # allow_none=True flag
        Column("has_validate", "BOOLEAN", default="0"),              # validate= keyword arg
        Column("has_custom_validator", "BOOLEAN", default="0"),      # @validates('field_name') decorator
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
        Column("field_count", "INTEGER", default="0"),               # Validation surface area
        Column("is_model_serializer", "BOOLEAN", default="0"),       # ModelSerializer vs Serializer
        Column("has_meta_model", "BOOLEAN", default="0"),            # Has Meta.model
        Column("has_read_only_fields", "BOOLEAN", default="0"),      # Has Meta.read_only_fields
        Column("has_custom_validators", "BOOLEAN", default="0"),     # validate_<field> methods
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
        Column("field_type", "TEXT", nullable=False),                # CharField, IntegerField, etc.
        Column("read_only", "BOOLEAN", default="0"),                 # read_only=True flag
        Column("write_only", "BOOLEAN", default="0"),                # write_only=True flag
        Column("required", "BOOLEAN", default="0"),                  # required=True flag
        Column("allow_null", "BOOLEAN", default="0"),                # allow_null=True flag
        Column("has_source", "BOOLEAN", default="0"),                # source= parameter
        Column("has_custom_validator", "BOOLEAN", default="0"),      # validate_<field> method
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
        Column("field_count", "INTEGER", default="0"),               # Validation surface area
        Column("has_custom_validators", "BOOLEAN", default="0"),     # validate_<field> methods
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
        Column("field_type", "TEXT", nullable=False),                # StringField, IntegerField, etc.
        Column("has_validators", "BOOLEAN", default="0"),            # validators=[...] keyword
        Column("has_custom_validator", "BOOLEAN", default="0"),      # validate_<field> method
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
        Column("decorator_name", "TEXT", nullable=False),         # task, shared_task, app.task
        Column("arg_count", "INTEGER", default="0"),              # Injection surface area
        Column("bind", "BOOLEAN", default="0"),                   # bind=True (task instance access)
        Column("serializer", "TEXT", nullable=True),              # pickle = RCE risk, json = safe
        Column("max_retries", "INTEGER", nullable=True),          # Retry configuration
        Column("rate_limit", "TEXT", nullable=True),              # Rate limiting (DoS protection)
        Column("time_limit", "INTEGER", nullable=True),           # Time limit (DoS protection)
        Column("queue", "TEXT", nullable=True),                   # Task queue (privilege separation)
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
        Column("caller_function", "TEXT", nullable=False),            # Function calling the task
        Column("task_name", "TEXT", nullable=False),                  # Task being invoked
        Column("invocation_type", "TEXT", nullable=False),            # delay, apply_async, chain, group, chord, s, si
        Column("arg_count", "INTEGER", default="0"),                  # Number of arguments passed
        Column("has_countdown", "BOOLEAN", default="0"),              # apply_async with countdown=
        Column("has_eta", "BOOLEAN", default="0"),                    # apply_async with eta=
        Column("queue_override", "TEXT", nullable=True),              # apply_async with queue= (bypass protection)
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
        Column("schedule_name", "TEXT", nullable=False),            # Key in beat_schedule dict
        Column("task_name", "TEXT", nullable=False),                # Task to execute
        Column("schedule_type", "TEXT", nullable=False),            # crontab, interval, periodic_task
        Column("schedule_expression", "TEXT", nullable=True),       # Cron expression or interval
        Column("args", "TEXT", nullable=True),                      # JSON-encoded task args
        Column("kwargs", "TEXT", nullable=True),                    # JSON-encoded task kwargs
    ],
    primary_key=["file", "line", "schedule_name"],
    indexes=[
        ("idx_python_celery_beat_schedules_file", ["file"]),
        ("idx_python_celery_beat_schedules_task", ["task_name"]),
        ("idx_python_celery_beat_schedules_type", ["schedule_type"]),
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
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
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
        # hooks_used REMOVED - see react_component_hooks junction table
        Column("props_type", "TEXT"),
    ],
    indexes=[
        ("idx_react_components_file", ["file"]),
        ("idx_react_components_name", ["name"]),
    ]
)

# Junction table for normalized React component hooks
# Replaces JSON TEXT column react_components.hooks_used with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
REACT_COMPONENT_HOOKS = TableSchema(
    name="react_component_hooks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("component_file", "TEXT", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("hook_name", "TEXT", nullable=False),  # 1 row per hook used
    ],
    indexes=[
        ("idx_react_comp_hooks_component", ["component_file", "component_name"]),  # FK composite lookup
        ("idx_react_comp_hooks_hook", ["hook_name"]),  # Fast search by hook name
        ("idx_react_comp_hooks_file", ["component_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["component_file", "component_name"],
            foreign_table="react_components",
            foreign_columns=["file", "name"]
        )
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
        # dependency_vars REMOVED - see react_hook_dependencies junction table
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

# Junction table for normalized React hook dependency variables
# Replaces JSON TEXT column react_hooks.dependency_vars with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
REACT_HOOK_DEPENDENCIES = TableSchema(
    name="react_hook_dependencies",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("hook_file", "TEXT", nullable=False),
        Column("hook_line", "INTEGER", nullable=False),
        Column("hook_component", "TEXT", nullable=False),
        Column("dependency_name", "TEXT", nullable=False),  # 1 row per dependency variable
    ],
    indexes=[
        ("idx_react_hook_deps_hook", ["hook_file", "hook_line", "hook_component"]),  # FK composite lookup
        ("idx_react_hook_deps_name", ["dependency_name"]),  # Fast search by variable name
        ("idx_react_hook_deps_file", ["hook_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["hook_file", "hook_line", "hook_component"],
            foreign_table="react_hooks",
            foreign_columns=["file", "line", "component_name"]
        )
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
# TERRAFORM TABLES (Infrastructure as Code)
# ============================================================================

TERRAFORM_FILES = TableSchema(
    name="terraform_files",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("module_name", "TEXT"),  # e.g., "vpc", "database", "networking"
        Column("stack_name", "TEXT"),   # e.g., "prod", "staging", "dev"
        Column("backend_type", "TEXT"), # e.g., "s3", "local", "remote"
        Column("providers_json", "TEXT"), # JSON array of provider configs
        Column("is_module", "BOOLEAN", default="0"),
        Column("module_source", "TEXT"), # For module blocks
    ],
    indexes=[
        ("idx_terraform_files_module", ["module_name"]),
        ("idx_terraform_files_stack", ["stack_name"]),
    ]
)

TERRAFORM_RESOURCES = TableSchema(
    name="terraform_resources",
    columns=[
        Column("resource_id", "TEXT", nullable=False, primary_key=True),  # Format: "file::type.name"
        Column("file_path", "TEXT", nullable=False),
        Column("resource_type", "TEXT", nullable=False),  # e.g., "aws_db_instance", "aws_security_group"
        Column("resource_name", "TEXT", nullable=False),  # e.g., "main_db", "web_sg"
        Column("module_path", "TEXT"),  # Hierarchical path for nested modules
        Column("properties_json", "TEXT"),  # Full resource properties
        Column("depends_on_json", "TEXT"),  # Explicit depends_on declarations
        Column("sensitive_flags_json", "TEXT"),  # Which properties are sensitive
        Column("has_public_exposure", "BOOLEAN", default="0"),  # Flagged during analysis
        Column("line", "INTEGER"),  # Start line in file
    ],
    indexes=[
        ("idx_terraform_resources_file", ["file_path"]),
        ("idx_terraform_resources_type", ["resource_type"]),
        ("idx_terraform_resources_name", ["resource_name"]),
        ("idx_terraform_resources_public", ["has_public_exposure"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="terraform_files",
            foreign_columns=["file_path"]
        )
    ]
)

TERRAFORM_VARIABLES = TableSchema(
    name="terraform_variables",
    columns=[
        Column("variable_id", "TEXT", nullable=False, primary_key=True),  # Format: "file::var_name"
        Column("file_path", "TEXT", nullable=False),
        Column("variable_name", "TEXT", nullable=False),
        Column("variable_type", "TEXT"),  # string, number, list, map, object, etc.
        Column("default_json", "TEXT"),  # Default value if provided
        Column("is_sensitive", "BOOLEAN", default="0"),
        Column("description", "TEXT"),
        Column("source_file", "TEXT"),  # .tfvars file if value sourced externally
        Column("line", "INTEGER"),
    ],
    indexes=[
        ("idx_terraform_variables_file", ["file_path"]),
        ("idx_terraform_variables_name", ["variable_name"]),
        ("idx_terraform_variables_sensitive", ["is_sensitive"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="terraform_files",
            foreign_columns=["file_path"]
        )
    ]
)

TERRAFORM_VARIABLE_VALUES = TableSchema(
    name="terraform_variable_values",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("variable_name", "TEXT", nullable=False),
        Column("variable_value_json", "TEXT"),
        Column("line", "INTEGER"),
        Column("is_sensitive_context", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_tf_var_values_file", ["file_path"]),
        ("idx_tf_var_values_name", ["variable_name"]),
        ("idx_tf_var_values_sensitive", ["is_sensitive_context"]),
    ]
)

TERRAFORM_OUTPUTS = TableSchema(
    name="terraform_outputs",
    columns=[
        Column("output_id", "TEXT", nullable=False, primary_key=True),  # Format: "file::output_name"
        Column("file_path", "TEXT", nullable=False),
        Column("output_name", "TEXT", nullable=False),
        Column("value_json", "TEXT"),  # The output expression
        Column("is_sensitive", "BOOLEAN", default="0"),
        Column("description", "TEXT"),
        Column("line", "INTEGER"),
    ],
    indexes=[
        ("idx_terraform_outputs_file", ["file_path"]),
        ("idx_terraform_outputs_name", ["output_name"]),
        ("idx_terraform_outputs_sensitive", ["is_sensitive"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="terraform_files",
            foreign_columns=["file_path"]
        )
    ]
)

TERRAFORM_FINDINGS = TableSchema(
    name="terraform_findings",
    columns=[
        Column("finding_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("resource_id", "TEXT"),  # FK to terraform_resources
        Column("category", "TEXT", nullable=False),  # "public_exposure", "iam_wildcard", "secret_propagation"
        Column("severity", "TEXT", nullable=False),  # "critical", "high", "medium", "low"
        Column("title", "TEXT", nullable=False),
        Column("description", "TEXT"),
        Column("graph_context_json", "TEXT"),  # Path nodes for blast radius
        Column("remediation", "TEXT"),
        Column("line", "INTEGER"),
    ],
    indexes=[
        ("idx_terraform_findings_file", ["file_path"]),
        ("idx_terraform_findings_resource", ["resource_id"]),
        ("idx_terraform_findings_severity", ["severity"]),
        ("idx_terraform_findings_category", ["category"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["file_path"],
            foreign_table="terraform_files",
            foreign_columns=["file_path"]
        ),
        ForeignKey(
            local_columns=["resource_id"],
            foreign_table="terraform_resources",
            foreign_columns=["resource_id"]
        )
    ]
)

# ============================================================================
# AWS CDK INFRASTRUCTURE-AS-CODE TABLES
# ============================================================================
# CDK construct analysis for cloud infrastructure security

CDK_CONSTRUCTS = TableSchema(
    name="cdk_constructs",
    columns=[
        Column("construct_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("cdk_class", "TEXT", nullable=False),  # e.g., 'aws_cdk.aws_s3.Bucket', 's3.Bucket'
        Column("construct_name", "TEXT"),  # Nullable - CDK logical ID (2nd positional arg)
    ],
    indexes=[
        ("idx_cdk_constructs_file", ["file_path"]),
        ("idx_cdk_constructs_class", ["cdk_class"]),
        ("idx_cdk_constructs_line", ["file_path", "line"]),
    ]
)

CDK_CONSTRUCT_PROPERTIES = TableSchema(
    name="cdk_construct_properties",
    columns=[
        Column("id", "INTEGER", primary_key=True),  # AUTOINCREMENT
        Column("construct_id", "TEXT", nullable=False),  # FK to cdk_constructs
        Column("property_name", "TEXT", nullable=False),  # e.g., 'public_read_access', 'encryption'
        Column("property_value_expr", "TEXT", nullable=False),  # Serialized via ast.unparse()
        Column("line", "INTEGER", nullable=False),  # Line number of property definition
    ],
    indexes=[
        ("idx_cdk_props_construct", ["construct_id"]),
        ("idx_cdk_props_name", ["property_name"]),
        ("idx_cdk_props_construct_name", ["construct_id", "property_name"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["construct_id"],
            foreign_table="cdk_constructs",
            foreign_columns=["construct_id"]
        )
    ]
)

CDK_FINDINGS = TableSchema(
    name="cdk_findings",
    columns=[
        Column("finding_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("construct_id", "TEXT"),  # FK to cdk_constructs (nullable for file-level findings)
        Column("category", "TEXT", nullable=False),  # "public_exposure", "missing_encryption", etc.
        Column("severity", "TEXT", nullable=False),  # "critical", "high", "medium", "low"
        Column("title", "TEXT", nullable=False),
        Column("description", "TEXT", nullable=False),
        Column("remediation", "TEXT"),
        Column("line", "INTEGER"),
    ],
    indexes=[
        ("idx_cdk_findings_file", ["file_path"]),
        ("idx_cdk_findings_construct", ["construct_id"]),
        ("idx_cdk_findings_severity", ["severity"]),
        ("idx_cdk_findings_category", ["category"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["construct_id"],
            foreign_table="cdk_constructs",
            foreign_columns=["construct_id"]
        )
    ]
)

# ============================================================================
# GITHUB ACTIONS WORKFLOW TABLES (CI/CD Security Analysis)
# ============================================================================

GITHUB_WORKFLOWS = TableSchema(
    name="github_workflows",
    columns=[
        Column("workflow_path", "TEXT", nullable=False, primary_key=True),  # .github/workflows/ci.yml
        Column("workflow_name", "TEXT"),  # Name from 'name:' field or filename
        Column("on_triggers", "TEXT", nullable=False),  # JSON array of trigger events
        Column("permissions", "TEXT"),  # JSON object of workflow-level permissions
        Column("concurrency", "TEXT"),  # JSON object of concurrency settings
        Column("env", "TEXT"),  # JSON object of workflow-level env vars
    ],
    indexes=[
        ("idx_github_workflows_path", ["workflow_path"]),
        ("idx_github_workflows_name", ["workflow_name"]),
    ]
)

GITHUB_JOBS = TableSchema(
    name="github_jobs",
    columns=[
        Column("job_id", "TEXT", nullable=False, primary_key=True),  # PK: workflow_path||':'||job_key
        Column("workflow_path", "TEXT", nullable=False),  # FK to github_workflows
        Column("job_key", "TEXT", nullable=False),  # Job key from YAML (e.g., 'build', 'test')
        Column("job_name", "TEXT"),  # Optional name: field
        Column("runs_on", "TEXT"),  # JSON array of runner labels (supports matrix)
        Column("strategy", "TEXT"),  # JSON object of matrix strategy
        Column("permissions", "TEXT"),  # JSON object of job-level permissions
        Column("env", "TEXT"),  # JSON object of job-level env vars
        Column("if_condition", "TEXT"),  # Conditional expression for job execution
        Column("timeout_minutes", "INTEGER"),  # Job timeout
        Column("uses_reusable_workflow", "BOOLEAN", default="0"),  # True if uses: workflow.yml
        Column("reusable_workflow_path", "TEXT"),  # Path to reusable workflow if used
    ],
    indexes=[
        ("idx_github_jobs_workflow", ["workflow_path"]),
        ("idx_github_jobs_key", ["job_key"]),
        ("idx_github_jobs_reusable", ["uses_reusable_workflow"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["workflow_path"],
            foreign_table="github_workflows",
            foreign_columns=["workflow_path"]
        )
    ]
)

GITHUB_JOB_DEPENDENCIES = TableSchema(
    name="github_job_dependencies",
    columns=[
        Column("job_id", "TEXT", nullable=False),  # FK to github_jobs
        Column("needs_job_id", "TEXT", nullable=False),  # FK to github_jobs (dependency)
    ],
    primary_key=["job_id", "needs_job_id"],
    indexes=[
        ("idx_github_job_deps_job", ["job_id"]),
        ("idx_github_job_deps_needs", ["needs_job_id"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["job_id"],
            foreign_table="github_jobs",
            foreign_columns=["job_id"]
        ),
        ForeignKey(
            local_columns=["needs_job_id"],
            foreign_table="github_jobs",
            foreign_columns=["job_id"]
        ),
    ]
)

GITHUB_STEPS = TableSchema(
    name="github_steps",
    columns=[
        Column("step_id", "TEXT", nullable=False, primary_key=True),  # PK: job_id||':'||sequence_order
        Column("job_id", "TEXT", nullable=False),  # FK to github_jobs
        Column("sequence_order", "INTEGER", nullable=False),  # Step order within job (0-indexed)
        Column("step_name", "TEXT"),  # Optional name: field
        Column("uses_action", "TEXT"),  # Action reference (e.g., 'actions/checkout@v4')
        Column("uses_version", "TEXT"),  # Version/ref extracted from uses (e.g., 'v4', 'main', 'sha')
        Column("run_script", "TEXT"),  # Shell script content from run: field
        Column("shell", "TEXT"),  # Shell type (bash, pwsh, python, etc.)
        Column("env", "TEXT"),  # JSON object of step-level env vars
        Column("with_args", "TEXT"),  # JSON object of action inputs (with: field)
        Column("if_condition", "TEXT"),  # Conditional expression for step execution
        Column("timeout_minutes", "INTEGER"),  # Step timeout
        Column("continue_on_error", "BOOLEAN", default="0"),  # Continue on failure
    ],
    indexes=[
        ("idx_github_steps_job", ["job_id"]),
        ("idx_github_steps_sequence", ["job_id", "sequence_order"]),
        ("idx_github_steps_action", ["uses_action"]),
        ("idx_github_steps_version", ["uses_version"]),  # Find mutable tags (main, v1)
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["job_id"],
            foreign_table="github_jobs",
            foreign_columns=["job_id"]
        )
    ]
)

GITHUB_STEP_OUTPUTS = TableSchema(
    name="github_step_outputs",
    columns=[
        Column("id", "INTEGER", primary_key=True),  # AUTOINCREMENT
        Column("step_id", "TEXT", nullable=False),  # FK to github_steps
        Column("output_name", "TEXT", nullable=False),  # Output key
        Column("output_expression", "TEXT", nullable=False),  # Value expression
    ],
    indexes=[
        ("idx_github_step_outputs_step", ["step_id"]),
        ("idx_github_step_outputs_name", ["output_name"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["step_id"],
            foreign_table="github_steps",
            foreign_columns=["step_id"]
        )
    ]
)

GITHUB_STEP_REFERENCES = TableSchema(
    name="github_step_references",
    columns=[
        Column("id", "INTEGER", primary_key=True),  # AUTOINCREMENT
        Column("step_id", "TEXT", nullable=False),  # FK to github_steps
        Column("reference_location", "TEXT", nullable=False),  # 'run', 'env', 'with', 'if'
        Column("reference_type", "TEXT", nullable=False),  # 'github', 'secrets', 'env', 'needs', 'steps'
        Column("reference_path", "TEXT", nullable=False),  # Full path (e.g., 'github.event.pull_request.head.sha')
    ],
    indexes=[
        ("idx_github_step_refs_step", ["step_id"]),
        ("idx_github_step_refs_type", ["reference_type"]),
        ("idx_github_step_refs_path", ["reference_path"]),
        ("idx_github_step_refs_location", ["reference_location"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["step_id"],
            foreign_table="github_steps",
            foreign_columns=["step_id"]
        )
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
        # imported_names REMOVED - see import_style_names junction table
        Column("alias_name", "TEXT"),
        Column("full_statement", "TEXT"),
    ],
    indexes=[
        ("idx_import_styles_file", ["file"]),
        ("idx_import_styles_package", ["package"]),
        ("idx_import_styles_style", ["import_style"]),
    ]
)

# Junction table for normalized import statement names
# Replaces JSON TEXT column import_styles.imported_names with relational model
# FOREIGN KEY constraints defined in database.py to avoid circular dependencies
IMPORT_STYLE_NAMES = TableSchema(
    name="import_style_names",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),  # AUTOINCREMENT handled by SQLite
        Column("import_file", "TEXT", nullable=False),
        Column("import_line", "INTEGER", nullable=False),
        Column("imported_name", "TEXT", nullable=False),  # 1 row per imported name
    ],
    indexes=[
        ("idx_import_style_names_import", ["import_file", "import_line"]),  # FK composite lookup
        ("idx_import_style_names_name", ["imported_name"]),  # Fast search by imported name
        ("idx_import_style_names_file", ["import_file"]),  # File-level aggregation queries
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["import_file", "import_line"],
            foreign_table="import_styles",
            foreign_columns=["file", "line"]
        )
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

VALIDATION_FRAMEWORK_USAGE = TableSchema(
    name="validation_framework_usage",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),  # 'zod', 'joi', 'yup'
        Column("method", "TEXT", nullable=False),  # 'parse', 'parseAsync', 'validate'
        Column("variable_name", "TEXT"),  # 'schema', 'userSchema' or NULL for direct calls
        Column("is_validator", "BOOLEAN", default="1"),  # True for validators, False for schema builders
        Column("argument_expr", "TEXT"),  # Expression being validated (e.g., 'req.body')
    ],
    indexes=[
        ("idx_validation_framework_file_line", ["file_path", "line"]),
        ("idx_validation_framework_method", ["framework", "method"]),
        ("idx_validation_is_validator", ["is_validator"]),
    ]
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
# PLANNING TABLES
# ============================================================================

PLANS = TableSchema(
    name="plans",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("name", "TEXT", nullable=False),
        Column("description", "TEXT"),
        Column("created_at", "TEXT", nullable=False),
        Column("status", "TEXT", nullable=False),
        Column("metadata_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        ("idx_plans_status", ["status"]),
        ("idx_plans_created", ["created_at"]),
    ]
)

PLAN_TASKS = TableSchema(
    name="plan_tasks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("plan_id", "INTEGER", nullable=False),
        Column("task_number", "INTEGER", nullable=False),
        Column("title", "TEXT", nullable=False),
        Column("description", "TEXT"),
        Column("status", "TEXT", nullable=False),
        Column("assigned_to", "TEXT"),
        Column("spec_id", "INTEGER"),
        Column("created_at", "TEXT", nullable=False),
        Column("completed_at", "TEXT"),
    ],
    indexes=[
        ("idx_plan_tasks_plan", ["plan_id"]),
        ("idx_plan_tasks_status", ["status"]),
        ("idx_plan_tasks_spec", ["spec_id"]),
    ],
    unique_constraints=[
        ["plan_id", "task_number"]
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["plan_id"],
            foreign_table="plans",
            foreign_columns=["id"]
        ),
        ForeignKey(
            local_columns=["spec_id"],
            foreign_table="plan_specs",
            foreign_columns=["id"]
        ),
    ]
)

PLAN_SPECS = TableSchema(
    name="plan_specs",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("plan_id", "INTEGER", nullable=False),
        Column("spec_yaml", "TEXT", nullable=False),
        Column("spec_type", "TEXT"),
        Column("created_at", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_plan_specs_plan", ["plan_id"]),
        ("idx_plan_specs_type", ["spec_type"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["plan_id"],
            foreign_table="plans",
            foreign_columns=["id"]
        ),
    ]
)

CODE_SNAPSHOTS = TableSchema(
    name="code_snapshots",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("plan_id", "INTEGER", nullable=False),
        Column("task_id", "INTEGER"),
        Column("checkpoint_name", "TEXT", nullable=False),
        Column("timestamp", "TEXT", nullable=False),
        Column("git_ref", "TEXT"),
        Column("files_json", "TEXT", default="'[]'"),
    ],
    indexes=[
        ("idx_code_snapshots_plan", ["plan_id"]),
        ("idx_code_snapshots_task", ["task_id"]),
        ("idx_code_snapshots_timestamp", ["timestamp"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["plan_id"],
            foreign_table="plans",
            foreign_columns=["id"]
        ),
        ForeignKey(
            local_columns=["task_id"],
            foreign_table="plan_tasks",
            foreign_columns=["id"]
        ),
    ]
)

CODE_DIFFS = TableSchema(
    name="code_diffs",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("snapshot_id", "INTEGER", nullable=False),
        Column("file_path", "TEXT", nullable=False),
        Column("diff_text", "TEXT"),
        Column("added_lines", "INTEGER"),
        Column("removed_lines", "INTEGER"),
    ],
    indexes=[
        ("idx_code_diffs_snapshot", ["snapshot_id"]),
        ("idx_code_diffs_file", ["file_path"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["snapshot_id"],
            foreign_table="code_snapshots",
            foreign_columns=["id"]
        ),
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
    "class_properties": CLASS_PROPERTIES,
    "env_var_usage": ENV_VAR_USAGE,
    "orm_relationships": ORM_RELATIONSHIPS,

    # API & routing
    "api_endpoints": API_ENDPOINTS,
    "api_endpoint_controls": API_ENDPOINT_CONTROLS,  # Junction table for normalized controls
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,
    "python_routes": PYTHON_ROUTES,
    "python_blueprints": PYTHON_BLUEPRINTS,
    "python_validators": PYTHON_VALIDATORS,

    # Python Phase 2.2: Advanced patterns
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

    # SQL & database
    "sql_objects": SQL_OBJECTS,
    "sql_queries": SQL_QUERIES,
    "sql_query_tables": SQL_QUERY_TABLES,  # Junction table for normalized table references
    "jwt_patterns": JWT_PATTERNS,
    "orm_queries": ORM_QUERIES,
    "prisma_models": PRISMA_MODELS,

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

    # React
    "react_components": REACT_COMPONENTS,
    "react_component_hooks": REACT_COMPONENT_HOOKS,  # Junction table for normalized hooks_used
    "react_hooks": REACT_HOOKS,
    "react_hook_dependencies": REACT_HOOK_DEPENDENCIES,  # Junction table for normalized dependency_vars

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

    # Terraform (Infrastructure as Code)
    "terraform_files": TERRAFORM_FILES,
    "terraform_resources": TERRAFORM_RESOURCES,
    "terraform_variables": TERRAFORM_VARIABLES,
    "terraform_variable_values": TERRAFORM_VARIABLE_VALUES,
    "terraform_outputs": TERRAFORM_OUTPUTS,
    "terraform_findings": TERRAFORM_FINDINGS,

    # AWS CDK (Infrastructure as Code)
    "cdk_constructs": CDK_CONSTRUCTS,
    "cdk_construct_properties": CDK_CONSTRUCT_PROPERTIES,
    "cdk_findings": CDK_FINDINGS,

    # GitHub Actions (CI/CD Security)
    "github_workflows": GITHUB_WORKFLOWS,
    "github_jobs": GITHUB_JOBS,
    "github_job_dependencies": GITHUB_JOB_DEPENDENCIES,
    "github_steps": GITHUB_STEPS,
    "github_step_outputs": GITHUB_STEP_OUTPUTS,
    "github_step_references": GITHUB_STEP_REFERENCES,

    # Build analysis
    "package_configs": PACKAGE_CONFIGS,
    "lock_analysis": LOCK_ANALYSIS,
    "import_styles": IMPORT_STYLES,
    "import_style_names": IMPORT_STYLE_NAMES,  # Junction table for normalized imported_names

    # Framework detection
    "frameworks": FRAMEWORKS,
    "framework_safe_sinks": FRAMEWORK_SAFE_SINKS,
    "validation_framework_usage": VALIDATION_FRAMEWORK_USAGE,

    # Findings
    "findings_consolidated": FINDINGS_CONSOLIDATED,

    # Planning
    "plans": PLANS,
    "plan_tasks": PLAN_TASKS,
    "plan_specs": PLAN_SPECS,
    "code_snapshots": CODE_SNAPSHOTS,
    "code_diffs": CODE_DIFFS,
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


def build_join_query(
    base_table: str,
    base_columns: List[str],
    join_table: str,
    join_columns: List[str],
    join_on: Optional[List[Tuple[str, str]]] = None,
    aggregate: Optional[Dict[str, str]] = None,
    where: Optional[str] = None,
    group_by: Optional[List[str]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
    join_type: str = "LEFT"
) -> str:
    """Build a JOIN query using schema definitions and foreign keys.

    This function generates SQL JOIN queries with schema validation,
    eliminating the need for raw SQL and enabling type-safe joins.

    Args:
        base_table: Name of the base table (e.g., 'react_hooks')
        base_columns: Columns to select from base table (e.g., ['file', 'line', 'hook_name'])
        join_table: Name of table to join (e.g., 'react_hook_dependencies')
        join_columns: Columns to select/aggregate from join table (e.g., ['dependency_name'])
        join_on: Optional explicit JOIN conditions as (base_col, join_col) tuples.
                 If None, uses foreign key relationship from schema.
        aggregate: Optional aggregation for join columns (e.g., {'dependency_name': 'GROUP_CONCAT'})
        where: Optional WHERE clause (without 'WHERE' keyword)
        group_by: Optional GROUP BY columns (required when using aggregation)
        order_by: Optional ORDER BY clause (without 'ORDER BY' keyword)
        limit: Optional LIMIT clause (just the number)
        join_type: Type of JOIN ('LEFT', 'INNER', 'RIGHT') - default 'LEFT'

    Returns:
        Complete SELECT query string with JOIN

    Example:
        >>> build_join_query(
        ...     base_table='react_hooks',
        ...     base_columns=['file', 'line', 'hook_name'],
        ...     join_table='react_hook_dependencies',
        ...     join_columns=['dependency_name'],
        ...     aggregate={'dependency_name': 'GROUP_CONCAT'},
        ...     group_by=['file', 'line', 'hook_name']
        ... )
        'SELECT rh.file, rh.line, rh.hook_name, GROUP_CONCAT(rhd.dependency_name, '|') as dependency_name_concat FROM react_hooks rh LEFT JOIN react_hook_dependencies rhd ON rh.file = rhd.hook_file AND rh.line = rhd.hook_line AND rh.component_name = rhd.hook_component GROUP BY rh.file, rh.line, rh.hook_name'

    Raises:
        ValueError: If tables don't exist, columns invalid, or foreign key not found
    """
    # Validate tables exist
    if base_table not in TABLES:
        raise ValueError(f"Unknown base table: {base_table}. Available: {', '.join(sorted(TABLES.keys()))}")
    if join_table not in TABLES:
        raise ValueError(f"Unknown join table: {join_table}. Available: {', '.join(sorted(TABLES.keys()))}")

    base_schema = TABLES[base_table]
    join_schema = TABLES[join_table]

    # Validate base columns exist
    base_col_names = set(base_schema.column_names())
    for col in base_columns:
        if col not in base_col_names:
            raise ValueError(
                f"Unknown column '{col}' in base table '{base_table}'. "
                f"Valid columns: {', '.join(sorted(base_col_names))}"
            )

    # Validate join columns exist (unless they're being aggregated)
    join_col_names = set(join_schema.column_names())
    for col in join_columns:
        if col not in join_col_names:
            raise ValueError(
                f"Unknown column '{col}' in join table '{join_table}'. "
                f"Valid columns: {', '.join(sorted(join_col_names))}"
            )

    # Determine JOIN ON conditions
    if join_on is None:
        # Auto-discover from foreign keys
        fk = None
        for foreign_key in join_schema.foreign_keys:
            if foreign_key.foreign_table == base_table:
                fk = foreign_key
                break

        if fk is None:
            raise ValueError(
                f"No foreign key found from '{join_table}' to '{base_table}'. "
                f"Either define foreign_keys in schema or provide explicit join_on parameter."
            )

        # Build JOIN conditions from foreign key
        join_on = list(zip(fk.foreign_columns, fk.local_columns))

    # Validate JOIN ON columns
    for base_col, join_col in join_on:
        if base_col not in base_col_names:
            raise ValueError(f"JOIN ON column '{base_col}' not found in base table '{base_table}'")
        if join_col not in join_col_names:
            raise ValueError(f"JOIN ON column '{join_col}' not found in join table '{join_table}'")

    # Generate table aliases
    base_alias = ''.join([c for c in base_table if c.isalpha()])[:2]  # First 2 letters
    join_alias = ''.join([c for c in join_table if c.isalpha()])[:3]  # First 3 letters

    # Build SELECT clause
    select_parts = [f"{base_alias}.{col}" for col in base_columns]

    if aggregate:
        for col, agg_func in aggregate.items():
            if agg_func == 'GROUP_CONCAT':
                select_parts.append(
                    f"GROUP_CONCAT({join_alias}.{col}, '|') as {col}_concat"
                )
            elif agg_func in ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']:
                select_parts.append(
                    f"{agg_func}({join_alias}.{col}) as {col}_{agg_func.lower()}"
                )
            else:
                raise ValueError(
                    f"Unknown aggregation function '{agg_func}'. "
                    f"Supported: GROUP_CONCAT, COUNT, SUM, AVG, MIN, MAX"
                )
    else:
        # No aggregation - select join columns directly
        select_parts.extend([f"{join_alias}.{col}" for col in join_columns])

    # Build JOIN ON clause
    on_conditions = [
        f"{base_alias}.{base_col} = {join_alias}.{join_col}"
        for base_col, join_col in join_on
    ]
    on_clause = " AND ".join(on_conditions)

    # Assemble query
    query_parts = [
        "SELECT",
        ", ".join(select_parts),
        "FROM",
        f"{base_table} {base_alias}",
        f"{join_type} JOIN",
        f"{join_table} {join_alias}",
        "ON",
        on_clause
    ]

    if where:
        query_parts.extend(["WHERE", where])

    if group_by:
        # Prefix group_by columns with base alias if not already qualified
        qualified_group_by = []
        for col in group_by:
            if '.' not in col:
                qualified_group_by.append(f"{base_alias}.{col}")
            else:
                qualified_group_by.append(col)
        query_parts.extend(["GROUP BY", ", ".join(qualified_group_by)])

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
