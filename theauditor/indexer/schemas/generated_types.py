# Auto-generated TypedDict definitions from schema
from typing import TypedDict, Any

class AngularComponentsRow(TypedDict):
    """Row type for angular_components table."""
    file: str
    line: int
    component_name: str
    selector: str | None
    template_path: str | None
    style_paths: str | None
    has_lifecycle_hooks: bool | None

class AngularGuardsRow(TypedDict):
    """Row type for angular_guards table."""
    file: str
    line: int
    guard_name: str
    guard_type: str
    implements_interface: str | None

class AngularModulesRow(TypedDict):
    """Row type for angular_modules table."""
    file: str
    line: int
    module_name: str
    declarations: str | None
    imports: str | None
    providers: str | None
    exports: str | None

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
    line: int | None
    method: str
    pattern: str
    path: str | None
    full_path: str | None
    has_auth: bool | None
    handler_function: str | None

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
    start_line: int
    end_line: int
    condition_expr: str | None

class CfgBlocksJsxRow(TypedDict):
    """Row type for cfg_blocks_jsx table."""
    id: int
    file: str
    function_name: str
    block_type: str
    start_line: int
    end_line: int
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

class ComposeServicesRow(TypedDict):
    """Row type for compose_services table."""
    file_path: str
    service_name: str
    image: str | None
    ports: str | None
    volumes: str | None
    environment: str | None
    is_privileged: bool | None
    network_mode: str | None
    user: str | None
    cap_add: str | None
    cap_drop: str | None
    security_opt: str | None
    restart: str | None
    command: str | None
    entrypoint: str | None
    depends_on: str | None
    healthcheck: str | None

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
    exposed_ports: str | None
    env_vars: str | None
    build_args: str | None
    user: str | None
    has_healthcheck: bool | None

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
    details_json: str | None

class FrameworkSafeSinksRow(TypedDict):
    """Row type for framework_safe_sinks table."""
    framework_id: int | None
    sink_pattern: str
    sink_type: str
    is_safe: bool | None
    reason: str | None

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

class FunctionReturnsRow(TypedDict):
    """Row type for function_returns table."""
    file: str
    line: int
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
    directives_json: str | None

class GraphqlFieldsRow(TypedDict):
    """Row type for graphql_fields table."""
    field_id: int
    type_id: int
    field_name: str
    return_type: str
    is_list: bool | None
    is_nullable: bool | None
    directives_json: str | None
    line: int | None
    column: int | None

class GraphqlFindingsCacheRow(TypedDict):
    """Row type for graphql_findings_cache table."""
    finding_id: int
    field_id: int | None
    resolver_symbol_id: int | None
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
    dependencies: str | None
    dev_dependencies: str | None
    peer_dependencies: str | None
    scripts: str | None
    engines: str | None
    workspaces: str | None
    private: bool | None

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

class PythonAbstractClassesRow(TypedDict):
    """Row type for python_abstract_classes table."""
    file: str
    line: int
    class_name: str
    abstract_method_count: int | None

class PythonArgumentMutationsRow(TypedDict):
    """Row type for python_argument_mutations table."""
    file: str
    line: int
    parameter_name: str
    mutation_type: str
    mutation_detail: str
    in_function: str

class PythonArithmeticProtocolRow(TypedDict):
    """Row type for python_arithmetic_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    methods: str
    has_reflected: bool | None
    has_inplace: bool | None

class PythonAssertStatementsRow(TypedDict):
    """Row type for python_assert_statements table."""
    id: int
    file: str
    line: int
    has_message: bool | None
    condition_type: str
    in_function: str

class PythonAssertionPatternsRow(TypedDict):
    """Row type for python_assertion_patterns table."""
    file: str
    line: int
    function_name: str
    assertion_type: str
    test_expr: str | None
    assertion_method: str | None

class PythonAsyncForLoopsRow(TypedDict):
    """Row type for python_async_for_loops table."""
    id: int
    file: str
    line: int
    has_else: bool | None
    target_count: int
    in_function: str

class PythonAsyncFunctionsRow(TypedDict):
    """Row type for python_async_functions table."""
    file: str
    line: int
    function_name: str
    has_await: bool | None
    await_count: int | None
    has_async_with: bool | None
    has_async_for: bool | None

class PythonAsyncGeneratorsRow(TypedDict):
    """Row type for python_async_generators table."""
    file: str
    line: int
    generator_type: str
    target_vars: str | None
    iterable_expr: str | None
    function_name: str | None

class PythonAttributeAccessProtocolRow(TypedDict):
    """Row type for python_attribute_access_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    has_getattr: bool | None
    has_setattr: bool | None
    has_delattr: bool | None
    has_getattribute: bool | None

