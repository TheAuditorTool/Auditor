## ADDED Requirements

### Requirement: Terraform Sources Are Indexed Into SQLite
Terraform, HCL, and tfvars files MUST be parsed structurally and persisted into the manifest database with resource, variable, output, and dependency data.

#### Scenario: Index Terraform Resources
- **GIVEN** a repository containing `main.tf` with multiple `resource` blocks and module references
- **WHEN** `aud index` (or `aud terraform provision`) runs
- **THEN** `terraform_files`, `terraform_resources`, `terraform_variables`, and `terraform_outputs` tables contain a row per parsed element with JSON properties matching the HCL structure
- **AND** `terraform_data_flow` stores edges for every `depends_on`, interpolation, or module input/output link the parser encounters

#### Scenario: Reject Regex Parsing
- **GIVEN** Terraform files that include heredocs, nested dynamic blocks, and complex interpolations
- **WHEN** the extractor runs under `THEAUDITOR_DEBUG=true`
- **THEN** logs confirm the structured parser (`python-hcl2` or tree-sitter HCL) handled the file
- **AND** no fallback regex extraction is executed

### Requirement: Provisioning Flow Graph Analysis Is Available
The system MUST construct a provisioning DAG and surface high-value Terraform security findings through the analyzer and rules engine.

#### Scenario: Detect Transitive Public Exposure
- **GIVEN** an `aws_db_instance` attached to a security group whose ingress allows `0.0.0.0/0`
- **WHEN** the Terraform analyzer runs
- **THEN** a finding is inserted into `terraform_findings` (and mirrored in `findings_consolidated`) describing the public exposure path
- **AND** the finding payload includes the list of graph nodes representing the exposure route (security group rule → security group → RDS instance)

#### Scenario: Trace Secret Propagation
- **GIVEN** a variable declared in `secrets.tfvars` feeding an ECS task definition environment variable
- **WHEN** the analyzer executes
- **THEN** `terraform_data_flow` includes edges from the variable to the task definition
- **AND** a secret propagation finding records both the source variable and the destination resource with evidence for FCE correlation

### Requirement: Pipeline & Reporting Expose Terraform Insights
Terraform provisioning analysis MUST integrate with the orchestrated pipeline, CLI, and downstream reporting.

#### Scenario: Full Pipeline Includes Terraform Stage
- **GIVEN** a project with Terraform files
- **WHEN** `aud full` executes
- **THEN** Stage 2 of `run_full_pipeline` runs the Terraform provisioning phase, emits `.pf/status/terraform_provision.status`, and populates `.pf/raw/terraform/*.json` by exporting database snapshots
- **AND** the command summary reports Terraform resource counts and finding severities

#### Scenario: FCE Correlates Terraform & Application Findings
- **GIVEN** an application secret finding referencing an IAM user and Terraform defines a wildcard policy for that user
- **WHEN** `aud fce` runs after Terraform analysis
- **THEN** FCE links the secret finding with the Terraform policy, generating a blast-radius correlation entry in `fce.json`
- **AND** the correlation references the Terraform resource IDs stored in the manifest
