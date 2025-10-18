## Verification Summary
- Indexer ignores Terraform/HCL sources; `.tf` files never enter `.pf/repo_index.db` (`theauditor/indexer/config.py:128`, extractor discovery log).
- Database schema has no Terraform tables; `rg "terraform"` across `schema.py` and `database.py` produced no hits.
- Pipeline/FCE/rules lack Terraform-aware stages, so no downstream consumer can reference IaC facts.
- No structural HCL parser dependency currently ships with TheAuditor; we must introduce one to avoid regex/heuristics.

## Goals
1. Parse Terraform projects (root and modules) structurally, capturing resources, variables, outputs, modules, and provider backends.
2. Persist provisioning facts and data-flow edges into SQLite so any agent can query relationships without re-reading HCL.
3. Analyze the resulting DAG for high-value security findings and expose them through rules, FCE, and reports.
4. Integrate Terraform analysis into the orchestrated pipeline with dual-write artifacts (DB primary, JSON secondary).

## Non-Goals
- Supporting every Terraform provider-specific nuance in v1 (focus on core AWS/Azure/GCP resource models, graph is provider-agnostic).
- Replacing Terraform plan/apply tooling; we ingest static configuration only.
- Building a general-purpose HCL editor—extraction only, no mutation/autofix.

## Component Architecture

### 1. Parsing Layer (`theauditor/terraform/parser.py`)
- Uses `python-hcl2` for canonical parsing; optionally enriches with `tree-sitter-hcl` when AST extras installed for precise position metadata.
- Normalizes blocks into typed records (resource, data, variable, output, module) with resolved module paths and stack names.
- Emits structured dictionaries with origin metadata (file path, line range, module path) for ingestion.

### 2. Indexer Integration
- New `TerraformExtractor` (discoverable via `ExtractorRegistry`) owns `.tf`, `.tfvars`, `.tf.json`, and module directories.
- Extractor orchestrates parser invocations, converts records to database rows, and streams them through the new DatabaseManager batch APIs.
- `IndexerOrchestrator` updates stats counters (`terraform_resources`, `terraform_data_edges`) and captures extractor exceptions with actionable logging.

### 3. Data Model (SQLite)
- `terraform_files`: catalog of Terraform entrypoints with backend/provider metadata to group resources per stack.
- `terraform_resources`: canonical resource nodes with JSON-serialized properties, dependency lists, and sensitivity flags (e.g., `public = true`, `kms_key` missing).
- `terraform_variables`: variables with default/object metadata and sensitivity classification.
- `terraform_outputs`: outputs referencing sensitive data (used for secret propagation analysis).
- `terraform_data_flow`: edges capturing interpolations and explicit `depends_on` relationships; fields encode source/destination type/kind.
- `terraform_findings`: normalized IaC findings with severity, category, graph context (path, affected nodes). This feeds FCE and chunking without overloading `findings_consolidated` with Terraform-specific columns.
- Each table defined in `schema.py` with indexes: e.g., `(resource_type, resource_name)` for resources, `(destination_id, edge_type)` for data flow, `(severity, category)` for findings.

### 4. Provisioning Flow Orchestrator (`theauditor/terraform/analyzer.py`)
- Consumes records via database queries (not in-memory caches) to build a Provisioning Flow Graph (DAG).
- Performs analyses:
  - **Public Exposure**: Trace any path from ingress CIDR `0.0.0.0/0` (security group rules) to compute/database resources flagged as sensitive.
  - **Privilege Escalation**: Identify IAM policies granting `*` actions or wildcard principals attached to resources tagged `env=prod` or flagged sensitive.
  - **Secret Propagation**: Track variables sourced from `.tfvars` or remote state marked sensitive ending up in plain environment variables, ECS task definitions, Lambda env, etc.
- Writes results to `terraform_findings` with JSON context (graph path nodes) and duplicates into `findings_consolidated` (tool=`terraform-analyzer`) to keep correlation unified.
- Exposes helper queries for FCE and rules to reuse graph traversals without recalculating them.

### 5. Rules Integration (`theauditor/rules/terraform/`)
- Rule modules interact strictly via SQLite queries built with `build_query`; they never read HCL files directly.
- Each rule produces `StandardFinding` objects, ensuring orchestrator/template compliance.
- Rules re-use analyzer-provided intermediate tables to avoid duplicating graph traversal logic (e.g., `terraform_attack_paths` view built by analyzer).

### 6. Pipeline & CLI
- New command `aud terraform provision` orchestrates: ensure index is fresh → run Terraform extractor (if index stale) → execute analyzer → run Terraform rules → emit reports.
- `run_full_pipeline` extends Stage 2 with a Terraform phase placed after dependency graph build but before heavy analyses, so Track B/Track C can consume Terraform findings in the same run.
- Phase writes `.pf/status/terraform_provision.status` with progress updates and logs outputs to `.pf/raw/terraform/` via `DatabaseManager.export_table_json` helpers.
- Timeout entries added to `COMMAND_TIMEOUTS` to avoid long-running stalls on huge Terraform repos.

### 7. Downstream Consumption
- `theauditor/fce.py` loads Terraform findings and correlates them with application secrets (`secrets` table) and taint paths to outline blast radius (e.g., leaked IAM key → IAM user policy → Terraform resource referencing it).
- `aud summary` and `aud impact` aggregate Terraform resource counts, high-risk findings, and graph metrics (node/edge counts) for quick visibility.
- Chunk generator emits Terraform-specific JSON capsules referencing the same database rows to keep AI-ready data consistent.

### 8. Failure Handling & Validation
- Parser errors: Terraform extractor logs file/line context and records a warning in `.pf/status` but continues processing other files.
- Schema validation: `validate_all_tables` extended to include new tables; tests ensure migrations refuse to silently proceed if schema drift detected.
- Optional dependencies: command detects missing `python-hcl2` and surfaces actionable instructions (`pip install theauditor[terraform]` once defined) without crashing the entire pipeline.
- Integration tests: curated Terraform fixtures (AWS VPC + RDS, IAM policies, ECS tasks) cover DAG construction, findings, and FCE correlation.

## Open Questions
- Do we need dedicated handling for Terraform Cloud/remote state references in v1? Proposal: store unresolved references with edge_type=`remote_state` and treat them as informational findings until a resolver is implemented.
- Should Terraform outputs be mirrored into `.pf/readthis/` by default or only when findings exist? Initial plan: emit summary chunk when any Terraform finding or sensitive resource is detected to avoid noisy output.