class PythonAugmentedAssignmentsRow(TypedDict):
    """Row type for python_augmented_assignments table."""
    file: str
    line: int
    target: str
    operator: str
    target_type: str
    in_function: str

class PythonAuthDecoratorsRow(TypedDict):
    """Row type for python_auth_decorators table."""
    file: str
    line: int
    function_name: str
    decorator_name: str
    permissions: str | None

class PythonAwaitExpressionsRow(TypedDict):
    """Row type for python_await_expressions table."""
    file: str
    line: int
    await_expr: str
    containing_function: str | None

class PythonBlueprintsRow(TypedDict):
    """Row type for python_blueprints table."""
    file: str
    line: int | None
    blueprint_name: str
    url_prefix: str | None
    subdomain: str | None

class PythonBreakContinuePassRow(TypedDict):
    """Row type for python_break_continue_pass table."""
    id: int
    file: str
    line: int
    statement_type: str
    loop_type: str
    in_function: str

class PythonBuiltinUsageRow(TypedDict):
    """Row type for python_builtin_usage table."""
    file: str
    line: int
    builtin: str
    has_key: bool | None
    in_function: str

class PythonBytesOperationsRow(TypedDict):
    """Row type for python_bytes_operations table."""
    id: int
    file: str
    line: int
    operation: str
    in_function: str

class PythonCachedPropertyRow(TypedDict):
    """Row type for python_cached_property table."""
    id: int
    file: str
    line: int
    method_name: str
    in_class: str
    is_functools: bool | None

class PythonCallableProtocolRow(TypedDict):
    """Row type for python_callable_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    param_count: int
    has_args: bool | None
    has_kwargs: bool | None

class PythonCeleryBeatSchedulesRow(TypedDict):
    """Row type for python_celery_beat_schedules table."""
    file: str
    line: int
    schedule_name: str
    task_name: str
    schedule_type: str
    schedule_expression: str | None
    args: str | None
    kwargs: str | None

class PythonCeleryTaskCallsRow(TypedDict):
    """Row type for python_celery_task_calls table."""
    file: str
    line: int
    caller_function: str
    task_name: str
    invocation_type: str
    arg_count: int | None
    has_countdown: bool | None
    has_eta: bool | None
    queue_override: str | None

class PythonCeleryTasksRow(TypedDict):
    """Row type for python_celery_tasks table."""
    file: str
    line: int
    task_name: str
    decorator_name: str
    arg_count: int | None
    bind: bool | None
    serializer: str | None
    max_retries: int | None
    rate_limit: str | None
    time_limit: int | None
    queue: str | None

class PythonChainedComparisonsRow(TypedDict):
    """Row type for python_chained_comparisons table."""
    file: str
    line: int
    chain_length: int
    operators: str | None
    in_function: str

class PythonClassDecoratorsRow(TypedDict):
    """Row type for python_class_decorators table."""
    id: int
    file: str
    line: int
    class_name: str
    decorator: str
    decorator_type: str
    has_arguments: bool | None

class PythonClassMutationsRow(TypedDict):
    """Row type for python_class_mutations table."""
    file: str
    line: int
    class_name: str
    attribute: str
    operation: str
    in_function: str
    is_classmethod: bool | None

class PythonClosureCapturesRow(TypedDict):
    """Row type for python_closure_captures table."""
    file: str
    line: int
    inner_function: str
    captured_variable: str
    outer_function: str
    is_lambda: bool | None

class PythonCollectionsUsageRow(TypedDict):
    """Row type for python_collections_usage table."""
    file: str
    line: int
    collection_type: str
    default_factory: str | None
    in_function: str

class PythonCommandInjectionRow(TypedDict):
    """Row type for python_command_injection table."""
    file: str
    line: int
    function: str
    shell_true: bool | None
    is_vulnerable: bool | None

class PythonComparisonProtocolRow(TypedDict):
    """Row type for python_comparison_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    methods: str
    is_total_ordering: bool | None
    has_all_rich: bool | None

