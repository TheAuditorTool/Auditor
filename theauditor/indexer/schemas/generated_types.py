# Auto-generated TypedDict definitions from schema
from typing import Any, TypedDict


class AngularComponentStylesRow(TypedDict):
    """Row type for angular_component_styles table."""
    file: str
    component_name: str
    style_path: str

class AngularComponentsRow(TypedDict):
    """Row type for angular_components table."""
    file: str
    line: int
    component_name: str
    selector: str | None
    template_path: str | None
    has_lifecycle_hooks: bool | None

class AngularGuardsRow(TypedDict):
    """Row type for angular_guards table."""
    file: str
    line: int
    guard_name: str
    guard_type: str
    implements_interface: str | None

class AngularModuleDeclarationsRow(TypedDict):
    """Row type for angular_module_declarations table."""
    file: str
    module_name: str
    declaration_name: str
    declaration_type: str | None

class AngularModuleExportsRow(TypedDict):
    """Row type for angular_module_exports table."""
    file: str
    module_name: str
    exported_name: str

class AngularModuleImportsRow(TypedDict):
    """Row type for angular_module_imports table."""
    file: str
    module_name: str
    imported_module: str

class AngularModuleProvidersRow(TypedDict):
    """Row type for angular_module_providers table."""
    file: str
    module_name: str
    provider_name: str
    provider_type: str | None

class AngularModulesRow(TypedDict):
    """Row type for angular_modules table."""
    file: str
    line: int
    module_name: str

class AngularServicesRow(TypedDict):
    """Row type for angular_services table."""
    file: str
    line: int
    service_name: str
    is_injectable: bool | None
    provided_in: str | None

class ApiEndpointControlsRow(TypedDict):
    """Row type for api_endpoint_controls table."""
    id: int
    endpoint_file: str
    endpoint_line: int
    control_name: str

class ApiEndpointsRow(TypedDict):
    """Row type for api_endpoints table."""
    file: str
    line: int
    method: str
    pattern: str
    path: str | None
    full_path: str | None
    has_auth: bool | None
    handler_function: str | None

class AssignmentSourceVarsRow(TypedDict):
    """Row type for assignment_source_vars table."""
    file: str
    line: int
    target_var: str
    source_var: str
    var_index: int

class AssignmentSourcesRow(TypedDict):
    """Row type for assignment_sources table."""
    id: int
    assignment_file: str
    assignment_line: int
    assignment_col: int
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
    col: int
    target_var: str
    source_expr: str
    in_function: str
    property_path: str | None

class AssignmentsJsxRow(TypedDict):
    """Row type for assignments_jsx table."""
    file: str
    line: int
    target_var: str
    source_expr: str
    in_function: str
    property_path: str | None
    jsx_mode: str
    extraction_pass: int | None

class BashCommandArgsRow(TypedDict):
    """Row type for bash_command_args table."""
    file: str
    command_line: int
    command_pipeline_position: int | None
    arg_index: int
    arg_value: str
    is_quoted: int
    quote_type: str
    has_expansion: int
    expansion_vars: str | None
    normalized_flags: str | None

class BashCommandsRow(TypedDict):
    """Row type for bash_commands table."""
    file: str
    line: int
    command_name: str
    pipeline_position: int | None
    containing_function: str | None
    wrapped_command: str | None

class BashControlFlowsRow(TypedDict):
    """Row type for bash_control_flows table."""
    file: str
    line: int
    end_line: int
    type: str
    condition: str | None
    has_else: int | None
    case_value: str | None
    num_patterns: int | None
    loop_variable: str | None
    iterable: str | None
    loop_expression: str | None
    containing_function: str | None

class BashFunctionsRow(TypedDict):
    """Row type for bash_functions table."""
    file: str
    line: int
    end_line: int
    name: str
    style: str
    body_start_line: int | None
    body_end_line: int | None

class BashPipesRow(TypedDict):
    """Row type for bash_pipes table."""
    file: str
    line: int
    pipeline_id: int
    position: int
    command_text: str
    containing_function: str | None

class BashRedirectionsRow(TypedDict):
    """Row type for bash_redirections table."""
    file: str
    line: int
    direction: str
    target: str
    fd_number: int | None
    containing_function: str | None

class BashSetOptionsRow(TypedDict):
    """Row type for bash_set_options table."""
    file: str
    line: int
    options: str
    containing_function: str | None

class BashSourcesRow(TypedDict):
    """Row type for bash_sources table."""
    file: str
    line: int
    sourced_path: str
    syntax: str
    has_variable_expansion: int
    containing_function: str | None

class BashSubshellsRow(TypedDict):
    """Row type for bash_subshells table."""
    file: str
    line: int
    col: int
    syntax: str
    command_text: str
    capture_target: str | None
    containing_function: str | None

class BashVariablesRow(TypedDict):
    """Row type for bash_variables table."""
    file: str
    line: int
    name: str
    scope: str
    readonly: int
    value_expr: str | None
    containing_function: str | None

class BullmqQueuesRow(TypedDict):
    """Row type for bullmq_queues table."""
    file: str
    line: int
    queue_name: str
    redis_config: str | None

class BullmqWorkersRow(TypedDict):
    """Row type for bullmq_workers table."""
    file: str
    line: int
    queue_name: str
    worker_function: str | None
    processor_path: str | None

class CargoDependenciesRow(TypedDict):
    """Row type for cargo_dependencies table."""
    file_path: str
    name: str
    version_spec: str | None
    is_dev: bool | None
    features: str | None

class CargoPackageConfigsRow(TypedDict):
    """Row type for cargo_package_configs table."""
    file_path: str
    package_name: str | None
    package_version: str | None
    edition: str | None

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
    construct_name: str | None

class CdkFindingsRow(TypedDict):
    """Row type for cdk_findings table."""
    finding_id: str
    file_path: str
    construct_id: str | None
    category: str
    severity: str
    title: str
    description: str
    remediation: str | None
    line: int | None

class CfgBlockStatementsRow(TypedDict):
    """Row type for cfg_block_statements table."""
    block_id: int
    statement_type: str
    line: int
    statement_text: str | None

class CfgBlockStatementsJsxRow(TypedDict):
    """Row type for cfg_block_statements_jsx table."""
    block_id: int
    statement_type: str
    line: int
    statement_text: str | None
    jsx_mode: str | None
    extraction_pass: int | None

