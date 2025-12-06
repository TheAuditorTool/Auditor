"""Database schema definitions - Single Source of Truth."""

import sqlite3

from theauditor.utils.logging import logger

from .schemas.bash_schema import BASH_TABLES
from .schemas.core_schema import CORE_TABLES
from .schemas.frameworks_schema import FRAMEWORKS_TABLES
from .schemas.go_schema import GO_TABLES
from .schemas.graphql_schema import GRAPHQL_TABLES
from .schemas.infrastructure_schema import INFRASTRUCTURE_TABLES
from .schemas.node_schema import NODE_TABLES
from .schemas.planning_schema import PLANNING_TABLES
from .schemas.python_schema import PYTHON_TABLES
from .schemas.rust_schema import RUST_TABLES
from .schemas.security_schema import SECURITY_TABLES
from .schemas.utils import TableSchema

TABLES: dict[str, TableSchema] = {
    **CORE_TABLES,
    **SECURITY_TABLES,
    **FRAMEWORKS_TABLES,
    **PYTHON_TABLES,
    **NODE_TABLES,
    **RUST_TABLES,
    **GO_TABLES,
    **BASH_TABLES,
    **INFRASTRUCTURE_TABLES,
    **PLANNING_TABLES,
    **GRAPHQL_TABLES,
}