class PythonComprehensionsRow(TypedDict):
    """Row type for python_comprehensions table."""
    file: str
    line: int
    comp_type: str
    result_expr: str | None
    iteration_var: str | None
    iteration_source: str | None
    has_filter: bool | None
    filter_expr: str | None
    nesting_level: int | None
    in_function: str

class PythonConditionalCallsRow(TypedDict):
    """Row type for python_conditional_calls table."""
    file: str
    line: int
    function_call: str
    condition_expr: str | None
    condition_type: str
    in_function: str
    nesting_level: int

class PythonContainerProtocolRow(TypedDict):
    """Row type for python_container_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    has_len: bool | None
    has_getitem: bool | None
    has_setitem: bool | None
    has_delitem: bool | None
    has_contains: bool | None
    is_sequence: bool | None
    is_mapping: bool | None

class PythonContextManagersRow(TypedDict):
    """Row type for python_context_managers table."""
    file: str
    line: int
    context_type: str
    context_expr: str | None
    as_name: str | None
    is_async: bool | None
    is_custom: bool | None

class PythonContextManagersEnhancedRow(TypedDict):
    """Row type for python_context_managers_enhanced table."""
    file: str
    line: int
    context_expr: str
    variable_name: str | None
    in_function: str
    is_async: bool | None
    resource_type: str | None

class PythonContextlibPatternsRow(TypedDict):
    """Row type for python_contextlib_patterns table."""
    file: str
    line: int
    pattern: str
    is_decorator: bool | None
    in_function: str

class PythonContextvarUsageRow(TypedDict):
    """Row type for python_contextvar_usage table."""
    id: int
    file: str
    line: int
    operation: str
    in_function: str

class PythonCopyProtocolRow(TypedDict):
    """Row type for python_copy_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    has_copy: bool | None
    has_deepcopy: bool | None

class PythonCryptoOperationsRow(TypedDict):
    """Row type for python_crypto_operations table."""
    file: str
    line: int
    algorithm: str | None
    mode: str | None
    is_weak: bool | None
    has_hardcoded_key: bool | None

class PythonDangerousEvalRow(TypedDict):
    """Row type for python_dangerous_eval table."""
    file: str
    line: int
    function: str
    is_constant_input: bool | None
    is_critical: bool | None

class PythonDataclassesRow(TypedDict):
    """Row type for python_dataclasses table."""
    file: str
    line: int
    class_name: str
    frozen: bool | None
    field_count: int | None

class PythonDatetimeOperationsRow(TypedDict):
    """Row type for python_datetime_operations table."""
    file: str
    line: int
    datetime_type: str
    in_function: str

class PythonDecoratorsRow(TypedDict):
    """Row type for python_decorators table."""
    file: str
    line: int
    decorator_name: str
    decorator_type: str
    target_type: str
    target_name: str
    is_async: bool | None

class PythonDelStatementsRow(TypedDict):
    """Row type for python_del_statements table."""
    id: int
    file: str
    line: int
    target_type: str
    target_count: int
    in_function: str

