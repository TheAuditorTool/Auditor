# Auto-generated TypedDict definitions from schema
from typing import TypedDict, Optional, Any

class AngularComponentsRow(TypedDict):
    """Row type for angular_components table."""
    file: str
    line: int
    component_name: str
    selector: Optional[str]
    template_path: Optional[str]
    style_paths: Optional[str]
    has_lifecycle_hooks: Optional[bool]

class AngularGuardsRow(TypedDict):
    """Row type for angular_guards table."""
    file: str
    line: int
    guard_name: str
    guard_type: str
    implements_interface: Optional[str]

class AngularModulesRow(TypedDict):
    """Row type for angular_modules table."""
    file: str
    line: int
    module_name: str
    declarations: Optional[str]
    imports: Optional[str]
    providers: Optional[str]
    exports: Optional[str]

class AngularServicesRow(TypedDict):
    """Row type for angular_services table."""
    file: str
    line: int
    service_name: str
    is_injectable: Optional[bool]
    provided_in: Optional[str]

class ApiEndpointControlsRow(TypedDict):
    """Row type for api_endpoint_controls table."""
    id: int
    endpoint_file: str
    endpoint_line: int
    control_name: str

class ApiEndpointsRow(TypedDict):
    """Row type for api_endpoints table."""
    file: str
    line: Optional[int]
    method: str
    pattern: str
    path: Optional[str]
    full_path: Optional[str]
    has_auth: Optional[bool]
    handler_function: Optional[str]

class AssignmentSourcesRow(TypedDict):
    """Row type for assignment_sources table."""
    id: int
    assignment_file: str
    assignment_line: int
    assignment_target: str
    source_var_name: str

class AssignmentSourcesJsxRow(TypedDict):
    """Row type for assignment_sources_jsx table."""
    id: int
    assignment_file: str
    assignment_line: int
    assignment_target: str
    jsx_mode: str
    source_var_name: str

class AssignmentsRow(TypedDict):
    """Row type for assignments table."""
    file: str
    line: int
    target_var: str
    source_expr: str
    in_function: str
    property_path: Optional[str]

class AssignmentsJsxRow(TypedDict):
    """Row type for assignments_jsx table."""
    file: str
    line: int
    target_var: str
    source_expr: str
    in_function: str
    property_path: Optional[str]
    jsx_mode: str
    extraction_pass: Optional[int]

class BullmqQueuesRow(TypedDict):
    """Row type for bullmq_queues table."""
    file: str
    line: int
    queue_name: str
    redis_config: Optional[str]

class BullmqWorkersRow(TypedDict):
    """Row type for bullmq_workers table."""
    file: str
    line: int
    queue_name: str
    worker_function: Optional[str]
    processor_path: Optional[str]

class CdkConstructPropertiesRow(TypedDict):
    """Row type for cdk_construct_properties table."""
    id: int
    construct_id: str
    property_name: str
    property_value_expr: str
    line: int

class CdkConstructsRow(TypedDict):
    """Row type for cdk_constructs table."""
    construct_id: str
    file_path: str
    line: int
    cdk_class: str
    construct_name: Optional[str]

class CdkFindingsRow(TypedDict):
    """Row type for cdk_findings table."""
    finding_id: str
    file_path: str
    construct_id: Optional[str]
    category: str
    severity: str
    title: str
    description: str
    remediation: Optional[str]
    line: Optional[int]

class CfgBlockStatementsRow(TypedDict):
    """Row type for cfg_block_statements table."""
    block_id: int
    statement_type: str
    line: int
    statement_text: Optional[str]

class CfgBlockStatementsJsxRow(TypedDict):
    """Row type for cfg_block_statements_jsx table."""
    block_id: int
    statement_type: str
    line: int
    statement_text: Optional[str]
    jsx_mode: Optional[str]
    extraction_pass: Optional[int]

class CfgBlocksRow(TypedDict):
    """Row type for cfg_blocks table."""
    id: int
    file: str
    function_name: str
    block_type: str
    start_line: int
    end_line: int
    condition_expr: Optional[str]

class CfgBlocksJsxRow(TypedDict):
    """Row type for cfg_blocks_jsx table."""
    id: int
    file: str
    function_name: str
    block_type: str
    start_line: int
    end_line: int
    condition_expr: Optional[str]
    jsx_mode: Optional[str]
    extraction_pass: Optional[int]

class CfgEdgesRow(TypedDict):
    """Row type for cfg_edges table."""
    id: int
    file: str
    function_name: str
    source_block_id: int
    target_block_id: int
    edge_type: str

class CfgEdgesJsxRow(TypedDict):
    """Row type for cfg_edges_jsx table."""
    id: int
    file: str
    function_name: str
    source_block_id: int
    target_block_id: int
    edge_type: str
    jsx_mode: Optional[str]
    extraction_pass: Optional[int]

class ClassPropertiesRow(TypedDict):
    """Row type for class_properties table."""
    file: str
    line: int
    class_name: str
    property_name: str
    property_type: Optional[str]
    is_optional: Optional[bool]
    is_readonly: Optional[bool]
    access_modifier: Optional[str]
    has_declare: Optional[bool]
    initializer: Optional[str]