class CfgBlocksRow(TypedDict):
    """Row type for cfg_blocks table."""
    id: int
    file: str
    function_name: str
    block_type: str
    start_line: int | None
    end_line: int | None
    condition_expr: str | None

class CfgBlocksJsxRow(TypedDict):
    """Row type for cfg_blocks_jsx table."""
    id: int
    file: str
    function_name: str
    block_type: str
    start_line: int | None
    end_line: int | None
    condition_expr: str | None
    jsx_mode: str | None
    extraction_pass: int | None

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
    jsx_mode: str | None
    extraction_pass: int | None

class ClassDecoratorArgsRow(TypedDict):
    """Row type for class_decorator_args table."""
    file: str
    class_line: int
    class_name: str
    decorator_index: int
    arg_index: int
    arg_value: str

class ClassDecoratorsRow(TypedDict):
    """Row type for class_decorators table."""
    file: str
    class_line: int
    class_name: str
    decorator_index: int
    decorator_name: str
    decorator_line: int

class ClassPropertiesRow(TypedDict):
    """Row type for class_properties table."""
    file: str
    line: int
    class_name: str
    property_name: str
    property_type: str | None
    is_optional: bool | None
    is_readonly: bool | None
    access_modifier: str | None
    has_declare: bool | None
    initializer: str | None

class CodeDiffsRow(TypedDict):
    """Row type for code_diffs table."""
    id: int
    snapshot_id: int
    file_path: str
    diff_text: str | None
    added_lines: int | None
    removed_lines: int | None

class CodeSnapshotsRow(TypedDict):
    """Row type for code_snapshots table."""
    id: int
    plan_id: int
    task_id: int | None
    sequence: int | None
    checkpoint_name: str
    timestamp: str
    git_ref: str | None
    shadow_sha: str | None
    files_json: str | None

class ComposeServiceCapabilitiesRow(TypedDict):
    """Row type for compose_service_capabilities table."""
    id: int
    file_path: str
    service_name: str
    capability: str
    is_add: bool

class ComposeServiceDepsRow(TypedDict):
    """Row type for compose_service_deps table."""
    id: int
    file_path: str
    service_name: str
    depends_on_service: str
    condition: str | None

class ComposeServiceEnvRow(TypedDict):
    """Row type for compose_service_env table."""
    id: int
    file_path: str
    service_name: str
    var_name: str
    var_value: str | None

class ComposeServicePortsRow(TypedDict):
    """Row type for compose_service_ports table."""
    id: int
    file_path: str
    service_name: str
    host_port: int | None
    container_port: int
    protocol: str | None

class ComposeServiceVolumesRow(TypedDict):
    """Row type for compose_service_volumes table."""
    id: int
    file_path: str
    service_name: str
    host_path: str | None
    container_path: str
    mode: str | None

class ComposeServicesRow(TypedDict):
    """Row type for compose_services table."""
    file_path: str
    service_name: str
    image: str | None
    is_privileged: bool | None
    network_mode: str | None
    user: str | None
    security_opt: str | None
    restart: str | None
    command: str | None
    entrypoint: str | None
    healthcheck: str | None
    mem_limit: str | None
    cpus: str | None
    read_only: bool | None

class ConfigFilesRow(TypedDict):
    """Row type for config_files table."""
    path: str
    content: str
    type: str
    context_dir: str | None

class DependencyVersionsRow(TypedDict):
    """Row type for dependency_versions table."""
    manager: str
    package_name: str
    locked_version: str
    latest_version: str | None
    delta: str | None
    is_outdated: bool
    last_checked: str
    error: str | None

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
    base_image: str | None
    user: str | None
    has_healthcheck: bool | None

class DockerfileEnvVarsRow(TypedDict):
    """Row type for dockerfile_env_vars table."""
    id: int
    file_path: str
    var_name: str
    var_value: str | None
    is_build_arg: bool | None

class DockerfileInstructionsRow(TypedDict):
    """Row type for dockerfile_instructions table."""
    id: int
    file_path: str
    line: int
    instruction: str
    arguments: str | None

class DockerfilePortsRow(TypedDict):
    """Row type for dockerfile_ports table."""
    id: int
    file_path: str
    port: int
    protocol: str | None

class EnvVarUsageRow(TypedDict):
    """Row type for env_var_usage table."""
    file: str
    line: int
    var_name: str
    access_type: str
    in_function: str | None
    property_access: str | None

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
    handler_file: str | None
    handler_function: str | None
    handler_line: int | None

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
    column: int | None
    rule: str
    tool: str
    message: str | None
    severity: str
    category: str | None
    confidence: float | None
    code_snippet: str | None
    cwe: str | None
    timestamp: str
    cfg_function: str | None
    cfg_complexity: int | None
    cfg_block_count: int | None
    cfg_edge_count: int | None
    cfg_has_loops: int | None
    cfg_has_recursion: int | None
    cfg_start_line: int | None
    cfg_end_line: int | None
    cfg_threshold: int | None
    graph_id: str | None
    graph_in_degree: int | None
    graph_out_degree: int | None
    graph_total_connections: int | None
    graph_centrality: float | None
    graph_score: float | None
    graph_cycle_nodes: str | None
    mypy_error_code: str | None
    mypy_severity_int: int | None
    mypy_column: int | None
    tf_finding_id: str | None
    tf_resource_id: str | None
    tf_remediation: str | None
    tf_graph_context: str | None
    details_json: str | None

class FrameworkSafeSinksRow(TypedDict):
    """Row type for framework_safe_sinks table."""
    framework_id: int | None
    sink_pattern: str
    sink_type: str
    is_safe: bool | None
    reason: str | None

class FrameworkTaintPatternsRow(TypedDict):
    """Row type for framework_taint_patterns table."""
    id: int
    framework_id: int
    pattern: str
    pattern_type: str
    category: str | None

class FrameworksRow(TypedDict):
    """Row type for frameworks table."""
    id: int
    name: str
    version: str | None
    language: str
    path: str | None
    source: str | None
    package_manager: str | None
    is_primary: bool | None

class FrontendApiCallsRow(TypedDict):
    """Row type for frontend_api_calls table."""
    file: str
    line: int
    method: str
    url_literal: str
    body_variable: str | None
    function_name: str | None

class FuncDecoratorArgsRow(TypedDict):
    """Row type for func_decorator_args table."""
    file: str
    function_line: int
    function_name: str
    decorator_index: int
    arg_index: int
    arg_value: str