class PythonDescriptorProtocolRow(TypedDict):
    """Row type for python_descriptor_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    has_get: bool | None
    has_set: bool | None
    has_delete: bool | None
    is_data_descriptor: bool | None

class PythonDescriptorsRow(TypedDict):
    """Row type for python_descriptors table."""
    file: str
    line: int
    class_name: str
    has_get: bool | None
    has_set: bool | None
    has_delete: bool | None
    descriptor_type: str

class PythonDictOperationsRow(TypedDict):
    """Row type for python_dict_operations table."""
    file: str
    line: int
    operation: str
    has_default: bool | None
    in_function: str

class PythonDjangoAdminRow(TypedDict):
    """Row type for python_django_admin table."""
    file: str
    line: int
    admin_class_name: str
    model_name: str | None
    list_display: str | None
    list_filter: str | None
    search_fields: str | None
    readonly_fields: str | None
    has_custom_actions: bool | None

class PythonDjangoFormFieldsRow(TypedDict):
    """Row type for python_django_form_fields table."""
    file: str
    line: int
    form_class_name: str
    field_name: str
    field_type: str
    required: bool | None
    max_length: int | None
    has_custom_validator: bool | None

class PythonDjangoFormsRow(TypedDict):
    """Row type for python_django_forms table."""
    file: str
    line: int
    form_class_name: str
    is_model_form: bool | None
    model_name: str | None
    field_count: int | None
    has_custom_clean: bool | None

class PythonDjangoManagersRow(TypedDict):
    """Row type for python_django_managers table."""
    file: str
    line: int
    manager_name: str
    base_class: str | None
    custom_methods: str | None
    model_assignment: str | None

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

class PythonDjangoQuerysetsRow(TypedDict):
    """Row type for python_django_querysets table."""
    file: str
    line: int
    queryset_name: str
    base_class: str | None
    custom_methods: str | None
    has_as_manager: bool | None
    method_chain: str | None

class PythonDjangoReceiversRow(TypedDict):
    """Row type for python_django_receivers table."""
    file: str
    line: int
    function_name: str
    signals: str | None
    sender: str | None
    is_weak: bool | None

class PythonDjangoSignalsRow(TypedDict):
    """Row type for python_django_signals table."""
    file: str
    line: int
    signal_name: str
    signal_type: str | None
    providing_args: str | None
    sender: str | None
    receiver_function: str | None

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

class PythonDrfSerializerFieldsRow(TypedDict):
    """Row type for python_drf_serializer_fields table."""
    file: str
    line: int
    serializer_class_name: str
    field_name: str
    field_type: str
    read_only: bool | None
    write_only: bool | None
    required: bool | None
    allow_null: bool | None
    has_source: bool | None
    has_custom_validator: bool | None

class PythonDrfSerializersRow(TypedDict):
    """Row type for python_drf_serializers table."""
    file: str
    line: int
    serializer_class_name: str
    field_count: int | None
    is_model_serializer: bool | None
    has_meta_model: bool | None
    has_read_only_fields: bool | None
    has_custom_validators: bool | None

class PythonDunderMethodsRow(TypedDict):
    """Row type for python_dunder_methods table."""
    file: str
    line: int
    method_name: str
    category: str
    in_class: str

class PythonDynamicAttributesRow(TypedDict):
    """Row type for python_dynamic_attributes table."""
    file: str
    line: int
    method_name: str
    in_class: str
    has_delegation: bool | None
    has_validation: bool | None

class PythonEllipsisUsageRow(TypedDict):
    """Row type for python_ellipsis_usage table."""
    id: int
    file: str
    line: int
    context: str
    in_function: str

class PythonEnumsRow(TypedDict):
    """Row type for python_enums table."""
    file: str
    line: int
    enum_name: str
    enum_type: str
    member_count: int | None

class PythonExceptionCatchesRow(TypedDict):
    """Row type for python_exception_catches table."""
    file: str
    line: int
    exception_types: str
    variable_name: str | None
    handling_strategy: str
    in_function: str

class PythonExceptionRaisesRow(TypedDict):
    """Row type for python_exception_raises table."""
    file: str
    line: int
    exception_type: str | None
    message: str | None
    from_exception: str | None
    in_function: str
    condition: str | None
    is_re_raise: bool | None

class PythonExecEvalCompileRow(TypedDict):
    """Row type for python_exec_eval_compile table."""
    id: int
    file: str
    line: int
    operation: str
    has_globals: bool | None
    has_locals: bool | None
    in_function: str

class PythonFinallyBlocksRow(TypedDict):
    """Row type for python_finally_blocks table."""
    file: str
    line: int
    cleanup_calls: str | None
    has_cleanup: bool | None
    in_function: str

class PythonFlaskAppsRow(TypedDict):
    """Row type for python_flask_apps table."""
    file: str
    line: int
    factory_name: str
    app_var_name: str | None
    config_source: str | None
    registers_blueprints: bool | None

class PythonFlaskCacheRow(TypedDict):
    """Row type for python_flask_cache table."""
    file: str
    line: int
    function_name: str
    cache_type: str
    timeout: int | None

class PythonFlaskCliCommandsRow(TypedDict):
    """Row type for python_flask_cli_commands table."""
    file: str
    line: int
    command_name: str
    function_name: str
    has_options: bool | None

class PythonFlaskCorsRow(TypedDict):
    """Row type for python_flask_cors table."""
    file: str
    line: int
    config_type: str
    origins: str | None
    is_permissive: bool | None

class PythonFlaskErrorHandlersRow(TypedDict):
    """Row type for python_flask_error_handlers table."""
    file: str
    line: int
    function_name: str
    error_code: int | None
    exception_type: str | None

class PythonFlaskExtensionsRow(TypedDict):
    """Row type for python_flask_extensions table."""
    file: str
    line: int
    extension_type: str
    var_name: str | None
    app_passed_to_constructor: bool | None

class PythonFlaskHooksRow(TypedDict):
    """Row type for python_flask_hooks table."""
    file: str
    line: int
    hook_type: str
    function_name: str
    app_var: str | None

class PythonFlaskRateLimitsRow(TypedDict):
    """Row type for python_flask_rate_limits table."""
    file: str
    line: int
    function_name: str
    limit_string: str | None

class PythonFlaskWebsocketsRow(TypedDict):
    """Row type for python_flask_websockets table."""
    file: str
    line: int
    function_name: str
    event_name: str | None
    namespace: str | None

class PythonForLoopsRow(TypedDict):
    """Row type for python_for_loops table."""
    id: int
    file: str
    line: int
    loop_type: str
    has_else: bool | None
    nesting_level: int
    target_count: int
    in_function: str

class PythonFunctoolsUsageRow(TypedDict):
    """Row type for python_functools_usage table."""
    file: str
    line: int
    function: str
    is_decorator: bool | None
    in_function: str

class PythonGeneratorYieldsRow(TypedDict):
    """Row type for python_generator_yields table."""
    file: str
    line: int
    generator_function: str
    yield_type: str
    yield_expr: str | None
    condition: str | None
    in_loop: bool | None

class PythonGeneratorsRow(TypedDict):
    """Row type for python_generators table."""
    file: str
    line: int
    generator_type: str
    name: str
    yield_count: int | None
    has_yield_from: bool | None
    has_send: bool | None
    is_infinite: bool | None

class PythonGenericsRow(TypedDict):
    """Row type for python_generics table."""
    file: str
    line: int
    class_name: str
    type_params: str | None

class PythonGlobalMutationsRow(TypedDict):
    """Row type for python_global_mutations table."""
    file: str
    line: int
    global_name: str
    operation: str
    in_function: str

class PythonHypothesisStrategiesRow(TypedDict):
    """Row type for python_hypothesis_strategies table."""
    file: str
    line: int
    test_name: str
    strategy_count: int | None
    strategies: str | None

class PythonIfStatementsRow(TypedDict):
    """Row type for python_if_statements table."""
    id: int
    file: str
    line: int
    has_elif: bool | None
    has_else: bool | None
    chain_length: int
    nesting_level: int
    has_complex_condition: bool | None
    in_function: str

class PythonImportStatementsRow(TypedDict):
    """Row type for python_import_statements table."""
    id: int
    file: str
    line: int
    import_type: str
    module: str
    has_alias: bool | None
    is_wildcard: bool | None
    relative_level: int | None
    imported_names: str
    in_function: str

class PythonInstanceMutationsRow(TypedDict):
    """Row type for python_instance_mutations table."""
    file: str
    line: int
    target: str
    operation: str
    in_function: str
    is_init: bool | None
    is_property_setter: bool | None
    is_dunder_method: bool | None

class PythonIoOperationsRow(TypedDict):
    """Row type for python_io_operations table."""
    file: str
    line: int
    io_type: str
    operation: str
    target: str | None
    is_static: bool | None
    in_function: str

class PythonIteratorProtocolRow(TypedDict):
    """Row type for python_iterator_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    has_iter: bool | None
    has_next: bool | None
    raises_stopiteration: bool | None
    is_generator: bool | None

