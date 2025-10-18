## 0. Verification (SOP v4.20 alignment)
- [ ] 0.1 Record hypotheses, evidence, and discrepancies in `verification.md` before implementation.
- [ ] 0.2 Review `theauditor/indexer/schema.py`, `theauditor/indexer/database.py`, and `theauditor/indexer/metadata_collector.py` to confirm current coverage handling.
- [ ] 0.3 Capture pipeline/FCE/summary behavior (ordering, outputs) to baseline regression checks.

## 1. Coverage Persistence Schema
- [ ] 1.1 Declare `test_coverage_summary`, `test_coverage_gaps`, and supporting indexes in `theauditor/indexer/schema.py` and `DatabaseManager.create_schema`.
- [ ] 1.2 Add maintenance hooks so `DatabaseManager.clear_tables` and migration helpers reset the new coverage tables safely.
- [ ] 1.3 Update `MetadataCollector.collect_coverage` to dual-write coverage summaries and uncovered-line rows via new database APIs (while still emitting JSON).

## 2. Risk Prioritization Module
- [ ] 2.1 Implement a coverage-aware risk scorer (e.g., `theauditor/risk_prioritizer.py`) that normalizes severity and computes `risk_score = severity_weight * (1 - coverage_ratio)`.
- [ ] 2.2 Add a CLI entry point (`aud prioritize`) under `theauditor/commands/prioritize.py` that runs the scorer, accepts `--root`/`--db` options, and respects Truth Courier conventions.
- [ ] 2.3 Persist risk results to SQLite (new table keyed by `findings_consolidated.id`), emit `.pf/raw/prioritized_findings.json`, and mirror a trimmed `.pf/risk_scores.json` summary sorted by descending risk.
- [ ] 2.4 Update `theauditor/docgen.py` and CLI help text so the new command appears in generated documentation.

## 3. Pipeline & FCE Integration
- [ ] 3.1 Update `run_full_pipeline` (`theauditor/pipelines.py`) to invoke `aud metadata analyze` (coverage + churn) and schedule `aud prioritize` in Stage 3B before FCE.
- [ ] 3.2 Extend FCE ingestion to join `finding_risk_scores`, attach risk metadata to `results["all_findings"]`, update sorting, and surface risk telemetry in logs.
- [ ] 3.3 Refresh extraction/chunking modules so `.pf/readthis/` lists the prioritized files and per-track capsules ahead of raw outputs.

## 4. Summary & AI Outputs
- [ ] 4.1 Enhance `aud summary` to build `summary_prioritized_combined.json` (≤100 KB) plus `summary_prioritized_overflow.json` when needed, embedding risk metadata.
- [ ] 4.2 Generate per-track capsules (`summary_lint_top_risk.json`, `summary_graph_top_risk.json`, `summary_import_top_risk.json`, `summary_taint_top_risk.json`, etc.) that reference DB tables and keep payloads bounded.
- [ ] 4.3 Update extraction/report publishing to include the combined summary and capsules in `.pf/readthis/manifest.json`.
- [ ] 4.4 Add automated checks (unit/integration) that validate risk ordering, file size limits, and capsule item caps.

## 5. Documentation & Validation
- [ ] 5.1 Document the new coverage tables, `aud prioritize` command, and summary outputs in contributor/user guides.
- [ ] 5.2 Add or update automated tests covering schema migrations, risk scoring, pipeline integration, and summary generation.
- [ ] 5.3 Run `openspec validate add-risk-prioritization --strict` plus project test suites (`pytest`, `ruff`, `mypy`) before closing the change.
