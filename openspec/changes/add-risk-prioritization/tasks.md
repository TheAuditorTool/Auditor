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
- [ ] 2.2 Add a CLI entry point (`aud prioritize`) that runs the scorer, accepts `--root`/`--db` options, and respects Truth Courier conventions.
- [ ] 2.3 Persist risk results to SQLite (new table keyed by `findings_consolidated.id`) and emit `.pf/raw/prioritized_findings.json` sorted by descending risk.

## 3. Pipeline & FCE Integration
- [ ] 3.1 Update `run_full_pipeline` to invoke coverage collection (switch to `aud metadata analyze` or equivalent) and run `aud prioritize` after findings generation.
- [ ] 3.2 Extend FCE ingestion to select finding IDs, join risk metadata, attach `risk_score`/coverage context to `results["all_findings"]`, and sort by risk before severity.
- [ ] 3.3 Ensure chunking/extraction modules can access the new risk metadata without regressing existing outputs.

## 4. Summary & AI Outputs
- [ ] 4.1 Enhance `aud summary` to build a combined prioritized summary (≤100 KB across ≤2 files) plus per-track capsules (`lint`, `graph`, `taint`, etc.) that reference risk data.
- [ ] 4.2 Update report/readthis orchestration so new summary files are published and discoverable by downstream agents.
- [ ] 4.3 Add automated checks (unit/integration) that validate risk ordering and file size limits for the new summaries.

## 5. Documentation & Validation
- [ ] 5.1 Document the new coverage tables, `aud prioritize` command, and summary outputs in contributor/user guides.
- [ ] 5.2 Add or update automated tests covering schema migrations, risk scoring, pipeline integration, and summary generation.
- [ ] 5.3 Run `openspec validate add-risk-prioritization --strict` plus project test suites (`pytest`, `ruff`, `mypy`) before closing the change.