class PythonItertoolsUsageRow(TypedDict):
    """Row type for python_itertools_usage table."""
    file: str
    line: int
    function: str
    is_infinite: bool | None
    in_function: str

class PythonJsonOperationsRow(TypedDict):
    """Row type for python_json_operations table."""
    file: str
    line: int
    operation: str
    direction: str
    in_function: str

class PythonJwtOperationsRow(TypedDict):
    """Row type for python_jwt_operations table."""
    file: str
    line: int
    operation: str
    algorithm: str | None
    verify: bool | None
    is_insecure: bool | None

class PythonLambdaFunctionsRow(TypedDict):
    """Row type for python_lambda_functions table."""
    file: str
    line: int
    parameter_count: int | None
    body: str | None
    captures_closure: bool | None
    used_in: str | None
    in_function: str

class PythonListMutationsRow(TypedDict):
    """Row type for python_list_mutations table."""
    file: str
    line: int
    method: str
    mutates_in_place: bool | None
    in_function: str

class PythonLiteralsRow(TypedDict):
    """Row type for python_literals table."""
    file: str
    line: int
    usage_context: str
    name: str | None
    literal_type: str

class PythonLoggingPatternsRow(TypedDict):
    """Row type for python_logging_patterns table."""
    file: str
    line: int
    log_level: str
    in_function: str

