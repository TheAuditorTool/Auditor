## Overview
- Replace the bespoke DFS/degree implementation in `theauditor/graph/analyzer.py` with a NetworkX-backed engine while keeping the courier/insights separation intact.
- Ensure `aud graph analyze` and downstream consumers (meta findings, visualizer, FCE) consume the new structure without losing dual-write guarantees.

## Current State
- `XGraphAnalyzer` builds adjacency lists manually, runs custom DFS for cycle detection, and calculates connectivity counts without NetworkX (`theauditor/graph/analyzer.py:22-210`).
- The CLI (`theauditor/commands/graph.py:173-302`) calls the manual helpers, formats hotspots via ad-hoc degree counts, and dual-writes outputs.
- The `all` optional dependency set in `pyproject.toml:50-78` omits NetworkX even though docs advertise it.
- Meta finding formatters in `theauditor/utils/meta_findings.py` expect hotspot dicts with `id`, `in_degree`, `out_degree`, `total_connections` fields.

## Target State
- Introduce `analyze_graph(db_path: str) -> dict` that:
  - Hydrates a `networkx.DiGraph` from `XGraphStore` data.
  - Uses `nx.simple_cycles`, `nx.degree_centrality`, and optional centrality metrics to produce cycles/hotspots.
  - Returns structured payloads (cycles list, hotspots list, summary stats) compatible with dual-write logic.
- Update `aud graph analyze` to:
  - Require NetworkX via the new helper (fail with actionable error if missing).
  - Persist results to JSON/SQLite using the same schema but enriched metrics (e.g., centrality scores).
  - Keep impact analysis path (workset) functional—either convert existing traversal to NetworkX or adapt helpers to interoperate with the new DiGraph.
- Ensure meta findings and visualizer functions can read the enhanced hotspot/cycle data without regressions (may require shims to preserve legacy keys).
- Add NetworkX to `[project.optional-dependencies].all` with a pinned version that matches supported Python.

## Key Decisions
1. **NetworkX Version Pin**: Target `networkx==3.2.1` (compatible with Python 3.11/3.12) to avoid unexpected API drift.
2. **Data Hydration Source**: Prefer using `XGraphStore` fetchers for nodes/edges over direct SQL so analyzer stays decoupled from DB internals.
3. **Hotspot Metric**: Combine degree centrality (`nx.degree_centrality`) with raw in/out degree counts to maintain backward-compatible fields while surfacing richer metrics.
4. **Impact Analysis**: Retain existing BFS-based traversal for impact or reimplement using NetworkX shortest paths depending on complexity; initial plan is to wrap the helper so callers can still rely on deterministic results.
5. **Fallback Behaviour**: If NetworkX missing, CLI should instruct user to install `pip install -e ".[all]"` rather than silently skipping analysis.

## Verification & Testing
- Unit tests for `analyze_graph` covering:
  - Cycle detection on a known cycle graph.
  - Hotspot ranking ordering based on degree centrality.
  - Summary stats accuracy (node/edge counts, density).
- CLI integration tests to ensure JSON output and database writes succeed post-refactor.
- Static analysis (`mypy`, `ruff`) across `theauditor/graph` to confirm type signatures remain valid.
- Manual smoke on sample repo: `aud graph build`, `aud graph analyze`, `aud summary` to verify no regressions in downstream consumers.