class CodeDiffsRow(TypedDict):
    """Row type for code_diffs table."""
    id: int
    snapshot_id: int
    file_path: str
    diff_text: Optional[str]
    added_lines: Optional[int]
    removed_lines: Optional[int]

class CodeSnapshotsRow(TypedDict):
    """Row type for code_snapshots table."""
    id: int
    plan_id: int
    task_id: Optional[int]
    sequence: Optional[int]
    checkpoint_name: str
    timestamp: str
    git_ref: Optional[str]
    shadow_sha: Optional[str]
    files_json: Optional[str]

class ComposeServicesRow(TypedDict):
    """Row type for compose_services table."""
    file_path: str
    service_name: str
    image: Optional[str]
    ports: Optional[str]
    volumes: Optional[str]
    environment: Optional[str]
    is_privileged: Optional[bool]
    network_mode: Optional[str]
    user: Optional[str]
    cap_add: Optional[str]
    cap_drop: Optional[str]
    security_opt: Optional[str]
    restart: Optional[str]
    command: Optional[str]
    entrypoint: Optional[str]
    depends_on: Optional[str]
    healthcheck: Optional[str]

class ConfigFilesRow(TypedDict):
    """Row type for config_files table."""
    path: str
    content: str
    type: str
    context_dir: Optional[str]

class DependencyVersionsRow(TypedDict):
    """Row type for dependency_versions table."""
    manager: str
    package_name: str
    locked_version: str
    latest_version: Optional[str]
    delta: Optional[str]
    is_outdated: bool
    last_checked: str
    error: Optional[str]

class DiInjectionsRow(TypedDict):
    """Row type for di_injections table."""
    file: str
    line: int
    target_class: str
    injected_service: str
    injection_type: str

class DockerImagesRow(TypedDict):
    """Row type for docker_images table."""
    file_path: str
    base_image: Optional[str]
    exposed_ports: Optional[str]
    env_vars: Optional[str]
    build_args: Optional[str]
    user: Optional[str]
    has_healthcheck: Optional[bool]

class EnvVarUsageRow(TypedDict):
    """Row type for env_var_usage table."""
    file: str
    line: int
    var_name: str
    access_type: str
    in_function: Optional[str]
    property_access: Optional[str]

class ExpressMiddlewareChainsRow(TypedDict):
    """Row type for express_middleware_chains table."""
    id: int
    file: str
    route_line: int
    route_path: str
    route_method: str
    execution_order: int
    handler_expr: str
    handler_type: str
    handler_file: Optional[str]
    handler_function: Optional[str]
    handler_line: Optional[int]

class FilesRow(TypedDict):
    """Row type for files table."""
    path: str
    sha256: str
    ext: str
    bytes: int
    loc: int
    file_category: str

class FindingsConsolidatedRow(TypedDict):
    """Row type for findings_consolidated table."""
    id: int
    file: str
    line: int
    column: Optional[int]
    rule: str
    tool: str
    message: Optional[str]
    severity: str
    category: Optional[str]
    confidence: Optional[float]
    code_snippet: Optional[str]
    cwe: Optional[str]
    timestamp: str
    details_json: Optional[str]

class FrameworkSafeSinksRow(TypedDict):
    """Row type for framework_safe_sinks table."""
    framework_id: Optional[int]
    sink_pattern: str
    sink_type: str
    is_safe: Optional[bool]
    reason: Optional[str]

class FrameworksRow(TypedDict):
    """Row type for frameworks table."""
    id: int
    name: str
    version: Optional[str]
    language: str
    path: Optional[str]
    source: Optional[str]
    package_manager: Optional[str]
    is_primary: Optional[bool]

class FrontendApiCallsRow(TypedDict):
    """Row type for frontend_api_calls table."""
    file: str
    line: int
    method: str
    url_literal: str
    body_variable: Optional[str]
    function_name: Optional[str]

class FunctionCallArgsRow(TypedDict):
    """Row type for function_call_args table."""
    file: str
    line: int
    caller_function: str
    callee_function: str
    argument_index: Optional[int]
    argument_expr: Optional[str]
    param_name: Optional[str]
    callee_file_path: Optional[str]

class FunctionCallArgsJsxRow(TypedDict):
    """Row type for function_call_args_jsx table."""
    file: str
    line: int
    caller_function: str
    callee_function: str
    argument_index: Optional[int]
    argument_expr: Optional[str]
    param_name: Optional[str]
    jsx_mode: str
    extraction_pass: Optional[int]

class FunctionReturnSourcesRow(TypedDict):
    """Row type for function_return_sources table."""
    id: int
    return_file: str
    return_line: int
    return_function: str
    return_var_name: str

class FunctionReturnSourcesJsxRow(TypedDict):
    """Row type for function_return_sources_jsx table."""
    id: int
    return_file: str
    return_line: int
    return_function: Optional[str]
    jsx_mode: str
    return_var_name: str

class FunctionReturnsRow(TypedDict):
    """Row type for function_returns table."""
    file: str
    line: int
    function_name: str
    return_expr: str
    has_jsx: Optional[bool]
    returns_component: Optional[bool]
    cleanup_operations: Optional[str]

class FunctionReturnsJsxRow(TypedDict):
    """Row type for function_returns_jsx table."""
    file: str
    line: int
    function_name: Optional[str]
    return_expr: Optional[str]
    has_jsx: Optional[bool]
    returns_component: Optional[bool]
    cleanup_operations: Optional[str]
    jsx_mode: str
    extraction_pass: Optional[int]