class PythonLoopComplexityRow(TypedDict):
    """Row type for python_loop_complexity table."""
    file: str
    line: int
    loop_type: str
    nesting_level: int
    has_growing_operation: bool | None
    in_function: str
    estimated_complexity: str

class PythonMarshmallowFieldsRow(TypedDict):
    """Row type for python_marshmallow_fields table."""
    file: str
    line: int
    schema_class_name: str
    field_name: str
    field_type: str
    required: bool | None
    allow_none: bool | None
    has_validate: bool | None
    has_custom_validator: bool | None

class PythonMarshmallowSchemasRow(TypedDict):
    """Row type for python_marshmallow_schemas table."""
    file: str
    line: int
    schema_class_name: str
    field_count: int | None
    has_nested_schemas: bool | None
    has_custom_validators: bool | None

class PythonMatchStatementsRow(TypedDict):
    """Row type for python_match_statements table."""
    id: int
    file: str
    line: int
    case_count: int
    has_wildcard: bool | None
    has_guards: bool | None
    pattern_types: str
    in_function: str

class PythonMatrixMultiplicationRow(TypedDict):
    """Row type for python_matrix_multiplication table."""
    file: str
    line: int
    in_function: str

class PythonMembershipTestsRow(TypedDict):
    """Row type for python_membership_tests table."""
    file: str
    line: int
    operator: str
    container_type: str | None
    in_function: str

class PythonMemoizationPatternsRow(TypedDict):
    """Row type for python_memoization_patterns table."""
    file: str
    line: int
    function_name: str
    has_memoization: bool | None
    memoization_type: str
    is_recursive: bool | None
    cache_size: int | None

class PythonMetaclassesRow(TypedDict):
    """Row type for python_metaclasses table."""
    file: str
    line: int
    class_name: str
    metaclass_name: str
    is_definition: bool | None

class PythonMethodTypesRow(TypedDict):
    """Row type for python_method_types table."""
    file: str
    line: int
    method_name: str
    method_type: str
    in_class: str

class PythonMockPatternsRow(TypedDict):
    """Row type for python_mock_patterns table."""
    file: str
    line: int
    mock_type: str
    target: str | None
    in_function: str | None
    is_decorator: bool | None

class PythonModuleAttributesRow(TypedDict):
    """Row type for python_module_attributes table."""
    id: int
    file: str
    line: int
    attribute: str
    usage_type: str
    in_function: str

class PythonMultipleInheritanceRow(TypedDict):
    """Row type for python_multiple_inheritance table."""
    file: str
    line: int
    class_name: str
    base_count: int
    base_classes: str | None

class PythonNamespacePackagesRow(TypedDict):
    """Row type for python_namespace_packages table."""
    id: int
    file: str
    line: int
    pattern: str
    in_function: str

class PythonNonePatternsRow(TypedDict):
    """Row type for python_none_patterns table."""
    file: str
    line: int
    pattern: str
    uses_is: bool | None
    in_function: str

class PythonNonlocalAccessRow(TypedDict):
    """Row type for python_nonlocal_access table."""
    file: str
    line: int
    variable_name: str
    access_type: str
    in_function: str

class PythonOperatorsRow(TypedDict):
    """Row type for python_operators table."""
    file: str
    line: int
    operator_type: str
    operator: str
    in_function: str

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