class FuncDecoratorsRow(TypedDict):
    """Row type for func_decorators table."""
    file: str
    function_line: int
    function_name: str
    decorator_index: int
    decorator_name: str
    decorator_line: int

class FuncParamDecoratorsRow(TypedDict):
    """Row type for func_param_decorators table."""
    file: str
    function_line: int
    function_name: str
    param_index: int
    decorator_name: str
    decorator_args: str | None

class FuncParamsRow(TypedDict):
    """Row type for func_params table."""
    file: str
    function_line: int
    function_name: str
    param_index: int
    param_name: str
    param_type: str | None

class FunctionCallArgsRow(TypedDict):
    """Row type for function_call_args table."""
    file: str
    line: int
    caller_function: str
    callee_function: str
    argument_index: int | None
    argument_expr: str | None
    param_name: str | None
    callee_file_path: str | None

class FunctionCallArgsJsxRow(TypedDict):
    """Row type for function_call_args_jsx table."""
    file: str
    line: int
    caller_function: str
    callee_function: str
    argument_index: int | None
    argument_expr: str | None
    param_name: str | None
    jsx_mode: str
    extraction_pass: int | None

class FunctionReturnSourcesRow(TypedDict):
    """Row type for function_return_sources table."""
    id: int
    return_file: str
    return_line: int
    return_col: int
    return_function: str
    return_var_name: str

class FunctionReturnSourcesJsxRow(TypedDict):
    """Row type for function_return_sources_jsx table."""
    id: int
    return_file: str
    return_line: int
    return_function: str | None
    jsx_mode: str
    return_var_name: str
    extraction_pass: int | None

class FunctionReturnsRow(TypedDict):
    """Row type for function_returns table."""
    file: str
    line: int
    col: int
    function_name: str
    return_expr: str
    has_jsx: bool | None
    returns_component: bool | None
    cleanup_operations: str | None

class FunctionReturnsJsxRow(TypedDict):
    """Row type for function_returns_jsx table."""
    file: str
    line: int
    function_name: str | None
    return_expr: str | None
    has_jsx: bool | None
    returns_component: bool | None
    cleanup_operations: str | None
    jsx_mode: str
    extraction_pass: int | None

class GithubJobDependenciesRow(TypedDict):
    """Row type for github_job_dependencies table."""
    job_id: str
    needs_job_id: str

class GithubJobsRow(TypedDict):
    """Row type for github_jobs table."""
    job_id: str
    workflow_path: str
    job_key: str
    job_name: str | None
    runs_on: str | None
    strategy: str | None
    permissions: str | None
    env: str | None
    if_condition: str | None
    timeout_minutes: int | None
    uses_reusable_workflow: bool | None
    reusable_workflow_path: str | None

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
    step_name: str | None
    uses_action: str | None
    uses_version: str | None
    run_script: str | None
    shell: str | None
    env: str | None
    with_args: str | None
    if_condition: str | None
    timeout_minutes: int | None
    continue_on_error: bool | None

class GithubWorkflowsRow(TypedDict):
    """Row type for github_workflows table."""
    workflow_path: str
    workflow_name: str | None
    on_triggers: str
    permissions: str | None
    concurrency: str | None
    env: str | None

class GoCapturedVarsRow(TypedDict):
    """Row type for go_captured_vars table."""
    file: str
    line: int
    goroutine_id: int
    var_name: str
    var_type: str | None
    is_loop_var: bool | None

class GoChannelOpsRow(TypedDict):
    """Row type for go_channel_ops table."""
    file: str
    line: int
    channel_name: str | None
    operation: str
    containing_func: str | None

class GoChannelsRow(TypedDict):
    """Row type for go_channels table."""
    file: str
    line: int
    name: str
    element_type: str | None
    direction: str | None
    buffer_size: int | None

class GoConstantsRow(TypedDict):
    """Row type for go_constants table."""
    file: str
    line: int
    name: str
    value: str | None
    type: str | None
    is_exported: bool | None

class GoDeferStatementsRow(TypedDict):
    """Row type for go_defer_statements table."""
    file: str
    line: int
    containing_func: str | None
    deferred_expr: str

class GoErrorReturnsRow(TypedDict):
    """Row type for go_error_returns table."""
    file: str
    line: int
    func_name: str
    returns_error: bool | None

class GoFuncParamsRow(TypedDict):
    """Row type for go_func_params table."""
    file: str
    func_name: str
    func_line: int
    param_index: int
    param_name: str | None
    param_type: str
    is_variadic: bool | None

class GoFuncReturnsRow(TypedDict):
    """Row type for go_func_returns table."""
    file: str
    func_name: str
    func_line: int
    return_index: int
    return_name: str | None
    return_type: str

class GoFunctionsRow(TypedDict):
    """Row type for go_functions table."""
    file: str
    line: int
    name: str
    signature: str | None
    is_exported: bool | None
    is_async: bool | None
    doc_comment: str | None

class GoGoroutinesRow(TypedDict):
    """Row type for go_goroutines table."""
    file: str
    line: int
    containing_func: str | None
    spawned_expr: str
    is_anonymous: bool | None

class GoImportsRow(TypedDict):
    """Row type for go_imports table."""
    file: str
    line: int
    path: str
    alias: str | None
    is_dot_import: bool | None

class GoInterfaceMethodsRow(TypedDict):
    """Row type for go_interface_methods table."""
    file: str
    interface_name: str
    method_name: str
    signature: str

class GoInterfacesRow(TypedDict):
    """Row type for go_interfaces table."""
    file: str
    line: int
    name: str
    is_exported: bool | None
    doc_comment: str | None

class GoMethodsRow(TypedDict):
    """Row type for go_methods table."""
    file: str
    line: int
    receiver_type: str
    receiver_name: str | None
    is_pointer_receiver: bool | None
    name: str
    signature: str | None
    is_exported: bool | None

class GoMiddlewareRow(TypedDict):
    """Row type for go_middleware table."""
    file: str
    line: int
    framework: str
    router_var: str | None
    middleware_func: str
    is_global: bool | None

class GoModuleConfigsRow(TypedDict):
    """Row type for go_module_configs table."""
    file_path: str
    module_path: str
    go_version: str | None

class GoModuleDependenciesRow(TypedDict):
    """Row type for go_module_dependencies table."""
    file_path: str
    module_path: str
    version: str
    is_indirect: bool | None

class GoPackagesRow(TypedDict):
    """Row type for go_packages table."""
    file: str
    line: int
    name: str
    import_path: str | None

