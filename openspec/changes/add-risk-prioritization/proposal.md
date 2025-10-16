## Why
- Coverage metrics currently live only in `.pf/raw/coverage_analysis.json` and low-coverage meta findings; there is no schema entry for querying coverage facts in SQLite (`theauditor/indexer/database.py:807`-`836`, `theauditor/indexer/metadata_collector.py:333`-`351`).
- The full pipeline never calls the coverage collector, so `.pf/repo_index.db` is missing quality data during an `aud full` run (`theauditor/pipelines.py:416`-`437`).
- FCE and downstream consumers sort findings purely by normalized severity, ignoring whether the affected code is untested (`theauditor/fce.py:75`-`87`, `theauditor/fce.py:1287`-`1306`).
- The audit summary aggregates counts only; copilots must ingest megabytes of raw chunks to discover what matters (`theauditor/commands/summary.py:15`-`200`).

## What Changes
- Extend the schema with normalized coverage summary and gap tables plus a risk score table keyed by `findings_consolidated.id`; teach `MetadataCollector.collect_coverage` to dual-write coverage facts into SQLite alongside the existing JSON output.
- Implement a risk prioritization module/CLI (`aud prioritize`) that normalizes severities, hydrates coverage for each finding, computes `risk_score = severity_weight * (1 - coverage_ratio)` (treat uncovered lines as zero coverage), and persists both SQLite rows and `.pf/raw/prioritized_findings.json`.
- Integrate coverage collection and the new prioritization command into Stage 3 of `run_full_pipeline`, wire `aud prioritize` into `command_order`, and update FCE to hydrate risk metadata, expose it in `results["all_findings"]`, and sort by risk before severity.
- Enhance `aud summary` and report chunking to emit a combined prioritized summary (≤100 KB across at most two files) plus per-track capsules (`lint summary`, `graph summary`, `import summary`, `taint summary`, and other analyzers) that list the top risk items while pointing back to the database for full detail.
- Extend the extraction/manifest pipeline so `.pf/readthis/` publishes the new prioritized documents alongside existing capsules, guaranteeing downstream AI agents can load risk-first facts without scraping raw megabyte-scale outputs.

## Impact
- Restores a database-first contract for coverage facts so risk analysis and future insights can query SQLite instead of reparsing JSON.
- Gives humans and copilots a deterministic, coverage-aware priority queue that surfaces untested critical findings before well-tested noise.
- Reduces AI context waste by delivering right-sized summaries while preserving `.pf/raw` artifacts for full fidelity review.
- Establishes a foundation for additional risk heuristics (churn weighting, exploitability) by centralizing risk metadata in the database.

## Verification Alignment
- Hypotheses, evidence, and discrepancies captured in `openspec/changes/add-risk-prioritization/verification.md` per SOP v4.20.
- Task list front-loads schema verification and requires regression coverage for pipeline, FCE, and summary flows before completion.
