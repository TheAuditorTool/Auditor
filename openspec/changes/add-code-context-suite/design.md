# Design: Code Context Command Suite

## Verification Summary (SOP v4.20)
- `theauditor/commands/context.py:17` defines the current `aud context` Click command and `_extract_semantic_chunks` enforces the 65 KB chunk threshold at `theauditor/commands/context.py:251`.
- Chunk limits (`max_chunk_size=56320`, `max_chunks_per_file=3`) live in `theauditor/config_runtime.py:33-68`, and the reusable courier helper `_chunk_large_file` is implemented in `theauditor/extraction.py:28-120`.
- Repository facts already exist in SQLite: `theauditor/indexer/database.py` provisions `files` (line 184), `api_endpoints` (221), `compose_services` (352), `function_call_args` (446), and `frameworks` (586); graph relationships are stored through `theauditor/graph/store.py:22-87`.
- Coverage metrics are exported to `.pf/raw/coverage_analysis.json` by `theauditor/indexer/metadata_collector.py:381`, and taint flows are persisted to `.pf/raw/taint_analysis.json` via `theauditor/commands/taint.py:312` (no dedicated table exists yet).
- The `theauditor/` package currently has no `context/` module, so the new builder can be introduced without conflicting imports (verified via repository listing).

## Goals
1. Refactor `aud context` into a Click group while keeping the YAML-driven semantic analyzer available under `aud context semantic`.
2. Provide factual presets (overview, target, symbol, route, cross-stack, and full) sourced from `.pf/repo_index.db`, `.pf/graphs.db`, and existing JSON couriers—never re-running analysis.
3. Emit raw and chunked outputs through the courier pipeline with machine-readable provenance for every fact.
4. Publish AI-focused CLI help and documentation that highlight preset usage and direct database query examples.

## CLI Restructuring
- Convert the root command in `theauditor/commands/context.py` into `@click.group(invoke_without_command=True)`.
- Add a `semantic` subcommand that wraps the current implementation so `aud context --file` (and `aud context semantic`) continue to work.
- Introduce a new `code` subcommand (either in the same module or `theauditor/commands/context_code.py`) and register it with `context.add_command(code, name="code")`.
- Update `theauditor/cli.py` so top-level help advertises the context group and its presets.

## CodeContextBuilder
Create `theauditor/context/code_context.py` containing a `CodeContextBuilder` class with the following responsibilities:

```python
class CodeContextBuilder:
    def __init__(self, root: Path):
        self.root = root
        self.pf_dir = root / ".pf"
        self.repo_db = sqlite3.connect(self.pf_dir / "repo_index.db")
        self.repo_db.row_factory = sqlite3.Row
        self.graph_db = sqlite3.connect(self.pf_dir / "graphs.db")
        self.graph_db.row_factory = sqlite3.Row
        self.raw_dir = self.pf_dir / "raw"
```

- `validate_inputs()` → ensure both `.pf/repo_index.db` and `.pf/graphs.db` exist; raise `click.UsageError` with remediation steps (`aud full`) if either is missing.
- `build_overview()` →
  - Query `files` for language/extension and LOC counts.
  - Read `frameworks`, `package_configs`, and `refs` (entrypoints) for platform summaries.
  - Pull container/service data from `compose_services` when available.
  - Use graph import edges (`edges` with `graph_type='import'`) to highlight top hotspots; fall back gracefully if no graph data exists.
  - Include optional coverage anchors sourced from `.pf/raw/coverage_analysis.json` when present.
- `build_target(path, max_depth, limit)` →
  - Collect inbound/outbound import and call edges from `edges` (`graph_type='import'` and `'call'`).
  - Join with `symbols`, `function_call_args`, and `function_returns` for richer linkage data.
  - Attach taint paths touching the file from `.pf/raw/taint_analysis.json` if that courier exists.
- `build_symbol(symbol_name, max_depth, limit)` →
  - Resolve the defining file (`symbols`).
  - Load callers/callees from call graph edges and gather return metadata from `function_returns`.
- `build_route(route_pattern, limit)` →
  - Query `api_endpoints` for matching routes and methods.
  - Map handlers to implementation files, then reuse call/import lookups to show upstream/downstream code and services.
- `build_cross_stack()` → join `vue_components` (if present), `api_endpoints`, `compose_services`, and relevant import edges to illustrate front-end ↔ API ↔ infrastructure chains.
- `build_full(presets)` → orchestrate the requested presets (overview, cross-stack, hotspots, optional targets/routes/symbols) into a single payload.

Each fact must be emitted as a structure containing the fact text/data plus a provenance block such as:

```json
{
  "fact": "services/payments.py imports services/common.py",
  "provenance": {
    "source": "graphs.db",
    "table": "edges",
    "graph_type": "import",
    "row_id": 1523
  }
}
```

Store the builders’ SQLite connections behind context managers so CLI commands can close them cleanly.

## Output Strategy
- Raw files: `.pf/raw/context_overview.json`, `.pf/raw/context_target_<slug>.json`, `.pf/raw/context_symbol_<slug>.json`, `.pf/raw/context_route_<slug>.json`, `.pf/raw/context_cross_stack.json`, and `.pf/raw/context_full.json`.
- Chunking: call `_chunk_large_file` from `theauditor.extraction` so chunk sizes respect runtime limits from `load_runtime_config()`.
- Metadata: include command invocation, generated timestamp, and explicit source lists (e.g., `repo_index.db`, `graphs.db`, `taint_analysis.json`, `coverage_analysis.json`).

## Help & Examples
- `aud context --help` should list the `semantic` and `code` subcommands, call out default behaviour, and show quick-start usage.
- `aud context code --help` must document:
  - Preset flags (`--overview`, `--target PATH`, `--symbol NAME`, `--route PATTERN`, `--cross-stack`, `--full`).
  - Options such as `--max-depth` and `--limit`.
  - Output locations for raw and chunked files.
  - Runnable examples, e.g.:

```bash
python - <<'PY'
import sqlite3, json
conn = sqlite3.connect('.pf/repo_index.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    'SELECT path, ext, loc FROM files ORDER BY loc DESC LIMIT 5'
).fetchall()
print(json.dumps([dict(r) for r in rows], indent=2))
PY
```

```bash
sqlite3 .pf/graphs.db "SELECT source, target, type FROM edges WHERE graph_type='call' LIMIT 10;"
```

## Testing Plan
1. **Unit tests** (`tests/unit/context/test_code_context_builder.py`)
   - Use in-memory SQLite fixtures seeded with representative rows; verify each builder method returns the right structure and provenance.
2. **Integration tests** (`tests/integration/test_context_code.py`)
   - Provide fixture `.pf` directories with sample databases and JSON couriers; execute the presets and assert raw + chunk outputs exist with provenance.
3. **CLI help snapshots**
   - Capture `aud context --help` and `aud context code --help` output and compare to golden files.
4. **Chunking regression**
   - Ensure generated chunk files respect `max_chunk_size` and `max_chunks_per_file` from `load_runtime_config()`.

## Error Handling
- Missing databases → raise `click.UsageError` instructing users to run `aud full`.
- Optional artifacts absent (taint or coverage) → include warnings in metadata while still returning other sections.
- Invalid `--target`, `--symbol`, or `--route` → surface empty sections with explanatory metadata rather than aborting.

## Compatibility
- `aud context --file foo.yaml` remains functional via the `semantic` subcommand.
- No schema migrations are required; all queries operate on existing tables and courier files.

## Follow-Up
- After implementation and validation, prepare the SOP C-4.20 completion report for the Auditor review.