class GoRoutesRow(TypedDict):
    """Row type for go_routes table."""
    file: str
    line: int
    framework: str
    method: str | None
    path: str | None
    handler_func: str | None

class GoStructFieldsRow(TypedDict):
    """Row type for go_struct_fields table."""
    file: str
    struct_name: str
    field_name: str
    field_type: str
    tag: str | None
    is_embedded: bool | None
    is_exported: bool | None

class GoStructsRow(TypedDict):
    """Row type for go_structs table."""
    file: str
    line: int
    name: str
    is_exported: bool | None
    doc_comment: str | None

class GoTypeAssertionsRow(TypedDict):
    """Row type for go_type_assertions table."""
    file: str
    line: int
    expr: str
    asserted_type: str
    is_type_switch: bool | None
    containing_func: str | None

class GoTypeParamsRow(TypedDict):
    """Row type for go_type_params table."""
    file: str
    line: int
    parent_name: str
    parent_kind: str
    param_index: int
    param_name: str
    type_constraint: str | None

class GoVariablesRow(TypedDict):
    """Row type for go_variables table."""
    file: str
    line: int
    name: str
    type: str | None
    initial_value: str | None
    is_exported: bool | None
    is_package_level: bool | None
    containing_func: str | None

class GraphqlArgDirectivesRow(TypedDict):
    """Row type for graphql_arg_directives table."""
    id: int
    field_id: int
    arg_name: str
    directive_name: str
    arguments_json: str | None

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
    has_default: bool | None
    default_value: str | None
    is_nullable: bool | None

class GraphqlFieldDirectivesRow(TypedDict):
    """Row type for graphql_field_directives table."""
    id: int
    field_id: int
    directive_name: str
    arguments_json: str | None

class GraphqlFieldsRow(TypedDict):
    """Row type for graphql_fields table."""
    field_id: int
    type_id: int
    field_name: str
    return_type: str
    is_list: bool | None
    is_nullable: bool | None
    line: int | None
    column: int | None

class GraphqlFindingsCacheRow(TypedDict):
    """Row type for graphql_findings_cache table."""
    finding_id: int
    field_id: int | None
    resolver_symbol_id: int | None
    rule: str
    severity: str
    description: str | None
    message: str | None
    confidence: str | None
    provenance: str

class GraphqlResolverMappingsRow(TypedDict):
    """Row type for graphql_resolver_mappings table."""
    field_id: int
    resolver_symbol_id: int
    resolver_path: str
    resolver_line: int
    resolver_language: str
    resolver_export: str | None
    binding_style: str

class GraphqlResolverParamsRow(TypedDict):
    """Row type for graphql_resolver_params table."""
    resolver_symbol_id: int
    arg_name: str
    param_name: str
    param_index: int
    is_kwargs: bool | None
    is_list_input: bool | None

class GraphqlSchemasRow(TypedDict):
    """Row type for graphql_schemas table."""
    file_path: str
    schema_hash: str
    language: str
    last_modified: int | None

class GraphqlTypesRow(TypedDict):
    """Row type for graphql_types table."""
    type_id: int
    schema_path: str
    type_name: str
    kind: str
    implements: str | None
    description: str | None
    line: int | None

class ImportSpecifiersRow(TypedDict):
    """Row type for import_specifiers table."""
    file: str
    import_line: int
    specifier_name: str
    original_name: str | None
    is_default: int | None
    is_namespace: int | None
    is_named: int | None

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
    alias_name: str | None
    full_statement: str | None
    resolved_path: str | None

class JwtPatternsRow(TypedDict):
    """Row type for jwt_patterns table."""
    file_path: str
    line_number: int
    pattern_type: str
    pattern_text: str | None
    secret_source: str | None
    algorithm: str | None

class LockAnalysisRow(TypedDict):
    """Row type for lock_analysis table."""
    file_path: str
    lock_type: str
    package_manager_version: str | None
    total_packages: int | None
    duplicate_packages: str | None
    lock_file_version: str | None

class NginxConfigsRow(TypedDict):
    """Row type for nginx_configs table."""
    file_path: str
    block_type: str
    block_context: str | None
    directives: str | None
    level: int | None

class ObjectLiteralsRow(TypedDict):
    """Row type for object_literals table."""
    id: int
    file: str
    line: int
    variable_name: str | None
    property_name: str
    property_value: str
    property_type: str | None
    nested_level: int | None
    in_function: str | None

class OrmQueriesRow(TypedDict):
    """Row type for orm_queries table."""
    file: str
    line: int
    query_type: str
    includes: str | None
    has_limit: bool | None
    has_transaction: bool | None

class OrmRelationshipsRow(TypedDict):
    """Row type for orm_relationships table."""
    file: str
    line: int
    source_model: str
    target_model: str
    relationship_type: str
    foreign_key: str | None
    cascade_delete: bool | None
    as_name: str | None

class PackageConfigsRow(TypedDict):
    """Row type for package_configs table."""
    file_path: str
    package_name: str | None
    version: str | None
    private: bool | None

class PackageDependenciesRow(TypedDict):
    """Row type for package_dependencies table."""
    id: int
    file_path: str
    name: str
    version_spec: str | None
    is_dev: bool | None
    is_peer: bool | None

class PackageEnginesRow(TypedDict):
    """Row type for package_engines table."""
    id: int
    file_path: str
    engine_name: str
    version_spec: str | None

class PackageScriptsRow(TypedDict):
    """Row type for package_scripts table."""
    id: int
    file_path: str
    script_name: str
    script_command: str

class PackageWorkspacesRow(TypedDict):
    """Row type for package_workspaces table."""
    id: int
    file_path: str
    workspace_path: str

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
    description: str | None
    success_criteria: str | None
    status: str
    created_at: str

class PlanSpecsRow(TypedDict):
    """Row type for plan_specs table."""
    id: int
    plan_id: int
    spec_yaml: str
    spec_type: str | None
    created_at: str

class PlanTasksRow(TypedDict):
    """Row type for plan_tasks table."""
    id: int
    plan_id: int
    phase_id: int | None
    task_number: int
    title: str
    description: str | None
    status: str
    audit_status: str | None
    assigned_to: str | None
    spec_id: int | None
    created_at: str
    completed_at: str | None

class PlansRow(TypedDict):
    """Row type for plans table."""
    id: int
    name: str
    description: str | None
    created_at: str
    status: str
    metadata_json: str | None

