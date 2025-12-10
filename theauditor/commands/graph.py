"""Cross-project dependency and call graph analysis."""

import json
import sqlite3
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console


def _normalize_path_filter(path_filter: tuple, extra_paths: tuple = ()) -> str | None:
    """Normalize path filter - handle shell expansion and convert wildcards to SQL LIKE.

    When shell expands 'frontend/*' into multiple paths, we extract the common prefix.
    Converts glob wildcards (*, **) to SQL LIKE wildcards (%).
    """
    # Combine --path values and any shell-expanded extra arguments
    all_paths = list(path_filter) + list(extra_paths)
    if not all_paths:
        return None

    if len(all_paths) == 1:
        path = all_paths[0]
    else:
        # Shell expanded the glob - extract common prefix
        paths = [p.replace("\\", "/") for p in all_paths]
        if paths:
            prefix_parts = paths[0].split("/")
            common_parts = []
            for i, part in enumerate(prefix_parts):
                if all(p.split("/")[i] == part if len(p.split("/")) > i else False for p in paths):
                    common_parts.append(part)
                else:
                    break
            path = "/".join(common_parts) + "/" if common_parts else ""
        else:
            return None

    # Normalize path separators and wildcards
    path = path.replace("\\", "/")
    path = path.replace("**", "%").replace("*", "%").replace("?", "_")
    if not path.endswith("%") and not path.endswith("/"):
        path += "%"
    elif path.endswith("/"):
        path += "%"
    return path


@click.group(cls=RichGroup)
@click.help_option("-h", "--help")
def graph():
    """Dependency and call graph analysis for architecture understanding and impact assessment.

    Group command for building and analyzing import/call graphs from indexed codebases. Detects
    circular dependencies, architectural hotspots, change impact radius, and hidden coupling.
    Supports Python, JavaScript/TypeScript with graph database backend for complex queries.

    AI ASSISTANT CONTEXT:
      Purpose: Analyze code architecture via dependency and call graphs
      Input: .pf/repo_index.db (code index)
      Output: .pf/graphs.db (graph database), visualizations
      Prerequisites: aud full (populates refs and calls tables)
      Integration: Architecture reviews, refactoring planning, impact analysis
      Performance: ~5-30 seconds (graph construction + analysis)

    SUBCOMMANDS:
      build:   Construct import and call graphs from indexed code
      analyze: Detect cycles, hotspots, architectural anti-patterns
      query:   Interactive graph relationship queries (who uses/imports X?)
      viz:     Generate visual representations (DOT, SVG, interactive HTML)

    GRAPH TYPES:
      Import Graph: File-level dependencies (who imports what)
      Call Graph:   Function-level dependencies (who calls what)
      Combined:     Multi-level analysis (files + functions)

    INSIGHTS PROVIDED:
      - Circular dependencies (import cycles breaking modular design)
      - Architectural hotspots (modules with >20 dependencies)
      - Change impact radius (blast radius for modifications)
      - Hidden coupling (indirect dependencies via intermediaries)

    TYPICAL WORKFLOW:
      aud full
      aud graph build
      aud graph analyze
      aud graph query --uses auth.py

    EXAMPLES:
      aud graph build
      aud graph analyze --workset
      aud graph query --uses database
      aud graph viz --format dot --out-dir ./output/

    PERFORMANCE:
      Small (<100 files):  ~2-5 seconds
      Medium (500 files):  ~10-20 seconds
      Large (2K+ files):   ~30-60 seconds

    RELATED COMMANDS:
      aud impact    # Uses graph for change impact analysis
      aud deadcode  # Uses graph for isolation detection
      aud full      # Populates refs/calls tables

    NOTE: Graph commands use separate graphs.db database (not repo_index.db).
    This is an optimization for complex graph traversal queries.

    EXAMPLE:
      aud graph query --calls api.send_email # What does send_email call?

    OUTPUT:
      .pf/graphs.db                   # SQLite database with graphs
      Use --json for analysis output  # Pipe to file if needed

    See: aud manual graph, aud manual callgraph, aud manual dependencies
    """
    pass