class GithubJobDependenciesRow(TypedDict):
    """Row type for github_job_dependencies table."""
    job_id: str
    needs_job_id: str

class GithubJobsRow(TypedDict):
    """Row type for github_jobs table."""
    job_id: str
    workflow_path: str
    job_key: str
    job_name: Optional[str]
    runs_on: Optional[str]
    strategy: Optional[str]
    permissions: Optional[str]
    env: Optional[str]
    if_condition: Optional[str]
    timeout_minutes: Optional[int]
    uses_reusable_workflow: Optional[bool]
    reusable_workflow_path: Optional[str]

class GithubStepOutputsRow(TypedDict):
    """Row type for github_step_outputs table."""
    id: int
    step_id: str
    output_name: str
    output_expression: str

class GithubStepReferencesRow(TypedDict):
    """Row type for github_step_references table."""
    id: int
    step_id: str
    reference_location: str
    reference_type: str
    reference_path: str

class GithubStepsRow(TypedDict):
    """Row type for github_steps table."""
    step_id: str
    job_id: str
    sequence_order: int
    step_name: Optional[str]
    uses_action: Optional[str]
    uses_version: Optional[str]
    run_script: Optional[str]
    shell: Optional[str]
    env: Optional[str]
    with_args: Optional[str]
    if_condition: Optional[str]
    timeout_minutes: Optional[int]
    continue_on_error: Optional[bool]

class GithubWorkflowsRow(TypedDict):
    """Row type for github_workflows table."""
    workflow_path: str
    workflow_name: Optional[str]
    on_triggers: str
    permissions: Optional[str]
    concurrency: Optional[str]
    env: Optional[str]

class GraphqlExecutionEdgesRow(TypedDict):
    """Row type for graphql_execution_edges table."""
    from_field_id: int
    to_symbol_id: int
    edge_kind: str

class GraphqlFieldArgsRow(TypedDict):
    """Row type for graphql_field_args table."""
    field_id: int
    arg_name: str
    arg_type: str
    has_default: Optional[bool]
    default_value: Optional[str]
    is_nullable: Optional[bool]
    directives_json: Optional[str]

class GraphqlFieldsRow(TypedDict):
    """Row type for graphql_fields table."""
    field_id: int
    type_id: int
    field_name: str
    return_type: str
    is_list: Optional[bool]
    is_nullable: Optional[bool]
    directives_json: Optional[str]
    line: Optional[int]
    column: Optional[int]

class GraphqlFindingsCacheRow(TypedDict):
    """Row type for graphql_findings_cache table."""
    finding_id: int
    field_id: Optional[int]
    resolver_symbol_id: Optional[int]
    rule: str
    severity: str
    details_json: str
    provenance: str

class GraphqlResolverMappingsRow(TypedDict):
    """Row type for graphql_resolver_mappings table."""
    field_id: int
    resolver_symbol_id: int
    resolver_path: str
    resolver_line: int
    resolver_language: str
    resolver_export: Optional[str]
    binding_style: str

class GraphqlResolverParamsRow(TypedDict):
    """Row type for graphql_resolver_params table."""
    resolver_symbol_id: int
    arg_name: str
    param_name: str
    param_index: int
    is_kwargs: Optional[bool]
    is_list_input: Optional[bool]

class GraphqlSchemasRow(TypedDict):
    """Row type for graphql_schemas table."""
    file_path: str
    schema_hash: str
    language: str
    last_modified: Optional[int]

class GraphqlTypesRow(TypedDict):
    """Row type for graphql_types table."""
    type_id: int
    schema_path: str
    type_name: str
    kind: str
    implements: Optional[str]
    description: Optional[str]
    line: Optional[int]

class ImportStyleNamesRow(TypedDict):
    """Row type for import_style_names table."""
    id: int
    import_file: str
    import_line: int
    imported_name: str

class ImportStylesRow(TypedDict):
    """Row type for import_styles table."""
    file: str
    line: int
    package: str
    import_style: str
    alias_name: Optional[str]
    full_statement: Optional[str]

class JwtPatternsRow(TypedDict):
    """Row type for jwt_patterns table."""
    file_path: str
    line_number: int
    pattern_type: str
    pattern_text: Optional[str]
    secret_source: Optional[str]
    algorithm: Optional[str]

class LockAnalysisRow(TypedDict):
    """Row type for lock_analysis table."""
    file_path: str
    lock_type: str
    package_manager_version: Optional[str]
    total_packages: Optional[int]
    duplicate_packages: Optional[str]
    lock_file_version: Optional[str]

class NginxConfigsRow(TypedDict):
    """Row type for nginx_configs table."""
    file_path: str
    block_type: str
    block_context: Optional[str]
    directives: Optional[str]
    level: Optional[int]

class ObjectLiteralsRow(TypedDict):
    """Row type for object_literals table."""
    id: int
    file: str
    line: int
    variable_name: Optional[str]
    property_name: str
    property_value: str
    property_type: Optional[str]
    nested_level: Optional[int]
    in_function: Optional[str]

