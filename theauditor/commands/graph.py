"""Cross-project dependency and call graph analysis."""

import json
from pathlib import Path
import click
from theauditor.config_runtime import load_runtime_config


@click.group()
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
      Prerequisites: aud index (populates refs and calls tables)
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
      aud index
      aud graph build
      aud graph analyze
      aud graph query --uses auth.py

    EXAMPLES:
      aud graph build
      aud graph analyze --workset
      aud graph query --imports database
      aud graph viz --format dot --output deps.svg

    PERFORMANCE:
      Small (<100 files):  ~2-5 seconds
      Medium (500 files):  ~10-20 seconds
      Large (2K+ files):   ~30-60 seconds

    RELATED COMMANDS:
      aud impact    # Uses graph for change impact analysis
      aud deadcode  # Uses graph for isolation detection
      aud index     # Populates refs/calls tables

    NOTE: Graph commands use separate graphs.db database (not repo_index.db).
    This is an optimization for complex graph traversal queries.

    EXAMPLE:
      aud graph query --calls api.send_email # What does send_email call?

    Output:
      .pf/graphs.db                   # SQLite database with graphs
      .pf/raw/graph_analysis.json     # Cycles, hotspots, metrics
      .pf/raw/graph_summary.json      # AI-readable summary
    """
    pass


@graph.command("build")
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--langs", multiple=True, help="Languages to process (e.g., python, javascript)")
@click.option("--workset", help="Path to workset.json to limit scope")
@click.option("--batch-size", default=200, type=int, help="Files per batch")
@click.option("--resume", is_flag=True, help="Resume from checkpoint")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--out-json", default="./.pf/raw/", help="JSON output directory")
def graph_build(root, langs, workset, batch_size, resume, db, out_json):
    """Build import and call graphs from your codebase.

    Constructs two types of graphs:
    1. Import Graph: Shows module/file dependencies (who imports what)
    2. Call Graph: Shows function relationships (who calls what)

    These graphs are the foundation for architectural analysis,
    cycle detection, and impact measurement.

    Examples:
      aud graph build                         # Full codebase
      aud graph build --langs python          # Python only
      aud graph build --workset workset.json  # Specific files
      aud graph build --resume                # Resume interrupted build

    Output:
      .pf/graphs.db - SQLite database containing:
        - import_nodes: Files and modules
        - import_edges: Import relationships
        - call_nodes: Functions and methods
        - call_edges: Call relationships

    FLAG INTERACTIONS:
      --workset + --langs: Analyze specific files in specific languages only
      --resume: Safe to use after interrupted builds (preserves partial progress)
      --batch-size: Larger = faster but more memory, smaller = slower but safer

    TROUBLESHOOTING:
      "No manifest found" error:
        Solution: Run 'aud index' first to create manifest.json

      Graph build very slow (>10 minutes):
        Cause: Large codebase or small batch size
        Solution: Increase --batch-size to 500, use --workset for subset

      Missing edges in graph:
        Cause: Dynamic imports or conditional requires not detected
        Solution: This is expected - only static imports captured

      Memory errors during build:
        Cause: Batch size too large for available RAM
        Solution: Reduce --batch-size to 100 or 50

    Note: Must run 'aud index' first to build manifest."""
    from theauditor.graph.builder import XGraphBuilder
    from theauditor.graph.store import XGraphStore
    
    try:
        # Initialize builder and store
        builder = XGraphBuilder(batch_size=batch_size, exclude_patterns=[], project_root=root)
        store = XGraphStore(db_path=db)
        
        # Load workset if provided
        file_filter = None
        workset_files = set()
        if workset:
            workset_path = Path(workset)
            if workset_path.exists():
                with open(workset_path) as f:
                    workset_data = json.load(f)
                    # Extract file paths from workset
                    workset_files = {p["path"] for p in workset_data.get("paths", [])}
                    click.echo(f"Loaded workset with {len(workset_files)} files")
        
        # Clear checkpoint if not resuming
        if not resume and builder.checkpoint_file.exists():
            builder.checkpoint_file.unlink()
        
        # Load manifest.json if it exists to use as file list
        file_list = None
        config = load_runtime_config(root)
        manifest_path = Path(config["paths"]["manifest"])
        if manifest_path.exists():
            click.echo("Loading file manifest...")
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            
            # Apply workset filtering if active
            if workset_files:
                file_list = [f for f in manifest_data if f.get("path") in workset_files]
                click.echo(f"  Filtered to {len(file_list)} files from workset")
            else:
                file_list = manifest_data
                click.echo(f"  Found {len(file_list)} files in manifest")
        else:
            click.echo("No manifest found, using filesystem walk")
        
        # Build import graph
        click.echo("Building import graph...")
        import_graph = builder.build_import_graph(
            root=root,
            langs=list(langs) if langs else None,
            file_list=file_list,
        )
        
        # Save to database (SINGLE SOURCE OF TRUTH)
        store.save_import_graph(import_graph)

        # Dual write: Save JSON to .pf/raw/ for human/AI consumption
        raw_import = Path(".pf/raw/import_graph.json")
        raw_import.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_import, 'w') as f:
            json.dump(import_graph, f, indent=2)

        click.echo(f"  Nodes: {len(import_graph['nodes'])}")
        click.echo(f"  Edges: {len(import_graph['edges'])}")
        
        # Build call graph
        click.echo("Building call graph...")
        call_graph = builder.build_call_graph(
            root=root,
            langs=list(langs) if langs else None,
            file_list=file_list,
        )
        
        # Save to database (SINGLE SOURCE OF TRUTH)
        store.save_call_graph(call_graph)

        # Dual write: Save JSON to .pf/raw/ for human/AI consumption
        raw_call = Path(".pf/raw/call_graph.json")
        raw_call.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_call, 'w') as f:
            json.dump(call_graph, f, indent=2)

        # Call graph uses 'nodes' for functions and 'edges' for calls
        click.echo(f"  Functions: {len(call_graph.get('nodes', []))}")
        click.echo(f"  Calls: {len(call_graph.get('edges', []))}")
        
        click.echo(f"\nGraphs saved to database: {db}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e


@graph.command("build-dfg")
@click.option("--root", default=".", help="Root directory")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--repo-db", default="./.pf/repo_index.db", help="Repo index database")
def graph_build_dfg(root, db, repo_db):
    """Build data flow graph from indexed assignments and returns.

    Constructs a data flow graph showing how data flows through variable
    assignments and function returns. Uses normalized junction tables
    (assignment_sources, function_return_sources) for accurate tracking.

    Must run 'aud index' first to populate junction tables.

    Examples:
      aud graph build-dfg                  # Build DFG from current project

    Output:
      .pf/graphs.db - SQLite database with:
        - nodes (graph_type='data_flow'): Variables and return values
        - edges (graph_type='data_flow'): Assignment and return relationships

    Stats shown:
      - Total assignments processed
      - Assignments with source variables
      - Edges created
      - Unique variables tracked
    """
    from theauditor.graph.dfg_builder import DFGBuilder
    from theauditor.graph.store import XGraphStore
    from pathlib import Path

    try:
        # Check that repo_index.db exists
        repo_db_path = Path(repo_db)
        if not repo_db_path.exists():
            click.echo(f"ERROR: {repo_db} not found. Run 'aud index' first.", err=True)
            raise click.Abort()

        # Initialize builder and store
        click.echo("Initializing DFG builder...")
        builder = DFGBuilder(db_path=repo_db)
        store = XGraphStore(db_path=db)

        click.echo("Building data flow graph...")

        # Build unified graph (assignments + returns)
        graph = builder.build_unified_flow_graph(root)

        # Display stats
        stats = graph["metadata"]["stats"]
        click.echo(f"\nData Flow Graph Statistics:")
        click.echo(f"  Assignment Stats:")
        click.echo(f"    Total assignments: {stats['assignment_stats']['total_assignments']:,}")
        click.echo(f"    With source vars:  {stats['assignment_stats']['assignments_with_sources']:,}")
        click.echo(f"    Edges created:     {stats['assignment_stats']['edges_created']:,}")
        click.echo(f"  Return Stats:")
        click.echo(f"    Total returns:     {stats['return_stats']['total_returns']:,}")
        click.echo(f"    With variables:    {stats['return_stats']['returns_with_vars']:,}")
        click.echo(f"    Edges created:     {stats['return_stats']['edges_created']:,}")
        click.echo(f"  Totals:")
        click.echo(f"    Total nodes:       {stats['total_nodes']:,}")
        click.echo(f"    Total edges:       {stats['total_edges']:,}")

        # Save to graphs.db
        click.echo(f"\nSaving to {db}...")
        store.save_data_flow_graph(graph)

        # Save JSON to .pf/raw/ for immutable record
        raw_output = Path(".pf/raw/data_flow_graph.json")
        raw_output.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_output, 'w') as f:
            json.dump(graph, f, indent=2)

        click.echo(f"Data flow graph saved to {db}")
        click.echo(f"Raw JSON saved to {raw_output}")

    except FileNotFoundError as e:
        click.echo(f"ERROR: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"ERROR: Failed to build DFG: {e}", err=True)
        raise click.Abort()


@graph.command("analyze")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--out", default="./.pf/raw/graph_analysis.json", help="Output JSON path")
@click.option("--max-depth", default=3, type=int, help="Max traversal depth for impact analysis")
@click.option("--workset", help="Path to workset.json for change impact")
@click.option("--no-insights", is_flag=True, help="Skip interpretive insights (health scores, recommendations)")
def graph_analyze(db, out, max_depth, workset, no_insights):
    """Analyze dependency graphs for architectural issues and change impact.

    Performs comprehensive graph analysis to detect circular dependencies,
    architectural hotspots, and measure the blast radius of code changes.
    Generates health metrics and recommendations for improving codebase
    architecture.

    AI ASSISTANT CONTEXT:
      Purpose: Detect architectural issues via graph analysis
      Input: .pf/graphs.db (import and call graphs from 'aud graph build')
      Output: .pf/raw/graph_analysis.json (cycles, hotspots, health metrics)
      Prerequisites: aud index, aud graph build
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

      Health Metrics (unless --no-insights):
        - Graph density (connectivity level)
        - Fragility score (brittleness measure)
        - Health grade (A-F overall assessment)

    EXAMPLES:
      aud graph analyze
      aud graph analyze --workset workset.json
      aud graph analyze --no-insights --max-depth 5
      aud graph analyze --out custom_analysis.json

    FLAG INTERACTIONS:
      --workset + --max-depth: Limits impact analysis to specific files and depth
      --no-insights: Disables health scoring (faster, basic metrics only)

    TROUBLESHOOTING:
      No graphs found:
        Solution: Run 'aud graph build' first

      High fragility score:
        Cause: Many circular dependencies or high coupling
        Solution: Review hotspots and refactor to reduce coupling

      Slow analysis (>30 seconds):
        Cause: Very large graph (>10K nodes)
        Solution: Use --workset to analyze subset, increase --max-depth cautiously"""
    from theauditor.graph.analyzer import XGraphAnalyzer
    from theauditor.graph.store import XGraphStore
    
    # Try to import insights module (optional)
    insights = None
    if not no_insights:
        try:
            from theauditor.graph.insights import GraphInsights
            insights = GraphInsights()
        except ImportError:
            click.echo("Note: Insights module not available. Running basic analysis only.")
            insights = None
    
    try:
        # Load graphs from database
        store = XGraphStore(db_path=db)
        import_graph = store.load_import_graph()
        call_graph = store.load_call_graph()
        
        if not import_graph["nodes"]:
            click.echo("No graphs found. Run 'aud graph build' first.")
            return
        
        # Initialize analyzer
        analyzer = XGraphAnalyzer()
        
        # Detect cycles
        click.echo("Detecting cycles...")
        cycles = analyzer.detect_cycles(import_graph)
        click.echo(f"  Found {len(cycles)} cycles")
        if cycles and len(cycles) > 0:
            click.echo(f"  Largest cycle: {cycles[0]['size']} nodes")
        
        # Rank hotspots (if insights available)
        hotspots = []
        if insights:
            click.echo("Ranking hotspots...")
            hotspots = insights.rank_hotspots(import_graph, call_graph)
            click.echo(f"  Top 10 hotspots:")
            for i, hotspot in enumerate(hotspots[:10], 1):
                click.echo(f"    {i}. {hotspot['id'][:50]} (score: {hotspot['score']})")
        else:
            # Basic hotspot detection without scoring
            click.echo("Finding most connected nodes...")
            degrees = analyzer.calculate_node_degrees(import_graph)
            connected = sorted(
                [(k, v["in_degree"] + v["out_degree"]) for k, v in degrees.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
            click.echo(f"  Top 10 most connected nodes:")
            for i, (node, connections) in enumerate(connected, 1):
                click.echo(f"    {i}. {node[:50]} ({connections} connections)")
        
        # Calculate change impact if workset provided
        impact = None
        if workset:
            workset_path = Path(workset)
            if workset_path.exists():
                with open(workset_path) as f:
                    workset_data = json.load(f)
                    targets = workset_data.get("seed_files", [])
                    
                    if targets:
                        click.echo(f"\nCalculating impact for {len(targets)} targets...")
                        impact = analyzer.impact_of_change(
                            targets=targets,
                            import_graph=import_graph,
                            call_graph=call_graph,
                            max_depth=max_depth,
                        )
                        click.echo(f"  Upstream impact: {len(impact['upstream'])} files")
                        click.echo(f"  Downstream impact: {len(impact['downstream'])} files")
                        click.echo(f"  Total impacted: {impact['total_impacted']}")
        
        # Generate summary
        summary = {}
        if insights:
            click.echo("\nGenerating interpreted summary...")
            summary = insights.summarize(
                import_graph=import_graph,
                call_graph=call_graph,
                cycles=cycles,
                hotspots=hotspots,
            )
            
            click.echo(f"  Graph density: {summary['import_graph'].get('density', 0):.4f}")
            click.echo(f"  Health grade: {summary['health_metrics'].get('health_grade', 'N/A')}")
            click.echo(f"  Fragility score: {summary['health_metrics'].get('fragility_score', 0):.2f}")
        else:
            # Basic summary without interpretation
            click.echo("\nGenerating basic summary...")
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
            
            click.echo(f"  Nodes: {nodes_count}")
            click.echo(f"  Edges: {edges_count}")
            click.echo(f"  Density: {density:.4f}")
            click.echo(f"  Cycles: {len(cycles)}")
        
        # Save analysis results
        analysis = {
            "cycles": cycles,
            "hotspots": hotspots[:50],  # Top 50
            "impact": impact,
            "summary": summary,
        }

        # DUAL-WRITE PATTERN: Write to database for FCE performance + JSON for AI consumption
        from theauditor.utils.meta_findings import format_hotspot_finding, format_cycle_finding
        from theauditor.indexer.database import DatabaseManager

        # Prepare meta-findings for database
        meta_findings = []

        # 1. Hotspot findings
        for hotspot in hotspots[:50]:  # Top 50 hotspots
            meta_findings.append(format_hotspot_finding(hotspot))

        # 2. Cycle findings (one finding per file in cycle)
        for cycle in cycles:
            meta_findings.extend(format_cycle_finding(cycle))

        # Write findings to repo_index.db (NOT graphs.db - that's for graph storage only)
        repo_db_path = Path(".pf") / "repo_index.db"
        if repo_db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(repo_db_path.resolve()))
                db_manager.write_findings_batch(meta_findings, "graph-analysis")
                db_manager.close()
                click.echo(f"  Wrote {len(meta_findings)} graph findings to database")
            except Exception as e:
                click.echo(f"  Warning: Could not write findings to database: {e}", err=True)

        # Write JSON for AI consumption (existing behavior)
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(analysis, f, indent=2, sort_keys=True)

        click.echo(f"\nAnalysis saved to {out}")
        
        # Save metrics for ML consumption (if insights available)
        if insights and hotspots:
            metrics = {}
            for hotspot in hotspots:
                metrics[hotspot['id']] = hotspot.get('centrality', 0)
            metrics_path = Path("./.pf/raw/graph_metrics.json")
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            with open(metrics_path, "w") as f:
                json.dump(metrics, f, indent=2)
            click.echo(f"  Saved graph metrics to {metrics_path}")
        
        # Create AI-readable summary
        graph_summary = analyzer.get_graph_summary(import_graph)
        summary_path = Path("./.pf/raw/graph_summary.json")
        with open(summary_path, "w") as f:
            json.dump(graph_summary, f, indent=2)
        click.echo(f"  Saved graph summary to {summary_path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e


@graph.command("query")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--uses", help="Find who uses/imports this module or calls this function")
@click.option("--calls", help="Find what this module/function calls or depends on")
@click.option("--nearest-path", nargs=2, help="Find shortest path between two nodes")
@click.option("--format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def graph_query(db, uses, calls, nearest_path, format):
    """Query graph relationships."""
    from theauditor.graph.analyzer import XGraphAnalyzer
    from theauditor.graph.store import XGraphStore
    
    # Check if any query options were provided
    if not any([uses, calls, nearest_path]):
        click.echo("Please specify a query option:")
        click.echo("  --uses MODULE     Find who uses a module")
        click.echo("  --calls FUNC      Find what a function calls")
        click.echo("  --nearest-path SOURCE TARGET  Find path between nodes")
        click.echo("\nExample: aud graph query --uses theauditor.cli")
        return
    
    try:
        # Load graphs
        store = XGraphStore(db_path=db)
        
        results = {}
        
        if uses:
            # Find who uses this node
            deps = store.query_dependencies(uses, direction="upstream")
            call_deps = store.query_calls(uses, direction="callers")
            
            all_users = sorted(set(deps.get("upstream", []) + call_deps.get("callers", [])))
            results["uses"] = {
                "node": uses,
                "used_by": all_users,
                "count": len(all_users),
            }
            
            if format == "table":
                click.echo(f"\n{uses} is used by {len(all_users)} nodes:")
                for user in all_users[:20]:  # Show first 20
                    click.echo(f"  - {user}")
                if len(all_users) > 20:
                    click.echo(f"  ... and {len(all_users) - 20} more")
        
        if calls:
            # Find what this node calls/depends on
            deps = store.query_dependencies(calls, direction="downstream")
            call_deps = store.query_calls(calls, direction="callees")
            
            all_deps = sorted(set(deps.get("downstream", []) + call_deps.get("callees", [])))
            results["calls"] = {
                "node": calls,
                "depends_on": all_deps,
                "count": len(all_deps),
            }
            
            if format == "table":
                click.echo(f"\n{calls} depends on {len(all_deps)} nodes:")
                for dep in all_deps[:20]:  # Show first 20
                    click.echo(f"  - {dep}")
                if len(all_deps) > 20:
                    click.echo(f"  ... and {len(all_deps) - 20} more")
        
        if nearest_path:
            # Find shortest path
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
                    click.echo(f"\nPath from {source} to {target} ({len(path)} steps):")
                    for i, node in enumerate(path):
                        prefix = "  " + ("-> " if i > 0 else "")
                        click.echo(f"{prefix}{node}")
                else:
                    click.echo(f"\nNo path found from {source} to {target}")
        
        if format == "json":
            click.echo(json.dumps(results, indent=2))
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e


@graph.command("viz")
@click.option("--db", default="./.pf/graphs.db", help="SQLite database path")
@click.option("--graph-type", type=click.Choice(["import", "call"]), default="import", help="Graph type to visualize")
@click.option("--out-dir", default="./.pf/raw/", help="Output directory for visualizations")
@click.option("--limit-nodes", default=500, type=int, help="Maximum nodes to display")
@click.option("--format", type=click.Choice(["dot", "svg", "png", "json"]), default="dot", help="Output format")
@click.option("--view", type=click.Choice(["full", "cycles", "hotspots", "layers", "impact"]), default="full", 
              help="Visualization view type")
@click.option("--include-analysis", is_flag=True, help="Include analysis results (cycles, hotspots) in visualization")
@click.option("--title", help="Graph title")
@click.option("--top-hotspots", default=10, type=int, help="Number of top hotspots to show (for hotspots view)")
@click.option("--impact-target", help="Target node for impact analysis (for impact view)")
@click.option("--show-self-loops", is_flag=True, help="Include self-referential edges")
def graph_viz(db, graph_type, out_dir, limit_nodes, format, view, include_analysis, title, 
              top_hotspots, impact_target, show_self_loops):
    """Visualize graphs with rich visual encoding (Graphviz).
    
    Creates visually intelligent graphs with multiple view modes:
    
    VIEW MODES:
    - full: Complete graph with all nodes and edges
    - cycles: Only nodes/edges involved in dependency cycles
    - hotspots: Top N most connected nodes with neighbors
    - layers: Architectural layers as subgraphs
    - impact: Highlight impact radius of changes
    
    VISUAL ENCODING:
    - Node Color: Programming language (Python=blue, JS=yellow, TS=blue)
    - Node Size: Importance/connectivity (larger = more dependencies)
    - Edge Color: Red for cycles, gray for normal
    - Border Width: Code churn (thicker = more changes)
    - Node Shape: box=module, ellipse=function, diamond=class
    
    Examples:
        # Basic visualization
        aud graph viz
        
        # Show only dependency cycles
        aud graph viz --view cycles --include-analysis
        
        # Top 5 hotspots with connections
        aud graph viz --view hotspots --top-hotspots 5
        
        # Architectural layers
        aud graph viz --view layers --include-analysis
        
        # Impact analysis for a specific file
        aud graph viz --view impact --impact-target "src/auth.py"
        
        # Generate SVG for AI analysis
        aud graph viz --format svg --view full --include-analysis
    """
    from theauditor.graph.store import XGraphStore
    from theauditor.graph.visualizer import GraphVisualizer
    
    try:
        # Load the appropriate graph
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
            click.echo(f"No {graph_type} graph found. Run 'aud graph build' first.")
            return
        
        # Load analysis if requested
        analysis = {}
        if include_analysis:
            # Try to load analysis from file
            analysis_path = Path("./.pf/raw/graph_analysis.json")
            if analysis_path.exists():
                with open(analysis_path) as f:
                    analysis_data = json.load(f)
                    analysis = {
                        'cycles': analysis_data.get('cycles', []),
                        'hotspots': analysis_data.get('hotspots', []),
                        'impact': analysis_data.get('impact', {})
                    }
                click.echo(f"Loaded analysis: {len(analysis['cycles'])} cycles, {len(analysis['hotspots'])} hotspots")
            else:
                click.echo("No analysis found. Run 'aud graph analyze' first for richer visualization.")
        
        # Create output directory
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            # Simple JSON output (original behavior)
            json_file = out_path / f"{output_name}.json"
            with open(json_file, "w") as f:
                json.dump({"nodes": graph["nodes"], "edges": graph["edges"]}, f, indent=2)
            
            click.echo(f"[OK] JSON saved to: {json_file}")
            click.echo(f"  Nodes: {len(graph['nodes'])}, Edges: {len(graph['edges'])}")
        else:
            # Use new visualizer for DOT/SVG/PNG
            visualizer = GraphVisualizer()
            
            # Set visualization options
            options = {
                'max_nodes': limit_nodes,
                'title': title or default_title,
                'show_self_loops': show_self_loops
            }
            
            # Generate DOT with visual intelligence based on view mode
            click.echo(f"Generating {format.upper()} visualization (view: {view})...")
            
            if view == "cycles":
                # Cycles-only view
                cycles = analysis.get('cycles', [])
                if not cycles:
                    # Check if analysis was run but found no cycles
                    if 'cycles' in analysis:
                        click.echo("[INFO] No dependency cycles detected in the codebase (good architecture!).")
                        click.echo("       Showing full graph instead...")
                    else:
                        click.echo("[WARN] No cycles data found. Run 'aud graph analyze' first.")
                        click.echo("       Falling back to full view...")
                    dot_content = visualizer.generate_dot(graph, analysis, options)
                else:
                    click.echo(f"  Showing {len(cycles)} cycles")
                    dot_content = visualizer.generate_cycles_only_view(graph, cycles, options)
                    
            elif view == "hotspots":
                # Hotspots-only view
                if not analysis.get('hotspots'):
                    # Try to calculate hotspots on the fly
                    from theauditor.graph.analyzer import XGraphAnalyzer
                    analyzer = XGraphAnalyzer()
                    hotspots = analyzer.identify_hotspots(graph, top_n=top_hotspots)
                    click.echo(f"  Calculated {len(hotspots)} hotspots")
                else:
                    hotspots = analysis['hotspots']
                
                click.echo(f"  Showing top {top_hotspots} hotspots")
                dot_content = visualizer.generate_hotspots_only_view(
                    graph, hotspots, options, top_n=top_hotspots
                )
                
            elif view == "layers":
                # Architectural layers view
                from theauditor.graph.analyzer import XGraphAnalyzer
                analyzer = XGraphAnalyzer()
                layers = analyzer.identify_layers(graph)
                click.echo(f"  Found {len(layers)} architectural layers")
                # Filter out None keys before iterating
                for layer_num, nodes in layers.items():
                    if layer_num is not None:
                        click.echo(f"    Layer {layer_num}: {len(nodes)} nodes")
                dot_content = visualizer.generate_dot_with_layers(graph, layers, analysis, options)
                
            elif view == "impact":
                # Impact analysis view
                if not impact_target:
                    click.echo("[ERROR] --impact-target required for impact view")
                    raise click.ClickException("Missing --impact-target for impact view")
                
                from theauditor.graph.analyzer import XGraphAnalyzer
                analyzer = XGraphAnalyzer()
                impact = analyzer.analyze_impact(graph, [impact_target])
                
                if not impact['targets']:
                    click.echo(f"[WARN] Target '{impact_target}' not found in graph")
                    click.echo("       Showing full graph instead...")
                    dot_content = visualizer.generate_dot(graph, analysis, options)
                else:
                    click.echo(f"  Target: {impact_target}")
                    click.echo(f"  Upstream: {len(impact['upstream'])} nodes")
                    click.echo(f"  Downstream: {len(impact['downstream'])} nodes")
                    click.echo(f"  Total impact: {len(impact['all_impacted'])} nodes")
                    dot_content = visualizer.generate_impact_visualization(graph, impact, options)
                
            else:  # view == "full" or default
                # Full graph view
                click.echo(f"  Nodes: {len(graph['nodes'])} (limit: {limit_nodes})")
                click.echo(f"  Edges: {len(graph['edges'])}")
                dot_content = visualizer.generate_dot(graph, analysis, options)
            
            # Save DOT file with view suffix
            if view != "full":
                output_filename = f"{output_name}_{view}"
            else:
                output_filename = output_name
            
            dot_file = out_path / f"{output_filename}.dot"
            with open(dot_file, "w") as f:
                f.write(dot_content)
            click.echo(f"[OK] DOT file saved to: {dot_file}")
            
            # Generate image if requested
            if format in ["svg", "png"]:
                try:
                    import subprocess
                    
                    # Check if Graphviz is installed
                    result = subprocess.run(
                        ["dot", "-V"],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        # Generate image
                        output_file = out_path / f"{output_filename}.{format}"
                        subprocess.run(
                            ["dot", f"-T{format}", str(dot_file), "-o", str(output_file)],
                            check=True
                        )
                        click.echo(f"[OK] {format.upper()} image saved to: {output_file}")
                        
                        # For SVG, also mention AI readability
                        if format == "svg":
                            click.echo("  ✓ SVG is AI-readable and can be analyzed for patterns")
                    else:
                        click.echo(f"[WARN] Graphviz not found. Install it to generate {format.upper()} images:")
                        click.echo("  Ubuntu/Debian: apt install graphviz")
                        click.echo("  macOS: brew install graphviz")
                        click.echo("  Windows: choco install graphviz")
                        click.echo(f"\n  Manual generation: dot -T{format} {dot_file} -o {output_filename}.{format}")
                        
                except FileNotFoundError:
                    click.echo(f"[WARN] Graphviz not installed. Cannot generate {format.upper()}.")
                    click.echo(f"  Install graphviz and run: dot -T{format} {dot_file} -o {output_filename}.{format}")
                except subprocess.CalledProcessError as e:
                    click.echo(f"[ERROR] Failed to generate {format.upper()}: {e}")
            
            # Provide visual encoding legend based on view
            click.echo("\nVisual Encoding:")
            
            if view == "cycles":
                click.echo("  • Red Nodes: Part of dependency cycles")
                click.echo("  • Red Edges: Cycle connections")
                click.echo("  • Subgraphs: Individual cycles grouped")
                
            elif view == "hotspots":
                click.echo("  • Node Color: Red gradient (darker = higher rank)")
                click.echo("  • Node Size: Total connections")
                click.echo("  • Gray Nodes: Connected but not hotspots")
                click.echo("  • Labels: Show in/out degree counts")
                
            elif view == "layers":
                click.echo("  • Subgraphs: Architectural layers")
                click.echo("  • Node Color: Programming language")
                click.echo("  • Border Width: Code churn (thicker = more changes)")
                click.echo("  • Node Size: Importance (in-degree)")
                
            elif view == "impact":
                click.echo("  • Red Nodes: Impact targets")
                click.echo("  • Orange Nodes: Upstream dependencies")
                click.echo("  • Blue Nodes: Downstream dependencies")
                click.echo("  • Purple Nodes: Both upstream and downstream")
                click.echo("  • Gray Nodes: Unaffected")
                
            else:  # full view
                click.echo("  • Node Color: Programming language")
                click.echo("  • Node Size: Importance (larger = more dependencies)")
                click.echo("  • Red Edges: Part of dependency cycles")
                click.echo("  • Node Shape: box=module, ellipse=function")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e