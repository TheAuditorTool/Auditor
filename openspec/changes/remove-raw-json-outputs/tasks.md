## 0. Verification

- [ ] 0.1 Grep all `.pf/raw/` references in codebase
- [ ] 0.2 Identify all `json.dump()` file writers to `.pf/raw/`
- [ ] 0.3 Map commands to their current output behavior (--json flag exists? --output flag? --write flag?)
- [ ] 0.4 Verify no external consumers depend on `.pf/raw/` files

## 1. Remove File Writers

- [ ] 1.1 `vulnerability_scanner.py`: Remove `_save_report()` and `.pf/raw/vulnerabilities.json` writes
- [ ] 1.2 `commands/docker_analyze.py`: Remove JSON file write, add `--json` flag
- [ ] 1.3 `commands/graph.py`: Remove `.pf/raw/graph_analysis.json`, `.pf/raw/graph_summary.json` writes, add `--json` to `analyze` subcommand
- [ ] 1.4 `commands/detect_frameworks.py`: Remove `.pf/raw/frameworks.json` write, add `--json` flag
- [ ] 1.5 `commands/deps.py`: Remove `.pf/raw/deps.json`, `deps_latest.json` writes, add `--json` flag
- [ ] 1.6 `commands/cfg.py`: Remove `--output` flag and `.pf/raw/cfg_analysis.json` write, add `--json` flag
- [ ] 1.7 `commands/terraform.py`: Remove `.pf/raw/terraform_*.json` writes, add `--json` to subcommands
- [ ] 1.8 `commands/workflows.py`: Remove `.pf/raw/github_workflows.json` write, add `--json` flag
- [ ] 1.9 `commands/metadata.py`: Remove `.pf/raw/churn_*.json`, `coverage_*.json` writes, add `--json` flag
- [ ] 1.10 `commands/context.py`: Remove `.pf/raw/semantic_context_*.json` write
- [ ] 1.11 `commands/deadcode.py`: Remove JSON file write if present
- [ ] 1.12 `commands/refactor.py`: Remove JSON report write
- [ ] 1.13 `linters/linters.py`: Remove `.pf/raw/lint.json` write
- [ ] 1.14 `indexer/metadata_collector.py`: Remove JSON file writes

## 2. Remove/Modify Flags

- [ ] 2.1 `commands/fce.py`: Remove `--write` flag entirely
- [ ] 2.2 `commands/taint.py`: Remove `--output` flag, keep `--json` flag
- [ ] 2.3 `commands/graph.py`: Remove `--out-json` and `--out` flags
- [ ] 2.4 `commands/cfg.py`: Remove `--output` flag
- [ ] 2.5 `commands/metadata.py`: Remove `--output` flags from subcommands
- [ ] 2.6 `commands/terraform.py`: Remove `--output` flags from subcommands
- [ ] 2.7 `commands/workflows.py`: Remove `--output` flag

## 3. Update Pipeline

- [ ] 3.1 `commands/full.py`: Remove raw file counting from summary output
- [ ] 3.2 `commands/full.py`: Remove `.pf/raw/` directory creation if present
- [ ] 3.3 `commands/full.py`: Update output messaging

## 4. Update Archive Command

- [ ] 4.1 `commands/_archive.py`: Remove `.pf/raw/` from archive logic

## 5. Update Help Text

- [ ] 5.1 `commands/manual_lib01.py`: Remove all `.pf/raw/` references from help strings
- [ ] 5.2 `commands/manual_lib02.py`: Remove all `.pf/raw/` references from help strings
- [ ] 5.3 Update any docstrings referencing `.pf/raw/` in modified files

## 6. FCE Engine

- [ ] 6.1 `fce/engine.py`: Remove `write_fce_report()` function or make it internal-only

## 7. GraphQL Builder

- [ ] 7.1 `graph/graphql/builder.py`: Remove schema/execution JSON file writes if going to `.pf/raw/`

## 8. Testing

- [ ] 8.1 Run `aud full --offline` and verify no `.pf/raw/` directory created
- [ ] 8.2 Test each modified command with `--json` flag
- [ ] 8.3 Verify commands still produce correct stdout output
- [ ] 8.4 Run smoke tests

## 9. Cleanup

- [ ] 9.1 Delete any existing `.pf/raw/` directory in dev environment
- [ ] 9.2 Add `.pf/raw/` to `.gitignore` as safety (prevents accidental commits if old code runs)