class PythonOverloadsRow(TypedDict):
    """Row type for python_overloads table."""
    file: str
    function_name: str
    overload_count: int
    variants: str

class PythonPackageConfigsRow(TypedDict):
    """Row type for python_package_configs table."""
    file_path: str
    file_type: str
    project_name: str | None
    project_version: str | None
    dependencies: str | None
    optional_dependencies: str | None
    build_system: str | None
    indexed_at: Any | None

class PythonParameterReturnFlowRow(TypedDict):
    """Row type for python_parameter_return_flow table."""
    file: str
    line: int
    function_name: str
    parameter_name: str
    return_expr: str
    flow_type: str
    is_async: bool | None

class PythonPasswordHashingRow(TypedDict):
    """Row type for python_password_hashing table."""
    file: str
    line: int
    hash_library: str | None
    hash_method: str | None
    is_weak: bool | None
    has_hardcoded_value: bool | None

class PythonPathOperationsRow(TypedDict):
    """Row type for python_path_operations table."""
    file: str
    line: int
    operation: str
    path_type: str
    in_function: str

class PythonPathTraversalRow(TypedDict):
    """Row type for python_path_traversal table."""
    file: str
    line: int
    function: str
    has_concatenation: bool | None
    is_vulnerable: bool | None

class PythonPickleProtocolRow(TypedDict):
    """Row type for python_pickle_protocol table."""
    id: int
    file: str
    line: int
    class_name: str
    has_getstate: bool | None
    has_setstate: bool | None
    has_reduce: bool | None
    has_reduce_ex: bool | None

class PythonPropertyPatternsRow(TypedDict):
    """Row type for python_property_patterns table."""
    file: str
    line: int
    property_name: str
    access_type: str
    in_class: str
    has_computation: bool | None
    has_validation: bool | None

class PythonProtocolsRow(TypedDict):
    """Row type for python_protocols table."""
    file: str
    line: int
    protocol_name: str
    methods: str | None
    is_runtime_checkable: bool | None

class PythonPytestFixturesRow(TypedDict):
    """Row type for python_pytest_fixtures table."""
    file: str
    line: int
    fixture_name: str
    scope: str | None
    has_autouse: bool | None
    has_params: bool | None

class PythonPytestMarkersRow(TypedDict):
    """Row type for python_pytest_markers table."""
    file: str
    line: int
    test_function: str
    marker_name: str
    marker_args: str | None

class PythonPytestParametrizeRow(TypedDict):
    """Row type for python_pytest_parametrize table."""
    file: str
    line: int
    test_function: str
    parameter_names: str
    argvalues_count: int | None

class PythonPytestPluginHooksRow(TypedDict):
    """Row type for python_pytest_plugin_hooks table."""
    file: str
    line: int
    hook_name: str
    param_count: int | None

class PythonRecursionPatternsRow(TypedDict):
    """Row type for python_recursion_patterns table."""
    file: str
    line: int
    function_name: str
    recursion_type: str
    calls_function: str
    base_case_line: int | None
    is_async: bool | None

class PythonRegexPatternsRow(TypedDict):
    """Row type for python_regex_patterns table."""
    file: str
    line: int
    operation: str
    has_flags: bool | None
    in_function: str

class PythonResourceUsageRow(TypedDict):
    """Row type for python_resource_usage table."""
    file: str
    line: int
    resource_type: str
    allocation_expr: str
    in_function: str
    has_cleanup: bool | None

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

class PythonSetOperationsRow(TypedDict):
    """Row type for python_set_operations table."""
    file: str
    line: int
    operation: str
    in_function: str

class PythonSliceOperationsRow(TypedDict):
    """Row type for python_slice_operations table."""
    file: str
    line: int
    target: str | None
    has_start: bool | None
    has_stop: bool | None
    has_step: bool | None
    is_assignment: bool | None
    in_function: str

class PythonSlotsRow(TypedDict):
    """Row type for python_slots table."""
    file: str
    line: int
    class_name: str
    slot_count: int | None

class PythonSqlInjectionRow(TypedDict):
    """Row type for python_sql_injection table."""
    file: str
    line: int
    db_method: str
    interpolation_type: str | None
    is_vulnerable: bool | None

class PythonStringFormattingRow(TypedDict):
    """Row type for python_string_formatting table."""
    file: str
    line: int
    format_type: str
    has_expressions: bool | None
    var_count: int | None
    in_function: str

