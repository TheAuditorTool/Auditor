## 0. Verification (SOP v4.20 alignment)
- [x] 0.1 Document hypotheses, evidence, and discrepancies in `openspec/changes/add-terraform-provisioning-flow/verification.md`.
- [x] 0.2 Capture architectural intent, parser selection, and DAG expectations in `design.md` for auditor review.
- [x] 0.3 Inspect `theauditor/indexer`, `theauditor/pipelines.py`, `theauditor/fce.py`, and `pyproject.toml` to confirm Terraform support is absent (see verification log).

## 1. Parser & Dependency Foundation
- [ ] 1.1 Add `python-hcl2` to the core dependency set and expose `tree-sitter-hcl` under the `ast` extra in `pyproject.toml`.
- [ ] 1.2 Extend `theauditor/ast_parser.py` to detect optional HCL grammar support and fall back to `python-hcl2` while enforcing structural parsing (no heuristics).
- [ ] 1.3 Create reusable Terraform parsing utilities (`theauditor/terraform/parser.py`) that normalize resources, variables, outputs, and module references from parsed HCL.

## 2. Schema & Persistence
- [ ] 2.1 Define new Terraform tables (`terraform_files`, `terraform_resources`, `terraform_variables`, `terraform_outputs`, `terraform_data_flow`, `terraform_findings`) in `theauditor/indexer/schema.py` with indexes and contracts.
- [ ] 2.2 Update `DatabaseManager` (`theauditor/indexer/database.py`) to initialize batch buffers, create tables, and expose insert helpers for the new schemas.
- [ ] 2.3 Add schema validation coverage in `tests/test_schema_contract.py` for the Terraform tables and ensure migrations are deterministic.

## 3. Indexer Extraction & DAG Construction
- [ ] 3.1 Implement `TerraformExtractor` under `theauditor/indexer/extractors/terraform.py` that walks `.tf`, `.tfvars`, and module directories, emitting normalized records via the new DatabaseManager hooks.
- [ ] 3.2 Register Terraform extensions in `ExtractorRegistry` and enrich `IndexerOrchestrator` with Terraform-aware statistics and failure logging.
- [ ] 3.3 Build `theauditor/terraform/graph.py` to transform raw records into a provisioning flow DAG and persist edges into `terraform_data_flow`.

## 4. Analysis, Rules, and Correlation
- [ ] 4.1 Add `theauditor/terraform/analyzer.py` to compute high-value insights (public exposure, IAM wildcarding, secret propagation) and dual-write findings to `terraform_findings` and `findings_consolidated`.
- [ ] 4.2 Create `theauditor/rules/terraform/` with standardized rule modules executed via the rules orchestrator; ensure they operate purely on database queries.
- [ ] 4.3 Extend `theauditor/fce.py` to join Terraform tables with application findings, produce blast-radius summaries, and expose correlation metadata.

## 5. Pipeline & CLI Integration
- [ ] 5.1 Implement `theauditor/commands/terraform.py` (`aud terraform provision`) with options for target root, module include/exclude, and offline mode.
- [ ] 5.2 Integrate Terraform provisioning into Stage 2 of `run_full_pipeline`, update phase manifests (`.pf/status/terraform_provision.status`), and honor `--exclude-self` semantics.
- [ ] 5.3 Ensure the new phase participates in pipeline retries/error handling, including timeout configuration and logging.

## 6. Outputs & Reporting
- [ ] 6.1 Emit raw Terraform artifacts under `.pf/raw/terraform/` (resources.json, graph.json, findings.json) sourced from database snapshots to keep JSON secondary.
- [ ] 6.2 Extend chunking/report pipelines (`theauditor/pipelines.py`, `theauditor/commands/summary.py`, `theauditor/commands/impact.py`) to surface Terraform counts and findings.
- [ ] 6.3 Update `.pf/allfiles.md` generation to list Terraform outputs for traceability.

## 7. Documentation & Testing
- [ ] 7.1 Document Terraform support in `README.md`, `HOWTOUSE.md`, `ARCHITECTURE.md`, and add a schema diagram covering the new tables.
- [ ] 7.2 Add extractor unit tests, DAG builder tests, and integration fixtures under `tests/terraform/` that verify database writes and rule detections.
- [ ] 7.3 Update any developer onboarding docs to highlight optional AST extras and Terraform prerequisites.

## 8. Validation
- [ ] 8.1 Run `openspec validate add-terraform-provisioning-flow --strict` and resolve findings.
- [ ] 8.2 Execute regression commands (`aud terraform provision`, `aud full`, `aud summary`, `aud fce`) against Terraform fixtures to confirm database-first behavior.
- [ ] 8.3 Keep `pytest`, `ruff`, and `mypy --strict` green across new modules.