FLUSH_ORDER: list[tuple[str, str]] = [
    ("files", "INSERT OR REPLACE"),
    ("config_files", "INSERT OR REPLACE"),
    ("plans", "INSERT"),
    ("plan_specs", "INSERT"),
    ("plan_tasks", "INSERT"),
    ("code_snapshots", "INSERT"),
    ("code_diffs", "INSERT"),
    ("refactor_candidates", "INSERT"),
    ("refactor_history", "INSERT"),
    ("refs", "INSERT"),
    ("symbols", "INSERT"),
    ("class_properties", "INSERT"),
    ("env_var_usage", "INSERT"),
    ("orm_relationships", "INSERT"),
    ("sql_objects", "INSERT"),
    ("sql_queries", "INSERT"),
    ("orm_queries", "INSERT"),
    ("prisma_models", "INSERT"),
    ("api_endpoints", "INSERT"),
    ("router_mounts", "INSERT"),
    ("api_endpoint_controls", "INSERT"),
    ("express_middleware_chains", "INSERT"),
    ("validation_framework_usage", "INSERT"),
    ("python_orm_models", "INSERT"),
    ("python_orm_fields", "INSERT"),
    ("python_routes", "INSERT"),
    ("python_validators", "INSERT"),
    ("python_package_configs", "INSERT"),
    ("python_package_dependencies", "INSERT"),
    ("python_build_requires", "INSERT"),
    ("python_decorators", "INSERT"),
    ("python_django_views", "INSERT"),
    ("python_django_middleware", "INSERT"),
    ("python_loops", "INSERT"),
    ("python_branches", "INSERT"),
    ("python_functions_advanced", "INSERT"),
    ("python_io_operations", "INSERT"),
    ("python_state_mutations", "INSERT"),
    ("python_class_features", "INSERT"),
    ("python_protocols", "INSERT"),
    ("python_descriptors", "INSERT"),
    ("python_type_definitions", "INSERT"),
    ("python_literals", "INSERT"),
    ("python_protocol_methods", "INSERT"),
    ("python_typeddict_fields", "INSERT"),
    ("python_security_findings", "INSERT"),
    ("python_test_cases", "INSERT"),
    ("python_test_fixtures", "INSERT"),
    ("python_framework_config", "INSERT"),
    ("python_validation_schemas", "INSERT"),
    ("python_fixture_params", "INSERT"),
    ("python_framework_methods", "INSERT"),
    ("python_schema_validators", "INSERT"),
    ("python_operators", "INSERT"),
    ("python_collections", "INSERT"),
    ("python_stdlib_usage", "INSERT"),
    ("python_imports_advanced", "INSERT"),
    ("python_expressions", "INSERT"),
    ("python_comprehensions", "INSERT"),
    ("python_control_statements", "INSERT"),
    ("sql_query_tables", "INSERT"),
    ("docker_images", "INSERT"),
    ("dockerfile_ports", "INSERT"),
    ("dockerfile_env_vars", "INSERT"),
    ("compose_services", "INSERT"),
    ("compose_service_ports", "INSERT"),
    ("compose_service_volumes", "INSERT"),
    ("compose_service_env", "INSERT"),
    ("compose_service_capabilities", "INSERT"),
    ("compose_service_deps", "INSERT"),
    ("nginx_configs", "INSERT"),
    ("terraform_files", "INSERT"),
    ("terraform_resources", "INSERT"),
    ("terraform_resource_properties", "INSERT"),
    ("terraform_resource_deps", "INSERT"),
    ("terraform_variables", "INSERT"),
    ("terraform_variable_values", "INSERT"),
    ("terraform_outputs", "INSERT"),
    ("terraform_data_sources", "INSERT"),
    ("terraform_findings", "INSERT"),
    ("cdk_constructs", "INSERT"),
    ("cdk_construct_properties", "INSERT"),
    ("cdk_findings", "INSERT"),
    ("graphql_schemas", "INSERT"),
    ("graphql_types", "INSERT"),
    ("graphql_fields", "INSERT"),
    ("graphql_field_directives", "INSERT"),
    ("graphql_field_args", "INSERT"),
    ("graphql_arg_directives", "INSERT"),
    ("graphql_resolver_mappings", "INSERT"),
    ("graphql_resolver_params", "INSERT"),
    ("graphql_execution_edges", "INSERT"),
    ("graphql_findings_cache", "INSERT"),
    ("github_workflows", "INSERT"),
    ("github_jobs", "INSERT"),
    ("github_job_dependencies", "INSERT"),
    ("github_steps", "INSERT"),
    ("github_step_outputs", "INSERT"),
    ("github_step_references", "INSERT"),
    ("rust_modules", "INSERT"),
    ("rust_use_statements", "INSERT"),
    ("rust_functions", "INSERT"),
    ("rust_structs", "INSERT"),
    ("rust_enums", "INSERT"),
    ("rust_traits", "INSERT"),
    ("rust_impl_blocks", "INSERT"),
    ("rust_generics", "INSERT"),
    ("rust_lifetimes", "INSERT"),
    ("rust_macros", "INSERT"),
    ("rust_macro_invocations", "INSERT"),
    ("rust_attributes", "INSERT"),
    ("rust_async_functions", "INSERT"),
    ("rust_await_points", "INSERT"),
    ("rust_unsafe_blocks", "INSERT"),
    ("rust_unsafe_traits", "INSERT"),
    ("rust_struct_fields", "INSERT"),
    ("rust_enum_variants", "INSERT"),
    ("rust_trait_methods", "INSERT"),
    ("rust_extern_functions", "INSERT"),
    ("rust_extern_blocks", "INSERT"),
    ("cargo_package_configs", "INSERT"),
    ("cargo_dependencies", "INSERT"),
    ("go_packages", "INSERT"),
    ("go_imports", "INSERT"),
    ("go_structs", "INSERT"),
    ("go_struct_fields", "INSERT"),
    ("go_interfaces", "INSERT"),
    ("go_interface_methods", "INSERT"),
    ("go_functions", "INSERT"),
    ("go_methods", "INSERT"),
    ("go_func_params", "INSERT"),
    ("go_func_returns", "INSERT"),
    ("go_goroutines", "INSERT"),
    ("go_channels", "INSERT"),
    ("go_channel_ops", "INSERT"),
    ("go_defer_statements", "INSERT"),
    ("go_error_returns", "INSERT"),
    ("go_type_assertions", "INSERT"),
    ("go_routes", "INSERT"),
    ("go_constants", "INSERT"),
    ("go_variables", "INSERT"),
    ("go_type_params", "INSERT"),
    ("go_captured_vars", "INSERT"),
    ("go_middleware", "INSERT"),
    ("go_module_configs", "INSERT"),
    ("go_module_dependencies", "INSERT"),
    ("bash_functions", "INSERT"),
    ("bash_variables", "INSERT"),
    ("bash_sources", "INSERT"),
    ("bash_commands", "INSERT"),
    ("bash_command_args", "INSERT"),
    ("bash_pipes", "INSERT"),
    ("bash_subshells", "INSERT"),
    ("bash_redirections", "INSERT"),
    ("bash_control_flows", "INSERT"),
    ("bash_set_options", "INSERT"),
    ("assignments", "INSERT"),
    ("assignment_sources", "INSERT"),
    ("function_call_args", "INSERT"),
    ("function_returns", "INSERT"),
    ("function_return_sources", "INSERT"),
    ("react_components", "INSERT"),
    ("react_component_hooks", "INSERT"),
    ("react_hooks", "INSERT"),
    ("react_hook_dependencies", "INSERT"),
    ("variable_usage", "INSERT"),
    ("object_literals", "INSERT"),
    ("function_returns_jsx", "INSERT OR REPLACE"),
    ("function_return_sources_jsx", "INSERT"),
    ("symbols_jsx", "INSERT OR REPLACE"),
    ("assignments_jsx", "INSERT OR REPLACE"),
    ("assignment_sources_jsx", "INSERT"),
    ("function_call_args_jsx", "INSERT OR REPLACE"),
    ("vue_components", "INSERT"),
    ("vue_hooks", "INSERT"),
    ("vue_directives", "INSERT"),
    ("vue_provide_inject", "INSERT"),
    ("type_annotations", "INSERT OR REPLACE"),
    ("package_configs", "INSERT OR REPLACE"),
    ("package_dependencies", "INSERT"),
    ("package_scripts", "INSERT"),
    ("package_engines", "INSERT"),
    ("package_workspaces", "INSERT"),
    ("lock_analysis", "INSERT OR REPLACE"),
    ("import_styles", "INSERT"),
    ("import_style_names", "INSERT"),
    ("func_params", "INSERT"),
    ("func_decorators", "INSERT"),
    ("func_decorator_args", "INSERT"),
    ("func_param_decorators", "INSERT"),
    ("class_decorators", "INSERT"),
    ("class_decorator_args", "INSERT"),
    ("assignment_source_vars", "INSERT"),
    ("return_source_vars", "INSERT"),
    ("import_specifiers", "INSERT"),
    ("sequelize_models", "INSERT"),
    ("sequelize_model_fields", "INSERT"),
    ("sequelize_associations", "INSERT"),
    ("angular_components", "INSERT"),
    ("angular_modules", "INSERT"),
    ("angular_services", "INSERT"),
    ("angular_guards", "INSERT"),
    ("plan_jobs", "INSERT"),
    ("plan_phases", "INSERT"),
    ("frameworks", "INSERT OR IGNORE"),
    ("framework_safe_sinks", "INSERT OR IGNORE"),
    ("framework_taint_patterns", "INSERT OR IGNORE"),
]


