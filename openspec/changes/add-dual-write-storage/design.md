# Design: Database-First Analysis Consumers

## Verification Summary (SOP v4.20)
- `openspec/changes/add-dual-write-storage/verification.md` captures the full hypothesis/evidence log.
- Existing analyzers (graph, CFG, churn, coverage, taint) already push meta facts into `findings_consolidated` via `DatabaseManager.write_findings_batch`; JSON files remain only for courier copies.
- Consumers (FCE, summary, dependency rules) continue to reload `.pf/raw/*.json`, so the performance gap sits on the reader side, not the writers.
- Producers without a database surface: semantic context classifications, dependency latest-version comparisons, and FCE correlation payloads.
- Schema contract (`theauditor/indexer/schema.py`, `theauditor/indexer/database.py`) is the single source of truth. Any new column/table must be declared there—no lazy creation or runtime divergence.

## Architectural Direction
1. Treat `findings_consolidated` as the canonical warehouse for analyzer output.
   - Extend the table with an optional `details_json` column so structured payloads travel with each finding.
   - Update `DatabaseManager.write_findings_batch` to persist the new column and normalize existing payloads (meta findings already include `additional_info`).
   - Add an index on `(tool, rule)` to keep queries fast for high-volume datasets.
2. Remove JSON fallbacks from consumers once the database path is available.
   - `theauditor/fce.py` will hydrate hotspots, complexity, churn, coverage, taint, and correlation data via SQL queries filtered on `tool`/`rule` values.
   - `theauditor/commands/summary.py` will mirror the FCE query strategy so summary generation never reopens `.pf/raw/*.json`.
   - `theauditor/rules/dependency/update_lag.py` will query package freshness data from the database instead of `.pf/raw/deps_latest.json`.
3. Only introduce new schema where no existing table can express the data.
   - Per-package freshness snapshots do not fit into `package_configs` (one row per manifest), so add a single normalized table `dependency_freshness` keyed by package identifier (manager + workspace + name).
   - Semantic context runs can map to `findings_consolidated` entries (one per classification) with `details_json` capturing pattern id, severity, and suggested replacement; an aggregated run record can live in `details_json` with `rule='SEMANTIC_CONTEXT_RUN'`.
   - FCE correlations can emit `findings_consolidated` entries with `tool='fce-correlation'` and `details_json` storing evidence IDs.

## Schema Changes
- Update `theauditor/indexer/schema.py`:
  - Add `details_json` (TEXT, nullable) to `findings_consolidated` plus `idx_findings_tool_rule` on `(tool, rule)`.
  - Define new table `dependency_freshness` with columns `(id INTEGER PRIMARY KEY, manager TEXT, workspace TEXT, package TEXT, locked_version TEXT, latest_version TEXT, latest_published TEXT, source TEXT, status TEXT, checked_at TEXT)`, unique on `(manager, workspace, package)`.
- Update `DatabaseManager.create_schema` to add the new column and table, including `ALTER TABLE` migration for existing databases (mirrors existing `api_endpoints` migration pattern).
- Extend `write_findings_batch` to accept an optional `details_json` value (defaults to `'{}'`).

## Producer Updates
1. **Dependency check (`theauditor/commands/deps.py`)**
   - After `check_latest_versions`, upsert rows into `dependency_freshness` and emit `findings_consolidated` entries (rule `DEPENDENCY_OUTDATED`/`DEPENDENCY_CURRENT`) with details about `locked`, `latest`, `delta`, and any errors.
2. **Semantic context (`theauditor/commands/context.py`)**
   - Convert each classification item into a finding (`SEMANTIC_OBSOLETE`, `SEMANTIC_TRANSITIONAL`, `SEMANTIC_CURRENT`) with `details_json` capturing pattern id, rule message, and migration metadata.
   - Emit an aggregated run summary finding (`SEMANTIC_CONTEXT_RUN`) containing totals so downstream tools can determine migration progress without reopening JSON.
3. **FCE correlations (`theauditor/fce.py`)**
   - After generating `meta_findings`, `factual_clusters`, and `path_clusters`, create corresponding `findings_consolidated` entries with `tool='fce-correlation'`, storing the assembled evidence in `details_json`.
4. **Existing producers (graph/cfg/churn/coverage/taint)**
   - Populate the new `details_json` field using their existing `additional_info` payloads so consumers have structured data to query.

## Consumer Updates
1. **FCE**
   - Replace JSON readers with targeted SQL queries, e.g., `SELECT file, line, message, details_json FROM findings_consolidated WHERE tool='graph-analysis' AND rule='ARCHITECTURAL_HOTSPOT'`.
   - Introduce lightweight data loaders that deserialize `details_json` into the prior Python structures.
   - Remove the code paths that fall back to `.pf/raw/*.json`.
2. **Summary command**
   - Mirror the FCE loaders to source hotspots, complexity, churn, coverage, taint, and dependency freshness directly from the database.
   - Drop the JSON parsing logic.
3. **Dependency rule (`update_lag`)**
   - Query `dependency_freshness` for outdated packages (e.g., `status='outdated'`) instead of parsing `deps_latest.json`.

## Migration Plan
- Schema migration handled inside `create_schema`:
  - `ALTER TABLE findings_consolidated ADD COLUMN details_json TEXT DEFAULT '{}'` guarded for existing installations.
  - `CREATE TABLE IF NOT EXISTS dependency_freshness ...`.
  - Create new index `idx_findings_tool_rule` if missing.
- Provide CLI guidance (`aud index --rebuild` or dedicated migration command) to refresh databases created before this change.

## Testing Strategy
- Unit tests for `write_findings_batch` covering the new `details_json` path and ensuring existing callers remain compatible.
- Integration tests for `aud deps --check-latest`, `aud context`, `aud graph analyze`, `aud cfg analyze`, `aud metadata churn`, and `aud fce` verifying that database rows exist with expected content and that JSON files are no longer required for FCE/summary execution.
- Regression tests for `update_lag` and summary generation to ensure they operate purely from the database.

## Rollout Considerations
- Update documentation (`ARCHITECTURE.md`, `HOWTOUSE.md`) to state that JSON files are courier copies only; the database is authoritative.
- Communicate the schema change to downstream tooling so they add support for `details_json` and `dependency_freshness` before removing JSON fallbacks.
- Monitor database size growth—`details_json` should store compact JSON to avoid ballooning the repo cache.
