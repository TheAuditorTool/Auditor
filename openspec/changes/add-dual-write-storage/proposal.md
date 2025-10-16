## Why
- Downstream tooling still reparses `.pf/raw/*.json` even though the analyzer pipeline already writes facts into `findings_consolidated`, wasting I/O and drifting from the Truth Courier model.
- Verified pain points:
  - `theauditor/fce.py:526`/`:545`/`:561`/`:576` reload graph/CFG/churn/coverage JSON instead of querying the database.
  - `theauditor/commands/summary.py:120`-`160` depends on the same JSON payloads.
  - `theauditor/rules/dependency/update_lag.py:53` only understands `.pf/raw/deps_latest.json`.
  - `theauditor/commands/context.py:181` has no database persistence for semantic classifications.
  - `theauditor/commands/deps.py:196` produces per-package freshness in JSON only.
  - `theauditor/fce.py:1340`/`:1350` outputs correlation data exclusively to JSON.
- Without a DB-first consumption path, AI agents and future automation must juggle courier files, defeating the purpose of the SQLite manifest.

## What Changes
- Extend `findings_consolidated` with a `details_json` column plus an index on `(tool, rule)` so analyzers can attach structured payloads without spawning bespoke tables.
- Introduce a normalized `dependency_freshness` table for per-package latest-version snapshots (manager/workspace/package scoped).
- Update producers to write their artifacts into the database:
  - `aud deps --check-latest` populates `dependency_freshness` and emits freshness findings.
  - `aud context` records semantic classifications and run summaries as findings.
  - Graph/CFG/churn/coverage/taint writers populate `details_json` using their existing `additional_info` payloads.
  - `aud fce` persists correlation/failure payloads in the database rather than JSON-only files.
- Refactor consumers to rely entirely on SQL:
  - `aud fce` and `aud summary` hydrate hotspots, complexity, churn, coverage, taint, dependency freshness, and correlations from the database only.
  - `update_lag` rule queries `dependency_freshness` instead of JSON.
  - Remove JSON fallback logic after the DB loaders land.
- Update documentation to make the DB-first contract explicit and describe the migration path.

## Impact
- Eliminates redundant JSON parsing in FCE, summary, and rules, restoring the database as the single authoritative source.
- Enables future context features and autonomous agents to operate purely from SQLite, aligning with the Truth Courier architecture.
- Adds a targeted table (`dependency_freshness`) and one column on `findings_consolidated`, minimizing schema sprawl while capturing the missing data.

## Verification Alignment
- Verification evidence recorded in `openspec/changes/add-dual-write-storage/verification.md` per SOP v4.20.
- Architecture adjustments (DB-first consumers, explicit schema changes) logged in `design.md` for review.