@graph.command("build", cls=RichCommand)
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--langs", multiple=True, help="Languages to process (e.g., python, javascript)")
@click.option("--workset", help="Path to workset.json to limit scope")
@click.option("--batch-size", default=200, type=int, help="Files per batch")
@click.option("--resume", is_flag=True, help="Resume from checkpoint")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path for output graphs")
@click.option("--repo-db", default="./.pf/repo_index.db", help="Repo index database for file list")
def graph_build(root, langs, workset, batch_size, resume, db, repo_db):
    """Build import and call graphs from indexed codebase.

    Constructs two graph types from the indexed database for architectural analysis,
    cycle detection, and impact measurement. Supports incremental builds and workset
    filtering for large codebases.

    AI ASSISTANT CONTEXT:
      Purpose: Construct dependency and call graphs from indexed code
      Input: .pf/repo_index.db (refs and calls tables from 'aud full')
      Output: .pf/graphs.db (import_nodes, import_edges, call_nodes, call_edges)
      Prerequisites: aud full (populates refs and calls tables)
      Integration: Required before 'aud graph analyze' or 'aud graph query'
      Performance: ~5-30 seconds depending on codebase size

    GRAPH TYPES:
      Import Graph (File-level):
        - Nodes: Files and modules
        - Edges: Import/require relationships
        - Use: Circular dependency detection, module structure analysis

      Call Graph (Function-level):
        - Nodes: Functions and methods
        - Edges: Call relationships (who calls what)
        - Use: Execution path tracing, dead code detection

    EXAMPLES:
      aud graph build                         # Full codebase
      aud graph build --langs python          # Python only
      aud graph build --workset workset.json  # Specific files
      aud graph build --resume                # Resume interrupted build

    OUTPUT FILES:
      .pf/graphs.db - SQLite database containing:
        - import_nodes: Files and modules
        - import_edges: Import relationships
        - call_nodes: Functions and methods
        - call_edges: Call relationships

    FLAG INTERACTIONS:
      --workset + --langs: Analyze specific files in specific languages only
      --resume: Safe to use after interrupted builds (preserves partial progress)
      --batch-size: Larger = faster but more memory (default 200)

    TROUBLESHOOTING:
      "No database found" error:
        -> Run 'aud full' first to build the repo_index.db

      Graph build very slow (>10 minutes):
        -> Increase --batch-size to 500
        -> Use --workset for subset analysis

      Missing edges in graph:
        -> Expected: only static imports captured
        -> Dynamic imports/conditional requires not detected

      Memory errors during build:
        -> Reduce --batch-size to 100 or 50

    RELATED COMMANDS:
      aud full            Build the repo_index.db first
      aud graph analyze   Detect cycles and hotspots from built graph
      aud graph query     Query relationships in the graph

    See: aud manual graph, aud manual callgraph, aud manual dependencies"""
    from theauditor.graph.builder import XGraphBuilder
    from theauditor.graph.store import XGraphStore

    try:
        builder = XGraphBuilder(batch_size=batch_size, exclude_patterns=[], project_root=root)
        store = XGraphStore(db_path=db)

        workset_files = set()
        if workset:
            workset_path = Path(workset)
            if workset_path.exists():
                with open(workset_path, encoding="utf-8") as f:
                    workset_data = json.load(f)

                    workset_files = {p["path"] for p in workset_data.get("paths", [])}
                    console.print(
                        f"Loaded workset with {len(workset_files)} files", highlight=False
                    )

        if not resume and builder.checkpoint_file.exists():
            builder.checkpoint_file.unlink()

        file_list = None
        repo_db_path = Path(repo_db)
        if repo_db_path.exists():
            console.print("Loading files from repo_index.db...")
            conn = sqlite3.connect(str(repo_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT path, sha256, ext, bytes, loc FROM files")
            all_files = [
                {"path": row[0], "sha256": row[1], "ext": row[2], "bytes": row[3], "loc": row[4]}
                for row in cursor.fetchall()
            ]
            conn.close()

            if workset_files:
                file_list = [f for f in all_files if f.get("path") in workset_files]
                console.print(f"  Filtered to {len(file_list)} files from workset", highlight=False)
            else:
                file_list = all_files
                console.print(f"  Found {len(file_list)} files in database", highlight=False)
        else:
            console.print(
                f"[error]ERROR: {repo_db} not found. Run 'aud full' first.[/error]", highlight=False
            )
            raise click.Abort()

        console.print("Building import graph...")
        import_graph = builder.build_import_graph(
            root=root,
            langs=list(langs) if langs else None,
            file_list=file_list,
        )

        store.save_import_graph(import_graph)

        console.print(f"  Nodes: {len(import_graph['nodes'])}", highlight=False)
        console.print(f"  Edges: {len(import_graph['edges'])}", highlight=False)

        console.print("Building call graph...")
        call_graph = builder.build_call_graph(
            root=root,
            langs=list(langs) if langs else None,
            file_list=file_list,
        )

        store.save_call_graph(call_graph)

        console.print(f"  Functions: {len(call_graph.get('nodes', []))}", highlight=False)
        console.print(f"  Calls: {len(call_graph.get('edges', []))}", highlight=False)

        console.print(f"\nGraphs saved to database: {db}", highlight=False)

    except Exception as e:
        console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e


@graph.command("build-dfg", cls=RichCommand)
@click.option("--root", default=".", help="Root directory")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--repo-db", default="./.pf/repo_index.db", help="Repo index database")
def graph_build_dfg(root, db, repo_db):
    """Build data flow graph from indexed assignments and returns.

    Constructs a data flow graph (DFG) showing how data flows through variable
    assignments and function returns. Essential for taint analysis and tracking
    how user input propagates through the codebase.

    AI ASSISTANT CONTEXT:
      Purpose: Build data flow graph for tracking variable assignments
      Input: .pf/repo_index.db (assignments and function_return_sources tables)
      Output: .pf/graphs.db (nodes/edges with graph_type='data_flow')
      Prerequisites: aud full (populates assignment_sources, function_return_sources)
      Integration: Used by taint analysis for data propagation tracking
      Performance: ~5-20 seconds depending on assignment count

    DATA FLOW TRACKING:
      Assignment Flow:
        - Tracks: x = y (x gets value from y)
        - Captures: variable-to-variable assignments
        - Uses: assignment_sources junction table

      Return Flow:
        - Tracks: return value propagation
        - Captures: which variables influence function returns
        - Uses: function_return_sources junction table

    EXAMPLES:
      aud graph build-dfg                  # Build DFG from current project

    OUTPUT:
      .pf/graphs.db with graph_type='data_flow':
        - nodes: Variables and return values
        - edges: Assignment and return relationships

    STATISTICS SHOWN:
      - Total assignments processed
      - Assignments with source variables (tracked edges)
      - Edges created
      - Total nodes (unique variables)

    TROUBLESHOOTING:
      "No database found" error:
        -> Run 'aud full' first to build repo_index.db

      Very few edges created:
        -> Expected for simple variable assignments (x = 5)
        -> DFG tracks variable-to-variable flow only

      Missing data flow edges:
        -> Complex expressions may not be fully tracked
        -> Only direct assignments captured

    RELATED COMMANDS:
      aud full            Build the repo_index.db first
      aud taint   Uses DFG for taint propagation
      aud graph build     Build import/call graphs (separate from DFG)

    See: aud manual graph, aud manual taint"""
    from pathlib import Path

    from theauditor.graph.dfg_builder import DFGBuilder
    from theauditor.graph.store import XGraphStore

    try:
        repo_db_path = Path(repo_db)
        if not repo_db_path.exists():
            console.print(
                f"[error]ERROR: {repo_db} not found. Run 'aud full' first.[/error]", highlight=False
            )
            raise click.Abort()

        console.print("Initializing DFG builder...")
        builder = DFGBuilder(db_path=repo_db)
        store = XGraphStore(db_path=db)

        console.print("Building data flow graph...")

        graph = builder.build_unified_flow_graph(root)

        stats = graph["metadata"]["stats"]
        console.print("\nData Flow Graph Statistics:")
        console.print("  Assignment Stats:")
        console.print(
            f"    Total assignments: {stats['assignment_stats']['total_assignments']:,}",
            highlight=False,
        )
        console.print(
            f"    With source vars:  {stats['assignment_stats']['assignments_with_sources']:,}",
            highlight=False,
        )
        console.print(
            f"    Edges created:     {stats['assignment_stats']['edges_created']:,}",
            highlight=False,
        )
        console.print("  Return Stats:")
        console.print(
            f"    Total returns:     {stats['return_stats']['total_returns']:,}", highlight=False
        )
        console.print(
            f"    With variables:    {stats['return_stats']['returns_with_vars']:,}",
            highlight=False,
        )
        console.print(
            f"    Edges created:     {stats['return_stats']['edges_created']:,}", highlight=False
        )
        console.print("  Totals:")
        console.print(f"    Total nodes:       {stats['total_nodes']:,}", highlight=False)
        console.print(f"    Total edges:       {stats['total_edges']:,}", highlight=False)

        console.print(f"\nSaving to {db}...", highlight=False)
        store.save_data_flow_graph(graph)

        console.print(f"Data flow graph saved to {db}", highlight=False)

    except FileNotFoundError as e:
        console.print(f"[error]ERROR: {e}[/error]", highlight=False)
        raise click.Abort() from e
    except Exception as e:
        console.print(f"[error]ERROR: Failed to build DFG: {e}[/error]", highlight=False)
        raise click.Abort() from e


@graph.command("analyze", cls=RichCommand)
@click.option("--root", default=".", help="Root directory")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--max-depth", default=3, type=int, help="Max traversal depth for impact analysis")
@click.option("--workset", help="Path to workset.json for change impact")
@click.option("--path", "path_filter", multiple=True, help="Filter analysis to paths matching pattern (e.g., 'src/api/%', 'frontend/*')")
@click.argument("extra_paths", nargs=-1, required=False)
def graph_analyze(root, db, max_depth, workset, path_filter, extra_paths):
    """Analyze dependency graphs for architectural issues and change impact.

    Performs comprehensive graph analysis to detect circular dependencies,
    architectural hotspots, and measure the blast radius of code changes.
    Generates health metrics and recommendations for improving codebase
    architecture.

    AI ASSISTANT CONTEXT:
      Purpose: Detect architectural issues via graph analysis
      Input: .pf/graphs.db (import and call graphs from 'aud graph build')
      Output: Console or JSON (--json), analysis results to stdout
      Prerequisites: aud full, aud graph build
      Integration: Architecture reviews, refactoring planning, impact analysis
      Performance: ~3-10 seconds (graph traversal + metrics calculation)

    ANALYSIS PERFORMED:
      Cycle Detection:
        - Identifies circular import dependencies
        - Ranks cycles by size and complexity
        - Highlights most problematic cycles

      Hotspot Ranking:
        - Finds highly connected modules (centrality metrics)
        - Identifies bottleneck components
        - Scores fragility risk

      Change Impact:
        - Calculates upstream dependencies (what depends on this)
        - Calculates downstream dependencies (what this depends on)
        - Measures total blast radius

    EXAMPLES:
      aud graph analyze
      aud graph analyze --path 'frontend/*'    # Analyze frontend only
      aud graph analyze --path 'src/api/%'     # SQL LIKE style also works
      aud graph analyze --workset workset.json
      aud graph analyze --max-depth 5
      aud graph analyze --out custom_analysis.json

    FLAG INTERACTIONS:
      --path: Filters graph to matching nodes before analysis (faster, focused)
      --workset + --max-depth: Limits impact analysis to specific files and depth

    TROUBLESHOOTING:
      No graphs found:
        -> Run 'aud graph build' first

      Slow analysis (>30 seconds):
        -> Very large graph (>10K nodes)
        -> Use --workset to analyze subset, reduce --max-depth

    RELATED COMMANDS:
      aud graph build     Build the graph database first
      aud graph query     Query specific relationships
      aud graph viz       Visualize cycles and hotspots
      aud impact          Focused change impact analysis

    See: aud manual graph, aud manual dependencies"""
    from theauditor.graph.analyzer import XGraphAnalyzer
    from theauditor.graph.store import XGraphStore

    insights = None

    try:
        store = XGraphStore(db_path=db)
        import_graph = store.load_import_graph()
        call_graph = store.load_call_graph()

        if not import_graph["nodes"]:
            console.print("No graphs found. Run 'aud graph build' first.")
            return

        # Filter by path if specified (handles shell glob expansion)
        path = _normalize_path_filter(path_filter, extra_paths)
        if path:
            import fnmatch

            path_pattern = path.replace("%", "*")  # Convert SQL LIKE to fnmatch

            def matches_path(node_id: str) -> bool:
                return fnmatch.fnmatch(node_id, path_pattern)

            original_count = len(import_graph["nodes"])
            filtered_nodes = [n for n in import_graph["nodes"] if matches_path(n["id"])]
            filtered_node_ids = {n["id"] for n in filtered_nodes}
            filtered_edges = [
                e for e in import_graph["edges"]
                if e["source"] in filtered_node_ids or e["target"] in filtered_node_ids
            ]
            import_graph = {"nodes": filtered_nodes, "edges": filtered_edges}

            # Filter call graph too
            if call_graph and call_graph.get("nodes"):
                call_filtered_nodes = [n for n in call_graph["nodes"] if matches_path(n.get("file", n["id"]))]
                call_filtered_ids = {n["id"] for n in call_filtered_nodes}
                call_filtered_edges = [
                    e for e in call_graph["edges"]
                    if e["source"] in call_filtered_ids or e["target"] in call_filtered_ids
                ]
                call_graph = {"nodes": call_filtered_nodes, "edges": call_filtered_edges}

            console.print(
                f"Filtered: {len(filtered_nodes)}/{original_count} nodes matching '{path}'",
                highlight=False
            )

        analyzer = XGraphAnalyzer()

        console.print("Detecting cycles...")
        cycles = analyzer.detect_cycles(import_graph)
        console.print(f"  Found {len(cycles)} cycles", highlight=False)
        if cycles and len(cycles) > 0:
            console.print(f"  Largest cycle: {cycles[0]['size']} nodes", highlight=False)

        hotspots = []
        if insights:
            console.print("Ranking hotspots...")
            hotspots = insights.rank_hotspots(import_graph, call_graph)
            console.print("  Top 10 hotspots:")
            for i, hotspot in enumerate(hotspots[:10], 1):
                console.print(
                    f"    {i}. {hotspot['id'][:50]} (score: {hotspot['score']})", highlight=False
                )
        else:
            console.print("Finding most connected nodes...")
            degrees = analyzer.calculate_node_degrees(import_graph)
            connected = sorted(
                [(k, v["in_degree"] + v["out_degree"]) for k, v in degrees.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:10]
            console.print("  Top 10 most connected nodes:")
            for i, (node, connections) in enumerate(connected, 1):
                console.print(f"    {i}. {node[:50]} ({connections} connections)", highlight=False)

        impact = None
        if workset:
            workset_path = Path(workset)
            if workset_path.exists():
                with open(workset_path, encoding="utf-8") as f:
                    workset_data = json.load(f)
                    targets = workset_data.get("seed_files", [])

                    if targets:
                        console.print(
                            f"\nCalculating impact for {len(targets)} targets...", highlight=False
                        )
                        impact = analyzer.impact_of_change(
                            targets=targets,
                            import_graph=import_graph,
                            call_graph=call_graph,
                            max_depth=max_depth,
                        )
                        console.print(
                            f"  Upstream impact: {len(impact['upstream'])} files", highlight=False
                        )
                        console.print(
                            f"  Downstream impact: {len(impact['downstream'])} files",
                            highlight=False,
                        )
                        console.print(
                            f"  Total impacted: {impact['total_impacted']}", highlight=False
                        )

        summary = {}
        if insights:
            console.print("\nGenerating interpreted summary...")
            summary = insights.summarize(
                import_graph=import_graph,
                call_graph=call_graph,
                cycles=cycles,
                hotspots=hotspots,
            )

            console.print(
                f"  Graph density: {summary['import_graph'].get('density', 0):.4f}", highlight=False
            )
            console.print(
                f"  Health grade: {summary['health_metrics'].get('health_grade', 'N/A')}",
                highlight=False,
            )
            console.print(
                f"  Fragility score: {summary['health_metrics'].get('fragility_score', 0):.2f}",
                highlight=False,
            )
        else:
            console.print("\nGenerating basic summary...")
            nodes_count = len(import_graph.get("nodes", []))
            edges_count = len(import_graph.get("edges", []))
            density = edges_count / (nodes_count * (nodes_count - 1)) if nodes_count > 1 else 0

            summary = {
                "import_graph": {
                    "nodes": nodes_count,
                    "edges": edges_count,
                    "density": density,
                },
                "cycles": {
                    "total": len(cycles),
                    "largest": cycles[0]["size"] if cycles else 0,
                },
            }

            if call_graph:
                summary["call_graph"] = {
                    "nodes": len(call_graph.get("nodes", [])),
                    "edges": len(call_graph.get("edges", [])),
                }

            console.print(f"  Nodes: {nodes_count}", highlight=False)
            console.print(f"  Edges: {edges_count}", highlight=False)
            console.print(f"  Density: {density:.4f}", highlight=False)
            console.print(f"  Cycles: {len(cycles)}", highlight=False)

        analysis = {
            "cycles": cycles,
            "hotspots": hotspots[:50],
            "impact": impact,
            "summary": summary,
        }

        from theauditor.indexer.database import DatabaseManager
        from theauditor.utils.findings import format_cycle_finding, format_hotspot_finding

        meta_findings = []

        for hotspot in hotspots[:50]:
            meta_findings.append(format_hotspot_finding(hotspot))

        for cycle in cycles:
            meta_findings.extend(format_cycle_finding(cycle))

        repo_db_path = Path(".pf") / "repo_index.db"
        if repo_db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(repo_db_path.resolve()))
                db_manager.write_findings_batch(meta_findings, "graph-analysis")
                db_manager.close()
                console.print(
                    f"  Wrote {len(meta_findings)} graph findings to database", highlight=False
                )
            except Exception as e:
                console.print(
                    f"[error]  Warning: Could not write findings to database: {e}[/error]",
                    highlight=False,
                )

        console.print("\n[success]Analysis complete.[/success] Use --json for machine-readable output.")

    except Exception as e:
        console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e


@graph.command("hotspots", cls=RichCommand)
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--path", "path_filter", multiple=True, help="Filter by file path pattern (e.g., 'frontend/%', 'src/api/%')")
@click.option("--top", default=20, type=int, help="Number of hotspots to show")
@click.option(
    "--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
@click.argument("extra_paths", nargs=-1, required=False)
def graph_hotspots(db, path_filter, top, output_format, extra_paths):
    """Show architectural hotspots - files with highest connectivity.

    Identifies files/modules that are most connected in the dependency graph.
    High connectivity indicates architectural importance but also potential
    fragility - changes to hotspots have wide blast radius.

    AI ASSISTANT CONTEXT:
      Purpose: Identify highly connected modules for architecture review
      Input: .pf/graphs.db (from 'aud graph build')
      Output: Ranked list of hotspots with connection counts
      Prerequisites: aud full, aud graph build
      Integration: Refactoring planning, risk assessment, code review prioritization
      Performance: <1 second (graph traversal)

    HOTSPOT METRICS:
      in_degree:  How many files depend on this file (importers)
      out_degree: How many files this file depends on (imports)
      total:      Sum of in + out (overall connectivity)

    INTERPRETATION:
      High in_degree:  Many dependents - breaking changes are risky
      High out_degree: Many dependencies - complex, hard to test in isolation
      High both:       Critical hub - requires careful maintenance

    EXAMPLES:
      aud graph hotspots                        # Top 20 hotspots
      aud graph hotspots --top 10               # Top 10 only
      aud graph hotspots --path 'frontend/%'   # Frontend files only
      aud graph hotspots --format json          # JSON for scripting

    RELATED COMMANDS:
      aud graph analyze   Full architectural analysis
      aud graph viz --view hotspots   Visual hotspot graph
      aud blueprint --hotspots        Quick hotspot overview

    See: aud manual graph, aud manual architecture"""
    from theauditor.graph.analyzer import XGraphAnalyzer
    from theauditor.graph.store import XGraphStore

    try:
        store = XGraphStore(db_path=db)
        import_graph = store.load_import_graph()
        call_graph = store.load_call_graph()

        if not import_graph.get("nodes"):
            console.print("No graphs found. Run 'aud graph build' first.", highlight=False)
            return

        # Filter by path if specified (handles shell glob expansion)
        path = _normalize_path_filter(path_filter, extra_paths)
        if path:
            import fnmatch

            path_pattern = path.replace("%", "*")  # Convert SQL LIKE to fnmatch

            def matches_path(node_id: str) -> bool:
                return fnmatch.fnmatch(node_id, path_pattern)

            filtered_nodes = [n for n in import_graph["nodes"] if matches_path(n["id"])]
            filtered_node_ids = {n["id"] for n in filtered_nodes}
            filtered_edges = [
                e for e in import_graph["edges"]
                if e["source"] in filtered_node_ids or e["target"] in filtered_node_ids
            ]
            import_graph = {"nodes": filtered_nodes, "edges": filtered_edges}

            console.print(f"Filtered to {len(filtered_nodes)} nodes matching '{path}'", highlight=False)

        analyzer = XGraphAnalyzer()
        hotspots = analyzer.identify_hotspots(import_graph, top_n=top)

        # Merge call graph data if available
        if call_graph and call_graph.get("nodes"):
            call_hotspots = analyzer.identify_hotspots(call_graph, top_n=top * 2)
            call_map = {h["id"]: h for h in call_hotspots}

            for hs in hotspots:
                if hs["id"] in call_map:
                    ch = call_map[hs["id"]]
                    hs["call_in"] = ch.get("in_degree", 0)
                    hs["call_out"] = ch.get("out_degree", 0)

        if output_format == "json":
            console.print(json.dumps(hotspots, indent=2), markup=False)
        else:
            if not hotspots:
                console.print("No hotspots found.", highlight=False)
                return

            console.print(f"\nTop {len(hotspots)} Architectural Hotspots:", highlight=False)
            console.print("-" * 80, highlight=False)

            for i, hs in enumerate(hotspots, 1):
                in_deg = hs.get("in_degree", 0)
                out_deg = hs.get("out_degree", 0)
                total = hs.get("total_connections", 0)
                lang = hs.get("lang", "?")

                # Risk indicator
                risk = ""
                if in_deg > 10:
                    risk = " [HIGH DEPENDENTS]"
                elif in_deg > 5:
                    risk = " [moderate dependents]"

                console.print(
                    f"  {i:2}. {hs['id'][:60]:<60} ({lang})",
                    highlight=False
                )
                console.print(
                    f"      in:{in_deg:<4} out:{out_deg:<4} total:{total:<4}{risk}",
                    highlight=False
                )

                # Show call graph info if available
                if "call_in" in hs:
                    console.print(
                        f"      calls: in:{hs['call_in']:<4} out:{hs['call_out']:<4}",
                        highlight=False
                    )

            console.print("-" * 80, highlight=False)
            console.print(
                "\nInterpretation: High 'in' = many dependents (risky to change)",
                highlight=False
            )
            console.print(
                "               High 'out' = many dependencies (complex)",
                highlight=False
            )

    except Exception as e:
        console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e


@graph.command("query", cls=RichCommand)
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--uses", help="Find who uses/imports this module or calls this function")
@click.option("--calls", help="Find what this module/function calls or depends on")
@click.option("--nearest-path", nargs=2, help="Find shortest path between two nodes")
@click.option(
    "--format", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
def graph_query(db, uses, calls, nearest_path, format):
    """Query dependency and call graph relationships interactively.

    Find who uses a module, what a function calls, or trace paths between nodes.
    Returns upstream (callers/importers) or downstream (callees/dependencies)
    relationships from the pre-built graph database.

    AI ASSISTANT CONTEXT:
      Purpose: Interactive graph relationship queries
      Input: .pf/graphs.db (from 'aud graph build')
      Output: List of related nodes (table or JSON format)
      Prerequisites: aud full, aud graph build
      Integration: Architecture exploration, impact analysis
      Performance: <1 second (indexed graph lookups)

    EXAMPLES:
      aud graph query --uses auth.py           # Who imports auth.py?
      aud graph query --calls send_email       # What does send_email call?
      aud graph query --nearest-path a.py b.py # Shortest path between files
      aud graph query --uses api --format json # JSON output for scripting

    TROUBLESHOOTING:
      No results found:
        -> Check node name matches exactly (case-sensitive)
        -> Run 'aud graph build' to rebuild graph
        -> Use partial name - graph may store full paths

      Graph database not found:
        -> Run 'aud graph build' first

    RELATED COMMANDS:
      aud graph build     Build the graph database
      aud graph analyze   Find cycles and hotspots
      aud impact          Change impact analysis

    See: aud manual graph, aud manual callgraph"""
    from theauditor.graph.analyzer import XGraphAnalyzer
    from theauditor.graph.store import XGraphStore

    if not any([uses, calls, nearest_path]):
        console.print("Please specify a query option:")
        console.print("  --uses MODULE     Find who uses a module")
        console.print("  --calls FUNC      Find what a function calls")
        console.print("  --nearest-path SOURCE TARGET  Find path between nodes")
        console.print("\nExample: aud graph query --uses theauditor.cli")
        return

    try:
        store = XGraphStore(db_path=db)

        results = {}

        if uses:
            deps = store.query_dependencies(uses, direction="upstream")
            call_deps = store.query_calls(uses, direction="callers")

            all_users = sorted(set(deps.get("upstream", []) + call_deps.get("callers", [])))
            results["uses"] = {
                "node": uses,
                "used_by": all_users,
                "count": len(all_users),
            }

            if format == "table":
                console.print(f"\n{uses} is used by {len(all_users)} nodes:", highlight=False)
                for user in all_users[:20]:
                    console.print(f"  - {user}", highlight=False)
                if len(all_users) > 20:
                    console.print(f"  ... and {len(all_users) - 20} more", highlight=False)

        if calls:
            deps = store.query_dependencies(calls, direction="downstream")
            call_deps = store.query_calls(calls, direction="callees")

            all_deps = sorted(set(deps.get("downstream", []) + call_deps.get("callees", [])))
            results["calls"] = {
                "node": calls,
                "depends_on": all_deps,
                "count": len(all_deps),
            }

            if format == "table":
                console.print(f"\n{calls} depends on {len(all_deps)} nodes:", highlight=False)
                for dep in all_deps[:20]:
                    console.print(f"  - {dep}", highlight=False)
                if len(all_deps) > 20:
                    console.print(f"  ... and {len(all_deps) - 20} more", highlight=False)

        if nearest_path:
            source, target = nearest_path
            import_graph = store.load_import_graph()

            analyzer = XGraphAnalyzer()
            path = analyzer.find_shortest_path(source, target, import_graph)

            results["path"] = {
                "source": source,
                "target": target,
                "path": path,
                "length": len(path) if path else None,
            }

            if format == "table":
                if path:
                    console.print(
                        f"\nPath from {source} to {target} ({len(path)} steps):", highlight=False
                    )
                    for i, node in enumerate(path):
                        prefix = "  " + ("-> " if i > 0 else "")
                        console.print(f"{prefix}{node}", highlight=False)
                else:
                    console.print(f"\nNo path found from {source} to {target}", highlight=False)

        if format == "json":
            console.print(json.dumps(results, indent=2), markup=False)

    except Exception as e:
        console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e


@graph.command("viz", cls=RichCommand)
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option(
    "--graph-type",
    type=click.Choice(["import", "call"]),
    default="import",
    help="Graph type to visualize",
)
@click.option("--out-dir", required=True, help="Output directory for visualizations")
@click.option("--limit-nodes", default=500, type=int, help="Maximum nodes to display")
@click.option(
    "--format",
    type=click.Choice(["dot", "svg", "png", "json"]),
    default="dot",
    help="Output format",
)
@click.option(
    "--view",
    type=click.Choice(["full", "cycles", "hotspots", "layers", "impact"]),
    default="full",
    help="Visualization view type",
)
@click.option(
    "--include-analysis",
    is_flag=True,
    help="Include analysis results (cycles, hotspots) in visualization",
)
@click.option("--title", help="Graph title")
@click.option(
    "--top-hotspots",
    default=10,
    type=int,
    help="Number of top hotspots to show (for hotspots view)",
)
@click.option("--impact-target", help="Target node for impact analysis (for impact view)")
@click.option("--show-self-loops", is_flag=True, help="Include self-referential edges")
def graph_viz(
    db,
    graph_type,
    out_dir,
    limit_nodes,
    format,
    view,
    include_analysis,
    title,
    top_hotspots,
    impact_target,
    show_self_loops,
):
    """Generate visual graph representations with Graphviz.

    Creates visually intelligent graphs with multiple view modes and rich visual
    encoding. Outputs DOT format by default; can generate SVG/PNG if Graphviz
    is installed.

    AI ASSISTANT CONTEXT:
      Purpose: Visualize dependency and call graphs for architecture understanding
      Input: .pf/graphs.db (from 'aud graph build')
      Output: DOT files, optionally SVG/PNG (specify --out-dir)
      Prerequisites: aud graph build (optionally aud graph analyze for cycles/hotspots)
      Integration: Architecture documentation, code review presentations
      Performance: ~1-5 seconds (graph rendering)

    VIEW MODES:
      full:     Complete graph with all nodes and edges
      cycles:   Only nodes/edges involved in dependency cycles
      hotspots: Top N most connected nodes with neighbors
      layers:   Architectural layers as subgraphs
      impact:   Highlight impact radius of changes (requires --impact-target)

    VISUAL ENCODING:
      Node Color:   Programming language (Python=blue, JS=yellow, TS=blue)
      Node Size:    Importance/connectivity (larger = more dependencies)
      Edge Color:   Red for cycles, gray for normal
      Border Width: Code churn (thicker = more changes)
      Node Shape:   box=module, ellipse=function, diamond=class

    EXAMPLES:
      aud graph viz                                    # Basic visualization
      aud graph viz --view cycles --include-analysis  # Show dependency cycles
      aud graph viz --view hotspots --top-hotspots 5  # Top 5 hotspots
      aud graph viz --view layers --include-analysis  # Architectural layers
      aud graph viz --view impact --impact-target "src/auth.py"  # Impact radius
      aud graph viz --format svg --view full          # SVG for AI analysis

    FLAG INTERACTIONS:
      --view cycles + --include-analysis: Requires 'aud graph analyze' first
      --view impact + --impact-target: Must specify target file/module
      --format svg/png: Requires Graphviz installed (apt install graphviz)

    TROUBLESHOOTING:
      "No graph found" error:
        -> Run 'aud graph build' first

      "Graphviz not found" warning:
        -> Install: apt install graphviz (Linux), brew install graphviz (Mac)
        -> DOT file still generated - use online viewer

      Empty cycles view:
        -> No cycles exist (good architecture!) or run 'aud graph analyze' first

    RELATED COMMANDS:
      aud graph build     Build the graph database first
      aud graph analyze   Generate cycles/hotspots data for richer viz
      aud graph query     Query specific relationships

    See: aud manual graph, aud manual dependencies"""
    from theauditor.graph.store import XGraphStore
    from theauditor.graph.visualizer import GraphVisualizer

    try:
        store = XGraphStore(db_path=db)

        if graph_type == "import":
            graph = store.load_import_graph()
            output_name = "import_graph"
            default_title = "Import Dependencies"
        else:
            graph = store.load_call_graph()
            output_name = "call_graph"
            default_title = "Function Call Graph"

        if not graph or not graph.get("nodes"):
            console.print(
                f"No {graph_type} graph found. Run 'aud graph build' first.", highlight=False
            )
            return

        analysis = {}
        if include_analysis:
            # Analysis data is now only in database, not in .pf/raw/
            console.print(
                "[dim]Note: Use 'aud graph analyze' for detailed analysis metrics.[/dim]"
            )

        if format == "json":
            # Output JSON to stdout
            json_output = json.dumps({"nodes": graph["nodes"], "edges": graph["edges"]}, indent=2)
            console.print(json_output, markup=False, highlight=False)
            return
        else:
            out_path = Path(out_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            visualizer = GraphVisualizer()

            options = {
                "max_nodes": limit_nodes,
                "title": title or default_title,
                "show_self_loops": show_self_loops,
            }

            console.print(
                f"Generating {format.upper()} visualization (view: {view})...", highlight=False
            )

            if view == "cycles":
                cycles = analysis.get("cycles", [])
                if not cycles:
                    if "cycles" in analysis:
                        console.print(
                            "[info]No dependency cycles detected in the codebase (good architecture!).[/info]"
                        )
                        console.print("       Showing full graph instead...")
                    else:
                        console.print(
                            "[warning]No cycles data found. Run 'aud graph analyze' first.[/warning]"
                        )
                        console.print("       Falling back to full view...")
                    dot_content = visualizer.generate_dot(graph, analysis, options)
                else:
                    console.print(f"  Showing {len(cycles)} cycles", highlight=False)
                    dot_content = visualizer.generate_cycles_only_view(graph, cycles, options)

            elif view == "hotspots":
                if not analysis.get("hotspots"):
                    from theauditor.graph.analyzer import XGraphAnalyzer

                    analyzer = XGraphAnalyzer()
                    hotspots = analyzer.identify_hotspots(graph, top_n=top_hotspots)
                    console.print(f"  Calculated {len(hotspots)} hotspots", highlight=False)
                else:
                    hotspots = analysis["hotspots"]

                console.print(f"  Showing top {top_hotspots} hotspots", highlight=False)
                dot_content = visualizer.generate_hotspots_only_view(
                    graph, hotspots, options, top_n=top_hotspots
                )

            elif view == "layers":
                from theauditor.graph.analyzer import XGraphAnalyzer

                analyzer = XGraphAnalyzer()
                layers = analyzer.identify_layers(graph)
                console.print(f"  Found {len(layers)} architectural layers", highlight=False)

                for layer_num, nodes in layers.items():
                    if layer_num is not None:
                        console.print(f"    Layer {layer_num}: {len(nodes)} nodes", highlight=False)
                dot_content = visualizer.generate_dot_with_layers(graph, layers, analysis, options)

            elif view == "impact":
                if not impact_target:
                    console.print("[error]--impact-target required for impact view[/error]")
                    raise click.ClickException("Missing --impact-target for impact view")

                from theauditor.graph.analyzer import XGraphAnalyzer

                analyzer = XGraphAnalyzer()
                impact = analyzer.analyze_impact(graph, [impact_target])

                if not impact["targets"]:
                    console.print(f"[warning]Target '{impact_target}' not found in graph[/warning]")
                    console.print("       Showing full graph instead...")
                    dot_content = visualizer.generate_dot(graph, analysis, options)
                else:
                    console.print(f"  Target: {impact_target}", highlight=False)
                    console.print(f"  Upstream: {len(impact['upstream'])} nodes", highlight=False)
                    console.print(
                        f"  Downstream: {len(impact['downstream'])} nodes", highlight=False
                    )
                    console.print(
                        f"  Total impact: {len(impact['all_impacted'])} nodes", highlight=False
                    )
                    dot_content = visualizer.generate_impact_visualization(graph, impact, options)

            else:
                console.print(
                    f"  Nodes: {len(graph['nodes'])} (limit: {limit_nodes})", highlight=False
                )
                console.print(f"  Edges: {len(graph['edges'])}", highlight=False)
                dot_content = visualizer.generate_dot(graph, analysis, options)

            output_filename = f"{output_name}_{view}" if view != "full" else output_name

            dot_file = out_path / f"{output_filename}.dot"
            with open(dot_file, "w") as f:
                f.write(dot_content)
            console.print(f"[success]DOT file saved to: {dot_file}[/success]")

            if format in ["svg", "png"]:
                try:
                    import subprocess

                    result = subprocess.run(["dot", "-V"], capture_output=True, text=True)

                    if result.returncode == 0:
                        output_file = out_path / f"{output_filename}.{format}"
                        subprocess.run(
                            ["dot", f"-T{format}", str(dot_file), "-o", str(output_file)],
                            check=True,
                        )
                        console.print(
                            f"[success]{format.upper()} image saved to: {output_file}[/success]"
                        )

                        if format == "svg":
                            console.print(
                                "  [success]SVG is AI-readable and can be analyzed for patterns[/success]"
                            )
                    else:
                        console.print(
                            f"[warning]Graphviz not found. Install it to generate {format.upper()} images:[/warning]"
                        )
                        console.print("  Ubuntu/Debian: apt install graphviz")
                        console.print("  macOS: brew install graphviz")
                        console.print("  Windows: choco install graphviz")
                        console.print(
                            f"\n  Manual generation: dot -T{format} {dot_file} -o {output_filename}.{format}",
                            highlight=False,
                        )

                except FileNotFoundError:
                    console.print(
                        f"[warning]Graphviz not installed. Cannot generate {format.upper()}.[/warning]"
                    )
                    console.print(
                        f"  Install graphviz and run: dot -T{format} {dot_file} -o {output_filename}.{format}",
                        highlight=False,
                    )
                except subprocess.CalledProcessError as e:
                    console.print(f"[error]Failed to generate {format.upper()}: {e}[/error]")

            console.print("\nVisual Encoding:")

            if view == "cycles":
                console.print("  • Red Nodes: Part of dependency cycles")
                console.print("  • Red Edges: Cycle connections")
                console.print("  • Subgraphs: Individual cycles grouped")

            elif view == "hotspots":
                console.print("  • Node Color: Red gradient (darker = higher rank)")
                console.print("  • Node Size: Total connections")
                console.print("  • Gray Nodes: Connected but not hotspots")
                console.print("  • Labels: Show in/out degree counts")

            elif view == "layers":
                console.print("  • Subgraphs: Architectural layers")
                console.print("  • Node Color: Programming language")
                console.print("  • Border Width: Code churn (thicker = more changes)")
                console.print("  • Node Size: Importance (in-degree)")

            elif view == "impact":
                console.print("  • Red Nodes: Impact targets")
                console.print("  • Orange Nodes: Upstream dependencies")
                console.print("  • Blue Nodes: Downstream dependencies")
                console.print("  • Purple Nodes: Both upstream and downstream")
                console.print("  • Gray Nodes: Unaffected")

            else:
                console.print("  • Node Color: Programming language")
                console.print("  • Node Size: Importance (larger = more dependencies)")
                console.print("  • Red Edges: Part of dependency cycles")
                console.print("  • Node Shape: box=module, ellipse=function")

    except Exception as e:
        console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e