class PythonStringMethodsRow(TypedDict):
    """Row type for python_string_methods table."""
    file: str
    line: int
    method: str
    in_function: str

class PythonTernaryExpressionsRow(TypedDict):
    """Row type for python_ternary_expressions table."""
    file: str
    line: int
    has_complex_condition: bool | None
    in_function: str

class PythonThreadingPatternsRow(TypedDict):
    """Row type for python_threading_patterns table."""
    file: str
    line: int
    threading_type: str
    in_function: str

class PythonTruthinessPatternsRow(TypedDict):
    """Row type for python_truthiness_patterns table."""
    file: str
    line: int
    pattern: str
    expression: str | None
    in_function: str

class PythonTupleOperationsRow(TypedDict):
    """Row type for python_tuple_operations table."""
    file: str
    line: int
    operation: str
    element_count: int | None
    in_function: str

class PythonTypeCheckingRow(TypedDict):
    """Row type for python_type_checking table."""
    file: str
    line: int
    check_type: str
    in_function: str

class PythonTypedDictsRow(TypedDict):
    """Row type for python_typed_dicts table."""
    file: str
    line: int
    typeddict_name: str
    fields: str | None

class PythonUnittestTestCasesRow(TypedDict):
    """Row type for python_unittest_test_cases table."""
    file: str
    line: int
    test_class_name: str
    test_method_count: int | None
    has_setup: bool | None
    has_teardown: bool | None
    has_setupclass: bool | None
    has_teardownclass: bool | None

class PythonUnpackingPatternsRow(TypedDict):
    """Row type for python_unpacking_patterns table."""
    file: str
    line: int
    unpack_type: str
    target_count: int | None
    has_rest: bool | None
    in_function: str

class PythonValidatorsRow(TypedDict):
    """Row type for python_validators table."""
    file: str
    line: int
    model_name: str
    field_name: str | None
    validator_method: str
    validator_type: str

class PythonVisibilityConventionsRow(TypedDict):
    """Row type for python_visibility_conventions table."""
    file: str
    line: int
    name: str
    visibility: str
    is_name_mangled: bool | None
    in_class: str

class PythonWalrusOperatorsRow(TypedDict):
    """Row type for python_walrus_operators table."""
    file: str
    line: int
    variable: str
    used_in: str
    in_function: str

class PythonWeakrefUsageRow(TypedDict):
    """Row type for python_weakref_usage table."""
    id: int
    file: str
    line: int
    usage_type: str
    in_function: str

class PythonWhileLoopsRow(TypedDict):
    """Row type for python_while_loops table."""
    id: int
    file: str
    line: int
    has_else: bool | None
    is_infinite: bool | None
    nesting_level: int
    in_function: str

class PythonWithStatementsRow(TypedDict):
    """Row type for python_with_statements table."""
    id: int
    file: str
    line: int
    is_async: bool | None
    context_count: int
    has_alias: bool | None
    in_function: str

class PythonWtformsFieldsRow(TypedDict):
    """Row type for python_wtforms_fields table."""
    file: str
    line: int
    form_class_name: str
    field_name: str
    field_type: str
    has_validators: bool | None
    has_custom_validator: bool | None

class PythonWtformsFormsRow(TypedDict):
    """Row type for python_wtforms_forms table."""
    file: str
    line: int
    form_class_name: str
    field_count: int | None
    has_custom_validators: bool | None

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

class RouterMountsRow(TypedDict):
    """Row type for router_mounts table."""
    file: str
    line: int
    mount_path_expr: str
    router_variable: str
    is_literal: bool | None

class SequelizeAssociationsRow(TypedDict):
    """Row type for sequelize_associations table."""
    file: str
    line: int
    model_name: str
    association_type: str
    target_model: str
    foreign_key: str | None
    through_table: str | None

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

class TerraformResourcesRow(TypedDict):
    """Row type for terraform_resources table."""
    resource_id: str
    file_path: str
    resource_type: str
    resource_name: str
    module_path: str | None
    properties_json: str | None
    depends_on_json: str | None
    sensitive_flags_json: str | None
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
    props_definition: str | None
    emits_definition: str | None
    setup_return: str | None

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
