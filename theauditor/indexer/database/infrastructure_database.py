"""Infrastructure database operations."""

import json
import os

from theauditor.utils.logging import logger


class InfrastructureDatabaseMixin:
    """Mixin providing add_* methods for INFRASTRUCTURE_TABLES."""

    def add_docker_image(
        self,
        file_path: str,
        base_image: str | None,
        user: str | None,
        has_healthcheck: bool,
    ):
        """Add a Docker image record to the batch."""
        self.generic_batches["docker_images"].append((file_path, base_image, user, has_healthcheck))

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
        """Add a Docker Compose service record to the batch."""
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
        """Add a Terraform resource record to the batch."""
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

    def add_terraform_data_source(
        self,
        data_id: str,
        file_path: str,
        data_type: str,
        data_name: str,
        line: int | None = None,
    ):
        """Add a Terraform data source record to the batch."""
        self.generic_batches["terraform_data_sources"].append(
            (data_id, file_path, data_type, data_name, line)
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
        """Add a CDK construct record to the batch."""

        if os.environ.get("THEAUDITOR_CDK_DEBUG") == "1":
            logger.info(f"Adding to batch: {construct_id}")

        self.generic_batches["cdk_constructs"].append(
            (construct_id, file_path, line, cdk_class, construct_name)
        )

    def add_cdk_construct_property(
        self, construct_id: str, property_name: str, property_value_expr: str, line: int
    ):
        """Add a CDK construct property record to the batch."""
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
        """Add a CDK security finding record to the batch."""
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
        """Add a GitHub Actions workflow record to the batch."""
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
        """Add a GitHub Actions job record to the batch."""
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
        """Add a GitHub Actions job dependency edge (needs: relationship)."""
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
        """Add a GitHub Actions step record to the batch."""
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
        """Add a GitHub Actions step output declaration."""
        self.generic_batches["github_step_outputs"].append(
            (step_id, output_name, output_expression)
        )

    def add_github_step_reference(
        self, step_id: str, reference_location: str, reference_type: str, reference_path: str
    ):
        """Add a GitHub Actions step reference (${{ }} expression)."""
        self.generic_batches["github_step_references"].append(
            (step_id, reference_location, reference_type, reference_path)
        )

    def add_dockerfile_port(
        self,
        file_path: str,
        port: str,
        protocol: str = "tcp",
    ):
        """Add a Dockerfile EXPOSE port to the batch."""
        self.generic_batches["dockerfile_ports"].append((file_path, port, protocol))

    def add_dockerfile_env_var(
        self,
        file_path: str,
        var_name: str,
        var_value: str | None,
        is_build_arg: bool = False,
    ):
        """Add a Dockerfile ENV/ARG variable to the batch."""
        self.generic_batches["dockerfile_env_vars"].append(
            (file_path, var_name, var_value, 1 if is_build_arg else 0)
        )

    def add_dockerfile_instruction(
        self,
        file_path: str,
        line: int,
        instruction: str,
        arguments: str | None,
    ):
        """Add a Dockerfile instruction to the batch."""
        self.generic_batches["dockerfile_instructions"].append(
            (file_path, line, instruction, arguments)
        )

    def add_compose_service_port(
        self,
        file_path: str,
        service_name: str,
        host_port: str | None,
        container_port: str,
        protocol: str = "tcp",
    ):
        """Add a compose service port mapping to the batch."""
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
        """Add a compose service volume mapping to the batch."""
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
        """Add a compose service environment variable to the batch."""
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
        """Add a compose service capability (cap_add/cap_drop) to the batch."""
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
        """Add a compose service dependency to the batch."""
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
        """Add a Terraform resource property to the batch."""
        self.generic_batches["terraform_resource_properties"].append(
            (resource_id, property_name, property_value, 1 if is_sensitive else 0)
        )

    def add_terraform_resource_dep(
        self,
        resource_id: str,
        depends_on_resource: str,
    ):
        """Add a Terraform resource dependency to the batch."""
        self.generic_batches["terraform_resource_deps"].append((resource_id, depends_on_resource))
