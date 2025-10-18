# Verification Report - add-code-context-suite
Generated: 2025-10-15T19:45:00+07:00
SOP Reference: Standard Operating Procedure v4.20

## Hypotheses & Evidence

1. `aud context` is currently a single Click command dedicated to semantic flows.
   - Evidence: `theauditor/commands/context.py:17` declares `@click.command(name="context")` with the legacy semantic workflow only.
   - Evidence: `_extract_semantic_chunks` lives in the same file and enforces a 65 KB chunk threshold at `theauditor/commands/context.py:251`.

2. Chunking defaults and courier helpers already exist.
   - Evidence: `theauditor/config_runtime.py:33-68` defines `max_chunk_size=56320` and `max_chunks_per_file=3` under `DEFAULTS["limits"]`.
   - Evidence: `_chunk_large_file` in `theauditor/extraction.py:28-120` provides the reusable courier chunker used by other commands.

3. Repository structure data is persisted in SQLite.
   - Evidence: `theauditor/indexer/database.py` creates tables for `files` (184), `api_endpoints` (221), `compose_services` (352), `function_call_args` (446), and `frameworks` (586).
   - Evidence: Graph relationships are saved through `theauditor/graph/store.py:22-87`, which defines the `nodes` and `edges` tables in `.pf/graphs.db`.

4. Coverage and taint artifacts remain JSON-backed.
   - Evidence: `theauditor/indexer/metadata_collector.py:381` writes coverage results to `.pf/raw/coverage_analysis.json`.
   - Evidence: `theauditor/commands/taint.py:312` calls `save_taint_analysis` to persist `.pf/raw/taint_analysis.json`; there is no `taint_paths` table in the current schema.

5. There is no existing `theauditor/context` package, so the new builder can be introduced without conflicting modules.
   - Evidence: Repository listing under `theauditor/` contains no `context/` directory (checked via `Get-ChildItem theauditor`).

## Discrepancies & Alignment Notes
- Taint flow details only exist in the JSON payload today; the builder must read from `.pf/raw/taint_analysis.json` until a database table exists.
- Coverage percentages likewise come from JSON, so provenance must cite the courier artifact instead of repo_index tables.

## Conclusion
The codebase already exposes the necessary SQLite schemas, courier chunking utilities, and raw JSON artifacts needed by the new context presets. Work will focus on reorganising the CLI and wiring queries around the existing truth sources without introducing speculative data.
