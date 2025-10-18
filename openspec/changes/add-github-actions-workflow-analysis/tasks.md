
## 0. Verification
- [ ] Re-confirm `repo_index` schema lacks GitHub Actions tables before implementation (see `verification.md` evidence).
- [ ] Capture representative real-world workflow samples the extractor must satisfy.

## 1. Schema & Indexer
- [ ] Add `github_*` table definitions to `theauditor/indexer/schema.py` with indexes for workflow/job/step lookups.
- [ ] Extend `DatabaseManager` batching/insertion logic to handle the new tables.
- [ ] Implement `GitHubWorkflowExtractor` that safely parses `.github/workflows/**` and writes directly to the database.
- [ ] Wire the extractor into the registry and ensure `aud index` stats include workflow counts.

## 2. CLI & Pipeline
- [ ] Create `theauditor/commands/workflows.py` with `analyze` (and optional `export`) subcommands that emit DB-backed JSON plus courier chunks.
- [ ] Register the command in `theauditor/cli.py` and insert `"workflows analyze"` into Stage 2 of `theauditor/pipelines.py`.
- [ ] Ensure pipeline status/log output enumerates the new phase and artifacts appear in `.pf/allfiles.md`.

## 3. Analysis Rules & Correlation
- [ ] Add `theauditor/rules/github_actions/` with rule modules covering untrusted checkout, secret exposure to mutable actions, and tainted outputs.
- [ ] Register GitHub-specific taint sources/sinks (e.g., outputs feeding `run`) so rules can query flow evidence.
- [ ] Update FCE aggregation to include workflow-derived findings and correlation clusters.

## 4. Outputs & Documentation
- [ ] Define `.pf/raw/github_workflows.json` (and related capsules) schema, enforcing provenance metadata.
- [ ] Update README/HOWTOUSE/ARCHITECTURE help to describe workflow modeling and CLI usage.
- [ ] Refresh CLI help for `aud`, `aud workflows`, and pipeline docs with new stage details.

## 5. Testing & Validation
- [ ] Expand schema contract tests to cover `github_*` tables.
- [ ] Add extractor unit tests with varied workflow fixtures (matrix, reusable workflow, secrets usage).
- [ ] Add CLI/pipeline smoke tests asserting JSON output and pipeline stage execution.
- [ ] Add rule/FCE tests exercising the high-value vulnerability scenarios outlined in the proposal.