def validate_schema_contract() -> list[str]:
    """Validate schema contract - all flush_order tables must exist in TABLES.

    Returns list of errors. Empty list means valid.
    """
    errors = []

    for table_name, _ in FLUSH_ORDER:
        if table_name not in TABLES:
            errors.append(f"FLUSH_ORDER table '{table_name}' missing from TABLES schema")

    return errors


_contract_errors = validate_schema_contract()
if _contract_errors:
    raise RuntimeError(
        "Schema contract violation:\n" + "\n".join(f"  - {e}" for e in _contract_errors)
    )


FILES = TABLES["files"]
CONFIG_FILES = TABLES["config_files"]
REFS = TABLES["refs"]
SYMBOLS = TABLES["symbols"]
SYMBOLS_JSX = TABLES["symbols_jsx"]
ASSIGNMENTS = TABLES["assignments"]
ASSIGNMENTS_JSX = TABLES["assignments_jsx"]
ASSIGNMENT_SOURCES = TABLES["assignment_sources"]
ASSIGNMENT_SOURCES_JSX = TABLES["assignment_sources_jsx"]
FUNCTION_CALL_ARGS = TABLES["function_call_args"]
FUNCTION_CALL_ARGS_JSX = TABLES["function_call_args_jsx"]
FUNCTION_RETURNS = TABLES["function_returns"]
FUNCTION_RETURNS_JSX = TABLES["function_returns_jsx"]
FUNCTION_RETURN_SOURCES = TABLES["function_return_sources"]
FUNCTION_RETURN_SOURCES_JSX = TABLES["function_return_sources_jsx"]
VARIABLE_USAGE = TABLES["variable_usage"]
OBJECT_LITERALS = TABLES["object_literals"]
CFG_BLOCKS = TABLES["cfg_blocks"]
CFG_EDGES = TABLES["cfg_edges"]
CFG_BLOCK_STATEMENTS = TABLES["cfg_block_statements"]
FINDINGS_CONSOLIDATED = TABLES["findings_consolidated"]


