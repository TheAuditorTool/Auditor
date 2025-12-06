"""Infrastructure storage handlers for IaC and GraphQL."""

import json

from theauditor.utils.logging import logger

from .base import BaseStorage


class InfrastructureStorage(BaseStorage):
    """Infrastructure-as-Code storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            "terraform_file": self._store_terraform_file,
            "terraform_resources": self._store_terraform_resources,
            "terraform_variables": self._store_terraform_variables,
            "terraform_variable_values": self._store_terraform_variable_values,
            "terraform_outputs": self._store_terraform_outputs,
            "terraform_data": self._store_terraform_data,
            "terraform_modules": self._store_terraform_modules,
            "terraform_providers": self._store_terraform_providers,
            "graphql_schemas": self._store_graphql_schemas,
            "graphql_types": self._store_graphql_types,
            "graphql_fields": self._store_graphql_fields,
            "graphql_field_args": self._store_graphql_field_args,
            "graphql_resolver_mappings": self._store_graphql_resolver_mappings,
            "graphql_resolver_params": self._store_graphql_resolver_params,
            "docker_images": self._store_docker_images,
            "dockerfile_ports": self._store_dockerfile_ports,
            "dockerfile_env_vars": self._store_dockerfile_env_vars,
            "dockerfile_instructions": self._store_dockerfile_instructions,
            "prisma_models": self._store_prisma_models,
            "compose_services": self._store_compose_services,
            "compose_service_ports": self._store_compose_service_ports,
            "compose_service_volumes": self._store_compose_service_volumes,
            "compose_service_envs": self._store_compose_service_envs,
            "compose_service_capabilities": self._store_compose_service_capabilities,
            "compose_service_deps": self._store_compose_service_deps,
            "nginx_configs": self._store_nginx_configs,
            "github_workflows": self._store_github_workflows,
            "github_jobs": self._store_github_jobs,
            "github_steps": self._store_github_steps,
            "github_step_outputs": self._store_github_step_outputs,
            "github_step_references": self._store_github_step_references,
            "github_job_dependencies": self._store_github_job_dependencies,
        }

    def _store_terraform_file(self, file_path: str, terraform_file: dict, jsx_pass: bool):
        """Store Terraform infrastructure definitions."""
        self.db_manager.add_terraform_file(
            file_path=terraform_file["file_path"],
            module_name=terraform_file.get("module_name"),
            stack_name=terraform_file.get("stack_name"),
            backend_type=terraform_file.get("backend_type"),
            providers_json=terraform_file.get("providers_json"),
            is_module=terraform_file.get("is_module", False),
            module_source=terraform_file.get("module_source"),
        )
        if "terraform_files" not in self.counts:
            self.counts["terraform_files"] = 0
        self.counts["terraform_files"] += 1

    def _store_terraform_resources(self, file_path: str, terraform_resources: list, jsx_pass: bool):
        """Store Terraform resources."""
        for resource in terraform_resources:
            resource_id = resource["resource_id"]
            properties = resource.get("properties", {})
            depends_on = resource.get("depends_on", [])
            sensitive_props = resource.get("sensitive_properties", [])

            self.db_manager.add_terraform_resource(
                resource_id=resource_id,
                file_path=resource["file_path"],
                resource_type=resource["resource_type"],
                resource_name=resource["resource_name"],
                module_path=resource.get("module_path"),
                has_public_exposure=resource.get("has_public_exposure", False),
                line=resource.get("line"),
            )

            for prop_name, prop_value in properties.items():
                is_sensitive = prop_name in sensitive_props
                self.db_manager.add_terraform_resource_property(
                    resource_id=resource_id,
                    property_name=prop_name,
                    property_value=str(prop_value) if prop_value is not None else "",
                    is_sensitive=is_sensitive,
                )

            for dep in depends_on:
                self.db_manager.add_terraform_resource_dep(
                    resource_id=resource_id,
                    depends_on_resource=dep,
                )

            if "terraform_resources" not in self.counts:
                self.counts["terraform_resources"] = 0
            self.counts["terraform_resources"] += 1

    def _store_terraform_variables(self, file_path: str, terraform_variables: list, jsx_pass: bool):
        """Store Terraform variables."""
        for variable in terraform_variables:
            self.db_manager.add_terraform_variable(
                variable_id=variable["variable_id"],
                file_path=variable["file_path"],
                variable_name=variable["variable_name"],
                variable_type=variable.get("variable_type"),
                default_json=json.dumps(variable.get("default"))
                if variable.get("default") is not None
                else None,
                is_sensitive=variable.get("is_sensitive", False),
                description=variable.get("description", ""),
                source_file=variable.get("source_file"),
                line=variable.get("line"),
            )
            if "terraform_variables" not in self.counts:
                self.counts["terraform_variables"] = 0
            self.counts["terraform_variables"] += 1

    def _store_terraform_variable_values(
        self, file_path: str, terraform_variable_values: list, jsx_pass: bool
    ):
        """Store Terraform variable values."""
        for value in terraform_variable_values:
            raw_value = value.get("variable_value")
            value_json = value.get("variable_value_json")
            if value_json is None and raw_value is not None:
                try:
                    value_json = json.dumps(raw_value)
                except TypeError:
                    value_json = json.dumps(str(raw_value))

            self.db_manager.add_terraform_variable_value(
                file_path=value["file_path"],
                variable_name=value["variable_name"],
                variable_value_json=value_json,
                line=value.get("line"),
                is_sensitive_context=value.get("is_sensitive_context", False),
            )
            if "terraform_variable_values" not in self.counts:
                self.counts["terraform_variable_values"] = 0
            self.counts["terraform_variable_values"] += 1

    def _store_terraform_outputs(self, file_path: str, terraform_outputs: list, jsx_pass: bool):
        """Store Terraform outputs."""
        for output in terraform_outputs:
            self.db_manager.add_terraform_output(
                output_id=output["output_id"],
                file_path=output["file_path"],
                output_name=output["output_name"],
                value_json=json.dumps(output.get("value"))
                if output.get("value") is not None
                else None,
                is_sensitive=output.get("is_sensitive", False),
                description=output.get("description", ""),
                line=output.get("line"),
            )
            if "terraform_outputs" not in self.counts:
                self.counts["terraform_outputs"] = 0
            self.counts["terraform_outputs"] += 1

    def _store_graphql_schemas(self, file_path: str, graphql_schemas: list, jsx_pass: bool):
        """Store GraphQL schema file records."""
        for schema in graphql_schemas:
            self.db_manager.add_graphql_schema(
                file_path=schema["file_path"],
                schema_hash=schema["schema_hash"],
                language=schema["language"],
                last_modified=schema.get("last_modified"),
            )
            if "graphql_schemas" not in self.counts:
                self.counts["graphql_schemas"] = 0
            self.counts["graphql_schemas"] += 1

    def _store_graphql_types(self, file_path: str, graphql_types: list, jsx_pass: bool):
        """Store GraphQL type definition records."""
        import os

        if os.environ.get("THEAUDITOR_DEBUG") == "1":
            logger.debug(f"Storage: _store_graphql_types called with {len(graphql_types)} types")

        for i, type_def in enumerate(graphql_types):
            if os.environ.get("THEAUDITOR_DEBUG") == "1" and i == 0:
                logger.debug(f"Storage: First type_def keys: {list(type_def.keys())}")
                logger.debug(f"Storage: First type_def values: {type_def}")

            self.db_manager.add_graphql_type(
                schema_path=type_def["schema_path"],
                type_name=type_def["type_name"],
                kind=type_def["kind"],
                implements=type_def.get("implements"),
                description=type_def.get("description"),
                line=type_def.get("line"),
            )
            if "graphql_types" not in self.counts:
                self.counts["graphql_types"] = 0
            self.counts["graphql_types"] += 1

    def _store_graphql_fields(self, file_path: str, graphql_fields: list, jsx_pass: bool):
        """Store GraphQL field definition records."""
        for field in graphql_fields:
            field_id = field.get("field_id")
            directives_json = field.get("directives_json")

            self.db_manager.add_graphql_field(
                type_id=field["type_id"],
                field_name=field["field_name"],
                return_type=field["return_type"],
                is_list=field.get("is_list", False),
                is_nullable=field.get("is_nullable", True),
                line=field.get("line"),
                column=field.get("column"),
            )

            if field_id and directives_json:
                try:
                    directives = json.loads(directives_json)
                    if isinstance(directives, list):
                        for directive in directives:
                            if isinstance(directive, dict):
                                self.db_manager.add_graphql_field_directive(
                                    field_id=field_id,
                                    directive_name=directive.get("name", ""),
                                    directive_args=json.dumps(directive.get("args", {})),
                                )
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(
                        f"DATA CORRUPTION: Invalid GraphQL field directives JSON.\n"
                        f"  File: {file_path}\n"
                        f"  Field: {field['field_name']}\n"
                        f"  Raw data: {repr(directives_json)[:200]}\n"
                        f"  Error: {e}"
                    ) from e

            if "graphql_fields" not in self.counts:
                self.counts["graphql_fields"] = 0
            self.counts["graphql_fields"] += 1

    def _store_graphql_field_args(self, file_path: str, graphql_field_args: list, jsx_pass: bool):
        """Store GraphQL field argument definition records."""
        for arg in graphql_field_args:
            field_id = arg["field_id"]
            arg_name = arg["arg_name"]
            directives_json = arg.get("directives_json")

            self.db_manager.add_graphql_field_arg(
                field_id=field_id,
                arg_name=arg_name,
                arg_type=arg["arg_type"],
                has_default=arg.get("has_default", False),
                default_value=arg.get("default_value"),
                is_nullable=arg.get("is_nullable", True),
            )

            if field_id and arg_name and directives_json:
                try:
                    directives = json.loads(directives_json)
                    if isinstance(directives, list):
                        for directive in directives:
                            if isinstance(directive, dict):
                                self.db_manager.add_graphql_arg_directive(
                                    field_id=field_id,
                                    arg_name=arg_name,
                                    directive_name=directive.get("name", ""),
                                    directive_args=json.dumps(directive.get("args", {})),
                                )
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(
                        f"DATA CORRUPTION: Invalid GraphQL arg directives JSON.\n"
                        f"  File: {file_path}\n"
                        f"  Arg: {arg_name}\n"
                        f"  Raw data: {repr(directives_json)[:200]}\n"
                        f"  Error: {e}"
                    ) from e

            if "graphql_field_args" not in self.counts:
                self.counts["graphql_field_args"] = 0
            self.counts["graphql_field_args"] += 1

    def _store_graphql_resolver_mappings(
        self, file_path: str, graphql_resolver_mappings: list, jsx_pass: bool
    ):
        """Store GraphQL resolver mapping records."""
        for mapping in graphql_resolver_mappings:
            self.db_manager.add_graphql_resolver_mapping(
                field_id=mapping.get("field_id", 0),
                resolver_symbol_id=mapping.get("resolver_symbol_id", 0),
                resolver_path=mapping.get("resolver_path", ""),
                resolver_line=mapping.get("resolver_line", 0),
                resolver_language=mapping.get("resolver_language", ""),
                binding_style=mapping.get("binding_style", ""),
                resolver_export=mapping.get("resolver_export"),
            )
            if "graphql_resolver_mappings" not in self.counts:
                self.counts["graphql_resolver_mappings"] = 0
            self.counts["graphql_resolver_mappings"] += 1

    def _store_graphql_resolver_params(
        self, file_path: str, graphql_resolver_params: list, jsx_pass: bool
    ):
        """Store GraphQL resolver parameter mapping records."""
        for param in graphql_resolver_params:
            self.db_manager.add_graphql_resolver_param(
                resolver_symbol_id=param.get("resolver_symbol_id", 0),
                arg_name=param.get("arg_name", ""),
                param_name=param.get("param_name", ""),
                param_index=param.get("param_index", 0),
                is_kwargs=param.get("is_kwargs", False),
                is_list_input=param.get("is_list_input", False),
            )
            if "graphql_resolver_params" not in self.counts:
                self.counts["graphql_resolver_params"] = 0
            self.counts["graphql_resolver_params"] += 1

    def _store_terraform_data(self, file_path: str, terraform_data: list, jsx_pass: bool):
        """Store Terraform data sources."""
        if not terraform_data:
            return
        for data_source in terraform_data:
            self.db_manager.add_terraform_data_source(
                data_id=data_source["data_id"],
                file_path=data_source["file_path"],
                data_type=data_source["data_type"],
                data_name=data_source["data_name"],
                line=data_source.get("line"),
            )
            if "terraform_data_sources" not in self.counts:
                self.counts["terraform_data_sources"] = 0
            self.counts["terraform_data_sources"] += 1

    def _store_terraform_modules(self, file_path: str, terraform_modules: list, jsx_pass: bool):
        """Store Terraform modules (stub - modules not yet extracted)."""

        pass

    def _store_terraform_providers(self, file_path: str, terraform_providers: list, jsx_pass: bool):
        """Store Terraform providers (stub - providers not yet extracted)."""

        pass

    def _store_docker_images(self, file_path: str, docker_images: list, jsx_pass: bool):
        """Store Docker image records."""
        for item in docker_images:
            self.db_manager.add_docker_image(
                file_path=item["file_path"],
                base_image=item.get("base_image"),
                user=item.get("user"),
                has_healthcheck=item.get("has_healthcheck", False),
            )
        if "docker_images" not in self.counts:
            self.counts["docker_images"] = 0
        self.counts["docker_images"] += len(docker_images)

    def _store_dockerfile_ports(self, file_path: str, dockerfile_ports: list, jsx_pass: bool):
        """Store Dockerfile EXPOSE port records."""
        for item in dockerfile_ports:
            self.db_manager.add_dockerfile_port(
                file_path=item["file_path"],
                port=item["port"],
                protocol=item.get("protocol", "tcp"),
            )
        if "dockerfile_ports" not in self.counts:
            self.counts["dockerfile_ports"] = 0
        self.counts["dockerfile_ports"] += len(dockerfile_ports)

    def _store_dockerfile_env_vars(self, file_path: str, dockerfile_env_vars: list, jsx_pass: bool):
        """Store Dockerfile ENV/ARG variable records."""
        for item in dockerfile_env_vars:
            self.db_manager.add_dockerfile_env_var(
                file_path=item["file_path"],
                var_name=item["var_name"],
                var_value=item.get("var_value"),
                is_build_arg=item.get("is_build_arg", False),
            )
        if "dockerfile_env_vars" not in self.counts:
            self.counts["dockerfile_env_vars"] = 0
        self.counts["dockerfile_env_vars"] += len(dockerfile_env_vars)

    def _store_dockerfile_instructions(
        self, file_path: str, dockerfile_instructions: list, jsx_pass: bool
    ):
        """Store Dockerfile instruction records."""
        for item in dockerfile_instructions:
            self.db_manager.add_dockerfile_instruction(
                file_path=item["file_path"],
                line=item["line"],
                instruction=item["instruction"],
                arguments=item.get("arguments"),
            )
        if "dockerfile_instructions" not in self.counts:
            self.counts["dockerfile_instructions"] = 0
        self.counts["dockerfile_instructions"] += len(dockerfile_instructions)

    def _store_prisma_models(self, file_path: str, prisma_models: list, jsx_pass: bool):
        """Store Prisma model field records."""
        for item in prisma_models:
            self.db_manager.add_prisma_model(
                model_name=item["model_name"],
                field_name=item["field_name"],
                field_type=item["field_type"],
                is_indexed=item.get("is_indexed", False),
                is_unique=item.get("is_unique", False),
                is_relation=item.get("is_relation", False),
            )
        if "prisma_models" not in self.counts:
            self.counts["prisma_models"] = 0
        self.counts["prisma_models"] += len(prisma_models)

    def _store_github_workflows(self, file_path: str, github_workflows: list, jsx_pass: bool):
        """Store GitHub Actions workflow records."""
        for item in github_workflows:
            self.db_manager.add_github_workflow(
                workflow_path=item["workflow_path"],
                workflow_name=item.get("workflow_name"),
                on_triggers=item["on_triggers"],
                permissions=item.get("permissions"),
                concurrency=item.get("concurrency"),
                env=item.get("env"),
            )
        if "github_workflows" not in self.counts:
            self.counts["github_workflows"] = 0
        self.counts["github_workflows"] += len(github_workflows)

    def _store_github_jobs(self, file_path: str, github_jobs: list, jsx_pass: bool):
        """Store GitHub Actions job records."""
        for item in github_jobs:
            self.db_manager.add_github_job(
                job_id=item["job_id"],
                workflow_path=item["workflow_path"],
                job_key=item["job_key"],
                job_name=item.get("job_name"),
                runs_on=item.get("runs_on"),
                strategy=item.get("strategy"),
                permissions=item.get("permissions"),
                env=item.get("env"),
                if_condition=item.get("if_condition"),
                timeout_minutes=item.get("timeout_minutes"),
                uses_reusable_workflow=item.get("uses_reusable_workflow", False),
                reusable_workflow_path=item.get("reusable_workflow_path"),
            )
        if "github_jobs" not in self.counts:
            self.counts["github_jobs"] = 0
        self.counts["github_jobs"] += len(github_jobs)

    def _store_github_steps(self, file_path: str, github_steps: list, jsx_pass: bool):
        """Store GitHub Actions step records."""
        for item in github_steps:
            self.db_manager.add_github_step(
                step_id=item["step_id"],
                job_id=item["job_id"],
                sequence_order=item["sequence_order"],
                step_name=item.get("step_name"),
                uses_action=item.get("uses_action"),
                uses_version=item.get("uses_version"),
                run_script=item.get("run_script"),
                shell=item.get("shell"),
                env=item.get("env"),
                with_args=item.get("with_args"),
                if_condition=item.get("if_condition"),
                timeout_minutes=item.get("timeout_minutes"),
                continue_on_error=item.get("continue_on_error", False),
            )
        if "github_steps" not in self.counts:
            self.counts["github_steps"] = 0
        self.counts["github_steps"] += len(github_steps)

    def _store_github_step_outputs(self, file_path: str, github_step_outputs: list, jsx_pass: bool):
        """Store GitHub Actions step output records."""
        for item in github_step_outputs:
            self.db_manager.add_github_step_output(
                step_id=item["step_id"],
                output_name=item["output_name"],
                output_expression=item["output_expression"],
            )
        if "github_step_outputs" not in self.counts:
            self.counts["github_step_outputs"] = 0
        self.counts["github_step_outputs"] += len(github_step_outputs)

    def _store_github_step_references(
        self, file_path: str, github_step_references: list, jsx_pass: bool
    ):
        """Store GitHub Actions step reference records."""
        for item in github_step_references:
            self.db_manager.add_github_step_reference(
                step_id=item["step_id"],
                reference_location=item["reference_location"],
                reference_type=item["reference_type"],
                reference_path=item["reference_path"],
            )
        if "github_step_references" not in self.counts:
            self.counts["github_step_references"] = 0
        self.counts["github_step_references"] += len(github_step_references)

    def _store_github_job_dependencies(
        self, file_path: str, github_job_dependencies: list, jsx_pass: bool
    ):
        """Store GitHub Actions job dependency records."""
        for item in github_job_dependencies:
            self.db_manager.add_github_job_dependency(
                job_id=item["job_id"],
                needs_job_id=item["needs_job_id"],
            )
        if "github_job_dependencies" not in self.counts:
            self.counts["github_job_dependencies"] = 0
        self.counts["github_job_dependencies"] += len(github_job_dependencies)

    def _store_compose_services(self, file_path: str, compose_services: list, jsx_pass: bool):
        """Store Docker Compose service records."""
        for item in compose_services:
            self.db_manager.add_compose_service(
                file_path=item["file_path"],
                service_name=item["service_name"],
                image=item.get("image"),
                is_privileged=item.get("is_privileged", False),
                network_mode=item.get("network_mode", "bridge"),
                user=item.get("user"),
                security_opt=item.get("security_opt"),
                restart=item.get("restart"),
                command=item.get("command"),
                entrypoint=item.get("entrypoint"),
                healthcheck=item.get("healthcheck"),
            )
        if "compose_services" not in self.counts:
            self.counts["compose_services"] = 0
        self.counts["compose_services"] += len(compose_services)

    def _store_compose_service_ports(
        self, file_path: str, compose_service_ports: list, jsx_pass: bool
    ):
        """Store Docker Compose service port mappings."""
        for item in compose_service_ports:
            self.db_manager.add_compose_service_port(
                file_path=item["file_path"],
                service_name=item["service_name"],
                host_port=item.get("host_port"),
                container_port=item["container_port"],
                protocol=item.get("protocol", "tcp"),
            )
        if "compose_service_ports" not in self.counts:
            self.counts["compose_service_ports"] = 0
        self.counts["compose_service_ports"] += len(compose_service_ports)

    def _store_compose_service_volumes(
        self, file_path: str, compose_service_volumes: list, jsx_pass: bool
    ):
        """Store Docker Compose service volume mappings."""
        for item in compose_service_volumes:
            self.db_manager.add_compose_service_volume(
                file_path=item["file_path"],
                service_name=item["service_name"],
                host_path=item.get("host_path"),
                container_path=item["container_path"],
                mode=item.get("mode", "rw"),
            )
        if "compose_service_volumes" not in self.counts:
            self.counts["compose_service_volumes"] = 0
        self.counts["compose_service_volumes"] += len(compose_service_volumes)

    def _store_compose_service_envs(
        self, file_path: str, compose_service_envs: list, jsx_pass: bool
    ):
        """Store Docker Compose service environment variables."""
        for item in compose_service_envs:
            self.db_manager.add_compose_service_env(
                file_path=item["file_path"],
                service_name=item["service_name"],
                var_name=item["var_name"],
                var_value=item.get("var_value"),
            )
        if "compose_service_envs" not in self.counts:
            self.counts["compose_service_envs"] = 0
        self.counts["compose_service_envs"] += len(compose_service_envs)

    def _store_compose_service_capabilities(
        self, file_path: str, compose_service_capabilities: list, jsx_pass: bool
    ):
        """Store Docker Compose service capabilities (cap_add/cap_drop)."""
        for item in compose_service_capabilities:
            self.db_manager.add_compose_service_capability(
                file_path=item["file_path"],
                service_name=item["service_name"],
                capability=item["capability"],
                is_add=item.get("is_add", True),
            )
        if "compose_service_capabilities" not in self.counts:
            self.counts["compose_service_capabilities"] = 0
        self.counts["compose_service_capabilities"] += len(compose_service_capabilities)

    def _store_compose_service_deps(
        self, file_path: str, compose_service_deps: list, jsx_pass: bool
    ):
        """Store Docker Compose service dependencies."""
        for item in compose_service_deps:
            self.db_manager.add_compose_service_dep(
                file_path=item["file_path"],
                service_name=item["service_name"],
                depends_on_service=item["depends_on_service"],
                condition=item.get("condition", "service_started"),
            )
        if "compose_service_deps" not in self.counts:
            self.counts["compose_service_deps"] = 0
        self.counts["compose_service_deps"] += len(compose_service_deps)

    def _store_nginx_configs(self, file_path: str, nginx_configs: list, jsx_pass: bool):
        """Store Nginx configuration blocks."""
        for item in nginx_configs:
            self.db_manager.add_nginx_config(
                file_path=item["file_path"],
                block_type=item["block_type"],
                block_context=item.get("block_context", "default"),
                directives=item.get("directives", {}),
                level=item.get("level", 0),
            )
        if "nginx_configs" not in self.counts:
            self.counts["nginx_configs"] = 0
        self.counts["nginx_configs"] += len(nginx_configs)
