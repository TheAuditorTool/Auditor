"""Infrastructure database operations.

This module contains add_* methods for INFRASTRUCTURE_TABLES defined in schemas/infrastructure_schema.py.
Handles 18 infrastructure tables including Docker, Terraform, AWS CDK, and GitHub Actions.
"""

import json
import os
from typing import Optional, Dict, List


class InfrastructureDatabaseMixin:
    """Mixin providing add_* methods for INFRASTRUCTURE_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    # ========================================================
    # DOCKER BATCH METHODS
    # ========================================================

    def add_docker_image(self, file_path: str, base_image: Optional[str], exposed_ports: List[str],
                        env_vars: Dict, build_args: Dict, user: Optional[str], has_healthcheck: bool):
        """Add a Docker image record to the batch."""
        ports_json = json.dumps(exposed_ports)
        env_json = json.dumps(env_vars)
        args_json = json.dumps(build_args)
        self.generic_batches['docker_images'].append((file_path, base_image, ports_json, env_json,
                                                      args_json, user, has_healthcheck))

    def add_compose_service(self, file_path: str, service_name: str, image: Optional[str],
                           ports: List[str], volumes: List[str], environment: Dict,
                           is_privileged: bool, network_mode: str,
                           # 9 new security fields (Phase 3C)
                           user: Optional[str] = None,
                           cap_add: Optional[List[str]] = None,
                           cap_drop: Optional[List[str]] = None,
                           security_opt: Optional[List[str]] = None,
                           restart: Optional[str] = None,
                           command: Optional[List[str]] = None,
                           entrypoint: Optional[List[str]] = None,
                           depends_on: Optional[List[str]] = None,
                           healthcheck: Optional[Dict] = None):
        """Add a Docker Compose service record to the batch.

        Args:
            file_path: Path to docker-compose.yml
            service_name: Name of the service
            image: Docker image name
            ports: List of port mappings
            volumes: List of volume mounts
            environment: Dictionary of environment variables
            is_privileged: Whether service runs in privileged mode
            network_mode: Network mode (bridge, host, etc.)
            user: User/UID to run as (security: detect root)
            cap_add: Linux capabilities to add (security: detect dangerous caps)
            cap_drop: Linux capabilities to drop (security: enforce hardening)
            security_opt: Security options (security: detect disabled AppArmor/SELinux)
            restart: Restart policy (operational: availability)
            command: Override CMD instruction (security: command injection risk)
            entrypoint: Override ENTRYPOINT instruction (security: tampering)
            depends_on: Service dependencies (operational: dependency graph)
            healthcheck: Health check configuration (operational: availability)
        """
        ports_json = json.dumps(ports)
        volumes_json = json.dumps(volumes)
        env_json = json.dumps(environment)

        # Encode new fields as JSON (or None if not provided)
        cap_add_json = json.dumps(cap_add) if cap_add else None
        cap_drop_json = json.dumps(cap_drop) if cap_drop else None
        security_opt_json = json.dumps(security_opt) if security_opt else None
        command_json = json.dumps(command) if command else None
        entrypoint_json = json.dumps(entrypoint) if entrypoint else None
        depends_on_json = json.dumps(depends_on) if depends_on else None
        healthcheck_json = json.dumps(healthcheck) if healthcheck else None

        self.generic_batches['compose_services'].append((
            file_path, service_name, image, ports_json, volumes_json, env_json,
            is_privileged, network_mode,
            # 9 new fields
            user, cap_add_json, cap_drop_json, security_opt_json,
            restart, command_json, entrypoint_json, depends_on_json, healthcheck_json
        ))

    def add_nginx_config(self, file_path: str, block_type: str, block_context: str,
                        directives: Dict, level: int):
        """Add an Nginx configuration block to the batch."""
        directives_json = json.dumps(directives)
        # Use a default context if empty to avoid primary key issues
        block_context = block_context or 'default'

        # Check for duplicates before adding
        batch = self.generic_batches['nginx_configs']
        batch_key = (file_path, block_type, block_context)
        if not any(b[:3] == batch_key for b in batch):
            batch.append((file_path, block_type, block_context, directives_json, level))

    # ========================================================
    # TERRAFORM BATCH METHODS
    # ========================================================

    def add_terraform_file(self, file_path: str, module_name: Optional[str] = None,
                          stack_name: Optional[str] = None, backend_type: Optional[str] = None,
                          providers_json: Optional[str] = None, is_module: bool = False,
                          module_source: Optional[str] = None):
        """Add a Terraform file record to the batch."""
        self.generic_batches['terraform_files'].append((
            file_path, module_name, stack_name, backend_type,
            providers_json, is_module, module_source
        ))

    def add_terraform_resource(self, resource_id: str, file_path: str, resource_type: str,
                               resource_name: str, module_path: Optional[str] = None,
                               properties_json: Optional[str] = None,
                               depends_on_json: Optional[str] = None,
                               sensitive_flags_json: Optional[str] = None,
                               has_public_exposure: bool = False,
                               line: Optional[int] = None):
        """Add a Terraform resource record to the batch."""
        self.generic_batches['terraform_resources'].append((
            resource_id, file_path, resource_type, resource_name,
            module_path, properties_json, depends_on_json,
            sensitive_flags_json, has_public_exposure, line
        ))

    def add_terraform_variable(self, variable_id: str, file_path: str, variable_name: str,
                               variable_type: Optional[str] = None,
                               default_json: Optional[str] = None,
                               is_sensitive: bool = False,
                               description: str = '',
                               source_file: Optional[str] = None,
                               line: Optional[int] = None):
        """Add a Terraform variable record to the batch."""
        self.generic_batches['terraform_variables'].append((
            variable_id, file_path, variable_name, variable_type,
            default_json, is_sensitive, description, source_file, line
        ))

    def add_terraform_variable_value(self, file_path: str, variable_name: str,
                                     variable_value_json: Optional[str] = None,
                                     line: Optional[int] = None,
                                     is_sensitive_context: bool = False):
        """Add a .tfvars variable value record to the batch."""
        self.generic_batches['terraform_variable_values'].append((
            file_path,
            variable_name,
            variable_value_json,
            line,
            is_sensitive_context,
        ))

    def add_terraform_output(self, output_id: str, file_path: str, output_name: str,
                            value_json: Optional[str] = None,
                            is_sensitive: bool = False,
                            description: str = '',
                            line: Optional[int] = None):
        """Add a Terraform output record to the batch."""
        self.generic_batches['terraform_outputs'].append((
            output_id, file_path, output_name, value_json,
            is_sensitive, description, line
        ))

    def add_terraform_finding(self, finding_id: str, file_path: str,
                             resource_id: Optional[str] = None,
                             category: str = '',
                             severity: str = 'medium',
                             title: str = '',
                             description: str = '',
                             graph_context_json: Optional[str] = None,
                             remediation: str = '',
                             line: Optional[int] = None):
        """Add a Terraform finding record to the batch."""
        self.generic_batches['terraform_findings'].append((
            finding_id, file_path, resource_id, category,
            severity, title, description, graph_context_json,
            remediation, line
        ))

    # ========================================================================
    # AWS CDK (Cloud Development Kit) Infrastructure-as-Code Methods
    # ========================================================================

    def add_cdk_construct(self, file_path: str, line: int, cdk_class: str,
                         construct_name: Optional[str], construct_id: str):
        """Add a CDK construct record to the batch.

        Args:
            file_path: Path to Python file containing construct
            line: Line number of construct instantiation
            cdk_class: CDK class name (e.g., 's3.Bucket', 'aws_cdk.aws_s3.Bucket')
            construct_name: CDK logical ID (nullable - 2nd positional arg)
            construct_id: Composite key: {file}::L{line}::{class}::{name}
        """
        # DEBUG: Log all construct_ids being added to batch
        if os.environ.get('THEAUDITOR_CDK_DEBUG') == '1':
            print(f"[CDK-DB] Adding to batch: {construct_id}")

        self.generic_batches['cdk_constructs'].append((
            construct_id, file_path, line, cdk_class, construct_name
        ))

    def add_cdk_construct_property(self, construct_id: str, property_name: str,
                                   property_value_expr: str, line: int):
        """Add a CDK construct property record to the batch.

        Args:
            construct_id: FK to cdk_constructs.construct_id
            property_name: Property keyword argument name (e.g., 'public_read_access')
            property_value_expr: Serialized property value via ast.unparse()
            line: Line number of property definition
        """
        self.generic_batches['cdk_construct_properties'].append((
            construct_id, property_name, property_value_expr, line
        ))

    def add_cdk_finding(self, finding_id: str, file_path: str,
                       construct_id: Optional[str] = None,
                       category: str = '',
                       severity: str = 'medium',
                       title: str = '',
                       description: str = '',
                       remediation: str = '',
                       line: Optional[int] = None):
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
        self.generic_batches['cdk_findings'].append((
            finding_id, file_path, construct_id, category,
            severity, title, description, remediation, line
        ))

    # ========================================================================
    # GitHub Actions CI/CD Workflow Security Methods
    # ========================================================================

    def add_github_workflow(self, workflow_path: str, workflow_name: Optional[str],
                           on_triggers: str, permissions: Optional[str] = None,
                           concurrency: Optional[str] = None, env: Optional[str] = None):
        """Add a GitHub Actions workflow record to the batch.

        Args:
            workflow_path: Path to workflow file (.github/workflows/ci.yml)
            workflow_name: Workflow name from 'name:' field or filename
            on_triggers: JSON array of trigger events
            permissions: JSON object of workflow-level permissions
            concurrency: JSON object of concurrency settings
            env: JSON object of workflow-level environment variables
        """
        self.generic_batches['github_workflows'].append((
            workflow_path, workflow_name, on_triggers, permissions, concurrency, env
        ))

    def add_github_job(self, job_id: str, workflow_path: str, job_key: str,
                      job_name: Optional[str], runs_on: Optional[str],
                      strategy: Optional[str] = None, permissions: Optional[str] = None,
                      env: Optional[str] = None, if_condition: Optional[str] = None,
                      timeout_minutes: Optional[int] = None,
                      uses_reusable_workflow: bool = False,
                      reusable_workflow_path: Optional[str] = None):
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
        self.generic_batches['github_jobs'].append((
            job_id, workflow_path, job_key, job_name, runs_on, strategy,
            permissions, env, if_condition, timeout_minutes,
            uses_reusable_workflow, reusable_workflow_path
        ))

    def add_github_job_dependency(self, job_id: str, needs_job_id: str):
        """Add a GitHub Actions job dependency edge (needs: relationship).

        Args:
            job_id: FK to github_jobs (dependent job)
            needs_job_id: FK to github_jobs (dependency job)
        """
        self.generic_batches['github_job_dependencies'].append((
            job_id, needs_job_id
        ))

    def add_github_step(self, step_id: str, job_id: str, sequence_order: int,
                       step_name: Optional[str], uses_action: Optional[str],
                       uses_version: Optional[str], run_script: Optional[str],
                       shell: Optional[str], env: Optional[str],
                       with_args: Optional[str], if_condition: Optional[str],
                       timeout_minutes: Optional[int], continue_on_error: bool = False):
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
        self.generic_batches['github_steps'].append((
            step_id, job_id, sequence_order, step_name, uses_action, uses_version,
            run_script, shell, env, with_args, if_condition, timeout_minutes,
            continue_on_error
        ))

    def add_github_step_output(self, step_id: str, output_name: str, output_expression: str):
        """Add a GitHub Actions step output declaration.

        Args:
            step_id: FK to github_steps
            output_name: Output key
            output_expression: Value expression
        """
        self.generic_batches['github_step_outputs'].append((
            step_id, output_name, output_expression
        ))

    def add_github_step_reference(self, step_id: str, reference_location: str,
                                  reference_type: str, reference_path: str):
        """Add a GitHub Actions step reference (${{ }} expression).

        Args:
            step_id: FK to github_steps
            reference_location: Where reference appears ('run', 'env', 'with', 'if')
            reference_type: Type of reference ('github', 'secrets', 'env', 'needs', 'steps')
            reference_path: Full path (e.g., 'github.event.pull_request.head.sha')
        """
        self.generic_batches['github_step_references'].append((
            step_id, reference_location, reference_type, reference_path
        ))