SQL_OBJECTS = TABLES["sql_objects"]
SQL_QUERIES = TABLES["sql_queries"]
SQL_QUERY_TABLES = TABLES["sql_query_tables"]
JWT_PATTERNS = TABLES["jwt_patterns"]
ENV_VAR_USAGE = TABLES["env_var_usage"]
TAINT_FLOWS = TABLES["taint_flows"]
RESOLVED_FLOW_AUDIT = TABLES["resolved_flow_audit"]


ORM_QUERIES = TABLES["orm_queries"]
ORM_RELATIONSHIPS = TABLES["orm_relationships"]
PRISMA_MODELS = TABLES["prisma_models"]
API_ENDPOINTS = TABLES["api_endpoints"]
API_ENDPOINT_CONTROLS = TABLES["api_endpoint_controls"]


PYTHON_ORM_MODELS = TABLES["python_orm_models"]
PYTHON_ORM_FIELDS = TABLES["python_orm_fields"]


PYTHON_ROUTES = TABLES["python_routes"]


PYTHON_VALIDATORS = TABLES["python_validators"]


PYTHON_PACKAGE_CONFIGS = TABLES["python_package_configs"]


PYTHON_DECORATORS = TABLES["python_decorators"]


PYTHON_DJANGO_VIEWS = TABLES["python_django_views"]
PYTHON_DJANGO_MIDDLEWARE = TABLES["python_django_middleware"]


PYTHON_LOOPS = TABLES["python_loops"]
PYTHON_BRANCHES = TABLES["python_branches"]
PYTHON_FUNCTIONS_ADVANCED = TABLES["python_functions_advanced"]
PYTHON_IO_OPERATIONS = TABLES["python_io_operations"]
PYTHON_STATE_MUTATIONS = TABLES["python_state_mutations"]


PYTHON_CLASS_FEATURES = TABLES["python_class_features"]
PYTHON_PROTOCOLS = TABLES["python_protocols"]
PYTHON_DESCRIPTORS = TABLES["python_descriptors"]
PYTHON_TYPE_DEFINITIONS = TABLES["python_type_definitions"]
PYTHON_LITERALS = TABLES["python_literals"]


PYTHON_SECURITY_FINDINGS = TABLES["python_security_findings"]
PYTHON_TEST_CASES = TABLES["python_test_cases"]
PYTHON_TEST_FIXTURES = TABLES["python_test_fixtures"]
PYTHON_FRAMEWORK_CONFIG = TABLES["python_framework_config"]
PYTHON_VALIDATION_SCHEMAS = TABLES["python_validation_schemas"]


PYTHON_OPERATORS = TABLES["python_operators"]
PYTHON_COLLECTIONS = TABLES["python_collections"]
PYTHON_STDLIB_USAGE = TABLES["python_stdlib_usage"]
PYTHON_IMPORTS_ADVANCED = TABLES["python_imports_advanced"]
PYTHON_EXPRESSIONS = TABLES["python_expressions"]


PYTHON_COMPREHENSIONS = TABLES["python_comprehensions"]
PYTHON_CONTROL_STATEMENTS = TABLES["python_control_statements"]


CLASS_PROPERTIES = TABLES["class_properties"]
TYPE_ANNOTATIONS = TABLES["type_annotations"]


REACT_COMPONENTS = TABLES["react_components"]
REACT_COMPONENT_HOOKS = TABLES["react_component_hooks"]
REACT_HOOKS = TABLES["react_hooks"]
REACT_HOOK_DEPENDENCIES = TABLES["react_hook_dependencies"]


VUE_COMPONENTS = TABLES["vue_components"]
VUE_HOOKS = TABLES["vue_hooks"]
VUE_DIRECTIVES = TABLES["vue_directives"]
VUE_PROVIDE_INJECT = TABLES["vue_provide_inject"]


PACKAGE_CONFIGS = TABLES["package_configs"]
DEPENDENCY_VERSIONS = TABLES["dependency_versions"]
LOCK_ANALYSIS = TABLES["lock_analysis"]
IMPORT_STYLES = TABLES["import_styles"]
IMPORT_STYLE_NAMES = TABLES["import_style_names"]


FRAMEWORKS = TABLES["frameworks"]
FRAMEWORK_SAFE_SINKS = TABLES["framework_safe_sinks"]
VALIDATION_FRAMEWORK_USAGE = TABLES["validation_framework_usage"]


