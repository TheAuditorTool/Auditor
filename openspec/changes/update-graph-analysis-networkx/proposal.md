## Why
- `ARCHITECTURE.md:162` and CLI docs advertise NetworkX-backed graph algorithms, yet `XGraphAnalyzer` still relies on bespoke DFS/degree code and the `all` extra omits the dependency.
- Custom traversal logic diverges from the project’s “avoid heuristics” directive, leaving cycle detection, hotspot ranking, and downstream metrics inconsistent with the documented guarantees.
- Aligning the analyzer with NetworkX unlocks the richer graph metrics promised to users (centrality, cycle enumeration, shortest paths) and removes a widening gap between courier outputs and published behaviour.

## What Changes
- Add `networkx` to the `[project.optional-dependencies].all` extra so `pip install -e ".[all]"` satisfies the documented requirement.
- Build a NetworkX-backed analysis entry point (`analyze_graph`) inside `theauditor/graph/analyzer.py` that hydrates a `DiGraph` from `.pf/graphs.db`, runs cycle detection (`nx.simple_cycles`), degree/centrality metrics, and returns structured results consumable by CLI and insights modules.
- Refactor `aud graph analyze` to call the new analyzer API, relay cycles/hotspots/impact data sourced from NetworkX, and persist both the JSON courier artefact and dual-write findings exactly as today.
- Extend supporting utilities (meta findings formatter, summary builder) so they accept the NetworkX result shape and can surface additional metrics (e.g., betweenness centrality, strongly connected component counts) without regressions.
- Update docs/help text that mention NetworkX to clarify installation behaviour and the new insights unlocked by the integration.

## Impact
- Restores parity between documentation, optional dependency lists, and runtime behaviour, preventing user confusion when enabling advanced graph analysis.
- Produces more reliable cycle and hotspot detection for large repositories by leveraging NetworkX’s optimized algorithms rather than home-grown traversal.
- Establishes a foundation for future graph features (shortest paths, community detection, centrality-based impact) with minimal incremental effort.

## Verification Alignment
- Evidence gathered in `openspec/changes/update-graph-analysis-networkx/verification.md` per SOP v4.20.
