## Why
- The indexer ignores Terraform/HCL files entirely, leaving infrastructure definitions out of `.pf/repo_index.db` (`theauditor/indexer/config.py:128` only authorizes Python/JS extensions; verification checklist #1).
- Without a provisioning flow graph, we cannot reason about relationships between IaC resources (e.g., security groups → databases) or correlate them with application findings; the database has no Terraform tables today (`verification.md`, hypothesis #2).
- The audit pipeline and rules engine have no Terraform stage or taint-aware rules, preventing the orchestrator and downstream agents from detecting public exposure, privilege escalation, or secret leakage paths defined in Terraform (`verification.md`, hypothesis #3-4).

## What Changes
- Introduce structural Terraform parsing:
  - Add `python-hcl2` (runtime) and `tree-sitter-hcl` (optional `ast` extra) dependencies in `pyproject.toml`.
  - Implement `TerraformExtractor` under `theauditor/indexer/extractors/terraform.py` that uses the structured parser, never regex, and emits resource, variable, output, and module metadata.
  - Extend `ASTParser` feature detection to register HCL parsing when optional grammar is available, falling back to `python-hcl2` to satisfy the “no guesswork” directive.
- Extend the SQLite manifest with Terraform-first tables, adhering to the schema contract:
  - `terraform_files(file_path, module_name, stack_name, backend_type, providers_json)`.
  - `terraform_resources(resource_id PK, file_path FK, resource_type, resource_name, module_path, properties_json, depends_on_json, sensitive_flags_json)`.
  - `terraform_variables(variable_id PK, file_path FK, variable_name, default_json, is_sensitive, source_file)`.
  - `terraform_outputs(output_id PK, file_path FK, output_name, value_json, is_sensitive)`.
  - `terraform_data_flow(source_id, source_kind, source_attribute, destination_id, destination_kind, destination_attribute, edge_type)`, representing DAG edges (variables/resources/data blocks).
  - Supply indexes (`idx_terraform_resources_type`, `idx_terraform_data_flow_destination`) and batch insert APIs inside `DatabaseManager`.
- Create a provisioning flow analysis module:
  - New package `theauditor/terraform/` with orchestrator that normalizes parsed data, constructs a canonical DAG, resolves interpolations, and writes consolidated findings to `terraform_findings` (a new normalized fact table) and `findings_consolidated` for FCE consumption.
  - Implement deterministic resolution of module outputs/inputs, remote state references, and provider aliases with strict error logging when lookups fail.
- Add IaC rule integration:
  - New `theauditor/rules/terraform/` category with standardized rules for (a) public exposure via security groups, (b) wildcard IAM policies on tagged resources, (c) secret propagation into plaintext environment variables.
  - Rules query the new tables via `build_query` and publish structured findings with graph context (path traces, blast radius lists).
- Pipeline and CLI orchestration:
  - Register `aud terraform provision` (standalone command) under `theauditor/commands/terraform.py` that runs extraction, graph build, rule execution, and report emission.
  - Extend `run_full_pipeline` Stage 2 to invoke the Terraform provisioning phase after graph construction, respecting `--offline` and `--exclude-self`.
  - Record progress in `.pf/status/terraform_provision.status`, dual-write raw JSON under `.pf/raw/terraform/` (graph, findings) while keeping the database authoritative.
- Downstream consumption:
  - Enhance `theauditor/fce.py` to correlate application secrets with Terraform IAM users/policies and to surface blast-radius summaries using the DAG.
  - Expose Terraform evidence through `.pf/readthis/terraform_*` capsules for AI agents, reusing the existing chunking pipeline.
  - Update `aud summary` and `aud impact` to include Terraform statistics (resource count, public-exposure findings).
- Documentation and guardrails:
  - Extend `README.md`, `HOWTOUSE.md`, and `ARCHITECTURE.md` with the Terraform pipeline overview and database schema diagrams.
  - Add unit coverage for extractor edge cases and integration tests that run the Terraform stage on curated fixtures (AWS + multi-module stacks).

## Impact
- Elevates Terraform to first-class status in the Truth Courier model: IaC resources, variables, and edges become queryable facts in SQLite, allowing all agents to reason about provisioning flows without re-parsing HCL.
- Enables complex IaC vulnerability detection (transitive exposure, privilege escalation, secret leakage) and correlates those findings with application code via the FCE, closing the current observability gap.
- Provides an orchestrator-compliant command and pipeline stage so Terraform analysis can be automated, cached, and consumed the same way as existing analyses.

## Verification Alignment
- Verification evidence captured in `openspec/changes/add-terraform-provisioning-flow/verification.md`.
- Architecture intent and data model decisions elaborated in `openspec/changes/add-terraform-provisioning-flow/design.md`.