class PrismaModelsRow(TypedDict):
    """Row type for prisma_models table."""
    model_name: str
    field_name: str
    field_type: str
    is_indexed: bool | None
    is_unique: bool | None
    is_relation: bool | None

class PythonBranchesRow(TypedDict):
    """Row type for python_branches table."""
    id: int | None
    file: str
    line: int
    branch_kind: str
    branch_type: str | None
    has_else: int | None
    has_elif: int | None
    chain_length: int | None
    has_complex_condition: int | None
    nesting_level: int | None
    case_count: int | None
    has_guards: int | None
    has_wildcard: int | None
    pattern_types: str | None
    exception_types: str | None
    handling_strategy: str | None
    variable_name: str | None
    exception_type: str | None
    is_re_raise: int | None
    from_exception: str | None
    message: str | None
    condition: str | None
    has_cleanup: int | None
    cleanup_calls: str | None
    in_function: str | None

class PythonBuildRequiresRow(TypedDict):
    """Row type for python_build_requires table."""
    file_path: str
    name: str
    version_spec: str | None

class PythonClassFeaturesRow(TypedDict):
    """Row type for python_class_features table."""
    id: int | None
    file: str
    line: int
    feature_kind: str
    feature_type: str | None
    class_name: str | None
    name: str | None
    in_class: str | None
    metaclass_name: str | None
    is_definition: int | None
    field_count: int | None
    frozen: int | None
    enum_name: str | None
    enum_type: str | None
    member_count: int | None
    slot_count: int | None
    abstract_method_count: int | None
    method_name: str | None
    method_type: str | None
    category: str | None
    visibility: str | None
    is_name_mangled: int | None
    decorator: str | None
    decorator_type: str | None
    has_arguments: int | None

class PythonCollectionsRow(TypedDict):
    """Row type for python_collections table."""
    id: int | None
    file: str
    line: int
    collection_kind: str
    collection_type: str | None
    operation: str | None
    method: str | None
    in_function: str | None
    has_default: int | None
    mutates_in_place: int | None
    builtin: str | None
    has_key: int | None

class PythonComprehensionsRow(TypedDict):
    """Row type for python_comprehensions table."""
    id: int | None
    file: str
    line: int
    comp_kind: str
    comp_type: str | None
    iteration_var: str | None
    iteration_source: str | None
    result_expr: str | None
    filter_expr: str | None
    has_filter: int | None
    nesting_level: int | None
    in_function: str | None

class PythonControlStatementsRow(TypedDict):
    """Row type for python_control_statements table."""
    id: int | None
    file: str
    line: int
    statement_kind: str
    statement_type: str | None
    loop_type: str | None
    condition_type: str | None
    has_message: int | None
    target_count: int | None
    target_type: str | None
    context_count: int | None
    has_alias: int | None
    is_async: int | None
    in_function: str | None

class PythonDecoratorsRow(TypedDict):
    """Row type for python_decorators table."""
    file: str
    line: int
    decorator_name: str
    decorator_type: str
    target_type: str
    target_name: str
    is_async: bool | None

class PythonDescriptorsRow(TypedDict):
    """Row type for python_descriptors table."""
    id: int | None
    file: str
    line: int
    descriptor_kind: str
    descriptor_type: str | None
    name: str | None
    class_name: str | None
    in_class: str | None
    has_get: int | None
    has_set: int | None
    has_delete: int | None
    is_data_descriptor: int | None
    property_name: str | None
    access_type: str | None
    has_computation: int | None
    has_validation: int | None
    method_name: str | None
    is_functools: int | None

class PythonDjangoMiddlewareRow(TypedDict):
    """Row type for python_django_middleware table."""
    file: str
    line: int
    middleware_class_name: str
    has_process_request: bool | None
    has_process_response: bool | None
    has_process_exception: bool | None
    has_process_view: bool | None
    has_process_template_response: bool | None

class PythonDjangoViewsRow(TypedDict):
    """Row type for python_django_views table."""
    file: str
    line: int
    view_class_name: str
    view_type: str
    base_view_class: str | None
    model_name: str | None
    template_name: str | None
    has_permission_check: bool | None
    http_method_names: str | None
    has_get_queryset_override: bool | None

class PythonExpressionsRow(TypedDict):
    """Row type for python_expressions table."""
    id: int | None
    file: str
    line: int
    expression_kind: str
    expression_type: str | None
    in_function: str | None
    target: str | None
    has_start: int | None
    has_stop: int | None
    has_step: int | None
    is_assignment: int | None
    element_count: int | None
    operation: str | None
    has_rest: int | None
    target_count: int | None
    unpack_type: str | None
    pattern: str | None
    uses_is: int | None
    format_type: str | None
    has_expressions: int | None
    var_count: int | None
    context: str | None
    has_globals: int | None
    has_locals: int | None
    generator_function: str | None
    yield_expr: str | None
    yield_type: str | None
    in_loop: int | None
    condition: str | None
    awaited_expr: str | None
    containing_function: str | None

class PythonFixtureParamsRow(TypedDict):
    """Row type for python_fixture_params table."""
    id: int | None
    file: str
    fixture_id: int
    param_name: str | None
    param_value: str | None
    param_order: int | None

class PythonFrameworkConfigRow(TypedDict):
    """Row type for python_framework_config table."""
    id: int | None
    file: str
    line: int
    config_kind: str
    config_type: str | None
    framework: str
    name: str | None
    endpoint: str | None
    cache_type: str | None
    timeout: int | None
    class_name: str | None
    model_name: str | None
    function_name: str | None
    target_name: str | None
    base_class: str | None
    has_process_request: int | None
    has_process_response: int | None
    has_process_exception: int | None
    has_process_view: int | None
    has_process_template_response: int | None

class PythonFrameworkMethodsRow(TypedDict):
    """Row type for python_framework_methods table."""
    id: int | None
    file: str
    config_id: int
    method_name: str
    method_order: int | None

class PythonFunctionsAdvancedRow(TypedDict):
    """Row type for python_functions_advanced table."""
    id: int | None
    file: str
    line: int
    function_kind: str
    function_type: str | None
    name: str | None
    function_name: str | None
    yield_count: int | None
    has_send: int | None
    has_yield_from: int | None
    is_infinite: int | None
    await_count: int | None
    has_async_for: int | None
    has_async_with: int | None
    parameter_count: int | None
    parameters: str | None
    body: str | None
    captures_closure: int | None
    captured_vars: str | None
    used_in: str | None
    as_name: str | None
    context_expr: str | None
    is_async: int | None
    iter_expr: str | None
    target_var: str | None
    base_case_line: int | None
    calls_function: str | None
    recursion_type: str | None
    cache_size: int | None
    memoization_type: str | None
    is_recursive: int | None
    has_memoization: int | None
    in_function: str | None

