## 0. Verification (SOP v4.20 alignment)
- [x] 0.1 Reviewed `theauditor/commands/context.py` to confirm the existing semantic-only Click command and chunking helper.
- [x] 0.2 Reviewed `theauditor/config_runtime.py`, `theauditor/extraction.py`, and `theauditor/indexer/metadata_collector.py` to confirm courier limits and JSON couriers.
- [x] 0.3 Reviewed `theauditor/indexer/database.py` and `theauditor/graph/store.py` to catalogue available tables for overview, route, and cross-stack data.
- [x] 0.4 Noted that detailed taint flows live in `.pf/raw/taint_analysis.json` (no database table yet) and must be treated as courier evidence.

## 1. Implementation
- [ ] 1.1 Refactor `theauditor/commands/context.py` into a Click group, exposing the legacy semantic analyzer via a `semantic` subcommand and adding a new `code` subcommand.
- [ ] 1.2 Implement `theauditor/context/code_context.py` with `CodeContextBuilder`, validating `.pf/repo_index.db` / `.pf/graphs.db` existence and providing overview/target/symbol/route/cross-stack/full builders.
- [ ] 1.3 Wire CLI presets (`--overview`, `--target`, `--symbol`, `--route`, `--cross-stack`, `--full`) to call the builder, enforce depth/limit options, and ensure provenance metadata is attached to every fact.
- [ ] 1.4 Emit raw outputs to `.pf/raw/context_*.json` and reuse `theauditor.extraction._chunk_large_file` so chunked files honour `load_runtime_config()` limits.
- [ ] 1.5 Update CLI help (`theauditor/cli.py`, `theauditor/commands/context.py`) and docs (README, HOWTOUSE) with AI-focused guidance and runnable SQLite/Python examples.
- [ ] 1.6 Add unit and integration tests for builder methods, preset orchestration, chunking behaviour, and help text snapshots.

## 2. Validation
- [ ] 2.1 Run `openspec validate add-code-context-suite --strict`.
- [ ] 2.2 Execute `aud context --help`, `aud context code --help`, `aud context code --full`, and `aud --help` to confirm messaging and command wiring.
- [ ] 2.3 Run `pytest tests/integration/test_context_code.py`, `ruff check .`, and `mypy theauditor --strict`.
