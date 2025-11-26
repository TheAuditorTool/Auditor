"""Control Flow Graph analysis commands."""

import json
from pathlib import Path
import click
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


@click.group()
@click.help_option("-h", "--help")
def cfg():
    """Control Flow Graph complexity analysis for maintainability and testability assessment.

    Group command for analyzing function complexity via Control Flow Graphs (CFG) - directed
    graphs mapping all possible execution paths through functions. Calculates cyclomatic
    complexity (McCabe metric), identifies unreachable code blocks, measures nesting depth,
    and visualizes control flow for refactoring candidates.

    AI ASSISTANT CONTEXT:
      Purpose: Measure function complexity for maintainability risk assessment
      Input: .pf/repo_index.db (function definitions)
      Output: Complexity metrics, dead code locations, visualizations
      Prerequisites: aud index (populates functions/classes)
      Integration: Code quality gates, refactoring prioritization, test planning
      Performance: ~5-15 seconds (AST parsing + graph construction)

    SUBCOMMANDS:
      analyze: Calculate cyclomatic complexity and detect issues
      viz:     Generate visual CFG diagrams (requires Graphviz)

    KEY METRICS:
      Cyclomatic Complexity:
        - Number of linearly independent paths through code
        - McCabe metric: edges - nodes + 2 * connected_components
        - Higher = more complex = harder to test

      Dead Code Blocks:
        - Unreachable code after return/break/continue
        - Conditions that can never be true

      Nesting Depth:
        - Maximum indentation level (nested if/for/while)
        - Deep nesting indicates high cognitive load

      Loop Complexity:
        - Nested loops and nested conditions
        - Contributes to overall complexity

    MCCABE COMPLEXITY THRESHOLDS:
      1-10:   Simple, low risk, easily testable
      11-20:  Moderate, medium risk, needs attention
      21-50:  Complex, high risk, refactor candidate
      50+:    Untestable, very high risk, immediate refactor

    EXAMPLES:
      aud cfg analyze
      aud cfg analyze --complexity-threshold 15
      aud cfg analyze --find-dead-code
      aud cfg viz --function process_payment

    PERFORMANCE: ~5-15 seconds

    RELATED COMMANDS:
      aud deadcode  # Module-level isolation
      aud graph     # File-level dependencies

    NOTE: CFG analysis is function-level (not module). For module-level dead
    code detection, use 'aud deadcode'.

    EXAMPLES:
      aud cfg analyze --workset                  # Analyze changed files only
      aud cfg viz --file auth.py --function login # Visualize login function

    Output:
      .pf/raw/cfg_analysis.json  # Complexity metrics and issues
      .pf/repo_index.db          # CFG data stored in database
        - cfg_blocks table        # Basic blocks
        - cfg_edges table         # Control flow edges

    Use Cases:
      - Code review: Find overly complex functions
      - Testing: Identify hard-to-test code
      - Refactoring: Prioritize by complexity
      - Security: Complex functions hide bugs
    """
    pass