class PythonImportsAdvancedRow(TypedDict):
    """Row type for python_imports_advanced table."""
    id: int | None
    file: str
    line: int
    import_kind: str
    import_type: str | None
    module: str | None
    name: str | None
    alias: str | None
    is_relative: int | None
    in_function: str | None
    has_alias: int | None
    imported_names: str | None
    is_wildcard: int | None
    relative_level: int | None
    attribute: str | None
    is_default: int | None
    export_type: str | None

class PythonIoOperationsRow(TypedDict):
    """Row type for python_io_operations table."""
    id: int | None
    file: str
    line: int
    io_kind: str
    io_type: str | None
    operation: str | None
    target: str | None
    is_static: int | None
    flow_type: str | None
    function_name: str | None
    parameter_name: str | None
    return_expr: str | None
    is_async: int | None
    in_function: str | None

class PythonLiteralsRow(TypedDict):
    """Row type for python_literals table."""
    id: int | None
    file: str
    line: int
    literal_kind: str
    literal_type: str | None
    name: str | None
    literal_value_1: str | None
    literal_value_2: str | None
    literal_value_3: str | None
    literal_value_4: str | None
    literal_value_5: str | None
    function_name: str | None
    overload_count: int | None
    variants: str | None

class PythonLoopsRow(TypedDict):
    """Row type for python_loops table."""
    id: int | None
    file: str
    line: int
    loop_kind: str
    loop_type: str | None
    has_else: int | None
    nesting_level: int | None
    target_count: int | None
    in_function: str | None
    is_infinite: int | None
    estimated_complexity: str | None
    has_growing_operation: int | None

class PythonOperatorsRow(TypedDict):
    """Row type for python_operators table."""
    id: int | None
    file: str
    line: int
    operator_kind: str
    operator_type: str | None
    operator: str | None
    in_function: str | None
    container_type: str | None
    chain_length: int | None
    operators: str | None
    has_complex_condition: int | None
    variable: str | None
    used_in: str | None

class PythonOrmFieldsRow(TypedDict):
    """Row type for python_orm_fields table."""
    file: str
    line: int
    model_name: str
    field_name: str
    field_type: str | None
    is_primary_key: bool | None
    is_foreign_key: bool | None
    foreign_key_target: str | None

class PythonOrmModelsRow(TypedDict):
    """Row type for python_orm_models table."""
    file: str
    line: int
    model_name: str
    table_name: str | None
    orm_type: str

class PythonPackageConfigsRow(TypedDict):
    """Row type for python_package_configs table."""
    file_path: str
    file_type: str
    project_name: str | None
    project_version: str | None
    indexed_at: Any | None

class PythonPackageDependenciesRow(TypedDict):
    """Row type for python_package_dependencies table."""
    file_path: str
    name: str
    version_spec: str | None
    is_dev: int | None
    group_name: str | None
    extras: str | None
    git_url: str | None

class PythonProtocolMethodsRow(TypedDict):
    """Row type for python_protocol_methods table."""
    id: int | None
    file: str
    protocol_id: int
    method_name: str
    method_order: int | None

class PythonProtocolsRow(TypedDict):
    """Row type for python_protocols table."""
    id: int | None
    file: str
    line: int
    protocol_kind: str
    protocol_type: str | None
    class_name: str | None
    in_function: str | None
    has_iter: int | None
    has_next: int | None
    is_generator: int | None
    raises_stopiteration: int | None
    has_contains: int | None
    has_getitem: int | None
    has_setitem: int | None
    has_delitem: int | None
    has_len: int | None
    is_mapping: int | None
    is_sequence: int | None
    has_args: int | None
    has_kwargs: int | None
    param_count: int | None
    has_getstate: int | None
    has_setstate: int | None
    has_reduce: int | None
    has_reduce_ex: int | None
    context_expr: str | None
    resource_type: str | None
    variable_name: str | None
    is_async: int | None
    has_copy: int | None
    has_deepcopy: int | None

class PythonRoutesRow(TypedDict):
    """Row type for python_routes table."""
    file: str
    line: int | None
    framework: str
    method: str | None
    pattern: str | None
    handler_function: str | None
    has_auth: bool | None
    dependencies: str | None
    blueprint: str | None

class PythonSchemaValidatorsRow(TypedDict):
    """Row type for python_schema_validators table."""
    id: int | None
    file: str
    schema_id: int
    validator_name: str
    validator_type: str | None
    validator_order: int | None

class PythonSecurityFindingsRow(TypedDict):
    """Row type for python_security_findings table."""
    id: int | None
    file: str
    line: int
    finding_kind: str
    finding_type: str | None
    function_name: str | None
    decorator_name: str | None
    permissions: str | None
    is_vulnerable: int | None
    shell_true: int | None
    is_constant_input: int | None
    is_critical: int | None
    has_concatenation: int | None

class PythonStateMutationsRow(TypedDict):
    """Row type for python_state_mutations table."""
    id: int | None
    file: str
    line: int
    mutation_kind: str
    mutation_type: str | None
    target: str | None
    operator: str | None
    target_type: str | None
    operation: str | None
    is_init: int | None
    is_dunder_method: int | None
    is_property_setter: int | None
    in_function: str | None

class PythonStdlibUsageRow(TypedDict):
    """Row type for python_stdlib_usage table."""
    id: int | None
    file: str
    line: int
    stdlib_kind: str
    module: str | None
    usage_type: str | None
    function_name: str | None
    pattern: str | None
    in_function: str | None
    operation: str | None
    has_flags: int | None
    direction: str | None
    path_type: str | None
    log_level: str | None
    threading_type: str | None
    is_decorator: int | None

class PythonTestCasesRow(TypedDict):
    """Row type for python_test_cases table."""
    id: int | None
    file: str
    line: int
    test_kind: str
    test_type: str | None
    name: str | None
    function_name: str | None
    class_name: str | None
    assertion_type: str | None
    test_expr: str | None

class PythonTestFixturesRow(TypedDict):
    """Row type for python_test_fixtures table."""
    id: int | None
    file: str
    line: int
    fixture_kind: str
    fixture_type: str | None
    name: str | None
    scope: str | None
    autouse: int | None
    in_function: str | None

