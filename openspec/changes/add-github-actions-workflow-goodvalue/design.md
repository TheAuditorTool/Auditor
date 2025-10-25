
# Design - add-github-actions-workflow-analysis

## Overview
We will extend TheAuditor with a database-first representation of GitHub Actions workflows so downstream agents can reason about execution graphs, permission boundaries, and data flows. The solution plugs into existing architecture layers:

1. **Indexer extractor** parses `.github/workflows/**/*.yml` during `aud index`, normalizes the workflow graph, and writes structured rows into new SQLite tables.
2. **Pipeline/CLI command** materializes JSON capsules for AI consumption (`.pf/raw` + courier chunking) and exposes operator tooling via `aud workflows`.
3. **Rules, taint, FCE** consume the new tables to detect high-risk paths, enrich taint analysis with workflow sources/sinks, and surface correlated findings.

All components honor the Prime Directive (no heuristics/regex for YAML semantics, dual-write to DB+JSON, orchestrator compliance).

## Database Schema Extensions

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `github_workflows` | One row per workflow file | `file_path` (PK), `workflow_name`, `on_triggers` (JSON array of event specs), `raw_permissions` (JSON), `created_at` |
| `github_jobs` | Job metadata | `job_id` (PK), `workflow_path` (FK), `name`, `runs_on` (JSON list to cover matrix), `strategy` (JSON), `permissions` (JSON), `uses_reusable_workflow` (bool) |
| `github_job_dependencies` | Graph edges | Composite PK of (`job_id`, `needs_job_id`) so Stage 2 queries can traverse `needs:` |
| `github_steps` | Step-level detail | `step_id` (PK), `job_id` (FK), `sequence_order`, `name`, `uses_action`, `uses_version`, `run_script`, `shell`, `env_vars` (JSON), `with_args` (JSON), `timeout_minutes` |
| `github_step_outputs` | Normalized outputs declared by a step | `step_id`, `output_name`, `expression` |
| `github_step_references` | Parsed `${{ }}` references gathered from `run`, `env`, and `with` | `step_id`, `reference_type` (`env`, `needs`, `steps`, `secrets`), `reference_key`, `reference_path` |

Implementation details:
- **Schema contracts** will be added to `theauditor/indexer/schema.py` with matching `TableSchema` entries and indexes on `workflow_path`, `job_id`, and reference columns to accelerate queries.
- **DatabaseManager** gains batch lists plus `add_github_*` helpers invoked by the extractor. Inserts follow existing transaction batching conventions.
- Permissions/env columns store canonical JSON (not strings) so downstream consumers can run `json_extract` queries.

## Extractor Integration
- Introduce `GitHubWorkflowExtractor` under `theauditor/indexer/extractors/github_actions.py`.
- The extractor registers `.yml`/`.yaml` but uses `should_extract` to match only under `.github/workflows/`.
- YAML parsing uses `yaml.safe_load_all` with explicit handling for anchors/matrices. We normalize the following:
  - Expand `strategy.matrix` into arrays stored in `github_jobs.strategy`.
  - Capture `outputs`, `env`, `with`, `permissions`, `timeout-minutes`.
  - Record `${{ github.event.* }}` and `${{ steps.xyz.outputs.foo }}` references into `github_step_references`.
- The extractor writes directly to the database via the new `DatabaseManager` API (database-first, no intermediate dicts). It returns empty dicts so the indexer's existing pipeline remains unaffected.

## CLI & Pipeline
- Add `theauditor/commands/workflows.py` (Click group) with:
  - `aud workflows analyze` - validates DB prerequisites, summarizes counts, and writes `.pf/raw/github_workflows.json`.
  - `aud workflows export --workflow <path>` - optional targeted export for a single workflow (future-proofing).