class OrmQueriesRow(TypedDict):
    """Row type for orm_queries table."""
    file: str
    line: int
    query_type: str
    includes: Optional[str]
    has_limit: Optional[bool]
    has_transaction: Optional[bool]

class OrmRelationshipsRow(TypedDict):
    """Row type for orm_relationships table."""
    file: str
    line: int
    source_model: str
    target_model: str
    relationship_type: str
    foreign_key: Optional[str]
    cascade_delete: Optional[bool]
    as_name: Optional[str]

class PackageConfigsRow(TypedDict):
    """Row type for package_configs table."""
    file_path: str
    package_name: Optional[str]
    version: Optional[str]
    dependencies: Optional[str]
    dev_dependencies: Optional[str]
    peer_dependencies: Optional[str]
    scripts: Optional[str]
    engines: Optional[str]
    workspaces: Optional[str]
    private: Optional[bool]

class PlanJobsRow(TypedDict):
    """Row type for plan_jobs table."""
    id: int
    task_id: int
    job_number: int
    description: str
    completed: int
    is_audit_job: int
    created_at: str

class PlanPhasesRow(TypedDict):
    """Row type for plan_phases table."""
    id: int
    plan_id: int
    phase_number: int
    title: str
    description: Optional[str]
    success_criteria: Optional[str]
    status: str
    created_at: str

class PlanSpecsRow(TypedDict):
    """Row type for plan_specs table."""
    id: int
    plan_id: int
    spec_yaml: str
    spec_type: Optional[str]
    created_at: str

class PlanTasksRow(TypedDict):
    """Row type for plan_tasks table."""
    id: int
    plan_id: int
    phase_id: Optional[int]
    task_number: int
    title: str
    description: Optional[str]
    status: str
    audit_status: Optional[str]
    assigned_to: Optional[str]
    spec_id: Optional[int]
    created_at: str
    completed_at: Optional[str]

class PlansRow(TypedDict):
    """Row type for plans table."""
    id: int
    name: str
    description: Optional[str]
    created_at: str
    status: str
    metadata_json: Optional[str]

class PrismaModelsRow(TypedDict):
    """Row type for prisma_models table."""
    model_name: str
    field_name: str
    field_type: str
    is_indexed: Optional[bool]
    is_unique: Optional[bool]
    is_relation: Optional[bool]

class PythonBranchesRow(TypedDict):
    """Row type for python_branches table."""
    id: Optional[int]
    file: str
    line: int
    branch_kind: str
    branch_type: Optional[str]
    has_else: Optional[int]
    has_elif: Optional[int]
    chain_length: Optional[int]
    has_complex_condition: Optional[int]
    nesting_level: Optional[int]
    case_count: Optional[int]
    has_guards: Optional[int]
    has_wildcard: Optional[int]
    pattern_types: Optional[str]
    exception_types: Optional[str]
    handling_strategy: Optional[str]
    variable_name: Optional[str]
    exception_type: Optional[str]
    is_re_raise: Optional[int]
    from_exception: Optional[str]
    message: Optional[str]
    condition: Optional[str]
    has_cleanup: Optional[int]
    cleanup_calls: Optional[str]
    in_function: Optional[str]

class PythonClassFeaturesRow(TypedDict):
    """Row type for python_class_features table."""
    id: Optional[int]
    file: str
    line: int
    feature_kind: str
    feature_type: Optional[str]
    class_name: Optional[str]
    name: Optional[str]
    in_class: Optional[str]
    metaclass_name: Optional[str]
    is_definition: Optional[int]
    field_count: Optional[int]
    frozen: Optional[int]
    enum_name: Optional[str]
    enum_type: Optional[str]
    member_count: Optional[int]
    slot_count: Optional[int]
    abstract_method_count: Optional[int]
    method_name: Optional[str]
    method_type: Optional[str]
    category: Optional[str]
    visibility: Optional[str]
    is_name_mangled: Optional[int]
    decorator: Optional[str]
    decorator_type: Optional[str]
    has_arguments: Optional[int]

class PythonCollectionsRow(TypedDict):
    """Row type for python_collections table."""
    id: Optional[int]
    file: str
    line: int
    collection_kind: str
    collection_type: Optional[str]
    operation: Optional[str]
    method: Optional[str]
    in_function: Optional[str]
    has_default: Optional[int]
    mutates_in_place: Optional[int]
    builtin: Optional[str]
    has_key: Optional[int]

class PythonComprehensionsRow(TypedDict):
    """Row type for python_comprehensions table."""
    id: Optional[int]
    file: str
    line: int
    comp_kind: str
    comp_type: Optional[str]
    iteration_var: Optional[str]
    iteration_source: Optional[str]
    result_expr: Optional[str]
    filter_expr: Optional[str]
    has_filter: Optional[int]
    nesting_level: Optional[int]
    in_function: Optional[str]

class PythonControlStatementsRow(TypedDict):
    """Row type for python_control_statements table."""
    id: Optional[int]
    file: str
    line: int
    statement_kind: str
    statement_type: Optional[str]
    loop_type: Optional[str]
    condition_type: Optional[str]
    has_message: Optional[int]
    target_count: Optional[int]
    target_type: Optional[str]
    context_count: Optional[int]
    has_alias: Optional[int]
    is_async: Optional[int]
    in_function: Optional[str]