class PythonTypeDefinitionsRow(TypedDict):
    """Row type for python_type_definitions table."""
    id: int | None
    file: str
    line: int
    type_kind: str
    name: str | None
    type_param_count: int | None
    type_param_1: str | None
    type_param_2: str | None
    type_param_3: str | None
    type_param_4: str | None
    type_param_5: str | None
    is_runtime_checkable: int | None
    methods: str | None

class PythonTypeddictFieldsRow(TypedDict):
    """Row type for python_typeddict_fields table."""
    id: int | None
    file: str
    typeddict_id: int
    field_name: str
    field_type: str | None
    required: int | None
    field_order: int | None

class PythonValidationSchemasRow(TypedDict):
    """Row type for python_validation_schemas table."""
    id: int | None
    file: str
    line: int
    schema_kind: str
    schema_type: str | None
    framework: str
    name: str | None
    field_type: str | None
    required: int | None

class PythonValidatorsRow(TypedDict):
    """Row type for python_validators table."""
    file: str
    line: int
    model_name: str
    field_name: str | None
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
    has_jsx: bool | None
    props_type: str | None

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
    dependency_array: str | None
    callback_body: str | None
    has_cleanup: bool | None
    cleanup_type: str | None

class RefactorCandidatesRow(TypedDict):
    """Row type for refactor_candidates table."""
    id: int
    file_path: str
    reason: str
    severity: str
    loc: int | None
    cyclomatic_complexity: int | None
    duplication_percent: float | None
    num_dependencies: int | None
    detected_at: str
    metadata_json: str | None

class RefactorHistoryRow(TypedDict):
    """Row type for refactor_history table."""
    id: int
    timestamp: str
    target_file: str
    refactor_type: str
    migrations_found: int | None
    migrations_complete: int | None
    schema_consistent: int | None
    validation_status: str | None
    details_json: str | None

class RefsRow(TypedDict):
    """Row type for refs table."""
    src: str
    kind: str
    value: str
    line: int | None

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
    sanitizer_file: str | None
    sanitizer_line: int | None
    sanitizer_method: str | None
    engine: str

class ReturnSourceVarsRow(TypedDict):
    """Row type for return_source_vars table."""
    file: str
    line: int
    function_name: str
    source_var: str
    var_index: int

class RouterMountsRow(TypedDict):
    """Row type for router_mounts table."""
    file: str
    line: int
    mount_path_expr: str
    router_variable: str
    is_literal: bool | None

class RustAsyncFunctionsRow(TypedDict):
    """Row type for rust_async_functions table."""
    file_path: str
    line: int
    function_name: str
    return_type: str | None
    has_await: bool | None
    await_count: int | None

class RustAttributesRow(TypedDict):
    """Row type for rust_attributes table."""
    file_path: str
    line: int
    attribute_name: str
    args: str | None
    target_type: str | None
    target_name: str | None
    target_line: int | None

class RustAwaitPointsRow(TypedDict):
    """Row type for rust_await_points table."""
    file_path: str
    line: int
    containing_function: str | None
    awaited_expression: str | None

class RustEnumVariantsRow(TypedDict):
    """Row type for rust_enum_variants table."""
    file_path: str
    enum_line: int
    variant_index: int
    variant_name: str
    variant_kind: str | None
    fields_json: str | None
    discriminant: str | None

class RustEnumsRow(TypedDict):
    """Row type for rust_enums table."""
    file_path: str
    line: int
    end_line: int | None
    name: str
    visibility: str | None
    generics: str | None
    derives_json: str | None

class RustExternBlocksRow(TypedDict):
    """Row type for rust_extern_blocks table."""
    file_path: str
    line: int
    end_line: int | None
    abi: str | None

class RustExternFunctionsRow(TypedDict):
    """Row type for rust_extern_functions table."""
    file_path: str
    line: int
    name: str
    abi: str | None
    return_type: str | None
    params_json: str | None
    is_variadic: bool | None

class RustFunctionsRow(TypedDict):
    """Row type for rust_functions table."""
    file_path: str
    line: int
    end_line: int | None
    name: str
    visibility: str | None
    is_async: bool | None
    is_unsafe: bool | None
    is_const: bool | None
    is_extern: bool | None
    abi: str | None
    return_type: str | None
    params_json: str | None
    generics: str | None
    where_clause: str | None

class RustGenericsRow(TypedDict):
    """Row type for rust_generics table."""
    file_path: str
    parent_line: int
    parent_type: str
    param_name: str
    param_kind: str | None
    bounds: str | None
    default_value: str | None

class RustImplBlocksRow(TypedDict):
    """Row type for rust_impl_blocks table."""
    file_path: str
    line: int
    end_line: int | None
    target_type_raw: str
    target_type_resolved: str | None
    trait_name: str | None
    trait_resolved: str | None
    generics: str | None
    where_clause: str | None
    is_unsafe: bool | None

class RustLifetimesRow(TypedDict):
    """Row type for rust_lifetimes table."""
    file_path: str
    parent_line: int
    lifetime_name: str
    is_static: bool | None

class RustMacroInvocationsRow(TypedDict):
    """Row type for rust_macro_invocations table."""
    file_path: str
    line: int
    macro_name: str
    containing_function: str | None
    args_sample: str | None

class RustMacrosRow(TypedDict):
    """Row type for rust_macros table."""
    file_path: str
    line: int
    name: str
    macro_type: str | None
    visibility: str | None

class RustModulesRow(TypedDict):
    """Row type for rust_modules table."""
    file_path: str
    module_name: str
    line: int
    visibility: str | None
    is_inline: bool | None
    parent_module: str | None

class RustStructFieldsRow(TypedDict):
    """Row type for rust_struct_fields table."""
    file_path: str
    struct_line: int
    field_index: int
    field_name: str | None
    field_type: str
    visibility: str | None
    is_pub: bool | None

class RustStructsRow(TypedDict):
    """Row type for rust_structs table."""
    file_path: str
    line: int
    end_line: int | None
    name: str
    visibility: str | None
    generics: str | None
    is_tuple_struct: bool | None
    is_unit_struct: bool | None
    derives_json: str | None

class RustTraitMethodsRow(TypedDict):
    """Row type for rust_trait_methods table."""
    file_path: str
    trait_line: int
    method_line: int
    method_name: str
    return_type: str | None
    params_json: str | None
    has_default: bool | None
    is_async: bool | None