- Both subcommands output provenance metadata (table/row identifiers) to maintain courier truth.
- Update `theauditor/cli.py` to register the new group, and refresh help text to mention workflow analysis.
- Insert `("workflows", ["analyze"])` into `command_order` in `theauditor/pipelines.py` right after metadata (Stage 2). Stage mapping ensures workflows run after indexing but before taint/rules.
- Extend pipeline status reporting to include the new phase name and ensure artifacts appear in `.pf/pipeline.log`.

## JSON & Courier Outputs
- `aud workflows analyze` writes:
  - `.pf/raw/github_workflows.json` - containing workflow/job/step nodes, dependency edges, and references list.
  - `.pf/raw/github_workflow_findings.json` - optional precomputed risk signals (e.g., secrets to unpinned actions) for agents.
  - Courier chunking to `.pf/readthis/github_workflows_*.json` via `theauditor.extraction` helpers (reuse `_chunk_large_file`).
- Payload structure includes:
  ```json
  {
    "workflow": "ci.yml",
    "trigger": ["pull_request_target"],
    "jobs": [
      {
        "job_id": "build",
        "runs_on": ["ubuntu-latest"],
        "needs": ["setup"],
        "steps": [
          {
            "name": "Checkout",
            "uses": "actions/checkout",
            "version": "v4",
            "env": {"GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}"},
            "references": [{"type": "secrets", "key": "GITHUB_TOKEN"}]
          }
        ]
      }
    ]
  }
  ```
- Each artefact lists `provenance` arrays referencing table names and primary keys.

## Rules & Taint Integration
- Create `theauditor/rules/github_actions/` with rules such as:
  - **Untrusted Checkout** - query workflows triggered by `pull_request_target` where an early step uses `actions/checkout` with `ref` pointing to PR head before a validation job.
  - **Unpinned Secret Usage** - flag steps with `uses_action` referencing mutable tags (`main`, `master`, `v1`) while exposing secrets/environment values.
  - **Output-to-run injection** - detect when a step's `run_script` references `${{ needs.*.outputs.* }}` sourced from jobs consuming PR data.
- Rules obtain taint assistance by registering new sources in `register_taint_patterns` with pseudo-language `github`. For instance, treat `github_step_outputs.reference_type == 'pull_request'` as source and `run_script` as sink.
- Findings write into `findings_consolidated` with `tool="github-actions-rules"` to keep FCE integration simple.

## FCE Enhancements
- Extend `run_fce` to:
  - Load workflow risk findings (both rules + JSON summary).
  - Join them with taint paths to elevate severity for correlated chains (e.g., tainted PR title -> workflow run step referencing it).
  - Surface new correlation clusters like `github_workflow_secret_leak`.
- Update JSON outputs `fce.json` / `fce_failures.json` to list workflow correlations.

## Testing & Validation
- Schema contract tests: extend `tests/test_schema_contract.py` with new table validations.
- Indexer unit tests: add fixtures under `tests/indexer/github_actions/` containing representative workflows (matrix, reusable workflows, PR triggers).
- Command tests: extend `tests/test_cli_full.py` (or similar) to assert `.pf/raw/github_workflows.json` is produced after full run.
- Rule tests: create targeted tests verifying new findings for dangerous patterns.
- End-to-end pipeline smoke test: ensure new stage executes and artifacts exist.

## Documentation & Help Updates
- Update `README.md` / `HOWTOUSE.md` sections covering pipeline phases to mention GitHub Actions modeling.
- Add a section in `ARCHITECTURE.md` explaining the workflow schema and how agents can query it (example SQL for `github_jobs`).
- Extend CLI help strings for `aud workflows` and `aud full` to surface the new capability prominently.

## Rollout Considerations
- Ensure migration path: when `aud index` runs against existing databases, the schema validator should prompt re-index if GitHub tables are missing.
- Backwards compatibility: other modules must tolerate empty GitHub tables if workflows are absent.
- Performance: caching results for repeated workflows (hash file content) to avoid redundant inserts when YAML unchanged.
