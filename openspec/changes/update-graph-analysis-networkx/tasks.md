## 0. Verification (SOP v4.20 alignment)
- [x] 0.1 Confirmed `ARCHITECTURE.md:162` promises NetworkX-backed graph algorithms.
- [x] 0.2 Reviewed `pyproject.toml:50-78` to verify the `all` extra omits `networkx`.
- [x] 0.3 Inspected `theauditor/graph/analyzer.py:22-210` to document the manual DFS/degree implementation.
- [x] 0.4 Audited `theauditor/commands/graph.py:173-302` to show `aud graph analyze` instantiates `XGraphAnalyzer` without NetworkX.
- [x] 0.5 Noted CLI guidance in `theauditor/commands/insights.py:127` referencing NetworkX despite the missing dependency.

## 1. Implementation
- [ ] 1.1 Add `networkx` (pinned version) to `[project.optional-dependencies].all` and update any packaging notes referencing graph extras.
- [ ] 1.2 Implement `analyze_graph` via NetworkX in `theauditor/graph/analyzer.py`, including helpers to hydrate a `DiGraph` from `.pf/graphs.db`, compute cycles (`nx.simple_cycles`), centrality, and hotspot metrics.
- [ ] 1.3 Refactor `aud graph analyze` to use the new API, streamlining cycle/hotspot reporting, impact calculation, JSON emission, and dual-write meta findings without regressions.
- [ ] 1.4 Adapt summary/visualization helpers (`get_graph_summary`, meta finding formatters, insights integration) to consume the NetworkX result shape and surface any new metrics (e.g., centrality scores).
- [ ] 1.5 Update user-facing docs and CLI help (README, HOWTOUSE, `theauditor/commands/insights.py`) to describe the NetworkX dependency and the enhanced graph analysis outputs.
- [ ] 1.6 Add unit coverage for the new analyzer entry point (e.g., fixtures in `tests/graph/test_analyzer.py`) ensuring cycles/hotspots match expectations on sample graphs.

## 2. Validation
- [ ] 2.1 Run `openspec validate update-graph-analysis-networkx --strict`.
- [ ] 2.2 Execute `aud graph build` + `aud graph analyze` on the sample repo to confirm NetworkX-backed cycles/hotspots persist to `.pf/raw/graph_analysis.json` and the database.
- [ ] 2.3 Run relevant regression suites (`pytest tests/graph`, `pytest tests/utils`, `mypy theauditor/graph`, `ruff check theauditor/graph`) to ensure analyzer refactor passes existing gates.
