# Verification Report - add-dual-write-storage
Generated: 2025-10-15T19:05:00+07:00
SOP Reference: Standard Operating Procedure v4.20

## Hypotheses & Evidence

1. Graph, CFG, churn, coverage, and taint producers already dual-write meta findings into `findings_consolidated`.
   - Evidence: `theauditor/commands/graph.py:301` batches hotspots/cycles into `DatabaseManager.write_findings_batch` before emitting JSON.
   - Evidence: `theauditor/commands/cfg.py:202` formats complexity findings and writes them via `write_findings_batch`.
   - Evidence: `theauditor/indexer/metadata_collector.py:143`/`:322` formats churn and coverage findings and persists them with the same API.
   - Evidence: `theauditor/commands/taint.py:288` pushes normalized taint findings into the database.
   - Result: ✅ Database already contains structured facts for these analyzers.

2. Consumers still favor JSON payloads even when equivalent findings exist in the database.
   - Evidence: `theauditor/fce.py:526`/`:545`/`:561`/`:576` reopen `.pf/raw/*_analysis.json` instead of querying `findings_consolidated`.
   - Evidence: `theauditor/commands/summary.py:120`-`160` loads the same JSON artifacts to build its report.
   - Result: ✅ Consumer-side work is the real gap.

3. Semantic context classifications are only exported to `.pf/raw/semantic_context_*.json`.
   - Evidence: `theauditor/commands/context.py:181` invokes `context.export_to_json` with no database write path.
   - Evidence: `theauditor/insights/semantic_context.py:602` has no persistence hook beyond JSON.
   - Result: ✅ Need a database surface for classifications.

4. Dependency latest-version comparisons live exclusively in `.pf/raw/deps_latest.json`.
   - Evidence: `theauditor/commands/deps.py:196` writes the JSON payload via `write_deps_latest_json`.
  - Evidence: `theauditor/rules/dependency/update_lag.py:53` loads the same file and never queries the database.
   - Result: ✅ Latest-version data requires a schema-backed store.

5. FCE correlation outputs remain JSON-only.
   - Evidence: `theauditor/fce.py:1340`/`:1350` serialize correlations and failures to `.pf/raw/fce*.json` with no call to `write_findings_batch`.
   - Result: ✅ Correlation facts need database persistence.

6. Schema changes must flow through the central registry—no lazy table creation.
   - Evidence: `theauditor/indexer/schema.py:1-70` defines the contract and forbids ad-hoc tables elsewhere.
   - Evidence: `theauditor/indexer/database.py:177-615` enumerates every `CREATE TABLE` statement; runtime "IF MISSING" additions are disallowed.
   - Result: ✅ Any new structure must be defined in `schema.py` and `database.py` together.

## Discrepancies & Alignment Notes
- Initial assumption that analyzers lacked DB writes was incorrect for graph/CFG/churn/coverage/taint. The dual-write gap is primarily on consumers plus semantic context, dependency freshness, and FCE correlation storage.
- `findings_consolidated` already acts as the normalized hub for meta-analysis; augmenting it (e.g., new columns for structured JSON) is preferable to spawning bespoke tables per feature.
- Any new schema must be declared in `theauditor/indexer/schema.py` and wired in `DatabaseManager.create_schema`—no lazy `CREATE TABLE` calls during command execution.

## Conclusion
The repository already captures most analysis outputs in `findings_consolidated`; the priority is to retire JSON-first readers (FCE, summary, rules) and to extend persistence for the remaining producers (semantic context, dependency freshness, FCE correlations). Upcoming design revisions will focus on leveraging the existing schema contract, adding minimal extensions where absolutely necessary, and removing JSON fallbacks once the database paths are in place.
