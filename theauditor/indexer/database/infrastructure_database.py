"""Infrastructure database operations.

This module contains add_* methods for INFRASTRUCTURE_TABLES defined in schemas/infrastructure_schema.py.
Handles 18 infrastructure tables including Docker, Terraform, AWS CDK, and GitHub Actions.
"""

import json
import os


class InfrastructureDatabaseMixin:
    """Mixin providing add_* methods for INFRASTRUCTURE_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    def add_docker_image(
        self,
        file_path: str,
        base_image: str | None,
        user: str | None,
        has_healthcheck: bool,
    ):
        """Add a Docker image record to the batch.

        Note: Ports, env vars, build args go to junction tables:
        - dockerfile_ports (via add_dockerfile_port)
        - dockerfile_env_vars (via add_dockerfile_env_var)
        """
        self.generic_batches["docker_images"].append(
            (file_path, base_image, user, has_healthcheck)
        )

    def add_compose_service(
        self,
        file_path: str,
        service_name: str,
        image: str | None,
        is_privileged: bool,
        network_mode: str,
        user: str | None = None,
        security_opt: list[str] | None = None,
        restart: str | None = None,
        command: list[str] | None = None,
        entrypoint: list[str] | None = None,
        healthcheck: dict | None = None,
    ):
        """Add a Docker Compose service record to the batch.

        Note: Ports, volumes, environment, capabilities, depends_on go to junction tables:
        - compose_service_ports (via add_compose_service_port)
        - compose_service_volumes (via add_compose_service_volume)
        - compose_service_env (via add_compose_service_env)
        - compose_service_capabilities (via add_compose_service_capability)
        - compose_service_deps (via add_compose_service_dep)
        """
        security_opt_json = json.dumps(security_opt) if security_opt else None
        command_json = json.dumps(command) if command else None
        entrypoint_json = json.dumps(entrypoint) if entrypoint else None
        healthcheck_json = json.dumps(healthcheck) if healthcheck else None

        self.generic_batches["compose_services"].append(
            (
                file_path,
                service_name,
                image,
                is_privileged,
                network_mode,
                user,
                security_opt_json,
                restart,
                command_json,
                entrypoint_json,
                healthcheck_json,
            )
        )

    def add_nginx_config(
        self, file_path: str, block_type: str, block_context: str, directives: dict, level: int
    ):
        """Add an Nginx configuration block to the batch."""
        directives_json = json.dumps(directives)

        block_context = block_context or "default"

        batch = self.generic_batches["nginx_configs"]
        # ZERO FALLBACK POLICY: No deduplication.
        # If extractor sends same nginx config twice, SQLite UNIQUE constraint catches it.
        batch.append((file_path, block_type, block_context, directives_json, level))

    def add_terraform_file(
        self,
        file_path: str,
        module_name: str | None = None,
        stack_name: str | None = None,
        backend_type: str | None = None,
        providers_json: str | None = None,
        is_module: bool = False,
        module_source: str | None = None,
    ):
        """Add a Terraform file record to the batch."""
        self.generic_batches["terraform_files"].append(
            (
                file_path,
                module_name,
                stack_name,
                backend_type,
                providers_json,
                is_module,
                module_source,
            )
        )

    def add_terraform_resource(
        self,
        resource_id: str,
        file_path: str,
        resource_type: str,
        resource_name: str,
        module_path: str | None = None,
        has_public_exposure: bool = False,
        line: int | None = None,
    ):
        """Add a Terraform resource record to the batch.

        Note: Properties, depends_on, sensitive flags go to junction tables:
        - terraform_resource_properties (via add_terraform_resource_property)
        - terraform_resource_deps (via add_terraform_resource_dep)
        """
        self.generic_batches["terraform_resources"].append(
            (
                resource_id,
                file_path,
                resource_type,
                resource_name,
                module_path,
                has_public_exposure,
                line,
            )
        )

    def add_terraform_variable(
        self,
        variable_id: str,
        file_path: str,
        variable_name: str,
        variable_type: str | None = None,
        default_json: str | None = None,
        is_sensitive: bool = False,
        description: str = "",
        source_file: str | None = None,
        line: int | None = None,
    ):
        """Add a Terraform variable record to the batch."""
        self.generic_batches["terraform_variables"].append(
            (
                variable_id,
                file_path,
                variable_name,
                variable_type,
                default_json,
                is_sensitive,
                description,
                source_file,
                line,
            )
        )

    def add_terraform_variable_value(
        self,
        file_path: str,
        variable_name: str,
        variable_value_json: str | None = None,
        line: int | None = None,
        is_sensitive_context: bool = False,
    ):
        """Add a .tfvars variable value record to the batch."""
        self.generic_batches["terraform_variable_values"].append(
            (
                file_path,
                variable_name,
                variable_value_json,
                line,
                is_sensitive_context,
            )
        )

    def add_terraform_output(
        self,
        output_id: str,
        file_path: str,
        output_name: str,
        value_json: str | None = None,
        is_sensitive: bool = False,
        description: str = "",
        line: int | None = None,
    ):
        """Add a Terraform output record to the batch."""
        self.generic_batches["terraform_outputs"].append(
            (output_id, file_path, output_name, value_json, is_sensitive, description, line)
        )

    def add_terraform_finding(
        self,
        finding_id: str,
        file_path: str,
        resource_id: str | None = None,
        category: str = "",
        severity: str = "medium",
        title: str = "",
        description: str = "",
        graph_context_json: str | None = None,
        remediation: str = "",
        line: int | None = None,
    ):
        """Add a Terraform finding record to the batch."""
        self.generic_batches["terraform_findings"].append(
            (
                finding_id,
                file_path,
                resource_id,
                category,
                severity,
                title,
                description,
                graph_context_json,
                remediation,
                line,
            )
        )

    def add_cdk_construct(
        self,
        file_path: str,
        line: int,
        cdk_class: str,
        construct_name: str | None,
        construct_id: str,
    ):
        """Add a CDK construct record to the batch.

        Args:
            file_path: Path to Python file containing construct
            line: Line number of construct instantiation
            cdk_class: CDK class name (e.g., 's3.Bucket', 'aws_cdk.aws_s3.Bucket')
            construct_name: CDK logical ID (nullable - 2nd positional arg)
            construct_id: Composite key: {file}::L{line}::{class}::{name}
        """

        if os.environ.get("THEAUDITOR_CDK_DEBUG") == "1":
            print(f"[CDK-DB] Adding to batch: {construct_id}")

        self.generic_batches["cdk_constructs"].append(
            (construct_id, file_path, line, cdk_class, construct_name)
        )

    def add_cdk_construct_property(
        self, construct_id: str, property_name: str, property_value_expr: str, line: int
    ):
        """Add a CDK construct property record to the batch.

        Args:
            construct_id: FK to cdk_constructs.construct_id
            property_name: Property keyword argument name (e.g., 'public_read_access')
            property_value_expr: Serialized property value via ast.unparse()
            line: Line number of property definition
        """
        self.generic_batches["cdk_construct_properties"].append(
            (construct_id, property_name, property_value_expr, line)
        )

    def add_cdk_finding(
        self,
        finding_id: str,
        file_path: str,
        construct_id: str | None = None,
        category: str = "",
        severity: str = "medium",
        title: str = "",
        description: str = "",
        remediation: str = "",
        line: int | None = None,
    ):
        """Add a CDK security finding record to the batch.

        Args:
            finding_id: Unique finding identifier
            file_path: Path to CDK file with issue
            construct_id: Optional FK to cdk_constructs (nullable for file-level findings)
            category: Finding category (e.g., 'public_exposure', 'missing_encryption')
            severity: Severity level ('critical', 'high', 'medium', 'low')
            title: Short finding title
            description: Detailed finding description
            remediation: Suggested fix
            line: Line number of issue
        """
        self.generic_batches["cdk_findings"].append(
            (
                finding_id,
                file_path,
                construct_id,
                category,
                severity,
                title,
                description,
                remediation,
                line,
            )
        )

    def add_github_workflow(
        self,
        workflow_path: str,
        workflow_name: str | None,
        on_triggers: str,
        permissions: str | None = None,
        concurrency: str | None = None,
        env: str | None = None,
    ):
        """Add a GitHub Actions workflow record to the batch.

        Args:
            workflow_path: Path to workflow file (.github/workflows/ci.yml)
            workflow_name: Workflow name from 'name:' field or filename
            on_triggers: JSON array of trigger events
            permissions: JSON object of workflow-level permissions
            concurrency: JSON object of concurrency settings
            env: JSON object of workflow-level environment variables
        """
        self.generic_batches["github_workflows"].append(
            (workflow_path, workflow_name, on_triggers, permissions, concurrency, env)
        )

    def add_github_job(
        self,
        job_id: str,
        workflow_path: str,
        job_key: str,
        job_name: str | None,
        runs_on: str | None,
        strategy: str | None = None,
        permissions: str | None = None,
        env: str | None = None,
        if_condition: str | None = None,
        timeout_minutes: int | None = None,
        uses_reusable_workflow: bool = False,
        reusable_workflow_path: str | None = None,
    ):
        """Add a GitHub Actions job record to the batch.

        Args:
            job_id: Composite PK (workflow_path||':'||job_key)
            workflow_path: FK to github_workflows
            job_key: Job key from YAML (e.g., 'build', 'test')
            job_name: Optional name: field
            runs_on: JSON array of runner labels (supports matrix)
            strategy: JSON object of matrix strategy
            permissions: JSON object of job-level permissions
            env: JSON object of job-level env vars
            if_condition: Conditional expression for job execution
            timeout_minutes: Job timeout
            uses_reusable_workflow: True if uses: workflow.yml
            reusable_workflow_path: Path to reusable workflow if used
        """
        self.generic_batches["github_jobs"].append(
            (
                job_id,
                workflow_path,
                job_key,
                job_name,
                runs_on,
                strategy,
                permissions,
                env,
                if_condition,
                timeout_minutes,
                uses_reusable_workflow,
                reusable_workflow_path,
            )
        )

    def add_github_job_dependency(self, job_id: str, needs_job_id: str):
        """Add a GitHub Actions job dependency edge (needs: relationship).

        Args:
            job_id: FK to github_jobs (dependent job)
            needs_job_id: FK to github_jobs (dependency job)
        """
        self.generic_batches["github_job_dependencies"].append((job_id, needs_job_id))

    def add_github_step(
        self,
        step_id: str,
        job_id: str,
        sequence_order: int,
        step_name: str | None,
        uses_action: str | None,
        uses_version: str | None,
        run_script: str | None,
        shell: str | None,
        env: str | None,
        with_args: str | None,
        if_condition: str | None,
        timeout_minutes: int | None,
        continue_on_error: bool = False,
    ):
        """Add a GitHub Actions step record to the batch.

        Args:
            step_id: Composite PK (job_id||':'||sequence_order)
            job_id: FK to github_jobs
            sequence_order: Step order within job (0-indexed)
            step_name: Optional name: field
            uses_action: Action reference (e.g., 'actions/checkout@v4')
            uses_version: Version/ref extracted from uses
            run_script: Shell script content from run: field
            shell: Shell type (bash, pwsh, python)
            env: JSON object of step-level env vars
            with_args: JSON object of action inputs (with: field)
            if_condition: Conditional expression for step execution
            timeout_minutes: Step timeout
            continue_on_error: Continue on failure flag
        """
        self.generic_batches["github_steps"].append(
            (
                step_id,
                job_id,
                sequence_order,
                step_name,
                uses_action,
                uses_version,
                run_script,
                shell,
                env,
                with_args,
                if_condition,
                timeout_minutes,
                continue_on_error,
            )
        )

    def add_github_step_output(self, step_id: str, output_name: str, output_expression: str):
        """Add a GitHub Actions step output declaration.

        Args:
            step_id: FK to github_steps
            output_name: Output key
            output_expression: Value expression
        """
        self.generic_batches["github_step_outputs"].append(
            (step_id, output_name, output_expression)
        )

    def add_github_step_reference(
        self, step_id: str, reference_location: str, reference_type: str, reference_path: str
    ):
        """Add a GitHub Actions step reference (${{ }} expression).

        Args:
            step_id: FK to github_steps
            reference_location: Where reference appears ('run', 'env', 'with', 'if')
            reference_type: Type of reference ('github', 'secrets', 'env', 'needs', 'steps')
            reference_path: Full path (e.g., 'github.event.pull_request.head.sha')
        """
        self.generic_batches["github_step_references"].append(
            (step_id, reference_location, reference_type, reference_path)
        )

    # ========== JUNCTION TABLE METHODS (Phase 1.6) ==========

    def add_dockerfile_port(
        self,
        file_path: str,
        port: str,
        protocol: str = "tcp",
    ):
        """Add a Dockerfile EXPOSE port to the batch.

        Schema: dockerfile_ports(file_path, port, protocol)
        FK: docker_images.file_path (TEXT)
        """
        self.generic_batches["dockerfile_ports"].append((file_path, port, protocol))

    def add_dockerfile_env_var(
        self,
        file_path: str,
        var_name: str,
        var_value: str | None,
        is_build_arg: bool = False,
    ):
        """Add a Dockerfile ENV/ARG variable to the batch.

        Schema: dockerfile_env_vars(file_path, var_name, var_value, is_build_arg)
        FK: docker_images.file_path (TEXT)
        """
        self.generic_batches["dockerfile_env_vars"].append(
            (file_path, var_name, var_value, 1 if is_build_arg else 0)
        )

    def add_compose_service_port(
        self,
        file_path: str,
        service_name: str,
        host_port: str | None,
        container_port: str,
        protocol: str = "tcp",
    ):
        """Add a compose service port mapping to the batch.

        Schema: compose_service_ports(file_path, service_name, host_port, container_port, protocol)
        FK: compose_services(file_path, service_name) composite
        """
        self.generic_batches["compose_service_ports"].append(
            (file_path, service_name, host_port, container_port, protocol)
        )

    def add_compose_service_volume(
        self,
        file_path: str,
        service_name: str,
        host_path: str,
        container_path: str,
        mode: str = "rw",
    ):
        """Add a compose service volume mapping to the batch.

        Schema: compose_service_volumes(file_path, service_name, host_path, container_path, mode)
        FK: compose_services(file_path, service_name) composite
        """
        self.generic_batches["compose_service_volumes"].append(
            (file_path, service_name, host_path, container_path, mode)
        )

    def add_compose_service_env(
        self,
        file_path: str,
        service_name: str,
        var_name: str,
        var_value: str | None,
    ):
        """Add a compose service environment variable to the batch.

        Schema: compose_service_env(file_path, service_name, var_name, var_value)
        FK: compose_services(file_path, service_name) composite
        """
        self.generic_batches["compose_service_env"].append(
            (file_path, service_name, var_name, var_value)
        )

    def add_compose_service_capability(
        self,
        file_path: str,
        service_name: str,
        capability: str,
        is_add: bool = True,
    ):
        """Add a compose service capability (cap_add/cap_drop) to the batch.

        Schema: compose_service_capabilities(file_path, service_name, capability, is_add)
        FK: compose_services(file_path, service_name) composite
        """
        self.generic_batches["compose_service_capabilities"].append(
            (file_path, service_name, capability, 1 if is_add else 0)
        )

    def add_compose_service_dep(
        self,
        file_path: str,
        service_name: str,
        depends_on_service: str,
        condition: str = "service_started",
    ):
        """Add a compose service dependency to the batch.

        Schema: compose_service_deps(file_path, service_name, depends_on_service, condition)
        FK: compose_services(file_path, service_name) composite
        """
        self.generic_batches["compose_service_deps"].append(
            (file_path, service_name, depends_on_service, condition)
        )

    def add_terraform_resource_property(
        self,
        resource_id: str,
        property_name: str,
        property_value: str,
        is_sensitive: bool = False,
    ):
        """Add a Terraform resource property to the batch.

        Schema: terraform_resource_properties(resource_id, property_name, property_value, is_sensitive)
        FK: terraform_resources.resource_id (TEXT)
        """
        self.generic_batches["terraform_resource_properties"].append(
            (resource_id, property_name, property_value, 1 if is_sensitive else 0)
        )

    def add_terraform_resource_dep(
        self,
        resource_id: str,
        depends_on_resource: str,
    ):
        """Add a Terraform resource dependency to the batch.

        Schema: terraform_resource_deps(resource_id, depends_on_resource)
        FK: terraform_resources.resource_id (TEXT)
        """
        self.generic_batches["terraform_resource_deps"].append(
            (resource_id, depends_on_resource)
        )