class PythonDecoratorsRow(TypedDict):
    """Row type for python_decorators table."""
    file: str
    line: int
    decorator_name: str
    decorator_type: str
    target_type: str
    target_name: str
    is_async: Optional[bool]

class PythonDescriptorsRow(TypedDict):
    """Row type for python_descriptors table."""
    id: Optional[int]
    file: str
    line: int
    descriptor_kind: str
    descriptor_type: Optional[str]
    name: Optional[str]
    class_name: Optional[str]
    in_class: Optional[str]
    has_get: Optional[int]
    has_set: Optional[int]
    has_delete: Optional[int]
    is_data_descriptor: Optional[int]
    property_name: Optional[str]
    access_type: Optional[str]
    has_computation: Optional[int]
    has_validation: Optional[int]
    method_name: Optional[str]
    is_functools: Optional[int]

class PythonDjangoMiddlewareRow(TypedDict):
    """Row type for python_django_middleware table."""
    file: str
    line: int
    middleware_class_name: str
    has_process_request: Optional[bool]
    has_process_response: Optional[bool]
    has_process_exception: Optional[bool]
    has_process_view: Optional[bool]
    has_process_template_response: Optional[bool]

class PythonDjangoViewsRow(TypedDict):
    """Row type for python_django_views table."""
    file: str
    line: int
    view_class_name: str
    view_type: str
    base_view_class: Optional[str]
    model_name: Optional[str]
    template_name: Optional[str]
    has_permission_check: Optional[bool]
    http_method_names: Optional[str]
    has_get_queryset_override: Optional[bool]

class PythonExpressionsRow(TypedDict):
    """Row type for python_expressions table."""
    id: Optional[int]
    file: str
    line: int
    expression_kind: str
    expression_type: Optional[str]
    in_function: Optional[str]
    target: Optional[str]
    has_start: Optional[int]
    has_stop: Optional[int]
    has_step: Optional[int]
    is_assignment: Optional[int]
    element_count: Optional[int]
    operation: Optional[str]
    has_rest: Optional[int]
    target_count: Optional[int]
    unpack_type: Optional[str]
    pattern: Optional[str]
    uses_is: Optional[int]
    format_type: Optional[str]
    has_expressions: Optional[int]
    var_count: Optional[int]
    context: Optional[str]
    has_globals: Optional[int]
    has_locals: Optional[int]
    generator_function: Optional[str]
    yield_expr: Optional[str]
    yield_type: Optional[str]
    in_loop: Optional[int]
    condition: Optional[str]
    awaited_expr: Optional[str]
    containing_function: Optional[str]

class PythonFixtureParamsRow(TypedDict):
    """Row type for python_fixture_params table."""
    id: Optional[int]
    file: str
    fixture_id: int
    param_name: Optional[str]
    param_value: Optional[str]
    param_order: Optional[int]

class PythonFrameworkConfigRow(TypedDict):
    """Row type for python_framework_config table."""
    id: Optional[int]
    file: str
    line: int
    config_kind: str
    config_type: Optional[str]
    framework: str
    name: Optional[str]
    endpoint: Optional[str]
    cache_type: Optional[str]
    timeout: Optional[int]
    has_process_request: Optional[int]
    has_process_response: Optional[int]
    has_process_exception: Optional[int]
    has_process_view: Optional[int]
    has_process_template_response: Optional[int]

class PythonFrameworkMethodsRow(TypedDict):
    """Row type for python_framework_methods table."""
    id: Optional[int]
    file: str
    config_id: int
    method_name: str
    method_order: Optional[int]

class PythonFunctionsAdvancedRow(TypedDict):
    """Row type for python_functions_advanced table."""
    id: Optional[int]
    file: str
    line: int
    function_kind: str
    function_type: Optional[str]
    name: Optional[str]
    function_name: Optional[str]
    yield_count: Optional[int]
    has_send: Optional[int]
    has_yield_from: Optional[int]
    is_infinite: Optional[int]
    await_count: Optional[int]
    has_async_for: Optional[int]
    has_async_with: Optional[int]
    parameter_count: Optional[int]
    parameters: Optional[str]
    body: Optional[str]
    captures_closure: Optional[int]
    captured_vars: Optional[str]
    used_in: Optional[str]
    as_name: Optional[str]
    context_expr: Optional[str]
    is_async: Optional[int]
    iter_expr: Optional[str]
    target_var: Optional[str]
    base_case_line: Optional[int]
    calls_function: Optional[str]
    recursion_type: Optional[str]
    cache_size: Optional[int]
    memoization_type: Optional[str]
    is_recursive: Optional[int]
    has_memoization: Optional[int]
    in_function: Optional[str]

class PythonImportsAdvancedRow(TypedDict):
    """Row type for python_imports_advanced table."""
    id: Optional[int]
    file: str
    line: int
    import_kind: str
    import_type: Optional[str]
    module: Optional[str]
    name: Optional[str]
    alias: Optional[str]
    is_relative: Optional[int]
    in_function: Optional[str]
    has_alias: Optional[int]
    imported_names: Optional[str]
    is_wildcard: Optional[int]
    relative_level: Optional[int]
    attribute: Optional[str]
    is_default: Optional[int]
    export_type: Optional[str]

