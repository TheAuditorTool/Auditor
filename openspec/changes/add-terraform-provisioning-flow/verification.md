# Verification Report - add-terraform-provisioning-flow
Generated: 2025-10-16T12:18:43.6239747+07:00
SOP Reference: Standard Operating Procedure v4.20

## Hypotheses & Evidence

1. Terraform/HCL files are not currently indexed or parsed.
   - Evidence: `theauditor/indexer/config.py:128` lists `SUPPORTED_AST_EXTENSIONS` limited to Python and JS/TS extensions; no `.tf`/`.hcl` entries.
   - Evidence: `theauditor/indexer/extractors/__init__.py:196` only discovers extractors for existing languages; directory listing (2025-10-16) shows no Terraform module under `theauditor/indexer/extractors/`.
   - Result: ✓ Terraform resources are invisible to the indexer today.

2. The SQLite manifest has no schema for Terraform constructs or IaC data flow.
   - Evidence: `theauditor/indexer/schema.py` contains 100+ table definitions yet `rg "terraform" theauditor/indexer/schema.py` returns no hits.
   - Evidence: `theauditor/indexer/database.py:84-276` initializes batch lists with no Terraform-related buffers or insert routines.
   - Result: ✓ There is no persistence surface for Terraform resources, variables, or graph edges.

3. The audit pipeline and CLI do not orchestrate any Terraform analysis stage.
   - Evidence: `theauditor/pipelines.py` references phases for index/workset/graph/taint/deps/etc.; `rg "terraform" theauditor/pipelines.py` returns zero results.
   - Evidence: `theauditor/cli.py:112-205` registers commands (index, graph, docker, metadata, etc.) with no Terraform command group.
   - Result: ✓ The pipeline cannot schedule Terraform ingestion or analysis.

4. Downstream consumers (rules, FCE, reports) have no Terraform awareness.
   - Evidence: `theauditor/rules/` tree lacks any Terraform/IaC category; orchestrator discovery (`theauditor/rules/orchestrator.py:55-224`) finds nothing Terraform-specific.
   - Evidence: `theauditor/fce.py:1-770` aggregates database-backed findings but never queries Terraform tables (none exist) and relies on application-centric sources only.
   - Result: ✓ No rule or correlation layer can reason about Terraform configurations.

5. The project dependencies do not include an HCL parser.
   - Evidence: `pyproject.toml:15-63` lists runtime dependencies without `python-hcl2` or Tree-sitter HCL bindings.
   - Result: ✓ A structural parser must be introduced to satisfy the "no regex" directive.

## Discrepancies & Alignment Notes
- Initial assumption that a rudimentary Terraform parser might exist in the generic extractor was disproven; GenericExtractor only targets Docker/compose artifacts and lacks `.tf` handling entirely.
- No latent IaC hooks were found inside the pipeline or FCE, so the new capability must define end-to-end plumbing (ingest → persistence → analysis → reporting).
- The absence of an HCL dependency confirms we must vendor or add one rather than extending Tree-sitter support inline.

## Conclusion
Terraform manifests are completely outside the current Truth Courier pipeline: the indexer ignores `.tf` files, the database has no storage contract, the pipeline lacks an execution phase, and downstream analysis engines have nothing to query. Implementing Terraform provisioning flow capture therefore requires new parser dependencies, indexer extractors, schema extensions, pipeline orchestration, and FCE/rule integration to uphold the project’s database-first guarantees.