class RustTraitsRow(TypedDict):
    """Row type for rust_traits table."""
    file_path: str
    line: int
    end_line: int | None
    name: str
    visibility: str | None
    generics: str | None
    supertraits: str | None
    is_unsafe: bool | None
    is_auto: bool | None

class RustUnsafeBlocksRow(TypedDict):
    """Row type for rust_unsafe_blocks table."""
    file_path: str
    line_start: int
    line_end: int | None
    containing_function: str | None
    reason: str | None
    safety_comment: str | None
    has_safety_comment: bool | None
    operations_json: str | None

class RustUnsafeTraitsRow(TypedDict):
    """Row type for rust_unsafe_traits table."""
    file_path: str
    line: int
    trait_name: str
    impl_type: str | None

class RustUseStatementsRow(TypedDict):
    """Row type for rust_use_statements table."""
    file_path: str
    line: int
    import_path: str
    local_name: str
    canonical_path: str | None
    is_glob: bool | None
    visibility: str | None

class SequelizeAssociationsRow(TypedDict):
    """Row type for sequelize_associations table."""
    file: str
    line: int
    model_name: str
    association_type: str
    target_model: str
    foreign_key: str | None
    through_table: str | None

class SequelizeModelFieldsRow(TypedDict):
    """Row type for sequelize_model_fields table."""
    file: str
    model_name: str
    field_name: str
    data_type: str
    is_primary_key: int | None
    is_nullable: int | None
    is_unique: int | None
    default_value: str | None

class SequelizeModelsRow(TypedDict):
    """Row type for sequelize_models table."""
    file: str
    line: int
    model_name: str
    table_name: str | None
    extends_model: bool | None

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
    end_line: int | None
    type_annotation: str | None
    parameters: str | None
    is_typed: bool | None

class SymbolsJsxRow(TypedDict):
    """Row type for symbols_jsx table."""
    path: str
    name: str
    type: str
    line: int
    col: int
    jsx_mode: str
    extraction_pass: int | None

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

class TerraformDataSourcesRow(TypedDict):
    """Row type for terraform_data_sources table."""
    data_id: str
    file_path: str
    data_type: str
    data_name: str
    line: int | None

class TerraformFilesRow(TypedDict):
    """Row type for terraform_files table."""
    file_path: str
    module_name: str | None
    stack_name: str | None
    backend_type: str | None
    providers_json: str | None
    is_module: bool | None
    module_source: str | None

class TerraformFindingsRow(TypedDict):
    """Row type for terraform_findings table."""
    finding_id: str
    file_path: str
    resource_id: str | None
    category: str
    severity: str
    title: str
    description: str | None
    graph_context_json: str | None
    remediation: str | None
    line: int | None

class TerraformOutputsRow(TypedDict):
    """Row type for terraform_outputs table."""
    output_id: str
    file_path: str
    output_name: str
    value_json: str | None
    is_sensitive: bool | None
    description: str | None
    line: int | None

class TerraformResourceDepsRow(TypedDict):
    """Row type for terraform_resource_deps table."""
    id: int
    resource_id: str
    depends_on_ref: str

class TerraformResourcePropertiesRow(TypedDict):
    """Row type for terraform_resource_properties table."""
    id: int
    resource_id: str
    property_name: str
    property_value: str | None
    is_sensitive: bool | None

class TerraformResourcesRow(TypedDict):
    """Row type for terraform_resources table."""
    resource_id: str
    file_path: str
    resource_type: str
    resource_name: str
    module_path: str | None
    has_public_exposure: bool | None
    line: int | None

class TerraformVariableValuesRow(TypedDict):
    """Row type for terraform_variable_values table."""
    id: int
    file_path: str
    variable_name: str
    variable_value_json: str | None
    line: int | None
    is_sensitive_context: bool | None

class TerraformVariablesRow(TypedDict):
    """Row type for terraform_variables table."""
    variable_id: str
    file_path: str
    variable_name: str
    variable_type: str | None
    default_json: str | None
    is_sensitive: bool | None
    description: str | None
    source_file: str | None
    line: int | None

class TypeAnnotationsRow(TypedDict):
    """Row type for type_annotations table."""
    file: str
    line: int
    column: int | None
    symbol_name: str
    symbol_kind: str
    type_annotation: str | None
    is_any: bool | None
    is_unknown: bool | None
    is_generic: bool | None
    has_type_params: bool | None
    type_params: str | None
    return_type: str | None
    extends_type: str | None

class ValidationFrameworkUsageRow(TypedDict):
    """Row type for validation_framework_usage table."""
    file_path: str
    line: int
    framework: str
    method: str
    variable_name: str | None
    is_validator: bool | None
    argument_expr: str | None

class VariableUsageRow(TypedDict):
    """Row type for variable_usage table."""
    file: str
    line: int
    variable_name: str
    usage_type: str
    in_component: str | None
    in_hook: str | None
    scope_level: int | None

class VueComponentEmitsRow(TypedDict):
    """Row type for vue_component_emits table."""
    file: str
    component_name: str
    emit_name: str
    payload_type: str | None

class VueComponentPropsRow(TypedDict):
    """Row type for vue_component_props table."""
    file: str
    component_name: str
    prop_name: str
    prop_type: str | None
    is_required: int | None
    default_value: str | None

class VueComponentSetupReturnsRow(TypedDict):
    """Row type for vue_component_setup_returns table."""
    file: str
    component_name: str
    return_name: str
    return_type: str | None

class VueComponentsRow(TypedDict):
    """Row type for vue_components table."""
    file: str
    name: str
    type: str
    start_line: int
    end_line: int
    has_template: bool | None
    has_style: bool | None
    composition_api_used: bool | None

class VueDirectivesRow(TypedDict):
    """Row type for vue_directives table."""
    file: str
    line: int
    directive_name: str
    expression: str | None
    in_component: str | None
    has_key: bool | None
    modifiers: str | None

class VueHooksRow(TypedDict):
    """Row type for vue_hooks table."""
    file: str
    line: int
    component_name: str
    hook_name: str
    hook_type: str
    dependencies: str | None
    return_value: str | None
    is_async: bool | None

class VueProvideInjectRow(TypedDict):
    """Row type for vue_provide_inject table."""
    file: str
    line: int
    component_name: str
    operation_type: str
    key_name: str
    value_expr: str | None
    is_reactive: bool | None