class PythonIoOperationsRow(TypedDict):
    """Row type for python_io_operations table."""
    id: Optional[int]
    file: str
    line: int
    io_kind: str
    io_type: Optional[str]
    operation: Optional[str]
    target: Optional[str]
    is_static: Optional[int]
    flow_type: Optional[str]
    function_name: Optional[str]
    parameter_name: Optional[str]
    return_expr: Optional[str]
    is_async: Optional[int]
    in_function: Optional[str]

class PythonLiteralsRow(TypedDict):
    """Row type for python_literals table."""
    id: Optional[int]
    file: str
    line: int
    literal_kind: str
    literal_type: Optional[str]
    name: Optional[str]
    literal_value_1: Optional[str]
    literal_value_2: Optional[str]
    literal_value_3: Optional[str]
    literal_value_4: Optional[str]
    literal_value_5: Optional[str]
    function_name: Optional[str]
    overload_count: Optional[int]
    variants: Optional[str]

class PythonLoopsRow(TypedDict):
    """Row type for python_loops table."""
    id: Optional[int]
    file: str
    line: int
    loop_kind: str
    loop_type: Optional[str]
    has_else: Optional[int]
    nesting_level: Optional[int]
    target_count: Optional[int]
    in_function: Optional[str]
    is_infinite: Optional[int]
    estimated_complexity: Optional[str]
    has_growing_operation: Optional[int]

class PythonOperatorsRow(TypedDict):
    """Row type for python_operators table."""
    id: Optional[int]
    file: str
    line: int
    operator_kind: str
    operator_type: Optional[str]
    operator: Optional[str]
    in_function: Optional[str]
    container_type: Optional[str]
    chain_length: Optional[int]
    operators: Optional[str]
    has_complex_condition: Optional[int]
    variable: Optional[str]
    used_in: Optional[str]

class PythonOrmFieldsRow(TypedDict):
    """Row type for python_orm_fields table."""
    file: str
    line: int
    model_name: str
    field_name: str
    field_type: Optional[str]
    is_primary_key: Optional[bool]
    is_foreign_key: Optional[bool]
    foreign_key_target: Optional[str]

class PythonOrmModelsRow(TypedDict):
    """Row type for python_orm_models table."""
    file: str
    line: int
    model_name: str
    table_name: Optional[str]
    orm_type: str

class PythonPackageConfigsRow(TypedDict):
    """Row type for python_package_configs table."""
    file_path: str
    file_type: str
    project_name: Optional[str]
    project_version: Optional[str]
    dependencies: Optional[str]
    optional_dependencies: Optional[str]
    build_system: Optional[str]
    indexed_at: Optional[Any]

class PythonProtocolMethodsRow(TypedDict):
    """Row type for python_protocol_methods table."""
    id: Optional[int]
    file: str
    protocol_id: int
    method_name: str
    method_order: Optional[int]

class PythonProtocolsRow(TypedDict):
    """Row type for python_protocols table."""
    id: Optional[int]
    file: str
    line: int
    protocol_kind: str
    protocol_type: Optional[str]
    class_name: Optional[str]
    in_function: Optional[str]
    has_iter: Optional[int]
    has_next: Optional[int]
    is_generator: Optional[int]
    raises_stopiteration: Optional[int]
    has_contains: Optional[int]
    has_getitem: Optional[int]
    has_setitem: Optional[int]
    has_delitem: Optional[int]
    has_len: Optional[int]
    is_mapping: Optional[int]
    is_sequence: Optional[int]
    has_args: Optional[int]
    has_kwargs: Optional[int]
    param_count: Optional[int]
    has_getstate: Optional[int]
    has_setstate: Optional[int]
    has_reduce: Optional[int]
    has_reduce_ex: Optional[int]
    context_expr: Optional[str]
    resource_type: Optional[str]
    variable_name: Optional[str]
    is_async: Optional[int]
    has_copy: Optional[int]
    has_deepcopy: Optional[int]

class PythonRoutesRow(TypedDict):
    """Row type for python_routes table."""
    file: str
    line: Optional[int]
    framework: str
    method: Optional[str]
    pattern: Optional[str]
    handler_function: Optional[str]
    has_auth: Optional[bool]
    dependencies: Optional[str]
    blueprint: Optional[str]

class PythonSchemaValidatorsRow(TypedDict):
    """Row type for python_schema_validators table."""
    id: Optional[int]
    file: str
    schema_id: int
    validator_name: str
    validator_type: Optional[str]
    validator_order: Optional[int]

class PythonSecurityFindingsRow(TypedDict):
    """Row type for python_security_findings table."""
    id: Optional[int]
    file: str
    line: int
    finding_kind: str
    finding_type: Optional[str]
    function_name: Optional[str]
    decorator_name: Optional[str]
    permissions: Optional[str]
    is_vulnerable: Optional[int]
    shell_true: Optional[int]
    is_constant_input: Optional[int]
    is_critical: Optional[int]
    has_concatenation: Optional[int]

class PythonStateMutationsRow(TypedDict):
    """Row type for python_state_mutations table."""
    id: Optional[int]
    file: str
    line: int
    mutation_kind: str
    mutation_type: Optional[str]
    target: Optional[str]
    operator: Optional[str]
    target_type: Optional[str]
    operation: Optional[str]
    is_init: Optional[int]
    is_dunder_method: Optional[int]
    is_property_setter: Optional[int]
    in_function: Optional[str]