EXPRESS_MIDDLEWARE_CHAINS = TABLES["express_middleware_chains"]


FRONTEND_API_CALLS = TABLES["frontend_api_calls"]


DOCKER_IMAGES = TABLES["docker_images"]
COMPOSE_SERVICES = TABLES["compose_services"]
NGINX_CONFIGS = TABLES["nginx_configs"]


TERRAFORM_FILES = TABLES["terraform_files"]
TERRAFORM_RESOURCES = TABLES["terraform_resources"]
TERRAFORM_VARIABLES = TABLES["terraform_variables"]
TERRAFORM_VARIABLE_VALUES = TABLES["terraform_variable_values"]
TERRAFORM_OUTPUTS = TABLES["terraform_outputs"]
TERRAFORM_FINDINGS = TABLES["terraform_findings"]


CDK_CONSTRUCTS = TABLES["cdk_constructs"]
CDK_CONSTRUCT_PROPERTIES = TABLES["cdk_construct_properties"]
CDK_FINDINGS = TABLES["cdk_findings"]


GITHUB_WORKFLOWS = TABLES["github_workflows"]
GITHUB_JOBS = TABLES["github_jobs"]
GITHUB_JOB_DEPENDENCIES = TABLES["github_job_dependencies"]
GITHUB_STEPS = TABLES["github_steps"]
GITHUB_STEP_OUTPUTS = TABLES["github_step_outputs"]
GITHUB_STEP_REFERENCES = TABLES["github_step_references"]


PLANS = TABLES["plans"]
PLAN_TASKS = TABLES["plan_tasks"]
PLAN_SPECS = TABLES["plan_specs"]
CODE_SNAPSHOTS = TABLES["code_snapshots"]
CODE_DIFFS = TABLES["code_diffs"]


