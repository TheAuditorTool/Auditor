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
    task_number: int
    title: str
    description: Optional[str]
    status: str
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

class PythonAsyncFunctionsRow(TypedDict):
    """Row type for python_async_functions table."""
    file: str
    line: int
    function_name: str
    has_await: Optional[bool]
    await_count: Optional[int]
    has_async_with: Optional[bool]
    has_async_for: Optional[bool]

class PythonAsyncGeneratorsRow(TypedDict):
    """Row type for python_async_generators table."""
    file: str
    line: int
    generator_type: str
    target_vars: Optional[str]
    iterable_expr: Optional[str]
    function_name: Optional[str]

class PythonAwaitExpressionsRow(TypedDict):
    """Row type for python_await_expressions table."""
    file: str
    line: int
    await_expr: str
    containing_function: Optional[str]

class PythonBlueprintsRow(TypedDict):
    """Row type for python_blueprints table."""
    file: str
    line: Optional[int]
    blueprint_name: str
    url_prefix: Optional[str]
    subdomain: Optional[str]

class PythonCeleryBeatSchedulesRow(TypedDict):
    """Row type for python_celery_beat_schedules table."""
    file: str
    line: int
    schedule_name: str
    task_name: str
    schedule_type: str
    schedule_expression: Optional[str]
    args: Optional[str]
    kwargs: Optional[str]

class PythonCeleryTaskCallsRow(TypedDict):
    """Row type for python_celery_task_calls table."""
    file: str
    line: int
    caller_function: str
    task_name: str
    invocation_type: str
    arg_count: Optional[int]
    has_countdown: Optional[bool]
    has_eta: Optional[bool]
    queue_override: Optional[str]

class PythonCeleryTasksRow(TypedDict):
    """Row type for python_celery_tasks table."""
    file: str
    line: int
    task_name: str
    decorator_name: str
    arg_count: Optional[int]
    bind: Optional[bool]
    serializer: Optional[str]
    max_retries: Optional[int]
    rate_limit: Optional[str]
    time_limit: Optional[int]
    queue: Optional[str]

class PythonContextManagersRow(TypedDict):
    """Row type for python_context_managers table."""
    file: str
    line: int
    context_type: str
    context_expr: Optional[str]
    as_name: Optional[str]
    is_async: Optional[bool]
    is_custom: Optional[bool]

class PythonDecoratorsRow(TypedDict):
    """Row type for python_decorators table."""
    file: str
    line: int
    decorator_name: str
    decorator_type: str
    target_type: str
    target_name: str
    is_async: Optional[bool]

class PythonDjangoAdminRow(TypedDict):
    """Row type for python_django_admin table."""
    file: str
    line: int
    admin_class_name: str
    model_name: Optional[str]
    list_display: Optional[str]
    list_filter: Optional[str]
    search_fields: Optional[str]
    readonly_fields: Optional[str]
    has_custom_actions: Optional[bool]

class PythonDjangoFormFieldsRow(TypedDict):
    """Row type for python_django_form_fields table."""
    file: str
    line: int
    form_class_name: str
    field_name: str
    field_type: str
    required: Optional[bool]
    max_length: Optional[int]
    has_custom_validator: Optional[bool]

class PythonDjangoFormsRow(TypedDict):
    """Row type for python_django_forms table."""
    file: str
    line: int
    form_class_name: str
    is_model_form: Optional[bool]
    model_name: Optional[str]
    field_count: Optional[int]
    has_custom_clean: Optional[bool]

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

class PythonDrfSerializerFieldsRow(TypedDict):
    """Row type for python_drf_serializer_fields table."""
    file: str
    line: int
    serializer_class_name: str
    field_name: str
    field_type: str
    read_only: Optional[bool]
    write_only: Optional[bool]
    required: Optional[bool]
    allow_null: Optional[bool]
    has_source: Optional[bool]
    has_custom_validator: Optional[bool]

class PythonDrfSerializersRow(TypedDict):
    """Row type for python_drf_serializers table."""
    file: str
    line: int
    serializer_class_name: str
    field_count: Optional[int]
    is_model_serializer: Optional[bool]
    has_meta_model: Optional[bool]
    has_read_only_fields: Optional[bool]
    has_custom_validators: Optional[bool]

class PythonGeneratorsRow(TypedDict):
    """Row type for python_generators table."""
    file: str
    line: int
    generator_type: str
    name: str
    yield_count: Optional[int]
    has_yield_from: Optional[bool]
    has_send: Optional[bool]
    is_infinite: Optional[bool]

class PythonGenericsRow(TypedDict):
    """Row type for python_generics table."""
    file: str
    line: int
    class_name: str
    type_params: Optional[str]

class PythonLiteralsRow(TypedDict):
    """Row type for python_literals table."""
    file: str
    line: int
    usage_context: str
    name: Optional[str]
    literal_type: str

class PythonMarshmallowFieldsRow(TypedDict):
    """Row type for python_marshmallow_fields table."""
    file: str
    line: int
    schema_class_name: str
    field_name: str
    field_type: str
    required: Optional[bool]
    allow_none: Optional[bool]
    has_validate: Optional[bool]
    has_custom_validator: Optional[bool]

class PythonMarshmallowSchemasRow(TypedDict):
    """Row type for python_marshmallow_schemas table."""
    file: str
    line: int
    schema_class_name: str
    field_count: Optional[int]
    has_nested_schemas: Optional[bool]
    has_custom_validators: Optional[bool]

class PythonMockPatternsRow(TypedDict):
    """Row type for python_mock_patterns table."""
    file: str
    line: int
    mock_type: str
    target: Optional[str]
    in_function: Optional[str]
    is_decorator: Optional[bool]

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

class PythonOverloadsRow(TypedDict):
    """Row type for python_overloads table."""
    file: str
    function_name: str
    overload_count: int
    variants: str

class PythonProtocolsRow(TypedDict):
    """Row type for python_protocols table."""
    file: str
    line: int
    protocol_name: str
    methods: Optional[str]
    is_runtime_checkable: Optional[bool]

class PythonPytestFixturesRow(TypedDict):
    """Row type for python_pytest_fixtures table."""
    file: str
    line: int
    fixture_name: str
    scope: Optional[str]
    has_autouse: Optional[bool]
    has_params: Optional[bool]

class PythonPytestMarkersRow(TypedDict):
    """Row type for python_pytest_markers table."""
    file: str
    line: int
    test_function: str
    marker_name: str
    marker_args: Optional[str]

class PythonPytestParametrizeRow(TypedDict):
    """Row type for python_pytest_parametrize table."""
    file: str
    line: int
    test_function: str
    parameter_names: str
    argvalues_count: Optional[int]

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

class PythonTypedDictsRow(TypedDict):
    """Row type for python_typed_dicts table."""
    file: str
    line: int
    typeddict_name: str
    fields: Optional[str]

class PythonValidatorsRow(TypedDict):
    """Row type for python_validators table."""
    file: str
    line: int
    model_name: str
    field_name: Optional[str]
    validator_method: str
    validator_type: str

class PythonWtformsFieldsRow(TypedDict):
    """Row type for python_wtforms_fields table."""
    file: str
    line: int
    form_class_name: str
    field_name: str
    field_type: str
    has_validators: Optional[bool]
    has_custom_validator: Optional[bool]

class PythonWtformsFormsRow(TypedDict):
    """Row type for python_wtforms_forms table."""
    file: str
    line: int
    form_class_name: str
    field_count: Optional[int]
    has_custom_validators: Optional[bool]

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

class RefsRow(TypedDict):
    """Row type for refs table."""
    src: str
    kind: str
    value: str
    line: Optional[int]

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