class PythonStdlibUsageRow(TypedDict):
    """Row type for python_stdlib_usage table."""
    id: Optional[int]
    file: str
    line: int
    stdlib_kind: str
    module: Optional[str]
    usage_type: Optional[str]
    function_name: Optional[str]
    pattern: Optional[str]
    in_function: Optional[str]
    operation: Optional[str]
    has_flags: Optional[int]
    direction: Optional[str]
    path_type: Optional[str]
    log_level: Optional[str]
    threading_type: Optional[str]
    is_decorator: Optional[int]

class PythonTestCasesRow(TypedDict):
    """Row type for python_test_cases table."""
    id: Optional[int]
    file: str
    line: int
    test_kind: str
    test_type: Optional[str]
    name: Optional[str]
    function_name: Optional[str]
    class_name: Optional[str]
    assertion_type: Optional[str]
    test_expr: Optional[str]

class PythonTestFixturesRow(TypedDict):
    """Row type for python_test_fixtures table."""
    id: Optional[int]
    file: str
    line: int
    fixture_kind: str
    fixture_type: Optional[str]
    name: Optional[str]
    scope: Optional[str]
    autouse: Optional[int]
    in_function: Optional[str]

class PythonTypeDefinitionsRow(TypedDict):
    """Row type for python_type_definitions table."""
    id: Optional[int]
    file: str
    line: int
    type_kind: str
    name: Optional[str]
    type_param_count: Optional[int]
    type_param_1: Optional[str]
    type_param_2: Optional[str]
    type_param_3: Optional[str]
    type_param_4: Optional[str]
    type_param_5: Optional[str]
    is_runtime_checkable: Optional[int]
    methods: Optional[str]

class PythonTypeddictFieldsRow(TypedDict):
    """Row type for python_typeddict_fields table."""
    id: Optional[int]
    file: str
    typeddict_id: int
    field_name: str
    field_type: Optional[str]
    required: Optional[int]
    field_order: Optional[int]

class PythonValidationSchemasRow(TypedDict):
    """Row type for python_validation_schemas table."""
    id: Optional[int]
    file: str
    line: int
    schema_kind: str
    schema_type: Optional[str]
    framework: str
    name: Optional[str]
    field_type: Optional[str]
    required: Optional[int]

class PythonValidatorsRow(TypedDict):
    """Row type for python_validators table."""
    file: str
    line: int
    model_name: str
    field_name: Optional[str]
    validator_method: str
    validator_type: str

class ReactComponentHooksRow(TypedDict):
    """Row type for react_component_hooks table."""
    id: int
    component_file: str
    component_name: str
    hook_name: str

class ReactComponentsRow(TypedDict):
    """Row type for react_components table."""
    file: str
    name: str
    type: str
    start_line: int
    end_line: int
    has_jsx: Optional[bool]
    props_type: Optional[str]

class ReactHookDependenciesRow(TypedDict):
    """Row type for react_hook_dependencies table."""
    id: int
    hook_file: str
    hook_line: int
    hook_component: str
    dependency_name: str

class ReactHooksRow(TypedDict):
    """Row type for react_hooks table."""
    file: str
    line: int
    component_name: str
    hook_name: str
    dependency_array: Optional[str]
    callback_body: Optional[str]
    has_cleanup: Optional[bool]
    cleanup_type: Optional[str]

class RefactorCandidatesRow(TypedDict):
    """Row type for refactor_candidates table."""
    id: int
    file_path: str
    reason: str
    severity: str
    loc: Optional[int]
    cyclomatic_complexity: Optional[int]
    duplication_percent: Optional[float]
    num_dependencies: Optional[int]
    detected_at: str
    metadata_json: Optional[str]

class RefactorHistoryRow(TypedDict):
    """Row type for refactor_history table."""
    id: int
    timestamp: str
    target_file: str
    refactor_type: str
    migrations_found: Optional[int]
    migrations_complete: Optional[int]
    schema_consistent: Optional[int]
    validation_status: Optional[str]
    details_json: Optional[str]

class RefsRow(TypedDict):
    """Row type for refs table."""
    src: str
    kind: str
    value: str
    line: Optional[int]

class ResolvedFlowAuditRow(TypedDict):
    """Row type for resolved_flow_audit table."""
    id: int
    source_file: str
    source_line: int
    source_pattern: str
    sink_file: str
    sink_line: int
    sink_pattern: str
    vulnerability_type: str
    path_length: int
    hops: int
    path_json: str
    flow_sensitive: int
    status: str
    sanitizer_file: Optional[str]
    sanitizer_line: Optional[int]
    sanitizer_method: Optional[str]
    engine: str

class RouterMountsRow(TypedDict):
    """Row type for router_mounts table."""
    file: str
    line: int
    mount_path_expr: str
    router_variable: str
    is_literal: Optional[bool]

class SequelizeAssociationsRow(TypedDict):
    """Row type for sequelize_associations table."""
    file: str
    line: int
    model_name: str
    association_type: str
    target_model: str
    foreign_key: Optional[str]
    through_table: Optional[str]

class SequelizeModelsRow(TypedDict):
    """Row type for sequelize_models table."""
    file: str
    line: int
    model_name: str
    table_name: Optional[str]
    extends_model: Optional[bool]

