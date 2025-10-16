## Why
- GitHub Actions workflows control supply-chain security, yet `.github/workflows/*.yml` are invisible to TheAuditor's SQLite manifest (`verification.md` confirms the gap).
- High-impact workflow exploits stem from execution order, permission boundaries, and data propagation between jobs and steps, all of which require structured graphs instead of ad-hoc string scans.
- Downstream agents (rules, taint, FCE, AI clients) need workflow truth in the same database/JSON dual-write model as other capabilities to run automated checks without bespoke parsing.

## What Changes
- Extend the indexer with a YAML-backed extractor that loads `.github/workflows/**` files, normalizes triggers/jobs/steps, and persists them into new tables (`github_workflows`, `github_jobs`, `github_job_dependencies`, `github_steps`, plus normalized IO tables).
- Teach `DatabaseManager`/schema contracts about the new tables, including JSON columns for permissions/env/output maps and indexes that support job/step traversal queries.
- Add a dedicated `aud workflows` command (with subcommands for `analyze`/`export`) that reads the DB, writes `.pf/raw/github_workflows.json`, hydrates `.pf/readthis/github_workflows_*.json`, and emits provenance metadata; register it with Stage 2 of the full pipeline.
- Introduce a `rules/github_actions` package with orchestrator-compliant rules that query the new tables to detect permission escalation paths, untrusted checkout sequences, and unpinned third-party actions; register taint sources and sinks for step outputs feeding shell execution.
- Enhance the Factual Correlation Engine to consume workflow-derived findings by joining GitHub tables with existing taint/graph data, folding the results into consolidated correlation output.
- Document helper queries and examples in CLI help and architecture docs so downstream producers/consumers can leverage the new schema without guessing.

## Impact
- Surfaces GitHub Actions supply-chain risks alongside code/taint findings, enabling compound correlation (for example, compromised action plus secret exposure).
- Establishes a reusable workflow graph model that downstream automations can query, paving the way for new rules without reprocessing YAML.
- Keeps the project's database-first conventions intact, avoiding ad-hoc parsers and ensuring orchestrator/template compliance for agents.

## Verification Alignment
- Evidence and gaps captured in `openspec/changes/add-github-actions-workflow-analysis/verification.md`.
- Tasks and design sections will reference the same sources to maintain Prime Directive traceability.
