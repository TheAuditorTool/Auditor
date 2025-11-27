"""
Infrastructure-as-Code schema definitions.

This module contains table schemas specific to infrastructure tools:
- Docker (containers, images, compose services)
- NGINX (web server configuration)
- Terraform (IaC resources, variables, outputs)
- AWS CDK (Infrastructure as Code with Python/TypeScript)

Design Philosophy:
- Infrastructure-only tables
- Multi-cloud support (AWS, Azure, GCP via Terraform)
- Security-focused (public exposure, misconfigurations)
"""

from .utils import Column, ForeignKey, TableSchema


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
    ],
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
    ],
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
    ],
)


TERRAFORM_FILES = TableSchema(
    name="terraform_files",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("module_name", "TEXT"),
        Column("stack_name", "TEXT"),
        Column("backend_type", "TEXT"),
        Column("providers_json", "TEXT"),
        Column("is_module", "BOOLEAN", default="0"),
        Column("module_source", "TEXT"),
    ],
    indexes=[
        ("idx_terraform_files_module", ["module_name"]),
        ("idx_terraform_files_stack", ["stack_name"]),
    ],
)

TERRAFORM_RESOURCES = TableSchema(
    name="terraform_resources",
    columns=[
        Column("resource_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("resource_type", "TEXT", nullable=False),
        Column("resource_name", "TEXT", nullable=False),
        Column("module_path", "TEXT"),
        Column("properties_json", "TEXT"),
        Column("depends_on_json", "TEXT"),
        Column("sensitive_flags_json", "TEXT"),
        Column("has_public_exposure", "BOOLEAN", default="0"),
        Column("line", "INTEGER"),
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
            foreign_columns=["file_path"],
        )
    ],
)

TERRAFORM_VARIABLES = TableSchema(
    name="terraform_variables",
    columns=[
        Column("variable_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("variable_name", "TEXT", nullable=False),
        Column("variable_type", "TEXT"),
        Column("default_json", "TEXT"),
        Column("is_sensitive", "BOOLEAN", default="0"),
        Column("description", "TEXT"),
        Column("source_file", "TEXT"),
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
            foreign_columns=["file_path"],
        )
    ],
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
    ],
)

TERRAFORM_OUTPUTS = TableSchema(
    name="terraform_outputs",
    columns=[
        Column("output_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("output_name", "TEXT", nullable=False),
        Column("value_json", "TEXT"),
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
            foreign_columns=["file_path"],
        )
    ],
)

TERRAFORM_FINDINGS = TableSchema(
    name="terraform_findings",
    columns=[
        Column("finding_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("resource_id", "TEXT"),
        Column("category", "TEXT", nullable=False),
        Column("severity", "TEXT", nullable=False),
        Column("title", "TEXT", nullable=False),
        Column("description", "TEXT"),
        Column("graph_context_json", "TEXT"),
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
            foreign_columns=["file_path"],
        ),
        ForeignKey(
            local_columns=["resource_id"],
            foreign_table="terraform_resources",
            foreign_columns=["resource_id"],
        ),
    ],
)


CDK_CONSTRUCTS = TableSchema(
    name="cdk_constructs",
    columns=[
        Column("construct_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("cdk_class", "TEXT", nullable=False),
        Column("construct_name", "TEXT"),
    ],
    indexes=[
        ("idx_cdk_constructs_file", ["file_path"]),
        ("idx_cdk_constructs_class", ["cdk_class"]),
        ("idx_cdk_constructs_line", ["file_path", "line"]),
    ],
)

CDK_CONSTRUCT_PROPERTIES = TableSchema(
    name="cdk_construct_properties",
    columns=[
        Column("id", "INTEGER", primary_key=True),
        Column("construct_id", "TEXT", nullable=False),
        Column("property_name", "TEXT", nullable=False),
        Column("property_value_expr", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
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
            foreign_columns=["construct_id"],
        )
    ],
)

CDK_FINDINGS = TableSchema(
    name="cdk_findings",
    columns=[
        Column("finding_id", "TEXT", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("construct_id", "TEXT"),
        Column("category", "TEXT", nullable=False),
        Column("severity", "TEXT", nullable=False),
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
            foreign_columns=["construct_id"],
        )
    ],
)


GITHUB_WORKFLOWS = TableSchema(
    name="github_workflows",
    columns=[
        Column("workflow_path", "TEXT", nullable=False, primary_key=True),
        Column("workflow_name", "TEXT"),
        Column("on_triggers", "TEXT", nullable=False),
        Column("permissions", "TEXT"),
        Column("concurrency", "TEXT"),
        Column("env", "TEXT"),
    ],
    indexes=[
        ("idx_github_workflows_path", ["workflow_path"]),
        ("idx_github_workflows_name", ["workflow_name"]),
    ],
)

GITHUB_JOBS = TableSchema(
    name="github_jobs",
    columns=[
        Column("job_id", "TEXT", nullable=False, primary_key=True),
        Column("workflow_path", "TEXT", nullable=False),
        Column("job_key", "TEXT", nullable=False),
        Column("job_name", "TEXT"),
        Column("runs_on", "TEXT"),
        Column("strategy", "TEXT"),
        Column("permissions", "TEXT"),
        Column("env", "TEXT"),
        Column("if_condition", "TEXT"),
        Column("timeout_minutes", "INTEGER"),
        Column("uses_reusable_workflow", "BOOLEAN", default="0"),
        Column("reusable_workflow_path", "TEXT"),
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
            foreign_columns=["workflow_path"],
        )
    ],
)