@cfg.command("analyze")
@click.option("--db", default=".pf/repo_index.db", help="Path to repository database")
@click.option("--file", help="Analyze specific file only")
@click.option("--function", help="Analyze specific function only")
@click.option("--complexity-threshold", default=10, type=int, help="Complexity threshold for reporting")
@click.option("--output", default="./.pf/raw/cfg_analysis.json", help="Output JSON file path")
@click.option("--find-dead-code", is_flag=True, help="Find unreachable code blocks")
@click.option("--workset", is_flag=True, help="Analyze workset files only")
def analyze(db, file, function, complexity_threshold, output, find_dead_code, workset):
    """Analyze control flow complexity and find issues.
    
    Examples:
        # Analyze all functions for high complexity
        aud cfg analyze --complexity-threshold 15
        
        # Find dead code in specific file
        aud cfg analyze --file src/auth.py --find-dead-code
        
        # Analyze specific function
        aud cfg analyze --function process_payment --output payment_cfg.json
    """
    from theauditor.graph.cfg_builder import CFGBuilder

    try:
        # Check if database exists
        db_path = Path(db)
        if not db_path.exists():
            click.echo(f"Database not found: {db}. Run 'aud full' first.")
            return

        # Initialize CFG builder
        builder = CFGBuilder(str(db_path))

        # Load workset if requested
        target_files = None
        if workset:
            workset_path = Path(".pf/workset.json")
            if workset_path.exists():
                with open(workset_path) as f:
                    workset_data = json.load(f)
                    target_files = {p["path"] for p in workset_data.get("paths", [])}
                    click.echo(f"Analyzing {len(target_files)} workset files")

        # Get all functions or filter
        if function:
            # Find specific function
            functions = builder.get_all_functions()
            matching = [f for f in functions if f['function_name'] == function]
            if not matching:
                click.echo(f"Function '{function}' not found")
                return
            functions = matching
        elif file:
            # Get functions from specific file
            functions = builder.get_all_functions(file_path=file)
            if not functions:
                click.echo(f"No functions found in {file}")
                return
        else:
            # Get all functions
            functions = builder.get_all_functions()

            # Filter by workset if requested
            if target_files:
                functions = [f for f in functions if f['file'] in target_files]

        click.echo(f"Analyzing {len(functions)} functions...")

        results = {
            "total_functions": len(functions),
            "complex_functions": [],
            "dead_code": [],
            "statistics": {
                "avg_complexity": 0,
                "max_complexity": 0,
                "functions_above_threshold": 0
            }
        }

        # Analyze complexity
        complex_functions = builder.analyze_complexity(
            file_path=file, 
            threshold=complexity_threshold
        )

        results["complex_functions"] = complex_functions
        results["statistics"]["functions_above_threshold"] = len(complex_functions)

        if complex_functions:
            complexities = [f['complexity'] for f in complex_functions]
            results["statistics"]["max_complexity"] = max(complexities)
            results["statistics"]["avg_complexity"] = sum(complexities) / len(complexities)

        # Display complex functions
        if complex_functions:
            click.echo(f"\n[COMPLEXITY] Found {len(complex_functions)} functions above threshold {complexity_threshold}:")
            for func in complex_functions[:10]:  # Show top 10
                click.echo(f"  • {func['function']} ({func['file']})")
                click.echo(f"    Complexity: {func['complexity']}, Blocks: {func['block_count']}, Has loops: {func['has_loops']}")
        else:
            click.echo(f"[OK] No functions exceed complexity threshold {complexity_threshold}")

        # Find dead code if requested
        if find_dead_code:
            click.echo("\n[DEAD CODE] Searching for unreachable blocks...")
            dead_blocks = builder.find_dead_code(file_path=file)
            results["dead_code"] = dead_blocks

            if dead_blocks:
                click.echo(f"Found {len(dead_blocks)} unreachable blocks:")

                # Group by function
                by_function = {}
                for block in dead_blocks:
                    key = f"{block['function']} ({block['file']})"
                    if key not in by_function:
                        by_function[key] = []
                    by_function[key].append(block)

                for func_key, blocks in list(by_function.items())[:5]:  # Show first 5 functions
                    click.echo(f"  • {func_key}: {len(blocks)} unreachable blocks")
                    for block in blocks[:2]:  # Show first 2 blocks per function
                        click.echo(f"    - {block['block_type']} block at lines {block['start_line']}-{block['end_line']}")
            else:
                click.echo("[OK] No unreachable code detected")

        # DUAL-WRITE PATTERN: Write to database for FCE performance + JSON for AI consumption
        from theauditor.utils.meta_findings import format_complexity_finding
        from theauditor.indexer.database import DatabaseManager

        # Prepare meta-findings for database
        meta_findings = []

        # Format complex function findings
        for func in complex_functions:
            meta_findings.append(format_complexity_finding(func))

        # Write findings to repo_index.db
        repo_db_path = Path(".pf") / "repo_index.db"
        if repo_db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(repo_db_path.resolve()))
                db_manager.write_findings_batch(meta_findings, "cfg-analysis")
                db_manager.close()
                click.echo(f"  Wrote {len(meta_findings)} CFG findings to database")
            except Exception as e:
                click.echo(f"  Warning: Could not write findings to database: {e}", err=True)

        # Write CFG results to JSON
        output_path = Path(".pf") / "raw" / "cfg.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        click.echo(f"\n[OK] CFG analysis saved to {output_path}")

        # Summary statistics
        click.echo("\n[SUMMARY]")
        click.echo(f"  Total functions analyzed: {len(functions)}")
        click.echo(f"  Functions above complexity {complexity_threshold}: {len(complex_functions)}")
        if complex_functions:
            click.echo(f"  Maximum complexity: {results['statistics']['max_complexity']}")
            click.echo(f"  Average complexity of complex functions: {results['statistics']['avg_complexity']:.1f}")
        if find_dead_code:
            click.echo(f"  Unreachable blocks found: {len(results['dead_code'])}")

        # Close database connection
        builder.close()

    except Exception as e:
        logger.error(f"CFG analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e))


@cfg.command("viz")
@click.option("--db", default=".pf/repo_index.db", help="Path to repository database")
@click.option("--file", required=True, help="File containing the function")
@click.option("--function", required=True, help="Function name to visualize")
@click.option("--output", help="Output file path (default: function_name.dot)")
@click.option("--format", type=click.Choice(["dot", "svg", "png"]), default="dot", help="Output format")
@click.option("--show-statements", is_flag=True, help="Include statements in blocks")
@click.option("--highlight-paths", is_flag=True, help="Highlight execution paths")
def viz(db, file, function, output, format, show_statements, highlight_paths):
    """Visualize control flow graph for a function.
    
    Examples:
        # Generate DOT file for a function
        aud cfg viz --file src/auth.py --function validate_token
        
        # Generate SVG with statements shown
        aud cfg viz --file src/payment.py --function process_payment --format svg --show-statements
        
        # Highlight execution paths
        aud cfg viz --file src/api.py --function handle_request --highlight-paths
    """
    from theauditor.graph.cfg_builder import CFGBuilder

    try:
        # Check if database exists
        db_path = Path(db)
        if not db_path.exists():
            click.echo(f"Database not found: {db}. Run 'aud full' first.")
            return

        # Initialize CFG builder
        builder = CFGBuilder(str(db_path))

        # Get CFG for the function
        click.echo(f"Loading CFG for {function} in {file}...")
        cfg = builder.get_function_cfg(file, function)

        if not cfg['blocks']:
            click.echo(f"No CFG data found for {function} in {file}")
            click.echo("Make sure the function was indexed with 'aud full'")
            return

        click.echo(f"Found {len(cfg['blocks'])} blocks and {len(cfg['edges'])} edges")

        # Generate DOT with enhanced visualization
        if show_statements:
            # Enhance DOT with statement details
            dot_content = builder.export_dot(file, function)
            # Add statement details to each block
            for block in cfg['blocks']:
                if block['statements']:
                    # Modify DOT to show statements
                    old_label = f"{block['type']}\\n{block['start_line']}-{block['end_line']}"
                    stmt_lines = [f"{s['type']}@{s['line']}" for s in block['statements'][:3]]
                    stmt_str = '\\n'.join(stmt_lines)
                    new_label = f"{old_label}\\n{stmt_str}"
                    dot_content = dot_content.replace(old_label, new_label)
        else:
            dot_content = builder.export_dot(file, function)

        # Highlight paths if requested
        if highlight_paths:
            paths = builder.get_execution_paths(file, function, max_paths=5)
            if paths:
                click.echo(f"Found {len(paths)} execution paths (showing first 5)")
                # Add path highlighting to DOT
                for i, path in enumerate(paths[:5]):
                    click.echo(f"  Path {i+1}: {' → '.join(map(str, path))}")

        # Determine output file
        if not output:
            output = f"{function}_cfg.{format}"
        elif not output.endswith(f".{format}"):
            output = f"{output}.{format}"

        output_path = Path(output)

        # Save DOT file
        if format == "dot":
            with open(output_path, 'w') as f:
                f.write(dot_content)
            click.echo(f"[OK] DOT file saved to {output_path}")
            click.echo(f"  View with: dot -Tsvg {output_path} -o {output_path.stem}.svg")
        else:
            # Generate image format
            import subprocess

            # First save DOT
            dot_path = output_path.with_suffix('.dot')
            with open(dot_path, 'w') as f:
                f.write(dot_content)

            try:
                # Convert to requested format
                result = subprocess.run(
                    ["dot", f"-T{format}", str(dot_path), "-o", str(output_path)],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    click.echo(f"[OK] {format.upper()} saved to {output_path}")
                    # Clean up temporary DOT file
                    dot_path.unlink()
                else:
                    click.echo(f"[ERROR] Graphviz failed: {result.stderr}")
                    click.echo(f"  DOT file saved to {dot_path}")
            except FileNotFoundError:
                click.echo("[ERROR] Graphviz not installed. Install it to generate images:")
                click.echo("  Ubuntu/Debian: apt install graphviz")
                click.echo("  macOS: brew install graphviz")
                click.echo("  Windows: choco install graphviz")
                click.echo(f"\n  DOT file saved to {dot_path}")
                click.echo(f"  Manual generation: dot -T{format} {dot_path} -o {output_path}")

        # Display metrics
        metrics = cfg['metrics']
        click.echo("\n[METRICS]")
        click.echo(f"  Cyclomatic Complexity: {metrics['cyclomatic_complexity']}")
        click.echo(f"  Decision Points: {metrics['decision_points']}")
        click.echo(f"  Maximum Nesting: {metrics['max_nesting_depth']}")
        click.echo(f"  Has Loops: {metrics['has_loops']}")

        # Close database connection
        builder.close()

    except Exception as e:
        logger.error(f"CFG visualization failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e))