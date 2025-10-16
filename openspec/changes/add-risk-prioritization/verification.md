# Verification Report - add-risk-prioritization
Generated: 2025-10-16T05:59:11+00:00
SOP Reference: Standard Operating Procedure v4.20

## Hypotheses & Evidence

1. Coverage facts already persist in SQLite for downstream consumers.
   - Evidence: `theauditor/indexer/database.py:827`-`840` defines `findings_consolidated` but no coverage tables.
   - Evidence: `theauditor/indexer/metadata_collector.py:329`-`348` only writes low-coverage meta findings via `write_findings_batch` before exiting.
   - Result: FALSE — coverage metrics live only in JSON outputs and derived meta findings.

2. The full pipeline collects coverage data by default.
   - Evidence: `theauditor/pipelines.py:421`-`434` schedules `aud metadata churn` but never invokes the coverage subcommand.
   - Result: FALSE — coverage analysis is skipped during `aud full`, leaving the database empty.

3. FCE already accounts for coverage when organizing findings.
   - Evidence: `theauditor/fce.py:75`-`87` sorts findings in SQL purely by severity.
   - Evidence: `theauditor/fce.py:1293`-`1306` normalizes severity and delegates to `sort_findings` without referencing coverage.
   - Result: FALSE — prioritization ignores coverage context entirely.

4. Existing summaries provide an AI-sized prioritized overview.
   - Evidence: `theauditor/commands/summary.py:16`-`226` aggregates counts and emits a single monolithic JSON report with no risk ordering or size guardrails.
   - Result: FALSE — copilots must load large raw chunks to identify high-risk work.

## Discrepancies & Alignment Notes
- Coverage facts are limited to `.pf/raw/coverage_analysis.json`; there is no normalized schema or ingestion path for coverage percentages or uncovered lines.
- Pipeline orchestration skips coverage entirely, so risk scoring would default to "untested" for every finding without new integration.
- FCE and downstream chunking rely on severity-only ordering, meaning well-tested critical findings can overshadow untested ones.
- Summary generation must be redesigned to emit bounded-size, risk-aware documents for AI consumption.

## Conclusion
The repository lacks database-backed coverage metrics, a risk scoring stage, and AI-sized prioritized outputs. Delivering the scoped changes will persist coverage facts, add a coverage-aware prioritization command, integrate it into the pipeline and FCE, and generate right-sized summaries for downstream agents.
