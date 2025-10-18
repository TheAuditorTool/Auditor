# Tasks: Restore CLI Truth Courier Mode

## 0. Verification
- [x] Read `teamsop.md`, `README.md`, and `openspec/AGENTS.md` for protocol alignment.
- [x] Reproduce `aud --help` failure and capture the `ASTExtractorMixin` import error.
- [x] Confirm stale flag references and missing commands in `theauditor/cli.py`.
- [x] Identify prescriptive messaging in taint, refactor, docker, and deps commands.

## 1. Implementation
- [ ] Restore `ASTExtractorMixin` exports so CLI bootstrap succeeds.
- [ ] Replace hard-coded help tables with introspection-driven output and refresh quick-start snippets.
- [ ] Remove prescriptive messaging from CLI commands while keeping factual payloads intact.
- [ ] Introduce regression utilities (`scripts/check_cli_help.py`, truthy formatter helper).

## 2. Quality
- [ ] Add CLI import smoke test and help rendering assertions.
- [ ] Add output keyword guard tests for taint, refactor, docker, deps commands.
- [ ] Run `openspec validate update-cli-truth-mode --strict`.