GITHUB_JOB_DEPENDENCIES = TableSchema(
    name="github_job_dependencies",
    columns=[
        Column("job_id", "TEXT", nullable=False),
        Column("needs_job_id", "TEXT", nullable=False),
    ],
    primary_key=["job_id", "needs_job_id"],
    indexes=[
        ("idx_github_job_deps_job", ["job_id"]),
        ("idx_github_job_deps_needs", ["needs_job_id"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["job_id"], foreign_table="github_jobs", foreign_columns=["job_id"]
        ),
        ForeignKey(
            local_columns=["needs_job_id"], foreign_table="github_jobs", foreign_columns=["job_id"]
        ),
    ],
)

GITHUB_STEPS = TableSchema(
    name="github_steps",
    columns=[
        Column("step_id", "TEXT", nullable=False, primary_key=True),
        Column("job_id", "TEXT", nullable=False),
        Column("sequence_order", "INTEGER", nullable=False),
        Column("step_name", "TEXT"),
        Column("uses_action", "TEXT"),
        Column("uses_version", "TEXT"),
        Column("run_script", "TEXT"),
        Column("shell", "TEXT"),
        Column("env", "TEXT"),
        Column("with_args", "TEXT"),
        Column("if_condition", "TEXT"),
        Column("timeout_minutes", "INTEGER"),
        Column("continue_on_error", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_github_steps_job", ["job_id"]),
        ("idx_github_steps_sequence", ["job_id", "sequence_order"]),
        ("idx_github_steps_action", ["uses_action"]),
        ("idx_github_steps_version", ["uses_version"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["job_id"], foreign_table="github_jobs", foreign_columns=["job_id"]
        )
    ],
)

GITHUB_STEP_OUTPUTS = TableSchema(
    name="github_step_outputs",
    columns=[
        Column("id", "INTEGER", primary_key=True),
        Column("step_id", "TEXT", nullable=False),
        Column("output_name", "TEXT", nullable=False),
        Column("output_expression", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_github_step_outputs_step", ["step_id"]),
        ("idx_github_step_outputs_name", ["output_name"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["step_id"], foreign_table="github_steps", foreign_columns=["step_id"]
        )
    ],
)

GITHUB_STEP_REFERENCES = TableSchema(
    name="github_step_references",
    columns=[
        Column("id", "INTEGER", primary_key=True),
        Column("step_id", "TEXT", nullable=False),
        Column("reference_location", "TEXT", nullable=False),
        Column("reference_type", "TEXT", nullable=False),
        Column("reference_path", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_github_step_refs_step", ["step_id"]),
        ("idx_github_step_refs_type", ["reference_type"]),
        ("idx_github_step_refs_path", ["reference_path"]),
        ("idx_github_step_refs_location", ["reference_location"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["step_id"], foreign_table="github_steps", foreign_columns=["step_id"]
        )
    ],
)


INFRASTRUCTURE_TABLES: dict[str, TableSchema] = {
    "docker_images": DOCKER_IMAGES,
    "compose_services": COMPOSE_SERVICES,
    "nginx_configs": NGINX_CONFIGS,
    "terraform_files": TERRAFORM_FILES,
    "terraform_resources": TERRAFORM_RESOURCES,
    "terraform_variables": TERRAFORM_VARIABLES,
    "terraform_variable_values": TERRAFORM_VARIABLE_VALUES,
    "terraform_outputs": TERRAFORM_OUTPUTS,
    "terraform_findings": TERRAFORM_FINDINGS,
    "cdk_constructs": CDK_CONSTRUCTS,
    "cdk_construct_properties": CDK_CONSTRUCT_PROPERTIES,
    "cdk_findings": CDK_FINDINGS,
    "github_workflows": GITHUB_WORKFLOWS,
    "github_jobs": GITHUB_JOBS,
    "github_job_dependencies": GITHUB_JOB_DEPENDENCIES,
    "github_steps": GITHUB_STEPS,
    "github_step_outputs": GITHUB_STEP_OUTPUTS,
    "github_step_references": GITHUB_STEP_REFERENCES,
}
