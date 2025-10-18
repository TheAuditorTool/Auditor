## ADDED Requirements
### Requirement: NetworkX Powers Dependency Analysis
The core graph analyzer MUST construct its dependency graph with NetworkX and rely on NetworkX algorithms for cycle and hotspot detection.

#### Scenario: Analyze Graph Builds NetworkX DiGraph
- **GIVEN** `.pf/graphs.db` contains rows in `nodes` and `edges` from `aud graph build`
- **WHEN** `theauditor/graph/analyzer.py:analyze_graph` is invoked with the database path
- **THEN** it hydrates a `networkx.DiGraph` with one node per `nodes.id` and directed edges for each import relationship
- **AND** it returns cycles sourced from `nx.simple_cycles` plus hotspot metrics using NetworkX degree/centrality scores.

#### Scenario: Hotspot Ranking Uses NetworkX Metrics
- **GIVEN** a graph where multiple modules share high connectivity
- **WHEN** `analyze_graph` computes hotspots
- **THEN** each hotspot entry includes the node id and its NetworkX-derived centrality/degree scores
- **AND** results are ordered by the NetworkX metric (descending) rather than custom heuristics.

### Requirement: Graph Analyze Command Emits NetworkX Findings
The `aud graph analyze` CLI MUST call the NetworkX-backed analyzer, persist the structured results, and surface them to downstream consumers.

#### Scenario: CLI Persists NetworkX Analysis
- **GIVEN** a user runs `aud graph analyze`
- **WHEN** the command completes successfully
- **THEN** it writes the analyzer results (cycles, hotspots, summary) to `.pf/raw/graph_analysis.json`
- **AND** dual-writes equivalent meta findings into `.pf/repo_index.db` using the NetworkX output payload.

#### Scenario: CLI Output Reflects NetworkX Metrics
- **GIVEN** `aud graph analyze` detects cycles via NetworkX
- **WHEN** the CLI prints cycle information
- **THEN** it reports counts and largest cycle sizes derived from `nx.simple_cycles`, ensuring the output matches the NetworkX result structure.

### Requirement: NetworkX Distributed via All Extra
The optional dependency bundle that unlocks advanced graph analysis MUST install NetworkX.

#### Scenario: `.[all]` Installs NetworkX
- **GIVEN** a user runs `pip install -e ".[all]"`
- **WHEN** pip resolves extras from `pyproject.toml`
- **THEN** the resolver includes a pinned `networkx` requirement so the analyzer can import it without manual steps.
