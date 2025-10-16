## 0. Verification (SOP v4.20 alignment)
- [x] 0.1 Capture hypotheses, evidence, and discrepancies in `openspec/changes/add-dual-write-storage/verification.md`.
- [x] 0.2 Log architecture corrections (DB-first, no lazy schema) inside `design.md` for architect review.
- [x] 0.3 Read `theauditor/indexer/schema.py`, `theauditor/indexer/database.py`, and `theauditor/taint/database.py` to confirm existing data flows and constraints.

## 1. Schema & Persistence
- [ ] 1.1 Extend `findings_consolidated` with a nullable `details_json` column and add `idx_findings_tool_rule` on `(tool, rule)`.
- [ ] 1.2 Create normalized `dependency_freshness` table (manager, workspace, package, locked_version, latest_version, status, checked_at, metadata).
- [ ] 1.3 Update `DatabaseManager.write_findings_batch` to persist `details_json` without breaking existing callers.
- [ ] 1.4 Wire migrations inside `DatabaseManager.create_schema` (ALTER TABLE + new index/table creation) and add CLI guidance for reindexing.

## 2. Producer Updates
- [ ] 2.1 Update `theauditor/commands/deps.py` to populate `dependency_freshness` and emit findings for each package status.
- [ ] 2.2 Update `theauditor/commands/context.py` (and related helpers) to emit semantic findings + run summary into `findings_consolidated` with structured details.
- [ ] 2.3 Extend graph/CFG/churn/coverage/taint writers to pass structured payloads into the new `details_json` column.
- [ ] 2.4 Emit FCE correlation and failure artifacts through `findings_consolidated` (no standalone JSON-only payloads).

## 3. Consumer Refactors
- [ ] 3.1 Refactor `theauditor/fce.py` to load hotspots, complexity, churn, coverage, taint, and correlations from the database only.
- [ ] 3.2 Refactor `theauditor/commands/summary.py` to mirror the database loaders and drop JSON parsing.
- [ ] 3.3 Update `theauditor/rules/dependency/update_lag.py` to query `dependency_freshness` instead of `.pf/raw/deps_latest.json`.
- [ ] 3.4 Delete JSON fallback paths and associated tests/config knobs once DB reads are in place.

## 4. Documentation & Guidance
- [ ] 4.1 Refresh `ARCHITECTURE.md`/`HOWTOUSE.md` to describe the DB-first workflow and the new schema elements.
- [ ] 4.2 Document migration instructions (e.g., `aud index --rebuild`) and expected DB footprints.

## 5. Validation
- [ ] 5.1 Run `openspec validate add-dual-write-storage --strict`.
- [ ] 5.2 Execute affected commands (`aud deps --check-latest`, `aud context`, `aud graph analyze`, `aud cfg analyze`, `aud metadata churn`, `aud metadata coverage`, `aud taint-analyze`, `aud fce`, `aud summary`) and confirm database-powered flows succeed without JSON.
- [ ] 5.3 Run test matrix / linting (`pytest`, `ruff`, `mypy`) for impacted modules.