class SqlObjectsRow(TypedDict):
    """Row type for sql_objects table."""
    file: str
    kind: str
    name: str

class SqlQueriesRow(TypedDict):
    """Row type for sql_queries table."""
    file_path: str
    line_number: int
    query_text: str
    command: str
    extraction_source: str

class SqlQueryTablesRow(TypedDict):
    """Row type for sql_query_tables table."""
    id: int
    query_file: str
    query_line: int
    table_name: str

class SymbolsRow(TypedDict):
    """Row type for symbols table."""
    path: str
    name: str
    type: str
    line: int
    col: int
    end_line: Optional[int]
    type_annotation: Optional[str]
    parameters: Optional[str]
    is_typed: Optional[bool]

class SymbolsJsxRow(TypedDict):
    """Row type for symbols_jsx table."""
    path: str
    name: str
    type: str
    line: int
    col: int
    jsx_mode: str
    extraction_pass: Optional[int]

class TaintFlowsRow(TypedDict):
    """Row type for taint_flows table."""
    id: int
    source_file: str
    source_line: int
    source_pattern: str
    sink_file: str
    sink_line: int
    sink_pattern: str
    vulnerability_type: str
    path_length: int
    hops: int
    path_json: str
    flow_sensitive: int

class TerraformFilesRow(TypedDict):
    """Row type for terraform_files table."""
    file_path: str
    module_name: Optional[str]
    stack_name: Optional[str]
    backend_type: Optional[str]
    providers_json: Optional[str]
    is_module: Optional[bool]
    module_source: Optional[str]

class TerraformFindingsRow(TypedDict):
    """Row type for terraform_findings table."""
    finding_id: str
    file_path: str
    resource_id: Optional[str]
    category: str
    severity: str
    title: str
    description: Optional[str]
    graph_context_json: Optional[str]
    remediation: Optional[str]
    line: Optional[int]

class TerraformOutputsRow(TypedDict):
    """Row type for terraform_outputs table."""
    output_id: str
    file_path: str
    output_name: str
    value_json: Optional[str]
    is_sensitive: Optional[bool]
    description: Optional[str]
    line: Optional[int]

class TerraformResourcesRow(TypedDict):
    """Row type for terraform_resources table."""
    resource_id: str
    file_path: str
    resource_type: str
    resource_name: str
    module_path: Optional[str]
    properties_json: Optional[str]
    depends_on_json: Optional[str]
    sensitive_flags_json: Optional[str]
    has_public_exposure: Optional[bool]
    line: Optional[int]

class TerraformVariableValuesRow(TypedDict):
    """Row type for terraform_variable_values table."""
    id: int
    file_path: str
    variable_name: str
    variable_value_json: Optional[str]
    line: Optional[int]
    is_sensitive_context: Optional[bool]

class TerraformVariablesRow(TypedDict):
    """Row type for terraform_variables table."""
    variable_id: str
    file_path: str
    variable_name: str
    variable_type: Optional[str]
    default_json: Optional[str]
    is_sensitive: Optional[bool]
    description: Optional[str]
    source_file: Optional[str]
    line: Optional[int]

class TypeAnnotationsRow(TypedDict):
    """Row type for type_annotations table."""
    file: str
    line: int
    column: Optional[int]
    symbol_name: str
    symbol_kind: str
    type_annotation: Optional[str]
    is_any: Optional[bool]
    is_unknown: Optional[bool]
    is_generic: Optional[bool]
    has_type_params: Optional[bool]
    type_params: Optional[str]
    return_type: Optional[str]
    extends_type: Optional[str]

class ValidationFrameworkUsageRow(TypedDict):
    """Row type for validation_framework_usage table."""
    file_path: str
    line: int
    framework: str
    method: str
    variable_name: Optional[str]
    is_validator: Optional[bool]
    argument_expr: Optional[str]

class VariableUsageRow(TypedDict):
    """Row type for variable_usage table."""
    file: str
    line: int
    variable_name: str
    usage_type: str
    in_component: Optional[str]
    in_hook: Optional[str]
    scope_level: Optional[int]

class VueComponentsRow(TypedDict):
    """Row type for vue_components table."""
    file: str
    name: str
    type: str
    start_line: int
    end_line: int
    has_template: Optional[bool]
    has_style: Optional[bool]
    composition_api_used: Optional[bool]
    props_definition: Optional[str]
    emits_definition: Optional[str]
    setup_return: Optional[str]

class VueDirectivesRow(TypedDict):
    """Row type for vue_directives table."""
    file: str
    line: int
    directive_name: str
    expression: Optional[str]
    in_component: Optional[str]
    has_key: Optional[bool]
    modifiers: Optional[str]

class VueHooksRow(TypedDict):
    """Row type for vue_hooks table."""
    file: str
    line: int
    component_name: str
    hook_name: str
    hook_type: str
    dependencies: Optional[str]
    return_value: Optional[str]
    is_async: Optional[bool]

class VueProvideInjectRow(TypedDict):
    """Row type for vue_provide_inject table."""
    file: str
    line: int
    component_name: str
    operation_type: str
    key_name: str
    value_expr: Optional[str]
    is_reactive: Optional[bool]