def build_query(
    table_name: str,
    columns: list[str] | None = None,
    where: str | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> str:
    """Build a SELECT query using schema definitions."""
    if table_name not in TABLES:
        raise ValueError(
            f"Unknown table: {table_name}. Available tables: {', '.join(sorted(TABLES.keys()))}"
        )

    schema = TABLES[table_name]

    if columns is None:
        columns = schema.column_names()
    else:
        valid_cols = set(schema.column_names())
        for col in columns:
            if col not in valid_cols:
                raise ValueError(
                    f"Unknown column '{col}' in table '{table_name}'. "
                    f"Valid columns: {', '.join(sorted(valid_cols))}"
                )

    query_parts = ["SELECT", ", ".join(columns), "FROM", table_name]

    if where:
        query_parts.extend(["WHERE", where])

    if order_by:
        query_parts.extend(["ORDER BY", order_by])

    if limit is not None:
        query_parts.extend(["LIMIT", str(limit)])

    return " ".join(query_parts)


def build_join_query(
    base_table: str,
    base_columns: list[str],
    join_table: str,
    join_columns: list[str],
    join_on: list[tuple[str, str]] | None = None,
    aggregate: dict[str, str] | None = None,
    where: str | None = None,
    group_by: list[str] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    join_type: str = "LEFT",
) -> str:
    """Build a JOIN query using schema definitions and foreign keys."""

    if base_table not in TABLES:
        raise ValueError(
            f"Unknown base table: {base_table}. Available: {', '.join(sorted(TABLES.keys()))}"
        )
    if join_table not in TABLES:
        raise ValueError(
            f"Unknown join table: {join_table}. Available: {', '.join(sorted(TABLES.keys()))}"
        )

    base_schema = TABLES[base_table]
    join_schema = TABLES[join_table]

    base_col_names = set(base_schema.column_names())
    for col in base_columns:
        if col not in base_col_names:
            raise ValueError(
                f"Unknown column '{col}' in base table '{base_table}'. "
                f"Valid columns: {', '.join(sorted(base_col_names))}"
            )

    join_col_names = set(join_schema.column_names())
    for col in join_columns:
        if col not in join_col_names:
            raise ValueError(
                f"Unknown column '{col}' in join table '{join_table}'. "
                f"Valid columns: {', '.join(sorted(join_col_names))}"
            )

    if join_on is None:
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

        join_on = list(zip(fk.foreign_columns, fk.local_columns, strict=True))

    for base_col, join_col in join_on:
        if base_col not in base_col_names:
            raise ValueError(f"JOIN ON column '{base_col}' not found in base table '{base_table}'")
        if join_col not in join_col_names:
            raise ValueError(f"JOIN ON column '{join_col}' not found in join table '{join_table}'")

    base_alias = "".join([c for c in base_table if c.isalpha()])[:2]
    join_alias = "".join([c for c in join_table if c.isalpha()])[:3]

    select_parts = [f"{base_alias}.{col}" for col in base_columns]

    if aggregate:
        for col, agg_func in aggregate.items():
            if agg_func == "GROUP_CONCAT":
                select_parts.append(f"GROUP_CONCAT({join_alias}.{col}, '|') as {col}_concat")
            elif agg_func in ["COUNT", "SUM", "AVG", "MIN", "MAX"]:
                select_parts.append(f"{agg_func}({join_alias}.{col}) as {col}_{agg_func.lower()}")
            else:
                raise ValueError(
                    f"Unknown aggregation function '{agg_func}'. "
                    f"Supported: GROUP_CONCAT, COUNT, SUM, AVG, MIN, MAX"
                )
    else:
        select_parts.extend([f"{join_alias}.{col}" for col in join_columns])

    on_conditions = [
        f"{base_alias}.{base_col} = {join_alias}.{join_col}" for base_col, join_col in join_on
    ]
    on_clause = " AND ".join(on_conditions)

    query_parts = [
        "SELECT",
        ", ".join(select_parts),
        "FROM",
        f"{base_table} {base_alias}",
        f"{join_type} JOIN",
        f"{join_table} {join_alias}",
        "ON",
        on_clause,
    ]

    if where:
        query_parts.extend(["WHERE", where])

    if group_by:
        qualified_group_by = []
        for col in group_by:
            if "." not in col:
                qualified_group_by.append(f"{base_alias}.{col}")
            else:
                qualified_group_by.append(col)
        query_parts.extend(["GROUP BY", ", ".join(qualified_group_by)])

    if order_by:
        query_parts.extend(["ORDER BY", order_by])

    if limit is not None:
        query_parts.extend(["LIMIT", str(limit)])

    return " ".join(query_parts)


def validate_all_tables(cursor: sqlite3.Cursor) -> dict[str, list[str]]:
    """Validate all table schemas against actual database."""
    results = {}
    for table_name, schema in TABLES.items():
        is_valid, errors = schema.validate_against_db(cursor)
        if not is_valid:
            results[table_name] = errors
    return results


def get_table_schema(table_name: str) -> TableSchema:
    """Get schema for a specific table."""
    if table_name not in TABLES:
        raise ValueError(
            f"Unknown table: {table_name}. Available tables: {', '.join(sorted(TABLES.keys()))}"
        )
    return TABLES[table_name]


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("TheAuditor Database Schema Contract (STUB)")
    logger.info("=" * 80)
    logger.info(f"\nTotal tables defined: {len(TABLES)}")
    logger.info("\nTable breakdown:")
    logger.info(f"  Core tables:           {len(CORE_TABLES)} (language-agnostic)")
    logger.info(f"  Python tables:         {len(PYTHON_TABLES)} (Flask/Django/SQLAlchemy)")
    logger.info(f"  Node tables:           {len(NODE_TABLES)} (React/Vue/TypeScript)")
    logger.info(f"  Infrastructure tables: {len(INFRASTRUCTURE_TABLES)} (Docker/Terraform/CDK)")
    logger.info(f"  Planning tables:       {len(PLANNING_TABLES)} (Meta-system)")
    logger.info("\nAll tables:")
    for table_name in sorted(TABLES.keys()):
        schema = TABLES[table_name]
        logger.info(f"  - {table_name}: {len(schema.columns)} columns")

    logger.info("\n" + "=" * 80)
    logger.info("Query Builder Examples:")
    logger.info("=" * 80)

    query1 = build_query("variable_usage", ["file", "line", "variable_name"])
    logger.info(f"\nExample 1:\n  {query1}")

    query2 = build_query(
        "sql_queries", where="command != 'UNKNOWN'", order_by="file_path, line_number"
    )
    logger.info(f"\nExample 2:\n  {query2}")

    query3 = build_query("function_returns")
    logger.info(f"\nExample 3 (all columns):\n  {query3}")

    logger.info("\n" + "=" * 80)
    logger.info("Schema stub loaded successfully!")
    logger.info("=" * 80)
