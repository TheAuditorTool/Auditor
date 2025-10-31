"""
Database schema definitions - Single Source of Truth.

This module is now a STUB that merges language-specific schema modules.
The actual table definitions have been split into:
- schemas/core_schema.py (21 tables - language-agnostic core patterns)
- schemas/security_schema.py (5 tables - cross-language security patterns)
- schemas/frameworks_schema.py (5 tables - cross-language framework patterns)
- schemas/python_schema.py (34 tables - Python-specific patterns)
- schemas/node_schema.py (17 tables - Node/React/Vue/TypeScript)
- schemas/infrastructure_schema.py (18 tables - Docker/Terraform/CDK/GitHub Actions)
- schemas/planning_schema.py (5 tables - Planning/meta-system)

This stub maintains 100% backward compatibility with all existing imports.

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
import sqlite3

# Import utility classes from schemas/utils.py
from .schemas.utils import Column, ForeignKey, TableSchema

# Import all table registries
from .schemas.core_schema import CORE_TABLES
from .schemas.security_schema import SECURITY_TABLES
from .schemas.frameworks_schema import FRAMEWORKS_TABLES
from .schemas.python_schema import PYTHON_TABLES
from .schemas.node_schema import NODE_TABLES
from .schemas.infrastructure_schema import INFRASTRUCTURE_TABLES
from .schemas.planning_schema import PLANNING_TABLES


# ============================================================================
# SCHEMA REGISTRY - Single source of truth (merged from all modules)
# ============================================================================

TABLES: Dict[str, TableSchema] = {
    **CORE_TABLES,           # 21 tables (language-agnostic core patterns)
    **SECURITY_TABLES,       # 5 tables (SQL, JWT, env vars - cross-language security)
    **FRAMEWORKS_TABLES,     # 5 tables (ORM, API routing - cross-language frameworks)
    **PYTHON_TABLES,         # 34 tables (5 basic + 29 advanced Python patterns)
    **NODE_TABLES,           # 17 tables (React/Vue/TypeScript + build tools)
    **INFRASTRUCTURE_TABLES, # 18 tables (Docker/Terraform/CDK + GitHub Actions)
    **PLANNING_TABLES,       # 5 tables (Planning/meta-system)
}

# Total: 108 tables (24 core [+3 cfg_jsx] + 5 security + 5 frameworks + 34 python + 17 node + 18 infrastructure + 5 planning)

# Verify table count at module load time
assert len(TABLES) == 108, f"Schema contract violation: Expected 108 tables, got {len(TABLES)}"
print(f"[SCHEMA] Loaded {len(TABLES)} tables")


# ============================================================================
# RE-EXPORT INDIVIDUAL TABLE CONSTANTS (Backward Compatibility)
# ============================================================================
# Consumer code and tests may import individual table constants directly.
# Extract all table schemas from the merged registry and export them.
#
# Tables are organized by their source module for maintainability.

# -------------------------
# CORE TABLES (21 tables from schemas/core_schema.py)
# -------------------------
FILES = TABLES['files']
CONFIG_FILES = TABLES['config_files']
REFS = TABLES['refs']
SYMBOLS = TABLES['symbols']
SYMBOLS_JSX = TABLES['symbols_jsx']
ASSIGNMENTS = TABLES['assignments']
ASSIGNMENTS_JSX = TABLES['assignments_jsx']
ASSIGNMENT_SOURCES = TABLES['assignment_sources']
ASSIGNMENT_SOURCES_JSX = TABLES['assignment_sources_jsx']
FUNCTION_CALL_ARGS = TABLES['function_call_args']
FUNCTION_CALL_ARGS_JSX = TABLES['function_call_args_jsx']
FUNCTION_RETURNS = TABLES['function_returns']
FUNCTION_RETURNS_JSX = TABLES['function_returns_jsx']
FUNCTION_RETURN_SOURCES = TABLES['function_return_sources']
FUNCTION_RETURN_SOURCES_JSX = TABLES['function_return_sources_jsx']
VARIABLE_USAGE = TABLES['variable_usage']
OBJECT_LITERALS = TABLES['object_literals']
CFG_BLOCKS = TABLES['cfg_blocks']
CFG_EDGES = TABLES['cfg_edges']
CFG_BLOCK_STATEMENTS = TABLES['cfg_block_statements']
FINDINGS_CONSOLIDATED = TABLES['findings_consolidated']

# -------------------------
# SECURITY TABLES (5 tables from schemas/security_schema.py)
# -------------------------
SQL_OBJECTS = TABLES['sql_objects']
SQL_QUERIES = TABLES['sql_queries']
SQL_QUERY_TABLES = TABLES['sql_query_tables']
JWT_PATTERNS = TABLES['jwt_patterns']
ENV_VAR_USAGE = TABLES['env_var_usage']

# -------------------------
# FRAMEWORK TABLES (5 tables from schemas/frameworks_schema.py)
# -------------------------
ORM_QUERIES = TABLES['orm_queries']
ORM_RELATIONSHIPS = TABLES['orm_relationships']
PRISMA_MODELS = TABLES['prisma_models']
API_ENDPOINTS = TABLES['api_endpoints']
API_ENDPOINT_CONTROLS = TABLES['api_endpoint_controls']

# -------------------------
# PYTHON TABLES (34 tables from schemas/python_schema.py)
# -------------------------
# Flask/FastAPI/Django ORM
PYTHON_ORM_MODELS = TABLES['python_orm_models']
PYTHON_ORM_FIELDS = TABLES['python_orm_fields']
PYTHON_ROUTES = TABLES['python_routes']
PYTHON_BLUEPRINTS = TABLES['python_blueprints']
PYTHON_VALIDATORS = TABLES['python_validators']

# Python language features
PYTHON_DECORATORS = TABLES['python_decorators']
PYTHON_CONTEXT_MANAGERS = TABLES['python_context_managers']
PYTHON_ASYNC_FUNCTIONS = TABLES['python_async_functions']
PYTHON_AWAIT_EXPRESSIONS = TABLES['python_await_expressions']
PYTHON_ASYNC_GENERATORS = TABLES['python_async_generators']
PYTHON_GENERATORS = TABLES['python_generators']

# Pytest patterns
PYTHON_PYTEST_FIXTURES = TABLES['python_pytest_fixtures']
PYTHON_PYTEST_PARAMETRIZE = TABLES['python_pytest_parametrize']
PYTHON_PYTEST_MARKERS = TABLES['python_pytest_markers']
PYTHON_MOCK_PATTERNS = TABLES['python_mock_patterns']

# Type system
PYTHON_PROTOCOLS = TABLES['python_protocols']
PYTHON_GENERICS = TABLES['python_generics']
PYTHON_TYPED_DICTS = TABLES['python_typed_dicts']
PYTHON_LITERALS = TABLES['python_literals']
PYTHON_OVERLOADS = TABLES['python_overloads']

# Django framework
PYTHON_DJANGO_VIEWS = TABLES['python_django_views']
PYTHON_DJANGO_FORMS = TABLES['python_django_forms']
PYTHON_DJANGO_FORM_FIELDS = TABLES['python_django_form_fields']
PYTHON_DJANGO_ADMIN = TABLES['python_django_admin']
PYTHON_DJANGO_MIDDLEWARE = TABLES['python_django_middleware']

# Marshmallow framework
PYTHON_MARSHMALLOW_SCHEMAS = TABLES['python_marshmallow_schemas']
PYTHON_MARSHMALLOW_FIELDS = TABLES['python_marshmallow_fields']

# Django REST Framework
PYTHON_DRF_SERIALIZERS = TABLES['python_drf_serializers']
PYTHON_DRF_SERIALIZER_FIELDS = TABLES['python_drf_serializer_fields']

# WTForms framework
PYTHON_WTFORMS_FORMS = TABLES['python_wtforms_forms']
PYTHON_WTFORMS_FIELDS = TABLES['python_wtforms_fields']

# Celery framework
PYTHON_CELERY_TASKS = TABLES['python_celery_tasks']
PYTHON_CELERY_TASK_CALLS = TABLES['python_celery_task_calls']
PYTHON_CELERY_BEAT_SCHEDULES = TABLES['python_celery_beat_schedules']

# -------------------------
# NODE TABLES (17 tables from schemas/node_schema.py)
# -------------------------
CLASS_PROPERTIES = TABLES['class_properties']
TYPE_ANNOTATIONS = TABLES['type_annotations']

# React framework
REACT_COMPONENTS = TABLES['react_components']
REACT_COMPONENT_HOOKS = TABLES['react_component_hooks']
REACT_HOOKS = TABLES['react_hooks']
REACT_HOOK_DEPENDENCIES = TABLES['react_hook_dependencies']

# Vue framework
VUE_COMPONENTS = TABLES['vue_components']
VUE_HOOKS = TABLES['vue_hooks']
VUE_DIRECTIVES = TABLES['vue_directives']
VUE_PROVIDE_INJECT = TABLES['vue_provide_inject']

# Package management
PACKAGE_CONFIGS = TABLES['package_configs']
LOCK_ANALYSIS = TABLES['lock_analysis']
IMPORT_STYLES = TABLES['import_styles']
IMPORT_STYLE_NAMES = TABLES['import_style_names']

# Framework detection
FRAMEWORKS = TABLES['frameworks']
FRAMEWORK_SAFE_SINKS = TABLES['framework_safe_sinks']
VALIDATION_FRAMEWORK_USAGE = TABLES['validation_framework_usage']

# -------------------------
# INFRASTRUCTURE TABLES (18 tables from schemas/infrastructure_schema.py)
# -------------------------
# Docker
DOCKER_IMAGES = TABLES['docker_images']
COMPOSE_SERVICES = TABLES['compose_services']
NGINX_CONFIGS = TABLES['nginx_configs']

# Terraform
TERRAFORM_FILES = TABLES['terraform_files']
TERRAFORM_RESOURCES = TABLES['terraform_resources']
TERRAFORM_VARIABLES = TABLES['terraform_variables']
TERRAFORM_VARIABLE_VALUES = TABLES['terraform_variable_values']
TERRAFORM_OUTPUTS = TABLES['terraform_outputs']
TERRAFORM_FINDINGS = TABLES['terraform_findings']

# AWS CDK
CDK_CONSTRUCTS = TABLES['cdk_constructs']
CDK_CONSTRUCT_PROPERTIES = TABLES['cdk_construct_properties']
CDK_FINDINGS = TABLES['cdk_findings']

# GitHub Actions
GITHUB_WORKFLOWS = TABLES['github_workflows']
GITHUB_JOBS = TABLES['github_jobs']
GITHUB_JOB_DEPENDENCIES = TABLES['github_job_dependencies']
GITHUB_STEPS = TABLES['github_steps']
GITHUB_STEP_OUTPUTS = TABLES['github_step_outputs']
GITHUB_STEP_REFERENCES = TABLES['github_step_references']

# -------------------------
# PLANNING TABLES (5 tables from schemas/planning_schema.py)
# -------------------------
PLANS = TABLES['plans']
PLAN_TASKS = TABLES['plan_tasks']
PLAN_SPECS = TABLES['plan_specs']
CODE_SNAPSHOTS = TABLES['code_snapshots']
CODE_DIFFS = TABLES['code_diffs']


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
    print("TheAuditor Database Schema Contract (STUB)")
    print("=" * 80)
    print(f"\nTotal tables defined: {len(TABLES)}")
    print("\nTable breakdown:")
    print(f"  Core tables:           {len(CORE_TABLES)} (language-agnostic)")
    print(f"  Python tables:         {len(PYTHON_TABLES)} (Flask/Django/SQLAlchemy)")
    print(f"  Node tables:           {len(NODE_TABLES)} (React/Vue/TypeScript)")
    print(f"  Infrastructure tables: {len(INFRASTRUCTURE_TABLES)} (Docker/Terraform/CDK)")
    print(f"  Planning tables:       {len(PLANNING_TABLES)} (Meta-system)")
    print("\nAll tables:")
    for table_name in sorted(TABLES.keys()):
        schema = TABLES[table_name]
        print(f"  - {table_name}: {len(schema.columns)} columns")

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
    print("Schema stub loaded successfully!")
    print("=" * 80)
